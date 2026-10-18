"""Independent CPU risk/AUC arithmetic plus explicitly exploratory score overlap."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU visibility required')
import json, math, sys
from pathlib import Path
import numpy as np

def run(root, analysis):
    rows = []
    for row in analysis['rows']:
        k=row['task_id'];z={s:np.load(root/f'proxy_{s}/{k}/inverse.npy',allow_pickle=False).astype(np.float64).ravel() for s in (25,50,100)}
        scores={n:np.load(root/f'scores/{k}/{n}.npy',allow_pickle=False) for n in ('baseline','consistency')}
        # Python ordering and searchsorted oracle differ from production lexsort/rank-sum.
        orders={n:sorted(range(16384),key=lambda j:(-float(v[j]),j)) for n,v in scores.items()}
        for label,path in [('original',root/f'reference/{k}/original_noise.npy'),('reference_reinversion',root/f'evaluation/{k}/inverse.npy')]:
            correct=(z[50]>=0)==(np.load(path,allow_pickle=False).ravel()>=0)
            for name,score in scores.items():
                for coverage in (.25,.5,.75,1.):
                    selected=orders[name][:math.ceil(coverage*16384)]
                    risk=sum(not bool(correct[j]) for j in selected)/len(selected)
                    assert risk==row[label]['risks'][name][str(coverage)]
                positive=score[correct];negative=np.sort(score[~correct])
                oracle=None if len(positive)==0 or len(negative)==0 else float(np.sum((np.searchsorted(negative,positive,side='left')+np.searchsorted(negative,positive,side='right'))*.5)/(len(positive)*len(negative)))
                assert oracle==row[label]['correctness_auc'][name]
        selected_a=set(orders['baseline'][:8192]);selected_b=set(orders['consistency'][:8192])
        rows.append(dict(task_id=k,all_three_sign_agreement=float(np.mean(((z[25]>=0)==(z[50]>=0)) & ((z[100]>=0)==(z[50]>=0)))),
                         selected_half_overlap_fraction=len(selected_a & selected_b)/8192,
                         selected_half_replaced_coordinates=len(selected_a-selected_b)))
    return dict(status='passed',risk_values_verified=64,auc_values_verified=16,
                label_rule='Sign labels only after remote official-CDF/sign equality check passed for all saved arrays',
                exploratory_after_primary_result=dict(question='How similar are fixed proxy paths and their selected sets?',rows=rows),
                gpu_used=False,models_loaded=False,new_model_experiments_run=0)

if __name__=='__main__':
    root=Path(sys.argv[1]);analysis=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    with Path(sys.argv[3]).open('x',encoding='utf-8') as f:json.dump(run(root,analysis),f,indent=2,allow_nan=False)
