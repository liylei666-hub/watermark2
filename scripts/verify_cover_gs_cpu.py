"""Recompute completed evaluator scores from retained latents with official CPU GS."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility must be empty')
if os.environ.get('HF_HUB_OFFLINE')!='1':raise SystemExit('Offline mode required')
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent/'cover_pilot'))
import contract as c
import bundle as b


def main(root,project,output):
    # No target-side score is read until the original full evaluation has completed.
    if c.read(root/'status.json').get('status')!='completed':raise ValueError('Group not completed')
    queue=b.evaluation_queue(root,root/'attack_plan.json')
    summary=c.read(root/'evaluator_results/summary.json')
    if [x['input'] for x in summary['rows']]!=queue:raise ValueError('Evaluation queue mismatch')
    if c.sha(root/'delivery_sealed.json')!=summary['delivery_seal_sha256']:raise ValueError('Seal mismatch')
    protocol=project/'protocols/17_cover_pilot.json'
    if c.sha(protocol)!=summary['protocol_sha256']:raise ValueError('Protocol mismatch')
    cfg=c.read(protocol);source_audit=c.read(project/'reports/16_cover_preparation/gs_source_audit.json')
    upstream=project/'third_party/semantic-forgery'
    for row in source_audit['sources']:
        if c.sha(upstream/row['path'])!=row['sha256']:raise ValueError('GS source changed')
    sys.path.insert(0,str(upstream))
    import numpy as np
    import torch
    from utils.wm.gs_provider import GsProvider
    from utils.utils import check_if_detection_successful,get_detection_threshold
    if torch.cuda.is_initialized():raise RuntimeError('CUDA initialized')
    if get_detection_threshold('GS')!=cfg['gs_threshold']:raise ValueError('Threshold mismatch')
    wm=GsProvider(latent_shape=(1,4,64,64),device='cpu',dtype=torch.float32,**cfg['gs_parameters'])
    results=[]
    for row in summary['rows']:
        task=row['input']['task_id'];kind=row['input']['kind'];record=row['result']
        p=root/'evaluator_results'/str(task)/kind/'target_inverse.npy'
        if c.sha(p)!=record['target_inverse']['sha256']:raise ValueError('Latent hash mismatch')
        array=np.load(p,allow_pickle=False)
        if array.shape!=(1,4,64,64) or array.dtype!=np.float32 or not np.isfinite(array).all():raise ValueError('Invalid latent')
        ba=float(wm.get_accuracies(torch.from_numpy(array))['bit_accuracies'][0])
        detected=check_if_detection_successful('GS',cfg['gs_threshold'],ba)
        if ba!=record['bit_accuracy'] or detected!=record['gs_detected']:raise ValueError('CPU score disagreement')
        results.append(dict(task_id=task,kind=kind,inverse_sha256=c.sha(p),bit_accuracy=ba,gs_detected=detected))
    if torch.cuda.is_initialized() or 'utils.pipe.pipe_utils' in sys.modules:raise RuntimeError('Unexpected GPU or pipeline use')
    c.write(output,dict(status='passed',rows=results,source_files_verified=len(source_audit['sources']),
        evaluator_summary_sha256=c.sha(root/'evaluator_results/summary.json'),delivery_seal_sha256=c.sha(root/'delivery_sealed.json'),
        gpu_used=False,models_loaded=False,new_generations=0,new_inversions=0,script_sha256=c.sha(__file__)))
    print('VERIFIED_12_STORED_GS_SCORES_CPU')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('project',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    main(a.root,a.project,a.output)
