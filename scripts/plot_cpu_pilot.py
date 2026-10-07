"""Render persisted score distributions and constructed-fact failure examples."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports/cpu_pilot'
rows=list(csv.DictReader((OUT/'scores.csv').open(encoding='utf-8',newline='')))
thresholds=json.loads((OUT/'thresholds.json').read_text(encoding='utf-8'))['values']
cats=['jpeg70','jpeg90','resize0.5','resize0.75','count','text','relation','process_control']
fig,axes=plt.subplots(2,1,figsize=(10,6),layout='constrained')
for ax,method in zip(axes,thresholds):
    for i,cat in enumerate(cats):
        values=[float(r[method]) for r in rows if r['split']=='test' and r['variant']==cat]
        ax.scatter(i+np.linspace(-.15,.15,len(values)),values,s=20,color='#276fbf' if i<4 else '#b35c1e',alpha=.8)
    ax.axhline(thresholds[method],color='black',ls='--',lw=1,label='calibration threshold')
    ax.set_xticks(range(len(cats)),cats,rotation=15);ax.set_ylabel('Cosine similarity');ax.set_title(method+' | 9 test source groups');ax.legend(loc='lower right');ax.grid(axis='y',alpha=.2)
fig.savefig(OUT/'scores.png',dpi=150);plt.close(fig)
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
sid=sorted({r['source_id'] for r in manifest if r['split']=='test'})[0]
variants=['reference','count','text','relation','jpeg70','process_control']
sheet=Image.new('RGB',(600,200),'white');draw=ImageDraw.Draw(sheet)
for n,v in enumerate(variants):
    r=next(r for r in manifest if r['source_id']==sid and r['variant']==v);x,y,w,h=r['box'];col=n%3;line=n//3
    sheet.paste(Image.open(ROOT/r['path']).crop((x,y,x+w,y+h)),(col*200,line*100+25))
    text=v
    if v!='reference':
        s=next(s for s in rows if s['source_id']==sid and s['variant']==v)
        text+=f" G={float(s['global_score']):.4f} L={float(s['multiscale_min']):.4f}"
    draw.text((col*200,line*100),text,fill='black')
sheet.save(OUT/'constructed_failure_examples.png')
print('Rendered scores.png and constructed_failure_examples.png; example source='+sid)
