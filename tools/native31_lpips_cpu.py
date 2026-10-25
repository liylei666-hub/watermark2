"""Post-hoc CPU LPIPS only. Does not generate/select/modify attack candidates."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('Empty CUDA visibility required')
import ast,datetime,getpass,hashlib,importlib.metadata,json,math,resource,socket,statistics,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path('/data0/liyanlei/watermark_research');RUN=ROOT/'runs/31_native_calibration_20261024T190323Z'
BACKBONE=Path('/home/liyanlei/.cache/torch/hub/checkpoints/alexnet-owt-7be5be79.pth')
LINEAR=ROOT/'envs/semantic_forgery_py310/lib/python3.10/site-packages/lpips/weights/v0.1/alex.pth'
WEIGHTS={str(BACKBONE):'7be5be791159472b1fbf3c69796f7cb30dca7ad8466c2df70058c37116cdee02',str(LINEAR):'df73285e35b22355a2df87cdb6b70b343713b667eddbda73e1977e0c860835c0'}
POINTS=(20,50,100,150,151)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,d):
 with Path(p).open('x',encoding='utf8') as f:json.dump(d,f,indent=2,ensure_ascii=False);f.write('\n')
def host():
 if sys.platform!='linux' or getpass.getuser()!='liyanlei' or Path.cwd()!=ROOT or '172.18.185.249' not in subprocess.check_output(['hostname','-I'],text=True).split():raise ValueError('Designated server/project required')
def inputs():
 if read(RUN/'scheduler_status.json')['state']!='completed':raise ValueError('Original run not completed')
 seal=read(RUN/'candidates_sealed.json');original=read(RUN/'analysis.json');rows=[]
 if len(seal['rows'])!=20 or len(original['rows'])!=28:raise ValueError('Wrong fixed denominator')
 for record in original['rows']:
  sid=record['task_id'];label=record['label']
  if label not in ('reference','cover')+tuple(map(str,POINTS)):raise ValueError('Unexpected label')
  p=RUN/'prepare'/str(sid)/(label+'.png') if label in ('reference','cover') else RUN/f'attack_{sid}'/f'update_{label}.png'
  cover=RUN/'prepare'/str(sid)/'cover.png'
  if sha(p)!=record['image']['sha256']:raise ValueError('Image changed')
  rows.append(dict(task_id=sid,label=label,image_path=str(p),image_sha256=sha(p),cover_path=str(cover),cover_sha256=sha(cover)))
 if {(r['task_id'],r['label']) for r in rows}!={(i,label) for i in range(1,5) for label in ('reference','cover')+tuple(map(str,POINTS))}:raise ValueError('Pairing differs')
 for candidate in seal['rows']:
  row=next(r for r in rows if r['task_id']==candidate['task_id'] and r['label']==str(candidate['actual_update']))
  if row['image_sha256']!=candidate['image']['sha256']:raise ValueError('Candidate seal differs')
 return rows
def main(output):
 start=time.perf_counter();host();out=Path(output);plan=read(out/'plan.json')
 if plan['worker_sha256']!=sha(__file__) or plan['inputs']!=inputs():raise ValueError('Frozen posthoc job changed')
 for name,digest in WEIGHTS.items():
  if sha(name)!=digest:raise ValueError('Existing weight integrity differs')
 original_hashes={p:sha(RUN/p) for p in ['analysis.json','candidates_sealed.json','results_sealed.json','evaluate/summary.json']}
 source=ROOT/'third_party/semantic-forgery/utils/image_utils.py';data=source.read_bytes()
 if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!='43c6755a9b132e8ac33fbb63ab38b85506a2cf85':raise ValueError('Official helper source changed')
 blocked=[]
 def deny(*args,**kwargs):blocked.append('blocked_network_or_download_call');raise RuntimeError('Network and downloads forbidden for offline metric')
 socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny;socket.getaddrinfo=deny
 urllib.request.urlopen=deny;urllib.request.urlretrieve=deny
 import numpy as np,torch
 torch.hub.download_url_to_file=deny
 if torch.cuda.device_count()!=0 or torch.cuda.is_initialized():raise ValueError('GPU unavailable to CPU metric by contract')
 torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(0)
 from PIL import Image
 import lpips
 scope=dict(Image=Image,torch=torch,np=np,lpips=lpips)
 node=next(n for n in ast.parse(data).body if isinstance(n,ast.FunctionDef) and n.name=='lpips_PIL')
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),scope);metric=scope['lpips_PIL'];device=torch.device('cpu')
 class Spy(torch.nn.Module):
  def forward(self,a,b):
   self.seen=dict(shape=list(a.shape),dtype=str(a.dtype),device=str(a.device),black_min=float(a.min()),black_max=float(a.max()),white_min=float(b.min()),white_max=float(b.max()));return torch.zeros(1)
 spy=Spy();metric(Image.new('RGB',(512,512)),Image.new('RGB',(512,512),'white'),spy,device)
 assert spy.seen==dict(shape=[1,3,512,512],dtype='torch.float32',device='cpu',black_min=-1.,black_max=-1.,white_min=1.,white_max=1.)
 tick=time.perf_counter();loss=lpips.LPIPS(net='alex',version='0.1',pretrained=True,pnet_rand=False,model_path=str(LINEAR),eval_mode=True,verbose=False).to(device);loss.eval();load_seconds=time.perf_counter()-tick
 if loss.training or any(m.training for m in loss.modules()) or any(p.device.type!='cpu' for p in loss.parameters()) or blocked:raise ValueError('Metric mode/device/offline admission failed')
 with Image.open(RUN/'prepare/1/cover.png') as image:
  with torch.no_grad():zero=metric(image,image,loss,device)
 if not math.isfinite(zero) or abs(zero)>1e-8:raise ValueError('Same-image LPIPS must be zero')
 versions={n:importlib.metadata.version(n) for n in ['torch','torchvision','lpips','numpy','Pillow']}
 write(out/'qa.json',dict(completed=True,helper_source_sha256=sha(source),helper_git_blob='43c6755a9b132e8ac33fbb63ab38b85506a2cf85',input_spy=spy.seen,same_image_lpips=zero,model_training=loss.training,all_modules_eval=True,all_parameters_cpu=True,cuda_initialized=False,versions=versions,network_attempts=len(blocked),model_load_seconds=load_seconds,lpips_version='0.1',pnet_rand=False,pretrained=True,resize_or_imagenet_crop=False,weights=WEIGHTS));print('QA_COMPLETED_CPU_OFFLINE',flush=True)
 scores=[];tick=time.perf_counter()
 with (out/'rows.jsonl').open('x',encoding='utf8') as stream:
  for row in plan['inputs']:
   if sha(row['image_path'])!=row['image_sha256'] or sha(row['cover_path'])!=row['cover_sha256']:raise ValueError('Pair changed')
   with Image.open(row['image_path']) as a,Image.open(row['cover_path']) as b:
    if a.mode!='RGB' or b.mode!='RGB' or a.size!=(512,512) or b.size!=(512,512):raise ValueError('Expected unchanged RGB512 pair')
    begin=time.perf_counter()
    with torch.no_grad():value=metric(a,b,loss,device)
   if not math.isfinite(value) or value<0 or (row['label']=='cover' and abs(value)>1e-8):raise ValueError('Invalid LPIPS')
   score=dict(**row,lpips=value,seconds=time.perf_counter()-begin);scores.append(score);stream.write(json.dumps(score)+'\n');stream.flush();print('SCORED_CPU',row['task_id'],row['label'],flush=True)
 groups={str(n):dict(n=4,mean_lpips=statistics.mean(r['lpips'] for r in scores if r['label']==str(n)),values=[r['lpips'] for r in scores if r['label']==str(n)]) for n in POINTS}
 if len(scores)!=28 or inputs()!=plan['inputs'] or any(sha(RUN/p)!=h for p,h in original_hashes.items()) or blocked or torch.cuda.is_initialized():raise ValueError('Post-compute seal/device check failed')
 for name,digest in WEIGHTS.items():
  if sha(name)!=digest:raise ValueError('Weight changed')
 write(out/'summary.json',dict(completed=True,posthoc_quality_supplement=True,not_preregistered_primary_metric=True,candidate_selection='All original presealed endpoints; no selection or candidate change',original_run=str(RUN),original_file_hashes_unchanged=original_hashes,rows=scores,checkpoints=groups,primary_actual_update=151,secondary_actual_update=150,network_attempts=0,gpu_used=False,cuda_initialized=False,metric_compute_seconds=time.perf_counter()-tick,total_worker_seconds=time.perf_counter()-start,peak_cpu_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,finished_at_utc=now(),qa_sha256=sha(out/'qa.json')));print('COMPLETED_POSTHOC_LPIPS_CPU',flush=True)
if __name__=='__main__':main(sys.argv[1])
