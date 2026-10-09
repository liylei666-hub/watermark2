"""Descriptive ECDFs of saved patch distances for the single cal shoe sample."""
import argparse,csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args();root=Path(args.run)
    audit=json.loads((root/'audit.json').read_text());assert audit['status']=='passed'
    with (root/'codec_distances.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    labels={'original':'Original','jpeg70_420':'JPEG70 4:2:0 (existing)','jpeg70_444':'JPEG70 4:4:4','jpeg95_420':'JPEG95 4:2:0'}
    colors=['#264653','#c55a3a','#d4972a','#3e8494'];styles=['-','--',':','-.']
    fig,axes=plt.subplots(1,2,figsize=(10,4.6))
    for ax,typ in zip(axes,['native','oracle']):
        for (variant,label),color,style in zip(labels.items(),colors,styles):
            r=[r for r in rows if r['reference']==typ and r['variant']==variant]
            assert len(r)==1024
            ax.step([float(v['l2']) for v in r],[float(v['ecdf']) for v in r],where='post',label=label,color=color,ls=style,lw=1.8)
        ax.axvline(2,color='#6a6872',lw=1,ls='--')
        ax.set(xlim=(0,10),ylim=(0,1),xlabel='Unnormalized patch L2 (16 scaled latent coordinates)',ylabel='Fraction of 1024 patches')
        ax.grid(alpha=.18)
        ax.set_title('Native query-derived reference' if typ=='native' else 'Oracle registered-noise reference')
    handles,legend_labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,legend_labels,loc='lower center',ncol=2,frameon=False,bbox_to_anchor=(.5,.01),fontsize=9)
    fig.suptitle('c04 shoe: fixed patch tolerance = 2; one calibration image',fontsize=12)
    fig.subplots_adjust(bottom=.25,top=.82,wspace=.25)
    fig.savefig(root/'codec_distance_ecdf.png',dpi=180);fig.savefig(root/'codec_distance_ecdf.svg')
    plt.close(fig)
    print('Saved descriptive ECDF PNG/SVG; no independent-patch inference')

if __name__=='__main__':main()
