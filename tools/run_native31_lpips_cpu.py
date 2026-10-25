"""One-shot detached CPU metric supervisor. Never starts an attack or GPU job."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU supervisor required')
import signal,subprocess,sys,time
from pathlib import Path
from native31_lpips_cpu import ROOT,WEIGHTS,host,inputs,read,sha,write,now
OUT=ROOT/'reports/31_native_calibration_lpips_20261025'
def supervise():
 plan=read(OUT/'plan.json');worker=ROOT/'tools/native31_lpips_cpu.py'
 if sha(worker)!=plan['worker_sha256']:raise ValueError('Worker changed')
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',TORCH_HOME='/home/liyanlei/.cache/torch',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1')
 started=time.perf_counter();reason=None
 with (OUT/'stdout.log').open('xb') as stdout,(OUT/'stderr.log').open('xb') as stderr:
  child=subprocess.Popen([sys.executable,str(worker),str(OUT)],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
  write(OUT/'process.json',dict(pid=child.pid,started_at_utc=now(),proc_start_ticks=Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()[19],environment={k:env[k] for k in ['CUDA_VISIBLE_DEVICES','TORCH_HOME','HF_HUB_OFFLINE','OMP_NUM_THREADS','MKL_NUM_THREADS']},worker_sha256=sha(worker)))
  while child.poll() is None:
   if time.perf_counter()-started>1800 or sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())>16*1024**2:
    reason='owned_cpu_worker_watchdog_or_output_limit';os.killpg(child.pid,signal.SIGKILL);break
   time.sleep(.5)
  code=child.wait()
 completed=code==0 and reason is None and (OUT/'summary.json').exists() and read(OUT/'summary.json')['completed'] is True and 'COMPLETED_POSTHOC_LPIPS_CPU' in (OUT/'stdout.log').read_text().splitlines()
 write(OUT/'execution.json',dict(completed=completed,exit_code=code,stop_reason=reason,process_wall_seconds=time.perf_counter()-started,finished_at_utc=now(),files={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and not p.name.startswith('supervisor.')}));write(OUT/'result_seal.json',dict(execution_sha256=sha(OUT/'execution.json'),summary_sha256=sha(OUT/'summary.json') if completed else None));print('CPU_SUPPLEMENT_TERMINAL',completed,flush=True)
def start():
 host()
 if OUT.exists():raise ValueError('Existing supplement; inspect instead of repeating')
 worker=ROOT/'tools/native31_lpips_cpu.py';pairs=inputs()
 for name,digest in WEIGHTS.items():
  if sha(name)!=digest:raise ValueError('Existing asset mismatch; no download')
 OUT.mkdir();write(OUT/'plan.json',dict(created_at_utc=now(),posthoc=True,worker_sha256=sha(worker),supervisor_sha256=sha(__file__),weights=WEIGHTS,inputs=pairs,watchdog_seconds=1800,max_output_bytes=16*1024**2,cpu_threads=4,gpu_allowed=False,implicit_downloads_allowed=False))
 with (OUT/'supervisor.stdout.log').open('xb') as stdout,(OUT/'supervisor.stderr.log').open('xb') as stderr:
  child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--supervise'],cwd=ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
 write(OUT/'launch.json',dict(supervisor_pid=child.pid,started_at_utc=now(),plan_sha256=sha(OUT/'plan.json')));print('STARTED_CPU_SUPPLEMENT',child.pid,str(OUT))
if __name__=='__main__':
 host()
 if len(sys.argv)==2 and sys.argv[1]=='--supervise':supervise()
 elif len(sys.argv)==1:start()
 else:raise SystemExit('Unexpected argument')
