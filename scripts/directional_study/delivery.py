"""CPU construction of exactly matched, single-level RGB direction probes.

This module accepts proxy gradients only. It does not load models or detectors.
The shared support and integer delivery are part of the experimental treatment.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

CONDITIONS = ('vae_descent', 'vae_ascent', 'inverse_descent', 'inverse_ascent', 'random')


def build(cover, vae_gradient, inverse_gradient, random_seed, min_active_fraction=0.5):
    cover = np.asarray(cover)
    if cover.dtype != np.uint8 or cover.ndim != 3 or cover.shape[-1] != 3:
        raise ValueError('Expected HWC RGB uint8 cover')
    if type(random_seed) is not int or random_seed < 0:
        raise ValueError('Expected nonnegative integer seed')
    if not 0 < min_active_fraction <= 1:
        raise ValueError('Invalid support threshold')
    gradients = [np.asarray(g) for g in (vae_gradient, inverse_gradient)]
    if any(g.shape != cover.shape or g.dtype.kind != 'f' or not np.isfinite(g).all() for g in gradients):
        raise ValueError('Expected finite matched HWC floating gradients with respect to RGB [0,1]')
    support = (cover > 0) & (cover < 255) & (gradients[0] != 0) & (gradients[1] != 0)
    count = int(support.sum())
    if count == 0 or count / cover.size < min_active_fraction:
        raise ValueError('Insufficient shared support; preserve failure, do not change threshold')
    a, b = [np.sign(g).astype(np.int16) * support for g in gradients]
    rng = np.random.Generator(np.random.PCG64(random_seed))
    random = (2 * rng.integers(0, 2, size=cover.shape, dtype=np.int16) - 1) * support
    steps = dict(zip(CONDITIONS, (-a, a, -b, b, random)))
    candidates = {}
    for name, step in steps.items():
        value = cover.astype(np.int16) + step
        if value.min() < 0 or value.max() > 255:
            raise RuntimeError('Integer delivery overflow')
        value = value.astype(np.uint8)
        delta = value.astype(np.int16) - cover.astype(np.int16)
        if not np.array_equal(delta != 0, support) or int(np.sum(delta.astype(np.int64)**2)) != count:
            raise RuntimeError('Unequal delivered distortion')
        candidates[name] = value
    return candidates, support, dict(active_channels=count, total_channels=int(cover.size),
        active_fraction=count/cover.size, squared_l2_integer=count, linf_integer=1,
        mse_rgb01=count/(cover.size*255**2), linf_rgb01=1/255,
        clipping_used=False, quantization_rounding_used=False)


def derivative_check(gradient, positive_delta_rgb01, loss_minus, loss_plus):
    g, d = np.asarray(gradient, dtype=np.float64), np.asarray(positive_delta_rgb01, dtype=np.float64)
    if g.shape != d.shape or not np.isfinite(g).all() or not np.isfinite(d).all():
        raise ValueError('Invalid derivative inputs')
    if not np.isfinite([loss_minus, loss_plus]).all():
        raise ValueError('Nonfinite loss')
    predicted = float(np.sum(g*d))
    observed = float((loss_plus-loss_minus)/2)
    error = abs(observed-predicted)/max(abs(observed),abs(predicted),1e-8)
    return dict(predicted_half_difference=predicted, observed_half_difference=observed,
        relative_error=error, within_predeclared_tolerance=error<=0.25,
        meaning='finite-step diagnostic; not an exact derivative or target-transfer guarantee')


def export(directory, cover, candidates, support, summary):
    directory = Path(directory)
    if set(candidates) != set(CONDITIONS):
        raise ValueError('Expected every predetermined condition')
    cover, support = np.asarray(cover), np.asarray(support)
    if cover.dtype != np.uint8 or support.dtype != bool or support.shape != cover.shape:
        raise ValueError('Invalid cover/support')
    for array in candidates.values():
        array = np.asarray(array)
        if array.dtype != np.uint8 or array.shape != cover.shape:
            raise ValueError('Invalid candidate')
        delta = array.astype(np.int16) - cover.astype(np.int16)
        if not np.array_equal(np.abs(delta), support.astype(np.int16)):
            raise ValueError('Candidate violates exact delivery constraint')
    # Exclusive directory creation prevents any partial or complete output overwrite.
    directory.mkdir(parents=False, exist_ok=False)
    records = {}
    for name in CONDITIONS:
        array = np.asarray(candidates[name])
        path = directory/(name+'.png')
        with path.open('xb') as f:
            Image.fromarray(array).save(f, format='PNG')
        with Image.open(path) as im:
            if im.mode != 'RGB' or not np.array_equal(np.asarray(im), array):
                raise RuntimeError('PNG readback changed pixels')
        records[name] = dict(path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            pixel_sha256=hashlib.sha256(array.tobytes()).hexdigest())
    with (directory/'support.npy').open('xb') as f:
        np.save(f, np.asarray(support, dtype=bool), allow_pickle=False)
    record = dict(conditions=records, distortion=summary,
        support_sha256=hashlib.sha256((directory/'support.npy').read_bytes()).hexdigest())
    with (directory/'candidate_set.json').open('x', encoding='utf-8') as f:
        json.dump(record, f, indent=2, allow_nan=False)
    return record
