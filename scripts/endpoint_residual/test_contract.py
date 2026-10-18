import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
import common as c


class Contract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = {'inputs': {}}
        for name, relative in c.expected_inputs().items():
            p = self.root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(name.encode())
            self.cfg['inputs'][name] = dict(path=c.REMOTE + '/' + relative, sha256=c.sha(p))

    def test_all_fixed_inputs(self):
        self.assertEqual(len(c.validate_inputs(self.cfg, self.root)), 21)

    def test_target_input_rejected(self):
        bad = copy.deepcopy(self.cfg)
        bad['inputs']['1/reference']['path'] = c.REMOTE + '/' + c.RUN + '/evaluator_results/1/reference/target_inverse.npy'
        with self.assertRaises(ValueError): c.validate_inputs(bad, self.root)

    def test_added_score_rejected(self):
        self.cfg['inputs']['score'] = {'path': 'metrics.json', 'sha256': '0'*64}
        with self.assertRaises(ValueError): c.validate_inputs(self.cfg, self.root)

    def test_missing_pair_rejected(self):
        del self.cfg['inputs']['3/cover']
        with self.assertRaises(ValueError): c.validate_inputs(self.cfg, self.root)

    def test_modified_input_rejected(self):
        (self.root / c.expected_inputs()['2/jain_png']).write_bytes(b'changed')
        with self.assertRaises(ValueError): c.validate_inputs(self.cfg, self.root)

    def test_squared_error_and_zero_baseline(self):
        a = np.zeros((1,4,64,64), np.float32)
        self.assertEqual(c.mse(a, a+2), 4.)
        self.assertEqual(c.relative_drop(4., 1.), .75)
        self.assertIsNone(c.relative_drop(0., 1.))

    def test_invalid_latent(self):
        a = np.zeros((1,4,64,64), np.float32)
        with self.assertRaises(ValueError): c.mse(a, np.zeros(3))
        a.flat[0] = np.nan
        with self.assertRaises(ValueError): c.mse(a, a)

    def test_delivery_decomposition(self):
        z = np.zeros((1,4,64,64), np.float32)
        a = {name: z.copy() for name in ['reference_z','reference_inverse']}
        for name in ['cover','imprint_png','jain_png','jain_float']: a[name+'_z'] = z+2
        for name, value in [('cover',2),('initial_png',3),('imprint_native',1),('imprint_png',2),('imprint_float',1.5),('jain_png',2)]:
            a[name+'_inverse'] = z+value
        result = c.summarize(a)
        self.assertEqual(result['imprint_native_improvement'], 3.)
        self.assertEqual(result['imprint_png_improvement'], 5.)
        self.assertEqual(result['imprint_png_improvement_retained'], 5/3)
        self.assertEqual(result['imprint_quantization_loss_difference'], 1.75)


if __name__ == '__main__': unittest.main(verbosity=2)
