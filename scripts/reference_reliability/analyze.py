"""CPU analysis of saved arrays. No model loading, selection or optimization."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU visibility required')
import sys
from pathlib import Path
import numpy as np
from common import read, write, sha
from boundary import verify_seal, load_inverse
from scores import score_vectors, cdf_bins, endpoints

def analyze(root):
    root = Path(root); verify_seal(root); rows = []
    for k in range(1, 5):
        arrays = {step: load_inverse(root / ('proxy_' + str(step)) / str(k) / 'inverse.npy') for step in (25, 50, 100)}
        # Check all saved proxy arrays, even though only z50 supplies predictions.
        quantized = {step: cdf_bins(z) for step, z in arrays.items()}
        scores = score_vectors(arrays)
        for name, value in scores.items():
            stored = np.load(root / 'scores' / str(k) / (name + '.npy'), allow_pickle=False)
            if not np.array_equal(stored, value):
                raise ValueError('Stored score differs from frozen formula')
        original_path = root / 'reference' / str(k) / 'original_noise.npy'
        if sha(original_path) != read(root / 'reference' / str(k) / 'record.json')['original_noise']['sha256']:
            raise ValueError('Original latent changed')
        original = cdf_bins(load_inverse(original_path))
        inverse = cdf_bins(load_inverse(root / 'evaluation' / str(k) / 'inverse.npy'))
        metrics = read(root / 'evaluation' / str(k) / 'metrics.json')
        rows.append(dict(task_id=k, original=endpoints(scores, quantized[50], original),
                         reference_reinversion=endpoints(scores, quantized[50], inverse),
                         reference_gs=metrics))
    return dict(completed=True, rows=rows,
                primary_mean=float(np.mean([row['original']['baseline_minus_consistency']['0.5'] for row in rows])),
                all_cdf_sign_checks_passed=True, images=4, coordinate_independence_assumed=False,
                candidate_attacks=0, full_defense_acceptance=None, automatic_method_promotion=False,
                proxy_seal_sha256=sha(root / 'proxy_sealed.json'))

if __name__ == '__main__':
    write(Path(sys.argv[2]), analyze(Path(sys.argv[1])))
