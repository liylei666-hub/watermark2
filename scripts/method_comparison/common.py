"""Image-only attack interfaces and complete-candidate seals for the fixed comparison."""
import importlib.util
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cover_pilot'))
import contract as c
import runtime as r

METHODS=('imprint','jain','delivery')
IDS=list(range(1,13))
PARAMETERS=dict(imprint=c.METHODS['imprint'],jain=c.METHODS['jain'],
    delivery=dict(updates=10,learning_rate=.01,inversion_steps=50,inversion_guidance=1.,inversion_prompt='',mask=None,
                  objective='continuous_decode_clamp_encode_inverse_mse',gradient='split_exact_chain',quantization_backward='not_in_objective'))

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def private_module():
    return module('comparison_private',Path(__file__).resolve().parents[1]/'reference_reliability/private_state.py')

def validate_job(path):
    path=Path(path);job=c.read(path)
    c.keys(job,['version','task_id','method','seed','reference','cover','proxy','parameters'])
    if job['version']!=1 or job['task_id'] not in IDS or job['method'] not in METHODS or job['seed']!=27300+job['task_id']:raise ValueError('Unexpected attack task')
    expected=dict(model_id=c.PROXY_ID,revision=c.PROXY_REVISION,snapshot=c.PROXY_SNAPSHOT,dtype='float32',resolution=512)
    if job['proxy']!=expected or job['parameters']!=PARAMETERS[job['method']]:raise ValueError('Attack settings changed')
    for kind in ('reference','cover'):
        if job[kind]!=c.png_record(path.parent/(kind+'.png')):raise ValueError('Attack image changed')
    return job

def copy(source,target):
    source=Path(source);target=Path(target)
    if source.is_symlink():raise ValueError('Unexpected symlink')
    digest=c.sha(source)
    with target.open('xb') as f:f.write(source.read_bytes())
    if c.sha(target)!=digest:raise ValueError('Copy mismatch')

def delivery(root):
    root=Path(root);rows=[]
    for task in IDS:
        for method in METHODS:
            job=root/'attack_inputs'/str(task)/(method+'.json');validate_job(job)
            output=root/'attack_outputs'/str(task)/method
            record=c.read(output/'candidate_frozen.json')
            expected=dict(task_id=task,method=method,job_sha256=c.sha(job),image=c.png_record(output/'candidate.png'))
            if record!=expected:raise ValueError('Candidate changed')
            execution=c.read(output/'execution.json')
            if not execution['completed'] or execution['exit_code']!=0:raise ValueError('Incomplete attack')
            rows.append(dict(**expected,path=(output/'candidate.png').relative_to(root).as_posix()))
    return dict(candidates=rows)

def verify_delivery(root):
    actual=delivery(root)
    sealed=c.read(Path(root)/'delivery_sealed.json')
    if sealed['delivery']!=actual:raise ValueError('Delivery seal mismatch')
    return sealed

def rng(folder,phase):
    import random,numpy as np,torch
    state=np.random.get_state()
    with (folder/('rng_'+phase+'.npz')).open('xb') as f:np.savez(f,numpy_state=state[1],torch_cpu=torch.get_rng_state().numpy(),torch_cuda=torch.cuda.get_rng_state(0).cpu().numpy())
    c.write(folder/('rng_'+phase+'.json'),dict(python=random.getstate(),numpy_algorithm=state[0],numpy_position=state[2],numpy_has_gauss=state[3],numpy_cached_gaussian=state[4]))
