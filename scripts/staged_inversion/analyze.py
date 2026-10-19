"""CPU finalizer: validate the complete fixed pilot, decode all saved inversions and decide."""
import datetime
import os
from pathlib import Path
from common import c,r,module,verify_seal,decide,BASE,METHODS


def analyze(root,cfg,private_folder):
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU visibility required')
    import numpy as np
    from PIL import Image
    seal=verify_seal(root);evaluated=c.read(root/'evaluate'/'summary.json')
    if evaluated['seal_sha256']!=c.sha(root/'candidates_sealed.json'):raise ValueError('Evaluation seal mismatch')
    execution=c.read(root/'evaluate'/'execution.json')
    if datetime.datetime.fromisoformat(execution['started_at_utc'])<=datetime.datetime.fromisoformat(seal['sealed_at_utc']):
        raise ValueError('Evaluation preceded candidate seal')
    decoder={ 'np':np }
    r.definitions(BASE/'cross_generator/verify_message_scores.py',{'decode'},decoder)
    private=module('stage28_cpu_private',BASE/'reference_reliability/private_state.py')
    rows=[];fingerprints=[]
    for task in cfg['design']['tasks']:
        sid=task['task_id'];record=c.read(root/'prepare_reference'/str(sid)/'record.json')
        fingerprints.append(record['encryption_fingerprints'])
        raw=private.load(private_folder,sid,record['encryption_fingerprints'])
        with Image.open(root/'attack_inputs'/str(sid)/'cover.png') as im:cover=np.asarray(im,dtype=np.float64)/255
        for kind in ('reference','cover')+METHODS:
            folder=root/'evaluate'/f'{sid}_{kind}';metric=c.read(folder/'metrics.json')
            path=root/'attack_inputs'/str(sid)/(kind+'.png') if kind in ('reference','cover') else root/f'attack_{sid}_{kind}'/'candidate.png'
            if metric['image']!=c.png_record(path) or metric['inverse']['sha256']!=c.sha(folder/'target_inverse.npy'):
                raise ValueError('Image/inverse association changed')
            value=np.load(folder/'target_inverse.npy',allow_pickle=False)
            if value.shape!=(1,4,64,64) or value.dtype!=np.float32 or not np.isfinite(value).all():raise ValueError('Invalid saved inverse')
            ba=decoder['decode'](value,raw)
            if ba!=metric['bit_accuracy'] or metric['gs_detected']!=(ba>cfg['design']['gs_threshold']):
                raise ValueError('Independent score decode differs')
            row=dict(task_id=sid,kind=kind,bit_accuracy=ba,gs_detected=metric['gs_detected'],cover_mse_rgb01=None,core_seconds=None)
            if kind in METHODS:
                with Image.open(path) as im:pixels=np.asarray(im,dtype=np.float64)/255
                row['cover_mse_rgb01']=float(np.mean((pixels-cover)**2))
                row['core_seconds']=c.read(root/f'attack_{sid}_{kind}'/'summary.json')['core_seconds']
            rows.append(row)
    if any(len({f[key] for f in fingerprints})!=4 for key in ('message','key','nonce')):
        raise ValueError('Repeated GS identity')
    result=dict(completed=True,rows=rows,independent_cpu_decodes=20,private_material_exported=False,
        gpu_used=False,models_loaded=False,decision=decide(rows,cfg['design']['decision_rule']))
    c.write(root/'analysis.json',result)
    return result
