"""Read saved stage11 gradients, probe tensors and images on CPU."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU analysis requires CUDA_VISIBLE_DEVICES=""')
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from imprint_gradient.measures import summarize_gradients


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mse(a, b):
    return float(np.mean((a.astype(np.float64) - b.astype(np.float64))**2))


def tensor(path, descriptor):
    assert sha(path) == descriptor['sha256'], str(path)
    a = np.load(path, allow_pickle=False)
    assert a.dtype == np.float32 and list(a.shape) == descriptor['shape'] == [1, 4, 64, 64]
    assert np.isfinite(a).all()
    return a


def analyze(run, protocol):
    cfg = load(protocol)
    execution = load(run/'execution.json')
    assert execution['completed'] and execution['exit_code'] == 0 and not execution['timed_out']
    assert load(run/'command.json')['protocol_sha256'] == sha(protocol)
    assert 'COMPLETED_IMPRINT_GRADIENT_DIAGNOSTIC' in (run/'stdout.log').read_text(encoding='utf-8')
    runtime = load(run/'runtime.json')
    assert runtime['protocol_sha256'] == sha(protocol) and runtime['deterministic_algorithms']
    reference = tensor(run/'reference_proxy_noise.npy', runtime['reference_proxy_noise'])
    assert sha(run/'reference_proxy_noise.npy') == cfg['inputs']['reference_control']['sha256']
    summary = load(run/'summary.json')
    assert summary['optimization_updates'] == 0 and not summary['target_scores_used'] and not summary['target_model_loaded']
    assert [p['step'] for p in summary['points']] == [p['step'] for p in cfg['points']]
    rows = []
    maximum_loss_error = 0.
    for point in summary['points']:
        specification = next(p for p in cfg['points'] if p['step'] == point['step'])
        base_descriptor = cfg['inputs'][specification['latent']]
        relative = base_descriptor['path'].removeprefix('/data0/liyanlei/watermark_research/')
        base_path = protocol.resolve().parents[1] / relative
        assert sha(base_path) == base_descriptor['sha256']
        base = np.load(base_path, allow_pickle=False)
        folder = run/f"point_{point['step']}"
        assert point == load(folder/'summary.json')
        g = load(folder/'gradients.json')
        grads = {key: tensor(folder/(key+'_gradient.npy'), desc) for key, desc in g['gradient_arrays'].items()}
        recomputed = summarize_gradients(grads['internal'], grads['float'])
        for key, value in recomputed.items():
            assert np.isclose(value, g['metrics'][key], rtol=1e-12, atol=1e-12), key
        for key, desc in g['baseline_arrays'].items():
            value = mse(tensor(folder/(key+'_noise.npy'), desc), reference)
            assert np.isclose(value, g['baseline'][key], rtol=2e-6, atol=1e-7)
            assert np.isclose(g['backward_losses'][key], g['baseline'][key], rtol=2e-6, atol=1e-7)
        probe_rows = []
        assert [p['direction'] for p in point['probes']] == ['internal', 'float']
        for probe in point['probes']:
            name = probe['direction']
            d = tensor(folder/(name+'_direction.npy'), probe['direction_array'])
            assert np.isclose(np.mean(d.astype(np.float64)**2), 1., atol=1e-6)
            expected = grads[name].astype(np.float64) / np.sqrt(np.mean(grads[name].astype(np.float64)**2))
            assert np.allclose(d, expected, rtol=2e-6, atol=1e-7)
            analytic = {key: float(np.sum(v.astype(np.float64)*d.astype(np.float64))) for key, v in grads.items()}
            for key in analytic:
                assert np.isclose(analytic[key], probe['analytic_derivatives'][key], rtol=1e-10, atol=1e-10)
            readback = {}
            assert set(probe['signed_probes']) == {'-1', '1'}
            for sign, observed in probe['signed_probes'].items():
                prefix = name+('_minus' if sign == '-1' else '_plus')
                path = folder/(prefix+'.png')
                assert sha(path) == observed['png_sha256'] == load(path.with_suffix('.json'))['sha256']
                with Image.open(path) as image:
                    image.load()
                    assert image.mode == 'RGB' and image.size == (cfg['resolution'], cfg['resolution'])
                arrays = {key: tensor(folder/(prefix+'_'+key+'.npy'), desc) for key, desc in observed['arrays'].items()}
                expected_latent = base + np.float32(int(sign)*cfg['probe_rms_radius'])*d
                assert np.array_equal(arrays['latent'], expected_latent)
                losses = {key: mse(arrays[key+'_noise'], reference) for key in ['internal', 'float', 'png']}
                for key, value in losses.items():
                    maximum_loss_error = max(maximum_loss_error, abs(value-observed[key]))
                    assert np.isclose(value, observed[key], rtol=2e-6, atol=1e-7)
                readback[sign] = losses
            fd_cpu = {key: (readback['1'][key]-readback['-1'][key])/(2*cfg['probe_rms_radius']) for key in ['internal','float','png']}
            for key in ['internal','float','png']:
                original = (probe['signed_probes']['1'][key]-probe['signed_probes']['-1'][key])/(2*cfg['probe_rms_radius'])
                assert original == probe['finite_difference_derivatives'][key]
                if key != 'png':
                    agrees = abs(original-probe['analytic_derivatives'][key]) <= cfg['fd_atol']+cfg['fd_rtol']*abs(probe['analytic_derivatives'][key])
                    assert agrees == probe['finite_difference_agreement'][key]
            probe_rows.append(dict(direction=name, analytic=analytic, finite_difference_float64_readback=fd_cpu,
                original_finite_difference_agreement=probe['finite_difference_agreement'],
                descent_changes={key: readback['-1'][key]-g['baseline'][key] for key in ['internal','float']},
                signed_losses_float64=readback))
        rows.append(dict(step=point['step'], gradient_metrics=recomputed, directions=probe_rows))
    return dict(status='verified', run_dir=run.as_posix(), protocol_sha256=sha(protocol), execution=execution,
        points=rows, maximum_loss_readback_error=maximum_loss_error,
        target_scores_used=False, optimization_updates=0, full_defense_accepted=None,
        inference_scope='Two dependent points on one development trajectory; no optimized attack or target-side evaluation',
        verifier_gpu_used=False, verifier_models_loaded=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    parser.add_argument('protocol',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    result=analyze(args.run,args.protocol)
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
