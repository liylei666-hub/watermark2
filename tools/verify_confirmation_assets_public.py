"""Verify public data-preparation evidence without downloading data or using models."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only verification')
import datetime,hashlib,json
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def verify(root):
 root=Path(root);out=root/'reports/confirmation100_assets_v1';protocol=root/'protocols/confirmation100_assets_v1.json';launch=read(out/'launch.json');ex=read(out/'execution.json');seal=read(out/'result_seal.json');state=read(out/'status.json')
 assert sha(protocol)==protocol.with_suffix('.sha256').read_text().strip()==launch['protocol_sha256']==sha(out/'protocol_snapshot.json')
 assert sha(root/'tools/prepare_confirmation100_assets.py')==launch['worker_sha256'] and sha(out/'execution.json')==seal['execution_sha256']
 for name,h in ex['files'].items():assert sha(out/name)==h
 coverage=read(out/'prior_coverage.json');events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
 freeze=next(e for e in events if e['event']=='rules_and_coverage_frozen');fetches=[e for e in events if e['event']=='fetch_started'];completed=[e for e in events if e['event']=='fetch_completed']
 assert freeze['coverage_sha256']==sha(out/'prior_coverage.json') and freeze['protocol_sha256']==sha(protocol)
 assert all(datetime.datetime.fromisoformat(e['at_utc'])>datetime.datetime.fromisoformat(freeze['at_utc']) for e in fetches)
 assert all(not x['path'].startswith(('private_eval/','datasets/','cache/','envs/')) for x in coverage['images'])
 assert read(out/'process.json')['cuda_visible_devices']=='' and launch['no_models'] and launch['no_service_credentials']
 after=read(out/'budget_after.json');assert after['worker_sha256']==launch['worker_sha256']
 assert after['budget']['artifact_bytes_excluding_existing_cache_env_git']<10*1024**3 and after['budget']['dataset_bytes']<=512*1024**2
 if not ex['completed']:
  assert ex['exit_code']==1 and state['state']=='blocked_or_failed_data_acquisition' and state['models_started']==0 and state['no_automatic_retry']
  assert len(fetches)==1 and len(completed)==0 and after['dataset_regular_files']==0 and after['budget']['dataset_bytes']==0 and seal['manifest_sha256'] is None
 return dict(status='passed',acquisition_status='blocked_at_official_metadata_tls_not_assets_ready',protocol_sha256=sha(protocol),coverage_sha256=sha(out/'prior_coverage.json'),worker_sha256=launch['worker_sha256'],sealed_artifacts=len(ex['files']),prior_image_count=len(coverage['images']),prior_image_decode_failures=len(coverage['image_failures']),metadata_documents_scanned=len(coverage['metadata_files']),known_prompt_hashes=len(coverage['known_prompt_hashes']),known_explicit_COCO_IDs=len(coverage['known_explicit_coco_ids']),metadata_attempts=len(fetches),successful_downloads=len(completed),dataset_files=after['dataset_regular_files'],dataset_bytes=after['budget']['dataset_bytes'],models_started=0,gpu_used=False,service_credentials_or_watermark_material_generated=False,independence_scope='Finite hash/pHash/metadata exclusions are not proof that all prior development use is absent.')
if __name__=='__main__':print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
