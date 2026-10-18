"""CPU regressions for the actual split-gradient update and image-only attack interface."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import json,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from common import c,METHODS,PARAMETERS,validate_job

class Interface(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('reference','cover'):Image.new('RGB',(512,512),(81,121,161)).save(self.root/(name+'.png'))
        self.job=dict(version=1,task_id=12,method='delivery',seed=27312,reference=c.png_record(self.root/'reference.png'),cover=c.png_record(self.root/'cover.png'),
            proxy=dict(model_id=c.PROXY_ID,revision=c.PROXY_REVISION,snapshot=c.PROXY_SNAPSHOT,dtype='float32',resolution=512),parameters=PARAMETERS['delivery'])
    def tearDown(self):self.tmp.cleanup()
    def check(self):
        path=self.root/'job.json';path.write_text(json.dumps(self.job));return validate_job(path)
    def test_valid_last_task(self):self.assertEqual(self.check()['task_id'],12)
    def test_target_information_rejected(self):
        self.job['target_score']=1
        with self.assertRaises(ValueError):self.check()
    def test_image_change_rejected(self):
        Image.new('RGB',(512,512),'black').save(self.root/'reference.png')
        with self.assertRaises(ValueError):self.check()
    def test_parameters_rejected(self):
        self.job['parameters']=dict(self.job['parameters'],updates=11)
        with self.assertRaises(ValueError):self.check()

class Gradient(unittest.TestCase):
    def test_split_matches_direct_with_checkpoint(self):
        import torch
        from torch.utils.checkpoint import checkpoint
        from common import module
        split_gradient=module('comparison_attack',Path(__file__).parent/'attack.py').split_gradient
        torch.manual_seed(27000)
        matrix=torch.randn(4,4,dtype=torch.float64)
        mapping=lambda z:(matrix@z).tanh().clamp(-.7,.7)
        inverse=lambda z:checkpoint(lambda v:(v*1.2).sin(),z,use_reentrant=True)
        a=torch.randn(4,dtype=torch.float64,requires_grad=True);b=a.detach().clone().requires_grad_(True);target=torch.randn(4,dtype=torch.float64)
        direct=torch.nn.functional.mse_loss(inverse(mapping(a)),target);direct.backward()
        loss=split_gradient(b,mapping,inverse,target)
        self.assertEqual(loss,float(direct.detach()));torch.testing.assert_close(a.grad,b.grad,rtol=0,atol=1e-14)
        x=torch.nn.Parameter(a.detach().clone());y=torch.nn.Parameter(b.detach().clone())
        ox=torch.optim.Adam([x],lr=.01);oy=torch.optim.Adam([y],lr=.01)
        for _ in range(3):
            ox.zero_grad();oy.zero_grad();torch.nn.functional.mse_loss(inverse(mapping(x)),target).backward();split_gradient(y,mapping,inverse,target);ox.step();oy.step()
        torch.testing.assert_close(x,y,rtol=0,atol=1e-14)
        self.assertFalse(torch.cuda.is_initialized())

if __name__=='__main__':unittest.main()
