"""One isolated GPU per process. Feature inputs contain no evaluation labels."""
import argparse, ctypes, datetime, fcntl, gc, json, os, subprocess, sys, time, traceback, uuid
from pathlib import Path
import numpy as np
from .core import HOST_GPUS, cache_key, dump, normalize, sha256, validate_gpu_config

PREPROCESS={
 'clip':dict(size=224,resize='shorter edge bicubic',crop='center 224x224',rgb=True,mean=[.48145466,.4578275,.40821073],std=[.26862954,.26130258,.27577711]),
 'sscd':dict(size=[320,320],resize='Pillow bilinear full frame (author skew_320)',crop=None,rgb=True,mean=[.485,.456,.406],std=[.229,.224,.225]),
 'dinov2':dict(size=[224,224],resize='Pillow bicubic full frame',crop=None,rgb=True,mean=[.485,.456,.406],std=[.229,.224,.225])}

def driver_identity():
    lib=ctypes.CDLL('libcuda.so.1')
    def call(name,*args):
        code=getattr(lib,name)(*args)
        if code:raise RuntimeError(f'{name} returned {code}')
    call('cuInit',0);count=ctypes.c_int();call('cuDeviceGetCount',ctypes.byref(count))
    if count.value!=1:raise RuntimeError('CUDA driver sees more/less than one GPU')
    dev=ctypes.c_int();call('cuDeviceGet',ctypes.byref(dev),0)
    buf=(ctypes.c_ubyte*16)();call('cuDeviceGetUuid',ctypes.byref(buf),dev)
    bus=ctypes.create_string_buffer(32);call('cuDeviceGetPCIBusId',bus,32,dev)
    return {'uuid':'GPU-'+str(uuid.UUID(bytes=bytes(buf))),'pci_bus_id':bus.value.decode(),'count':count.value}

def worker(root,config,task,stage='stage02'):
    if stage not in {'stage02','stage03'}:raise ValueError('unsupported artifact stage')
    visible=os.environ.get('CUDA_VISIBLE_DEVICES');idx=validate_gpu_config(config,visible,task)
    out=root/f'outputs/{stage}';out.mkdir(parents=True,exist_ok=True)
    lockdir=root/'.stage02_locks';lockdir.mkdir(exist_ok=True)
    lock=(lockdir/f'.gpu{idx}.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    inventory=subprocess.check_output(['nvidia-smi','-i',str(idx),'--query-gpu=index,uuid,pci.bus_id,name','--format=csv,noheader'],text=True).strip()
    if inventory.split(',')[1].strip()!=visible:raise RuntimeError('host inventory changed')
    identity=driver_identity()
    if identity['uuid']!=visible:raise RuntimeError('CUDA device identity differs from configured UUID')
    binding=dict(pid=os.getpid(),host_index=idx,task=task,CUDA_VISIBLE_DEVICES=visible,driver=identity,host_inventory=inventory,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    dump(out/f'binding_{task}.json',binding)
    import torch
    import torchvision
    from torchvision import transforms as T
    from PIL import Image
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    torch.manual_seed(config['seed']);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.use_deterministic_algorithms(True)
    if torch.cuda.device_count()!=1:raise RuntimeError('PyTorch visible GPU count mismatch')
    torch.cuda.set_device(0);torch.cuda.set_per_process_memory_fraction(.18,0)
    binding.update(torch_device='cuda:0',torch_name=torch.cuda.get_device_name(0),torch_visible_count=1,torch_version=torch.__version__,torchvision_version=torchvision.__version__)
    dump(out/f'binding_{task}.json',binding)
    registry=json.loads((root/'artifacts/models.json').read_text())
    inputs=json.loads((root/f'data/{stage}/image_inputs.json').read_text())
    results={}
    for name in (['clip','sscd'] if task=='clip_sscd' else ['dinov2']):
        t0=time.perf_counter();record=dict(status='incomplete',pid=os.getpid(),gpu_uuid=visible,device='cuda:0',batch_size=1,preprocess=PREPROCESS[name])
        try:
            meta=registry[name];weight=root/meta['path']
            if sha256(weight)!=meta['sha256']:raise ValueError('weight SHA mismatch')
            torch.cuda.reset_peak_memory_stats(0)
            if name=='clip':
                sys.path.insert(0,str(root/'third_party/clip'))
                import clip
                model,preprocess=clip.load(str(weight),device='cpu',jit=False)
                model=model.float().to('cuda:0')
            elif name=='sscd':
                model=torch.jit.load(str(weight),map_location='cpu').eval().to('cuda:0')
                preprocess=T.Compose([T.Resize((320,320),interpolation=T.InterpolationMode.BILINEAR),T.ToTensor(),T.Normalize(PREPROCESS[name]['mean'],PREPROCESS[name]['std'])])
            else:
                sys.path.insert(0,str(root/'third_party/dinov2'))
                from dinov2.hub.backbones import dinov2_vits14
                model=dinov2_vits14(pretrained=False)
                state=torch.load(weight,map_location='cpu',weights_only=True)
                model.load_state_dict(state,strict=True);del state
                model=model.eval().to('cuda:0')
                preprocess=T.Compose([T.Resize((224,224),interpolation=T.InterpolationMode.BICUBIC),T.ToTensor(),T.Normalize(PREPROCESS[name]['mean'],PREPROCESS[name]['std'])])
            model.eval()
            for p in model.parameters():p.requires_grad_(False)
            expected=(256,384) if name=='dinov2' else (512,)
            record.update(model=meta,feature_shape=expected,feature_dtype='float32',preprocess_runtime=repr(preprocess),load_seconds=time.perf_counter()-t0)
            def extract(path):
                im=Image.open(path).convert('RGB');x=preprocess(im).unsqueeze(0).to('cuda:0')
                with torch.inference_mode():
                    y=model.encode_image(x)[0] if name=='clip' else model(x)[0] if name=='sscd' else model.forward_features(x)['x_norm_patchtokens'][0]
                y=normalize(y.float().cpu().numpy())
                if y.shape!=expected or not np.isfinite(y).all():raise ValueError('feature shape/finiteness check failed')
                if not np.allclose(np.linalg.norm(y,axis=-1),1,atol=1e-5):raise ValueError('normalization check failed')
                return y
            first=root/inputs[0]['path'];a=extract(first);b=extract(first)
            repeat_error=float(np.max(np.abs(a-b)))
            if repeat_error>1e-5:raise ValueError('repeat extraction mismatch')
            self_error=float(np.max(np.abs(np.sum(a*a,axis=-1)-1)))
            if self_error>1e-5:raise ValueError('self similarity mismatch')
            process_snapshot=subprocess.check_output(['nvidia-smi','-i','5,7','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader'],text=True)
            pid_rows=[r for r in process_snapshot.splitlines() if len(r.split(','))>=2 and r.split(',')[1].strip()==str(os.getpid())]
            if not pid_rows or any(r.split(',')[0].strip()!=visible for r in pid_rows):raise RuntimeError('nvidia-smi PID GPU binding not confirmed')
            record['binding_evidence']=pid_rows;record['repeat_max_abs']=repeat_error;record['self_max_error']=self_error
            index={};elapsed=0;hits=0;infer=0
            for n,im in enumerate(inputs):
                path=root/im['path'];actual=sha256(path)
                if actual!=im['sha256']:raise ValueError('input image hash mismatch')
                key=cache_key(actual,name,meta['sha256'],meta['code_commit'],PREPROCESS[name]);dst=root/f'cache/{stage}'/name/(key+'.npy');dst.parent.mkdir(parents=True,exist_ok=True)
                start=time.perf_counter()
                if dst.exists() and not config.get('refresh_features',False):
                    feat=np.load(dst,allow_pickle=False);hits+=1
                    if feat.shape!=expected or not np.isfinite(feat).all() or not np.allclose(np.linalg.norm(feat,axis=-1),1,atol=1e-5):raise ValueError('invalid cached feature')
                else:
                    feat=extract(path);infer+=1
                    tmp=dst.with_suffix(f'.{os.getpid()}.tmp')
                    with tmp.open('wb') as f:np.save(f,feat,allow_pickle=False)
                    tmp.replace(dst)
                elapsed+=time.perf_counter()-start
                index[im['id']]=dict(path=str(dst.relative_to(root)),key=key,bytes=int(feat.nbytes),file_bytes=dst.stat().st_size)
                if n%40==0:print(name,n+1,'/',len(inputs),flush=True)
            dump(out/f'features_{name}.json',index)
            record.update(status='complete',images=len(inputs),inferred= infer,cache_hits=hits,extract_cache_seconds=elapsed,peak_allocated_bytes=torch.cuda.max_memory_allocated(0),peak_reserved_bytes=torch.cuda.max_memory_reserved(0),reference_array_bytes=int(a.nbytes),reference_npy_bytes=next(iter(index.values()))['file_bytes'],total_seconds=time.perf_counter()-t0)
            # No tensors from one model survive into the next GPU 5 model.
            del model,preprocess,a,b,extract;gc.collect();torch.cuda.empty_cache()
        except Exception as e:
            record.update(error=f'{type(e).__name__}: {e}',traceback=traceback.format_exc())
            print(record['traceback'],flush=True)
            if 'model' in locals():del model
            gc.collect();torch.cuda.empty_cache()
        results[name]=record;dump(out/f'worker_{task}.json',results)
    binding['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();dump(out/f'binding_{task}.json',binding)
    return 0 if all(v['status']=='complete' for v in results.values()) else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--task',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    try:sys.exit(worker(root,json.loads(Path(a.config).read_text()),a.task))
    except Exception as e:
        dump(root/f'outputs/stage02/fatal_{a.task}.json',dict(status='incomplete',error=str(e),traceback=traceback.format_exc(),pid=os.getpid()))
        raise
