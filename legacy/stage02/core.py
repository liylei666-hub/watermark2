import hashlib, json, math, os, tempfile
from pathlib import Path
import numpy as np

METHODS = ['CLIP_global','SSCD_global','DINO_global','DINO_local_mean','DINO_local_q10']
HOST_GPUS = {5:'GPU-e6f35928-0155-f121-e707-1eaf3c14965c',7:'GPU-9644fb82-cb6f-7311-8017-eaee41409bb7'}

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def dump(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(path)

def normalize(x):
    x=np.asarray(x,dtype=np.float32)
    if not np.isfinite(x).all():raise ValueError('nonfinite features')
    norms=np.linalg.norm(x,axis=-1,keepdims=True)
    if np.any(norms<1e-10):raise ValueError('zero features')
    return x/norms

def scores(a,b,model):
    if model!='dinov2':return {('CLIP_global' if model=='clip' else 'SSCD_global'):float(np.dot(a,b))}
    local=np.einsum('ij,ij->i',a,b)
    return dict(DINO_global=float(normalize(a.mean(axis=0))@normalize(b.mean(axis=0))),
                DINO_local_mean=float(local.mean()),DINO_local_q10=float(np.quantile(local,.1,method='linear')))

def calibrate(values,target=.05):
    a=np.sort(np.asarray(values,dtype=np.float64))
    if a.size==0 or not np.isfinite(a).all():raise ValueError('empty/nonfinite calibration')
    if not 0<=target<1:raise ValueError('invalid target')
    # accept score >= threshold; ties accepted. At most floor(target*n) rejected.
    return float(a[math.floor(target*len(a))])

def rate(values,threshold,reject=False):
    a=np.asarray(values,dtype=float)
    if not np.isfinite(a).all():raise ValueError('nonfinite scores')
    n=len(a);k=int(np.sum(a<threshold if reject else a>=threshold))
    return dict(count=k,total=n,rate=k/n if n else None)

def fit_thresholds(rows):
    return {m:calibrate([r[m] for r in rows if r['split']=='smoke_calibration' and r['category']=='A']) for m in METHODS}

def validate_gpu_config(config,visible,task):
    mapping={int(k):v for k,v in config['gpu_uuids'].items()}
    if mapping!=HOST_GPUS:raise ValueError('host GPU whitelist mismatch')
    idx=5 if task=='clip_sscd' else 7 if task=='dinov2' else None
    if idx is None or visible!=HOST_GPUS[idx]:raise ValueError('missing/unapproved task GPU binding')
    return idx

def cache_key(image_hash,model,weight_hash,code_commit,preprocess):
    payload=[image_hash,model,weight_hash,code_commit,preprocess,'stage02-features-v1-float32']
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def validate_manifest(manifest):
    images={x['id']:x for x in manifest['images']}
    if len(images)!=len(manifest['images']):raise ValueError('duplicate image ID')
    pair_ids=set();groups={};hash_splits={}
    for x in images.values():
        for key,table in [(x['group'],groups),(x['pixel_sha256'],hash_splits)]:
            if key in table and table[key]!=x['split']:raise ValueError('group/content split leakage')
            table[key]=x['split']
    for p in manifest['pairs']:
        if p['pair_id'] in pair_ids:raise ValueError('duplicate pair ID')
        pair_ids.add(p['pair_id'])
        a,b=images[p['left']],images[p['right']]
        if a['split']!=p['split'] or b['split']!=p['split']:raise ValueError('pair split leakage')
        if p['donor'] and images[p['donor']]['split']!=p['split']:raise ValueError('donor split leakage')
        if p['category']=='A' and (p['left']==p['right'] or a['group']!=b['group']):raise ValueError('invalid A pair')
        if p['category']=='D' and a['group']==b['group']:raise ValueError('invalid D pair')
    for a,b in manifest.get('near_duplicate_edges',[]):
        if images[a]['split']!=images[b]['split']:raise ValueError('near duplicate leakage')
    return True
