"""Fixed paired delivery contracts; imports do not initialize CUDA."""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cross_generator'))
import io_contract as c
from source_worker import r

IDS=c.SPLITS['target_test']
METHODS=('baseline','corrected')
PROMPT='A photograph of a red vintage car parked on a snowy street.'


def cast_input(value):
    if value.shape!=c.SHAPE or value.dtype not in (np.dtype('float32'),np.dtype('float64')) or not np.isfinite(value).all():
        raise ValueError('Invalid input latent')
    cast=value.astype(np.float32)
    if not np.isfinite(cast).all() or np.any((cast>=0)!=(value>=0)):
        raise ValueError('Float32 conversion changed sign or finiteness')
    return cast


def tasks():
    return [dict(sample_id=sid,prompt=PROMPT,seed=25001+i) for i,sid in enumerate(IDS)]


def bundle(folder,digest,kind):
    folder=Path(folder);sealed=c.verify_seal(folder,digest)
    expected_meta=dict(kind=kind,sample_ids=IDS,methods=list(METHODS))
    if sealed['metadata']!=expected_meta:raise ValueError('Bundle role or identities changed')
    expected={sid+'_'+method+('.npy' if kind=='attack_inputs' else '.png') for sid in IDS for method in METHODS}
    if kind=='evaluation_images':expected|={sid+'_reference.png' for sid in IDS}
    if set(sealed['files'])!=expected:raise ValueError('Incomplete delivery or unexpected information')
    for name in expected:
        if kind=='attack_inputs':c.array_record(folder/name)
        else:c.png_record(folder/name)
    return sealed


def seal_bundle(folder,kind):
    names=[p.name for p in Path(folder).iterdir()]
    digest=c.seal(folder,names,dict(kind=kind,sample_ids=IDS,methods=list(METHODS)))
    bundle(folder,digest,kind)
    return digest


def summary(rows):
    if [row['sample_id'] for row in rows]!=IDS:raise ValueError('All eight paired tasks required in order')
    diffs=[];reference_valid=[];passes={m:0 for m in METHODS}
    for row in rows:
        c.keys(row,['sample_id','reference','baseline','corrected'])
        for method in ('reference',)+METHODS:
            score=row[method]
            if not isinstance(score,(int,float)) or not np.isfinite(score) or not 0<=score<=1:raise ValueError('Invalid score')
        diffs.append(row['corrected']-row['baseline'])
        reference_valid.append(row['reference']>.70703125)
        for m in METHODS:passes[m]+=int(row[m]>.70703125)
    return dict(pairs=8,message_accuracy_differences=diffs,mean_difference=float(np.mean(diffs)),
        improved=sum(d>0 for d in diffs),tied=sum(d==0 for d in diffs),worse=sum(d<0 for d in diffs),
        ordinary_gs_pass_counts=passes,threshold=.70703125,comparison='strict_greater',
        valid_references=sum(reference_valid),reference_valid_secondary_mean=(float(np.mean([d for d,v in zip(diffs,reference_valid) if v])) if any(reference_valid) else None),
        prompt_group_means={f'test_{i+1}':float(np.mean(diffs[2*i:2*i+2])) for i in range(4)},
        full_defense_acceptance=None,formal_content_labels=None,population_attack_success_rate=None)
