"""Post-hoc CPU algebraic attribution of fixed predictions; no fitting or candidates."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':raise SystemExit('CPU visibility required')
import json
from pathlib import Path
import sys
import numpy as np
import io_contract as c
from phase_contract import SOURCE_FIT,verify_source,verify_predictions
from verify_tests import features


def components(model,baseline):
    x=features(baseline);weights=model['coefficients'][1:]/model['scale'][:,None]
    bias=model['coefficients'][0]-model['mean']@weights
    diagonal=np.diag(weights[:4])
    raw=x[:,:4];offdiag=weights[:4]-np.diag(diagonal)
    values=dict(raw_diagonal=raw*(diagonal-1),raw_cross_channel=raw@offdiag,
                local_means=x[:,4:]@weights[4:],intercept=np.broadcast_to(bias,raw.shape))
    return {key:np.moveaxis(value.reshape(64,64,4),-1,0)[None] for key,value in values.items()}


def measure(model,baseline,corrected,original):
    a,b,z=[np.asarray(x,dtype=np.float64) for x in (baseline,corrected,original)]
    changes=components(model,a);delta=b-a
    np.testing.assert_allclose(sum(changes.values()),delta,atol=1e-12,rtol=1e-12)
    error=a-z
    contributions={key:float(np.mean(-2*error*value-delta*value)) for key,value in changes.items()}
    total=float(np.mean(error**2)-np.mean((b-z)**2))
    np.testing.assert_allclose(sum(contributions.values()),total,atol=1e-12,rtol=1e-12)
    before=(a>=0)==(z>=0);after=(b>=0)==(z>=0)
    helpful=int(np.count_nonzero(~before & after));harmful=int(np.count_nonzero(before & ~after))
    return dict(mse_improvement=total,mse_algebraic_contributions=contributions,
                helpful_bit_flips=helpful,harmful_bit_flips=harmful,total_bit_flips=helpful+harmful,
                bit_error_improvement=(helpful-harmful)/z.size,coordinates=z.size)


def main(source,protocol,output):
    source=Path(source);protocol=Path(protocol);output=Path(output)
    if c.sha(protocol)!=protocol.with_suffix('.sha256').read_text().strip():raise ValueError('Readback protocol changed')
    cfg=c.read(protocol)
    if c.sha(__file__)!=cfg['code_sha256']:raise ValueError('Readback code changed')
    repo=Path(__file__).resolve().parents[2]
    for name,digest in cfg['dependency_hashes'].items():
        if c.sha(repo/name)!=digest:raise ValueError('Readback dependency changed')
    verify_source(source);tests=source/'tests';status=c.read(tests/'status.json')
    if status['prediction_seal_sha256']!=cfg['test_prediction_seal_sha256']:raise ValueError('Unexpected test predictions')
    verify_predictions(tests,status['prediction_seal_sha256'])
    source_meta=c.verify_seal(source/'source_fit',SOURCE_FIT)['metadata']
    model=c.load_model(source/'source_fit/model.json',source_meta['model_sha256'])
    rows=[]
    validation=c.load_bundle(source/'validation_inputs','validation',source_meta['validation_sha256'])
    for row in validation:
        sid=row['sample_id'];corrected=np.load(source/'source_fit'/(sid+'_corrected.npy'),allow_pickle=False)
        rows.append(dict(sample_id=sid,split='proxy_validation',**measure(model,row['estimate'],corrected,row['original_noise'])))
    for split,prefix in [('proxy_test','proxy'),('target_test','target')]:
        for i,sid in enumerate(c.SPLITS[split]):
            pred=tests/(split+'_predictions');original=tests/(prefix+'_generate_'+str(i//4))/sid/'original_noise.npy'
            record=c.read(original.parent/'record.json')
            if record['task']['sample_id']!=sid or c.array_record(original)!=record['original_noise']:raise ValueError('Original noise association changed')
            arrays=[np.load(path,allow_pickle=False) for path in [pred/(sid+'_baseline.npy'),pred/(sid+'_corrected.npy'),original]]
            rows.append(dict(sample_id=sid,split=split,**measure(model,*arrays)))
    summaries={}
    for split in ('proxy_validation','proxy_test','target_test'):
        selected=[row for row in rows if row['split']==split]
        summaries[split]=dict(mean_mse_improvement=float(np.mean([row['mse_improvement'] for row in selected])),
            mse_algebraic_contributions={name:float(np.mean([row['mse_algebraic_contributions'][name] for row in selected])) for name in selected[0]['mse_algebraic_contributions']},
            helpful_bit_flips=sum(row['helpful_bit_flips'] for row in selected),harmful_bit_flips=sum(row['harmful_bit_flips'] for row in selected),
            total_coordinates=sum(row['coordinates'] for row in selected))
    weights=model['coefficients'][1:]/model['scale'][:,None]
    c.write(output,dict(protocol_sha256=c.sha(protocol),rows=rows,summaries=summaries,
        raw_channel_diagonal_gains=np.diag(weights[:4]).tolist(),
        all_diagonal_gains_positive=bool(np.all(np.diag(weights[:4])>0)),
        interpretation='Exact algebraic allocation, not a component ablation or causal estimate',
        post_hoc=True,fit_count=0,new_model_experiments_run=0,new_candidates=0,gpu_used=False))


if __name__=='__main__':main(*sys.argv[1:])
