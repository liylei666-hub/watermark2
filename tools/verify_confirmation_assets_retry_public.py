"""Offline verification of the frozen rules and two terminal metadata attempts."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only verification')
import datetime,hashlib,json
from pathlib import Path
from verify_confirmation_assets_public import verify as verify_first

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))

def verify(root):
 root=Path(root);first=verify_first(root);out=root/'reports/confirmation100_assets_v1_retry1';old=root/'reports/confirmation100_assets_v1'
 launch=read(out/'launch.json');ex=read(out/'execution.json');seal=read(out/'result_seal.json');after=read(out/'budget_after.json');transfer=read(out/'transfer_001.json')
 assert sha(out/'execution.json')==seal['execution_sha256'] and not ex['completed'] and ex['exit_code']==1
 for name,h in ex['files'].items():assert sha(out/name)==h
 assert sha(root/'tools/retry_confirmation100_assets.py')==launch['transport_wrapper_sha256']==after['transport_wrapper_sha256']
 assert launch['worker_sha256']==first['worker_sha256']==after['worker_sha256']
 assert launch['protocol_sha256']==first['protocol_sha256']==sha(out/'protocol_snapshot.json')
 assert launch['coverage_sha256']==first['coverage_sha256']==sha(out/'prior_coverage.json')
 assert launch['first_execution_sha256']==sha(old/'execution.json')==after['first_execution_sha256']
 assert sha(old/'result_seal.json')==after['first_result_seal_sha256']
 events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
 freeze=next(x for x in events if x['event']=='rules_and_coverage_frozen');fetches=[x for x in events if x['event']=='fetch_started']
 assert len(fetches)==1 and fetches[0]['url']==read(root/'protocols/confirmation100_assets_v1.json')['metadata_url']==transfer['url']
 assert datetime.datetime.fromisoformat(freeze['at_utc'])<datetime.datetime.fromisoformat(fetches[0]['at_utc'])
 assert not any(x['event']=='fetch_completed' for x in events)
 assert transfer['exit_code']==28 and transfer['http_code']=='000' and transfer['partial_body_bytes']==0
 assert transfer['connect_timeout_seconds']==20 and transfer['total_timeout_seconds']==120
 assert not transfer['tls_verification_disabled'] and not transfer['redirects_followed'] and transfer['automatic_retries']==0
 assert after['budget']['dataset_bytes']==0 and after['dataset_regular_files']==1 and after['files'][0]['bytes']==0
 assert after['first_attempt_regular_files']==[] and after['active_acquisition_processes']==[]
 assert after['budget']['artifact_bytes_excluding_existing_cache_env_git']<10*1024**3
 assert read(out/'process.json')['cuda_visible_devices']=='' and launch['no_models'] and launch['no_service_credentials']
 assert read(out/'status.json')['models_started']==0 and seal['manifest_sha256'] is None
 return dict(status='passed',metadata_attempts_total=2,successful_downloads=0,covers=0,captions=0,metadata_response_body_bytes=0,first_sealed_artifacts=first['sealed_artifacts'],recovery_sealed_artifacts=len(ex['files']),protocol_sha256=first['protocol_sha256'],coverage_sha256=first['coverage_sha256'],selector_sha256=first['worker_sha256'],transport_wrapper_sha256=launch['transport_wrapper_sha256'],unchanged_first_failure=True,active_acquisition_processes=0,models_started=0,gpu_used=False,interpretation='Both official HTTPS requests timed out without an HTTP response. No conclusion about certificate rejection, permission denial or all official routes. Acquisition stopped after the one authorized retry.')

if __name__=='__main__':print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
