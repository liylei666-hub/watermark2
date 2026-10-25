"""Official COCO data acquisition only: no torch/model imports, no target scores."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only data preparation')
import ast,collections,datetime,getpass,hashlib,json,shutil,signal,ssl,subprocess,sys,time,unicodedata,urllib.error,urllib.parse,urllib.request,zipfile
from pathlib import Path
ROOT=Path('/data0/liyanlei/watermark_research');DATA=ROOT/'datasets/confirmation100_v1';PUBLIC=ROOT/'reports/confirmation100_assets_v1';PROTOCOL=ROOT/'protocols/confirmation100_assets_v1.json'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,x):
 with Path(p).open('x',encoding='utf8') as f:json.dump(x,f,indent=2,ensure_ascii=False);f.write('\n')
def status(state,**kw):
 p=PUBLIC/'status.tmp';p.write_text(json.dumps(dict(state=state,at_utc=now(),**kw),indent=2)+'\n');p.replace(PUBLIC/'status.json')
def event(kind,**kw):
 with (PUBLIC/'events.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(event=kind,at_utc=now(),**kw))+'\n')
def host():
 if sys.platform!='linux' or getpass.getuser()!='liyanlei' or Path.cwd()!=ROOT or '172.18.185.249' not in subprocess.check_output(['hostname','-I'],text=True).split():raise ValueError('Designated project/server required')
def treebytes(folder):
 return sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) if folder.exists() else 0
def artifact_bytes():
 total=0
 for folder,dirs,files in os.walk(ROOT):
  dirs[:]=[n for n in dirs if n not in ('cache','envs','.git','__pycache__')]
  for n in files:
   p=Path(folder)/n
   if p.is_file():total+=p.stat().st_size
 return total
def budget(extra=0):
 used=artifact_bytes();data=treebytes(DATA);free=shutil.disk_usage(ROOT).free
 if used+extra+8*1024**2>10*1024**3 or data+extra>512*1024**2 or free<extra+8*1024**2:raise RuntimeError('Artifact/dataset/disk budget gate')
 return dict(artifact_bytes_excluding_existing_cache_env_git=used,dataset_bytes=data,free_disk_bytes=free)
def normalize(text):return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())
def textsha(text):return hashlib.sha256(normalize(text).encode()).hexdigest()
def image_features(image):
 import numpy as np
 from PIL import Image
 from scipy.fftpack import dct
 rgb=image.convert('RGB');pixel=hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
 canonical=image.resize((512,512)).convert('RGB');canonical_sha=hashlib.sha256(canonical.tobytes()).hexdigest()
 gray=np.asarray(image.convert('L').resize((32,32),Image.Resampling.LANCZOS),dtype=np.float64)
 low=dct(dct(gray,axis=0,norm='ortho'),axis=1,norm='ortho')[:8,:8].ravel();bits=low[1:]>np.median(low[1:]);value=sum(int(b)<<(i+1) for i,b in enumerate(bits))
 return dict(rgb_pixel_sha256=pixel,canonical_rgb512_pixel_sha256=canonical_sha,phash64=f'{value:016x}'),canonical
def prior_coverage():
 from PIL import Image
 rows=[];bad=[];prompt_hashes=set();json_files=[];known_ids=set()
 def scan(value):
  if isinstance(value,dict):
   for k,v in value.items():
    if k in ('prompt','prompts','reference_prompt','cover_prompt','target_prompt','attack_prompt'):
     for s in ([v] if isinstance(v,str) else v if isinstance(v,list) else []):
      if isinstance(s,str):prompt_hashes.add(textsha(s))
    if k in ('original_coco_id','source_coco_id','coco_id') and isinstance(v,int):known_ids.add(v)
    if isinstance(v,(dict,list)):scan(v)
  elif isinstance(value,list):
   for v in value:
    if isinstance(v,(dict,list)):scan(v)
 for folder,dirs,files in os.walk(ROOT):
  dirs[:]=[n for n in dirs if n not in ('cache','envs','.git','__pycache__','private_eval','datasets')]
  for n in files:
   p=Path(folder)/n;rel=p.relative_to(ROOT).as_posix()
   if p.suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
    try:
     with Image.open(p) as im:features,_=image_features(im)
     rows.append(dict(path=rel,file_sha256=sha(p),**features))
    except Exception as e:bad.append(dict(path=rel,file_sha256=sha(p),error=str(e)))
   elif p.suffix=='.json' and rel.split('/')[0] in ('runs','reports','protocols') and p.stat().st_size<8*1024**2:
    try:scan(read(p));json_files.append(dict(path=rel,sha256=sha(p)))
    except (json.JSONDecodeError,UnicodeDecodeError):pass
 source=ROOT/'third_party/semantic-forgery/utils/prompt_utils.py'
 for node in ast.parse(source.read_bytes()).body:
  if isinstance(node,ast.Assign):
   try:value=ast.literal_eval(node.value)
   except (ValueError,TypeError):continue
   if isinstance(value,list):
    for s in value:
     if isinstance(s,str):prompt_hashes.add(textsha(s))
 return dict(created_at_utc=now(),images=rows,image_failures=bad,metadata_files=json_files,known_prompt_hashes=sorted(prompt_hashes),known_explicit_coco_ids=sorted(known_ids),scope='Project images and public run/report/protocol metadata; excluded private_eval,datasets,cache,envs,.git. Anonymous COCO_1..10 names are NOT COCO IDs. Exact/canonical/pHash checks do not prove all prior development use absent.')
def allowed_url(url):
 u=urllib.parse.urlsplit(url)
 return u.scheme=='https' and u.hostname=='images.cocodataset.org' and not u.username and not u.password and not u.query and not u.fragment
class RedirectGuard(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if not allowed_url(newurl):raise RuntimeError('Unapproved redirect; no access workaround')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(url,dest,limit):
 if not allowed_url(url):raise ValueError('Only frozen official HTTPS data origin allowed')
 if dest.exists() or dest.with_suffix(dest.suffix+'.part').exists():raise ValueError('Existing acquisition artifact; inspect, do not overwrite/retry')
 opener=urllib.request.build_opener(RedirectGuard(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
 event('fetch_started',url=url,destination=dest.relative_to(ROOT).as_posix())
 with opener.open(urllib.request.Request(url,headers={'User-Agent':'watermark2-confirmation-assets/1.0'}),timeout=45) as response:
  if response.status!=200 or not allowed_url(response.geturl()):raise RuntimeError('Unexpected HTTP status/origin')
  content_type=response.headers.get('Content-Type','');length=response.headers.get('Content-Length')
  if 'text/html' in content_type.lower():raise RuntimeError('HTML/access page instead of public data; stop')
  if length and int(length)>limit:raise RuntimeError('Source exceeds frozen per-file budget')
  budget(int(length) if length else limit);partial=dest.with_suffix(dest.suffix+'.part');count=0;last_check=0;h=hashlib.sha256()
  with partial.open('xb') as f:
   while True:
    b=response.read(262144)
    if not b:break
    if count+len(b)>limit:raise RuntimeError('Per-file streamed byte cap')
    if count-last_check>=8*1024**2:budget(len(b));last_check=count
    f.write(b);h.update(b);count+=len(b)
  if length and count!=int(length):raise RuntimeError('Incomplete body retained; no automatic retry')
  partial.rename(dest)
  record=dict(url=url,effective_url=response.geturl(),path=dest.relative_to(ROOT).as_posix(),bytes=count,sha256=h.hexdigest(),headers={n:response.headers.get(n) for n in ('Content-Type','Content-Length','ETag','Last-Modified')})
 event('fetch_completed',**record);return record
def rank(seed,role,ident):return hashlib.sha256(f'{seed}|{role}|{ident}'.encode()).hexdigest()
def prepare():
 host();protocol=read(PROTOCOL)
 if sha(PROTOCOL)!=PROTOCOL.with_suffix('.sha256').read_text().strip() or sha(PROTOCOL)!=read(PUBLIC/'launch.json')['protocol_sha256'] or sha(__file__)!=read(PUBLIC/'launch.json')['worker_sha256']:raise ValueError('Frozen protocol/source changed')
 before=read(PUBLIC/'launch.json')['budget_before'];write(PUBLIC/'protocol_snapshot.json',protocol)
 status('freezing_prior_coverage');bank=prior_coverage();write(PUBLIC/'prior_coverage.json',bank);event('rules_and_coverage_frozen',protocol_sha256=sha(PROTOCOL),coverage_sha256=sha(PUBLIC/'prior_coverage.json'))
 status('fetching_metadata');meta=DATA/'metadata';meta.mkdir();archive=meta/'annotations_trainval2017.zip';meta_download=fetch(protocol['metadata_url'],archive,256*1024**2)
 with zipfile.ZipFile(archive) as z:
  member=z.getinfo('annotations/captions_val2017.json')
  if member.file_size>16*1024**2:raise ValueError('Metadata member too large')
  raw=z.read(member)
 budget(len(raw));metadata_path=meta/'captions_val2017.json'
 with metadata_path.open('xb') as f:f.write(raw)
 document=json.loads(raw);images=document['images'];annotations=document['annotations'];licenses={int(x['id']):x for x in document['licenses']}
 if len(images)!=5000 or len({x['id'] for x in images})!=5000 or len(annotations)<25000:raise ValueError('Not expected COCO2017val caption metadata')
 eligible=[];meta_rejections=[]
 for image in images:
  ident=image['id'];lic=licenses.get(image.get('license'),{});u=urllib.parse.urlsplit(lic.get('url',''));flickr=urllib.parse.urlsplit(image.get('flickr_url',''));parts=flickr.path.strip('/').split('/')
  reason=None
  if u.hostname not in ('creativecommons.org','www.creativecommons.org') or not u.path.startswith('/licenses/by/') or u.path.rstrip('/').split('/')[-1] not in ('2.0','3.0','4.0'):reason='license_not_frozen_CC_BY_allowlist'
  elif flickr.hostname not in ('flickr.com','www.flickr.com') or len(parts)<3 or parts[0]!='photos' or not parts[1] or not parts[2].isdigit():reason='attribution_owner_or_photo_id_missing'
  elif not isinstance(ident,int) or image.get('file_name')!=f'{ident:012d}.jpg' or image.get('width',0)<=0 or image.get('height',0)<=0 or image['width']*image['height']>20000000:reason='invalid_frozen_image_metadata'
  elif ident in bank['known_explicit_coco_ids']:reason='known_historical_COCO_ID'
  else:
   expected=f'http://images.cocodataset.org/val2017/{ident:012d}.jpg'
   if image.get('coco_url') not in (expected,expected.replace('http:','https:')):reason='unexpected_official_image_url'
  if reason:meta_rejections.append(dict(coco_id=ident,reason=reason));continue
  eligible.append(dict(coco_id=ident,source_url=image['coco_url'],fetch_url=image['coco_url'].replace('http:','https:'),flickr_url=image['flickr_url'],creator_account_from_source_url=parts[1],creator_display_name=None,flickr_photo_id=parts[2],photo_key=parts[2],license=dict(id=lic['id'],name=lic.get('name'),url=lic['url'],basis='COCO2017 metadata declaration; not independent current-rights certification'),width=image['width'],height=image['height'],attribution=f"Flickr account {parts[1]}, photo {parts[2]}; source {image['flickr_url']}; license {lic['url']} as recorded by COCO2017"))
 write(PUBLIC/'metadata_audit.json',dict(metadata_download=meta_download,caption_metadata_sha256=sha(metadata_path),images=len(images),captions=len(annotations),eligible_images=len(eligible),rejections=meta_rejections,license_policy=protocol['license_policy']))
 if len(eligible)<200:raise RuntimeError('Fewer than200 eligible source identities; do not relax frozen license rules')
 known_files={x['file_sha256'] for x in bank['images']+bank['image_failures']};known_pixels={x['rgb_pixel_sha256'] for x in bank['images']};known_canonical={x['canonical_rgb512_pixel_sha256'] for x in bank['images']};phashes=[(int(x['phash64'],16),x['path']) for x in bank['images']]
 selected=[];rejections=[];used_photos=set();(DATA/'originals').mkdir();(DATA/'rgb512').mkdir();status('fetching_cover_candidates')
 from PIL import Image
 for image in sorted(eligible,key=lambda x:rank(protocol['seed'],'cover',x['coco_id'])):
  if len(selected)==100:break
  if image['photo_key'] in used_photos:rejections.append(dict(coco_id=image['coco_id'],reason='duplicate_source_photo'));continue
  if sum(1 for _ in (DATA/'originals').glob('*.jpg'))>=150:raise RuntimeError('Frozen150 candidate-download ceiling; no relaxed dedup')
  ident=image['coco_id'];source=DATA/'originals'/f'{ident:012d}.jpg';download=fetch(image['fetch_url'],source,8*1024**2)
  with Image.open(source) as im:
   if im.size!=(image['width'],image['height']):raise ValueError('Source dimensions differ; retain and stop')
   features,canonical=image_features(im)
  hit=None
  if download['sha256'] in known_files:hit='historical_or_selected_byte_duplicate'
  elif features['rgb_pixel_sha256'] in known_pixels:hit='historical_or_selected_pixel_duplicate'
  elif features['canonical_rgb512_pixel_sha256'] in known_canonical:hit='historical_or_selected_canonical_duplicate'
  else:
   value=int(features['phash64'],16)
   nearest=min(((value^v).bit_count(),name) for v,name in phashes) if phashes else (64,None)
   if nearest[0]<=4:hit='historical_or_selected_phash_le4'
  if hit:rejections.append(dict(coco_id=ident,reason=hit,source_sha256=download['sha256'],features=features,nearest=nearest if hit.endswith('le4') else None));event('cover_excluded',coco_id=ident,reason=hit);continue
  path=DATA/'rgb512'/f'{ident:012d}.png';budget(2*1024**2)
  with path.open('xb') as f:canonical.save(f,format='PNG')
  row=dict(**image,rank_sha256=rank(protocol['seed'],'cover',ident),source_file=download,dedup_features=features,minimum_prior_or_selected_phash_distance=nearest[0],preprocessed=dict(path=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=sha(path),rgb512_pixel_sha256=features['canonical_rgb512_pixel_sha256']))
  selected.append(row);used_photos.add(image['photo_key']);known_files.add(download['sha256']);known_pixels.add(features['rgb_pixel_sha256']);known_canonical.add(features['canonical_rgb512_pixel_sha256']);phashes.append((int(features['phash64'],16),'selected:'+str(ident)))
  if len(selected)%10==0:status('fetching_cover_candidates',accepted=len(selected),downloaded=sum(1 for _ in (DATA/'originals').glob('*.jpg')));print('COVERS_ACCEPTED',len(selected),flush=True)
 if len(selected)!=100:raise RuntimeError('Insufficient eligible covers after frozen exclusions')
 byimage=collections.defaultdict(list)
 for annotation in annotations:byimage[annotation['image_id']].append(annotation)
 coverids={x['coco_id'] for x in selected};used_prompt_hashes=set(bank['known_prompt_hashes']);captions=[];caption_rejections=[]
 for image in sorted(eligible,key=lambda x:rank(protocol['seed'],'caption',x['coco_id'])):
  if len(captions)==100:break
  if image['coco_id'] in coverids or image['photo_key'] in used_photos:caption_rejections.append(dict(coco_id=image['coco_id'],reason='cover_or_caption_source_overlap'));continue
  chosen=None
  for a in sorted(byimage[image['coco_id']],key=lambda a:a['id']):
   if a['caption'].strip() and textsha(a['caption']) not in used_prompt_hashes:chosen=a;break
  if chosen is None:caption_rejections.append(dict(coco_id=image['coco_id'],reason='no_unique_nonhistorical_caption'));continue
  row=dict(caption_annotation_id=chosen['id'],source_image=image,caption=chosen['caption'],normalized_caption_sha256=textsha(chosen['caption']),source_rank_sha256=rank(protocol['seed'],'caption',image['coco_id']),caption_license='https://creativecommons.org/licenses/by/4.0/',caption_attribution='COCO Consortium, COCO2017 captions annotations; https://cocodataset.org/#termsofuse')
  captions.append(row);used_prompt_hashes.add(row['normalized_caption_sha256']);used_photos.add(image['photo_key'])
 if len(captions)!=100:raise RuntimeError('Insufficient disjoint unique captions; no resampling')
 after=budget();manifest=dict(schema=1,status='assets_ready_for_protocol_review_not_model_launch',created_at_utc=now(),protocol_sha256=sha(PROTOCOL),coverage_sha256=sha(PUBLIC/'prior_coverage.json'),metadata_sha256=sha(metadata_path),covers=selected,captions=captions,pairs=[dict(case_id=f'confirm_{i+1:03d}',cover_coco_id=c['coco_id'],caption_annotation_id=p['caption_annotation_id'],caption_source_coco_id=p['source_image']['coco_id']) for i,(c,p) in enumerate(zip(selected,captions))],independence_scope='Excluded only under declared known-ID,byte,RGB,canonical,pHash and normalized-prompt checks. Not proof of all prior development use or foundation-model training absence.',usage='Frozen baseline confirmation only, never new-method selection/tuning; no target scores may be viewed in development',target_generation_started=False,attack_optimization_started=False,key_message_or_service_credentials_generated=False,images_not_redistributed_in_git=True)
 write(PUBLIC/'manifest.json',manifest);write(PUBLIC/'exclusions.json',dict(cover_candidates=rejections,caption_sources=caption_rejections));write(PUBLIC/'budget.json',dict(before=before,after=after,actual_dataset_bytes=treebytes(DATA),limit_new_artifacts=10*1024**3,dataset_limit=512*1024**2,existing_model_cache_env_git_excluded=True))
 checked=verify_assets();write(PUBLIC/'verification.json',checked);status('completed',covers=100,captions=100,manifest_sha256=sha(PUBLIC/'manifest.json'));print('COMPLETED_CONFIRMATION_ASSETS_CPU',flush=True)
def verify_assets():
 from PIL import Image
 m=read(PUBLIC/'manifest.json');assert m['protocol_sha256']==sha(PROTOCOL)==read(PUBLIC/'launch.json')['protocol_sha256']==sha(PUBLIC/'protocol_snapshot.json') and m['coverage_sha256']==sha(PUBLIC/'prior_coverage.json')
 assert sha(__file__)==read(PUBLIC/'launch.json')['worker_sha256']
 assert len(m['covers'])==len(m['captions'])==len(m['pairs'])==100
 assert len({c['coco_id'] for c in m['covers']})==100 and len({c['source_image']['coco_id'] for c in m['captions']})==100
 assert not ({c['coco_id'] for c in m['covers']}&{c['source_image']['coco_id'] for c in m['captions']})
 assert len({c['normalized_caption_sha256'] for c in m['captions']})==100 and len({c['photo_key'] for c in m['covers']}|{c['source_image']['photo_key'] for c in m['captions']})==200
 for c in m['captions']:assert textsha(c['caption'])==c['normalized_caption_sha256']
 for c in m['covers']:
  assert sha(ROOT/c['source_file']['path'])==c['source_file']['sha256'];p=ROOT/c['preprocessed']['path'];assert sha(p)==c['preprocessed']['sha256']
  with Image.open(p) as im:assert im.size==(512,512) and im.mode=='RGB' and hashlib.sha256(im.tobytes()).hexdigest()==c['preprocessed']['rgb512_pixel_sha256']
 assert sha(DATA/'metadata/captions_val2017.json')==m['metadata_sha256'];budget()
 assert not any(n in sys.modules for n in ('torch','diffusers','transformers','lpips'))
 return dict(status='passed',covers=100,captions=100,disjoint_source_ids=True,unique_caption_texts=True,original_and_preprocessed_hashes=200,model_imports=0,gpu_used=False,private_keys_or_messages_generated=False,manifest_sha256=sha(PUBLIC/'manifest.json'))
def supervise():
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1');started=time.perf_counter();reason=None
 with (PUBLIC/'stdout.log').open('xb') as stdout,(PUBLIC/'stderr.log').open('xb') as stderr:
  child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
  write(PUBLIC/'process.json',dict(pid=child.pid,started_at_utc=now(),cuda_visible_devices='',worker_sha256=sha(__file__)))
  while child.poll() is None:
   if time.perf_counter()-started>7200:reason='owned_data_worker_watchdog';os.killpg(child.pid,signal.SIGKILL);break
   time.sleep(1)
  code=child.wait()
 complete=code==0 and read(PUBLIC/'status.json')['state']=='completed'
 write(PUBLIC/'execution.json',dict(completed=complete,exit_code=code,stop_reason=reason,wall_seconds=time.perf_counter()-started,finished_at_utc=now(),files={p.name:sha(p) for p in PUBLIC.iterdir() if p.is_file() and not p.name.startswith('supervisor.')}));write(PUBLIC/'result_seal.json',dict(execution_sha256=sha(PUBLIC/'execution.json'),manifest_sha256=sha(PUBLIC/'manifest.json') if complete else None));print('ASSET_ACQUISITION_TERMINAL',complete,flush=True)
def start():
 host()
 if DATA.exists() or PUBLIC.exists():raise ValueError('Existing acquisition: inspect status, never repeat or overwrite')
 before=budget(512*1024**2)
 if sha(PROTOCOL)!=PROTOCOL.with_suffix('.sha256').read_text().strip():raise ValueError('Protocol SHA mismatch')
 DATA.mkdir(parents=True);PUBLIC.mkdir();write(PUBLIC/'launch.json',dict(created_at_utc=now(),protocol_sha256=sha(PROTOCOL),worker_sha256=sha(__file__),budget_before=before,no_models=True,no_service_credentials=True))
 with (PUBLIC/'supervisor.stdout.log').open('xb') as stdout,(PUBLIC/'supervisor.stderr.log').open('xb') as stderr:
  child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--supervise'],cwd=ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
 write(PUBLIC/'supervisor.json',dict(pid=child.pid,started_at_utc=now()));print('STARTED_DATA_ONLY',child.pid,str(PUBLIC))
if __name__=='__main__':
 host()
 if sys.argv[1:]==['--start']:start()
 elif sys.argv[1:]==['--supervise']:supervise()
 elif sys.argv[1:]==['--verify']:print(json.dumps(verify_assets(),indent=2))
 elif sys.argv[1:]==['--worker']:
  try:prepare()
  except BaseException as e:
   event('acquisition_stopped_no_retry',error_type=type(e).__name__,reason=str(e));status('blocked_or_failed_data_acquisition',error_type=type(e).__name__,reason=str(e),models_started=0,no_automatic_retry=True);raise
 else:raise SystemExit('Explicit --start/--worker/--supervise/--verify required')
