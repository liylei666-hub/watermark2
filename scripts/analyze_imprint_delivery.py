"""CPU readback of frozen Imprint delivery diagnostics; imports no model library."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU analysis requires CUDA_VISIBLE_DEVICES=""')
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mse(a, b):
    return float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))


def analyze(run, protocol):
    cfg = load(protocol)
    execution = load(run / 'execution.json')
    assert execution['completed'] and execution['exit_code'] == 0 and not execution['timed_out']
    assert 'COMPLETED_IMPRINT_DELIVERY_DIAGNOSTIC' in (run / 'stdout.log').read_text(encoding='utf-8')
    assert load(run / 'command.json')['protocol_sha256'] == sha(protocol)
    assert load(run / 'runtime.json')['protocol_sha256'] == sha(protocol)
    assert load(run / 'gradient_replay.json')['bitwise_equal']
    target_file = run / 'reference_proxy_noise.npy'
    assert sha(target_file) == load(run / 'runtime.json')['reference_proxy_noise']['sha256']
    target = np.load(target_file, allow_pickle=False)
    assert target.dtype == np.float32 and target.shape == (1, 4, 64, 64) and np.isfinite(target).all()
    rows = []
    max_error = 0.
    summary = load(run / 'summary.json')
    assert summary['optimization_steps'] == cfg['optimization_steps']
    assert not summary['target_model_loaded'] and not summary['target_scores_used']
    assert [r['step'] for r in summary['checkpoints']] == cfg['checkpoints']
    for step in cfg['checkpoints']:
        folder = run / f'checkpoint_{step}'
        record = load(folder / 'metrics.json')
        assert record == next(r for r in summary['checkpoints'] if r['step'] == step)
        assert record['internal_replay_bitwise_equal']
        assert load(folder / 'inversion_equivalence.json')['allclose']
        frozen = load(folder / 'candidate_frozen.json')
        assert frozen['sha256'] == sha(folder / 'candidate.png')
        assert frozen['pixel_readback_equal'] and frozen['step'] == step
        with Image.open(folder / 'candidate.png') as image:
            assert list(image.size) == frozen['size'] == [512, 512] and image.mode == 'RGB'
            image.load()
        arrays = {}
        for name, descriptor in record['arrays'].items():
            file = folder / (name + '.npy')
            assert sha(file) == descriptor['sha256']
            value = np.load(file, allow_pickle=False)
            assert str(value.dtype) == descriptor['dtype'] == 'float32'
            assert list(value.shape) == descriptor['shape'] == [1, 4, 64, 64]
            assert np.isfinite(value).all()
            arrays[name] = value
        values = {name: mse(arrays[array], target) for name, array in [
            ('internal_loss', 'internal_noise'), ('float_delivery_loss', 'float_noise'),
            ('png_delivery_loss', 'png_noise')]}
        values.update({name: mse(arrays[a], arrays[b]) for name, a, b in [
            ('float_latent_displacement', 'float_z', 'z'),
            ('png_latent_displacement', 'png_z', 'z'),
            ('quantization_latent_displacement', 'png_z', 'float_z')]})
        for name, value in values.items():
            error = abs(record[name] - value)
            max_error = max(max_error, error)
            assert np.isclose(record[name], value, atol=1e-7, rtol=2e-6), (step, name, error)
        rows.append(dict(step=step, **values,
            png_minus_internal=values['png_delivery_loss']-values['internal_loss'],
            png_minus_float=values['png_delivery_loss']-values['float_delivery_loss'],
            png_vs_float_noise_mse=mse(arrays['png_noise'], arrays['float_noise']),
            candidate_sha256=frozen['sha256'], content_pass=record['content_pass'],
            target_score=record['target_score'], full_defense_accepted=record['full_defense_accepted']))
    first, last = rows[0], rows[-1]
    improvement = {name: first[name]-last[name] for name in ['internal_loss', 'float_delivery_loss', 'png_delivery_loss']}
    return dict(status='verified', run_dir=str(run), protocol_sha256=sha(protocol),
        execution=execution, checkpoints=rows, improvement=improvement,
        improvement_internal_minus_png=improvement['internal_loss']-improvement['png_delivery_loss'],
        max_absolute_float64_readback_error=max_error,
        inference_scope='One development pair, native optimization; no target detection or causal intervention',
        full_defense_accepted=None, human_content_reviews=0,
        verifier_gpu_used=False, verifier_models_loaded=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('protocol', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = analyze(args.run, args.protocol)
    with args.output.open('x', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
