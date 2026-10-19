"""Image-only coarse-to-fine inversion allocation, with unchanged native comparator."""
import sys,time
from pathlib import Path
from common import c,r,module,preimport,validate_job,BASE


def staged(job,path,output):
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
    start=time.perf_counter();snapshot=job['proxy']['snapshot']
    scheduler=DDIMScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    inverse=DDIMInverseScheduler.from_pretrained(snapshot,subfolder='scheduler',local_files_only=True)
    pipe=StableDiffusionPipeline.from_pretrained(snapshot,scheduler=scheduler,safety_checker=None,
        local_files_only=True,torch_dtype=torch.float32).to('cuda:0')
    pipe.set_progress_bar_config(disable=True);pipe.text_encoder.requires_grad_(False);pipe.vae.requires_grad_(False)
    diff=scope['DiffPipe'](pipe,scheduler=inverse,device='cuda:0')
    torch.cuda.synchronize();loading=time.perf_counter()-start
    with PIL.Image.open(path.parent/'reference.png') as im:reference=im.convert('RGB')
    with PIL.Image.open(path.parent/'cover.png') as im:cover=im.convert('RGB')
    torch.cuda.synchronize();start=time.perf_counter();targets={}
    with torch.no_grad():
        ref_latent=scope['pixel_to_latent'](reference,pipe)
        pipe.scheduler=inverse
        for phase in job['schedule']:
            steps=phase['inversion_steps']
            targets[steps]=pipe(latents=ref_latent.clone(),num_inference_steps=steps,prompt=[''],negative_prompt=[''],
                guidance_scale=1.,width=512,height=512,output_type='latent',return_dict=False)[0].detach()
        pipe.scheduler=scheduler
        initial=scope['pixel_to_latent'](cover,pipe).detach()
    torch.cuda.synchronize();preparation=time.perf_counter()-start
    z=torch.nn.Parameter(initial.clone());optimizer=torch.optim.Adam([z],lr=job['learning_rate']);history=[]
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
    for phase_index,phase in enumerate(job['schedule']):
        steps=phase['inversion_steps']
        for update in range(phase['updates']):
            optimizer.zero_grad()
            loss=torch.nn.functional.mse_loss(diff(z,'',guidance_scale=1.,num_inference_steps=steps),targets[steps])
            loss.backward();optimizer.step()
            if not torch.isfinite(z).all() or not torch.isfinite(loss):raise RuntimeError('Nonfinite optimization')
            history.append(dict(phase=phase_index,inversion_steps=steps,update_in_phase=update+1,loss_before_update=float(loss.detach())))
            print('COMPLETED_UPDATE',len(history),steps,flush=True)
    torch.cuda.synchronize();optimization=time.perf_counter()-start;peak=torch.cuda.max_memory_allocated()
    r.tensor(output/'final_latent.npy',z)
    for steps,value in targets.items():r.tensor(output/f'reference_proxy_noise_{steps}.npy',value)
    c.write(output/'optimization.json',dict(schedule=job['schedule'],updates=history,adam_state_preserved_across_switch=True,target_feedback=False))
    start=time.perf_counter()
    with torch.no_grad():image=scope['latent_to_pil'](z.detach(),pipe)[0]
    with (output/'candidate.png').open('xb') as stream:image.save(stream,format='PNG')
    torch.cuda.synchronize();export=time.perf_counter()-start
    return dict(model_load_seconds=loading,reference_and_cover_preparation_seconds=preparation,
        optimization_seconds=optimization,export_seconds=export,peak_allocated_bytes=peak,updates=len(history))


def main(runtime,job_path,output):
    output=Path(output);path=Path(job_path);cfg=preimport(runtime,output)
    if cfg['role']!='attacker':raise ValueError('Expected attack runtime')
    job=validate_job(path,cfg);digest=c.sha(path);r.deterministic(job['seed'])
    if job['method']=='native50':
        baseline=module('original_native_core',BASE/'cover_pilot/attack.py')
        native=dict(job,parameters=dict(updates=10,learning_rate=.01))
        timing=baseline.imprint(native,path,output)
    else:timing=staged(job,path,output)
    if c.sha(path)!=digest:raise ValueError('Job changed during execution')
    validate_job(path,cfg)
    frozen=dict(task_id=job['task_id'],method=job['method'],job_sha256=digest,image=c.png_record(output/'candidate.png'))
    c.write(output/'candidate_frozen.json',frozen)
    c.write(output/'summary.json',dict(completed=True,timing=timing,candidate=frozen,
        core_seconds=timing['reference_and_cover_preparation_seconds']+timing['optimization_seconds'],
        target_scores_used=False,target_model_loaded=False,schedule=job['schedule'],
        optimization_forward_unet_calls=sum(p['updates']*p['inversion_steps'] for p in job['schedule'])))
    print('COMPLETED_STAGED_ATTACK',flush=True)


if __name__=='__main__':main(*sys.argv[1:])
