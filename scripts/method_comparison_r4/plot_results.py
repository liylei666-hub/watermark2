"""Descriptive development figure from verified final-PNG outcomes, CPU only."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import json,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def main(report):
    report=Path(report);data=json.loads((report/'verification_private.json').read_text());rows=data['rows']
    if not data['verified']:raise ValueError('Verified results required')
    methods=['imprint','jain','delivery'];labels=['Native Imprint','Adapted Jain','Delivery-path Imprint'];colors=['#2878B5','#E69F00','#009E73']
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for i,(method,label,color) in enumerate(zip(methods,labels,colors)):
        group=[r for r in rows if r['method']==method and r['status']=='completed'];x=np.array([r['task_id'] for r in group])+(i-1)*.16
        for ax,key in zip(axes.flat[:3],['bit_accuracy','cover_mse_rgb01','core_seconds']):ax.scatter(x,[r[key] for r in group],s=34,color=color,label=label,zorder=3)
    for ax in axes.flat[:3]:
        for group in (0,2):ax.axvspan(group*3+.5,group*3+3.5,color='#EEF2F6',zorder=0)
        ax.set_xticks(range(1,13));ax.set_xlim(.5,12.5);ax.set_xlabel('Frozen task (four prompt groups, three replicas each)');ax.grid(axis='y',alpha=.2)
    axes[0,0].axhline(.70703125,color='#555555',linestyle='--',linewidth=1,label='Strict GS threshold');axes[0,0].set_ylim(0,1.025);axes[0,0].set_ylabel('Final PNG message bit accuracy');axes[0,0].set_title('(a) Ordinary GS score');axes[0,0].legend(fontsize=8,loc='lower left')
    axes[0,1].set_yscale('log');axes[0,1].set_ylabel('Pixel MSE against cover, RGB [0, 1]');axes[0,1].set_title('(b) Delivered-image distortion')
    axes[1,0].set_ylabel('Measured core computation (seconds)');axes[1,0].set_title('(c) Actual computation, excluding model load')
    success=np.array([data['summary'][m]['gs_pass_count'] for m in methods]);missing=np.array([data['summary'][m]['failed'] for m in methods]);rejected=12-success-missing;x=np.arange(3)
    axes[1,1].bar(x,success,color='#009E73',label='Delivered + GS pass');axes[1,1].bar(x,rejected,bottom=success,color='#7CA7C5',label='Delivered + GS reject');axes[1,1].bar(x,missing,bottom=success+rejected,color='#DDDDDD',edgecolor='#555555',hatch='///',label='Engineering failure; score missing')
    axes[1,1].set_xticks(x,labels,fontsize=8);axes[1,1].set_ylim(0,14);axes[1,1].set_yticks(range(0,13,3));axes[1,1].set_ylabel('All 12 planned attempts per method');axes[1,1].set_title('(d) Attempt accounting');axes[1,1].legend(fontsize=8,loc='upper right')
    for i in range(3):axes[1,1].text(i,success[i]/2 if success[i] else .2,f'{success[i]}/12',ha='center',va='center',fontsize=10)
    fig.suptitle('Stage 27: fixed development comparison — 35 candidates, 1 recorded failure',fontsize=14)
    for suffix in ('png','pdf'):
        path=report/('results_figure.'+suffix)
        if path.exists():raise FileExistsError(path)
        fig.savefig(path,dpi=180,metadata={'Creator':'Stage27 verified-result plotting script'})
    plt.close(fig)

if __name__=='__main__':main(sys.argv[1])
