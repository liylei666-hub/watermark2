"""One GPU 7 worker; each image gets a new CPU RNG and a persistent time reservation."""
import argparse, datetime, fcntl, gc, importlib.metadata, inspect, json, os, sys, time
from pathlib import Path
import numpy as np
from stage02.core import dump, sha256, HOST_GPUS, validate_gpu_config
from stage02.worker import driver_identity
from .protocol import digest, generation_jobs, read_jsonl, save_once, validate_image_record

def run(root, config, phase):
    visible=os.environ.get('CUDA_VISIBLE_DEVICES');validate_gpu_config(config,visible,'dinov2')
    out=root/'outputs/stage03'; gen=config['generator']; lockdir=root/'.stage02_locks';lockdir.mkdir(exist_ok=True)
    lock=(lockdir/'.gpu7.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    import subprocess
    inventory=subprocess.check_output(['nvidia-smi','-i','7','--query-gpu=index,uuid,memory.free','--format=csv,noheader,nounits'],text=True).strip()
    fields=[s.strip() for s in inventory.split(',')]
    if fields[1]!=visible or float(fields[2])<gen['minimum_free_mib']: raise RuntimeError('GPU 7 identity/free-memory gate failed')
    registry=json.loads((out/'generator_files.json').read_text())
    if registry['status']!='complete' or registry['revision']!=gen['revision'] or registry['model_id']!=gen['model_id']:raise ValueError('Generator registry mismatch')
    for f in registry['files']:
        if sha256(root/f['path'])!=f['sha256']:raise ValueError('Generator weight/file SHA mismatch')
    identity=driver_identity()
    if identity['uuid']!=visible:raise RuntimeError('Driver UUID mismatch')
    binding=dict(pid=os.getpid(),host_index=7,task='generate_'+phase,CUDA_VISIBLE_DEVICES=visible,driver=identity,host_inventory=inventory,device='cuda:0')
    dump(out/f'binding_generate_{phase}.json',binding)
    import torch
    from diffusers import StableDiffusionPipeline
    from PIL import Image
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.use_deterministic_algorithms(True)
    if torch.cuda.device_count()!=1:raise RuntimeError('Expected single visible GPU')
    torch.cuda.set_device(0);torch.cuda.set_per_process_memory_fraction(gen['memory_fraction'],0)
    budgetpath=out/'generation_budget.json'
    budget=json.loads(budgetpath.read_text()) if budgetpath.exists() else dict(limit_seconds=gen['gpu_budget_seconds'],charged_seconds=0.,attempts=[])
    def reserve(kind):
        amount=gen['per_image_wall_limit_seconds']
        if budget['charged_seconds']+amount>budget['limit_seconds']:raise RuntimeError('Generation budget has no complete attempt reservation remaining')
        attempt=dict(kind=kind,status='reserved',charged_seconds=amount)
        budget['charged_seconds']+=amount;budget['attempts'].append(attempt);dump(budgetpath,budget)
        return attempt,time.monotonic()
    def settle(attempt,start,status):
        elapsed=time.monotonic()-start
        budget['charged_seconds']+=elapsed-attempt['charged_seconds'];attempt.update(charged_seconds=elapsed,status=status)
        dump(budgetpath,budget)
    attempt,start=reserve('pipeline load')
    try:
        pipe=StableDiffusionPipeline.from_pretrained(str(root/registry['local_path']),torch_dtype=torch.float16,use_safetensors=True,local_files_only=True).to('cuda:0')
    finally: settle(attempt,start,'load ended')
    pipe.set_progress_bar_config(disable=True)
    if type(pipe.scheduler).__name__!=gen['scheduler']:raise ValueError('Unexpected scheduler')
    sig=inspect.signature(pipe.__call__)
    for param in ['generator','height','width','num_inference_steps','guidance_scale','negative_prompt','callback_on_step_end']:
        if param not in sig.parameters:raise RuntimeError('Unsupported pipeline parameter '+param)
    runtime=dict(versions={p:importlib.metadata.version(p) for p in ['torch','torchvision','diffusers','transformers','accelerate','safetensors','huggingface-hub','invisible-watermark','Pillow','numpy']},
                 pipeline=type(pipe).__name__,scheduler=type(pipe.scheduler).__name__,scheduler_config=dict(pipe.scheduler.config),
                 safety_checker=type(getattr(pipe,'safety_checker',None)).__name__,watermarker=type(getattr(pipe,'watermark',None)).__name__,
                 generator_device='cpu',dtype='float16',vae_force_upcast=getattr(pipe.vae.config,'force_upcast',None),attention='PyTorch SDPA default',deterministic_algorithms=True,tf32=False,device_uuid=visible)
    runtime_path=out/'generator_runtime.json'
    if runtime_path.exists():
        previous=json.loads(runtime_path.read_text())
        # Diffusers builds this bookkeeping list from a Python set. Its order has
        # no scheduler meaning; retain recorded order while checking every value.
        old_defaults=previous['scheduler_config'].get('_use_default_values',[])
        new_defaults=runtime['scheduler_config'].get('_use_default_values',[])
        if sorted(old_defaults)==sorted(new_defaults):runtime['scheduler_config']['_use_default_values']=old_defaults
    save_once(runtime_path,runtime)
    runtime_hash=digest(runtime);generation_hash=digest(dict(generator=gen,registry=registry,runtime=runtime))
    prompts=read_jsonl(root/'data/stage03/prompts.jsonl');jobs=generation_jobs(prompts,phase=='preflight')
    image_dir=root/('data/stage03/preflight' if phase=='preflight' else 'data/stage03/images');image_dir.mkdir(parents=True,exist_ok=True)
    records_dir=out/'generation_records';records_dir.mkdir(exist_ok=True)
    if phase=='main':
        gate=json.loads((out/'preflight.json').read_text())
        if gate['status']!='passed' or gate['generation_config_sha256']!=generation_hash:raise RuntimeError('Preflight/config gate failed')
        save_once(out/'frozen_run.json',dict(config=config,generation_config_sha256=generation_hash,runtime_sha256=runtime_hash,
                    prompts_sha256=sha256(root/'data/stage03/prompts.jsonl'),protocol_lock_sha256=sha256(out/'protocol_lock.json'),generator_files_sha256=sha256(out/'generator_files.json')))
    def generate(job, suffix=''):
        rp=records_dir/(job['id']+suffix+'.json');path=image_dir/(job['id']+suffix+'.png')
        failure_path=records_dir/(job['id']+suffix+'.failure.json')
        if rp.exists():
            rec=json.loads(rp.read_text());validate_image_record(rec,job,generation_hash)
            if not path.exists() or rec['sha256']!=sha256(path):raise RuntimeError('Existing generated image is missing/corrupt; investigate, do not overwrite')
            with Image.open(path) as im:
                if im.mode!='RGB' or im.size!=(1024,1024) or im.format!='PNG' or digest_pixels(im)!=rec['pixel_sha256']:raise ValueError('Saved image invariant failed')
            return rec
        # A valid record wins over a stale failure marker left by an interrupted run.
        if failure_path.exists(): return None
        if path.exists():raise RuntimeError('Orphan image retained for explicit technical recovery: '+str(path))
        attempt,start=reserve(job['id']+suffix)
        def callback(pipeline,step,timestep,kwargs):
            if time.monotonic()-start>gen['per_image_wall_limit_seconds']-10:raise TimeoutError('Per-image time limit')
            return kwargs
        try:
            rng=torch.Generator(device='cpu').manual_seed(job['seed'])
            with torch.inference_mode():
                output=pipe(prompt=job['prompt'],negative_prompt=gen['negative_prompt'],height=gen['height'],width=gen['width'],num_inference_steps=gen['num_inference_steps'],guidance_scale=gen['guidance_scale'],num_images_per_prompt=1,generator=rng,output_type='pil',callback_on_step_end=callback)
                if output.nsfw_content_detected and any(output.nsfw_content_detected):raise RuntimeError('Safety checker blocked this fixed-seed output; group incomplete')
                im=output.images[0].convert('RGB')
            torch.cuda.synchronize()
            tmp=path.with_suffix('.tmp');im.save(tmp,format='PNG',compress_level=6);tmp.replace(path)
            elapsed=time.monotonic()-start
            rec=dict(**job,path=str(path.relative_to(root)),sha256=sha256(path),pixel_sha256=digest_pixels(im),mode=im.mode,size=list(im.size),
                     generation_config_sha256=generation_hash,runtime_sha256=runtime_hash,seconds=elapsed,transform='identity')
            dump(rp,rec);settle(attempt,start,'complete')
            return rec
        except Exception as e:
            settle(attempt,start,'failed');dump(failure_path,dict(job=job,error=repr(e),phase=phase,config_sha256=generation_hash));return None
    records=[]
    for i,job in enumerate(jobs):
        record=generate(job)
        if record is not None: records.append(record)
        else: print(phase,i+1,'/',len(jobs),job['id'],'INCOMPLETE_FIXED_SEED',flush=True)
        if i==0:
            rows=subprocess.check_output(['nvidia-smi','-i','5,7','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader'],text=True).splitlines()
            mine=[r for r in rows if r.split(',')[1].strip()==str(os.getpid())]
            if not mine or any(r.split(',')[0].strip()!=visible for r in mine):raise RuntimeError('Actual generation PID binding failed')
            binding['pid_rows']=mine;dump(out/f'binding_generate_{phase}.json',binding)
    for pid in sorted({r['prompt_id'] for r in records}):
        group=[r for r in records if r['prompt_id']==pid]
        if len(group)==4 and len({r['pixel_sha256'] for r in group})!=4:raise ValueError('Distinct seeds produced duplicate pixels')
    if phase=='preflight':
        repeated=generate(jobs[0],'_repeat');a=np.asarray(Image.open(root/records[0]['path'])).astype(np.int16);b=np.asarray(Image.open(root/repeated['path'])).astype(np.int16)
        difference=np.abs(a-b); repeat=dict(pixel_equal=bool(np.array_equal(a,b)),max_abs=int(difference.max()),mean_abs=float(difference.mean()))
        # Verify RGB opening and all baseline input transforms, without scores or model selection.
        from torchvision import transforms as T
        from stage02.worker import PREPROCESS
        for r in records:
            with Image.open(root/r['path']) as im:
                for model,pp in PREPROCESS.items():
                    tf=T.Compose([T.Resize(224,interpolation=T.InterpolationMode.BICUBIC),T.CenterCrop(224),T.ToTensor(),T.Normalize(pp['mean'],pp['std'])]) if model=='clip' else T.Compose([T.Resize(pp['size'],interpolation=T.InterpolationMode.BILINEAR if model=='sscd' else T.InterpolationMode.BICUBIC),T.ToTensor(),T.Normalize(pp['mean'],pp['std'])])
                    x=tf(im)
                    if not torch.isfinite(x).all():raise RuntimeError('Baseline preprocessing failed')
        forecast=float(np.mean([r['seconds'] for r in records]))*480*gen['forecast_safety_factor']
        passed=repeat['pixel_equal'] and budget['charged_seconds']+forecast<budget['limit_seconds']
        dump(out/'preflight.json',dict(status='passed' if passed else 'stopped',images=16,repeat=repeat,baseline_preprocessing='all three passed',
              mean_seconds=float(np.mean([r['seconds'] for r in records])),main_forecast_seconds_with_margin=forecast,generation_config_sha256=generation_hash))
        if not passed:raise RuntimeError('Repeatability or budget forecast gate failed')
    binding.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    dump(out/f'binding_generate_{phase}.json',binding)
    del pipe;gc.collect();torch.cuda.empty_cache()

def digest_pixels(im):
    import hashlib
    return hashlib.sha256(np.asarray(im).tobytes()+str(im.size).encode()).hexdigest()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--phase',choices=['preflight','main'],required=True);a=p.parse_args()
    run(Path(__file__).resolve().parents[1],json.loads(Path(a.config).read_text()),a.phase)
