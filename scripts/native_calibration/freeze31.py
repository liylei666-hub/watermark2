import sys,datetime
from common31 import c,r,ROOT,HERE,BASE,launch
def main(commit):
    launch.check_host(ROOT)
    if len(commit)!=40:raise ValueError('Exact source commit required')
    design=c.read(ROOT/'protocols/31_native_calibration_execution.json');previous=c.read(ROOT/'protocols/29_quality_controller_runtime.json')
    if design['native']['actual_adam_updates']!=151 or design['native']['checkpoint_actual_updates']!=[20,50,100,150,151]:raise ValueError('Endpoint revision changed')
    pins=dict(previous['code_hashes'])
    for p in HERE.glob('*.py'):pins[str(p)]=c.sha(p)
    pins[str(ROOT/'protocols/31_native_calibration_execution.json')]=c.sha(ROOT/'protocols/31_native_calibration_execution.json')
    pins[str(r.UPSTREAM/'run_imprint_forgery.py')]=c.sha(r.UPSTREAM/'run_imprint_forgery.py')
    for task in design['tasks']:
        p=ROOT/task['cover']
        if c.sha(p)!=task['cover_sha256']:raise ValueError('Cover file changed')
        pins[str(p)]=c.sha(p)
    devices=[dict(index=0,uuid='GPU-aafaf524-a6f4-f646-a2b5-7d243e80c8a5',model='NVIDIA GeForce RTX 3090'),dict(index=1,uuid='GPU-af8ecfa2-a36f-798c-9762-0a3cfb8a1fcd',model='NVIDIA GeForce RTX 3090')]
    paths={role:{str(d['index']):f'protocols/31_{role}_{d["index"]}_runtime.json' for d in devices} for role in ('attacker','evaluator')}
    allpaths=[ROOT/p for mapping in paths.values() for p in mapping.values()]+[ROOT/'protocols/31_controller_runtime.json']
    if any(p.exists() for p in allpaths):raise ValueError('Already frozen; no overwrite')
    hashes={role:{} for role in paths}
    for role in paths:
        for device in devices:
            idx=str(device['index']);sources=pins if role=='evaluator' else {n:h for n,h in pins.items() if n.endswith('.py') or n.startswith(design['proxy']['snapshot']+'/')}
            cfg=dict(stage='31',role=role,source_commit=commit,versions=previous['versions'],code_hashes=sources,device=device,proxy=design['proxy'],native=design['native'])
            if role=='evaluator':cfg['design']=design
            p=ROOT/paths[role][idx];c.write(p,cfg)
            with p.with_suffix('.sha256').open('x') as f:f.write(c.sha(p)+'\n')
            r.verify_runtime(p);hashes[role][idx]=c.sha(p)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');name='31_native_calibration_'+stamp
    cfg=dict(stage='31',role='controller',source_commit=commit,versions=previous['versions'],code_hashes=pins,design=design,devices=devices,per_device_runtime=paths,role_hashes=hashes,run_dir='runs/'+name,private_folder='private_eval/'+name)
    p=ROOT/'protocols/31_controller_runtime.json';c.write(p,cfg)
    with p.with_suffix('.sha256').open('x') as f:f.write(c.sha(p)+'\n')
    r.verify_runtime(p);print(__import__('json').dumps(dict(run_dir=cfg['run_dir'],controller_runtime_sha256=c.sha(p),role_hashes=hashes,devices=devices),indent=2))
if __name__=='__main__':main(sys.argv[1])
