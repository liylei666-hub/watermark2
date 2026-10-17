"""CPU file contracts for fixed cover tasks; data-flow checks, not OS isolation."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

PROXY_ID = 'Manojb/stable-diffusion-2-1-base'
PROXY_REVISION = '0094d483a120f3f33dafbd187ea4aa60d10de75c'
PROXY_SNAPSHOT = '/data0/liyanlei/watermark_research/cache/huggingface/hub/models--Manojb--stable-diffusion-2-1-base/snapshots/'+PROXY_REVISION
METHODS = {'imprint': dict(updates=10, learning_rate=0.01, inversion_steps=50, inversion_guidance=1.0, inversion_prompt='', mask=None),
           'jain': dict(updates=447, lamda=10000.0, alpha=5/255, delta=0, freeze_parameters=False)}
EXPECTED_PAIRS = {(i,m) for i in [1,2,3] for m in METHODS}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def keys(value, expected):
    if not isinstance(value,dict) or set(value)!=set(expected):
        raise ValueError('Unexpected contract fields')


def read(path):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate JSON key')
            result[k]=v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=unique)


def write(path, value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False)
        f.flush();os.fsync(f.fileno())


def inside(root, relative):
    if not isinstance(relative,str) or '\\' in relative or ':' in relative:
        raise ValueError('Expected POSIX relative path')
    p=PurePosixPath(relative)
    if p.is_absolute() or not p.parts or any(x in ('..','.') for x in p.parts):
        raise ValueError('Path is not a permitted relative path')
    root=Path(root).resolve();target=(root/relative).resolve()
    if not target.is_relative_to(root):raise ValueError('Path escapes bundle')
    return target


def png_record(path):
    from PIL import Image
    path=Path(path)
    with Image.open(path) as im:
        if im.format!='PNG' or im.mode!='RGB' or im.size!=(512,512):
            raise ValueError('Expected RGB 512x512 PNG')
        im.load()
    return dict(path=path.name,sha256=sha(path),bytes=path.stat().st_size)


def validate_job(path):
    path=Path(path);job=read(path)
    keys(job,['version','task_id','method','seed','reference','cover','proxy','parameters'])
    if job['version']!=1 or type(job['task_id']) is not int or job['task_id'] not in [1,2,3]:
        raise ValueError('Unknown task')
    if job['method'] not in METHODS or type(job['seed']) is not int or job['seed']!=500+job['task_id']:
        raise ValueError('Unexpected method or attack seed')
    keys(job['proxy'],['model_id','revision','snapshot','dtype','resolution'])
    if job['proxy']!=dict(model_id=PROXY_ID,revision=PROXY_REVISION,snapshot=PROXY_SNAPSHOT,dtype='float32',resolution=512):
        raise ValueError('Proxy setting changed')
    if job['parameters']!=METHODS[job['method']]:
        raise ValueError('Attack parameters changed')
    for name in ['reference','cover']:
        rec=job[name];keys(rec,['path','sha256','bytes'])
        if rec['path']!=name+'.png':raise ValueError('Unexpected input name')
        p=inside(path.parent,rec['path'])
        if png_record(p)!=rec:raise ValueError('Input image integrity mismatch')
    return job


def freeze_candidate(output_dir, job_path):
    job=validate_job(job_path);out=Path(output_dir)
    candidate=inside(out,'candidate.png')
    value=dict(version=1,task_id=job['task_id'],method=job['method'],
        job_sha256=sha(job_path),candidate=png_record(candidate))
    write(out/'candidate_frozen.json',value)
    return value


def collect_delivery(root, plan_path):
    root=Path(root);plan=read(plan_path)
    keys(plan,['version','jobs'])
    if plan['version']!=1 or not isinstance(plan['jobs'],list) or len(plan['jobs'])!=6:
        raise ValueError('Expected the six predetermined tasks')
    seen=set();records=[]
    for entry in plan['jobs']:
        keys(entry,['task_id','method','job_path','job_sha256','output_path'])
        pair=(entry['task_id'],entry['method'])
        if pair not in EXPECTED_PAIRS or pair in seen:raise ValueError('Wrong or duplicate task')
        seen.add(pair);jobpath=inside(root,entry['job_path'])
        if sha(jobpath)!=entry['job_sha256']:raise ValueError('Frozen job changed')
        job=validate_job(jobpath)
        if (job['task_id'],job['method'])!=pair:raise ValueError('Job identity mismatch')
        out=inside(root,entry['output_path']);frozen_path=inside(out,'candidate_frozen.json');frozen=read(frozen_path)
        keys(frozen,['version','task_id','method','job_sha256','candidate'])
        if frozen['version']!=1 or (frozen['task_id'],frozen['method'])!=pair or frozen['job_sha256']!=entry['job_sha256']:
            raise ValueError('Candidate identity mismatch')
        if frozen['candidate']!=png_record(inside(out,'candidate.png')):
            raise ValueError('Candidate changed after freezing')
        records.append(dict(task_id=pair[0],method=pair[1],job_sha256=entry['job_sha256'],
            candidate_path=entry['output_path']+'/candidate.png',candidate_sha256=frozen['candidate']['sha256'],
            freeze_record_sha256=sha(frozen_path)))
    return dict(version=1,plan_sha256=sha(plan_path),candidates=records)


def seal_delivery(root, plan_path):
    value=collect_delivery(root,plan_path)
    write(Path(root)/'delivery_sealed.json',value)
    return value


def verify_delivery(root, plan_path):
    current=collect_delivery(root,plan_path)
    if read(Path(root)/'delivery_sealed.json')!=current:
        raise ValueError('Delivery seal mismatch')
    return current
