"""Server-only CPU controller. Resume verified artifacts; fail on changed inputs."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') not in (None,''):raise SystemExit('CPU controller requires CUDA_VISIBLE_DEVICES empty')
os.environ['CUDA_VISIBLE_DEVICES']=''
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='2'
import argparse, datetime, fcntl, importlib.metadata, json, platform, subprocess, sys, time, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stage02.core import dump, sha256, HOST_GPUS
from stage03.protocol import prepare, save_once
OUT=ROOT/'outputs/stage03'

def snapshot():
    result=dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    for key,query in [('gpus','index,uuid,pci.bus_id,name,memory.total,memory.used,memory.free,utilization.gpu'),('processes','gpu_uuid,pid,process_name,used_gpu_memory')]:
        flag='--query-gpu=' if key=='gpus' else '--query-compute-apps='
        result[key]=subprocess.check_output(['nvidia-smi','-i','5,7',flag+query,'--format=csv'],text=True,timeout=15)
    return result

def preserve_stage02():
    paths=[ROOT/'configs/stage02.json']
    for folder in ['data/stage02','outputs/stage02','research']:
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and (folder!='research' or p.name.startswith('02_'))]
    record={str(p.relative_to(ROOT)):sha256(p) for p in paths}
    save_once(OUT/'stage02_preservation.json',record)

def launch(config, task, phase=None):
    idx=5 if task=='clip_sscd' else 7
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=HOST_GPUS[idx],XFORMERS_DISABLED='1',CUBLAS_WORKSPACE_CONFIG=':4096:8',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    command=[sys.executable,'-m','stage03.generate','--config','configs/stage03.json','--phase',phase] if task=='generate' else [sys.executable,'-m','stage03.features','--config','configs/stage03.json','--task',task]
    name=task+('_'+phase if phase else ''); timeout=config['generator']['gpu_budget_seconds']+120 if task=='generate' else config['features']['worker_timeout_seconds']
    logpath=OUT/'logs'/(name+'.log')
    snapshots=OUT/'logs'/(name+'_resources.jsonl')
    with logpath.open('a') as log, snapshots.open('a') as observations:
        proc=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
        print('launched',name,proc.pid,HOST_GPUS[idx],flush=True);start=time.monotonic();last=0.
        try:
            while proc.poll() is None:
                if time.monotonic()-last>=30:
                    observations.write(json.dumps(snapshot())+'\n');observations.flush();last=time.monotonic()
                    print(name,'elapsed',int(time.monotonic()-start),flush=True)
                if time.monotonic()-start>timeout:raise TimeoutError(name+' wall timeout')
                time.sleep(2)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=20)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
        if proc.returncode:raise RuntimeError(name+' exited '+str(proc.returncode)+'; see '+str(logpath))

def main(config,through):
    os.chdir(ROOT);(OUT/'logs').mkdir(parents=True,exist_ok=True)
    if platform.node()!='server249' or ROOT!=Path(config['server_project']) or sys.prefix!=config['environment_prefix']:raise RuntimeError('Must run in the verified server project/environment')
    if Path('/.dockerenv').exists() or os.environ.get('SLURM_JOB_ID') or os.environ.get('NVIDIA_VISIBLE_DEVICES'):raise RuntimeError('Allocation requires mapping review')
    locks=ROOT/'.stage02_locks';locks.mkdir(exist_ok=True)
    lock=(locks/'pipeline.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    preserve_stage02();before=snapshot();dump(OUT/'gpu_before_latest.json',before)
    if not (OUT/'gpu_before.json').exists():dump(OUT/'gpu_before.json',before)
    for line in before['gpus'].splitlines()[1:]:
        fields=[v.strip() for v in line.split(',')]
        if HOST_GPUS.get(int(fields[0]))!=fields[1]:raise RuntimeError('Host GPU mapping changed')
    versions={p:importlib.metadata.version(p) for p in ['torch','torchvision','diffusers','transformers','accelerate','safetensors','numpy','Pillow']}
    save_once(OUT/'environment.json',dict(host=platform.node(),python=sys.version,executable=sys.executable,versions=versions))
    prepare(ROOT,config)
    with (OUT/'logs/unittest.log').open('w') as log:
        tested=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],stdout=log,stderr=subprocess.STDOUT)
    dump(OUT/'tests.json',dict(exit_code=tested.returncode,command='CUDA_VISIBLE_DEVICES= python -m unittest discover -s tests -v'))
    if tested.returncode:raise RuntimeError('Unit tests failed')
    dump(OUT/'run_status.json',dict(status='prepared',generation=False,features=False,evaluation=False,audit=False))
    registry_path=OUT/'generator_files.json'
    if not registry_path.exists() or json.loads(registry_path.read_text()).get('status')!='complete':
        raise RuntimeError('Generator assets not yet completely transferred and verified')
    if not (OUT/'preflight.json').exists() or json.loads((OUT/'preflight.json').read_text())['status']!='passed':launch(config,'generate','preflight')
    if through=='preflight':return
    launch(config,'generate','main')
    from stage03.data import prepare_data
    prepare_data(ROOT,config)
    dump(OUT/'run_status.json',dict(status='generated',generation=True,features=False,evaluation=False,audit=False))
    if through=='generation':return
    launch(config,'clip_sscd');launch(config,'dinov2')
    dump(OUT/'run_status.json',dict(status='features',generation=True,features=True,evaluation=False,audit=False))
    from stage03.evaluate import evaluate
    evaluate(ROOT,config)
    dump(OUT/'run_status.json',dict(status='evaluation',generation=True,features=True,evaluation=True,audit=False))
    from stage03.audit import audit
    audit(ROOT,config);preserve_stage02()
    dump(OUT/'run_status.json',dict(status='audit_complete',generation=True,features=True,evaluation=True,audit=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--through',choices=['preflight','generation','audit'],default='audit');a=p.parse_args()
    try:main(json.loads(Path(a.config).read_text()),a.through)
    except Exception as e:
        OUT.mkdir(parents=True,exist_ok=True)
        previous=json.loads((OUT/'run_status.json').read_text()) if (OUT/'run_status.json').exists() else {}
        dump(OUT/'run_status.json',dict(previous,status='incomplete',error=repr(e),traceback=traceback.format_exc()));raise
    finally:
        if platform.node()=='server249':
            dump(OUT/'gpu_after.json',snapshot())
            dump(OUT/'gpu_binding.json',dict(whitelist=HOST_GPUS,workers=[json.loads(p.read_text()) for p in sorted(OUT.glob('binding_*.json'))],before=json.loads((OUT/'gpu_before.json').read_text()) if (OUT/'gpu_before.json').exists() else None,after=json.loads((OUT/'gpu_after.json').read_text())))
