"""CPU regression for the recorder's gradient API; no model weights loaded."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('Set CUDA_VISIBLE_DEVICES="" for CPU regression')
import unittest
import torch
from torch.utils.checkpoint import checkpoint


def recorded_gradient(loss, variable):
    variable.grad = None
    loss.backward()
    if variable.grad is None:
        raise RuntimeError('Missing optimized-latent gradient')
    return variable.grad.detach().clone()


class CheckpointGradientTests(unittest.TestCase):
    def test_reproduces_original_api_failure(self):
        x = torch.tensor([.2, -.5, 1.], requires_grad=True)
        loss = checkpoint(lambda a: a.square().sum(), x, use_reentrant=True)
        with self.assertRaisesRegex(RuntimeError, 'incompatible with .grad'):
            torch.autograd.grad(loss, x)

    def test_backward_matches_direct_gradient(self):
        x = torch.tensor([.2, -.5, 1.], requires_grad=True)
        loss = checkpoint(lambda a: a.square().sum(), x, use_reentrant=True)
        actual = recorded_gradient(loss, x)
        expected = 2 * x.detach()
        self.assertTrue(torch.equal(actual, expected))
        self.assertFalse(actual.requires_grad)

    def test_two_records_do_not_accumulate_or_alias(self):
        x = torch.tensor([.2, -.5, 1.], requires_grad=True)
        first = recorded_gradient(checkpoint(lambda a: a.square().sum(), x, use_reentrant=True), x)
        second = recorded_gradient(checkpoint(lambda a: 3*a.square().sum(), x, use_reentrant=True), x)
        self.assertTrue(torch.equal(first, 2*x.detach()))
        self.assertTrue(torch.equal(second, 6*x.detach()))
        self.assertNotEqual(first.data_ptr(), x.grad.data_ptr())
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == '__main__':
    unittest.main()
