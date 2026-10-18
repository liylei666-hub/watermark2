"""Exact CPU even/odd decomposition of predeclared symmetric probes."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import json,sys,hashlib
from pathlib import Path

def split(center,minus,plus):
    even=(plus+minus)/2-center
    odd=(plus-minus)/2
    reduction=center-minus
    if abs((odd-even)-reduction)>1e-12:raise ValueError('Decomposition identity failed')
    return dict(even_shift=even,odd_direction_effect=odd,descent_reduction=reduction)

source=Path(sys.argv[1]);data=json.loads(source.read_text(encoding='utf-8'));rows=[]
for task in data['tasks']:
    row=dict(task_id=task['task_id'],target={},proxy={})
    for direction in ['vae','inverse']:
        values=task['rows']
        row['target'][direction]=split(values['cover']['mse'],values[direction+'_descent']['mse'],values[direction+'_ascent']['mse'])
        row['proxy'][direction]={}
        for loss in ['vae','inverse']:
            values=task['proxy_loss_readback']
            row['proxy'][direction][loss]=split(values['cover'][loss],values[direction+'_descent'][loss],values[direction+'_ascent'][loss])
    row['target_odd_difference']=row['target']['inverse']['odd_direction_effect']-row['target']['vae']['odd_direction_effect']
    row['target_even_difference']=row['target']['inverse']['even_shift']-row['target']['vae']['even_shift']
    if abs(row['target_odd_difference']-row['target_even_difference']-task['primary_inverse_minus_vae_reduction'])>1e-12:
        raise ValueError('Primary contrast does not recombine')
    rows.append(row)
result=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),tasks=rows,
    mean_target_odd_difference=sum(r['target_odd_difference'] for r in rows)/len(rows),
    mean_target_even_difference=sum(r['target_even_difference'] for r in rows)/len(rows),
    interpretation='Exact finite-step algebra from predetermined plus/minus probes; not a gradient/Hessian estimate or component-causality proof',new_model_experiments_run=0)
with Path(sys.argv[2]).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in result.items() if k!='tasks'}))
