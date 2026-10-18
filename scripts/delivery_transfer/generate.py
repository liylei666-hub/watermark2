"""Proxy-only generation from a complete sealed float32 input bundle."""
import sys,time
from pathlib import Path
from common import c,r,bundle,tasks,METHODS
from source_worker import rng_record


def main(runtime,inputs,digest,batch,output):
    runtime=Path(runtime);inputs=Path(inputs);output=Path(output);batch=int(batch)
    cfg=r.check_device(runtime,output)
    if cfg['role']!='proxy_generator' or cfg['tasks']!=tasks() or batch not in (0,1):raise ValueError('Wrong generation contract')
    bundle(inputs,digest,'attack_inputs')
    import torch,numpy as np
    r.deterministic(0);start=time.perf_counter();provider=r.official_provider(cfg['proxy'])
    torch.cuda.synchronize();loading=time.perf_counter()-start
    if provider.get_dtype()!=torch.float32 or type(provider.scheduler).__name__!='DDIMScheduler':raise ValueError('Provider changed')
    rows=[]
    for task in tasks()[4*batch:4*batch+4]:
        for method in METHODS:
            sid=task['sample_id'];folder=output/(sid+'_'+method);folder.mkdir()
            path=inputs/(sid+'_'+method+'.npy');record=c.array_record(path)
            z=torch.from_numpy(np.load(path,allow_pickle=False).copy()).to('cuda:0');original=z.clone()
            r.deterministic(task['seed']);rng_record(folder,'before_generation');start=time.perf_counter()
            with torch.no_grad():result=provider.generate(prompts=[task['prompt']],num_inference_steps=50,guidance_scale=7.5,latents=z,return_latents=False)
            torch.cuda.synchronize();seconds=time.perf_counter()-start
            if not torch.equal(z,original):raise ValueError('Input changed by generator')
            rng_record(folder,'after_generation')
            _,image=c.save_png_readback(result['images_PIL'][0],folder/'candidate.png')
            row=dict(task=task,method=method,input=record,image=image,generation_seconds=seconds)
            c.write(folder/'record.json',row);rows.append(row)
    bundle(inputs,digest,'attack_inputs')
    c.write(output/'summary.json',dict(completed=True,rows=rows,model=cfg['proxy'],input_seal_sha256=digest,
        model_loading_seconds=loading,dtype=str(provider.get_dtype()),scheduler=type(provider.scheduler).__name__,
        vae_scaling_factor=provider.pipe.vae.config.scaling_factor))
    print('COMPLETED_DELIVERY_GENERATION',flush=True)

if __name__=='__main__':main(*sys.argv[1:])
