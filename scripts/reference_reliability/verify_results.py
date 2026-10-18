"""Read-only CPU evidence verification, with evaluator-private GS material."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '' or os.environ.get('HF_HUB_OFFLINE') != '1':
    raise SystemExit('CPU/offline required')
import sys
from pathlib import Path
from common import r, read, sha, write
from boundary import verify_seal, load_inverse, publishable_files
from analyze import analyze
import private_state as private

def verify(root, private_folder, analysis):
    verify_seal(root)
    if analyze(root) != read(analysis):
        raise ValueError('Analysis differs from saved arrays')
    sys.path.insert(0, str(r.UPSTREAM))
    if sha(r.UPSTREAM/'utils/wm/gs_provider.py') != '233ff05fa47d18d5875577d2cd920bd21d8ceea05149f5f100c1fab32c524d99':
        raise ValueError('GS provider source changed')
    import torch
    rows=[]
    for k in range(1,5):
        record=read(root/'reference'/str(k)/'record.json')
        raw=private.load(private_folder,k,record['encryption_fingerprints'])
        wm=private.provider(raw,'cpu')
        z=torch.from_numpy(load_inverse(root/'reference'/str(k)/'original_noise.npy'))
        orig=float(wm.get_accuracies(z)['bit_accuracies'][0])
        if orig!=1.:raise ValueError('Original noise is not valid GS')
        z=torch.from_numpy(load_inverse(root/'evaluation'/str(k)/'inverse.npy'))
        target=float(wm.get_accuracies(z)['bit_accuracies'][0])
        metrics=read(root/'evaluation'/str(k)/'metrics.json')
        if metrics['bit_accuracy']!=target or metrics['gs_detected']!=(target>.70703125):
            raise ValueError('Stored target metric mismatch')
        if metrics['inverse']['sha256']!=sha(root/'evaluation'/str(k)/'inverse.npy'):
            raise ValueError('Target inverse changed')
        rows.append(dict(task_id=k,original_bit_accuracy=orig,reference_bit_accuracy=target))
    executions=[read(root/name/'execution.json') for name in ['reference','proxy_25','proxy_50','proxy_100','evaluation']]
    if not all(x['completed'] and x['exit_code']==0 and not x['timed_out'] for x in executions):
        raise ValueError('Incomplete model execution')
    if torch.cuda.is_initialized() or 'utils.pipe.pipe_utils' in sys.modules:
        raise ValueError('Verification initialized models/CUDA')
    return dict(status='passed',rows=rows,analysis_recomputed=True,model_processes_verified=5,
                gpu_process_seconds=sum(x['elapsed_seconds'] for x in executions),
                publishable_files=len(publishable_files(root)),private_material_published=False,
                gpu_used=False,models_loaded=False,new_model_experiments_run=0)

if __name__=='__main__':
    write(Path(sys.argv[4]),verify(*map(Path,sys.argv[1:4])))
