"""CPU adversarial tests of scientific endpoints and information-boundary checks."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU visibility required')
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
import boundary as b
from scores import score_vectors, ranking, auc, endpoints, cdf_bins

class Scores(unittest.TestCase):
    def test_disagreement_and_scaling(self):
        x = np.array([1., -2., 3., -4.]); y = x.copy(); y[0] *= -1
        a = score_vectors({25:y, 50:x, 100:x})
        self.assertLess(a['consistency'][0], 0)
        z = score_vectors({25:y*7, 50:x*2, 100:x*11})
        np.testing.assert_allclose(a['consistency'], z['consistency'])
        np.testing.assert_allclose(a['baseline'], z['baseline'])

    def test_ranking_tie_index(self):
        self.assertEqual(ranking([2., 1., 2., -1.]).tolist(), [0, 2, 1, 3])

    def test_invalid_rms(self):
        for x in ([0, 0], [1, np.nan], [np.inf, 1]):
            with self.assertRaises(ValueError): score_vectors({25:x, 50:x, 100:x})

    def test_auc_against_pairwise_oracle(self):
        rng = np.random.default_rng(2301)
        for _ in range(40):
            s = rng.integers(-2, 3, size=13).astype(float); y = rng.integers(0, 2, size=13).astype(bool)
            expected = None if y.all() or not y.any() else float(np.mean([(a > b) + .5*(a == b) for a in s[y] for b in s[~y]]))
            self.assertEqual(auc(s, y), expected)
        self.assertIsNone(auc([1, 2], np.ones(2, dtype=bool)))
        self.assertIsNone(auc([1, 2], np.zeros(2, dtype=bool)))

    def test_ceil_and_risk_direction(self):
        s = dict(baseline=np.arange(5), consistency=-np.arange(5))
        x = endpoints(s, [0]*5, [0, 0, 0, 1, 1])
        self.assertEqual(x['risks']['baseline']['0.5'], 2/3)
        self.assertEqual(x['baseline_minus_consistency']['0.5'], 2/3)
        self.assertEqual(x['baseline_minus_consistency']['1.0'], 0)

    def test_cdf_sign_rule(self):
        self.assertEqual(cdf_bins([-20., -1., -1e-6, 0., 1e-6, 20.]).tolist(), [0, 0, 0, 1, 1, 1])
        with self.assertRaises(ValueError): cdf_bins([-1e-30])

class Boundary(unittest.TestCase):
    def fixture(self, root):
        for k in range(1, 5):
            f = root/'reference'/str(k); f.mkdir(parents=True)
            Image.new('RGB', (512, 512), (k, 0, 0)).save(f/'reference.png')
        b.export_inputs(root, {'synthetic': True})
        for step in (25, 50, 100):
            for k in range(1, 5):
                f=root/('proxy_'+str(step))/str(k);f.mkdir(parents=True)
                with (f/'inverse.npy').open('xb') as out:
                    np.save(out, np.full((1,4,64,64), k, dtype=np.float32))

    def test_seal_tamper_and_exclusive_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);b.seal_scores(root);b.verify_seal(root)
            with self.assertRaises(FileExistsError):b.seal_scores(root)
            p=root/'scores/1/consistency.npy';x=np.load(p);x[0]*=-1;np.save(p,x)
            with self.assertRaises(ValueError):b.verify_seal(root)

    def test_extra_proxy_fields_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            p=root/'proxy_inputs/jobs.json';v=b.read(p);v['target_score']=.9
            import json
            p.write_text(json.dumps(v))
            with self.assertRaises(ValueError):b.validate_inputs(root/'proxy_inputs')

    def test_private_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);self.assertTrue(b.publishable_files(root))
            (root/'reference/1/secret.bin').write_bytes(b'synthetic')
            with self.assertRaises(ValueError):b.publishable_files(root)

if __name__=='__main__':unittest.main(verbosity=2)
