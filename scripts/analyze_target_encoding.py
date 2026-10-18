"""CPU comparison of fixed image representations at encoding and inversion."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '': raise SystemExit('CPU-only analysis')
import json
import sys
from pathlib import Path
import numpy as np
from analyze_endpoint_transfer import metrics, selftest, sha


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def array(path, expected=None):
    if expected is not None and sha(path) != expected: raise ValueError('Array hash changed')
    value=np.load(path,allow_pickle=False)
    if value.dtype!=np.float32 or value.shape!=(1,4,64,64) or not np.isfinite(value).all():
        raise ValueError('Invalid latent')
    return value


def analyze(root,run):
    root,run=Path(root).resolve(),Path(run).resolve()
    cfg=read(root/'protocols/19_target_encoding.json')
    protocol_sha=sha(root/'protocols/19_target_encoding.json')
    if protocol_sha!=(root/'protocols/19_target_encoding.sha256').read_text().strip():
        raise ValueError('Protocol changed')
    execution,summary=read(run/'execution.json'),read(run/'summary.json')
    if execution['exit_code']!=0 or execution['timed_out'] or not execution['completed']:
        raise ValueError('Run unsuccessful')
    if not summary['completed'] or summary['protocol_sha256']!=protocol_sha or len(summary['rows'])!=12:
        raise ValueError('Summary invalid')
    if 'COMPLETED_TARGET_ENCODING' not in (run/'stdout.log').read_text(): raise ValueError('Missing completion marker')
    if summary['target_inversion_calls']!=0 or summary['target_encoding_calls']!=12 or summary['attack_feedback']:
        raise ValueError('Operation scope mismatch')
    old=root/'runs/17_cover_pilot_20261017T214442Z'
    proxy=root/'runs/18_endpoint_residual_20261018T003948Z'
    candidates=read(old/'delivery_sealed.json')['candidates']
    expected={(t,r) for t in [1,2,3] for r in ['reference','cover','imprint','jain']}
    if {(r['task_id'],r['role']) for r in summary['rows']}!=expected: raise ValueError('Task coverage changed')
    arrays={};bindings=[]
    for row in summary['rows']:
        task,role=row['task_id'],row['role'];key=f'{task}/{role}'
        rec=cfg['inputs'][key];prefix='/data0/liyanlei/watermark_research/'
        if not rec['path'].startswith(prefix):raise ValueError('Unknown input root')
        image=root/rec['path'][len(prefix):]
        if sha(image)!=rec['sha256'] or row['input_sha256']!=rec['sha256']:raise ValueError('Image binding failed')
        if role in ['imprint','jain']:
            seal=next(r for r in candidates if r['task_id']==task and r['method']==role)
            if seal['candidate_sha256']!=row['input_sha256']:raise ValueError('Candidate seal differs')
        new=row['target_encoding']
        if new['path']!=role+'_z.npy':raise ValueError('Unexpected output path')
        arrays[(task,'target_z0',role)]=array(run/str(task)/new['path'],new['sha256'])
        pm=read(proxy/str(task)/'metrics.json')['arrays']
        p_name=role+'_png' if role in ['imprint','jain'] else role
        for space,suffix in [('proxy_z0','_z'),('proxy_zT','_inverse')]:
            name=p_name+suffix
            arrays[(task,space,role)]=array(proxy/str(task)/(name+'.npy'),pm[name]['sha256'])
        target_rec=read(old/f'evaluator_results/{task}/{role}/metrics.json')['target_inverse']
        arrays[(task,'target_zT',role)]=array(old/f'evaluator_results/{task}/{role}/target_inverse.npy',target_rec['sha256'])
        bindings.append(dict(task_id=task,role=role,input_sha256=row['input_sha256'],target_z0_sha256=new['sha256']))
    rows=[]
    for task in [1,2,3]:
        spaces={}
        for space in ['proxy_z0','target_z0','proxy_zT','target_zT']:
            ref=arrays[(task,space,'reference')]
            values={role:metrics(arrays[(task,space,role)],ref) for role in ['cover','imprint','jain']}
            base=values['cover']['mse']
            for value in values.values():value['mse_reduction_from_cover']=None if base==0 else (base-value['mse'])/base
            spaces[space]=dict(values=values,
                lower_mse='imprint' if values['imprint']['mse']<values['jain']['mse'] else 'jain' if values['jain']['mse']<values['imprint']['mse'] else 'tie',
                higher_cosine='imprint' if values['imprint']['cosine']>values['jain']['cosine'] else 'jain' if values['jain']['cosine']>values['imprint']['cosine'] else 'tie')
        rows.append(dict(task_id=task,spaces=spaces))
    return dict(status='verified',selftest=selftest(),rows=rows,bindings=bindings,arrays_checked=48,
        new_target_encodings=12,existing_arrays=36,execution=execution,protocol_sha256=protocol_sha,
        scaling_factor=summary['scaling_factor'],data_role='development_exploratory_posthoc',
        attack_feedback=False,full_defense_acceptance=None,causal_component_effect=None)


if __name__=='__main__':
    result=analyze(sys.argv[1],sys.argv[2])
    with Path(sys.argv[3]).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
