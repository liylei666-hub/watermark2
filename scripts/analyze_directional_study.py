"""CPU-only readback of a complete, fixed directional study; no candidate selection."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import argparse,json,sys,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent/'directional_study'))
import interface as i
import delivery as d

def latent(path):
    a=np.load(path,allow_pickle=False)
    if a.dtype!=np.float32 or a.shape!=(1,4,64,64) or not np.isfinite(a).all():
        raise ValueError('Invalid saved latent')
    return a.astype(np.float64)

def metrics(a,b):
    denom=np.linalg.norm(a)*np.linalg.norm(b)
    return dict(mse=float(np.mean((a-b)**2)),cosine=None if denom==0 else float(np.sum(a*b)/denom))

def analyze(root):
    root=Path(root).resolve()
    if i.read(root/'status.json').get('completed') is not True:
        raise ValueError('Study incomplete; do not produce complete-study estimates')
    queue=i.verified_queue(root);evaluation=i.read(root/'evaluator_results/summary.json')
    if not evaluation['completed'] or len(evaluation['rows'])!=28 or len(queue)!=28:
        raise ValueError('Incomplete evaluation')
    if [r['input'] for r in evaluation['rows']]!=queue:raise ValueError('Evaluation order/input differs from seal')
    tasks=[]
    for task in range(1,5):
        private=root/'evaluator_results'/str(task)
        nr=latent(private/'reference/target_inverse.npy');nc=latent(private/'cover/target_inverse.npy')
        baseline=metrics(nc,nr);rows={}
        attack=root/'attack_outputs'/str(task);summary=i.read(attack/'summary.json')
        if not summary['completed']:raise ValueError('Incomplete attack')
        for kind in ['reference','cover',*d.CONDITIONS]:
            path=private/kind/'target_inverse.npy';z=latent(path)
            saved=i.read(private/kind/'metrics.json')
            if i.sha(path)!=saved['target_inverse']['sha256']:raise ValueError('Target tensor changed')
            if bool(saved['gs_detected'])!=(saved['bit_accuracy']>181/256):raise ValueError('GS strict decision mismatch')
            m=metrics(z,nr);m['mse_reduction_from_cover']=baseline['mse']-m['mse']
            m['bit_accuracy']=saved['bit_accuracy'];m['gs_detected']=saved['gs_detected'];rows[kind]=m
        # Recompute every proxy loss from stored tensors, rather than trusting logged scalars.
        zr=latent(attack/'reference_proxy_z.npy');pr=latent(attack/'reference_proxy_inverse.npy')
        recomputed={}
        for kind in ['cover',*d.CONDITIONS]:
            recomputed[kind]=dict(vae=metrics(latent(attack/(kind+'_proxy_z.npy')),zr)['mse'],
                inverse=metrics(latent(attack/(kind+'_proxy_inverse.npy')),pr)['mse'])
            for objective in ['vae','inverse']:
                if not np.isclose(recomputed[kind][objective],summary['proxy_losses'][kind][objective],rtol=1e-5,atol=1e-6):
                    raise ValueError('Proxy loss readback disagrees')
        gradients={k:np.load(attack/(k+'_pixel_gradient.npy'),allow_pickle=False) for k in ['vae','inverse']}
        with Image.open(root/'attack_inputs'/str(task)/'cover.png') as im:cover=np.array(im)
        candidates,support,distortion=d.build(cover,gradients['vae'],gradients['inverse'],800+task)
        for kind,array in candidates.items():
            with Image.open(attack/'probes'/(kind+'.png')) as im:
                if not np.array_equal(np.array(im),array):raise ValueError('Candidate is not the prescribed gradient-sign delivery')
        finite={}
        for objective in ['vae','inverse']:
            delta=(candidates[objective+'_ascent'].astype(np.float64)-cover)/255
            finite[objective]=d.derivative_check(gradients[objective],delta,
                recomputed[objective+'_descent'][objective],recomputed[objective+'_ascent'][objective])
        tasks.append(dict(task_id=task,identity_offset=1 if task<=2 else 2,rows=rows,distortion=distortion,
            proxy_loss_readback=recomputed,finite_difference_float64_readback=finite,
            primary_inverse_minus_vae_reduction=rows['inverse_descent']['mse_reduction_from_cover']-rows['vae_descent']['mse_reduction_from_cover'],
            finite_difference_runtime=summary['finite_difference_checks']))
    executions=[]
    for p in sorted(root.rglob('execution.json')):
        record=i.read(p)
        if record['exit_code']!=0 or record['completed'] is not True:raise ValueError('Failed model process')
        executions.append(dict(path=p.relative_to(root).as_posix(),sha256=i.sha(p),**record))
    if len(executions)!=7:raise ValueError('Expected seven model processes')
    return dict(status='verified',tasks=tasks,executions=executions,
        model_process_seconds=sum(r['elapsed_seconds'] for r in executions),
        ordinary_gs_counts={k:sum(t['rows'][k]['gs_detected'] for t in tasks) for k in ['reference','cover',*d.CONDITIONS]},
        primary_mean=float(np.mean([t['primary_inverse_minus_vae_reduction'] for t in tasks])),
        identity_cluster_means={str(o):float(np.mean([t['primary_inverse_minus_vae_reduction'] for t in tasks if t['identity_offset']==o])) for o in [1,2]},
        scientific_role='four development pairs in two identity clusters; no population or novel-method claim',
        content_pass=None,full_defense_acceptance=None,gpu_used_by_analysis=False,models_loaded_by_analysis=False)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    result=analyze(args.run)
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(status=result['status'],primary_mean=result['primary_mean'],ordinary_gs_counts=result['ordinary_gs_counts'])))
