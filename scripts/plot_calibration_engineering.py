"""Derived count tables and static engineering stability figure."""
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def main():
    root=Path(__file__).resolve().parents[1]/'reports/calibration_engineering'
    m=json.loads((root/'audit.json').read_text())['metrics'];cfg=json.loads((root/'inputs/sd15_clip_calibration.json').read_text())
    with (root/'source_counts.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.writer(f);w.writerow(['source','split','family',*cfg['benign_variants'],'minimum','unchecked10_bundle_accepted','cal_rule_bundle_accepted'])
        for s in cfg['sources']:
            p=m['source_profiles'][s['split']][s['id']]
            w.writerow([s['id'],s['split'],s['family'],*[p['counts'][v] for v in cfg['benign_variants']],p['minimum'],p['bundle_accepted_at_unchecked10'],p['bundle_accepted']])
    n=m['negative_controls']
    with (root/'negative_counts.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.writer(f);w.writerow(['kind','source','donor','count','unchecked10_accepted','cal_rule_accepted'])
        for sid,count in n['unmarked_draft']['counts'].items():w.writerow(['unmarked_draft',sid,'',count,count>=10,count>=m['count_threshold']])
        for r in n['wrong_reference_diagnostic']['rows']:w.writerow(['wrong_reference_diagnostic',r['source'],r['reference_donor'],r['count'],r['accepted_at_unchecked10'],r['accepted']])
    fig,axes=plt.subplots(1,2,figsize=(11,5.7),sharey=True)
    for ax,split in zip(axes,['calibration','test']):
        for s in [s for s in cfg['sources'] if s['split']==split]:
            p=m['source_profiles'][split][s['id']]
            ax.plot(range(5),[p['counts'][v] for v in cfg['benign_variants']],marker='o',linewidth=1.4,label=s['id']+' '+s['family'])
        ax.axhline(10,color='grey',linestyle='--',linewidth=1,label='unchecked count10')
        ax.set_xticks(range(5),['Original','JPEG70','JPEG90','Resize0.5','Resize0.75']);ax.set_title(split.capitalize()+' sources (n=6)')
        ax.set_ylim(-8,380);ax.grid(axis='y',alpha=.2);ax.legend(fontsize=7,loc='upper center',bbox_to_anchor=(0.5,-0.13),ncol=2)
    axes[0].set_ylabel('Native matched patches (higher is accepted)')
    fig.suptitle('SD1.5 / CLIP: count stability under allowed image processing',fontsize=12)
    fig.text(.5,.015,'Cal-only 90% source-bundle rule selected count0: degenerate; no usable operating point.',ha='center',fontsize=9)
    fig.subplots_adjust(top=.86,bottom=.31,wspace=.1);fig.savefig(root/'stability_counts.png',dpi=180);fig.savefig(root/'stability_counts.svg');plt.close(fig)
if __name__=='__main__':main()
