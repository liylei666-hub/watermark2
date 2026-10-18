"""Synthetic CPU checks for stage24 file boundaries and sealing order."""
import ast
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
import fit_source
import io_contract as c
import predict_fixed


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rng = np.random.default_rng(240001)

    def bundle(self, split, name=None, affine=True):
        name = name or split
        raw = self.root / ('raw_' + name); raw.mkdir()
        entries = {}
        for sid in c.SPLITS[split]:
            noise = self.rng.normal(size=c.SHAPE).astype(np.float32)
            inverse = (2 * noise + .4).astype(np.float32) if affine else noise.copy()
            entry = {}
            for key, value in [('estimate', inverse), ('original_noise', noise)]:
                if key == 'original_noise' and split.endswith('_test'):
                    continue
                path = raw / (sid + '_' + key + '.npy')
                c.save_array(path, value, 'float32'); entry[key] = path
            entries[sid] = entry
        folder = self.root / name
        digest = c.export_bundle(folder, split, entries)
        return folder, digest

    def change_manifest(self, folder, change):
        path = folder / 'bundle.json'; data = c.read(path); change(data)
        path.unlink(); c.write(path, data)
        return c.sha(path)

    def fit(self):
        train, train_sha = self.bundle('train')
        validation, validation_sha = self.bundle('validation')
        out = self.root / 'fit'
        with contextlib.redirect_stdout(io.StringIO()):
            gate, digest = fit_source.main(train, train_sha, validation, validation_sha, out)
        return out, gate, digest

    def test_fixed_split_and_float32_arrays(self):
        folder, digest = self.bundle('train')
        rows = c.load_bundle(folder, 'train', digest)
        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[0]['role'], 'proxy_train')
        self.assertEqual(rows[0]['estimate'].dtype, np.float32)
        with self.assertRaises(ValueError):
            c.load_bundle(folder, 'validation', digest)

    def test_extra_label_in_test_manifest_rejected(self):
        folder, _ = self.bundle('target_test')
        digest = self.change_manifest(folder, lambda d: d['rows'][0].update(original_noise=d['rows'][0]['estimate']))
        with self.assertRaises(ValueError): c.load_bundle(folder, 'target_test', digest)

    def test_unlisted_private_file_rejected(self):
        folder, digest = self.bundle('proxy_test')
        (folder / 'target_seed.json').write_text('{}')
        with self.assertRaises(ValueError): c.load_bundle(folder, 'proxy_test', digest)

    def test_mutated_file_and_manifest_rejected(self):
        folder, digest = self.bundle('proxy_test')
        path = next(folder.glob('*.npy'))
        value = np.load(path, allow_pickle=False); value.flat[0] += 1
        with path.open('wb') as stream: np.save(stream, value, allow_pickle=False)
        with self.assertRaises(ValueError): c.load_bundle(folder, 'proxy_test', digest)
        with (folder / 'bundle.json').open('a') as stream: stream.write(' ')
        with self.assertRaises(ValueError): c.load_bundle(folder, 'proxy_test', digest)

    def test_reordered_duplicate_missing_samples_rejected(self):
        for case in ('reordered', 'duplicate', 'missing'):
            folder, _ = self.bundle('train', name=case)
            def change(data):
                if case == 'reordered': data['rows'].reverse()
                elif case == 'duplicate': data['rows'][1] = data['rows'][0]
                else: data['rows'].pop()
            digest = self.change_manifest(folder, change)
            with self.assertRaises(ValueError): c.load_bundle(folder, 'train', digest)

    def test_path_traversal_rejected_before_file_read(self):
        folder, _ = self.bundle('target_test')
        digest = self.change_manifest(folder, lambda d: d['rows'][0]['estimate'].update(path='../private_eval/noise.npy'))
        with self.assertRaises(ValueError): c.load_bundle(folder, 'target_test', digest)
        for name in ('../a.npy', '/tmp/a.npy', 'a\\b.npy', 'C:a.npy', 'sub/a.npy'):
            with self.assertRaises(ValueError): c.checked_file(folder, name)

    def test_hardlink_rejected(self):
        folder, digest = self.bundle('proxy_test'); path = next(folder.glob('*.npy'))
        os.link(path, self.root / 'linked.npy')
        with self.assertRaises(ValueError): c.load_bundle(folder, 'proxy_test', digest)

    def test_symlink_rejected(self):
        folder, digest = self.bundle('proxy_test'); path = next(folder.glob('*.npy'))
        actual = self.root / 'actual.npy'; path.rename(actual)
        try: path.symlink_to(actual)
        except OSError as exc:
            self.skipTest('Host does not allow symlink creation: ' + str(exc))
        with self.assertRaises(ValueError): c.load_bundle(folder, 'proxy_test', digest)

    def test_duplicate_json_and_nonfinite_json_rejected(self):
        path = self.root / 'data.json'
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            path.write_text(text)
            with self.assertRaises(ValueError): c.read(path)

    def test_wrong_tensor_shape_dtype_and_nonfinite_rejected(self):
        path = self.root / 'data.npy'
        for value in (np.ones(c.SHAPE, dtype=np.float64), np.ones((1,4,32,32), dtype=np.float32),
                      np.full(c.SHAPE, np.nan, dtype=np.float32)):
            with path.open('wb') as stream: np.save(stream, value, allow_pickle=False)
            with self.assertRaises(ValueError): c.array_record(path)

    def test_png_roundtrip_exact_pixels_and_no_overwrite(self):
        pixels = self.rng.integers(0, 256, (512,512,3), dtype=np.uint8)
        image = Image.fromarray(pixels); path = self.root / 'fixture.png'
        reread, record = c.save_png_readback(image, path)
        self.assertEqual(reread.tobytes(), image.tobytes())
        self.assertEqual(record, c.png_record(path))
        with self.assertRaises(FileExistsError): c.save_png_readback(image, path)

    def test_fit_sealed_before_validation_read(self):
        train, ts = self.bundle('train'); val, vs = self.bundle('validation')
        out = self.root / 'fit'; original = fit_source.load_bundle; order = []
        def traced(folder, split, digest):
            if split == 'validation':
                record = c.read(out / 'fit_record.json')
                self.assertEqual(record['model_sha256'], c.sha(out / 'model.json'))
            order.append(split)
            return original(folder, split, digest)
        with patch.object(fit_source, 'load_bundle', side_effect=traced), contextlib.redirect_stdout(io.StringIO()):
            gate, digest = fit_source.main(train, ts, val, vs, out)
        self.assertEqual(order, ['train', 'validation'])
        self.assertTrue(gate['pass']); c.verify_seal(out, digest)

    def test_predict_receives_inverse_only_and_preserves_baseline(self):
        source, gate, digest = self.fit(); inputs, ish = self.bundle('target_test')
        self.assertTrue(gate['pass'])
        out = self.root / 'predictions'
        with contextlib.redirect_stdout(io.StringIO()):
            psha = predict_fixed.main(source, digest, inputs, 'target_test', ish, out)
        self.assertEqual(len(c.verify_seal(out, psha)['files']), 16)
        sid = c.SPLITS['target_test'][0]
        np.testing.assert_array_equal(np.load(inputs / (sid + '_estimate.npy'), allow_pickle=False),
                                      np.load(out / (sid + '_baseline.npy'), allow_pickle=False))
        with (out / (sid + '_corrected.npy')).open('ab') as stream: stream.write(b'x')
        with self.assertRaises(ValueError): c.verify_seal(out, psha)

    def test_failed_gate_rejects_prediction_before_test_read(self):
        source, _, digest = self.fit()
        gate = c.read(source / 'source_gate.json'); gate['pass'] = False
        (source / 'source_gate.json').unlink(); c.write(source / 'source_gate.json', gate)
        old = c.read(source / 'seal.json'); (source / 'seal.json').unlink()
        digest = c.seal(source, old['files'], old['metadata'])
        with patch.object(predict_fixed, 'load_bundle', side_effect=AssertionError('Test data read')) as load:
            with self.assertRaises(ValueError):
                predict_fixed.main(source, digest, self.root / 'absent', 'target_test', 'absent', self.root / 'out')
            load.assert_not_called()

    def test_training_entry_point_excludes_target_bundle(self):
        train, ts = self.bundle('target_test'); val, vs = self.bundle('validation')
        with self.assertRaises(ValueError): fit_source.main(train, ts, val, vs, self.root / 'bad_fit')
        self.assertFalse((self.root / 'bad_fit/model.json').exists())

    def test_cpu_modules_do_not_import_diffusion_or_private_state(self):
        forbidden = {'torch', 'diffusers', 'transformers', 'private_state', 'runtime', 'subprocess'}
        for name in ('io_contract.py', 'fit_source.py', 'predict_fixed.py', 'linear_probe.py'):
            tree = ast.parse(Path(__file__).with_name(name).read_bytes())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import): imported.update(n.name.split('.')[0] for n in node.names)
                elif isinstance(node, ast.ImportFrom): imported.add((node.module or '').split('.')[0])
            self.assertFalse(imported & forbidden, name)


if __name__ == '__main__':
    unittest.main()
