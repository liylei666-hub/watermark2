"""Independent CPU readback of fixed stage24 test tensors and image associations."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':raise SystemExit('CPU visibility required')
import json
from pathlib import Path
import sys
import numpy as np
import io_contract as c
from phase_contract import verify_source, verify_predictions, SOURCE_FIT, image_bundle


def features(value):
    raw=value[0].astype(np.float64)
    windows=np.lib.stride_tricks.sliding_window_view(np.pad(raw,((0,0),(1,1),(1,1)),mode='reflect'),(3,3),axis=(1,2))
    return np.moveaxis(np.concatenate((raw,windows.mean(axis=(-2,-1)))),0,-1).reshape(-1,8)


def verify(source):
    source=Path(source);folder=source/'tests';verify_source(source)
    status=c.read(folder/'status.json')
    if status.get('completed') is not True:raise ValueError('Test phase incomplete')
    verify_predictions(folder,status['prediction_seal_sha256'])
    result=c.read(folder/'evaluation.json')
    if result['prediction_seal_sha256']!=status['prediction_seal_sha256']:raise ValueError('Evaluation association changed')
    meta=c.verify_seal(source/'source_fit',SOURCE_FIT)['metadata']
    model=c.load_model(source/'source_fit/model.json',meta['model_sha256'])
    repo=Path(__file__).resolve().parents[2]
    design=c.read(repo/'protocols/24_cross_generator_design.json')
    frozen={row['sample_id']:row for row in design['tasks']}
    images_sha=c.sha(folder/'target_images/images.json');images=image_bundle(folder/'target_images',images_sha)
    output=[];prediction_error=0.;fingerprints=[]
    for split,prefix in [('proxy_test','proxy'),('target_test','target')]:
        inputs=folder/(split+'_inputs');input_rows=c.load_bundle(inputs,split,c.sha(inputs/'bundle.json'))
        pred_folder=folder/(split+'_predictions')
        pred_meta=c.verify_seal(pred_folder,c.sha(pred_folder/'seal.json'))['metadata']
        if pred_meta['input_sha256']!=c.sha(inputs/'bundle.json'):raise ValueError('Prediction input changed')
        for i,sid in enumerate(c.SPLITS[split]):
            original_folder=folder/(prefix+'_generate_'+str(i//4))/sid
            record=c.read(original_folder/'record.json')
            if record['task']!=frozen[sid] or c.png_record(original_folder/'reference.png')!=record['image']:raise ValueError('Generation association changed')
            if c.array_record(original_folder/'original_noise.npy')!=record['original_noise']:raise ValueError('Original noise changed')
            fingerprints.append(record['encryption_fingerprints'])
            original=np.load(original_folder/'original_noise.npy',allow_pickle=False).astype(np.float64)
            baseline=np.load(pred_folder/(sid+'_baseline.npy'),allow_pickle=False)
            corrected=np.load(pred_folder/(sid+'_corrected.npy'),allow_pickle=False)
            np.testing.assert_array_equal(baseline,input_rows[i]['estimate'])
            if split=='proxy_test':inverse=original_folder/'estimate.npy'
            else:
                inverse_folder=folder/('target_inverse_'+str(i//4))
                row=c.read(inverse_folder/'summary.json')['rows'][i%4]
                if row['sample_id']!=sid or row['image_sha256']!=record['image']['sha256']:raise ValueError('Target proxy inversion association changed')
                if images['rows'][i]['image']['sha256']!=record['image']['sha256']:raise ValueError('Delivered target image changed')
                inverse=inverse_folder/sid/'estimate.npy'
            np.testing.assert_array_equal(baseline,np.load(inverse,allow_pickle=False))
            f=features(baseline);a=np.column_stack((np.ones(len(f)),(f-model['mean'])/model['scale']))
            expected=np.moveaxis((a@model['coefficients']).reshape(64,64,4),-1,0)[None]
            prediction_error=max(prediction_error,float(np.max(np.abs(expected-corrected))))
            np.testing.assert_allclose(corrected,expected,atol=1e-12,rtol=1e-12)
            values=dict(baseline_mse=float(np.square(baseline.astype(np.float64)-original).sum()/original.size),
                corrected_mse=float(np.square(corrected-original).sum()/original.size),
                baseline_bit_error=float(np.count_nonzero((baseline>=0)!=(original>=0))/original.size),
                corrected_bit_error=float(np.count_nonzero((corrected>=0)!=(original>=0))/original.size))
            stored=[row for row in result['rows'] if row['sample_id']==sid]
            if len(stored)!=1:raise ValueError('Wrong evaluation identities')
            for key,value in values.items():np.testing.assert_allclose(value,stored[0][key],atol=1e-12,rtol=1e-12)
            output.append(dict(sample_id=sid,split=split,prompt_group=frozen[sid]['prompt_group'],**values))
    for name in ('key','nonce','message'):
        if len({fp[name] for fp in fingerprints})!=16:raise ValueError('GS state repeated')
    summaries={}
    for split in ('proxy_test','target_test'):
        rows=[row for row in output if row['split']==split]
        differences=[row['baseline_bit_error']-row['corrected_bit_error'] for row in rows]
        summaries[split]=dict(mean_bit_error_improvement=float(np.mean(differences)),
            mean_mse_improvement=float(np.mean([row['baseline_mse']-row['corrected_mse'] for row in rows])),
            bit_error_differences=differences,prompt_group_means={group:float(np.mean([row['baseline_bit_error']-row['corrected_bit_error'] for row in rows if row['prompt_group']==group])) for group in ['test_1','test_2','test_3','test_4']})
        if summaries[split]!=result['summaries'][split]:raise ValueError('Group summary differs')
    executions=[]
    for name in ['proxy_generate_0','proxy_generate_1','target_generate_0','target_generate_1','target_inverse_0','target_inverse_1']:
        out=folder/name;e=c.read(out/'execution.json');device=c.read(out/'device_preimport.json')
        if e['exit_code']!=0 or not e['completed'] or e['timed_out'] or device['compute_apps']:raise ValueError('Invalid model execution')
        if device['rows'][0][1]!=e['gpu_uuid'] or e['gpu_index'] not in (0,1,2):raise ValueError('Device association mismatch')
        events=[json.loads(line) for line in (out/'preflight.jsonl').read_text().splitlines()]
        if not any(event['event']=='idle_verified' for event in events):raise ValueError('Idle gate missing')
        executions.append(e)
    return dict(verified=True,rows=output,summaries=summaries,images=16,
                max_abs_prediction_readback_error=prediction_error,
                test_model_processes=6,test_model_process_seconds=sum(e['elapsed_seconds'] for e in executions),
                full_defense_acceptance=None,attack_success_rate=None,
                official_message_scores_recomputed=False,method='Independent sliding-window features, saved arrays, counts and file associations')


if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),indent=2))
