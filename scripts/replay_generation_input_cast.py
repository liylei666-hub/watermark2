"""Two-source supplied-noise dtype replay using the pinned helper; zero model calls."""
import argparse,json,os,time
from pathlib import Path
from sd15_clip_smoke import guard_gpu,sha,write_json
from runtime_provenance import array_binding

def main():
    ap=argparse.ArgumentParser()
    for f in ('prepare-run','csi-code','output'):ap.add_argument('--'+f,required=True)
    a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True);assert not (out/'frozen.json').exists()
    cfg={'physical_gpu':7,'physical_gpu_uuid':'GPU-9644fb82-cb6f-7311-8017-eaee41409bb7'}
    preflight=guard_gpu(cfg)
    import numpy as np,torch,sys
    from types import SimpleNamespace
    assert torch.cuda.device_count()==1 and torch.cuda.get_device_name(0)=='NVIDIA GeForce RTX 3090'
    sys.path.insert(0,a.csi_code)
    from csi.backends.sd import StableDiffusionBackend
    backend=object.__new__(StableDiffusionBackend);backend.device='cuda'
    backend.pipe=SimpleNamespace(unet=SimpleNamespace(dtype=torch.float16))
    source=Path(a.csi_code)/'csi/backends/sd.py'
    assert sha(source)=='bc88888ebf60b03dab9d8e77948812b36c38696251a33540f5266245120c75c2'
    write_json(out/'frozen.json',{'preflight':preflight,'pid':os.getpid(),'torch':torch.__version__,'script_sha256':sha(__file__),
        'csi_backend_sha256':sha(source),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'scope':'forward replay of actual pinned _to_torch conversion and scheduler sigma1; no initial UNet hook in original generation run'})
    start=time.perf_counter();rows=[]
    for sid in ('c04','c02'):
        path=Path(a.prepare_run)/(sid+'_registration.npz');z=np.load(path,allow_pickle=False)['registered_z']
        supplied=backend._to_torch(z);scaled=supplied*1.
        arrays={'supplied_noise_actual_runtime_fp16':supplied.cpu().numpy().copy(),'scheduler_input_sigma1_fp16':scaled.cpu().numpy().copy()}
        assert np.array_equal(arrays['supplied_noise_actual_runtime_fp16'],arrays['scheduler_input_sigma1_fp16'])
        np.savez_compressed(out/(sid+'_input.npz'),**arrays)
        rows.append({'source':sid,'registration_file_sha256':sha(path),'arrays_file':sid+'_input.npz',
            'array_bindings':{k:array_binding(v) for k,v in arrays.items()},
            'direct_numpy_cast_equal':bool(np.array_equal(z.astype(np.float16),arrays['supplied_noise_actual_runtime_fp16'])),
            'float32_intermediate_numpy_cast_equal':bool(np.array_equal(z.astype(np.float32).astype(np.float16),arrays['supplied_noise_actual_runtime_fp16']))})
    write_json(out/'results.json',rows)
    hashes={p.name:sha(p) for p in out.iterdir() if p.suffix in ('.npz','.json')}
    write_json(out/'runtime.json',{'wall_seconds':time.perf_counter()-start,'inversions':0,'generated_images':0,'vae_encodes':0,
        'new_model_download_bytes':0,'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated(0),
        'max_cuda_reserved_bytes':torch.cuda.max_memory_reserved(0),'gpu_uuid':cfg['physical_gpu_uuid'],'file_hashes':hashes,
        'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print(json.dumps(rows),flush=True)

if __name__=='__main__':main()
