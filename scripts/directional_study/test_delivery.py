"""Synthetic CPU checks of the scientific delivery and finite-step contracts."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU visibility must be empty')
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
import delivery as d


class Tests(unittest.TestCase):
    def setUp(self):
        self.cover = np.full((4, 5, 3), 128, dtype=np.uint8)
        self.a = np.ones(self.cover.shape, dtype=np.float32)
        self.b = -self.a

    def build(self):
        return d.build(self.cover, self.a, self.b, 801)

    def test_sign_and_units(self):
        images, mask, stat = self.build()
        self.assertTrue((images['vae_descent'] == 127).all())
        self.assertTrue((images['inverse_descent'] == 129).all())
        self.assertEqual(stat['squared_l2_integer'], 60)
        self.assertEqual(stat['linf_rgb01'], 1/255)
        self.assertEqual(stat['mse_rgb01'], 1/255**2)

    def test_boundary_and_gradient_zero_intersection(self):
        self.cover[0, 0] = [0, 255, 1]
        self.a[0, 1, 0] = 0
        self.b[0, 1, 1] = 0
        images, mask, stat = self.build()
        self.assertEqual(stat['active_channels'], 56)
        self.assertEqual(mask[0, 0].tolist(), [False, False, True])
        self.assertEqual(mask[0, 1].tolist(), [False, False, True])
        for im in images.values():
            self.assertEqual(int(np.square(im.astype(np.int64)-self.cover).sum()), 56)
            self.assertTrue(np.array_equal(im[~mask], self.cover[~mask]))

    def test_ascent_descent_symmetry(self):
        images, _, _ = self.build()
        for prefix in ['vae', 'inverse']:
            self.assertTrue(np.array_equal(images[prefix+'_ascent'].astype(int)+images[prefix+'_descent'], 2*self.cover.astype(int)))

    def test_positive_gradient_scale_invariance(self):
        first, _, _ = self.build()
        second, _, _ = d.build(self.cover, 4*self.a, 0.25*self.b, 801)
        for name in d.CONDITIONS:
            self.assertTrue(np.array_equal(first[name], second[name]))

    def test_random_reproducible(self):
        a, _, _ = self.build(); b, _, _ = self.build()
        self.assertTrue(np.array_equal(a['random'], b['random']))
        self.assertEqual(set(np.unique(a['random']).tolist()), {127, 129})

    def test_nonfinite_rejected(self):
        for value in [np.nan, np.inf, -np.inf]:
            self.a[0, 0, 0] = value
            with self.assertRaises(ValueError): self.build()

    def test_insufficient_support_rejected(self):
        self.a[:3] = 0
        with self.assertRaises(ValueError): self.build()

    def test_wrong_gradient_shape_rejected(self):
        self.a = self.a[:, :, :2]
        with self.assertRaises(ValueError): self.build()

    def test_exact_quadratic_central_difference(self):
        x=np.array([0.2, 0.6]); delta=np.array([1/255, -1/255])
        loss=lambda v: float(np.sum(v*v))
        r=d.derivative_check(2*x,delta,loss(x-delta),loss(x+delta))
        self.assertLess(r['relative_error'], 1e-12)
        self.assertTrue(r['within_predeclared_tolerance'])

    def test_wrong_gradient_is_flagged(self):
        r=d.derivative_check(np.ones(3),np.ones(3)/255,1.,1.)
        self.assertFalse(r['within_predeclared_tolerance'])

    def test_png_readback_and_exclusive_output(self):
        images, mask, stat = self.build()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'probes'
            result=d.export(out,self.cover,images,mask,stat)
            self.assertEqual(set(result['conditions']),set(d.CONDITIONS))
            for name in d.CONDITIONS:
                with Image.open(out/(name+'.png')) as im:
                    self.assertTrue(np.array_equal(np.asarray(im),images[name]))
            with self.assertRaises(FileExistsError): d.export(out,self.cover,images,mask,stat)

    def test_tampered_candidate_rejected_before_export(self):
        images, mask, stat = self.build()
        images['vae_descent'][0,0,0]=120
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'probes'
            with self.assertRaises(ValueError): d.export(out,self.cover,images,mask,stat)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        gpu_used=False,models_loaded=False,new_model_experiments_run=0,
        scope='synthetic RGB arrays and quadratic functions; no research images or model gradients')))
    raise SystemExit(0 if result.wasSuccessful() else 1)
