"""One fixed set of proxy-only pixel direction probes per image-only job."""
import sys
import time
from pathlib import Path
import interface as i
import delivery as d
from common import r
from gradient_core import objective_gradient

def main(runtime,jobpath,output):
    cfg=r.check_device(runtime,output);job=i.validate_job(jobpath);initial_hash=i.sha(jobpath)
    import typing
    import numpy as np
    import torch
    import PIL.Image
    from torchvision.transforms.functional import to_tensor,to_pil_image
    from torch.utils.checkpoint import checkpoint
    from diffusers import StableDiffusionPipeline,DDIMScheduler,DDIMInverseScheduler
    from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import retrieve_timesteps,rescale_noise_cfg
    r.deterministic(job['seed'])
    scope=dict(torch=torch,PIL=PIL,Optional=typing.Optional,Union=typing.Union,List=typing.List,
        checkpoint=checkpoint,to_tensor=to_tensor,to_pil_image=to_pil_image,
        retrieve_timesteps=retrieve_timesteps,rescale_noise_cfg=rescale_noise_cfg)
    r.definitions(r.UPSTREAM/'utils/imprint_utils.py',{'DiffPipe','UnetWrapper','pixel_to_latent'},scope)
    start=time.perf_counter();snapshot=job['proxy']['snapshot']
    scheduler=DDIMScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    inverse=DDIMInverseScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    pipe=StableDiffusionPipeline.from_pretrained(snapshot,scheduler=scheduler,safety_checker=None,
        local_files_only=True,torch_dtype=torch.float32).to('cuda:0')
    pipe.set_progress_bar_config(disable=True);pipe.vae.requires_grad_(False);pipe.text_encoder.requires_grad_(False)
    diff=scope['DiffPipe'](pipe,scheduler=inverse,device='cuda:0')
    torch.cuda.synchronize();load_seconds=time.perf_counter()-start
    images={}
    for kind in ['reference','cover']:
        with PIL.Image.open(jobpath.parent/(kind+'.png')) as im:images[kind]=im.copy()
    encode=lambda x:scope['pixel_to_latent'](2*x-1,pipe)
    def invert(z):
        old=pipe.scheduler;pipe.scheduler=inverse
        try:
            return pipe(latents=z,num_inference_steps=50,prompt=[''],negative_prompt=[''],
                guidance_scale=1.,width=512,height=512,output_type='latent',return_dict=False)[0]
        finally:pipe.scheduler=old
    pixels={k:to_tensor(v)[None].to('cuda:0') for k,v in images.items()}
    with torch.no_grad():
        zr=encode(pixels['reference']);nr=invert(zr)
        zc=encode(pixels['cover']);nc=invert(zc)
    r.tensor(output/'reference_proxy_z.npy',zr);r.tensor(output/'reference_proxy_inverse.npy',nr)
    gradients={};losses={};controls={};timings={}
    for name,transform,reference,control in [('vae',lambda z:z,zr,zc),
        ('inverse',lambda z:diff(z,'',guidance_scale=1.,num_inference_steps=50),nr,nc)]:
        torch.cuda.synchronize();start=time.perf_counter()
        loss,gradient,value=objective_gradient(pixels['cover'],encode,transform,reference)
        torch.cuda.synchronize();timings[name]=time.perf_counter()-start
        equivalent=torch.allclose(value,control,atol=cfg['forward_atol'],rtol=cfg['forward_rtol'])
        controls[name]=dict(allclose=equivalent,max_abs=float((value-control).abs().max().cpu()))
        i.write(output/(name+'_forward_control.json'),controls[name])
        if not equivalent:raise RuntimeError('Model forward equivalence gate failed')
        gradient=gradient[0].permute(1,2,0).contiguous()
        r.tensor(output/(name+'_pixel_gradient.npy'),gradient)
        gradients[name]=gradient.cpu().numpy();losses[name]=loss
    cover=np.array(images['cover'])
    candidates,support,distortion=d.build(cover,gradients['vae'],gradients['inverse'],job['seed'])
    d.export(output/'probes',cover,candidates,support,distortion)
    measured={}
    with torch.no_grad():
        for name,array in [('cover',cover),*candidates.items()]:
            tensor=to_tensor(PIL.Image.fromarray(array))[None].to('cuda:0')
            z=encode(tensor);n=invert(z)
            r.tensor(output/(name+'_proxy_z.npy'),z);r.tensor(output/(name+'_proxy_inverse.npy'),n)
            measured[name]=dict(vae=float(torch.nn.functional.mse_loss(z,zr).cpu()),
                inverse=float(torch.nn.functional.mse_loss(n,nr).cpu()))
    finite_checks={}
    for name in ['vae','inverse']:
        delta=(candidates[name+'_ascent'].astype(np.float64)-cover.astype(np.float64))/255
        finite_checks[name]=d.derivative_check(gradients[name],delta,
            measured[name+'_descent'][name],measured[name+'_ascent'][name])
    if i.sha(jobpath)!=initial_hash:raise RuntimeError('Job changed during execution')
    i.validate_job(jobpath)
    i.write(output/'summary.json',dict(completed=True,task_id=job['task_id'],model_loading_seconds=load_seconds,
        gradient_seconds=timings,forward_controls=controls,initial_gradient_losses=losses,
        proxy_losses=measured,finite_difference_checks=finite_checks,distortion=distortion,
        target_model_loaded=False,target_scores_used=False,optimization_updates=0,new_candidates=5,
        vae_scaling_factor=pipe.vae.config.scaling_factor,model_parameters_frozen=True))
    print('COMPLETED_DIRECTION_ATTACK',flush=True)

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
