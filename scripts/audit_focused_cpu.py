"""Independent manual NumPy audit of saved cal-only cross-swaps and patch axes."""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image
from runtime_provenance import file_sha, array_binding

def patches(x):
    assert x.shape == (1, 4, 64, 64)
    return np.stack([x[0, :, y:y+2, z:z+2].ravel() for y in range(0, 64, 2) for z in range(0, 64, 2)])

def main():
    ap = argparse.ArgumentParser()
    for name in ('run', 'base-run', 'output'):
        ap.add_argument('--' + name, required=True)
    args = ap.parse_args()
    root, base = Path(args.run), Path(args.base_run)
    frozen = json.loads((root / 'cpu/frozen.json').read_text(encoding='utf8'))
    cpu = json.loads((root / 'cpu/cpu_results.json').read_text(encoding='utf8'))
    assert file_sha(root / 'inputs/focused_cpu_controls.py') == frozen['script_sha256']
    assert file_sha(root / 'inputs/focused_stability.json') == frozen['config_sha256']
    for name, digest in frozen['input_hashes'].items():
        assert file_sha(base / name.replace('\\', '/')) == digest
    profiles = json.loads((base / 'audit.json').read_text(encoding='utf8'))['metrics']['source_profiles']['calibration']
    eligible = [s for s, p in profiles.items() if s != 'c04' and p['minimum'] >= 10]
    assert sorted(eligible, key=lambda s: (-profiles[s]['minimum'], s))[0] == frozen['selected_control'] == 'c02'
    assert cpu['status'] == 'passed' and all(cpu['controls'].values())
    assert len(cpu['rows']) == 8
    arrays = np.load(root / 'cpu/cross_swap_arrays.npz', allow_pickle=False)
    max_delta = 0.
    for row in cpu['rows']:
        sid, rv, sv = row['source'], row['recon_input'], row['semantic_input']
        prior = np.load(base / 'calibration' / (sid + '_arrays.npz'), allow_pickle=False)
        recon, ref, registered = prior[rv + '_recon'], prior[sv + '_reference'], prior['registered_z']
        native = np.linalg.norm(patches(recon) - patches(ref), axis=1)
        oracle = np.linalg.norm(patches(recon) - patches(registered), axis=1)
        name = sid + '_' + rv + '_recon_' + sv + '_semantic'
        for suffix, actual in (('_l2', native), ('_oracle_l2', oracle)):
            d = float(np.max(np.abs(actual - arrays[name + suffix])))
            max_delta = max(max_delta, d)
            assert d <= 1e-12
        assert array_binding(arrays[name + '_l2']) == row['native_l2_binding']
        assert array_binding(arrays[name + '_oracle_l2']) == row['oracle_l2_binding']
        E = arrays[name + '_query_bucket_ids'] == arrays[sid + '_draft_bucket_ids']
        D, A = oracle <= 2., native <= 2.
        for key, mask in (('E', E), ('D', D), ('A', A)):
            assert np.array_equal(mask, arrays[name + '_' + key]) and int(mask.sum()) == row[key]
        assert np.array_equal(A[E], D[E])
        assert int((E & D).sum()) == row['E_intersect_D']
        assert int((A & ~E).sum()) == row['A_outside_E']
        assert np.array_equal(registered, arrays[sid + '_registered_z'])
        rgb = np.asarray(Image.open(base / 'prepare' / (sid + '_' + rv + '.png')).convert('RGB'))
        expected = (rgb.astype(np.float32) / 255.).transpose(2, 0, 1)[None] * 2. - 1.
        assert np.array_equal(expected, arrays[sid + '_' + rv + '_vae_input_normalized_cpu'])
        identity = np.asarray(Image.open(root / 'cpu' / (sid + '_lossless_pixel_identity.png')).convert('RGB'))
        original = np.asarray(Image.open(base / 'prepare' / (sid + '_original.png')).convert('RGB'))
        assert np.array_equal(identity, original)
    zero = np.zeros((1, 4, 64, 64))
    for offset, expected in ((0., 1024), (0.49, 1024), (0.5, 1024), (0.50000001, 0)):
        assert int((np.linalg.norm(patches(zero + offset) - patches(zero), axis=1) <= 2.).sum()) == expected
    one = zero.copy()
    one[0, 0, 0, 0] = 3.
    changed = np.linalg.norm(patches(one) - patches(zero), axis=1)
    assert changed[0] == 3. and np.count_nonzero(changed) == 1
    result = {'status': 'passed', 'manual_cross_swaps_audited': 8, 'max_manual_patch_l2_delta': max_delta,
        'source_hashes_verified': len(frozen['input_hashes']), 'pixel_identity_verified': True,
        'manual_criterion_controls_passed': True, 'control_selection_rule_verified': True,
        'cpu_frozen_timestamp_semantics': 'started_utc is written after CPU calculations; a seal time, not a pre-score freeze time',
        'cpu_gpu_inversions_triggered_field_semantics': 'false records this CPU runner did not execute GPU; later GPU stage has separate trigger evidence',
        'scope': 'manual NumPy patch norm audit independent of CSI patch_l2 implementation; no encoder/model rerun'}
    Path(args.output).write_bytes((json.dumps(result, indent=2) + '\n').encode('utf8'))
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
