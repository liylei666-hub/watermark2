import concurrent.futures
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parent
REMOTE = '/data0/liyanlei/watermark_research/cache/huggingface/hub/'
SSH = ['ssh','-i','C:/Users/liylei/.ssh/ceramic_249_ed25519','-o','BatchMode=yes','liyanlei@172.18.185.249']
SCP = ['scp','-C','-X','buffer=262144','-X','nrequests=128','-i','C:/Users/liylei/.ssh/ceramic_249_ed25519','-o','BatchMode=yes']

def remote(code):
    return subprocess.check_output(SSH+['python3 -c '+shlex.quote(code)], text=True)

def transfer(item):
    local,rel,sha=item
    dst=REMOTE+rel
    code = 'from pathlib import Path; import hashlib; p=Path('+repr(dst)+'); print(hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() and p.stat().st_size<1000000000 else "unchecked")'
    if remote(code).strip()==sha:
        print('REUSED',rel,flush=True); return
    tmp=dst+'.relay_02_partial'
    remote('from pathlib import Path; p=Path('+repr(tmp)+'); p.parent.mkdir(parents=True,exist_ok=True); assert not p.exists(),str(p)')
    start=time.monotonic()
    subprocess.run(SCP+[str(local),'liyanlei@172.18.185.249:'+tmp],check=True)
    code='''from pathlib import Path
import hashlib
p=Path(%r); dst=Path(%r)
h=hashlib.sha256()
with p.open('rb') as f:
 for b in iter(lambda:f.read(16777216),b''): h.update(b)
assert p.stat().st_size==%d and h.hexdigest()==%r
if dst.exists():
 backup=dst.with_name(dst.name+'.interrupted_scp'); assert not backup.exists(); dst.rename(backup)
p.rename(dst)
'''%(tmp,dst,local.stat().st_size,sha)
    remote(code)
    print('TRANSFER_VERIFIED',rel,round(time.monotonic()-start,1),flush=True)

manifest=json.loads((ROOT/'model_manifest.json').read_text())
for m in manifest:
    base='models--'+m['repo'].replace('/','--')
    ref=ROOT/'hub'/base/'refs/main'
    while not ref.exists():
        time.sleep(10)
    items=[]
    for f in m['files']:
        rel=base+'/snapshots/'+m['revision']+'/'+f['rfilename']
        local=ROOT/'hub'/rel
        assert local.stat().st_size==f['size']
        sha=f.get('lfs',{}).get('sha256')
        if not sha: sha=hashlib.sha256(local.read_bytes()).hexdigest()
        f['sha256']=sha
        items.append((local,rel,sha))
    items.sort(key=lambda i:i[0].stat().st_size,reverse=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(transfer,items): pass
    transfer((ref,base+'/refs/main',hashlib.sha256(ref.read_bytes()).hexdigest()))
    print('MODEL_RELAY_COMPLETE',m['repo'],flush=True)
(ROOT/'model_manifest_verified.json').write_text(json.dumps(manifest,indent=2))
print('ALL_RELAY_COMPLETE',flush=True)
