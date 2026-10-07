"""CPU-only, bounded official artifact acquisition. No package installation."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import argparse, ast, hashlib, json, re, shutil, sys, tarfile, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMITS = {'clip': 'd05afc436d78f1c48dc0dbf8e5980a9d471f35f6',
           'dinov2': '7764ea0f912e53c92e82eb78a2a1631e92725fc8',
           'sscd': '95902662f2217a5f4aa45f2a3fc70a01dfd3b66a'}
BUDGET = 1_500_000_000
LEDGER = ROOT / 'artifacts/downloads.json'
ledger = []

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def save_ledger():
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding='utf-8')

def fetch(url, dst, cap=500_000_000):
    dst = Path(dst); dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists(): return dst
    used = sum(x['bytes'] for x in ledger)
    req = urllib.request.Request(url, headers={'User-Agent':'Watermark2-Research-Smoke/1.0 (noncommercial research)'})
    part = dst.with_suffix(dst.suffix+'.part')
    n = 0
    try:
        with urllib.request.urlopen(req, timeout=35) as r, part.open('wb') as f:
            expected = int(r.headers.get('Content-Length', 0))
            if expected > cap or used+expected>BUDGET: raise RuntimeError('download budget exceeded')
            while True:
                b = r.read(1024*1024)
                if not b: break
                n += len(b)
                if n>cap or used+n>BUDGET: raise RuntimeError('download budget exceeded')
                f.write(b)
        part.replace(dst)
        ledger.append(dict(url=url,path=str(dst.relative_to(ROOT)),bytes=n,sha256=sha(dst),status='complete'))
        save_ledger()
        print('downloaded',dst,n,flush=True)
        return dst
    except Exception:
        if n:
            ledger.append(dict(url=url,path=str(part.relative_to(ROOT)),bytes=n,status='failed_transfer'))
            save_ledger()
        raise

def sources_and_weights():
    info = {}
    for name, repo in [('clip','openai/CLIP'),('dinov2','facebookresearch/dinov2')]:
        arc=fetch('https://codeload.github.com/'+repo+'/tar.gz/'+COMMITS[name],ROOT/'artifacts'/f'{name}.tar.gz',30_000_000)
        dest=ROOT/'third_party'/name
        if not dest.exists():
            staging=ROOT/'third_party'/('_unpack_'+name); staging.mkdir(parents=True,exist_ok=True)
            with tarfile.open(arc) as tf:
                for member in tf.getmembers():
                    target=(staging/member.name).resolve()
                    if not target.is_relative_to(staging.resolve()) or member.issym() or member.islnk():
                        raise ValueError('unsafe archive entry')
                tf.extractall(staging)
            entries=list(staging.iterdir()); assert len(entries)==1
            entries[0].rename(dest); staging.rmdir()
    text=(ROOT/'third_party/clip/clip/clip.py').read_text()
    models=next(ast.literal_eval(n.value) for n in ast.parse(text).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_MODELS' for t in n.targets))
    urls={'clip':models['ViT-B/32'],
          'sscd':'https://dl.fbaipublicfiles.com/sscd-copy-detection/sscd_disc_mixup.torchscript.pt',
          'dinov2':'https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth'}
    for name,url in urls.items():
        dest=ROOT/'weights'/url.rsplit('/',1)[-1]
        fetch(url,dest)
        digest=sha(dest)
        if name=='clip': assert digest==url.split('/')[-2], 'CLIP official SHA mismatch'
        info[name]=dict(path=dest.relative_to(ROOT).as_posix(),sha256=digest,bytes=dest.stat().st_size,url=url,code_commit=COMMITS[name])
    (ROOT/'artifacts/models.json').write_text(json.dumps(info,indent=2), encoding='utf-8')

def images():
    params=dict(action='query',format='json',generator='search',gsrsearch='landscape filetype:bitmap',gsrnamespace=6,gsrlimit=40,prop='imageinfo',iiprop='url|extmetadata',iiurlwidth=640)
    url='https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(params)
    meta=fetch(url,ROOT/'artifacts/commons_query.json',4_000_000)
    pages=json.loads(meta.read_text(encoding='utf-8'))['query']['pages']
    sources=[]
    for page in sorted(pages.values(),key=lambda x:x['index']):
        if len(sources)>=20: break
        # Visual source audit: this Commons item is an oil painting, not a photograph.
        # Exclusion is by media type, independent of any model score.
        if page['pageid']==30727835: continue
        ii=page['imageinfo'][0]; ex=ii.get('extmetadata',{})
        val=lambda k:ex.get(k,{}).get('value','')
        license=val('LicenseShortName')
        if not any(s in license.lower() for s in ['cc by','cc0','public domain']): continue
        if not page['title'].lower().endswith(('.jpg','.jpeg','.png')): continue
        path=ROOT/'data/stage02/source'/f"commons_{page['pageid']}.jpg"
        try: fetch(ii['thumburl'],path,3_000_000)
        except Exception as e:
            print('image failed',page['title'],type(e).__name__,str(e),flush=True); continue
        sources.append(dict(id=f"commons_{page['pageid']}",path=path.relative_to(ROOT).as_posix(),sha256=sha(path),title=page['title'],source_url=ii['descriptionurl'],download_url=ii['thumburl'],license=license,license_url=val('LicenseUrl'),author_html=val('Artist'),description_html=val('ImageDescription')))
    (ROOT/'data/stage02/sources.json').write_text(json.dumps(sources,indent=2,ensure_ascii=False), encoding='utf-8')
    (ROOT/'data/stage02/source_audit.json').write_text(json.dumps(dict(exclusions={'30727835':'landscape painting, not a natural photograph'},replacement_rule='next licensed photograph in frozen Commons query rank',query='artifacts/commons_query.json'),indent=2),encoding='utf-8')
    print('natural source images',len(sources),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--models',action='store_true');p.add_argument('--images',action='store_true');a=p.parse_args()
    if LEDGER.exists(): ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
    if a.models:sources_and_weights()
    if a.images:images()
