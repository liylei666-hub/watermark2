"""CPU checks using independent analytic polynomial and split-backward examples."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU checks require CUDA_VISIBLE_DEVICES=""')
import unittest
from components import decompose


class ChainTests(unittest.TestCase):
    def test_nonlinearity_in_inverse(self):
        # T(z)=z^2, L(y)=y^2. T's central secant is exact; L adds 4*z*eps^2.
        z, eps = 2., .125
        y=z*z
        b=2*y*((z+eps)**2-(z-eps)**2)/(2*eps)
        c=((z+eps)**4-(z-eps)**4)/(2*eps)
        values=decompose(4*z**3,b,c)
        self.assertEqual(values['map_linearization_residual'],0.)
        self.assertEqual(values['inverse_linearization_residual'],-4*z*eps**2)

    def test_nonlinearity_in_map(self):
        # T(z)=z^3, L(y)=y. Entire residual belongs to the map.
        z, eps = 2., .125
        b=((z+eps)**3-(z-eps)**3)/(2*eps)
        values=decompose(3*z*z,b,b)
        self.assertEqual(values['map_linearization_residual'],-eps**2)
        self.assertEqual(values['inverse_linearization_residual'],0.)

    def test_split_vjp_with_frozen_parameters(self):
        import torch
        weight=torch.tensor([2.,-1.],requires_grad=False,dtype=torch.float64)
        z=torch.tensor([.2,.7],requires_grad=True,dtype=torch.float64)
        y=torch.sin(z*weight)
        (y.square().sum()).backward()
        original=z.grad.clone()
        y_leaf=y.detach().requires_grad_(True)
        y_leaf.square().sum().backward()
        z.grad=None
        torch.sin(z*weight).backward(y_leaf.grad)
        self.assertTrue(torch.equal(z.grad,original))


if __name__ == '__main__':
    unittest.main()
