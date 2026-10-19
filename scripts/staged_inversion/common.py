"""Frozen stage28 contracts. Importing this module does not import model libraries."""
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

METHODS = ('native50','short10','staged10_50')
SCHEDULES = {'native50': ((50,10),), 'short10': ((10,50),), 'staged10_50': ((10,30),(50,4))}


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
    c.keys(job,['schema','task_id','method','seed','reference','cover','proxy','schedule','learning_rate'])
    if job['schema']!=1 or job['task_id'] not in (1,2,3,4) or job['seed']!=28300+job['task_id']:
        raise ValueError('Invalid task identity')
    if job['schedule']!=schedule(job['method']) or job['learning_rate']!=.01 or job['proxy']!=cfg['proxy']:
        raise ValueError('Scientific settings changed')
    for name in ('reference','cover'):
        if job[name]!=c.png_record(path.parent/(name+'.png')):
            raise ValueError('Attack input changed')
    return job


def seal_rows(root):
    rows=[]
    for sid in range(1,5):
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


def decide(rows, rule):
    """Descriptive four-task go/no-go rule; never substitutes for confirmation."""
    import statistics as stats
    refs=[row for row in rows if row['kind']=='reference']
    by={(row['task_id'],row['kind']):row for row in rows}
    required={(i,k) for i in range(1,5) for k in ('reference','cover')+METHODS}
    if set(by)!=required or len(rows)!=len(required):
        return dict(decision='inconclusive_missing_evidence')
    pairs=[]
    for sid in range(1,5):
        native,short,staged=(by[(sid,m)] for m in METHODS)
        if native['cover_mse_rgb01']<=0 or native['core_seconds']<=0 or short['core_seconds']<=0:
            return dict(decision='inconclusive_invalid_ratio')
        pairs.append(dict(task_id=sid,pass_gain=int(staged['gs_detected'])-int(native['gs_detected']),
            accuracy_gain=staged['bit_accuracy']-native['bit_accuracy'],
            gain_over_short=staged['bit_accuracy']-short['bit_accuracy'],
            pass_gain_over_short=int(staged['gs_detected'])-int(short['gs_detected']),
            mse_ratio=staged['cover_mse_rgb01']/native['cover_mse_rgb01'],
            time_ratio=staged['core_seconds']/native['core_seconds'],
            short_time_ratio=short['core_seconds']/native['core_seconds']))
    gate=dict(all_references_valid=len(refs)==4 and all(row['gs_detected'] for row in refs),
        gain_over_native=sum(p['pass_gain'] for p in pairs)>=rule['minimum_additional_passes'],
        mean_accuracy_gain=stats.mean(p['accuracy_gain'] for p in pairs)>=rule['minimum_mean_accuracy_gain'],
        mean_gain_over_short=stats.mean(p['gain_over_short'] for p in pairs)>=rule['minimum_mean_gain_over_short'],
        no_pass_loss_vs_short=sum(p['pass_gain_over_short'] for p in pairs)>=0,
        distortion=stats.median(p['mse_ratio'] for p in pairs)<=rule['max_median_mse_ratio'],
        measured_time=all(rule['min_median_time_ratio']<=stats.median(p[key] for p in pairs)<=rule['max_median_time_ratio']
                          for key in ('time_ratio','short_time_ratio')))
    decision='advance_to_independent_confirmation' if all(gate.values()) else 'close_fixed_staged_candidate'
    if not gate['all_references_valid'] or not gate['measured_time']:
        decision='inconclusive_reference_or_actual_budget_mismatch'
    return dict(decision=decision,gates=gate,pairs=pairs,
        summary={m:dict(delivered=4,gs_passes=sum(by[(i,m)]['gs_detected'] for i in range(1,5)),
            mean_bit_accuracy=stats.mean(by[(i,m)]['bit_accuracy'] for i in range(1,5)),
            median_core_seconds=stats.median(by[(i,m)]['core_seconds'] for i in range(1,5))) for m in METHODS},
        ordinary_gs_only=True,independent_confirmation=False,formal_content_acceptance=None,novelty_established=False)
