"""CPU byte/stage audit of the conditional VAE-only precision ladder; no CUDA."""
import argparse, csv, json, os
from pathlib import Path
import numpy as np
from runtime_provenance import array_binding, file_sha

def rmse(a, b):
    delta = a.astype(np.float64) - b.astype(np.float64)
    return float(np.sqrt(np.mean(delta * delta)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    root = Path(args.run)
    folder = root / 'vae_precision'
    frozen = json.loads((folder / 'frozen.json').read_text(encoding='utf8'))
    cfg = frozen['config']
    runtime = json.loads((folder / 'runtime.json').read_text(encoding='utf8'))
    assert file_sha(root / 'inputs/focused_vae_precision.py') == frozen['script_sha256']
    assert file_sha(root / 'inputs/focused_vae_precision.json') == frozen['config_sha256']
    assert file_sha(root / 'gpu/frozen.json') == frozen['trace_frozen_sha256']
    assert file_sha(root / 'trace_audit.json') == frozen['trace_audit_sha256']
    for name, digest in runtime['file_hashes'].items():
        assert file_sha(folder / name) == digest, name
    assert json.loads((folder / 'exit_status.json').read_text(encoding='utf8'))['exit_code'] == 0
    assert runtime['vae_encodes'] == 16
    assert runtime['inversions'] == runtime['generated_images'] == runtime['weights_downloaded_bytes'] == 0
    assert cfg['sources'] == ['c04', 'c02'] and cfg['variants'] == ['original', 'jpeg70']
    assert frozen['vae_checkpoint_sha256'] == 'a2b5134f4dbc140d9c11f11cba3233099e00af40f262f136c691fb7d38d2194c'
    rows = json.loads((folder / 'results.json').read_text(encoding='utf8'))
    assert [(r['branch'], r['source'], r['variant']) for r in rows] == [
        (b, s, v) for b in cfg['branches'] for s in cfg['sources'] for v in cfg['variants']]
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    import torch
    torch.set_num_threads(4)
    cached = {}
    max_scale_delta = 0.
    for row in rows:
        prior_path = root / 'gpu' / (row['source'] + '_' + row['variant'] + '.npz')
        assert file_sha(prior_path) == row['prior_trace_sha256']
        with np.load(prior_path, allow_pickle=False) as prior, np.load(folder / row['arrays_file'], allow_pickle=False) as a:
            native = row['branch'] == 'native_fp16'
            if row['branch'] == 'fp32_checkpoint_weights_fp32_input':
                expected_input = (torch.from_numpy(prior['input_rgb'].astype(np.float32) / 255.).permute(2, 0, 1)[None] * 2. - 1.).numpy()
            else:
                expected_input = prior['vae_input_actual'].astype(np.float16 if native else np.float32)
            assert array_binding(expected_input) == row['input_binding']
            assert row['model_dtype'] == ('torch.float16' if native else 'torch.float32')
            assert row['attention_processors'] == ['AttnProcessor2_0']
            assert set(a.files) == set(row['array_bindings']) == {'mode', 'logvar', 'scaled_latent'}
            for k in a.files:
                assert a[k].shape == (1, 4, 64, 64) and np.isfinite(a[k]).all()
                assert str(a[k].dtype) == ('float16' if native else 'float32')
                assert array_binding(a[k]) == row['array_bindings'][k]
            expected_scaled = (torch.from_numpy(a['mode']) * cfg['latent_scale']).numpy()
            scale_delta = float(np.max(np.abs(expected_scaled.astype(float) - a['scaled_latent'].astype(float))))
            max_scale_delta = max(max_scale_delta, scale_delta)
            assert np.allclose(expected_scaled, a['scaled_latent'], rtol=0.0005, atol=0.001)
            measured = rmse(a['mode'], prior['vae_mode_actual'])
            assert abs(measured - row['mode_rmse_from_native']) <= 1e-12
            if native:
                assert np.array_equal(a['mode'], prior['vae_mode_actual'])
                assert np.array_equal(a['scaled_latent'], prior['initial_update_latent'])
            cached[(row['branch'], row['source'], row['variant'])] = {k: a[k].copy() for k in a.files}
    summaries = []
    for sid in cfg['sources']:
        native_pair = rmse(cached[('native_fp16', sid, 'original')]['mode'], cached[('native_fp16', sid, 'jpeg70')]['mode'])
        for branch in cfg['branches']:
            orig, jpeg = [cached[(branch, sid, v)] for v in cfg['variants']]
            pair = rmse(orig['mode'], jpeg['mode'])
            summaries.append({'source': sid, 'branch': branch, 'mode_pair_rmse': pair,
                'scaled_pair_rmse': rmse(orig['scaled_latent'], jpeg['scaled_latent']),
                'mode_pair_change_percent_from_native': 100. * (pair / native_pair - 1.),
                'original_mode_rmse_from_native': rmse(orig['mode'], cached[('native_fp16', sid, 'original')]['mode']),
                'jpeg70_mode_rmse_from_native': rmse(jpeg['mode'], cached[('native_fp16', sid, 'jpeg70')]['mode'])})
    result = {'status': 'passed', 'vae_encodes_audited': 16, 'native_modes_exact_prior_trace': True,
        'input_bindings_exact': True, 'max_scaled_cpu_replay_delta': max_scale_delta,
        'scaled_replay_tolerance': {'relative': 0.0005, 'absolute': 0.001},
        'cpu_torch': torch.__version__, 'rows': summaries,
        'measurement': {'rmse': 'sqrt(mean((float64(a)-float64(b))**2)) over every tensor element',
            'mode': 'unscaled VAE posterior mode, shape1x4x64x64, dimensionless model latent coordinates',
            'scaled': 'actual mode*0.18215 in branch dtype, same shape, scaled model latent coordinates',
            'percent_change': 'pair RMSE ratio to native pair RMSE in the same unscaled VAE coordinate space',
            'scope': 'two adaptively selected calibration sources; no inverse UNet execution or detector acceptance in this probe'}}
    output = Path(args.output)
    output.write_bytes((json.dumps(result, indent=2) + '\n').encode('utf8'))
    with (output.parent / 'precision_counts.csv').open('w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=list(summaries[0]))
        w.writeheader()
        w.writerows(summaries)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
