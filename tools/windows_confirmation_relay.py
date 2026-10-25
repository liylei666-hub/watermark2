"""Windows public-data relay; the frozen selector stays on the research server."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only data work')
import datetime,hashlib,json,re,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[2]
SOURCE=BASE/'gateway-data/confirmation100_sjtu_v1'
LOCAL=BASE/'gateway-data/confirmation100_relay_v1'
REMOTE='/data0/liyanlei/watermark_research'
TARGET='liyanlei@172.18.185.249'
OPTIONS=['-i',os.environ['WM_SSH_IDENTITY'],'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=20']
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
 with Path(p).open('x',encoding='utf8') as f:json.dump(x,f,indent=2);f.write('\n')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def remote(command,timeout=90):
 p=subprocess.run(['ssh',*OPTIONS,TARGET,'cd '+REMOTE+' && '+command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 if p.returncode:raise RuntimeError('SSH operation failed: '+p.stderr.decode(errors='replace'))
 return p.stdout.decode()
def upload(path,name):
 assert re.fullmatch(r'\d{3}\.(bin|ready\.json|failed\.json)',name)
 target=REMOTE+'/datasets/confirmation100_relay_v1/incoming/'+name
 remote('test ! -e '+target)
 p=subprocess.run(['scp',*OPTIONS,str(path),TARGET+':'+target],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
 if p.returncode:raise RuntimeError('SCP uncertain/failed; inspect existing destination, never overwrite: '+p.stderr.decode(errors='replace'))
def poll():return json.loads(remote('CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 envs/semantic_forgery_py310/bin/python tools/relay_confirmation100_assets.py --poll'))
def local_data_bytes():
 return sum(p.stat().st_size for parent in [SOURCE,LOCAL] if parent.exists() for p in parent.rglob('*') if p.is_file())
def init():
 if LOCAL.exists():raise ValueError('Relay previously admitted; inspect, do not duplicate')
 v=read(SOURCE/'zip_verification.json');assert v['archive']['sha256']=='113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268'
 LOCAL.mkdir();(LOCAL/'images').mkdir();write(LOCAL/'controller_launch.json',dict(started_at_utc=now(),controller_sha256=sha(__file__),metadata_verification_sha256=sha(SOURCE/'zip_verification.json'),local_data_bytes=local_data_bytes(),no_models=True,no_gpu=True))
 archive=SOURCE/v['archive']['path'];assert sha(archive)==v['archive']['sha256']
 with archive.open('rb') as f:
  p=subprocess.run(['ssh',*OPTIONS,TARGET,'cd '+REMOTE+' && CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 envs/semantic_forgery_py310/bin/python tools/hash_confirmation_stream.py'],stdin=f,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600)
 if p.returncode:raise RuntimeError('Full stream integrity operation failed or uncertain; inspect before retry: '+p.stderr.decode(errors='replace'))
 stream=json.loads(p.stdout.decode());assert stream['sha256']==v['archive']['sha256'] and stream['bytes']==v['archive']['bytes'];write(LOCAL/'server_full_zip_stream_verification.json',stream)
 remote('mkdir -p datasets/confirmation100_relay_v1/incoming')
 subset=SOURCE/v['transport_subset']['path'];assert sha(subset)==v['transport_subset']['sha256']
 receipt=dict(index=0,canonical_url='https://images.cocodataset.org/annotations/annotations_trainval2017.zip',actual_source_url=v['source_url'],http_status=200,tls_verification_disabled=False,bytes=subset.stat().st_size,sha256=sha(subset),full_archive_sha256=v['archive']['sha256'],member_sha256=v['member']['sha256'],transport_derivation=v['transport_subset']['derivation'],verified_at_utc=now(),full_zip_sha256_matches_server_stream=True)
 ready=LOCAL/'000.ready.json';write(ready,receipt);upload(subset,'000.bin');upload(ready,'000.ready.json')
 started=json.loads(remote('CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 envs/semantic_forgery_py310/bin/python tools/relay_confirmation100_assets.py --start'));write(LOCAL/'server_started.json',started);print('CPU_SELECTOR_STARTED',json.dumps(started),flush=True)
 run()
def run():
 begin=time.monotonic();handled=0
 while True:
  if time.monotonic()-begin>7200:raise RuntimeError('Owned data controller watchdog')
  state=poll()
  if state['terminal'] is not None:
   write(LOCAL/'controller_terminal.json',dict(finished_at_utc=now(),server_terminal=state['terminal'],wall_seconds=time.monotonic()-begin,local_data_bytes=local_data_bytes(),server_dataset_bytes=state['dataset_bytes'],combined_dataset_copy_bytes=local_data_bytes()+state['dataset_bytes'],models_started=0,gpu_used=False));print('DATA_RELAY_TERMINAL',state['terminal']['completed'],flush=True);return
  if not state['pending']:time.sleep(2);continue
  assert len(state['pending'])==1
  request=state['pending'][0];index=request['index'];url=request['canonical_url'];match=re.fullmatch(r'https://images\.cocodataset\.org/val2017/(\d{12}\.jpg)',url)
  if not match or not 1<=index<=150:raise ValueError('Unapproved image request')
  if local_data_bytes()+state['dataset_bytes']+16*1024**2>512*1024**2:raise RuntimeError('Combined Windows+server 512MiB storage gate')
  label=f'{index:03d}';folder=LOCAL/'images'/label
  if folder.exists():raise ValueError('Previously admitted image transfer; inspect, never overwrite')
  folder.mkdir();image=folder/match[1];actual='https://s3.us-east-1.amazonaws.com/images.cocodataset.org/val2017/'+match[1]
  cmd=['curl.exe','--silent','--show-error','--fail','--proto','=https','--connect-timeout','20','--max-time','120','--retry','0','--max-filesize','8388608','--dump-header',str(folder/'headers.private'),'--output',str(image),'--write-out','%{http_code}\n%{ssl_verify_result}\n%{size_download}\n%{time_total}\n',actual]
  write(folder/'launch.json',dict(at_utc=now(),request=request,actual_source_url=actual,automatic_retries=0,tls_verification_disabled=False))
  with (folder/'stderr.log').open('xb') as stderr:p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=stderr,timeout=130)
  fields=p.stdout.decode().splitlines();write(folder/'curl.json',dict(exit_code=p.returncode,fields=fields,at_utc=now()))
  if p.returncode or fields[:2]!=['200','0']:
   failed=folder/(label+'.failed.json');write(failed,dict(index=index,canonical_url=url,actual_source_url=actual,exit_code=p.returncode,http_code=fields[0] if fields else None,reason='Public data GET failed; no automatic retry',at_utc=now()));upload(failed,failed.name);raise RuntimeError('Image data source failed; see '+str(folder))
  assert image.stat().st_size==int(float(fields[2]))<=8388608
  receipt=dict(index=index,canonical_url=url,actual_source_url=actual,http_status=200,tls_verification_disabled=False,bytes=image.stat().st_size,sha256=sha(image),download_seconds=float(fields[3]),verified_at_utc=now())
  ready=folder/(label+'.ready.json');write(ready,receipt);upload(image,label+'.bin');upload(ready,ready.name);handled+=1
  if handled%10==0:print('RELAYED_IMAGES',handled,flush=True)
if __name__=='__main__':
 if sys.platform!='win32':raise SystemExit('Windows gateway only')
 if sys.argv[1:]!=['--init']:raise SystemExit('Explicit --init required; inspect uncertain outcomes before continuing')
 try:init()
 except BaseException as e:
  if LOCAL.exists() and not (LOCAL/'controller_failed.json').exists():write(LOCAL/'controller_failed.json',dict(at_utc=now(),error_type=type(e).__name__,reason=str(e),no_automatic_retry=True,models_started=0,gpu_used=False))
  raise
