"""CPU-only contract checks on pinned Jain functions with synthetic tensors.

No pretrained model, pipeline, detector or upstream module entry is imported.
"""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('Set CUDA_VISIBLE_DEVICES="" for CPU contract checks')
import argparse
import ast
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HASHES = {
    'Gaussian-Shading/my_utils.py': '454c9d02f66f67bacf938381bfe69122f6b87489a74bd59f0520bbd94c06127d',
    'Gaussian-Shading/image_utils.py': 'aa0dd86b4543bde39983e5b7ec8fd487fba476d7a435f83308891e187ee93fbb',
}
SOURCE_ROOT = None


def definitions(relative, names):
    path = SOURCE_ROOT / relative
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != HASHES[relative]:
        raise ValueError('Pinned source hash mismatch: ' + relative)
    tree = ast.parse(data)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != set(names) or any(n.decorator_list for n in nodes):
        raise ValueError('Unexpected source boundary')
    return compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec')


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        import numpy as np
        from PIL import Image
        from torchvision import transforms
        cls.torch, cls.np, cls.Image = torch, np, Image
        cls.scope = dict(torch=torch, Variable=torch.autograd.Variable, device=torch.device('cpu'),
            Image=Image, transforms=transforms)
        exec(definitions('Gaussian-Shading/my_utils.py', ['pgd_attack_lamda', 'save_img']), cls.scope)
        # This later wildcard import determines the entry's actual preprocessing function.
        exec(definitions('Gaussian-Shading/image_utils.py', ['transform_img']), cls.scope)

    def tiny_vae(self, frozen=False):
        torch = self.torch
        class SyntheticEncoder(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.gain = torch.nn.Parameter(torch.tensor(.5, dtype=torch.float64))
                self.config = SimpleNamespace(scaling_factor=.25)
            def encode(self, x):
                value = x*self.gain
                return SimpleNamespace(latent_dist=SimpleNamespace(mode=lambda: value))
        vae = SyntheticEncoder()
        if frozen:
            vae.requires_grad_(False)
        return vae

    def inputs(self):
        torch = self.torch
        c = torch.linspace(-.9,.9,12,dtype=torch.float64).reshape(1,3,2,2)
        return c, c.flip(-1)*-.7

    def test_exact_source_against_closed_form_three_updates(self):
        torch=self.torch; cover, reference=self.inputs(); c0=cover.clone(); r0=reference.clone()
        vae=self.tiny_vae(); alpha=.05; lamda=2.; expected=cover.clone()
        # Independent gradient of mean((gain*x/s-gain*r/s)^2)+lambda*mean((x-c)^2).
        for _ in range(3):
            grad=2*(.5/.25)**2*(expected-reference)/expected.numel()+2*lamda*(expected-cover)/expected.numel()
            expected=(expected-alpha*grad).clamp(-1,1)
        actual, delta=self.scope['pgd_attack_lamda'](cover,reference,vae,lamda=lamda,alpha=alpha,iters=3,delta=0)
        self.assertTrue(torch.allclose(actual,expected,rtol=1e-12,atol=1e-12))
        self.assertTrue(torch.equal(delta,cover-actual))
        self.assertTrue(torch.equal(cover,c0) and torch.equal(reference,r0))

    def test_parameter_freezing_preserves_synthetic_updates(self):
        torch=self.torch;cover,reference=self.inputs()
        mutable=self.tiny_vae();frozen=self.tiny_vae(True)
        kwargs=dict(lamda=2.,alpha=.05,iters=3,delta=0)
        a,_=self.scope['pgd_attack_lamda'](cover.clone(),reference.clone(),mutable,**kwargs)
        b,_=self.scope['pgd_attack_lamda'](cover.clone(),reference.clone(),frozen,**kwargs)
        self.assertTrue(torch.equal(a,b))
        # Assignment to vae.requires_grad does not freeze nn.Module parameters.
        self.assertTrue(mutable.gain.requires_grad)
        self.assertFalse(frozen.gain.requires_grad)
        self.assertIsNone(mutable.gain.grad)

    def test_box_clamp_is_not_cover_radius_projection(self):
        torch=self.torch
        c=torch.zeros(1,3,2,2,dtype=torch.float64);r=torch.ones_like(c)
        actual,_=self.scope['pgd_attack_lamda'](c,r,self.tiny_vae(),lamda=0.,alpha=10.,iters=1)
        self.assertTrue(torch.equal(actual,torch.ones_like(c)))

    def test_actual_serialization_and_float_readback_are_distinct(self):
        torch=self.torch;np=self.np
        # Non-square synthetic tensor avoids squeeze removing a spatial dimension.
        values=torch.tensor([-1.,-.8,0.,.998,1.],dtype=torch.float32)
        x=values.reshape(1,1,1,5).repeat(1,3,2,1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'probe.png';self.scope['save_img'](x,path)
            with self.Image.open(path) as image:
                pixels=np.array(image);self.assertEqual(image.mode,'RGB')
            self.assertEqual(pixels[0,:,0].tolist(),[0,25,127,254,255])
            readback=torch.from_numpy(pixels.copy()).permute(2,0,1)[None].float()/255*2-1
            self.assertFalse(torch.equal(x,readback))
            self.assertLessEqual(float((x-readback).abs().max()),2/255+1e-6)

    def test_effective_preprocessor_preserves_square_input_shape(self):
        np=self.np
        image=self.Image.fromarray(np.full((4,4,3),128,dtype=np.uint8))
        x=self.scope['transform_img'](image,target_size=4)
        self.assertEqual(tuple(x.shape),(3,4,4))
        expected=np.float32(128)/np.float32(255)*np.float32(2)-np.float32(1)
        self.assertEqual(x.dtype,self.torch.float32)
        self.assertTrue(self.torch.equal(x,self.torch.full_like(x,float(expected))))
        print('PREPROCESS_FP32',repr(float(x[0,0,0])), 'REAL_ARITHMETIC',repr(2*128/255-1))

    def test_no_pipeline_library_imported(self):
        import sys
        self.assertNotIn('diffusers',sys.modules)
        self.assertNotIn('open_clip',sys.modules)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',type=Path,required=True)
    args=parser.parse_args();SOURCE_ROOT=args.source_root
    unittest.main(argv=['test_cover_baseline_adapter'],verbosity=2)
