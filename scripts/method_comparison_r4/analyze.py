"""CPU analysis of the frozen comparison, retaining the one launched missing task."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import datetime,json,math,sys
from pathlib import Path
import numpy as np
from PIL import Image
from common import c,IDS,METHODS,origin,verify_source,verify_delivery,load,BASE

def pixels(path):
    with Image.open(path) as im:
        if im.mode!='RGB' or im.size!=(512,512):raise ValueError('Unexpected pixels')
        return np.asarray(im).copy()

def analyze(folder,private_check=False):
    folder=Path(folder);project=folder.parent.parent;cfg=c.read(project/'protocols/27_method_runtime_r4.json');meta=c.read(folder/'inheritance.json')
    if not c.read(folder/'status.json').get('completed'):raise ValueError('Continuation is not complete')
    if c.read(folder/'design.json')!=cfg['design']:raise ValueError('Design changed')
    for rel,h in cfg['copied_files'].items():
        if c.sha(folder/rel)!=h:raise ValueError('Inherited artifact changed')
    for rel,h in cfg['source_files'].items():
        if c.sha(project/cfg['source_run']/rel)!=h:raise ValueError('Original evidence changed')
    seal=verify_delivery(folder);sealed_at=datetime.datetime.fromisoformat(seal['sealed_at_utc'])
    expected={f'{role}_{batch}' for role in ('reference','cover','evaluate') for batch in range(3)}|{f'attack_outputs/{sid}/{method}' for sid in IDS for method in METHODS}
    actual={p.parent.relative_to(folder).as_posix() for p in folder.rglob('execution.json')}
    if actual!=expected-set(meta['completed'])-set(meta['failed']):raise ValueError('Continuation process inventory mismatch')
    executions=[]
    for name in sorted(expected):
        failed=name in meta['failed'];out=verify_source(folder,meta['failed'][name]) if failed else origin(folder,name)
        e=c.read(out/'execution.json');cmd=c.read(out/'command.json')
        if cfg['allowed_gpu_uuids'].get(str(e['gpu_index']))!=e['gpu_uuid'] or cmd['gpu_uuid']!=e['gpu_uuid']:raise ValueError('Device association failed')
        inherited=name in meta['completed'] or failed
        role='attack' if name.startswith('attack_outputs/') else 'eval'
        runtime=project/('protocols/27_method_'+role+'_runtime_'+('r2' if inherited else 'r4')+'.json')
        if cmd['runtime_sha256']!=c.sha(runtime):raise ValueError('Runtime binding changed')
        if failed:
            if e['completed'] or e['exit_code']==0 or (out/'candidate.png').exists():raise ValueError('Failed process misclassified')
        else:
            if not e['completed'] or e['exit_code']!=0 or e['timed_out']:raise ValueError('Unexpected failed process')
            pre=c.read(out/'device_preimport.json');row=pre['rows'][0]
            if len(pre['rows'])!=1 or pre['compute_apps'] or row[:3]!=[str(e['gpu_index']),e['gpu_uuid'],'NVIDIA GeForce RTX 3090'] or int(row[3])>50 or int(row[4])!=0:raise ValueError('Preimport gate failed')
            for file in ['preflight.jsonl']+([] if inherited else ['child_preflight.jsonl']):
                gate=[json.loads(line) for line in (out/file).read_text().splitlines()]
                if len(gate)<4 or gate[-1]['event']!='idle_verified':raise ValueError('Idle gate incomplete')
                for g in gate[-4:-1]:
                    if g['event']!='sample' or g['compute_apps'] or g['row'][:3]!=row[:3] or int(g['row'][4])>50 or int(g['row'][5])!=0:raise ValueError('Strict idle samples changed')
            marker='COMPLETED_COVER_'+('ATTACK' if role=='attack' else 'EVALUATION' if name.startswith('evaluate_') else 'PREPARATION')
            if marker not in (out/'stdout.log').read_text() or not c.read(out/'summary.json')['completed']:raise ValueError('Missing completion evidence')
        if name.startswith('evaluate_'):
            if datetime.datetime.fromisoformat(e['started_at_utc'])<=sealed_at:raise ValueError('Evaluation preceded sealing')
            if c.read(out/'summary.json')['delivery_seal_sha256']!=c.sha(folder/'delivery_sealed.json'):raise ValueError('Evaluator seal changed')
        executions.append(dict(path=(out/'execution.json').relative_to(project).as_posix(),sha256=c.sha(out/'execution.json'),gpu_process_wall_seconds=e['elapsed_seconds'],exit_code=e['exit_code'],completed=e['completed']))
    rows=[];scores=[];decoded=0;identities=[]
    if private_check:
        private=load('private_gs_state_cpu',BASE/'reference_reliability/private_state.py')
        sys.path.insert(0,str(BASE/'cross_generator'))
        decoder=load('independent_decoder_cpu',BASE/'cross_generator/verify_message_scores.py')
    for sid in IDS:
        task=cfg['design']['tasks'][sid-1];inputs=folder/'attack_inputs'/str(sid)
        for role in ('reference','cover'):
            prep=folder/(role+'_'+str((sid-1)//4))/str(sid);rec=c.read(prep/'record.json')
            if rec['image']!=c.png_record(prep/(role+'.png')) or c.sha(prep/(role+'.png'))!=c.sha(inputs/(role+'.png')):raise ValueError('Preparation image mismatch')
            if rec['seed']!=task[role+'_seed'] or rec['prompt']!=task[role+'_prompt']:raise ValueError('Task mismatch')
            if rec['original_noise']['sha256']!=c.sha(prep/'original_noise.npy'):raise ValueError('Noise association changed')
            if role=='reference':
                identities.append(rec['encryption_fingerprints'])
                if private_check:raw=private.load(project/cfg['private_folder'],sid,rec['encryption_fingerprints'])
        local_scores={}
        for kind in ('reference','cover')+METHODS:
            if f'attack_outputs/{sid}/{kind}' in meta['failed']:continue
            out=folder/('evaluate_'+str((sid-1)//4))/(str(sid)+'_'+kind);metric=c.read(out/'metrics.json')
            image=inputs/(kind+'.png') if kind in ('reference','cover') else folder/'attack_outputs'/str(sid)/kind/'candidate.png'
            if metric['task_id']!=sid or metric['kind']!=kind or metric['image']!=c.png_record(image) or metric['inverse']['sha256']!=c.sha(out/'target_inverse.npy'):raise ValueError('Evaluation association mismatch')
            z=np.load(out/'target_inverse.npy',allow_pickle=False)
            if z.dtype!=np.float32 or z.shape!=(1,4,64,64) or not np.isfinite(z).all():raise ValueError('Invalid inverse')
            ba=metric['bit_accuracy']
            if not 0<=ba<=1 or metric['gs_detected']!=(ba>.70703125):raise ValueError('Strict GS rule changed')
            if private_check:
                if decoder.decode(z,raw)!=ba:raise ValueError('Independent GS decoding differs')
                decoded+=1
            scores.append(dict(task_id=sid,kind=kind,bit_accuracy=ba,gs_detected=metric['gs_detected']));local_scores[kind]=ba
        cover=pixels(inputs/'cover.png');reference=pixels(inputs/'reference.png')
        for method in METHODS:
            name=f'attack_outputs/{sid}/{method}';failed=name in meta['failed'];out=folder/name
            source=verify_source(folder,meta['failed'][name]) if failed else origin(folder,name);ex=c.read(source/'execution.json')
            row=dict(task_id=sid,prompt_group=task['prompt_group'],method=method,status='failed' if failed else 'completed',reference_bit_accuracy=local_scores['reference'],cover_bit_accuracy=local_scores['cover'],process_seconds=ex['elapsed_seconds'],core_seconds=None,optimization_seconds=None,bit_accuracy=None,gs_detected=None,cover_mse_rgb01=None,cover_psnr_db=None,identical_to_cover=None,identical_to_reference=None,formal_content_label=None,full_defense_acceptance=None)
            if failed:
                row['failure_reason']='Original preimport idle gate rejected 1% utilization; no candidate, preserved without retry.'
                rows.append(row);continue
            image=pixels(out/'candidate.png');summary=c.read(out/'summary.json');timing=summary['timing']
            if summary['task_id']!=sid or summary['method']!=method or summary['candidate']!=c.read(out/'candidate_frozen.json'):raise ValueError('Attack binding changed')
            delta=(image.astype(np.float64)-cover.astype(np.float64))/255;mse=float(np.mean(delta**2))
            core=timing['reference_encoding_and_optimization_seconds'] if method=='jain' else timing['reference_and_cover_preparation_seconds']+timing['optimization_seconds']
            if method=='jain':
                arr=np.load(out/'final_float.npy',allow_pickle=False);expected_pixels=(np.clip(arr*.5+.5,0,1)*255).astype(np.uint8)[0].transpose(1,2,0)
                if not np.array_equal(image,expected_pixels):raise ValueError('Jain PNG differs from saved float')
            row.update(bit_accuracy=local_scores[method],gs_detected=local_scores[method]>.70703125,cover_mse_rgb01=mse,cover_psnr_db=None if mse==0 else -10*math.log10(mse),identical_to_cover=bool(np.array_equal(image,cover)),identical_to_reference=bool(np.array_equal(image,reference)),core_seconds=core,optimization_seconds=timing.get('optimization_seconds'))
            rows.append(row)
    if len(scores)!=59 or len(rows)!=36 or any(len({fp[k] for fp in identities})!=12 for k in ('message','key','nonce')):raise ValueError('Incomplete scores or repeated identity')
    by={(x['task_id'],x['method']):x for x in rows};paired=[]
    for sid in IDS:
        a=by[(sid,'imprint')];b=by[(sid,'delivery')]
        ratio=b['cover_mse_rgb01']/a['cover_mse_rgb01'] if a['cover_mse_rgb01'] else (1. if b['cover_mse_rgb01']==0 else None)
        paired.append(dict(task_id=sid,bit_accuracy_difference=b['bit_accuracy']-a['bit_accuracy'],pass_difference=int(b['gs_detected'])-int(a['gs_detected']),pixel_mse_ratio=ratio,core_time_ratio=b['core_seconds']/a['core_seconds']))
    summaries={}
    for method in METHODS:
        group=[x for x in rows if x['method']==method];ok=[x for x in group if x['status']=='completed']
        summaries[method]=dict(planned_tasks=12,delivered=len(ok),failed=12-len(ok),gs_pass_count=sum(x['gs_detected'] for x in ok),delivered_and_gs_pass_rate_over_all_tasks=sum(x['gs_detected'] for x in ok)/12,
            conditional_mean_bit_accuracy=float(np.mean([x['bit_accuracy'] for x in ok])),conditional_median_pixel_mse=float(np.median([x['cover_mse_rgb01'] for x in ok])),conditional_mean_psnr_db=float(np.mean([x['cover_psnr_db'] for x in ok if x['cover_psnr_db'] is not None])),conditional_median_core_seconds=float(np.median([x['core_seconds'] for x in ok])),total_process_seconds=sum(x['process_seconds'] for x in group))
    refs=sum(x['gs_detected'] for x in scores if x['kind']=='reference');rule=cfg['design']['decision_rule']
    mse_ratio=None if any(x['pixel_mse_ratio'] is None for x in paired) else float(np.median([x['pixel_mse_ratio'] for x in paired]))
    time_ratio=float(np.median([x['core_time_ratio'] for x in paired]));pass_gain=sum(x['pass_difference'] for x in paired)
    gates=dict(all_12_references_valid=refs==12,minimum_3_additional_gs_passes=pass_gain>=rule['minimum_additional_gs_passes_vs_imprint'],median_mse_ratio_at_most_1_05=None if mse_ratio is None else mse_ratio<=rule['max_median_pixel_mse_ratio_vs_imprint'],median_core_time_ratio_at_most_1_15=time_ratio<=rule['max_median_core_time_ratio_vs_imprint'])
    passed=all(v is True for v in gates.values());decision=rule['if_all_pass'] if passed else rule['missing_required_evidence'] if refs!=12 or mse_ratio is None else rule['otherwise']
    return dict(verified=True,rows=rows,scores=scores,summary=summaries,paired_differences=paired,valid_references=refs,gs_pass_gain=pass_gain,mean_bit_accuracy_difference=float(np.mean([p['bit_accuracy_difference'] for p in paired])),median_paired_pixel_mse_ratio=mse_ratio,median_paired_core_time_ratio=time_ratio,decision=decision,decision_gates=gates,decision_gate_passed=passed,
        primary_pairs_complete=12,secondary_jain_missing_tasks=[2],secondary_missingness_policy='No replacement; 12-task attempt denominator, conditional numeric summaries labeled explicitly.',model_processes=45,successful_model_processes=44,failed_model_processes=1,model_process_seconds=sum(x['gpu_process_wall_seconds'] for x in executions),execution_records=executions,independent_gs_scores_checked=decoded,images_checked=59,private_material_exported=False,gpu_used=False,models_loaded=False,full_defense_acceptance=None,formal_human_reviews=0,novelty_established=False,analysis_code_sha256=c.sha(__file__))

if __name__=='__main__':
    result=analyze(sys.argv[1],'--private-check' in sys.argv[3:]);c.write(Path(sys.argv[2]),result)
    print(json.dumps({k:result[k] for k in ('verified','summary','decision','model_processes','model_process_seconds','independent_gs_scores_checked')},indent=2))
