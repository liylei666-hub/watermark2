import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import collections,datetime,hashlib,json,sys,urllib.parse
from pathlib import Path
sys.path.insert(0,'/data0/liyanlei/watermark_research/tools')
import relay_confirmation100_assets as r
a=r.a;a.host()
assert (a.PUBLIC/'execution.json').exists() and not a.read(a.PUBLIC/'execution.json')['completed']
path=a.DATA/'metadata/captions_val2017.json';d=a.read(path);licenses={x['id']:x for x in d['licenses']};counts=collections.Counter(x['license'] for x in d['images'])
audit=dict(observed_at_utc=a.now(),metadata_sha256=a.sha(path),images=len(d['images']),captions=len(d['annotations']),license_records=len(d['licenses']),CC_BY_image_count=sum(v for k,v in counts.items() if '/licenses/by/' in licenses[k]['url']),license_counts=[dict(license=licenses[k],images=v) for k,v in sorted(counts.items())],flickr_hosts=dict(collections.Counter(urllib.parse.urlsplit(x['flickr_url']).hostname for x in d['images'])),flickr_photos_account_path_count=sum(urllib.parse.urlsplit(x['flickr_url']).path.startswith('/photos/') for x in d['images']),frozen_rejection_counts=dict(collections.Counter(x['reason'] for x in a.read(a.PUBLIC/'metadata_audit.json')['rejections'])),first_CC_BY_metadata_example=next({k:x[k] for k in ('id','license','flickr_url','coco_url','width','height')} for x in d['images'] if '/licenses/by/' in licenses[x['license']]['url']),interpretation='The frozen parser incorrectly assumed the original metadata flickr_url was an owner/photos page. All actual addresses are static images; no image was downloaded. Keep failure; do not relax owner or license requirements silently.')
a.write(a.PUBLIC/'schema_audit.json',audit)
files=[dict(path=p.relative_to(a.ROOT).as_posix(),bytes=p.stat().st_size,sha256=a.sha(p)) for p in a.DATA.rglob('*') if p.is_file()]
a.write(a.PUBLIC/'budget_after.json',dict(observed_at_utc=a.now(),budget=a.budget(),dataset_files=files,images_downloaded=0,model_experiments_started=0,worker_sha256=a.sha(a.__file__),relay_wrapper_sha256=a.sha(r.__file__)))
print(json.dumps(audit,indent=2))
