"""CPU cost and byte-equivalence audit of the native Imprint timing run."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU visibility must be empty')
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/15_imprint_timing_r2_20261017T205635Z'
CONTROL=ROOT/'runs/10_imprint_shadow_20261017T190952Z'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def analyze():
    timing=load(RUN/'timing.json');execution=load(RUN/'execution.json')
    assert execution['exit_code']==0 and execution['completed']
    assert 'COMPLETED_IMPRINT_TIMING' in (RUN/'stdout.log').read_text()
    assert load(RUN/'initial_control.json')==load(CONTROL/'initial_control.json')
    assert load(RUN/'trajectory_control.json')['final_latent_bitwise_equal']
    equal=[]
    for leaf in ['z.npy','internal_noise.npy','float_z.npy','png_z.npy','float_noise.npy','png_noise.npy','candidate.png','metrics.json']:
        assert (RUN/'checkpoint_10'/leaf).read_bytes()==(CONTROL/'checkpoint_10'/leaf).read_bytes(),leaf
        equal.append(leaf)
    for key in ['model_loading_seconds','reference_inversion_and_cover_encoding_seconds','ten_native_updates_seconds']:
        assert math.isfinite(timing[key]) and timing[key]>0
    vae=load(ROOT/'reports/14_vae_timing/analysis.json')
    budget=timing['reference_inversion_and_cover_encoding_seconds']+timing['ten_native_updates_seconds']
    # Resource-only calibration rule fixed before reading this run's measured costs.
    proposed=math.floor(100*budget/vae['core_seconds'])
    return dict(status='passed',equal_files=equal,timing=timing,
        imprint_reference_plus_10_updates_seconds=budget,
        jain_100_updates_with_reference_seconds=vae['core_seconds'],
        proposed_jain_updates_for_pilot=proposed,
        calibration_rule='floor(100 * Imprint(reference preparation + 10 updates) / Jain(reference encoding + 100 updates))',
        calibration_scope='Single development input and timing; approximate resource calibration, not guaranteed equal runtime. Actual pair costs must be reported; no score-based adjustment.',
        model_process_seconds=execution['elapsed_seconds'],cumulative_model_processes=21,
        cumulative_model_process_seconds=vae['cumulative_model_process_seconds']+execution['elapsed_seconds'],
        target_calls=0,full_defense_acceptance=None,
        analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


if __name__=='__main__':
    print(json.dumps(analyze(),indent=2,allow_nan=False))
