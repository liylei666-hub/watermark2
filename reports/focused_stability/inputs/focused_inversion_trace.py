"""Six instrumented calls to the pinned native invert method; no image generation."""
import argparse,json,os
from pathlib import Path
import sys,time
from sd15_clip_smoke import sha,write_json,guard_gpu
from runtime_provenance import public_cache_provenance,array_binding

def main():
    ap=argparse.ArgumentParser()
    for f in ('config','cpu-run','prepare-run','cal-run','base-run','sd-cache','clip-code','clip-weight','csi-code','output'):ap.add_argument('--'+f,required=True)
    args=ap.parse_args();cfg=json.loads(Path(args.config).read_text());cpu=Path(args.cpu_run);out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True);assert not (out/'frozen.json').exists()
    controls=json.loads((cpu/'cpu_results.json').read_text());assert controls['status']=='passed' and all(controls['controls'].values())
    def cell(rv,sv):
        return next(r['A'] for r in controls['rows'] if r['source']=='c04' and r['recon_input']==rv and r['semantic_input']==sv)
    assert cell('original','jpeg70')>=10 and cell('jpeg70','original')<10,'GPU trigger not satisfied'
    preflight=guard_gpu(cfg['conditional_gpu'])
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',DIFFUSERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',WANDB_MODE='disabled')
    import numpy as np,torch
    from PIL import Image
    from diffusers import DDIMScheduler,StableDiffusionPipeline
    assert torch.cuda.device_count()==1 and torch.cuda.get_device_name(0)=='NVIDIA GeForce RTX 3090'
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False
    sys.path.insert(0,args.csi_code)
    import csi.backends.sd as sdmodule
    from csi.backends.sd import StableDiffusionBackend
    from csi.schemes.seal import SealCore
    from csi.types import Key
    sys.path.insert(0,args.clip_code);import clip
    base=Path(args.base_run);bm=json.loads((base/'frozen.json').read_text())
    assert sha(args.clip_weight)==bm['clip_weight_sha256']
    for name,digest in bm['sd_file_hashes'].items():assert sha(Path(args.sd_cache)/name)==digest
    for name,digest in bm['clip_source_hashes'].items():assert sha(Path(args.clip_code)/name)==digest
    inv=json.loads((Path(args.csi_code).parent/'reports/reproduction_audit/csi_code_inventory.json').read_text())
    for f in inv['files']:assert sha(Path(args.csi_code)/f['path'])==f['sha256']
    cal=Path(args.cal_run);prepare=Path(args.prepare_run)
    provenance=public_cache_provenance(args.sd_cache,args.clip_code)
    previous=json.loads((cal/'frozen.json').read_text())['current_runtime_and_small_artifacts']
    assert provenance['versions']==previous['versions'],'Runtime changed; inspect before comparing'
    meta={'config':cfg,'config_sha256':sha(args.config),'script_sha256':sha(__file__),'pid':os.getpid(),
        'preflight':preflight,'logical_gpu':0,'cpu_controls_sha256':sha(cpu/'cpu_results.json'),
        'cal_frozen_sha256':sha(cal/'frozen.json'),'base_frozen_sha256':sha(base/'frozen.json'),
        'provenance':provenance,'csi_backend_sha256':sha(Path(args.csi_code)/'csi/backends/sd.py'),
        'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    write_json(out/'frozen.json',meta);start=time.perf_counter()
    pipe=StableDiffusionPipeline.from_pretrained(args.sd_cache,torch_dtype=torch.float16,local_files_only=True,use_safetensors=True)
    assert pipe.safety_checker is not None
    pipe.scheduler=DDIMScheduler.from_config(pipe.scheduler.config);pipe.set_progress_bar_config(disable=True);pipe.to('cuda')
    backend=object.__new__(StableDiffusionBackend);backend.pipe,backend.device=pipe,'cuda';backend.steps=50;backend.guidance=7.5;backend.invert_guidance=1.
    model,preprocess=clip.load(args.clip_weight,device='cuda',jit=False);model.eval()
    core=SealCore(k=1024,b=7,t_patch=2.);key=Key(seed=42);rows=[]
    def capture(t):return t.detach().cpu().numpy().copy()
    for sid in ('c04','c02'):
        prior=np.load(cal/(sid+'_arrays.npz'),allow_pickle=False);draft=prior['draft_feature'];registered=prior['registered_z'];draft_ids=core.bucket_ids(draft,key)
        for variant in ('original','lossless_pixel_identity','jpeg70'):
            name=sid+'_'+variant
            path=cpu/(sid+'_lossless_pixel_identity.png') if variant=='lossless_pixel_identity' else prepare/(sid+'_'+variant+'.png')
            image=Image.open(path).convert('RGB');rgb=np.array(image)
            expected='original' if variant=='lossless_pixel_identity' else variant
            original_rgb=np.array(Image.open(prepare/(sid+'_'+expected+'.png')).convert('RGB'))
            assert np.array_equal(rgb,original_rgb)
            with torch.inference_mode():
                clip_input=preprocess(image).unsqueeze(0)
                v=model.encode_image(clip_input.to('cuda')).float();v=(v/v.norm(dim=-1,keepdim=True)).cpu().numpy().astype(np.float64).ravel()
            reference=core.noise_from_embedding(v,key);qids=core.bucket_ids(v,key)
            data={'input_rgb':rgb,'clip_input_float32':capture(clip_input),'feature':v,'reference':reference,'registered_z':registered,'draft_feature':draft,'query_bucket_ids':qids,'draft_bucket_ids':draft_ids}
            model_inputs=[];epsilons=[];updates=[];stepinfo=[];conditions=[]
            original_encode=pipe.vae.encode;original_update=sdmodule._backward_ddim
            def wrapped_encode(x,*a,**kw):
                data['vae_input_actual']=capture(x)
                result=original_encode(x,*a,**kw)
                data['vae_mode_actual']=capture(result.latent_dist.mode())
                return result
            def pre_hook(module,a,kw):
                model_inputs.append(capture(a[0]))
                conditions.append(array_binding(capture(kw['encoder_hidden_states'])))
                stepinfo.append({'timestep':int(a[1].item()),'input_dtype':str(a[0].dtype),'batch_size':int(a[0].shape[0])})
            def post_hook(module,a,kw,result):epsilons.append(capture(result.sample))
            def wrapped_update(x,aa,ab,eps):
                if not updates:data['initial_update_latent']=capture(x)
                result=original_update(x,aa,ab,eps)
                updates.append(capture(result));stepinfo[-1].update(alpha_from=float(aa.item()),alpha_to=float(ab.item()),output_dtype=str(result.dtype))
                return result
            pipe.vae.encode=wrapped_encode;sdmodule._backward_ddim=wrapped_update
            pre_handle=pipe.unet.register_forward_pre_hook(pre_hook,with_kwargs=True)
            post_handle=pipe.unet.register_forward_hook(post_hook,with_kwargs=True)
            t=time.perf_counter()
            try:
                recon=backend.invert(image).z_T
            finally:
                pipe.vae.encode=original_encode;sdmodule._backward_ddim=original_update;pre_handle.remove();post_handle.remove()
            assert len(model_inputs)==len(epsilons)==len(updates)==len(stepinfo)==50
            assert all(x['batch_size']==1 for x in stepinfo)
            assert all(c==conditions[0] for c in conditions)
            data.update(model_inputs=np.stack(model_inputs),epsilon_predictions=np.stack(epsilons),
                trajectory=np.stack([data['initial_update_latent']]+updates),recon=recon)
            l2=core.patch_l2(recon,reference);oracle=core.patch_l2(recon,registered)
            E=qids==draft_ids;D=oracle<=2.;A=l2<=2.;assert np.array_equal(A[E],D[E])
            data.update(native_l2=l2,oracle_l2=oracle,E=E,D=D,A=A)
            np.savez_compressed(out/(name+'.npz'),**data)
            row={'source':sid,'variant':variant,'image_file_sha256':sha(path),'input_rgb':array_binding(rgb),
                'arrays_file':name+'.npz','array_bindings':{k:array_binding(a) for k,a in data.items()},
                'match_count':int(A.sum()),'oracle_matches':int(D.sum()),'E':int(E.sum()),'E_intersect_D':int((E&D).sum()),'A_outside_E':int((A&~E).sum()),
                'steps':stepinfo,'conditioning_binding':conditions[0],'unet_calls':50,'classifier_free_guidance_branch':False,
                'configured_inversion_guidance':1.,'effective_guidance_argument':'unused in pinned method',
                'latent_scale':sdmodule.LATENT_SCALE,'init_noise_sigma':float(pipe.scheduler.init_noise_sigma),
                'vae_dtype':str(pipe.vae.dtype),'unet_dtype':str(pipe.unet.dtype),'clip_visual_compute_dtype':str(model.dtype),
                'feature_max_delta_from_prior':float(np.max(np.abs(v-prior[expected+'_feature']))),
                'recon_max_delta_from_prior':float(np.max(np.abs(recon-prior[expected+'_recon']))),
                'reference_max_delta_from_prior':float(np.max(np.abs(reference-prior[expected+'_reference']))),
                'wall_seconds':time.perf_counter()-t}
            rows.append(row);write_json(out/'partial_results.json',rows)
            print(json.dumps({k:row[k] for k in ('source','variant','match_count','oracle_matches','feature_max_delta_from_prior','recon_max_delta_from_prior','wall_seconds')}),flush=True)
    write_json(out/'results.json',rows)
    hashes={p.name:sha(p) for p in out.iterdir() if p.suffix in ('.json','.npz')}
    write_json(out/'runtime.json',{'wall_seconds':time.perf_counter()-start,'inversions':6,'generated_images':0,'weights_downloaded_bytes':0,
        'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated(0),'max_cuda_reserved_bytes':torch.cuda.max_memory_reserved(0),
        'gpu_uuid':cfg['conditional_gpu']['physical_gpu_uuid'],'file_hashes':hashes,
        'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print('Completed six native inversions with trace hooks',flush=True)
if __name__=='__main__':main()
