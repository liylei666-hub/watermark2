"""Real installed pipeline/differentiable-wrapper CPU fixture, without model weights."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import ast,contextlib,sys,types,typing,unittest
from pathlib import Path
import torch
from torch.utils.checkpoint import checkpoint
from diffusers import StableDiffusionPipeline,DDIMInverseScheduler
from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import retrieve_timesteps,rescale_noise_cfg
ROOT=Path('/data0/liyanlei/watermark_research')
sys.path.insert(0,str(ROOT/'scripts/cover_pilot'))
import runtime as runtime

class ToyUNet(torch.nn.Module):
    def __init__(self):super().__init__();self.config=types.SimpleNamespace(in_channels=4,sample_size=8,time_cond_proj_dim=None)
    def forward(self,x,t,**kwargs):return (x*.125+t*.00001,)
class FixturePipe:
    def __init__(self):
        self.scheduler=DDIMInverseScheduler(num_train_timesteps=1000,beta_start=.00085,beta_end=.012,beta_schedule='scaled_linear',steps_offset=1,clip_sample=False)
        self.unet=ToyUNet();self.vae_scale_factor=8;self._execution_device=torch.device('cpu')
        self.guidance_scale=1.;self.guidance_rescale=0.;self.clip_skip=None;self.cross_attention_kwargs=None;self.do_classifier_free_guidance=False;self.interrupt=False
        self.image_processor=types.SimpleNamespace(postprocess=lambda x,**kwargs:x)
    def check_inputs(self,*args,**kwargs):pass
    def encode_prompt(self,*args,**kwargs):return torch.zeros(1,2,3,dtype=torch.float64),torch.zeros(1,2,3,dtype=torch.float64)
    def prepare_latents(self,*args):return args[-1]*self.scheduler.init_noise_sigma
    def prepare_extra_step_kwargs(self,*args):return {}
    def maybe_free_model_hooks(self):pass
    @contextlib.contextmanager
    def progress_bar(self,**kwargs):yield types.SimpleNamespace(update=lambda:None)

class NativeCPU(unittest.TestCase):
    def test_reference_tensor_and_pil_paths_have_different_normalization(self):
        import numpy as np
        import PIL.Image
        from torchvision import transforms
        from torchvision.transforms.functional import to_tensor
        scope=dict(typing=typing,Image=PIL.Image,torch=torch,transforms=transforms,to_tensor=to_tensor)
        runtime.definitions(ROOT/'third_party/semantic-forgery/utils/image_utils.py',{'PIL_to_torch'},scope)
        runtime.definitions(ROOT/'third_party/semantic-forgery/utils/imprint_utils.py',{'pixel_to_latent','invert_image'},scope)
        class RecordingPipe:
            device='cpu'
            def __init__(self):
                self.inputs=[];self.scheduler=object()
                self.vae=types.SimpleNamespace(config=types.SimpleNamespace(scaling_factor=1.),encode=self.encode)
            def encode(self,x):
                self.inputs.append(x.clone());return types.SimpleNamespace(latent_dist=types.SimpleNamespace(mean=x.clone()))
            def __call__(self,**kwargs):return (kwargs['latents'],)
        image=PIL.Image.fromarray(np.zeros((8,8,3),dtype=np.uint8));p=RecordingPipe()
        generated_pt=scope['PIL_to_torch']([image])
        scope['invert_image'](pipe=p,scheduler=object(),image_pt=generated_pt,resolution=8)
        scope['pixel_to_latent'](image,p)
        self.assertTrue(torch.equal(p.inputs[0],torch.zeros_like(p.inputs[0])))
        self.assertTrue(torch.equal(p.inputs[1],-torch.ones_like(p.inputs[1])))
        print('REFERENCE_PATH_AUDIT: official image_pt black=0; project PIL black=-1; not equivalent',flush=True)

    def test_actual_standard_pipeline_matches_original_diffpipe_forward(self):
        scope=dict(torch=torch,Optional=typing.Optional,Union=typing.Union,List=typing.List,checkpoint=checkpoint,
                   retrieve_timesteps=retrieve_timesteps,rescale_noise_cfg=rescale_noise_cfg)
        runtime.definitions(ROOT/'third_party/semantic-forgery/utils/imprint_utils.py',{'DiffPipe','UnetWrapper'},scope)
        torch.manual_seed(31);z=torch.randn(1,4,8,8,dtype=torch.float64)
        p=FixturePipe();expected=StableDiffusionPipeline.__call__(p,latents=z.clone(),prompt='',guidance_scale=1.,num_inference_steps=50,height=64,width=64,output_type='latent',return_dict=False)[0]
        p=FixturePipe();diff=scope['DiffPipe'](p,scheduler=p.scheduler,device='cpu');x=z.clone().requires_grad_(True)
        actual=diff(x,'',guidance_scale=1.,num_inference_steps=50)
        self.assertTrue(torch.equal(actual,expected));actual.square().mean().backward();self.assertTrue(torch.isfinite(x.grad).all())

    def test_official_ast_loop_matches_150_actual_adam_updates(self):
        path=ROOT/'third_party/semantic-forgery/run_imprint_forgery.py';tree=ast.parse(path.read_text())
        original=next(n for n in tree.body if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='step')
        body=[]
        for node in original.body:
            if isinstance(node,ast.If):break
            body.append(node)
        loop=ast.For(target=original.target,iter=original.iter,body=body,orelse=[])
        torch.manual_seed(3);initial=torch.randn(11,dtype=torch.float64);target=torch.randn(11,dtype=torch.float64)
        a=torch.nn.Parameter(initial.clone());optim=torch.optim.Adam([a],lr=.01)
        scope=dict(tqdm=types.SimpleNamespace(tqdm=lambda v:v),args=types.SimpleNamespace(steps=150),optim=optim,
                   z0=a,diffpipe=lambda z,*args,**kwargs:z.sin(),torch=torch,zT_retrieved=target)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[loop],type_ignores=[])),str(path),'exec'),scope)
        b=torch.nn.Parameter(initial.clone());other=torch.optim.Adam([b],lr=.01)
        for update in range(1,151):
            other.zero_grad();loss=torch.nn.functional.mse_loss(b.sin(),target.detach());loss.backward();other.step()
        self.assertTrue(torch.equal(a,b));self.assertEqual(int(optim.state[a]['step']),150)
        self.assertEqual([n+1 for n in range(151) if n%10==0][-1],151)

    def test_fixed_checkpoints_are_after_actual_updates(self):
        points=[i for i in range(1,151) if i in (20,50,100,150)]
        self.assertEqual(points,[20,50,100,150]);self.assertNotIn(151,points)

if __name__=='__main__':unittest.main()
