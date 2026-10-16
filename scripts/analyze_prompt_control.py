"""Read-only verification and descriptive analysis of frozen paired controls."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import argparse, csv, json, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import verify_archive as archive
from cpu_latent_audit import decomposition

def analyze(run):
    p = archive.load(run/'protocol.json')
    assert archive.sha(run/'protocol.json') == (run/'protocol.sha256').read_text().strip()
    assert p['seeds']==[101,102,103] and p['arms_in_order']==['same_prompt','changed_prompt']
    assert p['gpu_physical_index']==0 and p['allowed_gpu_physical_indices']==[0,1,2]
    for f,h in p['code_hashes'].items(): assert archive.sha(archive.resolve(f))==h
    group=archive.load(run/'group_execution.json')
    rows=[];bindings={}; errors=[]
    for seed in p['seeds']:
        for arm in p['arms_in_order']:
            case=run/f'seed_{seed}_{arm}'
            if case.name not in group['completed']: continue
            d=case/'evaluator_only';cfg=archive.load(d/'config.json')
            assert cfg['protocol_sha256']==archive.sha(run/'protocol.json')
            assert cfg['threshold']==p['gs_threshold'] and cfg['threshold_comparator']==p['gs_comparator']
            assert cfg['gs_parameters']==p['gs_parameters'] and cfg['dtype']==p['dtype']
            assert cfg['model_revisions']==p['model_revisions']
            assert cfg['arguments']['seed']==seed
            expected=dict(p['base_arguments'],seed=seed)
            if arm=='same_prompt':expected['attacker_prompt']=expected['target_prompt']
            assert cfg['arguments']==expected
            man,diag,mr,error=archive.check_recorded_run(case,d/'config.json');errors.append(error)
            assert archive.load(d/'actual_model_loads.json')
            loads={r['model_id']:r['actual_snapshot'] for r in archive.load(d/'actual_model_loads.json')}
            assert loads==p['model_snapshots']
            frozen=archive.load(d/'candidate_before_evaluation.json')
            assert frozen['event']=='before_target_validate'
            assert archive.sha(archive.resolve(frozen['path']))==frozen['sha256']==man['images']['1']['sha256']
            assert frozen['candidate_id']==cfg['candidate_id']
            device=archive.load(d/'device.json')
            assert device['uuid']==p['gpu_uuid'] and device['visible_count']==1 and device['logical_device']=='cuda:0'
            pre=archive.load(case/'pre_run_gpu.json')['gpu']
            assert pre['row'][:2]==['0',p['gpu_uuid']] and not pre['compute_apps']
            assert int(pre['row'][4])<=50 and int(pre['row'][5])==0
            pid=archive.load(case/'process.json')['pid']
            for line in (case/'monitor.jsonl').read_text().splitlines():
                g=json.loads(line)
                assert g['row'][:2]==['0',p['gpu_uuid']]
                assert all(int(a[1])==pid for a in g['compute_apps'])
            bindings[(seed,arm)]=man
            z=archive.float32_npy(archive.resolve(man['tensors']['target_original_wm_zT']['path']))
            for role,step in [('reference',-1),('candidate',1)]:
                name='target_inverted_reference_zT' if step==-1 else 'target_inverted_forged_zT'
                y=archive.float32_npy(archive.resolve(man['tensors'][name]['path']))
                rows.append(dict(seed=seed,arm=arm,role=role,**decomposition(z,y),
                    bit_accuracy=float(mr[step]['bit_accuracy']),gs_detected=mr[step]['detection_successful']=='True',
                    image_sha256=man['images'][str(step)]['sha256'],
                    image_path=archive.resolve(man['images'][str(step)]['path']).relative_to(ROOT).as_posix(),
                    original_latent_sha256=man['tensors']['target_original_wm_zT']['sha256'],
                    copied_reference=man['images']['-1']['sha256']==man['images']['1']['sha256']))
    pairs=[]
    for seed in p['seeds']:
        if not all((seed,arm) in bindings for arm in p['arms_in_order']):continue
        a,b=[bindings[(seed,arm)] for arm in p['arms_in_order']]
        assert a['images']['-1']['sha256']==b['images']['-1']['sha256']
        for k in ['target_original_wm_zT','target_inverted_reference_zT']:
            assert a['tensors'][k]['sha256']==b['tensors'][k]['sha256']
        aa,bb=[next(r for r in rows if r['seed']==seed and r['arm']==arm and r['role']=='candidate') for arm in p['arms_in_order']]
        pairs.append(dict(seed=seed,reference_pairing_verified=True,**{
            metric+'_same_minus_changed':aa[metric]-bb[metric]
            for metric in ['cosine','coordinate_sign_agreement','magnitude_cosine','bit_accuracy']}))
    aggregates={}
    for arm in p['arms_in_order']:
        rr=[r for r in rows if r['arm']==arm and r['role']=='candidate']
        refs={r['seed']:r for r in rows if r['arm']==arm and r['role']=='reference'}
        if rr: aggregates[arm]=dict(n=len(rr),gs_pass_count=sum(r['gs_detected'] for r in rr),
            reference_valid_count=sum(r['gs_detected'] for r in refs.values()),
            candidate_pass_among_reference_valid=sum(r['gs_detected'] and refs[r['seed']]['gs_detected'] for r in rr),
            **{k:dict(mean=statistics.mean(r[k] for r in rr),min=min(r[k] for r in rr),max=max(r[k] for r in rr))
            for k in ['cosine','coordinate_sign_agreement','magnitude_cosine','bit_accuracy']})
    pair_means={k:statistics.mean(r[k] for r in pairs) for k in pairs[0] if k.endswith('_same_minus_changed')} if pairs else {}
    used=sum(archive.load(run/c/'execution.json')['wall_time_seconds'] for c in group['started'])
    assert abs(used-group['cumulative_gpu_process_seconds'])<1e-8 and used<=7200
    historical=archive.load(run/'historical_integrity.json');assert not historical['changed']
    summary=dict(stage='07',data_role='development_control',run_dir=run.relative_to(ROOT).as_posix(),
        started=len(group['started']),completed=len(group['completed']),planned=6,failures=group['failures'],
        paired_seeds=len(pairs),aggregates=aggregates,paired_mean_differences=pair_means,
        gpu_physical_index=0,gpu_uuid=p['gpu_uuid'],gpu_process_seconds=used,remaining_gpu_process_seconds=7200-used,
        new_bytes_remote=group['new_bytes'],model_processes_started=len(group['started']),
        max_abs_cosine_readback_error=max(errors) if errors else None,
        historical_files_verified=historical['checked'],historical_changes=historical['changed'],
        candidate_prefreeze_verified=True if rows else None,permission_isolation_implemented=False,
        geometry_threshold=None,geometry_accepted=None,full_official_geometry_evaluation_completed=False,
        formal_new_attack_evaluation=False,analysis_device='cpu',analysis_loads_models=False,
        protocol_sha256=archive.sha(run/'protocol.json'),analysis_code_sha256=archive.sha(__file__),
        interpretation='Paired descriptive prompt intervention under fixed proxy pipeline; not population ASR, causal architecture attribution or full geometric acceptance')
    return rows,pairs,summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('run');ap.add_argument('--output',required=True);args=ap.parse_args()
    rows,pairs,summary=analyze(Path(args.run).resolve());out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    for name,data in [('per_sample',rows),('paired_contrasts',pairs)]:
        (out/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if data:
            with (out/(name+'.csv')).open('x',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
