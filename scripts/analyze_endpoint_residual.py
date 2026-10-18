"""CPU readback of fixed endpoint arrays, bindings, gates and measured residuals."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU readback requires CUDA_VISIBLE_DEVICES=""')
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent / 'endpoint_residual'))
import common as c


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def analyze(root, run):
    root, run = Path(root).resolve(), Path(run).resolve()
    protocol = root / 'protocols/18_endpoint_residual.json'
    cfg = read(protocol)
    if c.sha(protocol) != protocol.with_suffix('.sha256').read_text().strip():
        raise ValueError('Protocol changed')
    inputs = c.validate_inputs(cfg, root)
    execution, summary = read(run/'execution.json'), read(run/'summary.json')
    if execution['exit_code'] != 0 or not execution['completed'] or execution['timed_out']:
        raise ValueError('Execution unsuccessful')
    if 'COMPLETED_ENDPOINT_RESIDUAL' not in (run/'stdout.log').read_text():
        raise ValueError('Completion marker missing')
    if summary['protocol_sha256'] != c.sha(protocol) or not summary['completed']:
        raise ValueError('Summary binding failed')
    expected = {'reference_z','cover_z','imprint_png_z','jain_png_z','reference_inverse',
        'cover_inverse','imprint_png_inverse','jain_png_inverse','imprint_native_z',
        'imprint_native_inverse','imprint_pipeline_control','imprint_float_z',
        'imprint_float_inverse','initial_png_z','initial_png_inverse','jain_float_z'}
    if [row['task_id'] for row in summary['rows']] != [1,2,3]:
        raise ValueError('Task coverage changed')
    rows = []
    for task, saved in zip([1,2,3],summary['rows']):
        folder = run/str(task)
        if saved != read(folder/'metrics.json') or set(saved['arrays']) != expected:
            raise ValueError('Array inventory or summary mismatch')
        arrays = {}
        for name, rec in saved['arrays'].items():
            if rec['path'] != name+'.npy': raise ValueError('Array path mismatch')
            p = folder/rec['path']
            if c.sha(p) != rec['sha256']: raise ValueError('Array changed')
            arr = np.load(p,allow_pickle=False)
            if arr.dtype != np.float32 or arr.shape != (1,4,64,64) or not np.isfinite(arr).all():
                raise ValueError('Invalid latent')
            arrays[name] = arr
        if not np.array_equal(arrays['reference_inverse'], np.load(inputs[f'{task}/reference_inverse'],allow_pickle=False)):
            raise ValueError('Saved proxy reference differs')
        if not np.array_equal(arrays['imprint_native_z'], np.load(inputs[f'{task}/imprint_z'],allow_pickle=False)):
            raise ValueError('Native endpoint changed')
        if not np.allclose(arrays['imprint_native_inverse'],arrays['imprint_pipeline_control'],atol=cfg['atol'],rtol=cfg['rtol']):
            raise ValueError('Inversion equivalence failed')
        if not read(folder/'reference_control.json')['bitwise_equal'] or not read(folder/'decode_control.json')['png_pixels_bitwise_equal']:
            raise ValueError('Reference/decode gate failed')
        metrics = c.summarize(arrays)
        if metrics != saved['metrics']: raise ValueError('Float64 readback mismatch')
        # Jain also penalizes image displacement; residual alone is not convergence.
        with Image.open(inputs[f'{task}/cover']) as image:
            cover = np.asarray(image).astype(np.float32).transpose(2,0,1)[None] / 255
            cover = cover * 2 - 1
        final = np.load(inputs[f'{task}/jain_float'],allow_pickle=False)
        if final.shape != cover.shape or not np.isfinite(final).all():
            raise ValueError('Invalid floating image')
        pixel_mse = float(np.mean((final.astype(np.float64)-cover.astype(np.float64))**2))
        sf = summary['scaling_factor']
        initial_term = metrics['vae_mse']['cover'] / sf**4
        final_term = metrics['vae_mse']['jain_float'] / sf**4
        penalty = 10000. * pixel_mse
        total = final_term + penalty
        objective = dict(arithmetic='Float64 decomposition using scaled posterior mean; not a bitwise replay of FP32 upstream loss',
            initial_representation_term=initial_term,final_representation_term=final_term,
            pixel_penalty=penalty,final_sum=total,relative_reduction=c.relative_drop(initial_term,total),
            convergence_or_stationarity_established=False)
        rows.append(dict(task_id=task,metrics=metrics,jain_objective_decomposition=objective))
    return dict(status='verified',rows=rows,arrays_checked=48,input_files_checked=21,
        reference_replays_bitwise_equal=3,decode_pixel_controls_passed=3,inversion_equivalence_passed=3,
        source_run=str(run.relative_to(root)),protocol_sha256=c.sha(protocol),execution=execution,
        data_role='development_exploratory_posthoc',target_scores_used=False,
        new_candidate_images=0,optimization_updates=0,full_defense_acceptance=None)


if __name__ == '__main__':
    c.write(sys.argv[3],analyze(sys.argv[1],sys.argv[2]))
