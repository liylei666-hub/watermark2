"""CPU reconstruction of supplied generation-noise dtype; separate from native float64 oracle."""
import argparse,ast,csv,json,os
from pathlib import Path
import numpy as np
from runtime_provenance import array_binding,file_sha

def rmse(a,b):return float(np.sqrt(np.mean((a.astype(float)-b.astype(float))**2)))
def distances(a,b):
    d=a.astype(float)-b.astype(float)
    return np.array([np.linalg.norm(d[0,:,y:y+2,x:x+2].ravel()) for y in range(0,64,2) for x in range(0,64,2)])

def main():
    ap=argparse.ArgumentParser()
    for f in ('run','trace-run','csi-code'):ap.add_argument('--'+f,required=True)
    args=ap.parse_args();root=Path(args.run);trace=Path(args.trace_run)
    backend=Path(args.csi_code)/'csi/backends/sd.py'
    text=backend.read_text(encoding='utf8')
    assert 'device=self.device, dtype=self.pipe.unet.dtype' in text
    assert 'latents=backend._to_torch(registered)' in (root/'inputs/limited_codec_bypass.py').read_text()
    snippet=root/'inputs/diffusers_prepare_latents.txt'
    raw=snippet.read_bytes()
    source=raw.decode('utf16') if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else raw.decode('utf-8-sig')
    assert 'latents = latents.to(device)' in source and 'latents = latents * self.scheduler.init_noise_sigma' in source
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    folder=root/'input_cast'
    frozen=json.loads((folder/'frozen.json').read_text())
    runtime=json.loads((folder/'runtime.json').read_text())
    assert file_sha(root/'inputs/replay_generation_input_cast.py')==frozen['script_sha256']
    assert file_sha(backend)==frozen['csi_backend_sha256']
    assert runtime['inversions']==runtime['generated_images']==runtime['vae_encodes']==runtime['new_model_download_bytes']==0
    assert json.loads((folder/'exit_status.json').read_text())['exit_code']==0
    for name,h in runtime['file_hashes'].items():assert file_sha(folder/name)==h
    castrows={r['source']:r for r in json.loads((folder/'results.json').read_text())}
    rows=[];arrays={}
    for sid in ('c04','c02'):
        paired=np.load(root/'replay'/(sid+'_replay.npz'),allow_pickle=False)
        old=np.load(trace/(sid+'_original.npz'),allow_pickle=False)
        bypass=np.load(root/'bypass'/(sid+'_bypass.npz'),allow_pickle=False)
        assert paired['terminal_generation_latent'].dtype==np.float16
        z=paired['registered_z']
        cast=np.load(folder/(sid+'_input.npz'),allow_pickle=False)
        castrow=castrows[sid]
        for k in cast.files:assert array_binding(cast[k])==castrow['array_bindings'][k]
        assert castrow['registration_file_sha256']==json.loads((root/'replay/frozen.json').read_text())['source_bindings'][sid+'_registration.npz']
        ref=cast['scheduler_input_sigma1_fp16']
        assert np.array_equal(ref,cast['supplied_noise_actual_runtime_fp16'])
        direct=z.astype(np.float16)
        cpu=torch.from_numpy(z).to(torch.float16).numpy()
        assert np.array_equal(ref,z.astype(np.float32).astype(np.float16))
        # The recorded pipeline explicitly supplies fp16 latents and uses DDIM init sigma1.
        arrays[sid+'_runtime_replayed_supplied_noise_fp16']=ref
        for variant,recon in [('image_roundtrip',old['recon']),('paired_bypass',bypass['recon'])]:
            actual=distances(recon,ref);canonical=distances(recon,z)
            arrays[sid+'_'+variant+'_l2_to_fp16_input']=actual
            rows.append({'source':sid,'variant':variant,'matches_to_canonical_float64':int((canonical<=2).sum()),
                'matches_to_runtime_fp16_input':int((actual<=2).sum()),
                'rmse_to_runtime_fp16_input':rmse(recon,ref),
                'registered_dtype_conversion_rmse':rmse(z,ref),
                'direct_numpy_cast_different_coordinates':int(np.count_nonzero(direct!=ref)),
                'cpu_torch_cast_exact_runtime':bool(np.array_equal(cpu,ref)),
                'max_l2_reference_dtype_delta':float(np.max(np.abs(actual-canonical))),
                'median_l2_to_runtime_fp16_input':float(np.median(actual))})
    np.savez_compressed(root/'generation_input_controls.npz',**arrays)
    result={'status':'passed','rows':rows,'init_noise_sigma':1.,
        'reference_binding':{k:array_binding(v) for k,v in arrays.items()},
        'evidence':{'backend_sha256':file_sha(backend),'pipeline_prepare_latents_snippet_sha256':file_sha(snippet),'input_cast_frozen_sha256':file_sha(folder/'frozen.json')},
        'scope':'generation input reconstructed by actual pinned _to_torch CUDA replay in original Torch2.3.1 runtime and sigma1; no initial-UNet input hook was saved during original generation. Direct NumPy64->half differs for some coordinates; runtime replay is authoritative.',
        'interpretation':'keep native oracle against canonical float64 registered_z unchanged; report runtime-replayed supplied fp16-noise reference separately'}
    (root/'generation_input_audit.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    with (root/'generation_input_summary.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
