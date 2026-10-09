"""Read-only public cache/code provenance and exact stage digest helpers."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def array_binding(array):
    import numpy as np
    a=np.ascontiguousarray(array)
    return {'shape':list(a.shape),'dtype':str(a.dtype),'sha256_c_order_bytes':hashlib.sha256(a.tobytes(order='C')).hexdigest()}

def public_cache_provenance(sd_cache,clip_code):
    versions={}
    for name in ('torch','numpy','Pillow','diffusers','transformers','accelerate','safetensors'):
        versions[name]=importlib.metadata.version(name)
    tiny={}
    for label,root in [('sd',Path(sd_cache)),('clip',Path(clip_code))]:
        tiny[label]={}
        for p in sorted(root.rglob('*')):
            if p.is_file() and p.stat().st_size <= 16*1024*1024 and p.suffix.lower() in {
                '.json','.txt','.md','.gz','.model','.py'} and '__pycache__' not in p.parts:
                tiny[label][str(p.relative_to(root))]={'sha256':file_sha(p),'bytes':p.stat().st_size}
        for name in ('LICENSE','NOTICE'):
            p=root/name
            if p.is_file():tiny[label][name]={'sha256':file_sha(p),'bytes':p.stat().st_size}
    return {'observed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'versions':versions,'public_small_artifacts':tiny,'sd_snapshot':Path(sd_cache).name,
        'scope':'current read-only cache observation; earlier run package versions not retroactively proven'}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sd-cache',required=True);ap.add_argument('--clip-code',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args()
    p=Path(args.output);assert not p.exists()
    p.write_text(json.dumps(public_cache_provenance(args.sd_cache,args.clip_code),indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
