"""Plot matched completed seeds from saved CPU summaries; no model imports."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/f'reports/{name}/per_sample.json').read_text())
r7=read('07_prompt_control');r8=read('08_target_roundtrip');r9=read('09_vae_roundtrip')
fig,ax=plt.subplots(figsize=(9,4.6),layout='constrained')
labels=['Reference','Target VAE\nreconstruction','Proxy VAE\nreconstruction','Target full cycle\nsame prompt','Proxy full cycle\nsame prompt']
for seed,color,marker in [(101,'#1976a3','o'),(102,'#b74d28','s')]:
    get=lambda rows,arm,role=None:next(r for r in rows if r['seed']==seed and r['arm']==arm and (role is None or r['role']==role))
    values=[get(r9,'target_vae')['reference_cosine'],get(r9,'target_vae')['cosine'],get(r9,'proxy_vae')['cosine'],
            get(r8,'same_prompt')['cosine'],get(r7,'same_prompt','candidate')['cosine']]
    offset=-.07 if seed==101 else .07
    ax.scatter([i+offset for i in range(5)],values,label=f'Seed {seed}',color=color,marker=marker,s=65,zorder=3)
ax.set_xticks(range(5),labels);ax.set_ylim(0,1);ax.set_ylabel('Cosine to original target watermarked noise')
ax.set_title('Matched pipeline diagnostics on two completed references',loc='left',fontweight='bold')
ax.grid(axis='y',alpha=.2);ax.spines[['right','top']].set_visible(False);ax.legend(loc='lower left',frameon=False)
fig.supxlabel('Stage 09 stopped before seed 103. Different pipelines; gaps are not additive causal contributions.',fontsize=9)
out=ROOT/'reports/09_vae_roundtrip'
for ext in ['png','pdf']:fig.savefig(out/f'paired_pipeline_controls.{ext}',dpi=180)
