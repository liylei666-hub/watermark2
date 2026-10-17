"""CPU tests for source isolation, file integrity and exact image serialization."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU-only tests require CUDA_VISIBLE_DEVICES=""')
import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from experiment import EXPORTS, check_binding, extract_definitions, write


class ContractTests(unittest.TestCase):
    def test_cpu_import_loads_no_model_library(self):
        import sys
        self.assertNotIn('diffusers', sys.modules)

    def test_missing_binding(self):
        with patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': ''}):
            with self.assertRaises(ValueError):
                check_binding({'allowed_gpu_uuids': {'0': 'GPU-example'}})

    def test_multiple_or_unauthorized_devices(self):
        for value in ['0', 'GPU-example,GPU-other', 'GPU-other']:
            with patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': value}):
                with self.assertRaises(ValueError):
                    check_binding({'allowed_gpu_uuids': {'0': 'GPU-example'}})

    def test_offline_required(self):
        with patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': 'GPU-example',
                'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'HF_HUB_OFFLINE': '0'}):
            with self.assertRaises(ValueError):
                check_binding({'allowed_gpu_uuids': {'0': 'GPU-example'}})

    def test_hash_and_definition_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'helper.py'
            p.write_text('raise RuntimeError("ENTRY MUST NOT RUN")\n' +
                         '\n'.join('def ' + name + '():\n    pass' for name in sorted(EXPORTS)))
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            selected = extract_definitions(p, h)
            namespace = {}
            exec(compile(selected, str(p), 'exec'), namespace)
            self.assertEqual({x for x in namespace if not x.startswith('__')}, EXPORTS)
            p.write_text(p.read_text() + '\n# changed\n')
            with self.assertRaises(ValueError):
                extract_definitions(p, h)

    def test_missing_definition_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'helper.py'
            p.write_text('def pixel_to_latent(): pass\n')
            with self.assertRaises(ValueError):
                extract_definitions(p, hashlib.sha256(p.read_bytes()).hexdigest())

    def test_existing_record_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'record.json'
            write(p, {'original': 1})
            with self.assertRaises(FileExistsError):
                write(p, {'replacement': 1})
            self.assertEqual(json.loads(p.read_text()), {'original': 1})

    def test_pixel_floor_and_png_readback(self):
        # Synthetic pixels test the installed torchvision/PIL conversion, not a model result.
        import io
        import numpy as np
        import torch
        from PIL import Image
        from torchvision.transforms.functional import to_pil_image, to_tensor
        x = torch.tensor([0., .1, .5, .999, 1.], dtype=torch.float32).reshape(1, 1, 5).repeat(3, 1, 1)
        im = to_pil_image(x)
        self.assertEqual(np.asarray(im)[0, :, 0].tolist(), [0, 25, 127, 254, 255])
        with io.BytesIO() as buf:
            im.save(buf, format='PNG')
            buf.seek(0)
            loaded = Image.open(buf).convert('RGB')
            self.assertTrue(np.array_equal(np.asarray(loaded), np.asarray(im)))
            self.assertTrue(torch.equal(to_tensor(loaded), to_tensor(im)))


if __name__ == '__main__':
    unittest.main()
