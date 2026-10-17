"""CPU supervisor for a single frozen paired pilot; serial children, no retries."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU supervisor requires empty visibility')
import datetime
import fcntl
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import contract as c
import bundle as b
import runtime as r

PYTHON=r.ROOT/'envs/semantic_forgery_py310/bin/python'
SCRIPTS=r.ROOT/'scripts/cover_pilot'
PROTOCOL=r.ROOT/'protocols/17_cover_pilot.json'
RUNTIME=r.ROOT/'protocols/17_cover_runtime.json'
ATTACK_RUNTIME=r.ROOT/'protocols/17_cover_attack_runtime.json'


def run_child(name,script,args,root,cfg):
    out=root/name;out.mkdir(parents=True)
    spec=importlib.util.spec_from_file_location('idle_gate',r.ROOT/'scripts/gpu_preflight.py')
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    chosen=None
    with (out/'preflight.jsonl').open('x') as f:
        def record(value):f.write(json.dumps(value)+'\n');f.flush();os.fsync(f.fileno())
        for index,uuid in cfg['allowed_gpu_uuids'].items():
            try:
                gate.verify_idle(gate.snapshot,record,int(index),uuid,'NVIDIA GeForce RTX 3090')
                chosen=(index,uuid);break
            except Exception as exc:record(dict(event='device_unavailable',index=index,reason=str(exc)))
    if chosen is None:
        c.write(out/'status.json',dict(status='stopped_no_idle_gpu',model_processes_started=0))
        raise RuntimeError('No idle authorized GPU; pilot stopped without retry')
    size=sum(p.stat().st_size for folder in ['runs','reports','scripts','protocols'] for p in (r.ROOT/folder).rglob('*') if p.is_file())
    if size+512*1024**2>=cfg['max_new_bytes']:raise RuntimeError('Storage gate: insufficient safety margin')
    r.verify_runtime(RUNTIME)
    env=dict(os.environ,CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES=chosen[1],
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HOME=str(r.ROOT/'cache/huggingface'),
        PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    child_runtime=ATTACK_RUNTIME if script=='attack.py' else RUNTIME
    command=[str(PYTHON),str(SCRIPTS/script),str(child_runtime)]+[str(a) for a in args]+[str(out)]
    c.write(out/'command.json',dict(argv=command,gpu_index=int(chosen[0]),gpu_uuid=chosen[1],runtime_sha256=c.sha(child_runtime),watchdog_seconds=cfg['watchdog_seconds']))
    start=time.monotonic();at=datetime.datetime.now(datetime.timezone.utc).isoformat();timed_out=False
    with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
        proc=subprocess.Popen(command,env=env,cwd=r.ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
        c.write(out/'process.json',dict(pid=proc.pid,started_at_utc=at))
        try:code=proc.wait(timeout=cfg['watchdog_seconds'])
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(proc.pid,signal.SIGTERM)
            try:code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);code=proc.wait()
    seconds=time.monotonic()-start
    marker={'prepare.py':'COMPLETED_COVER_PREPARATION','attack.py':'COMPLETED_COVER_ATTACK','evaluate.py':'COMPLETED_COVER_EVALUATION'}[script]
    success=code==0 and (out/'summary.json').is_file() and marker in (out/'stdout.log').read_text()
    if success:success=c.read(out/'summary.json').get('completed') is True
    c.write(out/'execution.json',dict(exit_code=code,timed_out=timed_out,elapsed_seconds=seconds,
        started_at_utc=at,completed=success,model_processes_started=1,gpu_index=int(chosen[0]),gpu_uuid=chosen[1]))
    print(json.dumps(dict(child=name,completed=success,elapsed_seconds=seconds)),flush=True)
    if not success:raise RuntimeError('Child failed: '+name)
    return out


def main():
    cfg=r.verify_runtime(RUNTIME)
    if c.sha(PROTOCOL)!=PROTOCOL.with_suffix('.sha256').read_text().strip():raise ValueError('Protocol hash mismatch')
    with (r.ROOT/'runs/.imprint_delivery.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if list((r.ROOT/'runs').glob('17_cover_pilot_*/launch_intent.json')):
            raise RuntimeError('Pilot already attempted; inspect existing state')
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        root=r.ROOT/'runs'/('17_cover_pilot_'+stamp);root.mkdir()
        c.write(root/'launch_intent.json',dict(stage='17',protocol_sha256=c.sha(PROTOCOL),runtime_sha256=c.sha(RUNTIME),controller_pid=os.getpid(),planned_model_processes=9))
        print('RUN_DIR '+str(root),flush=True)
        try:
            ref=run_child('evaluator_private/reference','prepare.py',[PROTOCOL,'reference'],root,cfg)
            cover=run_child('evaluator_private/cover','prepare.py',[PROTOCOL,'cover'],root,cfg)
            prepared=dict(version=1,tasks=[])
            for task in [1,2,3]:
                row=dict(task_id=task)
                for kind,folder in [('reference',ref),('cover',cover)]:
                    path=folder/str(task)/(kind+'.png');row[kind]=c.png_record(path);row[kind]['path']=path.relative_to(root).as_posix()
                prepared['tasks'].append(row)
            c.write(root/'prepared_images.json',prepared)
            plan=b.export_jobs(root,prepared)
            # Export freezes image/job hashes before the first attack process.
            c.write(root/'attack_plan_frozen.json',dict(sha256=c.sha(root/'attack_plan.json')))
            for entry in plan['jobs']:
                job=c.inside(root,entry['job_path'])
                if c.sha(job)!=entry['job_sha256']:raise ValueError('Job changed before launch')
                run_child(entry['output_path'],'attack.py',[job],root,cfg)
            if c.sha(root/'attack_plan.json')!=c.read(root/'attack_plan_frozen.json')['sha256']:raise ValueError('Plan changed')
            c.seal_delivery(root,root/'attack_plan.json')
            run_child('evaluator_results','evaluate.py',[PROTOCOL,root],root,cfg)
            c.write(root/'status.json',dict(status='completed',completed=True,model_processes_started=9,full_defense_acceptance=None))
        except BaseException as exc:
            c.write(root/'status.json',dict(status='stopped',completed=False,error_type=type(exc).__name__,reason=str(exc),
                model_processes_started=len(list(root.rglob('process.json'))),unchanged_retry_allowed=False))
            raise
    print('COMPLETED_COVER_PILOT',flush=True)


if __name__=='__main__':
    if sys.argv[1:]!=['--run']:raise SystemExit('Explicit --run required')
    main()
