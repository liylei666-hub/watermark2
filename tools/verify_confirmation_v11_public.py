"""Verify public confirmation manifests and captured private-file integrity receipts."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only public verification')
import datetime,difflib,hashlib,json,unicodedata,urllib.parse
from pathlib import Path
from confirmation_attribution import parse_flickr_source
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
def verify(root):
 root=Path(root);out=root/'reports/confirmation100_assets_v11_completed';p=root/'protocols/confirmation100_assets_v11.json';protocol=read(p);old=read(root/'protocols/confirmation100_assets_v1.json');launch=read(out/'launch.json');m=read(out/'manifest.json');ex=read(out/'execution.json');seal=read(out/'result_seal.json')
 assert ex['completed'] and ex['exit_code']==0 and sha(out/'execution.json')==seal['execution_sha256'] and sha(out/'manifest.json')==seal['manifest_sha256']
 for name,h in ex['files'].items():assert sha(out/name)==h
 assert sha(p)==p.with_suffix('.sha256').read_text().strip()==launch['protocol_sha256']==m['protocol_sha256']==sha(out/'protocol_snapshot.json')
 for name,h in protocol['implementation_hashes'].items():assert sha(root/name)==h
 assert sha(root/'tools/prepare_confirmation100_assets_v11_completion.py')==launch['worker_sha256']
 assert sha(root/'tools/complete_confirmation_v11_offline.py')==launch['relay_wrapper_sha256']
 completion=root/'protocols/confirmation100_v11_completion.json';assert sha(completion)==launch['completion_plan_sha256']==completion.with_suffix('.sha256').read_text().strip()
 for name,h in read(completion)['implementation_hashes'].items():assert sha(root/name)==h
 assert read(out/'prior_data_preservation.json')['prior_file_bytes_unchanged']
 for name in ('seed','counts','ranking','exclusions','preprocessing','budgets'):assert protocol[name]==old[name]
 assert sha(out/'prior_coverage.json')==protocol['prior_coverage_sha256']==m['coverage_sha256']=='a8bbd98d20797e58da8edd4f949f75d779078437cc9cb159c6eb3216daae48fe'
 v1=(root/'tools/prepare_confirmation100_assets.py').read_text(encoding='utf8');v11=(root/'tools/prepare_confirmation100_assets_v11.py').read_text(encoding='utf8')
 expected=''.join(difflib.unified_diff(v1.splitlines(keepends=True),v11.splitlines(keepends=True),fromfile='frozen_v1_selector',tofile='v1.1_selector'))
 assert expected==(root/'protocols/confirmation100_v11_selector.diff').read_text(encoding='utf8')
 assert len(m['covers'])==len(m['captions'])==len(m['pairs'])==100
 coverids={x['coco_id'] for x in m['covers']};captionids={x['source_image']['coco_id'] for x in m['captions']}
 assert len(coverids)==len(captionids)==100 and not coverids&captionids
 assert len({norm(x['caption']) for x in m['captions']})==100
 assert len({x['flickr_photo_id'] for x in m['covers']}|{x['source_image']['flickr_photo_id'] for x in m['captions']})==200
 for image in m['covers']+[x['source_image'] for x in m['captions']]:
  source=parse_flickr_source(image['flickr_url']);assert source and source['flickr_photo_id']==image['flickr_photo_id'] and source['creator_account_from_source_url']==image['creator_account_from_source_url']
  assert image['creator_display_name'] is None and image['redistribution_status']=='not_cleared_do_not_publish_image'
  u=urllib.parse.urlsplit(image['license']['url']);assert u.hostname in ('creativecommons.org','www.creativecommons.org') and u.path.startswith('/licenses/by/') and u.path.rstrip('/').split('/')[-1] in ('2.0','3.0','4.0')
 assert [(x['cover_coco_id'],x['caption_annotation_id'],x['caption_source_coco_id']) for x in m['pairs']]==[(c['coco_id'],p['caption_annotation_id'],p['source_image']['coco_id']) for c,p in zip(m['covers'],m['captions'])]
 for x in m['captions']:assert hashlib.sha256(norm(x['caption']).encode()).hexdigest()==x['normalized_caption_sha256']
 transfers=[read(x) for x in (out/'transfers').glob('*.json')];byid={int(Path(urllib.parse.urlsplit(x['canonical_url']).path).stem):x for x in transfers if x['index']!=0}
 for c in m['covers']:
  t=byid[c['coco_id']];assert t['sha256']==c['source_file']['sha256'] and t['bytes']==c['source_file']['bytes'] and t['http_status']==200 and not t['tls_verification_disabled']
 assert not m['target_generation_started'] and not m['attack_optimization_started'] and not m['key_message_or_service_credentials_generated']
 replay=read(out/'selection_replay_verification.json');assert replay['status']=='passed' and replay['manifest_sha256']==sha(out/'manifest.json') and replay['deterministic_cover_order_replayed'] and replay['deterministic_caption_order_replayed'] and replay['disjoint_source_identities']==200
 assert datetime.datetime.fromisoformat(protocol['frozen_at_utc'])<datetime.datetime.fromisoformat(launch['created_at_utc'])
 storage=read(out/'storage_audit.json');assert storage['combined_dataset_copy_bytes']<=536870912 and storage['conservative_combined_workspace_plus_server_bytes']<=10737418240
 assert not any(x.suffix.lower() in ('.png','.jpg','.jpeg','.zip') for x in out.rglob('*') if x.is_file())
 return dict(status='passed',sealed_execution_artifacts=len(ex['files']),covers=100,unique_captions=100,disjoint_source_identities=200,parser_correction_diff_verified=True,frozen_seed_ranking_exclusions_preprocessing_unchanged=True,manifest_sha256=sha(out/'manifest.json'),downloaded_image_candidates=len(byid),public_transfer_hash_bindings=100,server_original_and_RGB512_file_hashes_attested=replay['original_and_RGB512_hashes_verified'],combined_dataset_copy_bytes=storage['combined_dataset_copy_bytes'],images_redistributed=False,unknown_creator_accounts=sum(x['creator_account_from_source_url'] is None for x in m['covers']),model_or_GPU_experiments_started=0,scope='Public seal/protocol/selection/receipt checks. Actual original/PNG decoding and deterministic replay were executed on server and recorded separately. Finite historical exclusions do not prove all prior development or model-training use absent.')
if __name__=='__main__':print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
