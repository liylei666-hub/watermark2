"""Evaluator-side CPU comparison of saved inversions in their own model spaces."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU analysis requires CUDA_VISIBLE_DEVICES=""')
import hashlib
import json
import sys
from pathlib import Path
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metrics(candidate, reference):
    a,b = np.asarray(candidate,dtype=np.float64).ravel(),np.asarray(reference,dtype=np.float64).ravel()
    if a.size != b.size or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Invalid arrays')
    na,nb = np.linalg.norm(a),np.linalg.norm(b)
    if na == 0 or nb == 0: raise ValueError('Undefined direction for zero latent')
    cosine = float(np.dot(a,b)/(na*nb))
    return dict(mse=float(np.mean((a-b)**2)),cosine=cosine,
        unit_direction_squared_distance=float(np.sum((a/na-b/nb)**2)),
        norm_ratio=float(na/nb),sign_agreement=float(np.mean((a>=0)==(b>=0))))


def selftest():
    a = np.array([1.,-2.,3.])
    same = metrics(2*a,a)
    assert abs(same['cosine']-1) < 1e-14 and abs(same['norm_ratio']-2) < 1e-14
    assert same['mse'] > 0 and same['unit_direction_squared_distance'] == 0
    opposite = metrics(-a,a)
    assert abs(opposite['cosine']+1) < 1e-14 and opposite['sign_agreement'] == 0
    for b in [a,np.array([3.,1.,-2.])]:
        value = metrics(a,b)
        assert abs(value['unit_direction_squared_distance']-2*(1-value['cosine'])) < 1e-14
    for bad in [np.zeros(3),np.array([np.nan,1,2]),np.zeros(2)]:
        try: metrics(a,bad)
        except ValueError: pass
        else: raise AssertionError('Invalid array accepted')
    return dict(status='passed',checks=['scaled_direction','opposite_sign','direction_identity','zero_nonfinite_shape_rejected'])


def main(root, config, output):
    root,config,output = Path(root).resolve(),Path(config),Path(output)
    cfg = json.loads(config.read_text(encoding='utf-8'))
    if sha(config) != config.with_suffix('.sha256').read_text().strip(): raise ValueError('Config changed')
    if sha(__file__) != cfg['analysis_code_sha256']: raise ValueError('Analysis changed')
    expected = {f'{task}/{domain}/{role}' for task in [1,2,3] for domain in ['proxy','target'] for role in ['reference','cover','imprint','jain']}
    if set(cfg['inputs']) != expected: raise ValueError('Incomplete fixed task inventory')
    arrays = {}
    for key,rec in cfg['inputs'].items():
        p = (root/rec['path']).resolve()
        if not p.is_relative_to(root) or sha(p) != rec['sha256']: raise ValueError('Input changed')
        arr = np.load(p,allow_pickle=False)
        if arr.dtype != np.float32 or arr.shape != (1,4,64,64): raise ValueError('Invalid latent format')
        arrays[key] = arr
    rows = []
    for task in [1,2,3]:
        domains = {}
        for domain in ['proxy','target']:
            ref = arrays[f'{task}/{domain}/reference']
            values = {role:metrics(arrays[f'{task}/{domain}/{role}'],ref) for role in ['cover','imprint','jain']}
            base = values['cover']['mse']
            for v in values.values(): v['mse_reduction_from_cover'] = None if base==0 else (base-v['mse'])/base
            domains[domain] = values
        rows.append(dict(task_id=task,domains=domains))
    with output.open('x',encoding='utf-8') as f:
        json.dump(dict(status='verified',selftest=selftest(),rows=rows,inputs_checked=24,
            protocol_sha256=sha(config),role='evaluator_only',new_model_calls=0,
            attack_feedback=False,full_defense_acceptance=None,
            interpretation='Within-domain reference-inversion diagnostics, not target original-noise geometry scores'),f,indent=2,allow_nan=False)


if __name__=='__main__':
    if sys.argv[1:]==['--selftest']: print(json.dumps(selftest()))
    else: main(*sys.argv[1:])
