"""Frozen independent engineering calibration; test begins only after a cal-only operating point."""
import argparse
import io
import json
import math
import os
from pathlib import Path
import sys
import time
from sd15_clip_smoke import sha, write_json, guard_gpu
from runtime_provenance import array_binding, public_cache_provenance

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('phase',choices=['prepare','calibration','test'])
    for flag in ('config','base-run','sd-cache','clip-code','clip-weight','csi-code','output'):
        ap.add_argument('--'+flag,required=True)
    ap.add_argument('--prepare-run');ap.add_argument('--cal-run')
    args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    assert cfg['source_count']==12 and cfg['calibration_source_count']==cfg['test_source_count']==6
    sources=cfg['sources']
    assert len({s['id'] for s in sources})==len({s['family'] for s in sources})==len({s['seed'] for s in sources})==12
    assert not {s['seed'] for s in sources}&{2026100801,2026100802,2026100803,2026100821}
    assert cfg['core']=={'k':1024,'b':7,'t_patch':2.0,'unchecked_fallback_matches':10}
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    assert not (out/'frozen.json').exists(),'Never overwrite a phase'
    prepare=Path(args.prepare_run) if args.prepare_run else None
    operating=None
    if args.phase!='prepare':
        review=json.loads((prepare/'visual_review.json').read_text())
        assert review['all_benign_facts_unchanged'] and review['reviewed_before_scoring']
        assert len(review['image_hashes'])==60
        for name,digest in review['image_hashes'].items():assert sha(prepare/name)==digest
        pr=json.loads((prepare/'runtime.json').read_text())
        for name,digest in pr['file_hashes'].items():assert sha(prepare/name)==digest
        if args.phase=='test':
            cal=Path(args.cal_run)
            operating=json.loads((cal/'operating_point.json').read_text())
            assert operating['selected_without_test_scores']
            assert sha(cal/'scores.json')==operating['cal_scores_sha256']
            assert sha(args.config)==operating['config_sha256']
            assert operating['source_ids']==[s['id'] for s in sources if s['split']=='calibration']
    preflight=guard_gpu(cfg)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',DIFFUSERS_OFFLINE='1',
                      TOKENIZERS_PARALLELISM='false',WANDB_MODE='disabled')
    import numpy as np
    import torch
    from PIL import Image
    from diffusers import DDIMScheduler,StableDiffusionPipeline
    assert torch.cuda.device_count()==1 and torch.cuda.get_device_name(0)=='NVIDIA GeForce RTX 3090'
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False
    sys.path.insert(0,args.csi_code)
    from csi.backends.sd import StableDiffusionBackend
    from csi.schemes.seal import SealCore
    from csi.types import Key
    sys.path.insert(0,args.clip_code)
    import clip
    base=Path(args.base_run);bm=json.loads((base/'frozen.json').read_text())
    assert sha(args.clip_weight)==bm['clip_weight_sha256']
    for name,digest in bm['sd_file_hashes'].items():assert sha(Path(args.sd_cache)/name)==digest
    for name,digest in bm['clip_source_hashes'].items():assert sha(Path(args.clip_code)/name)==digest
    inv=json.loads((Path(args.csi_code).parent/'reports/reproduction_audit/csi_code_inventory.json').read_text())
    for f in inv['files']:assert sha(Path(args.csi_code)/f['path'])==f['sha256']
    meta={'config':cfg,'config_sha256':sha(args.config),'script_sha256':sha(__file__),
          'helper_sha256':sha(Path(__file__).with_name('runtime_provenance.py')),
          'phase':args.phase,'pid':os.getpid(),'preflight':preflight,'logical_gpu':0,
          'base_frozen_sha256':sha(base/'frozen.json'),
          'current_runtime_and_small_artifacts':public_cache_provenance(args.sd_cache,args.clip_code),
          'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    if args.phase!='prepare':
        meta['visual_review_sha256']=sha(prepare/'visual_review.json')
        meta['prepare_frozen_sha256']=sha(prepare/'frozen.json')
    if operating is not None:
        meta['operating_point']=operating;meta['operating_point_sha256']=sha(cal/'operating_point.json')
    write_json(out/'frozen.json',meta)
    start=time.perf_counter()
    pipe=StableDiffusionPipeline.from_pretrained(args.sd_cache,torch_dtype=torch.float16,local_files_only=True,use_safetensors=True)
    assert pipe.safety_checker is not None
    pipe.scheduler=DDIMScheduler.from_config(pipe.scheduler.config)
    pipe.set_progress_bar_config(disable=True);pipe.to('cuda')
    backend=object.__new__(StableDiffusionBackend)
    backend.pipe,backend.device=pipe,'cuda'
    backend.steps,backend.guidance,backend.invert_guidance=50,7.5,1.0
    model,preprocess=clip.load(args.clip_weight,device='cuda',jit=False);model.eval()
    core=SealCore(k=1024,b=7,t_patch=2.0);key=Key(seed=42)
    @torch.inference_mode()
    def feature(image):
        v=model.encode_image(preprocess(image).unsqueeze(0).to('cuda')).float()
        return (v/v.norm(dim=-1,keepdim=True)).cpu().numpy().astype(np.float64).ravel()
    rows=[];safety=[];generated=0
    if args.phase=='prepare':
        @torch.inference_mode()
        def generate(prompt,z,name):
            r=pipe(prompt,latents=backend._to_torch(z),num_inference_steps=50,guidance_scale=7.5)
            r.images[0].save(out/(name+'.png'))
            assert r.nsfw_content_detected is not None
            safety.append({'image':name,'nsfw_content_detected':[bool(x) for x in r.nsfw_content_detected]})
            write_json(out/'safety_outputs.json',safety)
            assert not any(r.nsfw_content_detected),'Preserve safety failure and stop'
            return r.images[0]
        for s in sources:
            sid=s['id']
            draft=generate(s['prompt'],backend.random_latents(seed=s['seed']),sid+'_unmarked')
            v=feature(draft);z=core.noise_from_embedding(v,key)
            image=generate(s['prompt'],z,sid+'_original');generated+=2
            np.savez_compressed(out/(sid+'_registration.npz'),draft_feature=v,registered_z=z)
            for variant in cfg['benign_variants'][1:]:
                if variant.startswith('jpeg'):
                    buf=io.BytesIO();image.save(buf,format='JPEG',quality=int(variant[4:]),subsampling=2)
                    (out/(sid+'_'+variant+'.jpg')).write_bytes(buf.getvalue())
                    transformed=Image.open(io.BytesIO(buf.getvalue())).convert('RGB')
                else:
                    factor={'resize05':0.5,'resize075':0.75}[variant]
                    edge=int(512*factor)
                    transformed=image.resize((edge,edge),Image.Resampling.BICUBIC).resize((512,512),Image.Resampling.BICUBIC)
                transformed.save(out/(sid+'_'+variant+'.png'))
            print(json.dumps({'prepared_source':sid,'split':s['split'],'generated':generated}),flush=True)
    else:
        selected=[s for s in sources if s['split']==args.phase]
        for s in selected:
            sid=s['id'];arrays={}
            registration=np.load(prepare/(sid+'_registration.npz'),allow_pickle=False)
            arrays.update(registered_z=registration['registered_z'],draft_feature=registration['draft_feature'])
            variants=list(cfg['benign_variants'])+(['unmarked'] if args.phase=='test' else [])
            for variant in variants:
                name=sid+'_'+variant
                image=Image.open(prepare/(name+'.png')).convert('RGB')
                t=time.perf_counter();v=feature(image);reference=core.noise_from_embedding(v,key)
                recon=backend.invert(image).z_T;l2=core.patch_l2(recon,reference);count=int((l2<=2.0).sum())
                arrays.update({variant+'_feature':v,variant+'_reference':reference,variant+'_recon':recon,variant+'_l2':l2})
                row={'source':sid,'family':s['family'],'split':s['split'],'variant':variant,
                    'kind':'unmarked_negative' if variant=='unmarked' else 'benign_marked',
                    'input_image_sha256':sha(prepare/(name+'.png')),'decoded_rgb':array_binding(np.array(image)),
                    'array_file':sid+'_arrays.npz','array_prefix':variant,
                    'stage_bindings':{k:array_binding(a) for k,a in [('feature',v),('reference',reference),('recon',recon),('l2',l2)]},
                    'match_count':count,'unchecked_fallback_accepted':count>=10,
                    'patch_l2_min':float(l2.min()),'patch_l2_median':float(np.median(l2)),
                    'patch_l2_max':float(l2.max()),'wall_seconds':time.perf_counter()-t,
                    'completed_stages':['decode_rgb','clip_l2_feature','keyed_reference_noise','empty_prompt_ddim_inversion','patch_l2','match_count']}
                if operating is not None:
                    accepted=count>=operating['count_threshold']
                    row.update(calibrated_accepted=accepted,first_rejection_stage=None if accepted else 'match_count_threshold')
                rows.append(row);write_json(out/'partial_scores.json',rows)
                print(json.dumps({'source':sid,'variant':variant,'count':count}),flush=True)
            np.savez_compressed(out/(sid+'_arrays.npz'),**arrays)
        write_json(out/'scores.json',rows)
        if args.phase=='calibration':
            ids=[s['id'] for s in selected]
            minima={sid:min(r['match_count'] for r in rows if r['source']==sid) for sid in ids}
            required=math.ceil(cfg['target_source_bundle_acceptance']*len(ids))
            threshold=sorted(minima.values(),reverse=True)[required-1]
            op={'config_sha256':sha(args.config),'cal_scores_sha256':sha(out/'scores.json'),
                'selected_without_test_scores':True,'source_ids':ids,'source_bundle_min_counts':minima,
                'target_source_bundle_acceptance':cfg['target_source_bundle_acceptance'],
                'required_accepted_source_bundles':required,'count_threshold':threshold,
                'achieved_cal_source_bundles':sum(v>=threshold for v in minima.values()),
                'degenerate_zero_threshold':threshold==0,
                'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                'scope':'empirical cal-only engineering operating point; no FPR/security guarantee'}
            write_json(out/'operating_point.json',op)
            print(json.dumps(op),flush=True)
    hashes={p.name:sha(p) for p in out.iterdir() if p.suffix in ('.json','.npz','.png','.jpg')}
    write_json(out/'runtime.json',{'wall_seconds':time.perf_counter()-start,
        'generated_images':generated,'verified_versions':len(rows),'weights_downloaded_bytes':0,
        'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated(0),
        'max_cuda_reserved_bytes':torch.cuda.max_memory_reserved(0),'gpu_uuid':cfg['physical_gpu_uuid'],
        'file_hashes':hashes,'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print('Completed frozen engineering phase',flush=True)
if __name__=='__main__':main()
