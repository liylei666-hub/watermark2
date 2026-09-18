"""Fixed prompt-ID contact sheets, independent of feature extraction and scores."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import argparse, json, sys
from pathlib import Path
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stage02.core import dump, sha256
from stage03.protocol import read_jsonl, TOPICS

def main(topics):
    if any(t not in TOPICS for t in topics):raise ValueError('Unknown topic')
    prompts=read_jsonl(ROOT/'data/stage03/prompts.jsonl');out=ROOT/'outputs/stage03/figures';out.mkdir(exist_ok=True)
    selected=[min((p for p in prompts if p['topic']==t and p['split']==s),key=lambda p:p['prompt_id']) for s in ['calibration','test'] for t in topics]
    sheet=Image.new('RGB',(1024,282*len(selected)),'white');draw=ImageDraw.Draw(sheet);sources=[]
    for row,p in enumerate(selected):
        for slot in range(4):
            record=json.loads((ROOT/'outputs/stage03/generation_records'/f"{p['prompt_id']}_s{slot}.json").read_text())
            path=ROOT/record['path']
            if sha256(path)!=record['sha256']:raise ValueError('Image hash mismatch')
            with Image.open(path) as im:sheet.paste(im.resize((256,256),Image.Resampling.LANCZOS),(256*slot,282*row))
            draw.text((256*slot+3,282*row+257),f"{p['prompt_id']} {p['topic']} {p['split']} slot{slot}",fill='black')
            sources.append(dict(id=record['id'],sha256=record['sha256']))
    name='prescore_'+'_'.join(topics);sheet.save(out/(name+'.jpg'),quality=90)
    dump(out/(name+'.json'),dict(rule='lowest prompt_id per topic and split; slots 0..3; no score input',prompt_ids=[p['prompt_id'] for p in selected],sources=sources,figure_sha256=sha256(out/(name+'.jpg')),thresholds_existed=(ROOT/'outputs/stage03/thresholds.json').exists()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--topics',nargs='+',default=TOPICS);a=p.parse_args();main(a.topics)
