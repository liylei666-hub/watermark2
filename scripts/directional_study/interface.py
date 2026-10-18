"""Strict image-only jobs and complete candidate-set sealing; not OS isolation."""
import hashlib
import json
from pathlib import Path
from PIL import Image
import numpy as np
from delivery import CONDITIONS

PROXY = dict(model_id='Manojb/stable-diffusion-2-1-base',
    revision='0094d483a120f3f33dafbd187ea4aa60d10de75c',
    snapshot='/data0/liyanlei/watermark_research/cache/huggingface/hub/models--Manojb--stable-diffusion-2-1-base/snapshots/0094d483a120f3f33dafbd187ea4aa60d10de75c',
    dtype='float32', resolution=512)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)


def read(path):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result: raise ValueError('Duplicate JSON field')
            result[k]=v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def image_record(path):
    with Image.open(path) as im:
        if im.format!='PNG' or im.mode!='RGB' or im.size!=(512,512):
            raise ValueError('Expected RGB512 PNG')
        im.load()
    return dict(path=Path(path).name, sha256=sha(path))


def validate_job(path):
    path=Path(path); job=read(path)
    if set(job)!={'version','task_id','seed','proxy','reference','cover'}:
        raise ValueError('Job contains unexpected fields')
    if job['version']!=1 or type(job['task_id']) is not int or job['task_id'] not in range(1,5):
        raise ValueError('Unexpected job identity')
    if type(job['seed']) is not int or job['seed']!=800+job['task_id'] or job['proxy']!=PROXY:
        raise ValueError('Unexpected proxy settings')
    for name in ['reference','cover']:
        # Fixed names avoid consuming arbitrary paths supplied by job metadata.
        if job[name]!=image_record(path.parent/(name+'.png')):
            raise ValueError('Job image hash or path mismatch')
    return job


def export_job(root, task_id, reference_path, cover_path):
    if type(task_id) is not int or task_id not in range(1,5): raise ValueError('Unknown task')
    for p in [reference_path,cover_path]:image_record(p)
    folder=Path(root)/'attack_inputs'/str(task_id)
    folder.mkdir(parents=True, exist_ok=False)
    for name,source in [('reference',reference_path),('cover',cover_path)]:
        with (folder/(name+'.png')).open('xb') as f:f.write(Path(source).read_bytes())
    job=dict(version=1,task_id=task_id,seed=800+task_id,proxy=PROXY,
        reference=image_record(folder/'reference.png'),cover=image_record(folder/'cover.png'))
    write(folder/'job.json',job);validate_job(folder/'job.json')
    return sha(folder/'job.json')


def freeze_inputs(root):
    jobs=[]
    for task in range(1,5):
        path=Path(root)/'attack_inputs'/str(task)/'job.json'
        validate_job(path);jobs.append(dict(task_id=task,sha256=sha(path)))
    write(Path(root)/'input_jobs_sealed.json',jobs)
    return jobs


def collect(root):
    root=Path(root);rows=[];jobs=[]
    for task in range(1,5):
        job_path=root/'attack_inputs'/str(task)/'job.json'
        validate_job(job_path);jobs.append(dict(task_id=task,sha256=sha(job_path)))
        out=root/'attack_outputs'/str(task)/'probes';record=read(out/'candidate_set.json')
        if set(record)!= {'conditions','distortion','support_sha256'} or set(record['conditions'])!=set(CONDITIONS):
            raise ValueError('Incomplete candidate set')
        if sha(out/'support.npy')!=record['support_sha256']:raise ValueError('Support changed')
        support=np.load(out/'support.npy',allow_pickle=False)
        if support.dtype!=bool or support.shape!=(512,512,3) or support.mean()<0.5:
            raise ValueError('Invalid shared support')
        count=int(support.sum())
        expected=dict(active_channels=count,total_channels=int(support.size),active_fraction=count/support.size,
            squared_l2_integer=count,linf_integer=1,mse_rgb01=count/(support.size*255**2),
            linf_rgb01=1/255,clipping_used=False,quantization_rounding_used=False)
        if record['distortion']!=expected:raise ValueError('Distortion summary mismatch')
        with Image.open(job_path.parent/'cover.png') as im:cover=np.array(im)
        for kind in ['reference','cover']:
            p=job_path.parent/(kind+'.png')
            rows.append(dict(task_id=task,kind=kind,path=p.relative_to(root).as_posix(),sha256=sha(p)))
        for kind in CONDITIONS:
            p=out/(kind+'.png');rec=record['conditions'][kind]
            if set(rec)!= {'path','sha256','pixel_sha256'} or rec['path']!=p.name or rec['sha256']!=sha(p):
                raise ValueError('Candidate hash mismatch')
            image_record(p)
            with Image.open(p) as im:pixels=np.array(im)
            if hashlib.sha256(pixels.tobytes()).hexdigest()!=rec['pixel_sha256']:
                raise ValueError('Pixel fingerprint mismatch')
            if not np.array_equal(np.abs(pixels.astype(np.int16)-cover.astype(np.int16)), support.astype(np.int16)):
                raise ValueError('Delivered distortion changed')
            rows.append(dict(task_id=task,kind=kind,path=p.relative_to(root).as_posix(),sha256=sha(p)))
    if read(root/'input_jobs_sealed.json')!=jobs:
        raise ValueError('Inputs changed since pre-attack freeze')
    return dict(jobs=jobs,queue=rows)


def seal(root):
    value=collect(root);write(Path(root)/'delivery_sealed.json',value);return value


def verified_queue(root):
    value=collect(root)
    if read(Path(root)/'delivery_sealed.json')!=value:raise ValueError('Seal changed')
    return value['queue']


def evaluate(root, callback):
    queue=verified_queue(root);results=[]
    for row in queue:
        path=Path(root)/row['path']
        if sha(path)!=row['sha256']:raise ValueError('Changed image before evaluation')
        result=callback(path,row['task_id'],row['kind'])
        if sha(path)!=row['sha256']:raise ValueError('Changed image during evaluation')
        results.append(dict(input=row,result=result))
    verified_queue(root)
    return results
