"""Finalize already acquired data after a closed receipt-publication race; no network."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only completion')
import hashlib,json,shutil,sys,time,urllib.parse
from pathlib import Path
import prepare_confirmation100_assets_v11_completion as a
from confirmation_ready import publish_ready
a.DATA=a.ROOT/'datasets/confirmation100_relay_v11'
a.PUBLIC=a.ROOT/'reports/confirmation100_assets_v11_completed'
PREVIOUS=a.ROOT/'reports/confirmation100_assets_relay_v11'
BANK_SHA='a8bbd98d20797e58da8edd4f949f75d779078437cc9cb159c6eb3216daae48fe'
INDEX=0
def snapshot(folder):return {p.relative_to(folder).as_posix():dict(bytes=p.stat().st_size,sha256=a.sha(p)) for p in folder.rglob('*') if p.is_file()}
def bank():
 path=PREVIOUS/'prior_coverage.json';assert a.sha(path)==BANK_SHA;return a.read(path)
def fetch(url,dest,limit):
 global INDEX
 index=INDEX;INDEX+=1;label=f'{index:03d}'
 request=a.read(PREVIOUS/'requests'/(label+'.json'));assert request['canonical_url']==url
 prior=PREVIOUS/'transfers'/(label+'.json')
 if not prior.exists():prior=a.DATA/'incoming'/(label+'.ready.json')
 receipt=a.read(prior);assert receipt['index']==index and receipt['canonical_url']==url and receipt['http_status']==200 and not receipt['tls_verification_disabled']
 actual=urllib.parse.urlsplit(receipt['actual_source_url']);assert actual.scheme=='https' and actual.hostname=='s3.us-east-1.amazonaws.com' and not actual.query and not actual.fragment and not actual.username and not actual.password
 assert actual.path=='/images.cocodataset.org'+urllib.parse.urlsplit(url).path
 body=dest if dest.exists() else a.DATA/'incoming'/(label+'.bin')
 assert body.is_file() and body.stat().st_size==receipt['bytes']<=limit and a.sha(body)==receipt['sha256']
 staging=a.PUBLIC/'atomic_receipts'/(label+'.uploading');final=a.PUBLIC/'atomic_receipts'/(label+'.ready.json');a.write(staging,receipt);publish_ready(staging,final,body)
 if not dest.exists():
  with body.open('rb') as src,dest.open('xb') as output:shutil.copyfileobj(src,output)
  assert a.sha(dest)==receipt['sha256']
 a.write(a.PUBLIC/'transfers'/(label+'.json'),receipt)
 return dict(url=url,effective_url=receipt['actual_source_url'],path=dest.relative_to(a.ROOT).as_posix(),bytes=dest.stat().st_size,sha256=a.sha(dest),headers={},relay_receipt='transfers/'+label+'.json',already_acquired_bytes_reused=True,network_requests=0)
a.fetch=fetch;a.prior_coverage=bank
def complete():
 a.host()
 if a.PUBLIC.exists():raise ValueError('Offline completion already admitted; inspect before any retry')
 old=a.read(PREVIOUS/'execution.json');assert old['exit_code']==1 and not old['completed']
 assert a.sha(PREVIOUS/'execution.json')==a.read(PREVIOUS/'result_seal.json')['execution_sha256']
 for name,h in old['files'].items():assert a.sha(PREVIOUS/name)==h
 bank();plan=a.read(a.ROOT/'protocols/confirmation100_v11_completion.json')
 for name,h in plan['implementation_hashes'].items():assert a.sha(a.ROOT/name)==h
 for name,h in a.read(a.PROTOCOL)['implementation_hashes'].items():assert a.sha(a.ROOT/name)==h
 assert len(list((PREVIOUS/'requests').glob('*.json')))==101
 before=snapshot(a.DATA);a.PUBLIC.mkdir();(a.PUBLIC/'atomic_receipts').mkdir();(a.PUBLIC/'transfers').mkdir()
 a.write(a.PUBLIC/'before_snapshot.json',dict(at_utc=a.now(),files=before,previous_execution_sha256=a.sha(PREVIOUS/'execution.json')))
 a.write(a.PUBLIC/'launch.json',dict(created_at_utc=a.now(),protocol_sha256=a.sha(a.PROTOCOL),worker_sha256=a.sha(a.__file__),relay_wrapper_sha256=a.sha(__file__),completion_plan_sha256=a.sha(a.ROOT/'protocols/confirmation100_v11_completion.json'),budget_before=a.budget(),no_models=True,no_service_credentials=True,network_requests=0,scope='Offline reuse of100 fully received original images; retain closed v1.1 failure and all prior file bytes'))
 begin=time.perf_counter();error=None;code=0
 try:
  a.prepare()
  for name,record in before.items():assert (a.DATA/name).stat().st_size==record['bytes'] and a.sha(a.DATA/name)==record['sha256']
  for name,h in old['files'].items():assert a.sha(PREVIOUS/name)==h
  a.write(a.PUBLIC/'prior_data_preservation.json',dict(status='passed',prior_files=len(before),prior_file_bytes_unchanged=True,added_files=sorted(set(snapshot(a.DATA))-set(before)),closed_failure_report_files_unchanged=True))
 except BaseException as e:
  code=1;error=e;a.event('offline_completion_failed',reason=str(e));a.status('blocked_or_failed_data_acquisition',reason=str(e),models_started=0,no_automatic_retry=True)
 complete=code==0
 a.write(a.PUBLIC/'execution.json',dict(completed=complete,exit_code=code,wall_seconds=time.perf_counter()-begin,finished_at_utc=a.now(),network_requests=0,files={p.relative_to(a.PUBLIC).as_posix():a.sha(p) for p in a.PUBLIC.rglob('*') if p.is_file()}))
 a.write(a.PUBLIC/'result_seal.json',dict(execution_sha256=a.sha(a.PUBLIC/'execution.json'),manifest_sha256=a.sha(a.PUBLIC/'manifest.json') if complete else None))
 print(json.dumps(dict(completed=complete,exit_code=code,report=str(a.PUBLIC),wall_seconds=time.perf_counter()-begin)))
 if error:raise error
if __name__=='__main__':
 if sys.argv[1:]!=['--complete']:raise SystemExit('Explicit --complete required')
 complete()
