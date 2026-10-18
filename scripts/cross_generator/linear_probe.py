"""CPU-only fixed diagnostic estimator; no diffusion imports or file discovery."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise RuntimeError('Set CUDA_VISIBLE_DEVICES="" for the CPU estimator')
import numpy as np

RIDGE = 0.001
SCALE_FLOOR = 1e-6


def tensor(value):
    x = np.asarray(value, dtype=np.float64)
    if x.ndim != 4 or x.shape[:2] != (1, 4) or min(x.shape[2:]) < 3:
        raise ValueError('Expected one four-channel spatial tensor')
    if not np.isfinite(x).all():
        raise ValueError('Nonfinite tensor')
    return x


def features(value):
    x = tensor(value)[0]
    h, w = x.shape[1:]
    pad = np.pad(x, ((0, 0), (1, 1), (1, 1)), mode='reflect')
    local = sum(pad[:, a:a+h, b:b+w] for a in range(3) for b in range(3)) / 9.
    return np.concatenate((x, local), axis=0).reshape(8, -1).T


def validate_records(records):
    if not records:
        raise ValueError('Empty training set')
    seen = set()
    for r in records:
        if r['role'] != 'proxy_train' or r['generator_role'] != 'proxy':
            raise ValueError('Training accepts proxy training records only')
        if r['sample_id'] in seen:
            raise ValueError('Duplicate sample ID')
        seen.add(r['sample_id'])
        if tensor(r['estimate']).shape != tensor(r['original_noise']).shape:
            raise ValueError('Label/estimate shape mismatch')
    # These metadata checks do not authenticate provenance or isolate OS permissions.


def fit(records):
    validate_records(records)
    xs = [features(r['estimate']) for r in records]
    ys = [tensor(r['original_noise'])[0].reshape(4, -1).T for r in records]
    if len({x.shape[0] for x in xs}) != 1:
        raise ValueError('Training images must have the same resolution')
    n = sum(x.shape[0] for x in xs)
    mean = sum(x.sum(0) for x in xs) / n
    variance = sum(((x - mean) ** 2).sum(0) for x in xs) / n
    scale = np.maximum(np.sqrt(variance), SCALE_FLOOR)
    gram = np.zeros((9, 9)); rhs = np.zeros((9, 4))
    for x, y in zip(xs, ys):
        a = np.column_stack((np.ones(len(x)), (x - mean) / scale))
        gram += a.T @ a / n
        rhs += a.T @ y / n
    penalty = np.diag([0.] + [RIDGE] * 8)
    coefficients = np.linalg.solve(gram + penalty, rhs)
    if not np.isfinite(coefficients).all():
        raise ValueError('Nonfinite fitted estimator')
    return {'mean': mean, 'scale': scale, 'coefficients': coefficients,
            'ridge': RIDGE, 'train_sample_ids': [r['sample_id'] for r in records]}


def predict(model, value):
    x = tensor(value)
    a = np.column_stack((np.ones(x.shape[2] * x.shape[3]),
                         (features(x) - model['mean']) / model['scale']))
    y = a @ model['coefficients']
    if not np.isfinite(y).all():
        raise ValueError('Nonfinite prediction')
    return y.T.reshape(x.shape)


def source_gate(baseline, corrected, originals):
    if not baseline or not (len(baseline) == len(corrected) == len(originals)):
        raise ValueError('Invalid validation group')
    mse_differences = []; bit_differences = []
    for a, b, z in zip(baseline, corrected, originals):
        a, b, z = tensor(a), tensor(b), tensor(z)
        if not a.shape == b.shape == z.shape:
            raise ValueError('Validation shape mismatch')
        mse_differences.append(float(np.mean((a-z)**2) - np.mean((b-z)**2)))
        bit_differences.append(float(np.mean((a>=0)!=(z>=0)) - np.mean((b>=0)!=(z>=0))))
    return {'mse_differences': mse_differences, 'bit_differences': bit_differences,
            'pass': bool(np.mean(mse_differences) > 0 and np.mean(bit_differences) >= 0)}
