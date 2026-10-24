"""Native calibration contracts. Importing does not initialize CUDA/model libraries."""
import ast,importlib.util,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
sys.path.insert(0,str(BASE/'cover_pilot'));import contract as c;import runtime as r
sys.path.insert(0,str(BASE/'parallel_execution'));import launcher as launch;import scheduler as sched
ROOT=r.ROOT;POINTS=(20,50,100,150,151)
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def update_code(path):
    tree=ast.parse(Path(path).read_bytes());loop=next(n for n in tree.body if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='step')
    body=[]
    for node in loop.body:
        if isinstance(node,ast.If):break
        body.append(node)
    if len(body)!=5:raise ValueError('Official update changed')
    return compile(ast.Module(body=body,type_ignores=[]),str(path),'exec')
def gate(runtime,out):
    launch.check_host(ROOT);cfg=r.verify_runtime(Path(runtime));d=sched.Device(**cfg['device'])
    expected=dict(CUDA_VISIBLE_DEVICES=d.uuid,CUDA_DEVICE_ORDER='PCI_BUS_ID',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if d.index==6 or any(os.environ.get(k)!=v for k,v in expected.items()):raise ValueError('Wrong environment')
    rows=[];idle=sched.verify_idle(d,launch.sample,rows.append);c.write(Path(out)/'device_preimport.json',dict(device=d.__dict__,idle=idle,samples=rows))
    if not idle:raise RuntimeError('Child device busy, preserve no retry')
    return cfg
def guard(scheduler,records):
    original=scheduler.set_timesteps
    def checked(*a,**kw):
        result=original(*a,**kw);ts=scheduler.timesteps.tolist()
        if ts!=list(range(1,982,20)):raise ValueError('Unexpected actual inverse timestep array')
        records.append(dict(timesteps=ts,endpoint_alpha_cumprod=float(scheduler.alphas_cumprod[ts[-1]])));return result
    scheduler.set_timesteps=checked
def validate_job(path,cfg):
    path=Path(path);j=c.read(path);c.keys(j,['schema','task_id','seed','reference','cover','proxy','native'])
    if j['schema']!=1 or j['task_id'] not in (1,2,3,4) or j['seed']!=31300+j['task_id'] or j['proxy']!=cfg['proxy'] or j['native']!=cfg['native']:raise ValueError('Frozen native job changed')
    for kind in ('reference','cover'):
        if j[kind]!=c.png_record(path.parent/(kind+'.png')):raise ValueError('Input changed')
    return j
def candidates(root):
    rows=[]
    for sid in range(1,5):
        out=root/f'attack_{sid}';job=root/'attack_inputs'/str(sid)/'job.json';frozen=c.read(out/'candidates_frozen.json')
        if frozen['job_sha256']!=c.sha(job) or not c.read(out/'execution.json')['outcome']['completed']:raise ValueError('Unsealed job')
        for n in POINTS:
            record=c.png_record(out/f'update_{n}.png')
            if frozen['images'][str(n)]!=record:raise ValueError('PNG changed')
            rows.append(dict(task_id=sid,actual_update=n,path=out.name+f'/update_{n}.png',image=record))
    return rows
