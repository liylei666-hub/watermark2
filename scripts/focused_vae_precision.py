"""Small VAE precision ladder after hash-verified two-source trace evidence."""
import argparse,json,os
from pathlib import Path
import time
from sd15_clip_smoke import sha,write_json,guard_gpu
from runtime_provenance import array_binding
def main():
    ap=argparse.ArgumentParser()
    for f in ('config','trace-run','trace-audit','sd-cache','output'):ap.add_argument('--'+f,required=True)
    args=ap.parse_args();cfg=json.loads(Path(args.config).read_text());out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True);assert not (out/'frozen.json').exists()
    audit=json.loads(Path(args.trace_audit).read_text());assert audit['status']=='passed' and audit['same_pixel_all_stages_exact']
    a,b=audit['diagnostics']['c04'],audit['diagnostics']['c02']
    assert a['vae_mode_actual']>2*b['vae_mode_actual'] and a['vae_input_actual']<b['vae_input_actual']
    preflight=guard_gpu(cfg)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',DIFFUSERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',WANDB_MODE='disabled')
    import numpy as np,torch
    from diffusers import AutoencoderKL
    assert torch.cuda.device_count()==1 and torch.cuda.get_device_name(0)=='NVIDIA GeForce RTX 3090'
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False
    trace=Path(args.trace_run);meta=json.loads((trace/'frozen.json').read_text());rt=json.loads((trace/'runtime.json').read_text())
    for s in cfg['sources']:
        for v in cfg['variants']:assert sha(trace/(s+'_'+v+'.npz'))==rt['file_hashes'][s+'_'+v+'.npz']
    vaefile=Path(args.sd_cache)/'vae/diffusion_pytorch_model.safetensors'
    assert sha(vaefile)=='a2b5134f4dbc140d9c11f11cba3233099e00af40f262f136c691fb7d38d2194c'
    write_json(out/'frozen.json',{'config':cfg,'config_sha256':sha(args.config),'script_sha256':sha(__file__),
        'trace_frozen_sha256':sha(trace/'frozen.json'),'trace_audit_sha256':sha(args.trace_audit),'vae_checkpoint_sha256':sha(vaefile),
        'preflight':preflight,'logical_gpu':0,'pid':os.getpid(),'torch':torch.__version__,
        'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    start=time.perf_counter();rows=[]
    vae=AutoencoderKL.from_pretrained(args.sd_cache,subfolder='vae',torch_dtype=torch.float16,use_safetensors=True,local_files_only=True).to('cuda')
    for branch in cfg['branches']:
        if branch=='fp32_arithmetic_fp16_weights_fp16_input':
            vae.to(dtype=torch.float32) # exact expansion of already quantized native weights
        elif branch=='fp32_checkpoint_weights_fp16_input':
            del vae
            vae=AutoencoderKL.from_pretrained(args.sd_cache,subfolder='vae',torch_dtype=torch.float32,use_safetensors=True,local_files_only=True).to('cuda')
        for s in cfg['sources']:
            for v in cfg['variants']:
                prior=np.load(trace/(s+'_'+v+'.npz'),allow_pickle=False)
                if branch=='fp32_checkpoint_weights_fp32_input':
                    pixels=prior['input_rgb'].astype(np.float32)/255.
                    x=torch.from_numpy(pixels).permute(2,0,1)[None]*2.-1.
                else:
                    x=torch.from_numpy(prior['vae_input_actual'])
                x=x.to(device='cuda',dtype=vae.dtype)
                t=time.perf_counter()
                with torch.inference_mode():
                    result=vae.encode(x).latent_dist
                    mode=result.mode();logvar=result.logvar;scaled=mode*cfg['latent_scale']
                data={'mode':mode.cpu().numpy().copy(),'logvar':logvar.cpu().numpy().copy(),'scaled_latent':scaled.cpu().numpy().copy()}
                if branch=='native_fp16':assert np.array_equal(data['mode'],prior['vae_mode_actual']),'Standalone native VAE differs; stop'
                name=branch+'_'+s+'_'+v
                np.savez_compressed(out/(name+'.npz'),**data)
                row={'branch':branch,'source':s,'variant':v,'prior_trace_sha256':sha(trace/(s+'_'+v+'.npz')),
                    'input_binding':array_binding(x.detach().cpu().numpy()),'arrays_file':name+'.npz',
                    'array_bindings':{k:array_binding(a) for k,a in data.items()},'model_dtype':str(vae.dtype),
                    'attention_processors':sorted({type(a).__name__ for a in vae.attn_processors.values()}),
                    'mode_rmse_from_native':float(np.sqrt(np.mean((data['mode'].astype(float)-prior['vae_mode_actual'].astype(float))**2))),
                    'wall_seconds':time.perf_counter()-t}
                rows.append(row);write_json(out/'partial_results.json',rows)
                print(json.dumps({k:row[k] for k in ('branch','source','variant','mode_rmse_from_native')}),flush=True)
    assert len(rows)==16;write_json(out/'results.json',rows)
    hashes={p.name:sha(p) for p in out.iterdir() if p.suffix in ('.json','.npz')}
    write_json(out/'runtime.json',{'wall_seconds':time.perf_counter()-start,'vae_encodes':16,'inversions':0,'generated_images':0,'weights_downloaded_bytes':0,
        'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated(0),'max_cuda_reserved_bytes':torch.cuda.max_memory_reserved(0),
        'gpu_uuid':cfg['physical_gpu_uuid'],'file_hashes':hashes,'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print('Completed VAE precision ladder; no new inversion or generation',flush=True)
if __name__=='__main__':main()
