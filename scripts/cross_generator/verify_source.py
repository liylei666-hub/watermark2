"""CPU independent arithmetic readback of the source phase and ridge normal equations."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise RuntimeError('CPU verification requires empty CUDA visibility')
import json
from pathlib import Path
import sys
import numpy as np
import io_contract as c


def verify(root):
    root = Path(root)
    status = c.read(root / 'source_status.json')
    if status['source_phase_completed'] is not True:
        raise ValueError('Source phase incomplete')
    sealed = c.verify_seal(root / 'source_fit', status['source_seal_sha256'])
    meta = sealed['metadata']
    train = c.load_bundle(root / 'train_inputs', 'train', meta['train_sha256'])
    validation = c.load_bundle(root / 'validation_inputs', 'validation', meta['validation_sha256'])
    model = c.load_model(root / 'source_fit/model.json', meta['model_sha256'])
    gate = c.read(root / 'source_fit/source_gate.json')
    # Independently reconstruct the eight features using sliding-window view.
    def features(x):
        raw = x[0].astype(np.float64)
        padded = np.pad(raw, ((0,0),(1,1),(1,1)), mode='reflect')
        mean = np.lib.stride_tricks.sliding_window_view(padded, (3,3), axis=(1,2)).mean(axis=(-2,-1))
        return np.moveaxis(np.concatenate((raw,mean)), 0, -1).reshape(-1,8)
    x = np.concatenate([features(row['estimate']) for row in train])
    y = np.concatenate([np.moveaxis(row['original_noise'][0],0,-1).reshape(-1,4) for row in train]).astype(np.float64)
    np.testing.assert_allclose(model['mean'], x.mean(0), atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(model['scale'], np.maximum(x.std(0),1e-6), atol=1e-12, rtol=1e-12)
    a = np.column_stack((np.ones(len(x)), (x-model['mean'])/model['scale']))
    gram = a.T @ a / len(x) + np.diag([0.] + [.001]*8)
    rhs = a.T @ y / len(x)
    residual = float(np.max(np.abs(gram @ model['coefficients'] - rhs)))
    if residual > 1e-10:
        raise ValueError('Normal-equation residual failed')
    mse = []; bits = []; rows = []
    for row in validation:
        sid = row['sample_id']; baseline = row['estimate'].astype(np.float64); original = row['original_noise'].astype(np.float64)
        corrected = np.load(root / 'source_fit' / (sid + '_corrected.npy'), allow_pickle=False)
        f = features(baseline)
        expected = np.column_stack((np.ones(len(f)), (f-model['mean'])/model['scale'])) @ model['coefficients']
        expected = np.moveaxis(expected.reshape(64,64,4), -1, 0)[None]
        np.testing.assert_allclose(corrected, expected, atol=1e-12, rtol=1e-12)
        a_mse = float(np.square(baseline-original).sum()/original.size)
        b_mse = float(np.square(corrected-original).sum()/original.size)
        a_bits = np.count_nonzero((baseline>=0)!=(original>=0))/original.size
        b_bits = np.count_nonzero((corrected>=0)!=(original>=0))/original.size
        mse.append(a_mse-b_mse); bits.append(a_bits-b_bits)
        rows.append(dict(sample_id=sid,baseline_mse=a_mse,corrected_mse=b_mse,
                         baseline_bit_error=a_bits,corrected_bit_error=b_bits))
    np.testing.assert_allclose(mse, gate['mse_differences'], atol=1e-12, rtol=1e-12)
    np.testing.assert_array_equal(bits, gate['bit_differences'])
    passed = bool(np.mean(mse)>0 and np.mean(bits)>=0)
    if passed != gate['pass'] or passed != status['source_gate_pass']:
        raise ValueError('Source gate mismatch')
    executions = [c.read(root / ('source_'+str(i)) / 'execution.json') for i in range(6)]
    if any(e['exit_code'] != 0 or not e['completed'] or e['timed_out'] for e in executions):
        raise ValueError('Model execution incomplete')
    return dict(verified=True, source_gate_pass=passed, normal_equation_max_abs_residual=residual,
                mean_mse_improvement=float(np.mean(mse)), mean_bit_error_improvement=float(np.mean(bits)),
                rows=rows, new_model_processes=6,
                model_process_seconds=sum(e['elapsed_seconds'] for e in executions),
                method='Saved-array arithmetic and independent feature reconstruction; no diffusion imports')


if __name__ == '__main__':
    print(json.dumps(verify(sys.argv[1]), indent=2, allow_nan=False))
