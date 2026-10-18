"""Post-completion CPU verification and predeclared outcome of the full comparison."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import datetime,json,math,sys
from pathlib import Path
import numpy as np
from PIL import Image
from common import c,IDS,METHODS,private_module,verify_delivery

def pixels(path):
    with Image.open(path) as im:
        if im.mode!='RGB' or im.size!=(512,512):raise ValueError('Unexpected pixels')
        return np.asarray(im).copy()

def analyze(folder,private_check=False):
    folder=Path(folder);project=folder.parent.parent;cfg=c.read(project/'protocols/27_method_runtime_r2.json')
    if c.read(folder/'status.json').get('completed') is not True:raise ValueError('Full comparison not complete')
    if c.read(folder/'design.json')!=cfg['design']:raise ValueError('Design changed')
    seal=verify_delivery(folder);sealed_at=datetime.datetime.fromisoformat(seal['sealed_at_utc'])
    expected={f'{role}_{batch}' for role in ('reference','cover','evaluate') for batch in range(3)}
    expected|={f'attack_outputs/{sid}/{method}' for sid in IDS for method in METHODS}
    actual={p.parent.relative_to(folder).as_posix() for p in folder.rglob('execution.json')}
    if actual!=expected:raise ValueError('Model process inventory differs from planned 45')
    executions=[]
    for name in sorted(expected):
        out=folder/name;e=c.read(out/'execution.json');cmd=c.read(out/'command.json')
        if not e['completed'] or e['exit_code']!=0 or e['timed_out']:raise ValueError('Model process failed')
        if cfg['allowed_gpu_uuids'].get(str(e['gpu_index']))!=e['gpu_uuid'] or cmd['gpu_uuid']!=e['gpu_uuid']:raise ValueError('Device association failed')
        pre=c.read(out/'device_preimport.json');row=pre['rows'][0]
        if len(pre['rows'])!=1 or pre['compute_apps'] or row[:3]!=[str(e['gpu_index']),e['gpu_uuid'],'NVIDIA GeForce RTX 3090'] or int(row[3])>50 or int(row[4])!=0:raise ValueError('Preimport gate evidence failed')
        gate=[json.loads(line) for line in (out/'preflight.jsonl').read_text().splitlines()]
        if gate[-1]['event']!='idle_verified':raise ValueError('No idle verification')
        for g in gate[-4:-1]:
            if g['event']!='sample' or g['compute_apps'] or g['row'][:3]!=row[:3] or int(g['row'][4])>50 or int(g['row'][5])!=0:raise ValueError('Idle samples changed')
        if name.startswith('evaluate_'):
            if datetime.datetime.fromisoformat(e['started_at_utc'])<=sealed_at:raise ValueError('Evaluation preceded candidate seal')
            if c.read(out/'summary.json')['delivery_seal_sha256']!=c.sha(folder/'delivery_sealed.json'):raise ValueError('Evaluator seal changed')
        runtime='attack' if name.startswith('attack_outputs/') else 'eval'
        if cmd['runtime_sha256']!=c.sha(project/('protocols/27_method_'+runtime+'_runtime_r2.json')):raise ValueError('Runtime association changed')
        marker='COMPLETED_COVER_'+('ATTACK' if runtime=='attack' else 'EVALUATION' if name.startswith('evaluate_') else 'PREPARATION')
        if marker not in (out/'stdout.log').read_text() or not c.read(out/'summary.json')['completed']:raise ValueError('Completion marker missing')
        executions.append(dict(path=(out/'execution.json').relative_to(project).as_posix(),sha256=c.sha(out/'execution.json'),gpu_process_wall_seconds=e['elapsed_seconds'],exit_code=e['exit_code']))
    rows=[];scores=[];decoded=0;identities=[]
    if private_check:
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cross_generator'))
        from verify_message_scores import decode
        private=private_module()
    for sid in IDS:
        task=cfg['design']['tasks'][sid-1];inputs=folder/'attack_inputs'/str(sid)
        for role in ('reference','cover'):
            prep=folder/(role+'_'+str((sid-1)//4))/str(sid);rec=c.read(prep/'record.json')
            if rec['image']!=c.png_record(prep/(role+'.png')) or c.sha(prep/(role+'.png'))!=c.sha(inputs/(role+'.png')):raise ValueError('Prepared image association changed')
            if rec['seed']!=task[role+'_seed'] or rec['prompt']!=task[role+'_prompt']:raise ValueError('Task configuration changed')
            if rec['original_noise']['sha256']!=c.sha(prep/'original_noise.npy'):raise ValueError('Original noise changed')
            if role=='reference':
                identities.append(rec['encryption_fingerprints'])
                if private_check:raw=private.load(project/'private_eval'/folder.name,sid,rec['encryption_fingerprints'])
        local_scores={}
        for kind in ('reference','cover')+METHODS:
            out=folder/('evaluate_'+str((sid-1)//4))/(str(sid)+'_'+kind);metric=c.read(out/'metrics.json')
            image=inputs/(kind+'.png') if kind in ('reference','cover') else folder/'attack_outputs'/str(sid)/kind/'candidate.png'
            if metric['task_id']!=sid or metric['kind']!=kind or metric['image']!=c.png_record(image) or metric['inverse']['sha256']!=c.sha(out/'target_inverse.npy'):raise ValueError('Evaluator input association changed')
            z=np.load(out/'target_inverse.npy',allow_pickle=False)
            if z.dtype!=np.float32 or z.shape!=(1,4,64,64) or not np.isfinite(z).all():raise ValueError('Invalid inverse tensor')
            ba=metric['bit_accuracy']
            if not 0<=ba<=1 or metric['gs_detected']!=(ba>.70703125):raise ValueError('Strict GS rule mismatch')
            if private_check:
                if decode(z,raw)!=ba:raise ValueError('Independent GS decode mismatch')
                decoded+=1
            scores.append(dict(task_id=sid,kind=kind,bit_accuracy=ba,gs_detected=metric['gs_detected']));local_scores[kind]=ba
        cover=pixels(inputs/'cover.png');reference=pixels(inputs/'reference.png')
        for method in METHODS:
            out=folder/'attack_outputs'/str(sid)/method;image=pixels(out/'candidate.png');summary=c.read(out/'summary.json');timing=summary['timing']
            if summary['task_id']!=sid or summary['method']!=method or summary['candidate']!=c.read(out/'candidate_frozen.json'):raise ValueError('Attack binding changed')
            delta=(image.astype(np.float64)-cover.astype(np.float64))/255;mse=float(np.mean(delta**2))
            core=timing['reference_encoding_and_optimization_seconds'] if method=='jain' else timing['reference_and_cover_preparation_seconds']+timing['optimization_seconds']
            if method=='jain':
                arr=np.load(out/'final_float.npy',allow_pickle=False)
                expected_pixels=(np.clip(arr*.5+.5,0,1)*255).astype(np.uint8)[0].transpose(1,2,0)
                if not np.array_equal(image,expected_pixels):raise ValueError('Jain output differs from retained float')
            rows.append(dict(task_id=sid,prompt_group=task['prompt_group'],method=method,bit_accuracy=local_scores[method],gs_detected=local_scores[method]>.70703125,
                reference_bit_accuracy=local_scores['reference'],cover_bit_accuracy=local_scores['cover'],cover_mse_rgb01=mse,cover_psnr_db=None if mse==0 else -10*math.log10(mse),
                identical_to_cover=bool(np.array_equal(image,cover)),identical_to_reference=bool(np.array_equal(image,reference)),core_seconds=core,
                optimization_seconds=timing.get('optimization_seconds'),formal_content_label=None,full_defense_acceptance=None))
    if any(len({fp[k] for fp in identities})!=12 for k in ('message','key','nonce')):raise ValueError('GS identities repeated')
    by={(x['task_id'],x['method']):x for x in rows}
    paired=[]
    for sid in IDS:
        a=by[(sid,'imprint')];b=by[(sid,'delivery')]
        ratio=b['cover_mse_rgb01']/a['cover_mse_rgb01'] if a['cover_mse_rgb01'] else (1. if b['cover_mse_rgb01']==0 else None)
        paired.append(dict(task_id=sid,bit_accuracy_difference=b['bit_accuracy']-a['bit_accuracy'],pass_difference=int(b['gs_detected'])-int(a['gs_detected']),
            pixel_mse_ratio=ratio,core_time_ratio=b['core_seconds']/a['core_seconds']))
    summaries={m:dict(tasks=12,gs_pass_count=sum(x['gs_detected'] for x in rows if x['method']==m),
        mean_bit_accuracy=float(np.mean([x['bit_accuracy'] for x in rows if x['method']==m])),
        median_pixel_mse=float(np.median([x['cover_mse_rgb01'] for x in rows if x['method']==m])),
        mean_psnr_db=float(np.mean([x['cover_psnr_db'] for x in rows if x['method']==m and x['cover_psnr_db'] is not None])),
        median_core_seconds=float(np.median([x['core_seconds'] for x in rows if x['method']==m]))) for m in METHODS}
    refs=sum(x['gs_detected'] for x in scores if x['kind']=='reference');rule=cfg['design']['decision_rule']
    mse_ratio=None if any(x['pixel_mse_ratio'] is None for x in paired) else float(np.median([x['pixel_mse_ratio'] for x in paired]))
    time_ratio=float(np.median([x['core_time_ratio'] for x in paired]));pass_gain=sum(x['pass_difference'] for x in paired)
    passed=refs==12 and mse_ratio is not None and pass_gain>=rule['minimum_additional_gs_passes_vs_imprint'] and mse_ratio<=rule['max_median_pixel_mse_ratio_vs_imprint'] and time_ratio<=rule['max_median_core_time_ratio_vs_imprint']
    decision=rule['if_all_pass'] if passed else rule['missing_required_evidence'] if refs!=12 or mse_ratio is None else rule['otherwise']
    return dict(verified=True,checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=rows,scores=scores,summary=summaries,paired_differences=paired,
        valid_references=refs,gs_pass_gain=pass_gain,mean_bit_accuracy_difference=float(np.mean([p['bit_accuracy_difference'] for p in paired])),
        median_paired_pixel_mse_ratio=mse_ratio,median_paired_core_time_ratio=time_ratio,decision=decision,decision_gate_passed=passed,
        model_processes=45,model_process_seconds=sum(x['gpu_process_wall_seconds'] for x in executions),execution_records=executions,
        independent_gs_scores_checked=decoded,images_checked=60,private_material_exported=False,gpu_used=False,models_loaded=False,
        full_defense_acceptance=None,formal_human_reviews=0,novelty_established=False,analysis_code_sha256=c.sha(__file__))

if __name__=='__main__':
    result=analyze(sys.argv[1],len(sys.argv)>3 and sys.argv[3]=='--private-check');c.write(Path(sys.argv[2]),result)
    print(json.dumps({k:result[k] for k in ('verified','summary','decision','model_processes','model_process_seconds','independent_gs_scores_checked')},indent=2))
