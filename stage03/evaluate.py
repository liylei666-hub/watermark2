"""Calibration-only thresholds and paired family bootstrap, using frozen stage02 scores."""
import csv, json, time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from stage02.core import METHODS, calibrate, dump, normalize, rate, scores, sha256
from .protocol import read_jsonl, save_once

def fit_thresholds(rows, targets):
    return {str(t):{m:calibrate([r[m] for r in rows if r['split']=='calibration' and r['category']=='A'],t) for m in METHODS} for t in targets}

def summarize(rows, method, threshold, category):
    selected=[r for r in rows if r['category']==category]
    result=rate([r[method] for r in selected],threshold,category=='A')
    groups=defaultdict(list);families=defaultdict(list)
    for r in selected:
        wrong=float(r[method]<threshold if category=='A' else r[method]>=threshold)
        groups[r['prompt_id']].append(wrong);families[r['family']].append(wrong)
    result.update(prompts=len(groups),families=len(families),prompt_mean=float(np.mean([np.mean(v) for v in groups.values()])),family_mean=float(np.mean([np.mean(v) for v in families.values()])))
    result['by_transform']={t:rate([r[method] for r in selected if r['transform']==t],threshold,category=='A') for t in sorted({r['transform'] for r in selected})}
    result['by_topic']={t:rate([r[method] for r in selected if r['topic']==t],threshold,category=='A') for t in sorted({r['topic'] for r in selected})}
    return result

def bootstrap(rows, config):
    cal=[r for r in rows if r['split']=='calibration'];test=[r for r in rows if r['split']=='test']
    cf=sorted({r['family'] for r in cal});tf=sorted({r['family'] for r in test});rng=np.random.default_rng(config['bootstrap']['seed'])
    n=config['bootstrap']['replicates'];ci=rng.integers(len(cf),size=(n,len(cf)));ti=rng.integers(len(tf),size=(n,len(tf)))
    cats=['A','B_raw','B_post','D'];targets=config['targets_frr'];values={str(t):{m:{c:[] for c in cats} for m in METHODS} for t in targets}
    # Fixed equal-size families permit a dense representation. D resamples source families;
    # donors recur, so its CI conditions on the fixed donor graph rather than independent edges.
    ca={m:np.array([[r[m] for r in cal if r['family']==f and r['category']=='A'] for f in cf]) for m in METHODS}
    te={m:{c:np.array([[r[m] for r in test if r['family']==f and r['category']==c] for f in tf]) for c in cats} for m in METHODS}
    for b in range(n):
        for m in METHODS:
            a=ca[m][ci[b]].ravel()
            for target in targets:
                threshold=calibrate(a,target)
                for c in cats:
                    v=te[m][c][ti[b]].ravel();values[str(target)][m][c].append(float(np.mean(v<threshold if c=='A' else v>=threshold)))
    result={}
    for target,methods in values.items():
        result[target]={}
        for m,categories in methods.items():
            result[target][m]={c:dict(lower=float(np.quantile(v,.025,method='linear')),upper=float(np.quantile(v,.975,method='linear')),degenerate=bool(np.ptp(v)==0)) for c,v in categories.items()}
    return dict(unit='family',replicates=n,seed=config['bootstrap']['seed'],calibration_families=cf,test_families=tf,
                indices_sha256=__import__('hashlib').sha256(ci.tobytes()+ti.tobytes()).hexdigest(),same_indices_all_methods=True,intervals=result,
                limitation='Exploratory empirical family bootstrap; degenerate zero-error intervals do not establish zero FAR. D intervals condition on fixed donor assignments and do not fully model crossed donor dependence.')

def evaluate(root,config):
    out=root/'outputs/stage03';pairs=read_jsonl(root/'data/stage03/pairs.jsonl');images=read_jsonl(root/'data/stage03/manifest.jsonl')
    index={m:json.loads((out/f'features_{m}.json').read_text()) for m in ['clip','sscd','dinov2']}
    features={m:{k:np.load(root/v['path'],allow_pickle=False) for k,v in ix.items()} for m,ix in index.items()}
    # This feature-only API is also used in stage02; prompt metadata is joined after scoring.
    times={m:0. for m in METHODS};globals={k:normalize(v.mean(axis=0)) for k,v in features['dinov2'].items()};global_index={}
    for k,v in globals.items():
        path=root/'cache/stage03/dinov2_global'/(index['dinov2'][k]['key']+'.npy');path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if not np.array_equal(np.load(path,allow_pickle=False),v):raise ValueError('DINO global cache mismatch')
        else:np.save(path,v,allow_pickle=False)
        global_index[k]=dict(path=str(path.relative_to(root)),bytes=v.nbytes,file_bytes=path.stat().st_size)
    dump(out/'features_dinov2_global.json',global_index)
    def score_pair(pair):
        left,right=pair['left'],pair['right'];result={}
        for model in ['clip','sscd']:
            start=time.perf_counter();part=scores(features[model][left],features[model][right],model);result.update(part)
            times[next(iter(part))]+=time.perf_counter()-start
        start=time.perf_counter();result['DINO_global']=float(globals[left]@globals[right]);times['DINO_global']+=time.perf_counter()-start
        start=time.perf_counter();local=np.einsum('ij,ij->i',features['dinov2'][left],features['dinov2'][right]);shared=time.perf_counter()-start
        start=time.perf_counter();result['DINO_local_mean']=float(local.mean());times['DINO_local_mean']+=shared+time.perf_counter()-start
        start=time.perf_counter();result['DINO_local_q10']=float(np.quantile(local,.1,method='linear'));times['DINO_local_q10']+=shared+time.perf_counter()-start
        return dict(pair,**result)
    # Test pairs are not even scored until the calibration thresholds have been persisted.
    calrows=[score_pair(p) for p in pairs if p['split']=='calibration']
    thresholds=fit_thresholds(calrows,config['targets_frr'])
    frozen=dict(thresholds=thresholds,accept='score >= threshold; ties accepted',rule='sorted calibration A[floor(target*n)]',
                calibration_pairs=sum(r['category']=='A' for r in calrows),prompts_sha256=sha256(root/'data/stage03/prompts.jsonl'),run_sha256=sha256(out/'frozen_run.json'))
    save_once(out/'thresholds.json',frozen);threshold_hash=sha256(out/'thresholds.json')
    save_once(out/'thresholds.sha256.json',dict(sha256=threshold_hash))
    testrows=[score_pair(p) for p in pairs if p['split']=='test'];rows=calrows+testrows
    with (out/'pair_scores.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(pairs[0])+METHODS);writer.writeheader();writer.writerows(rows)
    metrics=dict(status='complete',threshold_sha256=threshold_hash,originals=480,images=len(images),counts=dict(Counter(r['split']+'/'+r['category'] for r in rows)),
                 prompts=120,families=60,methods={},scoring_seconds=times,C=dict(status='not evaluated'),scope='Content representation diagnosis with full reference features; no credential extraction or adaptive attack')
    for m in METHODS:
        sample=next(iter(global_index.values())) if m=='DINO_global' else next(iter(index['clip' if m.startswith('CLIP') else 'sscd' if m.startswith('SSCD') else 'dinov2'].values()))
        result=dict(reference_array_bytes=sample['bytes'],reference_npy_bytes=sample['file_bytes'],reference_dtype='float32',working_points={})
        for target in config['targets_frr']:
            threshold=thresholds[str(target)][m]
            result['working_points'][str(target)]=dict(threshold=threshold,calibration_A=summarize(calrows,m,threshold,'A'),test={c:summarize(testrows,m,threshold,c) for c in ['A','B_raw','B_post','D']})
        metrics['methods'][m]=result
    metrics['bootstrap']=bootstrap(rows,config)
    metrics['workers']={task:json.loads((out/f'worker_{task}.json').read_text()) for task in ['clip_sscd','dinov2']}
    metrics['generation_budget']=json.loads((out/'generation_budget.json').read_text())
    if sha256(out/'thresholds.json')!=threshold_hash:raise ValueError('Threshold mutated during evaluation')
    dump(out/'metrics.json',metrics)
    make_figures(root,rows,images,thresholds['0.05'])
    return metrics

def make_figures(root,rows,images,thresholds):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    out=root/'outputs/stage03/figures';out.mkdir(exist_ok=True);table={r['id']:r for r in images};test=[r for r in rows if r['split']=='test']
    fig,axs=plt.subplots(1,5,figsize=(20,4))
    for ax,m in zip(axs,METHODS):
        for c in ['A','B_raw','B_post','D']:ax.hist([r[m] for r in test if r['category']==c],bins=25,density=True,alpha=.4,label=c)
        ax.axvline(thresholds[m],color='black',linestyle='--');ax.set_title(m);ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'score_distributions.png',dpi=130);plt.close(fig)
    chosen=[]
    for m in METHODS:
        for c in ['B_raw','B_post']:
            r=max((r for r in test if r['category']==c),key=lambda r:r[m]);chosen.append(dict(method=m,reason='post hoc highest '+c,accepted=r[m]>=thresholds[m],threshold=thresholds[m],**r))
        errors=[r for r in test if r['category'].startswith('B') and r[m]>=thresholds[m]]
        if errors:
            r=min(errors,key=lambda r:r['pair_id']);chosen.append(dict(method=m,reason='post hoc first false acceptance',accepted=True,threshold=thresholds[m],**r))
    dump(out/'posthoc_cases.json',chosen)
    fig,axs=plt.subplots(len(chosen),2,figsize=(8,3*len(chosen)),squeeze=False)
    for axes,r in zip(axs,chosen):
        for ax,side in zip(axes,['left','right']):ax.imshow(Image.open(root/table[r[side]]['path']));ax.axis('off')
        axes[0].set_title(r['method']+' '+r['category']+' '+r['prompt_id'],fontsize=9)
        axes[1].set_title(f"post hoc: {r[r['method']]:.4f} / {r['threshold']:.4f}; accept={r['accepted']}",fontsize=9)
    fig.tight_layout();fig.savefig(out/'posthoc_cases.jpg',dpi=90);plt.close(fig)
