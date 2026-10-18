"""Synthetic CPU regression checks, not diffusion-model experiments."""
import unittest
import numpy as np
from linear_probe import features, fit, predict, source_gate, RIDGE


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(12001)
        self.records = []
        for i in range(3):
            z = self.rng.normal(size=(1, 4, 8, 8))
            self.records.append(dict(sample_id=str(i), role='proxy_train',
                                     generator_role='proxy', estimate=2*z + .4,
                                     original_noise=z))

    def test_matches_augmented_least_squares(self):
        m = fit(self.records)
        x = np.concatenate([features(r['estimate']) for r in self.records])
        y = np.concatenate([r['original_noise'][0].reshape(4, -1).T for r in self.records])
        a = np.column_stack((np.ones(len(x)), (x-m['mean'])/m['scale']))
        reg = np.diag([0.] + [np.sqrt(len(x)*RIDGE)]*8)
        expected = np.linalg.lstsq(np.vstack((a, reg)), np.vstack((y, np.zeros((9, 4)))), rcond=None)[0]
        np.testing.assert_allclose(m['coefficients'], expected, atol=1e-10, rtol=1e-10)

    def test_recovery_on_independent_affine_fixture(self):
        m = fit(self.records); z = self.rng.normal(size=(1,4,8,8)); a = 2*z+.4
        b = predict(m, a)
        self.assertLess(np.mean((b-z)**2), 1e-4)
        self.assertTrue(source_gate([a], [b], [z])['pass'])

    def test_target_and_holdout_labels_rejected(self):
        for field, value in [('role','target_test'), ('role','proxy_validation'), ('generator_role','target')]:
            rows = [dict(r) for r in self.records]; rows[0][field] = value
            with self.assertRaises(ValueError): fit(rows)

    def test_duplicates_and_nonfinite_rejected(self):
        with self.assertRaises(ValueError): fit(self.records + [self.records[0]])
        rows = [dict(r) for r in self.records]; rows[0]['original_noise'] = np.full((1,4,8,8), np.nan)
        with self.assertRaises(ValueError): fit(rows)

    def test_constant_feature_handling(self):
        rows = [dict(sample_id='constant', role='proxy_train', generator_role='proxy',
                     estimate=np.ones((1,4,8,8)), original_noise=np.full((1,4,8,8), .3))]
        m=fit(rows); np.testing.assert_allclose(predict(m, rows[0]['estimate']), .3, atol=1e-12)

    def test_lower_mse_does_not_override_bit_regression(self):
        z=np.full((1,4,8,8), .1); a=np.full_like(z, 10.); b=np.full_like(z, -.01)
        gate=source_gate([a],[b],[z]); self.assertGreater(gate['mse_differences'][0],0)
        self.assertLess(gate['bit_differences'][0],0); self.assertFalse(gate['pass'])


if __name__ == '__main__':
    unittest.main()
