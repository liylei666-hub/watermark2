"""A bounded CPU diagnostic using existing authorized photographs and SSCD weights.

Constructed placards carry explicit facts; they are NOT natural-image semantic edits.
Separate prepare, review and score stages prevent score-driven label selection.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform
import sys
import time
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES'] = ''
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/cpu_pilot'
OUT = ROOT / 'reports/cpu_pilot'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def config():
    return load(ROOT / 'configs/cpu_pilot.json')


def placard(image, box, font, variant):
    from PIL import ImageDraw
    im = image.copy()
    d = ImageDraw.Draw(im)
    x, y, w, h = box
    d.rectangle((x, y, x+w-1, y+h-1), fill='white', outline=(80,80,80), width=2)
    dark = (45,45,45) if variant == 'process_control' else (0,0,0)
    for k in (1,2):
        d.line((x+64*k, y, x+64*k, y+h-1), fill=(180,180,180), width=1)
    d.text((x+6,y+4), 'N', font=font, fill=dark)
    for i in range(3 if variant == 'count' else 2):
        cx = x+12+18*i
        d.ellipse((cx-5,y+47,cx+5,y+57), fill=dark)
    d.text((x+69,y+24), '80' if variant == 'text' else '30', font=font, fill=dark)
    left, right = (x+145,x+176) if variant != 'relation' else (x+176,x+145)
    d.ellipse((left-7,y+33,left+7,y+47), fill=(190,20,20))
    d.rectangle((right-7,y+33,right+7,y+47), fill=(20,60,190))
    return im


def prepare(asset_root, font_path):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    cfg = config()
    if (OUT/'manifest.json').exists():
        raise RuntimeError('Run already prepared; use a new experiment ID/directory rather than overwrite')
    font = ImageFont.truetype(str(font_path), 26)
    sources = [s for s in load(ROOT/'legacy/data/stage02/sources.json') if s['id'] not in cfg['exclude_source_ids']]
    old = load(ROOT/'legacy/data/stage02/manifest.json')
    splits = {r['id']:r['split'].replace('smoke_', '') for r in old['images'] if r['id']==r['original']}
    assert len(sources)==cfg['source_count']
    RUN.mkdir(parents=True,exist_ok=True)
    records=[]; source_log=[]
    seen=set()
    thumb=Image.new('RGB',(800, len(sources)*86),'white')
    for n, src in enumerate(sorted(sources,key=lambda s:s['id'])):
        path=asset_root/src['path']
        assert digest(path)==src['sha256'], path
        with Image.open(path) as image:
            base=ImageOps.exif_transpose(image).convert('RGB').resize((512,512),Image.Resampling.BICUBIC)
        pixel_hash=hashlib.sha256(base.tobytes()).hexdigest()
        assert pixel_hash not in seen, 'duplicate normalized source'
        seen.add(pixel_hash)
        # Placement frozen from ID, unrelated to scores or image semantics.
        code=int(hashlib.sha256(src['id'].encode()).hexdigest()[:8],16)
        box=[24 if code%2==0 else 296,24 if (code//2)%2==0 else 392,192,72]
        ref=placard(base,box,font,'reference')
        variants={'reference':ref}
        for quality in (70,90):
            buffer=io.BytesIO();ref.save(buffer,format='JPEG',quality=quality,subsampling=2)
            buffer.seek(0);variants['jpeg'+str(quality)]=Image.open(buffer).convert('RGB')
        for scale in (.5,.75):
            variants['resize'+str(scale)]=ref.resize((int(512*scale),int(512*scale)),Image.Resampling.BICUBIC).resize((512,512),Image.Resampling.BICUBIC)
        for variant in ['count','text','relation','process_control']:
            variants[variant]=placard(base,box,font,variant)
        for variant,im in variants.items():
            out=RUN/'images'/f"{src['id']}_{variant}.png";out.parent.mkdir(parents=True,exist_ok=True);im.save(out)
            diff=np.any(np.asarray(im)!=np.asarray(ref),axis=2)
            if variant in cfg['modifications']+['process_control']:
                x,y,w,h=box;outside=diff.copy();outside[y:y+h,x:x+w]=False
                assert not outside.any() and diff.any()
            records.append(dict(id=src['id']+'_'+variant,source_id=src['id'],split=splits[src['id']],variant=variant,
                                path=str(out.relative_to(ROOT)).replace('\\','/'),sha256=digest(out),changed_pixels=int(diff.sum()),box=box,
                                facts=dict(count=3 if variant=='count' else 2,text='80' if variant=='text' else '30',
                                           relation='red_right_of_blue' if variant=='relation' else 'red_left_of_blue')))
        x,y,w,h=box
        for col,variant in enumerate(['reference','count','text','relation']):
            thumb.paste(variants[variant].crop((x,y,x+w,y+h)),(col*200,n*86+14))
            ImageDraw.Draw(thumb).text((col*200,n*86),src['id']+' '+variant,fill='black')
        source_log.append(dict(src,split=splits[src['id']],normalized_pixel_sha256=pixel_hash))
    thumb.save(RUN/'fact_review.png')
    # A complete reference contact sheet for source-level visual duplicate review.
    sheet=Image.new('RGB',(1000,4*220),'white')
    for n,src in enumerate(sorted(sources,key=lambda s:s['id'])):
        im=Image.open(RUN/'images'/f"{src['id']}_reference.png")
        sheet.paste(im.resize((196,196)),((n%5)*200,(n//5)*220+20))
        ImageDraw.Draw(sheet).text(((n%5)*200,(n//5)*220),src['id']+' '+splits[src['id']],fill='black')
    sheet.save(RUN/'source_review.png')
    save(OUT/'manifest.json',records);save(OUT/'sources.json',source_log)
    save(OUT/'frozen_inputs.json',dict(config=cfg,config_sha256=digest(ROOT/'configs/cpu_pilot.json'),
                                    manifest_sha256=digest(OUT/'manifest.json'),sources_sha256=digest(OUT/'sources.json'),
                                    script_sha256=digest(Path(__file__)),font_sha256=digest(font_path),
                                    font_name=font_path.name,variants=len(records),labels='known rendered facts; AI visual review pending',
                                    excluded=[dict(id='commons_30727835',reason='excluded by existing source audit: painting')]+[dict(id=sid,reason=cfg['exclusion_reason']) for sid in cfg['exclude_source_ids']]))
    print(json.dumps(dict(prepared=len(records),sources=len(sources),review_sheet=str(RUN/'fact_review.png')),indent=2))


def fit(values, target):
    a=sorted(values)
    if not a or not all(math.isfinite(v) for v in a) or not 0<=target<1:
        raise ValueError('invalid calibration')
    return a[math.floor(target*len(a))]


def score(asset_root):
    import numpy as np
    import torch
    from PIL import Image, __version__ as pillow_version
    cfg=config(); frozen=load(OUT/'frozen_inputs.json')
    assert digest(ROOT/'configs/cpu_pilot.json')==frozen['config_sha256']
    assert digest(OUT/'manifest.json')==frozen['manifest_sha256']
    assert digest(Path(__file__))==frozen['script_sha256'], 'implementation changed after freeze'
    review=load(OUT/'visual_review.json');assert review['status']=='ready_for_scoring'
    model_path=asset_root/'weights'/cfg['model'];assert digest(model_path)==cfg['model_sha256']
    torch.set_num_threads(cfg['threads']);torch.set_num_interop_threads(1);torch.manual_seed(cfg['seed'])
    torch.use_deterministic_algorithms(True)
    started=time.perf_counter()
    # File objects avoid TorchScript's Windows non-ASCII path handling issue.
    with model_path.open('rb') as model_file:
        model=torch.jit.load(model_file,map_location='cpu').eval()
    records=load(OUT/'manifest.json');features={}; timings={}; mean=np.array(cfg['mean'],dtype=np.float32);std=np.array(cfg['std'],dtype=np.float32)
    def extract(record):
        assert digest(ROOT/record['path'])==record['sha256']
        image=Image.open(ROOT/record['path']).convert('RGB')
        arrays=[]
        for box in cfg['views']:
            a=np.asarray(image.crop(box).resize(tuple(cfg['model_resize']),Image.Resampling.BILINEAR),dtype=np.float32)/255.
            arrays.append(np.transpose((a-mean)/std,(2,0,1)))
        batch=torch.from_numpy(np.stack(arrays))
        start=time.perf_counter()
        with torch.inference_mode():
            y=model(batch).float().numpy()
        timings[record['id']]=time.perf_counter()-start
        norms=np.linalg.norm(y,axis=1,keepdims=True);assert np.isfinite(y).all() and (norms>0).all()
        return y/norms
    for n,r in enumerate(records):
        if time.perf_counter()-started > cfg['wall_limit_seconds']:
            raise RuntimeError('CPU wall budget exhausted; do not report partial results as complete')
        features[r['id']]=extract(r)
        if n%10==0: print(f'extracted {n+1}/{len(records)} elapsed={time.perf_counter()-started:.1f}s',flush=True)
    repeat=extract(records[0]);repeat_error=float(np.max(abs(repeat-features[records[0]['id']])))
    assert repeat_error<1e-5
    np.savez_compressed(RUN/'features.npz',**features)
    rows=[]
    for r in records:
        if r['variant']=='reference':continue
        cosine=np.sum(features[r['source_id']+'_reference']*features[r['id']],axis=1)
        rows.append(dict(source_id=r['source_id'],split=r['split'],variant=r['variant'],global_score=float(cosine[0]),multiscale_min=float(cosine.min())))
    for split in ('calibration','test'):
        ids=sorted({r['source_id'] for r in records if r['split']==split})
        for i,source in enumerate(ids):
            donor=ids[(i+1)%len(ids)];cosine=np.sum(features[source+'_reference']*features[donor+'_reference'],axis=1)
            rows.append(dict(source_id=source,split=split,variant='replacement',global_score=float(cosine[0]),multiscale_min=float(cosine.min())))
    methods=['global_score','multiscale_min'];thresholds={m:fit([r[m] for r in rows if r['split']=='calibration' and r['variant'] in cfg['allowed']],cfg['target_frr']) for m in methods}
    save(OUT/'thresholds.json',dict(values=thresholds,fit_split='calibration',target_frr=cfg['target_frr'],accept='score >= threshold',calibration_pairs=sum(r['split']=='calibration' and r['variant'] in cfg['allowed'] for r in rows)))
    with (OUT/'scores.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    metrics={}
    for m in methods:
        metrics[m]={}
        for split in ('calibration','test'):
            metrics[m][split]={}
            for category in cfg['allowed']+cfg['modifications']+['process_control','replacement','allowed_pooled']:
                selected=[r for r in rows if r['split']==split and (r['variant'] in cfg['allowed'] if category=='allowed_pooled' else r['variant']==category)]
                accepted=[int(r[m]>=thresholds[m]) for r in selected]
                ids=sorted({r['source_id'] for r in selected})
                macro=np.mean([np.mean([int(r[m]>=thresholds[m]) for r in selected if r['source_id']==sid]) for sid in ids])
                metrics[m][split][category]=dict(accepted=sum(accepted),total=len(accepted),source_groups=len(ids),rate=float(np.mean(accepted)),source_macro=float(macro),
                                               score_min=min(r[m] for r in selected),score_median=float(np.median([r[m] for r in selected])),score_max=max(r[m] for r in selected))
    # Paired source resampling, refit calibration thresholds each replicate.
    rng=np.random.default_rng(cfg['seed']);calids=sorted({r['source_id'] for r in rows if r['split']=='calibration'});testids=sorted({r['source_id'] for r in rows if r['split']=='test'})
    categories=cfg['allowed']+cfg['modifications']+['process_control','replacement','allowed_pooled'];diffs={c:[] for c in categories}
    cal={m:np.array([[r[m] for r in rows if r['source_id']==sid and r['variant'] in cfg['allowed']] for sid in calids]) for m in methods}
    tests={m:{c:np.array([[r[m] for r in rows if r['source_id']==sid and (r['variant'] in cfg['allowed'] if c=='allowed_pooled' else r['variant']==c)] for sid in testids]) for c in categories} for m in methods}
    for _ in range(cfg['bootstrap_replicates']):
        ci=rng.integers(len(calids),size=len(calids));ti=rng.integers(len(testids),size=len(testids))
        th={m:fit(cal[m][ci].ravel().tolist(),cfg['target_frr']) for m in methods}
        for c in categories:
            rates={m:float(np.mean(tests[m][c][ti]>=th[m])) for m in methods}
            diffs[c].append(rates['multiscale_min']-rates['global_score'])
    intervals={c:dict(point=metrics['multiscale_min']['test'][c]['rate']-metrics['global_score']['test'][c]['rate'],low=float(np.quantile(v,.025)),high=float(np.quantile(v,.975))) for c,v in diffs.items()}
    save(OUT/'metrics.json',dict(status='complete',scope=cfg['scope'],metrics=metrics,paired_acceptance_delta_multiscale_minus_global=intervals,
                               bootstrap=dict(replicates=cfg['bootstrap_replicates'],unit='source',refit_calibration=True,seed=cfg['seed'],limitation='small exploratory reused-source sample; replacement conditions on fixed cyclic donors'),
                               failures=dict(input_hash=0,feature_extraction=0,nonfinite=0),new_experiment=True,full_watermark_verifier=False))
    save(OUT/'runtime.json',dict(device='cpu',CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],threads=cfg['threads'],python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,pillow=pillow_version,
                               model_sha256=digest(model_path),script_sha256=digest(Path(__file__)),seconds=time.perf_counter()-started,images=len(records),views_per_image=5,embedding_dimension=int(repeat.shape[1]),
                               repeat_max_abs=repeat_error,total_model_forward_seconds=sum(timings.values()),reference_bytes_global=int(repeat[0].nbytes),reference_bytes_multiscale=int(repeat.nbytes),
                               score_sha256=digest(OUT/'scores.csv'),features_sha256=digest(RUN/'features.npz'),per_image_forward_seconds=timings))
    print(json.dumps(dict(status='complete',seconds=time.perf_counter()-started,test={m:metrics[m]['test'] for m in methods}),indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','score']);parser.add_argument('--asset-root',type=Path,required=True);parser.add_argument('--font',type=Path)
    args=parser.parse_args()
    if args.stage=='prepare':
        if not args.font:parser.error('--font required')
        prepare(args.asset_root,args.font)
    else:score(args.asset_root)
