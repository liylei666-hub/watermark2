import concurrent.futures, hashlib, json, os, struct, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent; CACHE=ROOT/'hub'
manifest=json.loads((ROOT/'model_manifest.json').read_text())
def download(m,f):
    repo,rev=m['repo'],m['revision']; path=f['rfilename']; size=f['size']
    dst=CACHE/('models--'+repo.replace('/','--'))/'snapshots'/rev/path; dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists() and dst.stat().st_size==size: return verify(m,f,dst)
    url='https://huggingface.co/{}/resolve/{}/{}'.format(repo,rev,path)
    tmp=dst.with_suffix(dst.suffix+'.partial');
    with tmp.open('wb') as out: out.truncate(size)
    chunk=16*1024*1024
    ranges=[(i,min(i+chunk,size)-1) for i in range(0,size,chunk)]
    def one(pair):
        a,b=pair; req=urllib.request.Request(url,headers={'Range':'bytes={}-{}'.format(a,b)})
        with urllib.request.urlopen(req,timeout=120) as r:
            if r.status!=206: raise RuntimeError('range unsupported {} {}'.format(path,r.status))
            data=r.read()
        if len(data)!=b-a+1: raise RuntimeError('short range {}'.format(path))
        with tmp.open('r+b') as out: out.seek(a); out.write(data)
    print('download',repo,path,size,flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for fut in concurrent.futures.as_completed([pool.submit(one,x) for x in ranges]): fut.result()
    tmp.rename(dst); return verify(m,f,dst)
def verify(m,f,dst):
    h=hashlib.sha256()
    with dst.open('rb') as s:
        for b in iter(lambda:s.read(16*1024*1024),b''): h.update(b)
    sha=h.hexdigest(); expected=f.get('lfs',{}).get('sha256')
    if expected and sha!=expected: raise RuntimeError('sha mismatch '+str(dst))
    print('verified',m['repo'],f['rfilename'],sha,flush=True)
    return f
for m in manifest:
    for f in m['files']:
        download(m,f)
    refs=CACHE/('models--'+m['repo'].replace('/','--'))/'refs'; refs.mkdir(exist_ok=True)
    (refs/'main').write_text(m['revision'])
(ROOT/'model_manifest_verified.json').write_text(json.dumps(manifest,indent=2))
print('ALL_MODELS_VERIFIED',flush=True)
