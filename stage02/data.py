import hashlib, io, json, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from .core import dump, sha256, validate_manifest

def dhash(im):
    a=np.asarray(im.convert('L').resize((9,8),Image.Resampling.BILINEAR))
    return a[:,1:]>a[:,:-1]

def allowed_variants(im):
    """The six frozen stage02 edits, shared with stage03 at the input's native size."""
    w,h=im.size
    for q in [90,70]:
        buf=io.BytesIO();im.save(buf,format='JPEG',quality=q,subsampling=2);buf.seek(0);new=Image.open(buf).convert('RGB')
        yield f'jpeg{q}',new,dict(kind='jpeg',quality=q,subsampling=2,order=['JPEG encode','decode RGB','PNG'])
    for scale in [.75,.5]:
        small=(round(w*scale),round(h*scale));new=im.resize(small,Image.Resampling.BICUBIC).resize((w,h),Image.Resampling.BICUBIC)
        yield f'scale{scale}',new,dict(kind='resize',scale=scale,interpolation='Pillow bicubic',intermediate_size=small,order=['downsample','restore','PNG'])
    for factor in [.95,1.05]:
        yield f'brightness{factor}',ImageEnhance.Brightness(im).enhance(factor),dict(kind='brightness',factor=factor,order=['Pillow RGB brightness','PNG'])

def prepare(root,seed):
    src=json.loads((root/'data/stage02/sources.json').read_text())
    if len(src)<10:raise RuntimeError('insufficient natural sources; do not substitute synthetic results')
    rng=np.random.default_rng(seed); base={};parents={s['id']:s['id'] for s in src}
    def find(x):
        while parents[x]!=x:x=parents[x]
        return x
    edges=[]
    for s in src:
        if sha256(root/s['path'])!=s['sha256']:raise ValueError('source SHA mismatch')
        im=ImageOps.exif_transpose(Image.open(root/s['path'])).convert('RGB')
        im.thumbnail((512,512),Image.Resampling.LANCZOS);base[s['id']]=im
    ids=sorted(base);hashes={i:dhash(base[i]) for i in ids};pixels={i:np.asarray(base[i].resize((32,32))).astype(float)/255 for i in ids}
    for k,a in enumerate(ids):
        for b in ids[k+1:]:
            if np.sum(hashes[a]!=hashes[b])<=8 or np.mean((pixels[a]-pixels[b])**2)<.002:
                edges.append([a,b]);parents[find(b)]=find(a)
    groups=sorted({find(i) for i in ids});rng.shuffle(groups)
    split_by_group={g:'smoke_calibration' if k<len(groups)//2 else 'smoke_test' for k,g in enumerate(groups)}
    images=[];pairs=[];provenance={s['id']:s for s in src}
    def add(i,im,original):
        path=Path('data/stage02/images')/(i+'.png');(root/path).parent.mkdir(parents=True,exist_ok=True)
        im.convert('RGB').save(root/path,format='PNG',compress_level=6)
        images.append(dict(id=i,path=str(path),sha256=sha256(root/path),pixel_sha256=hashlib.sha256(np.asarray(im).tobytes()+str(im.size).encode()).hexdigest(),
                           group=find(original),original=original,split=split_by_group[find(original)],size=list(im.size),source_url=provenance[original]['source_url']))
    def pair(i,j,category,params,donor=None,mask=None):
        pairs.append(dict(pair_id=f'{i}__{j}',group=find(i),left=i,right=j,category=category,split=split_by_group[find(i)],params=params,source=provenance[i]['source_url'],donor=donor,mask=mask))
    for i in ids:add(i,base[i],i)
    for i in ids:
        im=base[i];w,h=im.size
        for suffix,new,params in allowed_variants(im):
            j=f'{i}_{suffix}';add(j,new,i);pair(i,j,'A',params)
        candidates=[k for k in ids if split_by_group[find(k)]==split_by_group[find(i)] and find(k)!=find(i)]
        donor=candidates[int(rng.integers(len(candidates)))];donor_im=base[donor].resize((w,h),Image.Resampling.BICUBIC)
        for area in [.05,.15]:
            bw=max(1,round(w*math.sqrt(area)));bh=max(1,round(h*math.sqrt(area)))
            x=int(rng.integers(w-bw+1));y=int(rng.integers(h-bh+1));box=[x,y,x+bw,y+bh]
            new=im.copy();new.paste(donor_im.crop(box),(x,y));mask=Image.new('L',(w,h));mask.paste(255,box)
            j=f'{i}_patch{area}';mp=Path('data/stage02/masks')/(j+'.png');(root/mp).parent.mkdir(parents=True,exist_ok=True);mask.save(root/mp)
            add(j,new,i);pair(i,j,'C_proxy',dict(kind='rectangular donor replacement',target_area=area,actual_area=bw*bh/(w*h),box=box,interpolation='Pillow bicubic donor resize',order=['resize donor','paste rectangle','PNG']),donor,str(mp))
        pair(i,i,'SELF',dict(kind='identity check'))
    for k,a in enumerate(ids):
        for b in ids[k+1:]:
            if split_by_group[find(a)]==split_by_group[find(b)] and find(a)!=find(b):pair(a,b,'D',dict(kind='different originals'))
    manifest=dict(seed=seed,images=images,pairs=pairs,near_duplicate_edges=edges,near_duplicate_policy='dHash<=8/64 OR 32x32 RGB MSE<0.002, connected components before split; contact sheet reviewed separately',B='missing',sources=src)
    validate_manifest(manifest);dump(root/'data/stage02/manifest.json',manifest)
    # This manifest is the feature extractor's only input. No labels, masks, or donors.
    dump(root/'data/stage02/image_inputs.json',[{k:x[k] for k in ['id','path','sha256']} for x in images])
    return manifest
