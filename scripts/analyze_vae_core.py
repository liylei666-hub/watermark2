"""CPU readback of the frozen real-VAE equivalence check; no model imports."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU analysis requires CUDA_VISIBLE_DEVICES=""')
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'runs/13_vae_core_20261017T202854Z'


def analyze():
    stored = json.loads((RUN/'summary.json').read_text(encoding='utf-8'))
    cover = np.load(RUN/'cover_input.npy', allow_pickle=False)
    rows = []
    for steps in [1,2,3]:
        arrays, pixels = [], []
        for mode in ['upstream', 'frozen_parameters']:
            stem = mode+'_'+str(steps)
            a = np.load(RUN/(stem+'.npy'), allow_pickle=False)
            delta = np.load(RUN/(stem+'_delta.npy'), allow_pickle=False)
            assert a.dtype == np.float32 and a.shape == (1,3,512,512)
            assert np.isfinite(a).all() and np.array_equal(cover-a, delta)
            with Image.open(RUN/(stem+'.png')) as im:
                assert im.mode == 'RGB' and im.size == (512,512)
                p = np.array(im)
            serialized = (np.clip(a/np.float32(2)+np.float32(.5),0,1).squeeze().transpose(1,2,0)*np.float32(255)).astype(np.uint8)
            assert np.array_equal(serialized,p)
            arrays.append(a);pixels.append(p)
        d = arrays[0].astype(np.float64)-arrays[1].astype(np.float64)
        pd = pixels[0].astype(np.int16)-pixels[1].astype(np.int16)
        png_equal = (RUN/('upstream_'+str(steps)+'.png')).read_bytes() == (RUN/('frozen_parameters_'+str(steps)+'.png')).read_bytes()
        row = dict(steps=steps,bitwise_equal=bool(np.array_equal(*arrays)),
            max_abs_difference=float(np.abs(d).max()),rms_difference=float(np.sqrt(np.mean(d*d))),
            different_float_coordinates=int(np.count_nonzero(d)),total_float_coordinates=d.size,
            png_byte_equal=png_equal,different_png_channels=int(np.count_nonzero(pd)),
            different_png_pixels=int(np.count_nonzero(np.any(pd != 0,axis=2))),
            total_png_pixels=512*512,max_png_channel_difference=int(np.abs(pd).max()))
        recorded=stored['comparisons'][steps-1]
        assert all(row[k]==recorded[k] for k in recorded)
        rows.append(row)
    exe=json.loads((RUN/'execution.json').read_text(encoding='utf-8'))
    assert exe['exit_code']==1 and not exe['timed_out'] and not exe['completed']
    prior=json.loads((ROOT/'reports/13_vae_core/cpu_preparation.json').read_text(encoding='utf-8'))
    return dict(status='exact_equivalence_failed_preserved',comparisons=rows,
        serialization_checks_passed=6,delta_checks_passed=6,model_process_seconds=exe['elapsed_seconds'],
        cumulative_model_process_seconds=prior['cumulative_seconds']+exe['elapsed_seconds'],
        cumulative_model_processes=18,target_calls=0,causal_backend_mechanism=None,
        original_same_flag_repeatability=None,full_defense_acceptance=None,
        inference='Observed failure of the frozen-parameter equivalence gate in one development pair; no detector or performance conclusion',
        analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


if __name__=='__main__':
    print(json.dumps(analyze(),indent=2,allow_nan=False))
