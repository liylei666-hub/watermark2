"""CPU differentiation checks, using synthetic functions and an AST VAE stub."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import ast,hashlib,json,unittest,types
from pathlib import Path
import torch
from torch.utils.checkpoint import checkpoint
from gradient_core import objective_gradient

class Tests(unittest.TestCase):
    def test_chain_and_rgb_units(self):
        x=torch.full((1,3,2,2),.6,dtype=torch.float64)
        _,g,_=objective_gradient(x,lambda v:2*v-1,lambda z:3*z,torch.zeros_like(x))
        self.assertTrue(torch.allclose(g,36*(2*x-1)/x.numel(),atol=1e-14,rtol=0))

    def test_reentrant_checkpoint(self):
        x=torch.full((1,3,2,2),.6,dtype=torch.float64)
        _,g,_=objective_gradient(x,lambda v:2*v-1,
            lambda z:checkpoint(lambda v:3*v,z,use_reentrant=True),torch.zeros_like(x))
        self.assertTrue(torch.allclose(g,36*(2*x-1)/x.numel(),atol=1e-14,rtol=0))

    def test_original_pixels_not_mutated(self):
        x=torch.full((1,3,2,2),.6);before=x.clone()
        objective_gradient(x,lambda v:v,lambda z:z,torch.zeros_like(x))
        self.assertTrue(torch.equal(x,before));self.assertIsNone(x.grad)

    def test_live_reference_rejected(self):
        x=torch.full((1,3,2,2),.6)
        with self.assertRaises(ValueError):
            objective_gradient(x,lambda v:v,lambda z:z,torch.zeros_like(x,requires_grad=True))

    def test_nonfinite_gradient_rejected(self):
        x=torch.zeros((1,3,2,2))
        with self.assertRaises(RuntimeError):
            objective_gradient(x,lambda v:v,lambda z:torch.sqrt(z),torch.ones_like(x))

    def test_official_pixel_adapter(self):
        source=Path('/data0/liyanlei/watermark_research/third_party/semantic-forgery/utils/imprint_utils.py')
        raw=source.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'1c95450d48462cac0b1a631e97f83f5abeafd73452de9e46919a403d0641830b')
        tree=ast.parse(raw);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pixel_to_latent')
        from torchvision.transforms.functional import to_tensor
        from PIL import Image
        import numpy as np
        scope=dict(torch=torch,to_tensor=to_tensor)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),scope)
        vae=types.SimpleNamespace(config=types.SimpleNamespace(scaling_factor=.18215),
            encode=lambda x:types.SimpleNamespace(latent_dist=types.SimpleNamespace(mean=.1*x)))
        pipe=types.SimpleNamespace(device='cpu',vae=vae)
        image=Image.fromarray(np.full((2,2,3),128,dtype=np.uint8));pixels=to_tensor(image)[None]
        from_image=scope['pixel_to_latent'](image,pipe)
        from_pixels=scope['pixel_to_latent'](2*pixels-1,pipe)
        self.assertTrue(torch.equal(from_image,from_pixels))
        _,g,_=objective_gradient(pixels,lambda x:scope['pixel_to_latent'](2*x-1,pipe),lambda z:z,torch.zeros_like(pixels))
        expected=4*(.1*.18215)**2*(2*pixels-1)/pixels.numel()
        self.assertTrue(torch.allclose(g,expected,rtol=1e-6,atol=1e-10))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert not torch.cuda.is_initialized()
    print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        gpu_used=False,models_loaded=False,new_model_experiments_run=0,scope='synthetic differentiable functions and official helper with stub VAE')))
    raise SystemExit(0 if result.wasSuccessful() else 1)
