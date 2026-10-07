"""Post-hoc matched-transform control: no new thresholds, no model training."""
import argparse
import csv
import io
import json
import os
import time
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES']=''
from cpu_pilot import ROOT, RUN, OUT, config, digest, load, save


def run(asset_root):
    import numpy as np
    import torch
    from PIL import Image
    follow=load(ROOT/'configs/cpu_followup.json');cfg=config();target=OUT/'followup'
    target.mkdir(exist_ok=True)
    assert not (target/'scores.csv').exists(), 'do not overwrite completed followup'
    threshold_path=OUT/'thresholds.json';threshold_hash=digest(threshold_path);thresholds=load(threshold_path)['values']
    manifest=load(OUT/'manifest.json');feature_path=RUN/'features.npz'
    assert digest(feature_path)==load(OUT/'runtime.json')['features_sha256']
    references=np.load(feature_path,allow_pickle=False)
    records=[]
    for r in manifest:
        if r['variant'] not in follow['modifications']:continue
        assert digest(ROOT/r['path'])==r['sha256']
        im=Image.open(ROOT/r['path']).convert('RGB')
        for post in follow['postprocess']:
            if post=='jpeg70':
                buffer=io.BytesIO();im.save(buffer,format='JPEG',quality=70,subsampling=2);buffer.seek(0);derived=Image.open(buffer).convert('RGB')
            else:derived=im.resize((256,256),Image.Resampling.BICUBIC).resize((512,512),Image.Resampling.BICUBIC)
            path=RUN/'followup'/f"{r['id']}_{post}.png";path.parent.mkdir(exist_ok=True);derived.save(path)
            records.append(dict(source_id=r['source_id'],split=r['split'],modification=r['variant'],postprocess=post,
                                path=str(path.relative_to(ROOT)).replace('\\','/'),sha256=digest(path),facts=r['facts']))
    save(target/'manifest.json',records)
    save(target/'frozen.json',dict(config=follow,config_sha256=digest(ROOT/'configs/cpu_followup.json'),script_sha256=digest(Path(__file__)),
                                  manifest_sha256=digest(target/'manifest.json'),threshold_sha256=threshold_hash,selection='all available changed placards; no score-based exclusion'))
    model_path=asset_root/'weights'/cfg['model'];assert digest(model_path)==cfg['model_sha256']
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    start=time.perf_counter()
    with model_path.open('rb') as f:model=torch.jit.load(f,map_location='cpu').eval()
    mean=np.array(cfg['mean'],dtype=np.float32);std=np.array(cfg['std'],dtype=np.float32);rows=[]
    for i,r in enumerate(records):
        assert time.perf_counter()-start < follow['wall_limit_seconds']
        im=Image.open(ROOT/r['path']).convert('RGB');arrays=[]
        for box in cfg['views']:
            a=np.asarray(im.crop(box).resize(tuple(cfg['model_resize']),Image.Resampling.BILINEAR),dtype=np.float32)/255.
            arrays.append(np.transpose((a-mean)/std,(2,0,1)))
        with torch.inference_mode():features=model(torch.from_numpy(np.stack(arrays))).numpy()
        features=features/np.linalg.norm(features,axis=1,keepdims=True);assert np.isfinite(features).all()
        cosine=np.sum(features*references[r['source_id']+'_reference'],axis=1)
        rows.append(dict(source_id=r['source_id'],split=r['split'],modification=r['modification'],postprocess=r['postprocess'],global_score=float(cosine[0]),multiscale_min=float(cosine.min())))
        if i%20==0:print(f'followup {i+1}/{len(records)} elapsed={time.perf_counter()-start:.1f}s',flush=True)
    with (target/'scores.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    primary=list(csv.DictReader((OUT/'scores.csv').open(encoding='utf-8',newline='')))
    metrics={}
    for method,threshold in thresholds.items():
        metrics[method]={}
        for edit in follow['modifications']:
            for post in follow['postprocess']:
                selected=[r for r in rows if r['split']=='test' and r['modification']==edit and r['postprocess']==post]
                benign={r['source_id']:float(r[method])>=threshold for r in primary if r['split']=='test' and r['variant']==post}
                accepted=sum(r[method]>=threshold for r in selected)
                metrics[method][edit+'+'+post]=dict(accepted=accepted,total=len(selected),source_macro=accepted/len(selected),
                    matching_benign_accepted=sum(benign.values()),same_decision_as_matching_benign=sum((r[method]>=threshold)==benign[r['source_id']] for r in selected),
                    score_min=min(r[method] for r in selected),score_median=float(np.median([r[method] for r in selected])))
    assert digest(threshold_path)==threshold_hash
    save(target/'metrics.json',dict(status='complete',scope='posthoc processing-matched constructed-fact controls',metrics=metrics,source_groups=18,test_source_groups=9,
                                  image_count=len(records),cpu_seconds=time.perf_counter()-start,device='cpu',thresholds_unchanged=True,threshold_sha256=threshold_hash,
                                  score_sha256=digest(target/'scores.csv'),full_watermark_verifier=False))
    print(json.dumps(metrics,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--asset-root',type=Path,required=True);args=parser.parse_args();run(args.asset_root)
