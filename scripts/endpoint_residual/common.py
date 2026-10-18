"""CPU contracts and float64 measurements for fixed proxy endpoints."""
import hashlib
import json
from pathlib import Path

RUN = 'runs/17_cover_pilot_20261017T214442Z'
REMOTE = '/data0/liyanlei/watermark_research'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def expected_inputs():
    result = {}
    for task in [1, 2, 3]:
        prefix = f'{RUN}/attack_inputs/{task}'
        out = f'{RUN}/attack_outputs/{task}'
        for name, relative in {
            'reference': f'{prefix}/reference.png', 'cover': f'{prefix}/cover.png',
            'imprint_png': f'{out}/imprint/candidate.png',
            'jain_png': f'{out}/jain/candidate.png',
            'imprint_z': f'{out}/imprint/final_latent.npy',
            'reference_inverse': f'{out}/imprint/reference_proxy_noise.npy',
            'jain_float': f'{out}/jain/final_float.npy',
        }.items():
            result[f'{task}/{name}'] = relative
    return result


def validate_inputs(cfg, root):
    expected = expected_inputs()
    if set(cfg['inputs']) != set(expected):
        raise ValueError('Expected all three pairs with exactly seven proxy inputs each')
    paths = {}
    for name, relative in expected.items():
        record = cfg['inputs'][name]
        if set(record) != {'path', 'sha256'} or record['path'] != REMOTE + '/' + relative:
            raise ValueError('Input outside fixed proxy-input allowlist')
        path = Path(root) / relative
        if sha(path) != record['sha256']:
            raise ValueError('Fixed input changed: ' + name)
        paths[name] = path
    return paths


def mse(a, b):
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or a.shape != (1, 4, 64, 64):
        raise ValueError('Expected matched latent shapes')
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Nonfinite latent')
    return float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))


def relative_drop(initial, final):
    return None if initial == 0 else (initial - final) / initial


def summarize(arrays):
    zr, nr = arrays['reference_z'], arrays['reference_inverse']
    cover_vae = mse(arrays['cover_z'], zr)
    cover_noise = mse(arrays['cover_inverse'], nr)
    vae = {name: mse(arrays[name + '_z'], zr)
           for name in ['cover', 'imprint_png', 'jain_png', 'jain_float']}
    noise = {name: mse(arrays[name + '_inverse'], nr)
             for name in ['cover', 'initial_png', 'imprint_native', 'imprint_png', 'imprint_float', 'jain_png']}
    native_improvement = cover_noise - noise['imprint_native']
    png_improvement = noise['initial_png'] - noise['imprint_png']
    return dict(vae_mse=vae, vae_relative_reduction={k: relative_drop(cover_vae, v) for k, v in vae.items()},
        inversion_mse=noise,
        inversion_reduction_from_cover={k: relative_drop(cover_noise, v) for k, v in noise.items()},
        imprint_native_improvement=native_improvement, imprint_png_improvement=png_improvement,
        imprint_png_improvement_retained=None if native_improvement == 0 else png_improvement / native_improvement,
        imprint_final_delivery_gap=noise['imprint_png'] - noise['imprint_native'],
        imprint_float_delivery_gap=noise['imprint_float'] - noise['imprint_native'],
        imprint_quantization_loss_difference=noise['imprint_png'] - noise['imprint_float'],
        jain_float_to_png_vae_difference=vae['jain_png'] - vae['jain_float'])
