import os,math,statistics
from common31 import c,r,module,BASE,POINTS,candidates
def analyze(root,private_folder):
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU only')
    import numpy as np
    from PIL import Image
    private=module('native_cpu_private',BASE/'reference_reliability/private_state.py');decoder={'np':np};r.definitions(BASE/'cross_generator/verify_message_scores.py',{'decode'},decoder)
    summary=c.read(root/'evaluate/summary.json')
    if summary['candidate_seal_sha256']!=c.sha(root/'candidates_sealed.json') or c.read(root/'candidates_sealed.json')['rows']!=candidates(root):raise ValueError('Seal differs')
    rows=[];errors=[]
    for row in summary['rows']:
        sid=row['task_id'];record=c.read(root/'prepare'/str(sid)/'record.json');raw=private.load(private_folder,sid,record['encryption_fingerprints']);folder=root/'evaluate'/row['folder']
        if c.sha(folder/'target_inverse.npy')!=row['inverse']['sha256']:raise ValueError('Inverse changed')
        ba=decoder['decode'](np.load(folder/'target_inverse.npy',allow_pickle=False),raw)
        if ba!=row['bit_accuracy']:raise ValueError('CPU message decode differs')
        path=root/'prepare'/str(sid)/(row['label']+'.png') if row['label'] in ('reference','cover') else root/f'attack_{sid}'/f'update_{row["label"]}.png'
        if c.png_record(path)!=row['image']:raise ValueError('Image changed')
        with Image.open(path) as im:a=np.asarray(im,dtype=np.float64)/255
        with Image.open(root/'prepare'/str(sid)/'cover.png') as im:b=np.asarray(im,dtype=np.float64)/255
        mse=float(np.mean((a-b)**2));errors.append(abs(mse-row['mse_rgb01']));rows.append(row)
    if len(rows)!=28 or max(errors)>1e-15:raise ValueError('Wrong denominator or distortion')
    summaries={str(n):dict(n=4,gs_passes=sum(row['gs_detected'] for row in rows if row['label']==str(n)),mean_ba=statistics.mean(row['bit_accuracy'] for row in rows if row['label']==str(n)),mean_psnr_db=statistics.mean(row['psnr_db'] for row in rows if row['label']==str(n))) for n in POINTS}
    result=dict(completed=True,rows=rows,summary=summaries,independent_cpu_redecodes=28,max_mse_abs_error=max(errors),official_cli_endpoint_actual_update=151,paper_text_endpoint_actual_update=150,full_paper_reproduction=False,calibration_only=True,primary_selection='fixed151_no_best_checkpoint',lpips=None,formal_human_labels=None,source_equivalence_scope='Original CLI RGB01 reference path retained; not earlier project normalized PIL reference path')
    c.write(root/'analysis.json',result);return result
