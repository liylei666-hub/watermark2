"""CPU recomputation of the alternative configuration's persisted detector stages."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--csi-code', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    import numpy as np
    sys.path.insert(0, args.csi_code)
    from csi.schemes.seal import SealCore
    from csi.types import Key
    run = Path(args.run)
    frozen = json.loads((run / 'frozen.json').read_text())
    cfg = frozen['config']
    assert cfg['configuration_id'] in {'sd15-clip-image-binding-smoke-v1',
                                       'sd15-clip-image-binding-color-followup-v1'}
    assert cfg['source_count'] == 3 and cfg['physical_gpu'] == 7
    assert cfg['max_new_weight_download_bytes'] == 0
    assert cfg['operating_point_provenance'].startswith('unchecked')
    runtime = json.loads((run / 'runtime.json').read_text())
    for name, digest in runtime['file_hashes'].items():
        assert sha(run / name) == digest, name
    assert json.loads((run / 'exit_status.json').read_text())['exit_code'] == 0
    arrays = np.load(run / 'arrays.npz', allow_pickle=False)
    rows = json.loads((run / 'scores.json').read_text())
    assert len(rows) == 6
    assert {(r['source'], r['variant']) for r in rows} == {
        ('s' + str(i), variant) for i in range(3) for variant in cfg['variants']}
    assert cfg['core'] == {'k': 1024, 'b': 7, 't_patch': 2.0, 'fallback_matches': 10.0}
    core = SealCore(k=1024, b=7, t_patch=cfg['core']['t_patch'])
    key = Key(seed=cfg['key_seed'])
    max_reference_delta, max_l2_delta = 0.0, 0.0
    for row in rows:
        prefix = row['source'] + '_' + row['variant']
        v = arrays[prefix + '_feature']
        reference = core.noise_from_embedding(v, key)
        reference_delta = float(np.max(np.abs(reference - arrays[prefix + '_reference'])))
        max_reference_delta = max(max_reference_delta, reference_delta)
        assert reference_delta == 0
        l2 = core.patch_l2(arrays[prefix + '_recon'], reference)
        delta = float(np.max(np.abs(l2 - arrays[prefix + '_l2'])))
        max_l2_delta = max(max_l2_delta, delta)
        assert delta <= 1e-12
        count = int((l2 <= core.t_patch).sum())
        assert count == row['match_count']
        assert (count >= cfg['core']['fallback_matches']) == row['fallback_accepted']
        assert core.match_count(arrays[prefix + '_recon'], arrays[row['source'] + '_registered_z']) == row['registration_reference_matches']
    for i in range(3):
        p = 's' + str(i)
        assert np.array_equal(core.noise_from_embedding(arrays[p + '_draft_feature'], key), arrays[p + '_registered_z'])
    result = {'status': 'passed', 'configuration_id': cfg['configuration_id'],
        'sources': 3, 'detector_rows': 6, 'hashed_run_files': len(runtime['file_hashes']),
        'max_reference_noise_delta': max_reference_delta, 'max_patch_l2_delta': max_l2_delta,
        'scope': 'persisted-stage CPU recomputation; no rerun of generation, CLIP, inversion or safety checker',
        'threshold_provenance': 'unchecked; no security or robustness estimate'}
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
