"""Run the frozen CPU selector with hash-verified Windows-relayed data only."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU data work only')
import hashlib,json,signal,subprocess,sys,time,urllib.parse
from pathlib import Path
import prepare_confirmation100_assets as a
FIRST=a.PUBLIC
a.DATA=a.ROOT/'datasets/confirmation100_relay_v1'
a.PUBLIC=a.ROOT/'reports/confirmation100_assets_relay_v1'
INCOMING=a.DATA/'incoming'
SOURCE_SHA='0432e5418d669059554a37e5d0aff28ee3b3b47e10d25510132008137eb76fa0'
BANK_SHA='a8bbd98d20797e58da8edd4f949f75d779078437cc9cb159c6eb3216daae48fe'
ARCHIVE_SHA='113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268'
sequence=0
def bank():
 assert a.sha(FIRST/'prior_coverage.json')==BANK_SHA
 return a.read(FIRST/'prior_coverage.json')

def fetch(url,dest,limit):
 global sequence
 assert a.allowed_url(url)
 ident=sequence;sequence+=1
 if ident==0:assert url==a.read(a.PROTOCOL)['metadata_url']
 else:assert urllib.parse.urlsplit(url).path.startswith('/val2017/') and len(Path(url).stem)==12
 if ident>150 or dest.exists():raise ValueError('Frozen transfer count/exclusive output gate')
 label=f'{ident:03d}';request=a.PUBLIC/'requests'/(label+'.json');ready=INCOMING/(label+'.ready.json');body=INCOMING/(label+'.bin')
 a.write(request,dict(index=ident,canonical_url=url,destination=dest.relative_to(a.ROOT).as_posix(),limit_bytes=limit,created_at_utc=a.now()))
 a.event('relay_requested',index=ident,canonical_url=url)
 start=time.monotonic()
 while not ready.exists():
  if (INCOMING/(label+'.failed.json')).exists():raise RuntimeError('Windows transfer failed; preserve evidence, no automatic retry')
  if time.monotonic()-start>1800:raise RuntimeError('Data relay wait expired; no repeated acquisition')
  time.sleep(1)
 receipt=a.read(ready);assert receipt['index']==ident and receipt['canonical_url']==url
 assert receipt['tls_verification_disabled'] is False and receipt['http_status'] in (200,206)
 source=urllib.parse.urlsplit(receipt['actual_source_url'])
 assert source.scheme=='https' and source.hostname in ('storage.googleapis.com','scidata.sjtu.edu.cn','s3.us-east-1.amazonaws.com') and not source.username and not source.password
 assert body.is_file() and body.stat().st_size==receipt['bytes']<=limit and a.sha(body)==receipt['sha256']
 if ident==0:
  assert receipt['full_archive_sha256']==ARCHIVE_SHA
  import zipfile
  with zipfile.ZipFile(body) as z:assert hashlib.sha256(z.read('annotations/captions_val2017.json')).hexdigest()==receipt['member_sha256']
 else:
  basename=urllib.parse.urlsplit(url).path.rsplit('/',1)[1]
  if source.hostname in ('storage.googleapis.com','s3.us-east-1.amazonaws.com'):assert source.path=='/images.cocodataset.org/val2017/'+basename and not source.query
  else:assert receipt['zip_member']=='val2017/'+basename and source.path=='/records/7rp0x-d6e31/files/val2017.zip'
 a.budget();body.rename(dest)
 a.write(a.PUBLIC/'transfers'/(label+'.json'),receipt)
 result=dict(url=url,effective_url=receipt['actual_source_url'],path=dest.relative_to(a.ROOT).as_posix(),bytes=dest.stat().st_size,sha256=a.sha(dest),headers={},relay_receipt='transfers/'+label+'.json')
 a.event('fetch_completed',**result);return result
a.fetch=fetch;a.prior_coverage=bank

def start():
 a.host();assert a.sha(a.__file__)==SOURCE_SHA;bank()
 if a.PUBLIC.exists():raise ValueError('Selector already admitted; inspect, never restart')
 assert INCOMING.exists() and (INCOMING/'000.ready.json').exists()
 before=a.budget();a.PUBLIC.mkdir();(a.PUBLIC/'requests').mkdir();(a.PUBLIC/'transfers').mkdir()
 a.write(a.PUBLIC/'launch.json',dict(created_at_utc=a.now(),protocol_sha256=a.sha(a.PROTOCOL),worker_sha256=SOURCE_SHA,relay_wrapper_sha256=a.sha(__file__),coverage_sha256=BANK_SHA,budget_before=before,no_models=True,no_service_credentials=True,transport='Windows verified HTTPS acquisition plus SSH/SCP; original selector unchanged; metadata container contains only byte-identical captions_val2017 member'))
 with (a.PUBLIC/'supervisor.stdout.log').open('xb') as out,(a.PUBLIC/'supervisor.stderr.log').open('xb') as err:
  child=subprocess.Popen([sys.executable,__file__,'--supervise'],cwd=a.ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
 a.write(a.PUBLIC/'supervisor.json',dict(pid=child.pid,started_at_utc=a.now()));print(json.dumps(dict(pid=child.pid,report=str(a.PUBLIC))))

def supervise():
 begin=time.perf_counter();reason=None
 with (a.PUBLIC/'stdout.log').open('xb') as out,(a.PUBLIC/'stderr.log').open('xb') as err:
  child=subprocess.Popen([sys.executable,__file__,'--worker'],cwd=a.ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4'),stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
  a.write(a.PUBLIC/'process.json',dict(pid=child.pid,started_at_utc=a.now(),cuda_visible_devices=''))
  while child.poll() is None:
   if time.perf_counter()-begin>7200:reason='owned_data_worker_watchdog';os.killpg(child.pid,signal.SIGKILL);break
   time.sleep(1)
  code=child.wait()
 complete=code==0 and a.read(a.PUBLIC/'status.json')['state']=='completed'
 records={p.relative_to(a.PUBLIC).as_posix():a.sha(p) for p in a.PUBLIC.rglob('*') if p.is_file() and not p.name.startswith('supervisor.')}
 a.write(a.PUBLIC/'execution.json',dict(completed=complete,exit_code=code,stop_reason=reason,wall_seconds=time.perf_counter()-begin,finished_at_utc=a.now(),files=records));a.write(a.PUBLIC/'result_seal.json',dict(execution_sha256=a.sha(a.PUBLIC/'execution.json'),manifest_sha256=a.sha(a.PUBLIC/'manifest.json') if complete else None))

def poll():
 a.host();pending=[]
 for p in sorted((a.PUBLIC/'requests').glob('*.json')):
  if not (INCOMING/(p.stem+'.ready.json')).exists() and not (INCOMING/(p.stem+'.failed.json')).exists():pending.append(a.read(p))
 print(json.dumps(dict(pending=pending,status=a.read(a.PUBLIC/'status.json') if (a.PUBLIC/'status.json').exists() else None,terminal=a.read(a.PUBLIC/'execution.json') if (a.PUBLIC/'execution.json').exists() else None,dataset_bytes=a.treebytes(a.DATA))))

if __name__=='__main__':
 a.host()
 if sys.argv[1:]==['--start']:start()
 elif sys.argv[1:]==['--supervise']:supervise()
 elif sys.argv[1:]==['--poll']:poll()
 elif sys.argv[1:]==['--verify']:print(json.dumps(a.verify_assets()))
 elif sys.argv[1:]==['--worker']:
  try:
   assert a.sha(__file__)==a.read(a.PUBLIC/'launch.json')['relay_wrapper_sha256'];a.prepare()
  except BaseException as e:a.event('acquisition_stopped_no_retry',error_type=type(e).__name__,reason=str(e));a.status('blocked_or_failed_data_acquisition',error_type=type(e).__name__,reason=str(e),models_started=0,no_automatic_retry=True);raise
 else:raise SystemExit('Explicit mode required')
