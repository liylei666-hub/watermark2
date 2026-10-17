import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU tests require CUDA_VISIBLE_DEVICES=""')
import unittest
import numpy as np
from measures import summarize_gradients


class GradientMetricsTests(unittest.TestCase):
    def test_parallel_with_scale(self):
        a = np.array([3., 4.])
        r = summarize_gradients(a, 2*a)
        self.assertAlmostEqual(r['cosine'], 1.)
        self.assertAlmostEqual(r['native_l2'], 5.)
        self.assertAlmostEqual(r['delivery_to_native_l2_ratio'], 2.)

    def test_opposed_and_orthogonal(self):
        a = np.array([1., 0.])
        self.assertEqual(summarize_gradients(a, -a)['cosine'], -1.)
        self.assertEqual(summarize_gradients(a, np.array([0., 1.]))['cosine'], 0.)

    def test_bad_inputs_fail(self):
        a = np.ones(2)
        for b in [np.zeros(2), np.array([np.nan, 1]), np.ones(3)]:
            with self.assertRaises(ValueError):
                summarize_gradients(a, b)


if __name__ == '__main__':
    unittest.main()
