"""Evaluator-owned image preparation with original sampling noise and RNG retention."""
import sys
import time
from pathlib import Path
import contract as c
import runtime as r


def main(runtime,protocol,role,output):
    r.check_device(runtime,output)
    cfg=c.read(protocol)
    if c.sha(protocol)!=protocol.with_suffix('.sha256').read_text().strip():raise ValueError('Protocol changed')
    if role not in ['reference','cover']:raise ValueError('Unknown preparation role')
    import random
    import numpy as np
    import torch
    r.deterministic(0)
    start=time.perf_counter();provider=r.official_provider(cfg['target'] if role=='reference' else cfg['proxy'])
    torch.cuda.synchronize();load=time.perf_counter()-start
    from utils.wm.gs_provider import GsProvider
    from utils.utils import set_random_seed
    wm=GsProvider(latent_shape=(1,4,64,64),device='cuda:0',**cfg['gs_parameters']) if role=='reference' else None
    rows=[]
    for task in cfg['tasks']:
        folder=output/str(task['task_id']);folder.mkdir()
        seed=task[role+'_seed'];set_random_seed(seed)
        # Store CPU-safe RNG arrays plus Python/NumPy metadata before noise sampling.
        for phase in ['before_noise','before_generation','after_generation']:
            if phase=='before_generation':
                z=wm.get_wm_latents()['zT_torch'] if wm is not None else torch.randn((1,4,64,64),device='cuda:0',dtype=torch.float32)
                original=z.detach().clone();noise_record=r.tensor(folder/'original_noise.npy',original)
            if phase=='after_generation':
                torch.cuda.synchronize();start=time.perf_counter()
                with torch.no_grad():
                    generated=provider.generate(prompts=[task[role+'_prompt']],num_inference_steps=50,guidance_scale=7.5,latents=z,return_latents=False)
                torch.cuda.synchronize();seconds=time.perf_counter()-start
                if not torch.equal(z,original):raise RuntimeError('Generation mutated supplied noise')
                with (folder/(role+'.png')).open('xb') as f:generated['images_PIL'][0].save(f,format='PNG')
            state=np.random.get_state()
            with (folder/('rng_'+phase+'.npz')).open('xb') as f:
                np.savez(f,numpy_state=state[1],torch_cpu=torch.get_rng_state().numpy(),torch_cuda=torch.cuda.get_rng_state(0).cpu().numpy())
            c.write(folder/('rng_'+phase+'.json'),dict(python=random.getstate(),numpy_algorithm=state[0],numpy_position=state[2],numpy_has_gauss=state[3],numpy_cached_gaussian=state[4]))
        rec=dict(task_id=task['task_id'],role=role,seed=seed,prompt=task[role+'_prompt'],
            image=c.png_record(folder/(role+'.png')),original_noise=noise_record,generation_seconds=seconds)
        c.write(folder/'record.json',rec);rows.append(rec)
    c.write(output/'summary.json',dict(completed=True,role=role,rows=rows,model_loading_seconds=load,
        model=cfg['target'] if role=='reference' else cfg['proxy'],scheduler=type(provider.scheduler).__name__,
        inverse_scheduler=type(provider.scheduler_inverse).__name__,dtype=str(provider.get_dtype()),
        vae_scaling_factor=provider.pipe.vae.config.scaling_factor,protocol_sha256=c.sha(protocol),target_scores_used=False))
    print('COMPLETED_COVER_PREPARATION',flush=True)


if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3],Path(sys.argv[4]))
