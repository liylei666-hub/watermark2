"""Post-run CPU analysis; separate from the frozen stage31 model runtime."""
import datetime,hashlib,json,math,os,statistics,sys
from pathlib import Path
POINTS=(20,50,100,150,151)
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def aggregate(rows):
    if not rows or any(r['mse_rgb01']<0 or not math.isfinite(r['mse_rgb01']) for r in rows):raise ValueError('Invalid MSE')
    mean_mse=statistics.mean(r['mse_rgb01'] for r in rows)
    return dict(n=len(rows),mean_mse_rgb01=mean_mse,mean_per_image_psnr_db=None if any(r['mse_rgb01']==0 for r in rows) else statistics.mean(-10*math.log10(r['mse_rgb01']) for r in rows),aggregate_mse_psnr_db=None if mean_mse==0 else -10*math.log10(mean_mse),aggregate_psnr_infinite=mean_mse==0)
def analyze(root):
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU-only analysis')
    import numpy as np
    from PIL import Image
    root=Path(root);status=read(root/'scheduler_status.json')
    if status['state']!='completed':raise ValueError('Only completed fixed calibration')
    result=read(root/'analysis.json');rows=result['rows'];evaluation=read(root/'evaluate/summary.json');seal=read(root/'candidates_sealed.json')
    if rows!=evaluation['rows'] or evaluation['candidate_seal_sha256']!=sha(root/'candidates_sealed.json') or len(seal['rows'])!=20:raise ValueError('Evaluation/seal binding differs')
    expected={(i,label) for i in range(1,5) for label in ['reference','cover']+list(map(str,POINTS))}
    if len(rows)!=28 or {(r['task_id'],r['label']) for r in rows}!=expected:raise ValueError('Wrong fixed image denominator')
    by_id={(r['task_id'],r['label']):r for r in rows}
    for candidate in seal['rows']:
        if candidate['image']!=by_id[candidate['task_id'],str(candidate['actual_update'])]['image']:raise ValueError('Candidate seal differs from evaluated image')
    errors=[]
    for row in rows:
        sid=row['task_id'];label=row['label']
        path=root/'prepare'/str(sid)/(label+'.png') if label in ('reference','cover') else root/f'attack_{sid}'/f'update_{label}.png'
        if sha(path)!=row['image']['sha256']:raise ValueError('Image hash differs')
        if sha(root/'evaluate'/row['folder']/'target_inverse.npy')!=row['inverse']['sha256']:raise ValueError('Inverse hash differs')
        with Image.open(path) as im:a=np.asarray(im.convert('RGB'),dtype=np.float64)/255
        with Image.open(root/'prepare'/str(sid)/'cover.png') as im:b=np.asarray(im.convert('RGB'),dtype=np.float64)/255
        if a.shape!=b.shape or a.shape!=(512,512,3):raise ValueError('Unexpected image dimensions')
        mse=float(np.mean((a-b)**2));errors.append(abs(mse-row['mse_rgb01']))
        if abs(mse-row['mse_rgb01'])>1e-15:raise ValueError('Distortion readback differs')
        if row['gs_detected']!=(row['bit_accuracy']>.70703125):raise ValueError('Strict threshold differs')
    groups={}
    for n in POINTS:
        current=[r for r in rows if r['label']==str(n)];g=aggregate(current)
        if len(current)!=4:raise ValueError('Missing checkpoint')
        g.update(mean_ba=statistics.mean(r['bit_accuracy'] for r in current),gs_passes=sum(r['gs_detected'] for r in current),mean_ssim_grayscale=statistics.mean(r['ssim_grayscale'] for r in current),mean_ms_ssim_rgb=statistics.mean(r['ms_ssim_rgb'] for r in current))
        groups[str(n)]=g
    return dict(analysis_revision=2,created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),run_analysis_sha256=sha(root/'analysis.json'),candidate_seal_sha256=sha(root/'candidates_sealed.json'),checkpoints=groups,primary_actual_update=151,secondary_paper_text_actual_update=150,checkpoint_selection=False,max_mse_readback_error=max(errors),public_verification='PNG and inverse hashes, distortion arithmetic and denominators independently checked; BA is recorded evaluator output. Private28-redecode assertion belongs to the server evaluator receipt, not this public check.',lpips=None,formal_human_labels=None,full_paper_reproduction=False)
def weight_audit(root,controller):
    """Read weights only after the model run. This is not a prelaunch seal."""
    root=Path(root);cfg=read(controller);server=Path('/data0/liyanlei/watermark_research')
    if sha(controller)!=read(root/'launch_intent.json')['runtime_sha256'] or sha(controller)!=Path(controller).with_suffix('.sha256').read_text().strip():raise ValueError('Controller runtime changed')
    if read(root/'scheduler_status.json')['state'] not in ('completed','stopped'):raise ValueError('Defer heavy weight IO until terminal state')
    rows=[];start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for role in ('proxy','target'):
        model=cfg['design'][role];snapshot=Path(model['snapshot'])
        for path in sorted(snapshot.rglob('*')):
            if not path.is_file() or path.suffix not in ('.safetensors','.bin','.ckpt','.pt'):continue
            resolved=path.resolve()
            if not resolved.is_relative_to(server.resolve()):raise ValueError('Cached weight escapes designated project')
            before=resolved.stat();digest=sha(path);after=resolved.stat()
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('Weight changed during retrospective read')
            rows.append(dict(role=role,snapshot_revision=model['revision'],relative_path=path.relative_to(snapshot).as_posix(),resolved_path=str(resolved),is_symlink=path.is_symlink(),bytes=after.st_size,mtime_ns=after.st_mtime_ns,ctime_ns=after.st_ctime_ns,inode=after.st_ino,sha256=digest))
    if not rows or set(x['role'] for x in rows)!= {'proxy','target'}:raise ValueError('No weights for both roles')
    return dict(audit_started_at_utc=start,audit_finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),timing='retrospective_after_run_not_prelaunch_seal',scope='Existing snapshot weight-file bytes and filesystem timestamps. Does not certify which alternative serialization was loaded, unchanged prelaunch bytes, or identity with original paper checkpoint.',controller_runtime_sha256=sha(controller),weights=rows)
def write_once(path,data):
    with Path(path).open('x',encoding='utf8') as f:json.dump(data,f,indent=2,ensure_ascii=False);f.write('\n')
if __name__=='__main__':
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only')
    root=Path(sys.argv[1]);write_once(root/'postrun_analysis_v2.json',analyze(root));write_once(root/'weight_integrity_retrospective.json',weight_audit(root,sys.argv[2]));print('POSTRUN_ANALYSIS_AND_RETROSPECTIVE_WEIGHTS_VERIFIED')
