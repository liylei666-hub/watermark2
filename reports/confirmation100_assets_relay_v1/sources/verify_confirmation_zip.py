"""Validate downloaded public data, retaining the full ZIP and only one extracted member."""
import datetime,hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).parent;folder=root/'gateway-data/confirmation100_sjtu_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p,kind='sha256'):
 h=hashlib.new(kind)
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
launch=read(folder/'launch.json')
s3_recovery=(folder/'s3resume.terminal.json').exists()
fresh_recovery=(folder/'retry2.terminal.json').exists() and not s3_recovery
recovery=((folder/'resume1.terminal.json').exists() or s3_recovery) and not fresh_recovery
terminal=folder/('s3resume.terminal.json' if s3_recovery else 'retry2.terminal.json' if fresh_recovery else 'resume1.terminal.json' if recovery else 'terminal.json')
assert read(terminal)['curl_exit_code']==0
fields=(folder/('s3resume.curl.txt' if s3_recovery else 'retry2.curl.txt' if fresh_recovery else 'resume1.curl.txt' if recovery else 'metadata.curl.txt')).read_text(encoding='utf-8-sig').splitlines();assert fields[0]==('206' if recovery else '200') and fields[1]=='0'
name='annotations_trainval2017_retry2.zip' if fresh_recovery else 'annotations_trainval2017.zip'
part=folder/(name+'.part');archive=folder/name
assert part.exists() and not archive.exists() and part.stat().st_size==launch['expected_bytes']==252907541
if recovery:
 previous=read(folder/('s3resume.launch.json' if s3_recovery else 'resume1.launch.json'))
 if not s3_recovery:assert digest(folder/'terminal.json')==previous['original_terminal_sha256']
 prefix=hashlib.sha256();remaining=previous['resume_offset']
 with part.open('rb') as f:
  while remaining:
   b=f.read(min(remaining,1024*1024));assert b;prefix.update(b);remaining-=len(b)
 assert prefix.hexdigest()==previous['original_partial_sha256']
if fresh_recovery:
 previous=read(folder/'retry2.launch.json');old=folder/'annotations_trainval2017.zip.part'
 assert old.stat().st_size==previous['prior_partial_bytes'] and digest(old)==previous['prior_partial_sha256']
 prefix=hashlib.sha256()
 with part.open('rb') as f:
  remaining=previous['prior_partial_bytes']
  while remaining:
   b=f.read(min(remaining,1024*1024));assert b;prefix.update(b);remaining-=len(b)
 assert prefix.hexdigest()==previous['prior_partial_sha256']
sha=digest(part);md5=digest(part,'md5')
assert sha==launch['expected_sha256'] and md5==launch['expected_mirror_md5']
with zipfile.ZipFile(part) as z:
 entries=z.infolist();assert len({x.filename for x in entries})==len(entries)
 assert all(not x.filename.startswith('/') and '..' not in Path(x.filename).parts and not x.flag_bits&1 for x in entries)
 assert sum(x.file_size for x in entries)<2*1024**3 and z.testzip() is None
 member=z.getinfo('annotations/captions_val2017.json');assert member.file_size<=16*1024**2
 raw=z.read(member)
document=json.loads(raw);assert len(document['images'])==5000 and len({x['id'] for x in document['images']})==5000
assert len(document['annotations'])==25014 and len({x['id'] for x in document['annotations']})==25014
image_ids={x['id'] for x in document['images']}
assert all(a['image_id'] in image_ids for a in document['annotations'])
assert all(x['file_name']==f"{x['id']:012d}.jpg" for x in document['images'])
assert len(document['licenses'])==8
archive=part.rename(archive)
member_path=folder/'captions_val2017.json'
with member_path.open('xb') as f:f.write(raw)
subset=folder/'captions_val2017_transport.zip'
with zipfile.ZipFile(subset,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.writestr('annotations/captions_val2017.json',raw)
with zipfile.ZipFile(subset) as z:assert z.testzip() is None and z.read('annotations/captions_val2017.json')==raw
receipt=dict(verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_url=launch['url'],institutional_record=launch['institutional_record'],archive=dict(path=archive.name,bytes=archive.stat().st_size,sha256=sha,md5=md5,zip_crc_all_members_passed=True,members=[dict(name=x.filename,bytes=x.file_size,compressed_bytes=x.compress_size,crc32=f'{x.CRC:08x}') for x in entries]),independent_sha256_source='https://raw.githubusercontent.com/tensorflow/datasets/master/tensorflow_datasets/url_checksums/coco_captions.txt',mirror_md5_not_COCO_authentication=True,resumed=recovery,original_failure_and_partial_prefix_preserved=True if recovery else None,member=dict(name='annotations/captions_val2017.json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),images=5000,captions=25014,licenses=8,split='val2017'),transport_subset=dict(path=subset.name,bytes=subset.stat().st_size,sha256=digest(subset),derivation='Mechanically repack only verified captions_val2017.json bytes; not the original full ZIP',uncompressed_member_unchanged=True),full_zip_retained_on_windows=True,entire_archive_not_extracted=True,models_started=0,gpu_used=False,windows_data_bytes=sum(p.stat().st_size for p in folder.iterdir() if p.suffix in ('.zip','.json') and p.name not in ('launch.json','terminal.json')))
if s3_recovery:
 receipt['source_url']=read(folder/'s3resume.launch.json')['url']
 receipt['acquisition_lineage']=dict(first_prefix_source=launch['url'],first_prefix_bytes=previous['resume_offset'],first_prefix_sha256=previous['original_partial_sha256'],remaining_source=receipt['source_url'],remaining_HTTP_status=206,source_identity='COCO official DNS CNAME plus AWS documented path-style endpoint; original prefix unchanged; complete TFDS SHA256 matches')
with (folder/'zip_verification.json').open('x',encoding='utf8') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(receipt,indent=2))
