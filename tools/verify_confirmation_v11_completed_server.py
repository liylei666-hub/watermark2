"""Offline replay of deterministic data selection; no models or network requests."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only verification')
import collections,hashlib,json,sys,urllib.parse
from pathlib import Path
import complete_confirmation_v11_offline as r
from confirmation_attribution import parse_flickr_source
a=r.a
def verify():
 a.host();ex=a.read(a.PUBLIC/'execution.json');seal=a.read(a.PUBLIC/'result_seal.json');assert ex['completed'] and ex['exit_code']==0
 assert a.sha(a.PUBLIC/'execution.json')==seal['execution_sha256']
 for name,h in ex['files'].items():assert a.sha(a.PUBLIC/name)==h
 base=a.verify_assets();m=a.read(a.PUBLIC/'manifest.json');bank=a.read(a.PUBLIC/'prior_coverage.json');protocol=a.read(a.PROTOCOL)
 old=a.read(a.ROOT/'protocols/confirmation100_assets_v1.json')
 for k in ('seed','counts','ranking','exclusions','preprocessing','budgets'):assert protocol[k]==old[k]
 assert a.sha(a.PUBLIC/'prior_coverage.json')==r.BANK_SHA==protocol['prior_coverage_sha256']
 for name,h in protocol['implementation_hashes'].items():assert a.sha(a.ROOT/name)==h
 d=a.read(a.DATA/'metadata/captions_val2017.json');licenses={x['id']:x for x in d['licenses']};eligible=[]
 for image in d['images']:
  ident=image['id'];lic=licenses[image['license']];u=urllib.parse.urlsplit(lic['url']);source=parse_flickr_source(image.get('flickr_url'))
  if u.hostname not in ('creativecommons.org','www.creativecommons.org') or not u.path.startswith('/licenses/by/') or u.path.rstrip('/').split('/')[-1] not in ('2.0','3.0','4.0') or source is None:continue
  if ident in bank['known_explicit_coco_ids']:continue
  assert image['file_name']==f'{ident:012d}.jpg' and 0<image['width']*image['height']<=20000000
  eligible.append(dict(image=image,source=source))
 assert len(eligible)==a.read(a.PUBLIC/'metadata_audit.json')['eligible_images']==857
 files={x['file_sha256'] for x in bank['images']+bank['image_failures']};pixels={x['rgb_pixel_sha256'] for x in bank['images']};canonical={x['canonical_rgb512_pixel_sha256'] for x in bank['images']};phashes=[int(x['phash64'],16) for x in bank['images']]
 expected=[];seen_photos=set();downloads=[];rejections=[]
 from PIL import Image
 for row in sorted(eligible,key=lambda x:a.rank(protocol['seed'],'cover',x['image']['id'])):
  if len(expected)==100:break
  image=row['image'];identity=row['source'];ident=image['id']
  if identity['photo_key'] in seen_photos:rejections.append((ident,'duplicate_source_photo'));continue
  path=a.DATA/'originals'/image['file_name'];assert path.is_file();downloads.append(ident)
  with Image.open(path) as im:
   assert im.size==(image['width'],image['height']);features,png=a.image_features(im)
  byte_sha=a.sha(path);reason=None
  if byte_sha in files:reason='historical_or_selected_byte_duplicate'
  elif features['rgb_pixel_sha256'] in pixels:reason='historical_or_selected_pixel_duplicate'
  elif features['canonical_rgb512_pixel_sha256'] in canonical:reason='historical_or_selected_canonical_duplicate'
  elif phashes and min((int(features['phash64'],16)^v).bit_count() for v in phashes)<=4:reason='historical_or_selected_phash_le4'
  if reason:rejections.append((ident,reason));continue
  actual=m['covers'][len(expected)];assert actual['coco_id']==ident
  assert actual['flickr_url']==image['flickr_url'] and actual['flickr_photo_id']==identity['flickr_photo_id'] and actual['creator_account_from_source_url']==identity['creator_account_from_source_url']
  assert actual['creator_display_name'] is None and actual['redistribution_status']=='not_cleared_do_not_publish_image'
  assert actual['source_file']['sha256']==byte_sha and actual['dedup_features']==features
  assert actual['preprocessed']['rgb512_pixel_sha256']==hashlib.sha256(png.tobytes()).hexdigest()
  expected.append(ident);seen_photos.add(identity['photo_key']);files.add(byte_sha);pixels.add(features['rgb_pixel_sha256']);canonical.add(features['canonical_rgb512_pixel_sha256']);phashes.append(int(features['phash64'],16))
 assert len(expected)==100 and len(downloads)<=150 and {int(p.stem) for p in (a.DATA/'originals').glob('*.jpg')}==set(downloads)
 exclusions=a.read(a.PUBLIC/'exclusions.json');assert [(x['coco_id'],x['reason']) for x in exclusions['cover_candidates']]==rejections
 byimage=collections.defaultdict(list)
 for annotation in d['annotations']:byimage[annotation['image_id']].append(annotation)
 prompt_hashes=set(bank['known_prompt_hashes']);caption_ids=[];caption_sources=[]
 for row in sorted(eligible,key=lambda x:a.rank(protocol['seed'],'caption',x['image']['id'])):
  if len(caption_ids)==100:break
  image=row['image'];identity=row['source']
  if image['id'] in expected or identity['photo_key'] in seen_photos:continue
  chosen=next((x for x in sorted(byimage[image['id']],key=lambda x:x['id']) if x['caption'].strip() and a.textsha(x['caption']) not in prompt_hashes),None)
  if chosen is None:continue
  actual=m['captions'][len(caption_ids)];assert actual['caption_annotation_id']==chosen['id'] and actual['caption']==chosen['caption'] and actual['source_image']['coco_id']==image['id']
  caption_ids.append(chosen['id']);caption_sources.append(image['id']);prompt_hashes.add(a.textsha(chosen['caption']));seen_photos.add(identity['photo_key'])
 assert len(caption_ids)==100 and len(seen_photos)==200
 assert [(x['cover_coco_id'],x['caption_annotation_id'],x['caption_source_coco_id']) for x in m['pairs']]==list(zip(expected,caption_ids,caption_sources))
 transfers=[a.read(p) for p in sorted((a.PUBLIC/'transfers').glob('*.json'))];assert len(transfers)==len(downloads)+1
 for receipt in transfers[1:]:assert receipt['http_status']==200 and not receipt['tls_verification_disabled'] and receipt['sha256']==a.sha(a.DATA/'originals'/Path(urllib.parse.urlsplit(receipt['canonical_url']).path).name)
 assert not any(x in sys.modules for x in ('torch','diffusers','transformers','lpips'))
 return dict(status='passed',verified_at_utc=a.now(),execution_sealed_files=len(ex['files']),metadata_eligible=857,covers=100,unique_caption_texts=100,disjoint_source_identities=200,downloaded_candidates=len(downloads),deterministic_cover_order_replayed=True,deterministic_caption_order_replayed=True,cover_rejections_replayed=len(rejections),original_and_RGB512_hashes_verified=200,Windows_receipt_hashes_match_server=True,known_owner_accounts=sum(x['creator_account_from_source_url'] is not None for x in m['covers']),unknown_owner_accounts=sum(x['creator_account_from_source_url'] is None for x in m['covers']),image_redistribution_cleared=False,model_imports=0,gpu_used=False,target_generation_or_scoring_started=False,manifest_sha256=a.sha(a.PUBLIC/'manifest.json'),original_data_verification=base,server_dataset_bytes=a.treebytes(a.DATA),all_confirmation_dataset_bytes=sum(a.treebytes(p) for p in (a.ROOT/'datasets').glob('confirmation100*')),project_budget=a.budget())
if __name__=='__main__':
 result=verify();a.write(a.PUBLIC/'selection_replay_verification.json',result);print(json.dumps(result,indent=2))
