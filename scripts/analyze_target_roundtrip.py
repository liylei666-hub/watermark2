"""CPU-only integrity checks and paired descriptive target-roundtrip analysis."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import argparse, csv, json, statistics, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import verify_archive as a
from cpu_latent_audit import decomposition

def analyze(run):
    p=a.load(run/'protocol.json'); group=a.load(run/'group_execution.json')
    assert a.sha(run/'protocol.json')==(run/'protocol.sha256').read_text().strip()
    assert p['planned_seeds']==[101,102,103] and p['arms']==['same_prompt','changed_prompt']
    assert group['completed']==group['started']==p['planned_seeds'] and not group['failures']
    for field in ['code_hashes','input_hashes']:
        for path,h in p[field].items(): assert a.sha(a.resolve(path))==h
    prior=a.load(ROOT/'reports/07_prompt_control/per_sample.json')
    rows=[]; max_error=0; wall=0
    for seed in p['planned_seeds']:
        d=run/f'seed_{seed}';cfg=a.load(d/'config.json');m=a.load(d/'metrics.json')
        assert cfg['protocol_sha256']==a.sha(run/'protocol.json')
        assert cfg['seed']==m['seed']==seed and cfg['evaluation_only'] and m['evaluation_only']
        assert cfg['dtype']=='float32' and cfg['resolution']==512 and cfg['scheduler']=='DDIM'
        assert cfg['generation_steps']==cfg['inversion_steps']==50
        assert cfg['generation_guidance']==7.5 and cfg['inversion_guidance']==1 and cfg['inversion_prompt']==''
        assert cfg['gs_threshold']==.70703125 and cfg['gs_comparator']=='>'
        assert cfg['gpu_physical_index']==p['selected_gpu']==0 and cfg['gpu_uuid']==p['uuid']
        oldcfg=a.load(a.resolve(next(k for k in cfg['input_hashes'] if k.endswith('/config.json'))))
        assert cfg['gs_parameters']==oldcfg['gs_parameters']
        assert cfg['model_revision']==oldcfg['model_revisions'][cfg['model_id']]
        for path,h in cfg['input_hashes'].items():assert a.sha(a.resolve(path))==h
        man=a.load(d/'tensor_manifest.json');assert man['config_sha256']==a.sha(d/'config.json')
        for rec in list(man['arrays'].values())+list(man['images'].values()):assert a.sha(a.resolve(rec['path']))==rec['sha256']
        replay=a.load(d/'reference_replay.json')
        assert replay['bitwise_equal'] and replay['max_abs_error']==0
        assert replay['archived_sha256']==replay['recomputed_sha256']==a.sha(a.resolve(cfg['reference_inversion']))
        assert a.sha(d/'recomputed_reference_zT.npy')==replay['recomputed_sha256']
        assert a.load(d/'actual_model_loads.json')==[dict(model_id=cfg['model_id'],snapshot=cfg['model_snapshot'])]
        dev=a.load(d/'device.json');assert dev['uuid']==p['uuid'] and dev['visible_count']==1 and dev['logical_device']=='cuda:0'
        pre=a.load(d/'preflight.json')['gpu'];assert pre['row'][:2]==['0',p['uuid']] and not pre['compute_apps']
        assert int(pre['row'][4])<=50 and int(pre['row'][5])==0
        pid=a.load(d/'process.json')['pid']
        for line in (d/'gpu_monitor.jsonl').read_text().splitlines():
            g=json.loads(line);assert g['row'][:2]==['0',p['uuid']]
            assert all(int(proc[1])==pid for proc in g['compute_apps'])
        ex=a.load(d/'execution.json');assert ex['exit_code']==0 and ex['failure'] is None and ex['wall_time_seconds']<=1200
        assert 'COMPLETED_TARGET_ROUNDTRIP' in (d/'stdout.log').read_text()
        wall+=ex['wall_time_seconds']
        z=a.float32_npy(a.resolve(cfg['original_latent']));ref=a.float32_npy(d/'recomputed_reference_zT.npy')
        for arm in p['arms']:
            metric=m['results'][arm];image=man['images'][arm]
            assert a.load(d/(arm+'_frozen.json'))==image and image['event']=='before_target_inversion'
            y=a.float32_npy(d/(arm+'_inverted_zT.npy'));c=a.cosine(z,y);cr=a.cosine(ref,y)
            max_error=max(max_error,abs(c-metric['cosine_to_original']),abs(cr-metric['cosine_to_reference_inverse']))
            assert metric['gs_detected']==(metric['bit_accuracy']>.70703125)
            old=next(r for r in prior if r['seed']==seed and r['arm']==arm and r['role']=='candidate')
            assert old['original_latent_sha256']==a.sha(a.resolve(cfg['original_latent']))
            rows.append(dict(seed=seed,arm=arm,**decomposition(z,y),
                reference_cosine=a.cosine(z,ref),cosine_to_reference_inverse=cr,
                proxy_cosine=old['cosine'],target_minus_proxy_cosine=c-old['cosine'],
                bit_accuracy=metric['bit_accuracy'],gs_detected=metric['gs_detected'],
                proxy_bit_accuracy=old['bit_accuracy'],image_sha256=image['sha256'],
                image_path=a.resolve(image['path']).relative_to(ROOT).as_posix()))
    assert max_error<1e-12 and abs(wall-group['stage_gpu_process_seconds'])<1e-8
    assert abs(wall+group['prior_gpu_process_seconds']-group['cumulative_gpu_process_seconds'])<1e-8
    aggregates={arm:dict(n=3,gs_pass_count=sum(r['gs_detected'] for r in rows if r['arm']==arm),
        **{key:statistics.mean(r[key] for r in rows if r['arm']==arm) for key in
           ['cosine','reference_cosine','cosine_to_reference_inverse','proxy_cosine','target_minus_proxy_cosine','bit_accuracy']})
        for arm in p['arms']}
    return rows,dict(stage='08',data_role='evaluator_development_control',completed_model_processes=3,
        candidate_count=6,reference_replay_bitwise_equal_count=3,aggregates=aggregates,
        max_abs_cosine_readback_error=max_error,protocol_sha256=a.sha(run/'protocol.json'),
        analysis_code_sha256=a.sha(__file__),**group,analysis_device='cpu',
        geometry_threshold=None,geometry_accepted=None,formal_new_attack_evaluation=False,
        interpretation='Paired target self-roundtrip intervention; target internals remain evaluator-only. Model pipelines differ jointly, so this does not isolate architecture or VAE causality.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('run');ap.add_argument('--output',required=True);args=ap.parse_args()
    rows,summary=analyze(Path(args.run).resolve());out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    for name,data in [('per_sample',rows),('summary',summary)]:
        (out/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    with (out/'per_sample.csv').open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2))
