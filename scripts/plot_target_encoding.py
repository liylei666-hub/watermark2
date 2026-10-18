"""Render fixed-pair encoding/inversion diagnostics from verified CPU readback."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '': raise SystemExit('CPU-only plotting')
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main(source, destination):
    data=json.loads(Path(source).read_text(encoding='utf-8'))
    if data['status']!='verified':raise ValueError('Verified analysis required')
    destination=Path(destination)
    for suffix in ['.png','.svg']:
        if destination.with_suffix(suffix).exists():raise FileExistsError('Preserve existing figure')
    spaces=['proxy_z0','target_z0','proxy_zT','target_zT']
    labels=['Proxy\nencoding','Target\nencoding','Proxy\ninversion','Target\ninversion']
    colors={'imprint':'#2563a6','jain':'#d97a26'}
    fig,axes=plt.subplots(1,3,figsize=(12,4),sharey=True)
    for ax,row in zip(axes,data['rows']):
        for method,shift in [('imprint',-.18),('jain',.18)]:
            values=[100*row['spaces'][s]['values'][method]['mse_reduction_from_cover'] for s in spaces]
            ax.bar(np.arange(4)+shift,values,width=.34,color=colors[method],label={'imprint':'Imprint','jain':'Jain adaptation'}[method])
        ax.axhline(0,color='#555',linewidth=.7)
        ax.set_xticks(np.arange(4),labels,fontsize=9)
        ax.set_title('Pair '+str(row['task_id']),fontsize=12)
        ax.set_ylim(-12,66);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('MSE reduction from original cover (%)')
    handles,legend=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend,loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.5,.98))
    fig.text(.5,.015,'Each residual uses the matching reference image within its own model/space. Three development pairs.',ha='center',fontsize=9)
    fig.subplots_adjust(top=.80,bottom=.20,left=.07,right=.99,wspace=.16)
    fig.savefig(destination.with_suffix('.png'),dpi=170)
    fig.savefig(destination.with_suffix('.svg'))
    plt.close(fig)


if __name__=='__main__':main(*sys.argv[1:])
