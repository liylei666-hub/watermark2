"""CPU readback of component-level directional residuals at fixed existing probes."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU analysis requires CUDA_VISIBLE_DEVICES=""')
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from imprint_components.components import decompose


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tensor(p, record):
    assert sha(p) == record['sha256'], p
    a=np.load(p,allow_pickle=False)
    assert a.dtype == np.float32 and a.shape == (1,4,64,64) and np.isfinite(a).all()
    return a


def branches(p, record):
    assert sha(p) == record['sha256']
    with np.load(p,allow_pickle=False) as archive:
        assert archive.files == ['branches']
        a=archive['branches']
    assert a.dtype == np.uint8 and a.shape == (1,3,512,512)
    assert set(np.unique(a)).issubset({0,1,2})
    return a


def analyze(run, protocol):
    cfg=load(protocol); root=protocol.resolve().parents[1]
    def supplied(key):
        record=cfg['inputs'][key]
        p=root/record['path'].removeprefix('/data0/liyanlei/watermark_research/')
        return tensor(p,record)
    execution=load(run/'execution.json')
    assert execution['exit_code']==0 and execution['completed'] and not execution['timed_out']
    assert 'COMPLETED_IMPRINT_COMPONENT_DIAGNOSTIC' in (run/'stdout.log').read_text(encoding='utf-8')
    assert load(run/'command.json')['protocol_sha256']==sha(protocol)
    runtime=load(run/'runtime.json')
    assert runtime['protocol_sha256']==sha(protocol) and runtime['deterministic_algorithms']
    u=tensor(run/'reference_proxy_noise.npy',runtime['reference_proxy_noise']).astype(np.float64)
    assert sha(run/'reference_proxy_noise.npy')==cfg['inputs']['reference_control']['sha256']
    summary=load(run/'summary.json')
    assert summary['optimization_updates']==0 and summary['new_candidate_images']==0
    assert not summary['target_scores_used'] and not summary['target_model_loaded']
    assert [p['step'] for p in summary['points']]==[p['step'] for p in cfg['points']]
    points=[]
    for point, specification in zip(summary['points'],cfg['points']):
        folder=run/f"point_{point['step']}"
        assert point==load(folder/'summary.json')
        y=tensor(folder/'encoded_latent.npy',point['encoded_latent'])
        assert np.array_equal(y,supplied(specification['encoded_latent']))
        gi=tensor(folder/'downstream_gradient.npy',point['downstream_gradient']).astype(np.float64)
        gz=tensor(folder/'recomposed_gradient.npy',point['recomposed_gradient'])
        original=supplied(specification['float_gradient'])
        equal=bool(np.array_equal(gz,original))
        close=bool(np.allclose(gz,original,rtol=cfg['chain_rtol'],atol=cfg['chain_atol']))
        error=float(np.max(np.abs(gz-original)))
        assert point['chain_comparison']==dict(bitwise_equal=equal,allclose=close,max_abs_difference=error)
        mask=branches(folder/'baseline_branches.npz',point['baseline_branches'])
        probes={p['name']:p for p in point['probes']}
        assert set(probes)=={p['name'] for p in specification['probes']}
        records={p['name']:p for p in specification['probes']}
        directions=[]
        for name, key in specification['directions'].items():
            d=supplied(key).astype(np.float64)
            values={}; branch_counts={}
            for suffix, sign in [('minus',-1),('plus',1)]:
                probe_name=name+'_'+suffix; obs=probes[probe_name]; spec=records[probe_name]
                v=tensor(folder/(probe_name+'_encoded.npy'),obs['encoded']).astype(np.float64)
                noise=supplied(spec['noise']).astype(np.float64)
                probe_mask=branches(folder/(probe_name+'_branches.npz'),obs['branches'])
                values[sign]=dict(encoded=v,loss=float(np.mean((noise-u)**2)))
                branch_counts[suffix]=dict(changed_coordinates=int(np.count_nonzero(mask!=probe_mask)),
                    coordinate_count=int(mask.size),changed_fraction=float(np.mean(mask!=probe_mask)))
            a=float(np.sum(original.astype(np.float64)*d))
            b=float(np.sum(gi*(values[1]['encoded']-values[-1]['encoded'])/(2*cfg['probe_rms_radius'])))
            c=(values[1]['loss']-values[-1]['loss'])/(2*cfg['probe_rms_radius'])
            residuals=decompose(a,b,c)
            assert np.isclose(residuals['total_residual'],residuals['map_linearization_residual']+residuals['inverse_linearization_residual'],atol=1e-12)
            directions.append(dict(direction=name,**residuals,clamp_branch_changes=branch_counts,
                recomposed_analytic=float(np.sum(gz.astype(np.float64)*d))))
        points.append(dict(step=point['step'],chain_comparison=point['chain_comparison'],
            baseline_saturated_coordinates=int(np.count_nonzero(mask!=1)),
            directions=directions))
    return dict(status='verified',execution=execution,protocol_sha256=sha(protocol),points=points,
        diagnostic_chain_agreement=all(p['chain_comparison']['allclose'] for p in points),
        interpretation_scope='Fixed finite-step residual localization, not proof of clamp causation or derivative correctness in a limit',
        optimization_updates=0,new_candidate_images=0,target_scores_used=False,full_defense_accepted=None,
        verifier_gpu_used=False,verifier_models_loaded=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path);parser.add_argument('protocol',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();result=analyze(args.run,args.protocol)
    with args.output.open('x',encoding='utf-8',newline='\n') as file:
        json.dump(result,file,indent=2);file.write('\n')
    print(json.dumps(result,indent=2))
