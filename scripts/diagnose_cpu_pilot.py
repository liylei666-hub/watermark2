"""Post-hoc location/sensitivity analysis and source-level binomial limits."""
import csv
import json
import math
from pathlib import Path
import numpy as np
from cpu_pilot import ROOT,RUN,OUT,load,save


def upper(k,n,alpha=.05):
    if k==n:return 1.
    lo,hi=0.,1.
    for _ in range(100):
        p=(lo+hi)/2
        cdf=sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(k+1))
        if cdf>alpha:lo=p
        else:hi=p
    return (lo+hi)/2


def run():
    manifest=load(OUT/'manifest.json');features=np.load(RUN/'features.npz',allow_pickle=False)
    thresholds=load(OUT/'thresholds.json')['values'];rows=[]
    for r in manifest:
        if r['split']!='test' or r['variant']=='reference':continue
        cosine=np.sum(features[r['source_id']+'_reference']*features[r['id']],axis=1)
        x,y,_,_=r['box'];panel_view=1+(x>=256)+2*(y>=256)
        rows.append(dict(source_id=r['source_id'],variant=r['variant'],view_cosines=cosine.tolist(),
                         panel_quadrant_view=int(panel_view),minimum_view=int(np.argmin(cosine)),
                         modified_pixel_fraction=r['changed_pixels']/(512*512),
                         global_accept=bool(cosine[0]>=thresholds['global_score']),multiscale_accept=bool(cosine.min()>=thresholds['multiscale_min'])))
    failures=[r for r in rows if r['variant'] in ['jpeg70','jpeg90','resize0.5','resize0.75'] and not r['multiscale_accept']]
    sensitivity={}
    for category in ['jpeg70','jpeg90','resize0.5','resize0.75','count','text','relation','process_control']:
        chosen=[r for r in rows if r['variant']==category]
        sensitivity[category]=dict(median_global_cosine_drop=float(np.median([1-r['view_cosines'][0] for r in chosen])),
                                   median_panel_quadrant_cosine_drop=float(np.median([1-r['view_cosines'][r['panel_quadrant_view']] for r in chosen])),
                                   median_changed_pixel_fraction=float(np.median([r['modified_pixel_fraction'] for r in chosen])))
    # Treat each source as failed if ANY of its four allowed variants is rejected.
    source_ids=sorted({r['source_id'] for r in rows});bounds={}
    for method in ['global_accept','multiscale_accept']:
        k=sum(any(not r[method] for r in rows if r['source_id']==sid and r['variant'] in ['jpeg70','jpeg90','resize0.5','resize0.75']) for sid in source_ids)
        bounds[method]=dict(allowed_source_any_reject=k,sources=len(source_ids),one_sided_95_percent_upper=upper(k,len(source_ids)))
    save(OUT/'diagnosis.json',dict(scope='posthoc; modification boxes only used to explain scores, never by verifier',view_order=['full','top_left','top_right','bottom_left','bottom_right'],
                                  benign_false_rejects=failures,sensitivity=sensitivity,per_source_views=rows,source_error_bounds=bounds,
                                  zero_of_9_one_sided_95_upper=upper(0,9),
                                  binomial_assumptions='Exact Clopper-Pearson bound only under independent identically distributed source-level Bernoulli trials; exploratory reused sources and cyclic replacement donors do not establish these assumptions. No patch/variant inflation.'))
    print(json.dumps(dict(false_rejects=failures,sensitivity=sensitivity,bounds=bounds,zero_of_9_upper=upper(0,9)),indent=2))


if __name__=='__main__':run()
