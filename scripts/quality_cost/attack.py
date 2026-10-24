"""Two image-space inversion controls under the same final PNG and wall-time limits."""
import sys,time
from pathlib import Path
from common import c,r,preimport,validate_job,BASE
from quality import project_tensor,quantize_feasible,enough_time


def split_gradient(x, mapping, inverse, target):
    import torch
    with torch.no_grad():encoded=mapping(x)
    leaf=encoded.detach().requires_grad_(True)
    loss=torch.nn.functional.mse_loss(inverse(leaf),target)
    loss.backward()
    if leaf.grad is None or not torch.isfinite(leaf.grad).all():raise RuntimeError('Invalid inverse gradient')
    value=float(loss.detach());gradient=leaf.grad.detach().clone()
    del loss,leaf,encoded
    mapping(x).backward(gradient)
    if x.grad is None or not torch.isfinite(x.grad).all():raise RuntimeError('Invalid image gradient')
    return value


def load_model(proxy):
    import typing,torch,PIL.Image
    from torchvision.transforms.functional import to_tensor,to_pil_image
    from torch.utils.checkpoint import checkpoint
    from diffusers import StableDiffusionPipeline,DDIMScheduler,DDIMInverseScheduler
    from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import retrieve_timesteps,rescale_noise_cfg
    scope=dict(torch=torch,PIL=PIL,Optional=typing.Optional,Union=typing.Union,List=typing.List,
               checkpoint=checkpoint,to_tensor=to_tensor,to_pil_image=to_pil_image,
               retrieve_timesteps=retrieve_timesteps,rescale_noise_cfg=rescale_noise_cfg)
    r.definitions(r.UPSTREAM/'utils/imprint_utils.py',{'DiffPipe','UnetWrapper','pixel_to_latent'},scope)
    snapshot=proxy['snapshot'];start=time.perf_counter()
    scheduler=DDIMScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    inverse=DDIMInverseScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    pipe=StableDiffusionPipeline.from_pretrained(snapshot,scheduler=scheduler,safety_checker=None,
        local_files_only=True,torch_dtype=torch.float32).to('cuda:0')
    pipe.set_progress_bar_config(disable=True);pipe.text_encoder.requires_grad_(False);pipe.vae.requires_grad_(False)
    diff=scope['DiffPipe'](pipe,scheduler=inverse,device='cuda:0')
    torch.cuda.synchronize()
    return pipe,diff,inverse,scheduler,scope,time.perf_counter()-start


def optimize(model, reference, cover, steps, policy, output, maximum_updates=None):
    import numpy as np,torch
    from PIL import Image
    pipe,diff,inverse,scheduler,scope,loading=model
    torch.cuda.synchronize();core_start=time.perf_counter()
    ref=Image.fromarray(reference)
    cover_tensor=torch.from_numpy(cover.copy()).permute(2,0,1).contiguous().float().div(255).unsqueeze(0).to('cuda:0')
    def mapping(value):return scope['pixel_to_latent'](value*2-1,pipe)
    with torch.no_grad():
        # Same FP32 normalization as upstream PIL path, checked before optimization.
        reference_latent=scope['pixel_to_latent'](ref,pipe)
        pil_cover_latent=scope['pixel_to_latent'](Image.fromarray(cover),pipe)
        tensor_cover_latent=mapping(cover_tensor)
        if not torch.equal(pil_cover_latent,tensor_cover_latent):raise ValueError('PIL/tensor encode mismatch')
        pipe.scheduler=inverse
        target=pipe(latents=reference_latent,num_inference_steps=steps,prompt=[''],negative_prompt=[''],guidance_scale=1.,
            width=512,height=512,output_type='latent',return_dict=False)[0].detach()
        pipe.scheduler=scheduler
    torch.cuda.synchronize();preparation=time.perf_counter()-core_start
    x=torch.nn.Parameter(cover_tensor.clone())
    optimizer=torch.optim.Adam([x],lr=policy['learning_rate'],betas=(.9,.999),eps=1e-8)
    history=[];durations=[];optimization_start=time.perf_counter()
    limit=maximum_updates if maximum_updates is not None else policy['max_updates']
    for iteration in range(limit):
        if not enough_time(time.perf_counter()-core_start,durations,steps,policy['core_budget_seconds'],policy['finalization_reserve_seconds']):break
        torch.cuda.synchronize();update_start=time.perf_counter();optimizer.zero_grad()
        loss=split_gradient(x,mapping,lambda z:diff(z,'',guidance_scale=1.,num_inference_steps=steps),target)
        grad_norm=float(x.grad.norm())
        if not grad_norm>0:raise RuntimeError('Zero image gradient')
        optimizer.step();project_tensor(x,cover_tensor,policy['mse_limit'],policy['linf_levels'])
        if not torch.isfinite(x).all():raise RuntimeError('Nonfinite pixels')
        torch.cuda.synchronize();duration=time.perf_counter()-update_start;durations.append(duration)
        history.append(dict(update=iteration+1,loss_before_update=loss,gradient_norm=grad_norm,seconds=duration,
                            continuous_mse=float((x-cover_tensor).square().mean())))
        print('COMPLETED_UPDATE',iteration+1,steps,flush=True)
    torch.cuda.synchronize();optimization=time.perf_counter()-optimization_start
    if not history:raise RuntimeError('No feasible update within budget')
    pixels=x.detach()[0].permute(1,2,0).cpu().numpy()
    result,quality=quantize_feasible(pixels,cover,policy['mse_limit'],policy['linf_levels'])
    with (output/'candidate.png').open('xb') as stream:Image.fromarray(result).save(stream,format='PNG')
    with Image.open(output/'candidate.png') as im:
        if not np.array_equal(np.asarray(im),result):raise RuntimeError('PNG roundtrip differs')
    torch.cuda.synchronize();core=time.perf_counter()-core_start
    # Analysis tensors/logging occur after the measured deliverable is finalized.
    r.tensor(output/'reference_proxy_noise.npy',target)
    c.write(output/'optimization.json',dict(updates=history,target_feedback=False,parameterization='RGB01 pixels',
        continuous_objective=True,quantizer_differentiated=False,endpoint_selection='last feasible update'))
    return dict(model_load_seconds=loading,reference_and_cover_preparation_seconds=preparation,
        optimization_seconds=optimization,finalization_seconds=core-preparation-optimization,
        core_seconds=core,updates=len(history),quality=quality,update_seconds=durations,
        finalization_reserve_exceeded=core-preparation-optimization>policy['finalization_reserve_seconds'])


def main(runtime,job_path,output):
    import numpy as np
    from PIL import Image
    output=Path(output);path=Path(job_path);cfg=preimport(runtime,output)
    if cfg['role']!='attacker':raise ValueError('Wrong role')
    job=validate_job(path,cfg);digest=c.sha(path);r.deterministic(job['seed'])
    with Image.open(path.parent/'reference.png') as im:reference=np.asarray(im.convert('RGB')).copy()
    with Image.open(path.parent/'cover.png') as im:cover=np.asarray(im.convert('RGB')).copy()
    timing=optimize(load_model(job['proxy']),reference,cover,job['inversion_steps'],job['policy'],output)
    if c.sha(path)!=digest:raise ValueError('Job changed')
    validate_job(path,cfg)
    frozen=dict(task_id=job['task_id'],method=job['method'],job_sha256=digest,image=c.png_record(output/'candidate.png'))
    c.write(output/'candidate_frozen.json',frozen)
    c.write(output/'summary.json',dict(completed=True,timing=timing,core_seconds=timing['core_seconds'],
        candidate=frozen,target_scores_used=False,target_model_loaded=False,quality=timing['quality']))
    print('COMPLETED_QUALITY_ATTACK',flush=True)


if __name__=='__main__':main(*sys.argv[1:])
