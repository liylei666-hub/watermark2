import csv, json, time
from collections import Counter
from pathlib import Path
import numpy as np
from .core import METHODS, calibrate, dump, rate, scores, sha256

def evaluate(root,manifest):
    out=root/'outputs/stage02';indexes={};features={};times={}
    for model in ['clip','sscd','dinov2']:
        path=out/f'features_{model}.json'
        if path.exists():
            indexes[model]=json.loads(path.read_text());features[model]={i:np.load(root/x['path'],allow_pickle=False) for i,x in indexes[model].items()};times[model]=0.
    global_dino={};global_index={}
    if 'dinov2' in features:
        from .core import normalize
        for i,patches in features['dinov2'].items():
            global_dino[i]=normalize(patches.mean(axis=0));dst=root/'cache/stage02/dinov2_global'/(indexes['dinov2'][i]['key']+'.npy');dst.parent.mkdir(parents=True,exist_ok=True)
            tmp=dst.with_suffix('.tmp')
            with tmp.open('wb') as f:np.save(f,global_dino[i],allow_pickle=False)
            tmp.replace(dst)
            global_index[i]=dict(path=str(dst.relative_to(root)),bytes=int(global_dino[i].nbytes),file_bytes=dst.stat().st_size)
        dump(out/'features_dinov2_global.json',global_index)
    rows=[];method_times={m:0. for m in METHODS};shared_local_time=0.
    for p in manifest['pairs']:
        row={k:p[k] for k in ['pair_id','group','left','right','category','split','source','donor','mask']};row['params']=json.dumps(p['params'])
        for model,feat in features.items():
            t=time.perf_counter()
            if model=='dinov2':
                t_shared=time.perf_counter()
                local=np.einsum('ij,ij->i',feat[p['left']],feat[p['right']])
                shared_local_time+=time.perf_counter()-t_shared
                t_method=time.perf_counter();row['DINO_global']=float(global_dino[p['left']]@global_dino[p['right']]);method_times['DINO_global']+=time.perf_counter()-t_method
                t_method=time.perf_counter();row['DINO_local_mean']=float(local.mean());method_times['DINO_local_mean']+=time.perf_counter()-t_method
                t_method=time.perf_counter();row['DINO_local_q10']=float(np.quantile(local,.1,method='linear'));method_times['DINO_local_q10']+=time.perf_counter()-t_method
            else:
                method='CLIP_global' if model=='clip' else 'SSCD_global'
                t_method=time.perf_counter();row.update(scores(feat[p['left']],feat[p['right']],model));method_times[method]+=time.perf_counter()-t_method
            times[model]+=time.perf_counter()-t
        rows.append(row)
    fields=['pair_id','group','left','right','category','split','source','donor','mask','params']+METHODS
    with (out/'pair_scores.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    available=[m for m in METHODS if rows and m in rows[0]]
    thresholds={m:calibrate([r[m] for r in rows if r['split']=='smoke_calibration' and r['category']=='A']) for m in available}
    tp=out/'thresholds.json';dump(tp,dict(thresholds=thresholds,target_frr=.05,accept='score >= threshold; ties accepted',rule='sorted_A[floor(0.05*n)]',source='smoke_calibration A only'))
    frozen_hash=sha256(tp)
    metrics=dict(status='complete' if len(available)==5 else 'incomplete',B=dict(status='missing',reason='No verified same-prompt different-seed generation instances'),threshold_file_sha256=frozen_hash,methods={},scoring_seconds=times,method_scoring_seconds=method_times,shared_DINO_local_cosine_seconds=shared_local_time,
                 counts=dict(Counter(p['split']+'/'+p['category'] for p in manifest['pairs'])),originals=len(manifest['sources']),images=len(manifest['images']),groups=len({i['group'] for i in manifest['images']}),near_duplicate_edges=manifest['near_duplicate_edges'])
    for m in METHODS:
        if m not in thresholds:metrics['methods'][m]=dict(status='incomplete');continue
        t=thresholds[m];by=lambda s,c:[r[m] for r in rows if r['split']==s and r['category']==c]
        base='clip' if m.startswith('CLIP') else 'sscd' if m.startswith('SSCD') else 'dinov2'
        sample=next(iter(indexes[base].values()))
        used=next(iter(global_index.values())) if m=='DINO_global' else sample
        metrics['methods'][m]=dict(status='complete',threshold=t,calibration_frr=rate(by('smoke_calibration','A'),t,True),test_frr=rate(by('smoke_test','A'),t,True),test_D_false_accept=rate(by('smoke_test','D'),t),test_C_proxy_false_accept=rate(by('smoke_test','C_proxy'),t),reference_dtype='float32',reference_array_bytes=used['bytes'],reference_npy_bytes=used['file_bytes'],shared_dino_patch_cache_bytes=sample['bytes'] if base=='dinov2' else None,reference_info='reference image features only; no external reference database')
    assert sha256(tp)==frozen_hash
    dump(out/'metrics.json',metrics);figures(root,manifest,rows,thresholds,features)
    return metrics

def figures(root,manifest,rows,thresholds,features):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    out=root/'outputs/stage02/figures';out.mkdir(parents=True,exist_ok=True)
    images={x['id']:x for x in manifest['images']}
    originals=[x for x in manifest['images'] if x['id']==x['original']]
    fig,axes=plt.subplots(4,5,figsize=(15,10))
    for ax,x in zip(axes.flat,originals):
        ax.imshow(Image.open(root/x['path']));ax.set_title(x['id']+'\n'+x['split'],fontsize=8);ax.axis('off')
    for ax in list(axes.flat)[len(originals):]:ax.axis('off')
    fig.tight_layout();fig.savefig(out/'source_contact_sheet.png',dpi=120);plt.close(fig)
    fig,axes=plt.subplots(1,5,figsize=(20,4))
    for ax,m in zip(axes,METHODS):
        if m not in thresholds:ax.set_title(m+' incomplete');continue
        for cat in ['A','D','C_proxy']:
            vals=[r[m] for r in rows if r['split']=='smoke_test' and r['category']==cat]
            ax.hist(vals,bins=15,alpha=.5,label=cat)
        ax.axvline(thresholds[m],color='black',linestyle='--');ax.set_title(m);ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'score_distributions.png',dpi=150);plt.close(fig)
    # Deterministic examples: first test A rejection and C acceptance per method.
    chosen=[]
    for m,t in thresholds.items():
        for cat in ['A','C_proxy']:
            failures=[r for r in rows if r['split']=='smoke_test' and r['category']==cat and ((r[m]<t) if cat=='A' else (r[m]>=t))]
            if failures:chosen.append((m,failures[0]))
    dump(out/'representative_errors.json',[dict(method=m,**r) for m,r in chosen])
    if chosen:
        fig,axes=plt.subplots(len(chosen),3,figsize=(10,3*len(chosen)),squeeze=False)
        for axs,(m,r) in zip(axes,chosen):
            for ax,side in zip(axs[:2],['left','right']):ax.imshow(Image.open(root/images[r[side]]['path']));ax.axis('off')
            axs[0].set_title(m+' '+r['category'],fontsize=9);axs[1].set_title(f"score {r[m]:.5f} / threshold {thresholds[m]:.5f}",fontsize=9)
            axs[2].axis('off')
            if r['mask']:axs[2].imshow(Image.open(root/r['mask']),cmap='gray');axs[2].set_title('analysis mask')
        fig.tight_layout();fig.savefig(out/'representative_errors.png',dpi=100);plt.close(fig)
    if 'dinov2' in features:
        p=next(r for r in rows if r['split']=='smoke_test' and r['category']=='C_proxy')
        a,b=(features['dinov2'][p[k]] for k in ['left','right']);heat=np.sum(a*b,axis=-1).reshape(16,16)
        fig,axs=plt.subplots(1,4,figsize=(14,4))
        axs[0].imshow(Image.open(root/images[p['left']]['path']));axs[1].imshow(Image.open(root/images[p['right']]['path']))
        axs[2].imshow(Image.open(root/p['mask']),cmap='gray');im=axs[3].imshow(heat,vmin=0,vmax=1,cmap='viridis');fig.colorbar(im,ax=axs[3])
        for ax,title in zip(axs,['Reference','C_proxy','Analysis mask','DINO cosine (same location)']):ax.set_title(title);ax.axis('off')
        fig.tight_layout();fig.savefig(out/'local_similarity.png',dpi=150);plt.close(fig)
    coverage=[]
    for r in rows:
        if r['category']!='C_proxy':continue
        w,h=images[r['left']]['size'];x0,y0,x1,y1=json.loads(r['params'])['box'];s=min(w,h);cx=(w-s)/2;cy=(h-s)/2
        overlap=max(0,min(x1,cx+s)-max(x0,cx))*max(0,min(y1,cy+s)-max(y0,cy))
        coverage.append(dict(pair_id=r['pair_id'],clip_visible_mask_fraction=overlap/((x1-x0)*(y1-y0)),note='continuous center-square approximation; CLIP resize rounding can differ by ~1 pixel'))
    dump(root/'outputs/stage02/crop_visibility.json',coverage)
