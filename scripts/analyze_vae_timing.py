"""CPU-only file and pixel readback for the fixed 100-update timing endpoint."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU visibility must be empty')
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/14_vae_timing_20261017T203633Z'


def analyze():
    x=np.load(RUN/'native_100.npy',allow_pickle=False)
    c=np.load(RUN/'cover_input.npy',allow_pickle=False)
    d=np.load(RUN/'native_100_delta.npy',allow_pickle=False)
    assert x.dtype==np.float32 and x.shape==(1,3,512,512)
    assert np.isfinite(x).all() and np.array_equal(c-x,d)
    with Image.open(RUN/'native_100.png') as im:p=np.array(im.convert('RGB'))
    with Image.open(RUN/'cover_rgb.png') as im:cover=np.array(im.convert('RGB'))
    serial=(np.clip(x/np.float32(2)+np.float32(.5),0,1).squeeze().transpose(1,2,0)*np.float32(255)).astype(np.uint8)
    assert np.array_equal(serial,p)
    mse=float(np.mean(((p.astype(np.float64)-cover.astype(np.float64))/255)**2))
    fl_mse=float(np.mean((x.astype(np.float64)-c.astype(np.float64))**2))
    s=json.loads((RUN/'summary.json').read_text(encoding='utf-8'))
    assert abs(fl_mse-s['pixel_mse_minus1_to1']) < 1e-9
    e=json.loads((RUN/'execution.json').read_text(encoding='utf-8'))
    assert e['exit_code']==0 and e['completed']
    assert 'COMPLETED_VAE_TIMING' in (RUN/'stdout.log').read_text()
    assert hashlib.sha256((RUN/'native_100.png').read_bytes()).hexdigest()==s['timings']['native_100']['png_sha256']
    prior=json.loads((ROOT/'reports/13_vae_core/replay_verification.json').read_text(encoding='utf-8'))
    return dict(status='passed',fixed_updates=100,finite_output=True,serialized_pixels_verified=True,
        png_to_cover_mse_0_1=mse,png_to_cover_psnr_db=10*math.log10(1/mse),
        png_to_cover_linf_8bit=int(np.abs(p.astype(np.int16)-cover.astype(np.int16)).max()),
        floating_pixel_mse_minus1_to1=fl_mse,core_seconds=s['timings']['native_100']['seconds'],
        core_timing_includes_reference_encoding=True,peak_allocated_bytes=s['timings']['native_100']['peak_allocated_bytes'],
        model_process_seconds=e['elapsed_seconds'],cumulative_model_processes=20,
        cumulative_model_process_seconds=prior['cumulative_model_process_seconds']+e['elapsed_seconds'],
        proxy_initial_latent_mse_recorded=s['proxy_initial_latent_mse'],proxy_final_latent_mse_recorded=s['proxy_final_latent_mse'],
        proxy_latent_metric_cpu_recomputed=False,target_calls=0,full_defense_acceptance=None,
        analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


if __name__=='__main__':
    print(json.dumps(analyze(),indent=2,allow_nan=False))
