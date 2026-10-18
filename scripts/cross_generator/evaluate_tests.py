"""Evaluator-only CPU diagnostics, after all test predictions have been sealed."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise RuntimeError('CPU evaluation requires empty visibility')
from pathlib import Path
import sys
import time
import numpy as np
import io_contract as c
from phase_contract import verify_predictions


def metrics(baseline, corrected, original):
    arrays = [np.asarray(x, dtype=np.float64) for x in (baseline,corrected,original)]
    if any(a.shape != c.SHAPE or not np.isfinite(a).all() for a in arrays):
        raise ValueError('Invalid metric input')
    a,b,z = arrays
    return dict(baseline_mse=float(np.mean((a-z)**2)),corrected_mse=float(np.mean((b-z)**2)),
                baseline_bit_error=float(np.mean((a>=0)!=(z>=0))),
                corrected_bit_error=float(np.mean((b>=0)!=(z>=0))))


def quantizer_gate(value):
    from scipy.stats import norm
    bits = np.minimum((2*norm.cdf(value.astype(np.float64))).astype(np.int32),1)
    if not np.array_equal(bits, value>=0):
        raise ValueError('CDF quantizer and sign differ; interpretation stopped')


def main(folder, seal_sha, private_folder, output):
    folder = Path(folder); output = Path(output)
    verify_predictions(folder, seal_sha)
    # Target labels and private state are first read below this verification gate.
    from gs_batch import private_module, r
    sys.path.insert(0, str(r.UPSTREAM))
    import torch
    private = private_module(); rows = []; start = time.perf_counter()
    fingerprints = []
    for split in ('proxy_test','target_test'):
        prefix = 'proxy' if split == 'proxy_test' else 'target'
        for i,sid in enumerate(c.SPLITS[split]):
            source = folder / (prefix+'_generate_'+str(i//4)) / sid
            record = c.read(source / 'record.json')
            if record['task']['sample_id'] != sid or c.array_record(source/'original_noise.npy') != record['original_noise']:
                raise ValueError('Original-noise association changed')
            original = np.load(source/'original_noise.npy',allow_pickle=False)
            pred = folder / (split+'_predictions')
            arrays = {'original':original}
            for suffix,dtype in [('baseline','float32'),('corrected','float64')]:
                path=pred/(sid+'_'+suffix+'.npy');c.array_record(path,dtype)
                arrays[suffix]=np.load(path,allow_pickle=False)
            for value in arrays.values():quantizer_gate(value)
            raw = private.load(Path(private_folder),sid,record['encryption_fingerprints'])
            fingerprints.append(record['encryption_fingerprints'])
            wm = private.provider(raw,'cpu')
            scores = {name:float(wm.get_accuracies(torch.from_numpy(value.copy()))['bit_accuracies'][0])
                      for name,value in arrays.items()}
            if scores['original'] != 1.0:raise ValueError('Original GS message did not recover exactly')
            row=metrics(arrays['baseline'],arrays['corrected'],original)
            row.update(sample_id=sid,split=split,prompt_group=record['task']['prompt_group'],
                       decoded_message_accuracy=scores,full_defense_acceptance=None,target_image_detection=None)
            rows.append(row)
    for name in ('message','key','nonce'):
        if len({fp[name] for fp in fingerprints}) != 16:raise ValueError('Repeated GS state')
    summaries={}
    for split in ('proxy_test','target_test'):
        selected=[row for row in rows if row['split']==split]
        differences=[row['baseline_bit_error']-row['corrected_bit_error'] for row in selected]
        summaries[split]=dict(bit_error_differences=differences,mean_bit_error_improvement=float(np.mean(differences)),
            mean_mse_improvement=float(np.mean([row['baseline_mse']-row['corrected_mse'] for row in selected])),
            prompt_group_means={group:float(np.mean([row['baseline_bit_error']-row['corrected_bit_error'] for row in selected if row['prompt_group']==group]))
                                for group in ['test_1','test_2','test_3','test_4']})
    verify_predictions(folder,seal_sha)
    result=dict(completed=True,rows=rows,summaries=summaries,prediction_seal_sha256=seal_sha,
                cpu_seconds=time.perf_counter()-start,original_gs_scores_verified=16,
                official_message_scores=48,independent_states=16,cdf_sign_checks=48,
                feedback_to_estimator=False,target_inversions=0,attack_candidates=0,
                coordinate_independence_assumed=False,full_defense_acceptance=None,attack_success_rate=None)
    c.write(output,result)
    print('COMPLETED_TEST_EVALUATION',flush=True)
    return result


if __name__ == '__main__':main(*sys.argv[1:])
