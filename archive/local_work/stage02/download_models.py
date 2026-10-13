import concurrent.futures
import hashlib
import json
import struct
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'hub'
manifest = []
for repo in ['stabilityai/stable-diffusion-xl-base-1.0', 'Manojb/stable-diffusion-2-1-base']:
    meta = json.loads((ROOT/repo.replace('/', '--')/'metadata.json').read_text())
    index = json.loads((ROOT/repo.replace('/', '--')/'model_index.json').read_text())
    components = {k for k,v in index.items() if isinstance(v,list) and len(v)==2 and v[0] is not None}
    selected = []
    for f in meta['siblings']:
        path = f['rfilename']
        if path == 'model_index.json' or (path.split('/')[0] in components and
            (path.endswith(('.json','.txt')) or path.endswith('.safetensors') and '.fp16.' not in path)):
            selected.append(f)
    manifest.append({'repo':repo, 'revision':meta['sha'], 'files':selected})
(ROOT/'model_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('planned_bytes',sum(f['size'] for m in manifest for f in m['files']),flush=True)

def getfile(m,f):
    repo, rev = m['repo'],m['revision']
    path=f['rfilename']
    dst=CACHE/('models--'+repo.replace('/','--'))/'snapshots'/rev/path
    dst.parent.mkdir(parents=True,exist_ok=True)
    expected=f.get('lfs',{}).get('sha256')
    url=f'https://huggingface.co/{repo}/resolve/{rev}/{path}'
    if not dst.exists():
        temp=dst.with_suffix(dst.suffix+'.partial')
        if temp.exists():
            raise RuntimeError('existing partial requires explicit resume: '+path)
        print('download',repo,path,f['size'],flush=True)
        with urllib.request.urlopen(url,timeout=60) as response, temp.open('xb') as out:
            while True:
                data=response.read(8*1024*1024)
                if not data: break
                out.write(data)
        if temp.stat().st_size != f['size']: raise RuntimeError('size mismatch '+path)
        temp.rename(dst)
    h=hashlib.sha256()
    with dst.open('rb') as stream:
        for data in iter(lambda:stream.read(8*1024*1024),b''): h.update(data)
    sha=h.hexdigest()
    if expected and sha != expected: raise RuntimeError('sha256 mismatch '+path)
    f['verified_sha256']=sha
    f['local_path']=str(dst)
    if path.endswith('.safetensors'):
        with dst.open('rb') as stream:
            n=struct.unpack('<Q',stream.read(8))[0]
            header=json.loads(stream.read(n))
        types=sorted(set(v['dtype'] for k,v in header.items() if k!='__metadata__'))
        f['tensor_dtypes']=types
        if any(t in ['F16','BF16'] for t in types): raise RuntimeError('non-float32 weights '+path)
    print('verified',repo,path,sha,flush=True)
    return f

# Inspect component configuration before fetching weights.
for m in manifest:
    for f in m['files']:
        if not f['rfilename'].endswith('.safetensors'):
            getfile(m,f)
            if f['rfilename'].endswith('config.json'):
                c=json.loads(Path(f['local_path']).read_text())
                print('component_config',m['repo'],f['rfilename'],'dtype',c.get('torch_dtype'),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(getfile,m,f) for m in manifest for f in m['files'] if f['rfilename'].endswith('.safetensors')]
    for fut in concurrent.futures.as_completed(futures): fut.result()
for m in manifest:
    refs=CACHE/('models--'+m['repo'].replace('/','--'))/'refs'
    refs.mkdir(exist_ok=True)
    (refs/'main').write_text(m['revision'],encoding='ascii')
(ROOT/'model_manifest_verified.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('ALL_MODELS_VERIFIED',flush=True)
