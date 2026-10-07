"""CPU orchestrator; launches one UUID-restricted worker for each authorized GPU."""
import os
# Respect pre-existing allocation instead of overriding it.
prior_visibility=os.environ.get('CUDA_VISIBLE_DEVICES')
if prior_visibility not in (None,''):
    raise SystemExit('Run CPU orchestrator with CUDA_VISIBLE_DEVICES empty; do not override an existing allocation')
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ.setdefault('OMP_NUM_THREADS','2');os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import argparse, datetime, fcntl, json, platform, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stage02.core import HOST_GPUS, dump, validate_gpu_config

def snapshot():
    rec={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    for key,query in [('gpus','--query-gpu=index,uuid,pci.bus_id,name,memory.total,memory.used,memory.free,utilization.gpu'),('processes','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory')]:
        rec[key]=subprocess.check_output(['nvidia-smi','-i','5,7',query,'--format=csv'],text=True)
    return rec

def main(config):
    os.chdir(ROOT);out=ROOT/'outputs/stage02'
    lockdir=ROOT/'.stage02_locks';lockdir.mkdir(exist_ok=True)
    runlock=(lockdir/'pipeline.lock').open('w');fcntl.flock(runlock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if out.exists():
        archive=ROOT/'outputs/runs'/datetime.datetime.now(datetime.timezone.utc).strftime('stage02_%Y%m%dT%H%M%S_%fZ')
        archive.parent.mkdir(parents=True,exist_ok=True);out.rename(archive)
    (out/'logs').mkdir(parents=True,exist_ok=True)
    if sys.prefix!=config['environment_prefix']:raise RuntimeError('unexpected Python environment')
    if config['batch_size']!=1 or config['target_frr']!=.05:raise ValueError('stage02 fixes batch=1 and target FRR=0.05')
    if Path('/.dockerenv').exists() or os.environ.get('SLURM_JOB_ID') or os.environ.get('NVIDIA_VISIBLE_DEVICES'):
        raise RuntimeError('Container/scheduler allocation requires explicit mapping review before GPU launch')
    for task,idx in [('clip_sscd',5),('dinov2',7)]:validate_gpu_config(config,HOST_GPUS[idx],task)
    before=snapshot();dump(out/'gpu_before.json',before)
    subprocess.run([sys.executable,'scripts/inspect_stage02_env.py'],check=True,stdout=(out/'logs/environment.log').open('w'),env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
    for line in before['gpus'].splitlines()[1:]:
        fields=[x.strip() for x in line.split(',')]
        if HOST_GPUS.get(int(fields[0]))!=fields[1]:raise RuntimeError('inventory UUID mismatch')
        if float(fields[6].split()[0])<2500:raise RuntimeError('authorized GPU free memory below 2500 MiB')
    # CPU unit tests are part of the entry point and gate all actual GPU work.
    with (out/'logs/unittest.log').open('w') as f:
        test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
    dump(out/'tests.json',dict(command='python -m unittest discover -s tests -v',exit_code=test.returncode))
    if test.returncode:raise RuntimeError('CPU tests failed')
    from stage02.data import prepare
    manifest=prepare(ROOT,config['seed']);dump(out/'run_config.json',config)
    workers=[];logs=[]
    for task,idx in [('clip_sscd',5),('dinov2',7)]:
        env=dict(os.environ,CUDA_VISIBLE_DEVICES=HOST_GPUS[idx],OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',XFORMERS_DISABLED='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
        log=(out/f'logs/{task}.log').open('w');logs.append(log)
        proc=subprocess.Popen([sys.executable,'-m','stage02.worker','--config',str(out/'run_config.json'),'--task',task],env=env,stdout=log,stderr=subprocess.STDOUT)
        workers.append((task,proc,idx));print('launched',task,proc.pid,HOST_GPUS[idx],flush=True)
    observations=[];dump(out/'gpu_during.json',observations);started=time.monotonic();last=started;high_load=0
    try:
        while any(p.poll() is None for _,p,_ in workers):
            time.sleep(2)
            if time.monotonic()-last>=30:
                snap=snapshot();observations.append(snap);dump(out/'gpu_during.json',observations);last=time.monotonic()
                row5=next(r for r in snap['gpus'].splitlines()[1:] if r.split(',')[0].strip()=='5')
                high_load=high_load+1 if float(row5.split(',')[-1].strip().split()[0])>=90 else 0
                if high_load>=2:
                    for task,p,idx in workers:
                        if idx==5 and p.poll() is None:
                            p.terminate();dump(out/'resource_adjustment.json',dict(reason='GPU5 utilization >=90% for two samples; own worker stopped',pid=p.pid))
                print('workers active',[(t,p.pid,p.poll()) for t,p,_ in workers],flush=True)
            if time.monotonic()-started>config['worker_timeout_seconds']:
                for _,p,_ in workers:
                    if p.poll() is None:p.terminate()
                dump(out/'resource_adjustment.json',dict(reason='own worker timeout',seconds=config['worker_timeout_seconds']));break
    finally:
        for _,p,_ in workers:
            if p.poll() is None:
                p.terminate()
            p.wait(timeout=20)
        for f in logs:f.close()
        dump(out/'gpu_after.json',snapshot())
    bindings=[]
    for task,p,idx in workers:
        bp=out/f'binding_{task}.json';b=json.loads(bp.read_text()) if bp.exists() else {'task':task,'pid':p.pid,'host_index':idx,'status':'incomplete'}
        b['exit_code']=p.returncode;bindings.append(b)
    dump(out/'gpu_binding.json',dict(whitelist=HOST_GPUS,workers=bindings,before=before,scope='Only recorded subprocesses are covered by these execution records'))
    from stage02.evaluate import evaluate
    metrics=evaluate(ROOT,manifest)
    if metrics['status']=='complete' and all(p.returncode==0 for _,p,_ in workers):
        with (out/'logs/runtime_checks.log').open('w') as f:
            audit=subprocess.run([sys.executable,'scripts/check_stage02_results.py'],stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
        if audit.returncode:raise RuntimeError('real artifact audit failed')
    print(json.dumps(metrics,indent=2),flush=True)
    return 0 if metrics['status']=='complete' and all(p.returncode==0 for _,p,_ in workers) else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--refresh-features',action='store_true');args=p.parse_args()
    config=json.loads(Path(args.config).read_text())
    config['refresh_features']=args.refresh_features
    try:code=main(config)
    except Exception as e:
        import traceback
        dump(ROOT/'outputs/stage02/run_status.json',dict(status='incomplete',error=str(e),traceback=traceback.format_exc()));raise
    dump(ROOT/'outputs/stage02/run_status.json',dict(status='complete' if code==0 else 'incomplete',exit_code=code));sys.exit(code)
