"""Frozen three-reference VAE control; reuse the bounded serial supervisor."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import datetime, importlib.util, json, shlex, subprocess, sys
from pathlib import Path
ROOT=Path('/data0/liyanlei/watermark_research'); CODE=Path(__file__).resolve().parent
PRIOR=ROOT/'runs/08_target_roundtrip_20261016T014337Z'
spec=importlib.util.spec_from_file_location('bounded08',ROOT/'scripts/target_roundtrip/control.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
c=b.c;read,write,sha=b.read,b.write,b.sha

def total_bytes(run):
    folders=[b.SOURCE,PRIOR,run,ROOT/'scripts/prompt_control',ROOT/'scripts/target_roundtrip',CODE]
    return sum(p.stat().st_size for folder in folders for p in folder.rglob('*') if p.is_file())

def guard(run):
    g=c.guard();p=read(run/'protocol.json')
    assert sha(run/'protocol.json')==(run/'protocol.sha256').read_text().strip()
    assert all(sha(f)==h for f,h in p['code_hashes'].items())
    assert all(sha(f)==h for f,h in p['input_hashes'].items())
    assert total_bytes(run)<10*1024**3
    return g

def prepare():
    assert not list((ROOT/'runs').glob('09_vae_roundtrip_*')), 'Inspect existing group; no repetitions'
    pre=c.guard();old=read(PRIOR/'group_execution.json')
    assert old['completed']==[101,102,103] and not old['failures']
    run=ROOT/'runs'/('09_vae_roundtrip_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    run.mkdir();write(run/'preflight.json',pre)
    with (run/'cpu_test.stdout').open('x') as so,(run/'cpu_test.stderr').open('x') as se:
        q=subprocess.run([str(c.PY),str(CODE/'test_workflow.py')],env=c.environment(),stdout=so,stderr=se,timeout=60)
    write(run/'cpu_test.json',dict(exit_code=q.returncode));assert q.returncode==0
    prior_protocol=read(PRIOR/'protocol.json')
    hashes={str(f):sha(f) for f in CODE.glob('*.py')}
    for folder,name in [('target_roundtrip','control.py'),('prompt_control','control.py'),('05_seed_pilot_20261013T041252Z','stage05.py')]:
        f=ROOT/'scripts'/folder/name;hashes[str(f)]=sha(f)
    p=dict(stage='09',created_at=c.now(),planned_seeds=[101,102,103],planned_model_processes=3,
        arms=['target_vae','proxy_vae'],data_role='evaluator_development_control',
        prior_gpu_process_seconds=old['cumulative_gpu_process_seconds'],total_limit_seconds=7200,
        per_process_limit_seconds=1200,max_new_bytes=10*1024**3,allowed_gpus=[0,1,2],selected_gpu=0,uuid=c.UUID,
        code_hashes=hashes,input_hashes=prior_protocol['input_hashes'],model_snapshots=pre['model_snapshots'],
        rationale='Measure VAE-only reconstruction effects before assigning full roundtrip differences to diffusion models',
        intervention='RGB/255 -> 2*x-1 -> VAE posterior mean -> scaled latent / same scaling factor -> VAE decode -> standard PIL quantization -> target inversion',
        planned_contrasts=['reconstruction versus original reference inversion cosine','target VAE versus proxy VAE, paired by reference'],
        generation_calls=0,retries=0,selection_by_target_score=False,geometry_threshold=None,geometry_accepted=None,
        stop_rule='Any engineering/replay/hash/device/budget failure stops group with no retry')
    write(run/'protocol.json',p);c.save_text(run/'protocol.sha256',sha(run/'protocol.json')+'\n')
    for seed in p['planned_seeds']:
        cfg=read(PRIOR/f'seed_{seed}'/'config.json')
        for key in ['prompts','generation_guidance','generation_steps']:cfg.pop(key)
        cfg.update(stage='09',arms=p['arms'],generation_calls=0,protocol_sha256=sha(run/'protocol.json'),
            proxy_snapshot=pre['model_snapshots']['Manojb/stable-diffusion-2-1-base'])
        case=run/f'seed_{seed}';case.mkdir();write(case/'config.json',cfg)
        command=[str(c.PY),str(CODE/'experiment.py'),str(case)]
        write(case/'command.json',dict(argv=command,config_sha256=sha(case/'config.json')))
        e=c.environment(False);names=['CUDA_VISIBLE_DEVICES','CUDA_DEVICE_ORDER','HF_HOME','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_IMPLICIT_TOKEN','PYTHONDONTWRITEBYTECODE']
        c.save_text(case/'command.sh','cd '+shlex.quote(str(c.UP))+'\n'+' '.join(k+'='+shlex.quote(e[k]) for k in names)+' '+shlex.join(command)+'\n')
    print(run,flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':
        b.guard=guard;b.total_bytes=total_bytes
        b.execute(Path(sys.argv[2]))
    else:raise ValueError('prepare or run')
