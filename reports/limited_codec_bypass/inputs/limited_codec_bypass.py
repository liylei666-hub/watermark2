"""Bounded cal-only JPEG codec and paired generation-latent bypass diagnostics."""
import argparse, io, json, os, sys, time
from pathlib import Path
from sd15_clip_smoke import sha, write_json, guard_gpu
from runtime_provenance import array_binding, public_cache_provenance

def instrument_invert(backend, image, sdmodule, replacement=None):
    import numpy as np
    data = {}; models = []; eps = []; updates = []; steps = []; conditions = []
    def capture(t): return t.detach().cpu().numpy().copy()
    pipe = backend.pipe
    original_encode, original_update = pipe.vae.encode, sdmodule._backward_ddim
    original_encode_image = backend.encode_image
    def encode(x, *a, **kw):
        data['vae_input_actual'] = capture(x)
        r = original_encode(x, *a, **kw)
        data['vae_mode_actual'] = capture(r.latent_dist.mode())
        return r
    def pre(module, a, kw):
        models.append(capture(a[0])); conditions.append(array_binding(capture(kw['encoder_hidden_states'])))
        steps.append({'timestep':int(a[1].item()),'batch_size':int(a[0].shape[0])})
    def post(module, a, kw, r): eps.append(capture(r.sample))
    def update(x, aa, ab, e):
        if not updates: data['initial_update_latent'] = capture(x)
        r = original_update(x, aa, ab, e)
        steps[-1].update(alpha_from=float(aa.item()), alpha_to=float(ab.item()))
        updates.append(capture(r)); return r
    pipe.vae.encode, sdmodule._backward_ddim = encode, update
    if replacement is not None:
        backend.encode_image = lambda unused_image: replacement.clone()
    h1 = pipe.unet.register_forward_pre_hook(pre, with_kwargs=True)
    h2 = pipe.unet.register_forward_hook(post, with_kwargs=True)
    try: recon = backend.invert(image).z_T
    finally:
        pipe.vae.encode, sdmodule._backward_ddim = original_encode, original_update
        backend.encode_image = original_encode_image
        h1.remove(); h2.remove()
    assert len(models) == len(eps) == len(updates) == len(steps) == 50
    assert all(s['batch_size'] == 1 for s in steps) and all(c == conditions[0] for c in conditions)
    if replacement is not None: assert 'vae_input_actual' not in data
    data.update(model_inputs=np.stack(models), epsilon_predictions=np.stack(eps),
        trajectory=np.stack([data['initial_update_latent']] + updates), recon=recon)
    return data, {'steps':steps,'conditioning_binding':conditions[0],'unet_calls':50,
        'effective_inversion':'empty prompt, one UNet branch, guidance argument unused',
        'vae_bypassed':replacement is not None,'latent_scale':sdmodule.LATENT_SCALE,'init_noise_sigma':float(pipe.scheduler.init_noise_sigma)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('phase', choices=['jpeg','replay','bypass'])
    for f in ('config','prepare-run','cal-run','trace-run','base-run','sd-cache','clip-code','clip-weight','csi-code','output'):
        ap.add_argument('--'+f,required=True)
    ap.add_argument('--replay-run')
    args=ap.parse_args();cfg=json.loads(Path(args.config).read_text());out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True);assert not (out/'frozen.json').exists()
    prepare,cal,trace,base=map(Path,[args.prepare_run,args.cal_run,args.trace_run,args.base_run])
    pr=json.loads((prepare/'runtime.json').read_text());tr=json.loads((trace/'runtime.json').read_text())
    for sid in cfg['paired_sources']:
        for name in (sid+'_original.png',sid+'_registration.npz'):assert sha(prepare/name)==pr['file_hashes'][name]
        name=sid+'_original.npz';assert sha(trace/name)==tr['file_hashes'][name]
    preflight=guard_gpu(cfg)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',DIFFUSERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',WANDB_MODE='disabled')
    import numpy as np,torch
    from PIL import Image,JpegImagePlugin
    from diffusers import DDIMScheduler,StableDiffusionPipeline
    assert torch.cuda.device_count()==1 and torch.cuda.get_device_name(0)=='NVIDIA GeForce RTX 3090'
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False
    sys.path.insert(0,args.csi_code)
    import csi.backends.sd as sdmodule
    from csi.backends.sd import StableDiffusionBackend
    from csi.schemes.seal import SealCore
    from csi.types import Key
    inv=json.loads((Path(args.csi_code).parent/'reports/reproduction_audit/csi_code_inventory.json').read_text())
    for f in inv['files']:assert sha(Path(args.csi_code)/f['path'])==f['sha256']
    bm=json.loads((base/'frozen.json').read_text())
    assert sha(args.clip_weight)==bm['clip_weight_sha256']
    for name,digest in bm['sd_file_hashes'].items():assert sha(Path(args.sd_cache)/name)==digest
    provenance=public_cache_provenance(args.sd_cache,args.clip_code)
    assert provenance['versions']==json.loads((trace/'frozen.json').read_text())['provenance']['versions']
    meta={'config':cfg,'config_sha256':sha(args.config),'script_sha256':sha(__file__),'phase':args.phase,
        'pid':os.getpid(),'preflight':preflight,'logical_gpu':0,'provenance':provenance,
        'prepare_frozen_sha256':sha(prepare/'frozen.json'),'trace_frozen_sha256':sha(trace/'frozen.json'),
        'csi_backend_sha256':sha(Path(args.csi_code)/'csi/backends/sd.py'),
        'source_bindings':{n:pr['file_hashes'][n] for sid in cfg['paired_sources'] for n in (sid+'_original.png',sid+'_registration.npz')},
        'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    if args.phase=='bypass':
        assert args.replay_run
        replay=Path(args.replay_run);rr=json.loads((replay/'runtime.json').read_text())
        assert rr['generated_images']==2 and rr['inversions']==0
        for n,h in rr['file_hashes'].items():assert sha(replay/n)==h
        meta['replay_frozen_sha256']=sha(replay/'frozen.json')
    write_json(out/'frozen.json',meta);start=time.perf_counter()
    pipe=StableDiffusionPipeline.from_pretrained(args.sd_cache,torch_dtype=torch.float16,local_files_only=True,use_safetensors=True)
    assert pipe.safety_checker is not None
    pipe.scheduler=DDIMScheduler.from_config(pipe.scheduler.config);pipe.set_progress_bar_config(disable=True);pipe.to('cuda')
    assert float(pipe.scheduler.init_noise_sigma)==1.
    backend=object.__new__(StableDiffusionBackend);backend.pipe,backend.device=pipe,'cuda';backend.steps=50;backend.guidance=7.5;backend.invert_guidance=1.
    core=SealCore(k=1024,b=7,t_patch=2.);key=Key(seed=42);rows=[];inversions=generated=0
    if args.phase=='jpeg':
        sys.path.insert(0,args.clip_code);import clip
        model,preprocess=clip.load(args.clip_weight,device='cuda',jit=False);model.eval()
        sid='c04';original=Image.open(prepare/(sid+'_original.png')).convert('RGB')
        # Positive codec binding: reproduce the original quality70/subsampling2 bytes before adding variants.
        buf=io.BytesIO();original.save(buf,format='JPEG',quality=70,subsampling=2)
        assert buf.getvalue()==(prepare/(sid+'_jpeg70.jpg')).read_bytes()
        assert np.array_equal(np.array(Image.open(io.BytesIO(buf.getvalue())).convert('RGB')),np.array(Image.open(prepare/(sid+'_jpeg70.png')).convert('RGB')))
        write_json(out/'codec_control.json',{'baseline_jpeg70_420_bytes_exact':True,'baseline_jpeg70_420_decoded_rgb_exact':True,'prior_jpeg_sha256':sha(prepare/(sid+'_jpeg70.jpg'))})
        registration=np.load(prepare/(sid+'_registration.npz'),allow_pickle=False)
        draft,registered=registration['draft_feature'],registration['registered_z'];dids=core.bucket_ids(draft,key)
        for variant in cfg['jpeg_variants']:
            name=sid+'_'+variant['id'];buf=io.BytesIO()
            original.save(buf,format='JPEG',quality=variant['quality'],subsampling=variant['subsampling'])
            (out/(name+'.jpg')).write_bytes(buf.getvalue())
            decoded=Image.open(io.BytesIO(buf.getvalue()));assert JpegImagePlugin.get_sampling(decoded)==variant['subsampling']
            image=decoded.convert('RGB');image.save(out/(name+'.png'));rgb=np.array(image)
            with torch.inference_mode():
                ci=preprocess(image).unsqueeze(0);v=model.encode_image(ci.to('cuda')).float()
                v=(v/v.norm(dim=-1,keepdim=True)).cpu().numpy().astype(np.float64).ravel()
            data,details=instrument_invert(backend,image,sdmodule);inversions+=1
            reference=core.noise_from_embedding(v,key);qids=core.bucket_ids(v,key)
            l2=core.patch_l2(data['recon'],reference);oracle=core.patch_l2(data['recon'],registered)
            E=qids==dids;D=oracle<=2.;A=l2<=2.
            data.update(input_rgb=rgb,clip_input_float32=ci.numpy(),feature=v,reference=reference,registered_z=registered,
                draft_feature=draft,query_bucket_ids=qids,draft_bucket_ids=dids,native_l2=l2,oracle_l2=oracle,E=E,D=D,A=A)
            np.savez_compressed(out/(name+'.npz'),**data)
            row={'source':sid,'variant':variant,'arrays_file':name+'.npz','input_image_sha256':sha(out/(name+'.png')),
                'jpeg_sha256':sha(out/(name+'.jpg')),'array_bindings':{k:array_binding(a) for k,a in data.items()},
                'match_count':int(A.sum()),'oracle_matches':int(D.sum()),'E':int(E.sum()),
                'E_intersect_D':int((E&D).sum()),'A_outside_E':int((A&~E).sum()),**details}
            rows.append(row);write_json(out/'partial_results.json',rows)
            print(json.dumps({k:row[k] for k in ('source','variant','match_count','oracle_matches','E')}),flush=True)
    elif args.phase=='replay':
        sourcecfg=json.loads((Path(__file__).parents[1]/'configs/sd15_clip_calibration.json').read_text())
        assert sha(Path(__file__).parents[1]/'configs/sd15_clip_calibration.json')==json.loads((prepare/'frozen.json').read_text())['config_sha256']
        for sid in cfg['paired_sources']:
            s=next(s for s in sourcecfg['sources'] if s['id']==sid);captured={};callbacks=[]
            registered=np.load(prepare/(sid+'_registration.npz'),allow_pickle=False)['registered_z']
            def end_callback(pipeline,index,timestep,kwargs):
                callbacks.append(int(index))
                if index==49:captured['terminal_generation_latent']=kwargs['latents'].detach().cpu().numpy().copy()
                return kwargs
            decode_original=pipe.vae.decode
            def decode_hook(z,*a,**kw):
                captured['actual_decoder_input']=z.detach().cpu().numpy().copy()
                return decode_original(z,*a,**kw)
            pipe.vae.decode=decode_hook
            try:
                with torch.inference_mode():
                    result=pipe(s['prompt'],latents=backend._to_torch(registered),num_inference_steps=50,guidance_scale=7.5,
                        callback_on_step_end=end_callback,callback_on_step_end_tensor_inputs=['latents'])
            finally:pipe.vae.decode=decode_original
            generated+=1;assert callbacks==list(range(50)) and result.nsfw_content_detected is not None
            image=result.images[0];image.save(out/(sid+'_replay.png'))
            safety=[bool(x) for x in result.nsfw_content_detected]
            assert not any(safety),'Preserve safety failure; stop'
            old=np.array(Image.open(prepare/(sid+'_original.png')).convert('RGB'));new=np.array(image.convert('RGB'))
            paired=np.array_equal(old,new)
            prior=np.load(trace/(sid+'_original.npz'),allow_pickle=False)
            captured.update(registered_z=registered,old_rgb=old,replay_rgb=new,old_vae_scaled_mode=prior['initial_update_latent'])
            expected=torch.from_numpy(captured['terminal_generation_latent']).to('cuda')/pipe.vae.config.scaling_factor
            assert np.array_equal(expected.cpu().numpy(),captured['actual_decoder_input'])
            np.savez_compressed(out/(sid+'_replay.npz'),**captured)
            row={'source':sid,'paired_old_pixels_exact':bool(paired),'paired_old_png_bytes_exact':sha(out/(sid+'_replay.png'))==sha(prepare/(sid+'_original.png')),
                'old_image_sha256':sha(prepare/(sid+'_original.png')),'replay_image_sha256':sha(out/(sid+'_replay.png')),
                'arrays_file':sid+'_replay.npz','array_bindings':{k:array_binding(a) for k,a in captured.items()},
                'safety_flags':safety,'generation_guidance':7.5,'generation_steps':50,'decoder_scaling_factor':float(pipe.vae.config.scaling_factor)}
            rows.append(row);write_json(out/'partial_results.json',rows);print(json.dumps({k:row[k] for k in ('source','paired_old_pixels_exact','paired_old_png_bytes_exact')}),flush=True)
    else:
        pairedrows=json.loads((replay/'results.json').read_text())
        for pairing in pairedrows:
            if not pairing['paired_old_pixels_exact']:
                rows.append({'source':pairing['source'],'bypass_executed':False,'reason':'generation replay pixel mismatch; no old-image latent pairing'})
                continue
            sid=pairing['source'];a=np.load(replay/pairing['arrays_file'],allow_pickle=False);prior=np.load(trace/(sid+'_original.npz'),allow_pickle=False)
            original=Image.open(prepare/(sid+'_original.png')).convert('RGB')
            assert np.array_equal(a['old_rgb'],a['replay_rgb']) and np.array_equal(a['old_rgb'],np.array(original))
            terminal=torch.from_numpy(a['terminal_generation_latent']).to('cuda',dtype=pipe.unet.dtype)
            data,details=instrument_invert(backend,original,sdmodule,replacement=terminal);inversions+=1
            assert np.array_equal(data['initial_update_latent'],a['terminal_generation_latent'])
            reference,registered=prior['reference'],prior['registered_z'];qids,dids=prior['query_bucket_ids'],prior['draft_bucket_ids']
            l2=core.patch_l2(data['recon'],reference);oracle=core.patch_l2(data['recon'],registered);E=qids==dids;D=oracle<=2.;A=l2<=2.
            data.update(terminal_generation_latent=a['terminal_generation_latent'],old_vae_scaled_mode=prior['initial_update_latent'],
                old_recon=prior['recon'],input_rgb=prior['input_rgb'],feature=prior['feature'],reference=reference,registered_z=registered,
                draft_feature=prior['draft_feature'],query_bucket_ids=qids,draft_bucket_ids=dids,native_l2=l2,oracle_l2=oracle,E=E,D=D,A=A)
            np.savez_compressed(out/(sid+'_bypass.npz'),**data)
            row={'source':sid,'bypass_executed':True,'paired_replay_file_sha256':sha(replay/pairing['arrays_file']),
                'arrays_file':sid+'_bypass.npz','array_bindings':{k:array_binding(v) for k,v in data.items()},
                'match_count':int(A.sum()),'oracle_matches':int(D.sum()),'E':int(E.sum()),
                'E_intersect_D':int((E&D).sum()),'A_outside_E':int((A&~E).sum()),**details}
            rows.append(row);write_json(out/'partial_results.json',rows)
            print(json.dumps({k:row[k] for k in ('source','bypass_executed','match_count','oracle_matches')}),flush=True)
    assert inversions<=2 and generated<=2
    write_json(out/'results.json',rows)
    hashes={p.name:sha(p) for p in out.iterdir() if p.suffix in ('.json','.npz','.png','.jpg')}
    write_json(out/'runtime.json',{'wall_seconds':time.perf_counter()-start,'phase':args.phase,'inversions':inversions,'generated_images':generated,
        'weights_downloaded_bytes':0,'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated(0),'max_cuda_reserved_bytes':torch.cuda.max_memory_reserved(0),
        'gpu_uuid':cfg['physical_gpu_uuid'],'file_hashes':hashes,'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print('Bounded phase complete',flush=True)

if __name__=='__main__':main()
