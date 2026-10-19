"""Explicit detached launch, recording this controller's identity and log paths."""
import os,subprocess,sys
from pathlib import Path
from common import ROOT,BASE,c,r,launch,sched


def main():
    if sys.argv[1:]!=['--launch']:raise SystemExit('Explicit --launch required')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('Supervisor visibility must be empty')
    launch.check_host(ROOT)
    runtime=ROOT/'protocols/28_staged_controller_runtime.json';cfg=r.verify_runtime(runtime)
    with sched.project_lock(ROOT/'runs/.imprint_delivery.lock'):
        if (ROOT/cfg['run_dir']).exists():raise ValueError('Existing run; launch refused')
    report=ROOT/'reports'/Path(cfg['run_dir']).name;report.mkdir()
    command=[sys.executable,str(BASE/'staged_inversion/control.py'),'--run',str(runtime)]
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
    with (report/'controller_stdout.log').open('xb') as stdout,(report/'controller_stderr.log').open('xb') as stderr:
        child=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
    receipt=dict(pid=child.pid,argv=command,started_at_utc=sched.now(),run_dir=cfg['run_dir'],
        runtime_sha256=c.sha(runtime),source_commit=cfg['source_commit'],maximum_concurrent_gpu_children=1)
    c.write(report/'controller_launch.json',receipt)
    print(__import__('json').dumps(receipt,indent=2))


if __name__=='__main__':main()
