"""CPU check of official call-path equivalence with a model-free encoder stub."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '': raise SystemExit('CPU-only check')
import ast
import json
import types
import typing
from pathlib import Path
import torch
import numpy as np
import PIL.Image
from torchvision import transforms
from common import REMOTE, validate


def run():
    root=Path(REMOTE);up=root/'third_party/semantic-forgery'
    scope=dict(torch=torch,typing=typing,PIL=PIL,Image=PIL.Image,transforms=transforms,DTYPE=torch.float32,
               torch_to_PIL=lambda value:None)
    image_ast=ast.parse((up/'utils/image_utils.py').read_bytes())
    fn=[n for n in image_ast.body if isinstance(n,ast.FunctionDef) and n.name=='PIL_to_torch']
    assert len(fn)==1
    exec(compile(ast.Module(body=fn,type_ignores=[]),'official_image_helper','exec'),scope)
    tree=ast.parse((up/'utils/pipe/pipe_provider.py').read_bytes())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PipeProvider')
    names={'vae_encode','imgs_to_latents','PIL_to_torch','get_dtype','__load_pipe','allow_device','invert_images'}
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(methods)==len(names)
    minimal=ast.ClassDef(name='PipeProvider',bases=[],keywords=[],body=methods,decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[minimal],type_ignores=[]))
    exec(compile(module,'official_encoding_methods','exec'),scope)

    class StubVAE:
        config=types.SimpleNamespace(scaling_factor=.125)
        def encode(self,x):
            self.received=x.clone()
            return types.SimpleNamespace(latent_dist=types.SimpleNamespace(mean=x))

    class StubPipe:
        vae=StubVAE()
        def to(self,device): return self

    provider=scope['PipeProvider']();provider.pipe=StubPipe();provider.device='cpu'
    cfg=json.loads((root/'protocols/19_target_encoding.json').read_text())
    paths=validate(cfg,root);rows=[]
    for key,p in paths.items():
        with PIL.Image.open(p) as image:
            direct=provider.imgs_to_latents(image)
            expected=torch.from_numpy(np.asarray(image).copy()).permute(2,0,1).float()[None]/255
            expected=2*expected-1
            assert torch.equal(provider.pipe.vae.received,expected)
            inverse_entry=provider.invert_images(image,skip_inversion=True)['z0_torch']
            assert torch.equal(direct,inverse_entry)
            assert torch.equal(direct,expected*.125)
            rows.append(dict(input=key,preprocessing_exact=True,entry_paths_equal=True))
    return dict(status='passed',rows=rows,images_checked=12,gpu_used=False,models_loaded=False,
                scope='Official source methods with identity posterior stub; numerical target VAE not executed')


if __name__=='__main__':print(json.dumps(run()))
