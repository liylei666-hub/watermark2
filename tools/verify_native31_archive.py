"""Model-free public archive verification for the fixed stage31 calibration."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only verification requires empty CUDA visibility')
import ast,datetime,hashlib,json,math,statistics,sys
from pathlib import Path
import numpy as np
from PIL import Image
from analyze_native_calibration import analyze,sha,read,POINTS

def verify(project):
    project=Path(project);root=project/'runs/31_native_calibration_20261024T190323Z'
    result=read(root/'analysis.json');seal=read(root/'results_sealed.json');cand=read(root/'candidates_sealed.json')
    assert sha(root/'analysis.json')==seal['analysis_sha256']
    recomputed=analyze(root);saved=read(root/'postrun_analysis_v2.json')
    assert recomputed['checkpoints']==saved['checkpoints'] and recomputed['max_mse_readback_error']==0
    jobs=['prepare']+[f'attack_{i}' for i in range(1,5)]+['evaluate'];bindings=0;costs={};flags={};calls={}
    for name in jobs:
        folder=root/name;ex=read(folder/'execution.json');out=ex['outcome']
        assert out['completed'] and out['exit_code']==0 and out['stop_reason'] is None
        assert sha(folder/'execution.json')==seal['executions'][name]==read(folder/'execution_seal.json')['sha256']
        for rel,digest in out['artifacts'].items():assert sha(folder/rel)==digest;bindings+=1
        process=read(folder/'process.json');uuid=process['gpu_uuid'];env=process['environment']
        assert uuid in ('GPU-aafaf524-a6f4-f646-a2b5-7d243e80c8a5','GPU-af8ecfa2-a36f-798c-9762-0a3cfb8a1fcd')
        assert env['CUDA_VISIBLE_DEVICES']==uuid and env['CUDA_DEVICE_ORDER']=='PCI_BUS_ID' and env['HF_HUB_OFFLINE']=='1'
        costs[name]=dict(process_wall_seconds=out['process_wall_seconds'])
        if name.startswith('attack_'):
            summary=read(folder/'summary.json');opt=read(folder/'optimization.json')
            assert summary['actual_updates']==151 and len(opt['updates'])==151 and opt['mask'] is None and opt['target_scores_seen']==0
            for n,row in enumerate(opt['updates'],1):assert row['actual_update']==n and row['official_loop_index']==n-1 and math.isfinite(row['loss_before_update']) and row['update_seconds']>0
            assert sorted(map(int,opt['checkpoints']))==list(POINTS)
            for n in POINTS:assert opt['checkpoints'][str(n)]['adam_step']==n
            for row in opt['scheduler_calls']:assert row['timesteps']==list(range(1,982,20))
            calls[name]=dict(count=len(opt['scheduler_calls']),endpoint_alphas=sorted(set(x['endpoint_alpha_cumprod'] for x in opt['scheduler_calls'])))
            costs[name].update(summary['timing']);costs[name]['synchronized_update_seconds']=sum(x['update_seconds'] for x in opt['updates'])
            assert abs(summary['timing']['core_seconds']-summary['timing']['reference_and_cover_preparation_seconds']-summary['timing']['optimization_and_export_seconds'])<1e-8
            flags[name]=read(folder/'parameter_flags.json');assert flags[name]['unet']['requires_grad']==0
    evaluator=read(root/'evaluate/summary.json')
    for row in evaluator['scheduler_calls']:assert row['timesteps']==list(range(1,982,20))
    calls['evaluate']=dict(count=len(evaluator['scheduler_calls']),endpoint_alphas=sorted(set(x['endpoint_alpha_cumprod'] for x in evaluator['scheduler_calls'])))
    arrays=list(root.rglob('*.npy'))
    for path in arrays:
        value=np.load(path,allow_pickle=False);assert value.dtype==np.float32 and value.shape==(1,4,64,64) and np.isfinite(value).all()
        if path.name.endswith('_adam_sq.npy'):assert (value>=0).all()
    parse=datetime.datetime.fromisoformat
    assert parse(cand['sealed_at_utc'])<parse(read(root/'evaluate/process.json')['started_at_utc'])
    controls=[{k:r[k] for k in ('task_id','label','bit_accuracy','gs_detected')} for r in result['rows'] if r['label'] in ('reference','cover')]
    assert len(controls)==8 and all(x['bit_accuracy']==1 and x['gs_detected'] for x in controls if x['label']=='reference')
    oldpath=project/'audit_sources/psnr_versions/43eec7e2b82ffbc947a88785a1b7a9963abb5a09.py'
    node=next(n for n in ast.parse(oldpath.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='psnr_PIL');scope=dict(Image=Image,np=np,math=math)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(oldpath),'exec'),scope)
    old_rows=[]
    for row in result['rows']:
        if row['label'] not in list(map(str,POINTS)):continue
        sid=row['task_id']
        with Image.open(root/f'attack_{sid}'/f'update_{row["label"]}.png') as im:a=im.copy()
        with Image.open(root/'prepare'/str(sid)/'cover.png') as im:b=im.copy()
        old_rows.append(dict(task_id=sid,actual_update=int(row['label']),old_buggy_psnr_db=float(scope['psnr_PIL'](a,b)),correct_psnr_db=row['psnr_db']))
    weights=read(root/'weight_integrity_retrospective.json');assert weights['timing']=='retrospective_after_run_not_prelaunch_seal' and parse(weights['audit_started_at_utc'])>parse(seal['finished_at_utc'])
    assert set(x['role'] for x in weights['weights'])=={'proxy','target'}
    official_errors=[abs(x['psnr_db']-x['official_torchmetrics_psnr_db']) for x in result['rows'] if x['psnr_db'] is not None]
    return dict(status='passed',raw_files=sum(p.is_file() for p in root.rglob('*')),execution_artifact_bindings_verified=bindings,model_processes=6,float32_arrays_verified=len(arrays),candidate_pngs=20,evaluated_images=28,independent_public_pixel_mse_error=0.0,private_decoder_receipt_count=result['independent_cpu_redecodes'],private_decoder_scope='Server private28-redecode receipt preserved; public verification cannot independently recover secret messages.',checkpoints=saved['checkpoints'],controls=controls,costs=costs,scheduler_calls=calls,parameter_flags=flags,max_float64_vs_official_float32_psnr_difference=max(official_errors),old_metric_replay=dict(source_sha256=sha(oldpath),rows=old_rows,primary151_mean_buggy_psnr_db=statistics.mean(x['old_buggy_psnr_db'] for x in old_rows if x['actual_update']==151)),weights_manifest_sha256=sha(root/'weight_integrity_retrospective.json'),retrospective_weight_files=len(weights['weights']),retrospective_weight_bytes=sum(x['bytes'] for x in weights['weights']),end_to_end_wall_seconds=(parse(seal['finished_at_utc'])-parse(read(root/'launch_intent.json')['started_at_utc'])).total_seconds(),model_process_wall_seconds=sum(x['process_wall_seconds'] for x in costs.values()),attack_core_seconds=sum(x['core_seconds'] for k,x in costs.items() if k.startswith('attack_')),candidate_seal_sha256=sha(root/'candidates_sealed.json'),result_seal_sha256=sha(root/'results_sealed.json'),source_runtime_sha256=read(root/'launch_intent.json')['runtime_sha256'],new_models_loaded_by_verifier=0)
if __name__=='__main__':print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
