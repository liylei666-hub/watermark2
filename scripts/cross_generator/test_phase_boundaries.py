"""CPU test-phase contract checks using synthetic images and arrays."""
import ast
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
import io_contract as c
import phase_contract as phase
import evaluate_tests


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def images(self):
        source=self.root/'source';source.mkdir();paths={}
        for sid in c.SPLITS['target_test']:
            path=source/(sid+'.png');Image.new('RGB',(512,512),(20,80,130)).save(path);paths[sid]=path
        out=self.root/'images';digest=phase.export_images(out,paths)
        return out,digest

    def test_image_bundle_contains_only_fixed_images(self):
        out,digest=self.images();self.assertEqual(len(phase.image_bundle(out,digest)['rows']),8)
        (out/'original_noise.npy').write_bytes(b'not allowed')
        with self.assertRaises(ValueError):phase.image_bundle(out,digest)

    def test_image_metadata_cannot_carry_target_rng_or_key(self):
        out,_=self.images();path=out/'images.json';data=c.read(path)
        data['rows'][0]['target_seed']=14001;path.unlink();c.write(path,data)
        with self.assertRaises(ValueError):phase.image_bundle(out,c.sha(path))

    def test_incomplete_or_modified_image_delivery_rejected(self):
        out,digest=self.images();path=out/(c.SPLITS['target_test'][0]+'.png')
        Image.new('RGB',(512,512),'red').save(path)
        with self.assertRaises(ValueError):phase.image_bundle(out,digest)
        path.unlink()
        with self.assertRaises(ValueError):phase.image_bundle(out,digest)

    def test_source_snapshot_matches_committed_seal(self):
        root=Path(__file__).resolve().parents[2]/'runs/24_cross_generator_20261018T044821Z'
        if not root.exists():self.skipTest('Archived source evidence unavailable')
        phase.verify_source(root)

    def test_evaluation_refuses_missing_prediction_seal_before_private_import(self):
        with patch.dict('sys.modules',{'gs_batch':None}):
            with self.assertRaises(FileNotFoundError):
                evaluate_tests.main(self.root,'0'*64,self.root/'private',self.root/'out.json')

    def test_metrics_match_explicit_counts(self):
        z=np.ones(c.SHAPE);a=z.copy();b=z.copy();a.reshape(-1)[:100]=-1;b.reshape(-1)[:20]=-2
        value=evaluate_tests.metrics(a,b,z)
        self.assertEqual(value['baseline_bit_error'],100/z.size)
        self.assertEqual(value['corrected_bit_error'],20/z.size)
        self.assertEqual(value['baseline_mse'],400/z.size)
        self.assertEqual(value['corrected_mse'],180/z.size)

    def test_proxy_worker_has_no_private_or_generator_import(self):
        tree=ast.parse(Path(__file__).with_name('invert_test_images.py').read_bytes())
        names=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):names.extend(a.name for a in n.names)
            if isinstance(n,ast.ImportFrom):names.append(n.module)
        self.assertFalse({'gs_batch','private_state','evaluate_tests','phase_control'} & set(names))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        check=next(n.lineno for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='check_device')
        gpu=next(n.lineno for n in ast.walk(main) if isinstance(n,ast.Import) and any(a.name=='torch' for a in n.names))
        self.assertLess(check,gpu)

    def test_source_mse_improvement_cannot_substitute_test_bit_result(self):
        z=np.full(c.SHAPE,.1);a=np.full(c.SHAPE,10.);b=np.full(c.SHAPE,-.01)
        value=evaluate_tests.metrics(a,b,z)
        self.assertLess(value['corrected_mse'],value['baseline_mse'])
        self.assertGreater(value['corrected_bit_error'],value['baseline_bit_error'])


if __name__=='__main__':unittest.main()
