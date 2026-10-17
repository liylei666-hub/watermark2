"""Fixed final-output attacks; receives an image-only job and runtime source pins."""
import sys
import time
from pathlib import Path
import contract as c
import runtime as r


def imprint(job,path,output):
    import typing
    import numpy as np
    import torch
    import PIL.Image
    from torchvision.transforms.functional import to_tensor,to_pil_image
    from torch.utils.checkpoint import checkpoint
    from diffusers import StableDiffusionPipeline,DDIMScheduler,DDIMInverseScheduler
    from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import retrieve_timesteps,rescale_noise_cfg
    scope=dict(torch=torch,PIL=PIL,Optional=typing.Optional,Union=typing.Union,List=typing.List,
        checkpoint=checkpoint,to_tensor=to_tensor,to_pil_image=to_pil_image,retrieve_timesteps=retrieve_timesteps,rescale_noise_cfg=rescale_noise_cfg)
    r.definitions(r.UPSTREAM/'utils/imprint_utils.py',{'DiffPipe','UnetWrapper','latent_to_pil','pixel_to_latent'},scope)
    t=time.perf_counter();snapshot=job['proxy']['snapshot']
    scheduler=DDIMScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    inverse=DDIMInverseScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    pipe=StableDiffusionPipeline.from_pretrained(snapshot,scheduler=scheduler,safety_checker=None,local_files_only=True,torch_dtype=torch.float32).to('cuda:0')
    pipe.set_progress_bar_config(disable=True);pipe.text_encoder.requires_grad_(False);pipe.vae.requires_grad_(False)
    diff=scope['DiffPipe'](pipe,scheduler=inverse,device='cuda:0')
    torch.cuda.synchronize();load=time.perf_counter()-t
    with PIL.Image.open(path.parent/'reference.png') as im:reference=im.convert('RGB')
    with PIL.Image.open(path.parent/'cover.png') as im:cover=im.convert('RGB')
    torch.cuda.synchronize();t=time.perf_counter()
    with torch.no_grad():
        pipe.scheduler=inverse
        target=pipe(latents=scope['pixel_to_latent'](reference,pipe),num_inference_steps=50,prompt=[''],negative_prompt=[''],guidance_scale=1.,width=512,height=512,output_type='latent',return_dict=False)[0].detach()
        pipe.scheduler=scheduler
        initial=scope['pixel_to_latent'](cover,pipe).detach()
    torch.cuda.synchronize();setup=time.perf_counter()-t
    r.tensor(output/'reference_proxy_noise.npy',target)
    z=torch.nn.Parameter(initial.clone());optimizer=torch.optim.Adam([z],lr=job['parameters']['learning_rate'])
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();t=time.perf_counter()
    for step in range(job['parameters']['updates']):
        optimizer.zero_grad()
        loss=torch.nn.functional.mse_loss(diff(z,'',guidance_scale=1.,num_inference_steps=50),target)
        loss.backward();optimizer.step()
    torch.cuda.synchronize();optimize=time.perf_counter()-t;peak=torch.cuda.max_memory_allocated()
    r.tensor(output/'final_latent.npy',z)
    t=time.perf_counter()
    with torch.no_grad():image=scope['latent_to_pil'](z.detach(),pipe)[0]
    with (output/'candidate.png').open('xb') as f:image.save(f,format='PNG')
    torch.cuda.synchronize();export=time.perf_counter()-t
    return dict(model_load_seconds=load,reference_and_cover_preparation_seconds=setup,optimization_seconds=optimize,
        export_seconds=export,peak_allocated_bytes=peak,updates=job['parameters']['updates'])


def jain(job,path,output):
    import torch
    from PIL import Image
    from torchvision import transforms
    from diffusers import AutoencoderKL
    scope=dict(torch=torch,Variable=torch.autograd.Variable,device=torch.device('cuda:0'),Image=Image,transforms=transforms)
    base=r.ROOT/'audit_sources/jain_0443396/Gaussian-Shading'
    r.definitions(base/'my_utils.py',{'pgd_attack_lamda','save_img'},scope)
    r.definitions(base/'image_utils.py',{'transform_img'},scope)
    inputs={}
    for kind in ['reference','cover']:
        with Image.open(path.parent/(kind+'.png')) as im:inputs[kind]=scope['transform_img'](im.convert('RGB')).unsqueeze(0).to('cuda:0')
    t=time.perf_counter()
    vae=AutoencoderKL.from_pretrained(job['proxy']['snapshot'],subfolder='vae',local_files_only=True,use_safetensors=True,torch_dtype=torch.float32).to('cuda:0').eval()
    # Preserve the original parameter flags verified in stage13.
    if not all(p.requires_grad for p in vae.parameters()):raise RuntimeError('Unexpected VAE parameter flags')
    torch.cuda.synchronize();load=time.perf_counter()-t
    warm=inputs['cover'].detach().clone().requires_grad_(True)
    warm_loss=vae.encode(warm).latent_dist.mode().square().mean();torch.autograd.grad(warm_loss,warm)
    del warm,warm_loss
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();t=time.perf_counter();p=job['parameters']
    x,delta=scope['pgd_attack_lamda'](inputs['cover'].clone(),inputs['reference'].clone(),vae,lamda=p['lamda'],alpha=p['alpha'],iters=p['updates'],delta=0)
    torch.cuda.synchronize();core=time.perf_counter()-t;peak=torch.cuda.max_memory_allocated()
    if any(p.grad is not None for p in vae.parameters()):raise RuntimeError('Unexpected parameter gradients')
    r.tensor(output/'final_float.npy',x);r.tensor(output/'final_delta.npy',delta)
    t=time.perf_counter();scope['save_img'](x,output/'candidate.png');torch.cuda.synchronize();export=time.perf_counter()-t
    return dict(model_load_seconds=load,reference_encoding_and_optimization_seconds=core,export_seconds=export,
        peak_allocated_bytes=peak,updates=p['updates'],parameters_require_grad=True)


def main(runtime,job_path,output):
    r.check_device(runtime,output);job=c.validate_job(job_path);job_hash=c.sha(job_path)
    r.deterministic(job['seed'])
    timing={'imprint':imprint,'jain':jain}[job['method']](job,job_path,output)
    if c.sha(job_path)!=job_hash:raise RuntimeError('Job changed during attack')
    frozen=c.freeze_candidate(output,job_path)
    c.write(output/'summary.json',dict(completed=True,task_id=job['task_id'],method=job['method'],timing=timing,
        candidate=frozen,target_scores_used=False,target_model_loaded=False,full_defense_acceptance=None))
    print('COMPLETED_COVER_ATTACK',flush=True)


if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
