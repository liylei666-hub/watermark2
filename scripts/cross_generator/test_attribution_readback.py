import unittest
import numpy as np
from attribution_readback import measure
from linear_probe import predict


class AttributionTests(unittest.TestCase):
    def test_arbitrary_fixed_affine_map_decomposes_exactly(self):
        rng=np.random.default_rng(241001)
        model=dict(mean=rng.normal(size=8),scale=np.exp(rng.normal(size=8)),coefficients=rng.normal(size=(9,4)))
        a=rng.normal(size=(1,4,64,64));z=rng.normal(size=a.shape);b=predict(model,a)
        value=measure(model,a,b,z)
        self.assertAlmostEqual(sum(value['mse_algebraic_contributions'].values()),value['mse_improvement'],places=11)
        self.assertAlmostEqual(value['bit_error_improvement'],np.mean((a>=0)!=(z>=0))-np.mean((b>=0)!=(z>=0)))

    def test_positive_scaling_changes_mse_but_no_bits(self):
        coefficients=np.zeros((9,4));coefficients[1:5]=np.eye(4)*.8
        model=dict(mean=np.zeros(8),scale=np.ones(8),coefficients=coefficients)
        a=np.random.default_rng(241002).normal(size=(1,4,64,64));z=.8*a
        value=measure(model,a,predict(model,a),z)
        self.assertGreater(value['mse_improvement'],0)
        self.assertEqual(value['total_bit_flips'],0)
        self.assertAlmostEqual(value['mse_algebraic_contributions']['raw_diagonal'],value['mse_improvement'])


if __name__=='__main__':unittest.main()
