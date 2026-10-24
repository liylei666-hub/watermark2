"""Frozen stage29 contracts. Importing this module does not import model libraries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path('/data0/liyanlei/watermark_research')
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(1, str(BASE/'cover_pilot'))
import contract as c
import runtime as r
sys.path.insert(1, str(BASE/'parallel_execution'))
import launcher as launch
import scheduler as sched

METHODS = ('pixel50','pixel10')
STEPS = {'pixel50':50,'pixel10':10}
COUNT = 16

def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def schedule(method):
    if method not in SCHEDULES:
        raise ValueError('Unknown frozen method')
    return [dict(inversion_steps=n,updates=k) for n,k in SCHEDULES[method]]


def preimport(runtime, output):
    import os
    launch.check_host(ROOT)
    cfg=r.verify_runtime(Path(runtime));device=sched.Device(**cfg['device'])
    expected=dict(CUDA_VISIBLE_DEVICES=device.uuid,CUDA_DEVICE_ORDER='PCI_BUS_ID',
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if any(os.environ.get(k)!=v for k,v in expected.items()):
        raise ValueError('Child environment changed')
    records=[];idle=sched.verify_idle(device,launch.sample,records.append)
    c.write(output/'device_preimport.json',dict(device=device.__dict__,idle=idle,samples=records))
    if not idle:
        raise RuntimeError('Busy device; no model import')
    return cfg


def validate_job(path, cfg):
    path=Path(path);job=c.read(path)
    c.keys(job,['schema','task_id','method','seed','reference','cover','proxy','inversion_steps','policy'])
    if job['schema']!=1 or job['task_id'] not in range(1,COUNT+1) or job['seed']!=29300+job['task_id']:
        raise ValueError('Invalid task identity')
    if job['method'] not in METHODS or job['inversion_steps']!=STEPS[job['method']]:raise ValueError('Method changed')
    if job['policy']!=cfg['policy'] or job['proxy']!=cfg['proxy']:raise ValueError('Scientific settings changed')
    for name in ('reference','cover'):
        if job[name]!=c.png_record(path.parent/(name+'.png')):raise ValueError('Input changed')
    return job


def seal_rows(root):
    rows=[]
    for sid in range(1,COUNT+1):
        for method in METHODS:
            out=root/f'attack_{sid}_{method}'
            execution=c.read(out/'execution.json')
            if execution['outcome'].get('completed') is not True or execution['outcome']['exit_code']!=0:
                raise ValueError('Every candidate must complete before target evaluation')
            frozen=c.read(out/'candidate_frozen.json')
            image=c.png_record(out/'candidate.png')
            if frozen['image']!=image or frozen['job_sha256']!=c.sha(root/'attack_inputs'/str(sid)/(method+'.json')):
                raise ValueError('Candidate binding changed')
            rows.append(dict(task_id=sid,method=method,path=out.name+'/candidate.png',image=image))
    return rows


def verify_seal(root):
    expected=c.read(root/'candidates_sealed.json')
    if expected['rows']!=seal_rows(root):
        raise ValueError('Candidate seal changed')
    return expected


def endpoint_qualification(root, design):
    import numpy as np
    from PIL import Image
    from quality import certify
    policy=design['policy'];rows=[];problems=[]
    for sid in range(1,COUNT+1):
        with Image.open(root/'attack_inputs'/str(sid)/'cover.png') as im:cover=np.asarray(im.convert('RGB'))
        pair=[]
        for method in METHODS:
            folder=root/f'attack_{sid}_{method}';summary=c.read(folder/'summary.json')
            with Image.open(folder/'candidate.png') as im:pixels=np.asarray(im.convert('RGB'))
            q=certify(pixels,cover,policy['mse_limit'],policy['linf_levels']);seconds=summary['core_seconds']
            if q!=summary['quality']:raise ValueError('Quality certificate changed')
            if not q['feasible'] or q['mse_rgb01'] < policy['minimum_mse_fraction']*policy['mse_limit']:
                problems.append(f'{sid}/{method}:quality')
            if not policy['minimum_budget_fraction']*policy['core_budget_seconds']<=seconds<=policy['core_budget_seconds']:
                problems.append(f'{sid}/{method}:cost')
            pair.append(dict(task_id=sid,method=method,quality=q,core_seconds=seconds))
        time_ratio=pair[1]['core_seconds']/pair[0]['core_seconds']
        mse_ratio=pair[1]['quality']['mse_rgb01']/max(pair[0]['quality']['mse_rgb01'],1e-30)
        if not .90<=time_ratio<=1.10:problems.append(f'{sid}:paired_cost')
        if not .95<=mse_ratio<=1.05:problems.append(f'{sid}:paired_quality')
        rows.append(dict(task_id=sid,arms=pair,time_ratio=time_ratio,mse_ratio=mse_ratio))
    return dict(qualified=not problems,problems=problems,rows=rows,target_scores_used=False)


def decide(rows, rule):
    import numpy as np
    by={(row['task_id'],row['kind']):row for row in rows}
    required={(i,k) for i in range(1,COUNT+1) for k in ('reference','cover')+METHODS}
    if set(by)!=required or len(rows)!=len(required):return dict(decision='inconclusive_missing_evidence')
    if not all(by[i,'reference']['gs_detected'] for i in range(1,COUNT+1)):
        return dict(decision='inconclusive_invalid_reference')
    pairs=[dict(task_id=i,accuracy_difference=by[i,'pixel10']['bit_accuracy']-by[i,'pixel50']['bit_accuracy'],
                gs_pass_gain=int(by[i,'pixel10']['gs_detected'])-int(by[i,'pixel50']['gs_detected'])) for i in range(1,COUNT+1)]
    differences=np.array([p['accuracy_difference'] for p in pairs],dtype=np.float64)
    rng=np.random.default_rng(rule['bootstrap_seed'])
    samples=differences[rng.integers(0,COUNT,size=(rule['bootstrap_resamples'],COUNT))].mean(axis=1)
    interval=np.quantile(samples,[.025,.975]).tolist()
    mean=float(differences.mean());positive=int(np.sum(differences>0))
    ceiling=sum(by[i,'pixel50']['bit_accuracy']>=.99 and by[i,'pixel10']['bit_accuracy']>=.99 for i in range(1,COUNT+1))
    gates=dict(mean_gain=mean>=rule['minimum_mean_accuracy_gain'],interval_lower_positive=interval[0]>0,
               consistent_direction=positive>=rule['minimum_positive_pairs'])
    decision='advance_quality_constrained_comparison_to_confirmation' if all(gates.values()) else 'close_fixed_short_efficiency_claim'
    if ceiling>=rule['ceiling_pair_count']:decision='inconclusive_continuous_endpoint_ceiling'
    return dict(decision=decision,gates=gates,pairs=pairs,mean_accuracy_difference=mean,
                descriptive_paired_bootstrap_95_interval=interval,positive_pairs=positive,continuous_ceiling_pairs=ceiling,
                summary={m:dict(delivered=COUNT,gs_passes=sum(by[i,m]['gs_detected'] for i in range(1,COUNT+1)),
                               mean_bit_accuracy=float(np.mean([by[i,m]['bit_accuracy'] for i in range(1,COUNT+1)]))) for m in METHODS},
                inference_scope='One quality/cost point, 16 independent prompt groups, development evidence only',
                original_imprint_reproduction=False,formal_content_acceptance=None,full_defense_acceptance=None,
                novelty_established=False)
