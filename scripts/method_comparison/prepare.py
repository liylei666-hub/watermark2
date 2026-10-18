"""Generate new fixed reference/cover tasks; independent evaluator-only GS identities."""
import sys,time
from pathlib import Path
from common import c,r,private_module,rng

def main(runtime,role,batch,private_folder,output):
    output=Path(output);cfg=r.check_device(Path(runtime),output);batch=int(batch)
    if cfg['role']!='evaluator' or role not in ('reference','cover') or batch not in range(3):raise ValueError('Wrong preparation role')
    import torch
    private=private_module();r.deterministic(0);model=cfg['design']['target' if role=='reference' else 'proxy']
    start=time.perf_counter();provider=r.official_provider(model);torch.cuda.synchronize();loading=time.perf_counter()-start
    if provider.get_dtype()!=torch.float32:raise ValueError('Precision changed')
    rows=[]
    for task in cfg['design']['tasks'][batch*4:(batch+1)*4]:
        sid=task['task_id'];folder=output/str(sid);folder.mkdir();r.deterministic(task[role+'_seed'])
        wm=None;fingerprints=None
        if role=='reference':
            raw=private.create(Path(private_folder),sid);wm=private.provider(raw,'cuda:0');fingerprints=private.fingerprints(raw)
        rng(folder,'before_noise')
        z=wm.get_wm_latents()['zT_torch'] if wm is not None else torch.randn((1,4,64,64),device='cuda:0',dtype=torch.float32)
        original=z.detach().clone();noise=r.tensor(folder/'original_noise.npy',original);rng(folder,'before_generation')
        start=time.perf_counter()
        with torch.no_grad():generated=provider.generate(prompts=[task[role+'_prompt']],num_inference_steps=50,guidance_scale=7.5,latents=z,return_latents=False)
        torch.cuda.synchronize();seconds=time.perf_counter()-start;rng(folder,'after_generation')
        if not torch.equal(original,z):raise ValueError('Original noise changed')
        with (folder/(role+'.png')).open('xb') as f:generated['images_PIL'][0].save(f,format='PNG')
        row=dict(task_id=sid,role=role,seed=task[role+'_seed'],prompt=task[role+'_prompt'],image=c.png_record(folder/(role+'.png')),
                 original_noise=noise,encryption_fingerprints=fingerprints,generation_seconds=seconds)
        c.write(folder/'record.json',row);rows.append(row)
    c.write(output/'summary.json',dict(completed=True,rows=rows,model=model,model_loading_seconds=loading,dtype=str(provider.get_dtype()),
              scheduler=type(provider.scheduler).__name__,inverse_scheduler=type(provider.scheduler_inverse).__name__,vae_scaling_factor=provider.pipe.vae.config.scaling_factor))
    print('COMPLETED_COVER_PREPARATION',flush=True)

if __name__=='__main__':main(*sys.argv[1:])
