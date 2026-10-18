"""Fixed-budget final-output comparison; the attack receives PNGs and proxy settings only."""
import sys,time
from pathlib import Path
from common import c,r,module,validate_job

def split_gradient(z,mapping,inverse,target):
    import torch
    # Recompute the deterministic map after inverse backward to avoid holding both graphs.
    with torch.no_grad():encoded=mapping(z)
    leaf=encoded.detach().requires_grad_(True)
    loss=torch.nn.functional.mse_loss(inverse(leaf),target)
    loss.backward()
    if leaf.grad is None or not torch.isfinite(leaf.grad).all():raise RuntimeError('Invalid inverse gradient')
    value=float(loss.detach().cpu());downstream=leaf.grad.detach().clone()
    del loss,leaf,encoded
    mapped=mapping(z);mapped.backward(downstream)
    if z.grad is None or not torch.isfinite(z.grad).all():raise RuntimeError('Invalid composed gradient')
    return value

def delivery_attack(job,path,output):
    import typing,numpy as np,torch,PIL.Image
    from torchvision.transforms.functional import to_tensor,to_pil_image
    from torch.utils.checkpoint import checkpoint
    from diffusers import StableDiffusionPipeline,DDIMScheduler,DDIMInverseScheduler
    from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import retrieve_timesteps,rescale_noise_cfg
    scope=dict(torch=torch,PIL=PIL,Optional=typing.Optional,Union=typing.Union,List=typing.List,checkpoint=checkpoint,
               to_tensor=to_tensor,to_pil_image=to_pil_image,retrieve_timesteps=retrieve_timesteps,rescale_noise_cfg=rescale_noise_cfg)
    r.definitions(r.UPSTREAM/'utils/imprint_utils.py',{'DiffPipe','UnetWrapper','latent_to_pil','pixel_to_latent'},scope)
    start=time.perf_counter();snapshot=job['proxy']['snapshot']
    scheduler=DDIMScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    inverse=DDIMInverseScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    pipe=StableDiffusionPipeline.from_pretrained(snapshot,scheduler=scheduler,safety_checker=None,local_files_only=True,torch_dtype=torch.float32).to('cuda:0')
    pipe.set_progress_bar_config(disable=True);pipe.text_encoder.requires_grad_(False);pipe.vae.requires_grad_(False)
    diff=scope['DiffPipe'](pipe,scheduler=inverse,device='cuda:0')
    torch.cuda.synchronize();loading=time.perf_counter()-start
    with PIL.Image.open(path.parent/'reference.png') as im:reference=im.convert('RGB')
    with PIL.Image.open(path.parent/'cover.png') as im:cover=im.convert('RGB')
    start=time.perf_counter()
    with torch.no_grad():
        pipe.scheduler=inverse
        target=pipe(latents=scope['pixel_to_latent'](reference,pipe),num_inference_steps=50,prompt=[''],negative_prompt=[''],guidance_scale=1.,width=512,height=512,output_type='latent',return_dict=False)[0].detach()
        pipe.scheduler=scheduler;initial=scope['pixel_to_latent'](cover,pipe).detach()
    torch.cuda.synchronize();setup=time.perf_counter()-start
    r.tensor(output/'reference_proxy_noise.npy',target)
    def mapping(value):
        raw=pipe.vae.decode(value/pipe.vae.config.scaling_factor,return_dict=False)[0]
        return scope['pixel_to_latent'](2*(raw*.5+.5).clamp(0,1)-1,pipe)
    inverse_fn=lambda value:diff(value,'',guidance_scale=1.,num_inference_steps=50)
    z=torch.nn.Parameter(initial.clone());optimizer=torch.optim.Adam([z],lr=job['parameters']['learning_rate']);losses=[]
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
    for step in range(job['parameters']['updates']):
        optimizer.zero_grad();losses.append(split_gradient(z,mapping,inverse_fn,target));optimizer.step()
        if not torch.isfinite(z).all():raise RuntimeError('Nonfinite updated latent')
        print('COMPLETED_UPDATE',step+1,flush=True)
    torch.cuda.synchronize();optimization=time.perf_counter()-start;peak=torch.cuda.max_memory_allocated()
    r.tensor(output/'final_latent.npy',z);c.write(output/'optimization.json',dict(loss_before_updates=losses,objective=job['parameters']['objective'],target_feedback=False))
    start=time.perf_counter()
    with torch.no_grad():image=scope['latent_to_pil'](z.detach(),pipe)[0]
    with (output/'candidate.png').open('xb') as f:image.save(f,format='PNG')
    with PIL.Image.open(output/'candidate.png') as im:
        if not np.array_equal(np.asarray(im),np.asarray(image)):raise RuntimeError('PNG pixels changed')
    torch.cuda.synchronize();export=time.perf_counter()-start
    return dict(model_load_seconds=loading,reference_and_cover_preparation_seconds=setup,optimization_seconds=optimization,
                export_seconds=export,peak_allocated_bytes=peak,updates=job['parameters']['updates'])

def main(runtime,job_path,output):
    job_path=Path(job_path);output=Path(output);cfg=r.check_device(Path(runtime),output)
    if cfg['role']!='attacker':raise ValueError('Wrong role')
    job=validate_job(job_path);digest=c.sha(job_path);r.deterministic(job['seed'])
    if job['method']=='delivery':timing=delivery_attack(job,job_path,output)
    else:
        baseline=module('official_core_adapter',Path(__file__).resolve().parents[1]/'cover_pilot/attack.py')
        timing=getattr(baseline,job['method'])(job,job_path,output)
    if c.sha(job_path)!=digest:raise ValueError('Job changed during attack')
    validate_job(job_path)
    frozen=dict(task_id=job['task_id'],method=job['method'],job_sha256=digest,image=c.png_record(output/'candidate.png'))
    c.write(output/'candidate_frozen.json',frozen)
    c.write(output/'summary.json',dict(completed=True,task_id=job['task_id'],method=job['method'],timing=timing,
             candidate=frozen,target_scores_used=False,target_model_loaded=False,full_defense_acceptance=None))
    print('COMPLETED_COVER_ATTACK',flush=True)

if __name__=='__main__':main(*sys.argv[1:])
