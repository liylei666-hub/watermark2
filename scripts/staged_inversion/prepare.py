"""Generate four new fixed tasks; GS identity and original noise stay evaluator-only."""
import sys,time
from pathlib import Path
from common import c,r,module,preimport,BASE


def main(runtime,role,private_folder,output):
    output=Path(output);cfg=preimport(runtime,output)
    if cfg['role']!='evaluator' or role not in ('reference','cover'):raise ValueError('Wrong preparation role')
    import torch
    private=module('stage28_private',BASE/'reference_reliability/private_state.py')
    r.deterministic(0);model=cfg['design']['target' if role=='reference' else 'proxy']
    start=time.perf_counter();provider=r.official_provider(model);torch.cuda.synchronize();loading=time.perf_counter()-start
    if provider.get_dtype()!=torch.float32:raise ValueError('Expected float32')
    rows=[]
    for task in cfg['design']['tasks']:
        sid=task['task_id'];out=output/str(sid);out.mkdir();r.deterministic(task[role+'_seed'])
        raw=private.create(Path(private_folder),sid) if role=='reference' else None
        wm=private.provider(raw,'cuda:0') if raw is not None else None
        z=wm.get_wm_latents()['zT_torch'] if wm else torch.randn((1,4,64,64),device='cuda:0',dtype=torch.float32)
        original=z.detach().clone();noise=r.tensor(out/'original_noise.npy',original)
        start=time.perf_counter()
        with torch.no_grad():result=provider.generate(prompts=[task[role+'_prompt']],num_inference_steps=50,
            guidance_scale=7.5,latents=z,return_latents=False)
        torch.cuda.synchronize();elapsed=time.perf_counter()-start
        if not torch.equal(z,original):raise ValueError('Input noise changed')
        with (out/(role+'.png')).open('xb') as stream:result['images_PIL'][0].save(stream,format='PNG')
        row=dict(task_id=sid,role=role,prompt=task[role+'_prompt'],seed=task[role+'_seed'],
            image=c.png_record(out/(role+'.png')),original_noise=noise,
            encryption_fingerprints=private.fingerprints(raw) if raw is not None else None,generation_seconds=elapsed)
        c.write(out/'record.json',row);rows.append(row)
        print('PREPARED',role,sid,flush=True)
    c.write(output/'summary.json',dict(completed=True,rows=rows,model=model,model_load_seconds=loading))
    print('COMPLETED_STAGED_PREPARATION',flush=True)


if __name__=='__main__':main(*sys.argv[1:])
