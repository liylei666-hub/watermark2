"""Serial continuation of never-launched work, with durable resource waiting."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU supervisor requires empty visibility')
import datetime,fcntl,json,signal,subprocess,sys,time
from pathlib import Path
from common import c,r,IDS,METHODS,verify_source,delivery,verify_delivery,validate_job
from gate import gate_functions

RUNTIME=r.ROOT/'protocols/27_method_runtime_r4.json'
ATTACK=r.ROOT/'protocols/27_method_attack_runtime_r4.json'
EVAL=r.ROOT/'protocols/27_method_eval_runtime_r4.json'
SCRIPTS=Path(__file__).resolve().parent
PYTHON=r.ROOT/'envs/semantic_forgery_py310/bin/python'

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,value):
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)
def event(root,**value):
    with (root/'scheduler_events.jsonl').open('a') as f:f.write(json.dumps(dict(at_utc=now(),**value))+'\n');f.flush();os.fsync(f.fileno())
def state(root,name,meta):
    if name in meta['completed']:verify_source(root,meta['completed'][name]);return 'inherited_completed'
    if name in meta['failed']:verify_source(root,meta['failed'][name]);return 'recorded_failure'
    out=root/name
    if (out/'execution.json').exists():
        ex=c.read(out/'execution.json')
        return 'completed' if ex['completed'] and ex['exit_code']==0 and not ex['timed_out'] else 'failed'
    if out.exists():return 'unknown_launched'  # Any prelaunch reservation also prevents ambiguous relaunch.
    return 'never_started'
def counts(root,meta):
    values=[state(root,f'attack_outputs/{sid}/{m}',meta) for sid in IDS for m in METHODS]
    return dict(completed=sum(v in ('completed','inherited_completed') for v in values),failed=sum(v in ('recorded_failure','failed') for v in values),not_started=values.count('never_started'),unknown=values.count('unknown_launched'))
def initialize(root,cfg):
    source=c.inside(r.ROOT,cfg['source_run'])
    for rel,h in cfg['source_files'].items():
        if c.sha(c.inside(source,rel))!=h:raise ValueError('Original source changed: '+rel)
    if root.exists():
        if c.read(root/'launch_intent.json')['runtime_sha256']!=c.sha(RUNTIME):raise ValueError('Different existing continuation')
        if c.read(root/'inheritance.json')!=cfg['inheritance']:raise ValueError('Inheritance changed')
    else:
        actual={p.relative_to(r.ROOT).as_posix():c.sha(p) for p in (r.ROOT/'runs').rglob('execution.json') if p.relative_to(r.ROOT/'runs').parts[0][:2].isdigit() and int(p.relative_to(r.ROOT/'runs').parts[0][:2])>=7}
        if actual!=cfg['historical_execution_hashes']:raise ValueError('Historical execution inventory changed')
        root.mkdir();c.write(root/'launch_intent.json',dict(runtime_sha256=c.sha(RUNTIME),created_at_utc=now(),controller_pid=os.getpid(),new_attacks=32,new_evaluation_batches=3))
        c.write(root/'inheritance.json',cfg['inheritance'])
    for rel,h in cfg['copied_files'].items():
        dst=c.inside(root,rel)
        if dst.exists():
            if c.sha(dst)!=h:raise ValueError('Inherited artifact changed: '+rel)
        else:
            dst.parent.mkdir(parents=True,exist_ok=True)
            with dst.open('xb') as f:f.write(c.inside(source,rel).read_bytes())
            if c.sha(dst)!=h:raise ValueError('Inherited copy mismatch')
    for sid in IDS:
        for m in METHODS:validate_job(root/'attack_inputs'/str(sid)/(m+'.json'))
    return cfg['inheritance']

def choose(root,cfg,name,meta):
    scope=gate_functions()
    while True:
        records=[]
        for index,uuid in cfg['allowed_gpu_uuids'].items():
            try:
                scope['verify_idle'](scope['snapshot'],records.append,int(index),uuid,'NVIDIA GeForce RTX 3090')
                event(root,event='resource_acquired',task=name,index=int(index),uuid=uuid)
                return int(index),uuid,records
            except RuntimeError as exc:
                if str(exc) not in ('GPU compute process present','GPU did not meet stable idle conditions within bounded sampling'):raise
                event(root,event='device_busy',task=name,index=int(index),reason=str(exc),samples=records)
                records=[]
        checked=now();next_check=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=cfg['resource_recheck_seconds'])).isoformat()
        atomic(root/'scheduler_status.json',dict(status='waiting_resource',task=name,last_checked_at_utc=checked,next_check_at_utc=next_check,counts=counts(root,meta)))
        event(root,event='waiting_resource',task=name,next_check_at_utc=next_check)
        time.sleep(cfg['resource_recheck_seconds'])

def run_child(root,cfg,meta,name,script,args):
    previous=state(root,name,meta)
    if previous in ('completed','inherited_completed','recorded_failure'):return
    if previous!='never_started':raise RuntimeError('Launched or ambiguous task cannot be retried: '+name+' '+previous)
    index,uuid,records=choose(root,cfg,name,meta)
    size=sum(p.stat().st_size for group in ('runs','reports','scripts','protocols') for p in (r.ROOT/group).rglob('*') if p.is_file())
    if size+512*1024**2>=cfg['max_new_bytes']:raise RuntimeError('Storage safety margin exhausted')
    r.verify_runtime(RUNTIME)
    out=root/name;out.mkdir(parents=True)
    with (out/'preflight.jsonl').open('x') as f:
        for row in records:f.write(json.dumps(row)+'\n')
    runtime=ATTACK if script=='attack.py' else EVAL
    command=[str(PYTHON),str(SCRIPTS/script),str(runtime)]+list(map(str,args))+[str(out)]
    env=dict(os.environ,CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES=uuid,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HOME=str(r.ROOT/'cache/huggingface'),PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    c.write(out/'command.json',dict(argv=command,gpu_index=index,gpu_uuid=uuid,runtime_sha256=c.sha(runtime),watchdog_seconds=cfg['watchdog_seconds']))
    started=now();start=time.monotonic();timeout=False
    with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
        proc=subprocess.Popen(command,env=env,cwd=r.ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
        c.write(out/'process.json',dict(pid=proc.pid,started_at_utc=started,proc_start_ticks=Path(f'/proc/{proc.pid}/stat').read_text().split()[21]))
        atomic(root/'scheduler_status.json',dict(status='running',task=name,pid=proc.pid,started_at_utc=started,counts=counts(root,meta)))
        try:code=proc.wait(timeout=cfg['watchdog_seconds'])
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(proc.pid,signal.SIGTERM)
            try:code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);code=proc.wait()
    elapsed=time.monotonic()-start;marker='COMPLETED_COVER_'+('ATTACK' if script=='attack.py' else 'EVALUATION')
    success=code==0 and (out/'summary.json').is_file() and c.read(out/'summary.json').get('completed') is True and marker in (out/'stdout.log').read_text()
    c.write(out/'execution.json',dict(exit_code=code,timed_out=timeout,elapsed_seconds=elapsed,started_at_utc=started,completed=success,model_processes_started=1,gpu_index=index,gpu_uuid=uuid))
    event(root,event='child_completed',task=name,completed=success,elapsed_seconds=elapsed);print(json.dumps(dict(child=name,completed=success,elapsed_seconds=elapsed)),flush=True)
    if not success:raise RuntimeError('New child failed; retain and investigate without retry: '+name)

def main():
    cfg=r.verify_runtime(RUNTIME);root=c.inside(r.ROOT,cfg['run_dir'])
    with (r.ROOT/'runs/.imprint_delivery.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);meta=initialize(root,cfg)
        if (root/'status.json').exists() and c.read(root/'status.json').get('completed'):return
        event(root,event='controller_started',pid=os.getpid(),runtime_sha256=c.sha(RUNTIME))
        try:
            for sid in IDS:
                order=METHODS[(sid-1)%3:]+METHODS[:(sid-1)%3]
                for method in order:run_child(root,cfg,meta,f'attack_outputs/{sid}/{method}','attack.py',[root/'attack_inputs'/str(sid)/(method+'.json')])
            rows=delivery(root)
            if (root/'delivery_sealed.json').exists():verify_delivery(root)
            else:c.write(root/'delivery_sealed.json',dict(rows=rows,sealed_at_utc=now(),target_detection_calls_before_seal=0))
            for batch in range(3):run_child(root,cfg,meta,'evaluate_'+str(batch),'evaluate.py',[root,batch,r.ROOT/cfg['private_folder']])
            verify_delivery(root);r.verify_runtime(RUNTIME)
            atomic(root/'status.json',dict(status='completed_with_recorded_failure',completed=True,candidates=35,failed_attack_tasks=1,planned_attack_tasks=36,target_inversions=59,new_model_processes=35,feedback_to_attack=False,full_defense_acceptance=None))
            atomic(root/'scheduler_status.json',dict(status='completed',counts=counts(root,meta),checked_at_utc=now()))
        except BaseException as exc:
            event(root,event='controller_stopped',reason=str(exc),error_type=type(exc).__name__)
            atomic(root/'status.json',dict(completed=False,status='stopped',reason=str(exc),error_type=type(exc).__name__,counts=counts(root,meta),unchanged_retry_allowed=False));raise
    print('COMPLETED_METHOD_COMPARISON_CONTINUATION',flush=True)

if __name__=='__main__':
    if sys.argv[1:]!=['--run']:raise SystemExit('Explicit --run required')
    main()
