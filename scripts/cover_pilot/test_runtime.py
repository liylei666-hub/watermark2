"""CPU preimport device gates and snapshot dispatch with synthetic dependencies."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only tests')
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
import sys
import contract as c
import runtime as r


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.uuid='GPU-test'
        self.cfg=dict(allowed_gpu_uuids={'0':self.uuid})
        self.env=dict(CUDA_VISIBLE_DEVICES=self.uuid,CUDA_DEVICE_ORDER='PCI_BUS_ID',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')

    def check(self,row,apps):
        with patch.dict(os.environ,self.env),patch.object(r,'verify_runtime',return_value=self.cfg),patch.object(r.subprocess,'check_output',side_effect=[row,apps]):
            return r.check_device(self.root/'runtime.json',self.root)

    def test_idle_verified(self):
        self.assertEqual(self.check('0, GPU-test, NVIDIA GeForce RTX 3090, 4, 0\n',''),self.cfg)

    def test_foreign_process_blocks(self):
        with self.assertRaises(RuntimeError):self.check('0, GPU-test, NVIDIA GeForce RTX 3090, 4, 0\n','GPU-test, 123, 1024\n')

    def test_uuid_mismatch_blocks(self):
        with self.assertRaises(RuntimeError):self.check('1, GPU-other, NVIDIA GeForce RTX 3090, 4, 0\n','')

    def test_ambiguous_memory_blocks(self):
        with self.assertRaises(ValueError):self.check('0, GPU-test, NVIDIA GeForce RTX 3090, N/A, 0\n','')

    def test_busy_memory_blocks(self):
        with self.assertRaises(RuntimeError):self.check('0, GPU-test, NVIDIA GeForce RTX 3090, 1000, 0\n','')

    def test_unrestricted_visibility_blocks_before_queries(self):
        env=dict(self.env,CUDA_VISIBLE_DEVICES='')
        with patch.dict(os.environ,env),patch.object(r,'verify_runtime',return_value=self.cfg),patch.object(r.subprocess,'check_output') as query:
            with self.assertRaises(ValueError):r.check_device(self.root/'runtime.json',self.root)
            query.assert_not_called()

    def test_offline_requirement_blocks_before_queries(self):
        env=dict(self.env,HF_HUB_OFFLINE='0')
        with patch.dict(os.environ,env),patch.object(r,'verify_runtime',return_value=self.cfg),patch.object(r.subprocess,'check_output') as query:
            with self.assertRaises(ValueError):r.check_device(self.root/'runtime.json',self.root)
            query.assert_not_called()

    def test_exact_snapshot_passed_to_official_dispatch_class(self):
        seen=[]
        def cls(**kwargs):seen.append(kwargs);return 'provider-fixture'
        model=dict(model_id='synthetic/model',snapshot='/synthetic/snapshot')
        fake=SimpleNamespace(PIPE_PROVIDERS={model['model_id']:cls},SCHEDULER_CLASSES={'DDIM':('forward','inverse')})
        with patch.dict(sys.modules,{'utils.pipe':SimpleNamespace(pipe_utils=fake)}):
            self.assertEqual(r.official_provider(model),'provider-fixture')
        self.assertEqual(seen[0]['pretrained_model_name_or_path'],model['snapshot'])
        self.assertEqual(seen[0]['scheduler_classes'],('forward','inverse'))
        self.assertEqual(seen[0]['device'],'cuda:0')
        self.assertIsNone(seen[0]['vae_id'])


if __name__=='__main__':unittest.main(verbosity=2)
