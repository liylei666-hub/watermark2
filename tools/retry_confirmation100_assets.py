"""One authorized transport recovery; retain frozen selector and first failure."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only data acquisition')
import json,resource,signal,subprocess,sys,time
from pathlib import Path
import prepare_confirmation100_assets as a
FIRST=a.PUBLIC
ORIGINAL_DATA=a.DATA
FROZEN_SOURCE='0432e5418d669059554a37e5d0aff28ee3b3b47e10d25510132008137eb76fa0'
FROZEN_COVERAGE='a8bbd98d20797e58da8edd4f949f75d779078437cc9cb159c6eb3216daae48fe'
a.PUBLIC=a.ROOT/'reports/confirmation100_assets_v1_retry1'
a.DATA=a.ROOT/'datasets/confirmation100_v1_retry1'

def coverage():
 assert a.sha(FIRST/'prior_coverage.json')==FROZEN_COVERAGE
 return a.read(FIRST/'prior_coverage.json')

def fetch(url,dest,limit):
 if not a.allowed_url(url):raise ValueError('Frozen official HTTPS origin required')
 part=dest.with_suffix(dest.suffix+'.part')
 if dest.exists() or part.exists():raise ValueError('Existing transfer: inspect; never overwrite or retry')
 a.budget(limit)
 index=sum(1 for _ in a.PUBLIC.glob('transfer_*.json'))+1
 label=f'transfer_{index:03d}'
 raw_headers=dest.with_suffix(dest.suffix+'.headers')
 err=a.PUBLIC/(label+'.stderr.log')
 cmd=['curl','--silent','--show-error','--fail','--proto','=https','--connect-timeout','20','--max-time','120','--retry','0','--max-filesize',str(limit),'--dump-header',str(raw_headers),'--output',str(part),'--write-out','%{http_code}\n%{ssl_verify_result}\n%{time_total}\n',url]
 a.event('fetch_started',url=url,destination=dest.relative_to(a.ROOT).as_posix(),attempt_policy='single_GET_no_redirect_no_retry',connect_timeout_seconds=20,total_timeout_seconds=120)
 def limits():resource.setrlimit(resource.RLIMIT_FSIZE,(limit,limit))
 start=time.perf_counter()
 with err.open('xb') as stderr:
  child=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=stderr,stdin=subprocess.DEVNULL,preexec_fn=limits)
  try:stdout,_=child.communicate(timeout=130)
  except subprocess.TimeoutExpired:
   child.kill();stdout,_=child.communicate();raise RuntimeError('Owned curl hard timeout; partial retained; no retry')
 fields=stdout.decode('ascii',errors='replace').splitlines()
 record=dict(url=url,exit_code=child.returncode,http_code=fields[0] if fields else None,ssl_verify_result=fields[1] if len(fields)>1 else None,curl_time_total=fields[2] if len(fields)>2 else None,wall_seconds=time.perf_counter()-start,partial_body_bytes=part.stat().st_size if part.exists() else 0,partial_sha256=a.sha(part) if part.exists() else None,connect_timeout_seconds=20,total_timeout_seconds=120,tls_verification_disabled=False,redirects_followed=False,automatic_retries=0,curl_stdout=stdout.decode('ascii',errors='replace'),stderr_path=err.name)
 a.write(a.PUBLIC/(label+'.json'),record)
 if child.returncode!=0 or record['http_code']!='200' or record['ssl_verify_result']!='0':
  a.event('fetch_failed',**record)
  raise RuntimeError('Bounded official HTTPS GET failed; curl exit '+str(child.returncode)+'; HTTP '+str(record['http_code'])+'; see '+label+'.stderr.log; no further retry')
 if not part.exists() or part.stat().st_size>limit:raise RuntimeError('Transfer body/byte cap invalid')
 headers={}
 for line in raw_headers.read_text(encoding='latin1').splitlines():
  if ':' in line:
   k,v=line.split(':',1)
   if k.lower() in ('content-type','content-length','etag','last-modified'):headers[k.lower()]=v.strip()
 if 'text/html' in headers.get('content-type','').lower():raise RuntimeError('HTML/access page retained; stop')
 if 'content-length' in headers and int(headers['content-length'])!=part.stat().st_size:raise RuntimeError('Incomplete body retained')
 part.rename(dest)
 result=dict(url=url,effective_url=url,path=dest.relative_to(a.ROOT).as_posix(),bytes=dest.stat().st_size,sha256=a.sha(dest),headers=headers,transport_receipt=label+'.json')
 a.event('fetch_completed',**result);return result

a.prior_coverage=coverage
a.fetch=fetch

def start():
 a.host()
 assert a.sha(a.__file__)==FROZEN_SOURCE
 assert a.read(FIRST/'execution.json')['exit_code']==1 and not a.read(FIRST/'execution.json')['completed']
 assert a.sha(FIRST/'execution.json')==a.read(FIRST/'result_seal.json')['execution_sha256']
 coverage()
 if any(p.is_file() for p in ORIGINAL_DATA.rglob('*')):raise ValueError('First attempt has unexpected files; inspect')
 if a.DATA.exists() or a.PUBLIC.exists():raise ValueError('Recovery already admitted; inspect rather than relaunch')
 before=a.budget(512*1024**2)
 assert a.sha(a.PROTOCOL)==a.PROTOCOL.with_suffix('.sha256').read_text().strip()
 a.DATA.mkdir();a.PUBLIC.mkdir()
 a.write(a.PUBLIC/'launch.json',dict(created_at_utc=a.now(),protocol_sha256=a.sha(a.PROTOCOL),worker_sha256=FROZEN_SOURCE,transport_wrapper_sha256=a.sha(__file__),coverage_sha256=FROZEN_COVERAGE,first_execution_sha256=a.sha(FIRST/'execution.json'),budget_before=before,no_models=True,no_service_credentials=True,recovery='One parent-authorized same-URL HTTPS metadata retry; frozen selector/coverage unchanged',curl_version=subprocess.check_output(['curl','--version'],text=True).splitlines()[0]))
 with (a.PUBLIC/'supervisor.stdout.log').open('xb') as out,(a.PUBLIC/'supervisor.stderr.log').open('xb') as err:
  child=subprocess.Popen([sys.executable,__file__,'--supervise'],cwd=a.ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
 a.write(a.PUBLIC/'supervisor.json',dict(pid=child.pid,started_at_utc=a.now()));print('STARTED_DATA_RECOVERY',child.pid,str(a.PUBLIC))

def supervise():
 start=time.perf_counter();reason=None
 with (a.PUBLIC/'stdout.log').open('xb') as out,(a.PUBLIC/'stderr.log').open('xb') as err:
  child=subprocess.Popen([sys.executable,__file__,'--worker'],cwd=a.ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
  a.write(a.PUBLIC/'process.json',dict(pid=child.pid,started_at_utc=a.now(),cuda_visible_devices='',worker_sha256=FROZEN_SOURCE,transport_wrapper_sha256=a.sha(__file__)))
  while child.poll() is None:
   if time.perf_counter()-start>7200:reason='owned_data_worker_watchdog';os.killpg(child.pid,signal.SIGKILL);break
   time.sleep(1)
  code=child.wait()
 complete=code==0 and a.read(a.PUBLIC/'status.json')['state']=='completed'
 a.write(a.PUBLIC/'execution.json',dict(completed=complete,exit_code=code,stop_reason=reason,wall_seconds=time.perf_counter()-start,finished_at_utc=a.now(),files={p.name:a.sha(p) for p in a.PUBLIC.iterdir() if p.is_file() and not p.name.startswith('supervisor.')}))
 a.write(a.PUBLIC/'result_seal.json',dict(execution_sha256=a.sha(a.PUBLIC/'execution.json'),manifest_sha256=a.sha(a.PUBLIC/'manifest.json') if complete else None))

if __name__=='__main__':
 a.host()
 if sys.argv[1:]==['--start']:start()
 elif sys.argv[1:]==['--supervise']:supervise()
 elif sys.argv[1:]==['--verify']:print(json.dumps(a.verify_assets(),indent=2))
 elif sys.argv[1:]==['--worker']:
  try:
   assert a.sha(__file__)==a.read(a.PUBLIC/'launch.json')['transport_wrapper_sha256']
   a.prepare()
  except BaseException as e:
   a.event('acquisition_stopped_no_retry',error_type=type(e).__name__,reason=str(e));a.status('blocked_or_failed_data_acquisition',error_type=type(e).__name__,reason=str(e),models_started=0,no_automatic_retry=True);raise
 else:raise SystemExit('Explicit execution mode required')
