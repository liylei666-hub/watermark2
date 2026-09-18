"""Build A/B/D from one frozen generator; no features enter this module."""
import json
from PIL import Image, ImageDraw
from stage02.core import dump, sha256
from stage02.data import allowed_variants
from .generate import digest_pixels
from .protocol import read_jsonl, write_jsonl_once, donor_ids, validate_manifest, generation_jobs, validate_image_record, TOPICS

def prepare_data(root, config):
    out=root/'outputs/stage03'; prompts=read_jsonl(root/'data/stage03/prompts.jsonl')
    frozen=json.loads((out/'frozen_run.json').read_text());images=[];pairs=[]
    for job in generation_jobs(prompts):
        rec=json.loads((out/'generation_records'/(job['id']+'.json')).read_text());validate_image_record(rec,job,frozen['generation_config_sha256'])
        if sha256(root/rec['path'])!=rec['sha256']:raise ValueError('Original SHA mismatch')
        images.append(rec)
        with Image.open(root/rec['path']) as im:
            for suffix,new,params in allowed_variants(im):
                iid=job['id']+'_'+suffix;path=root/'data/stage03/images'/(iid+'.png')
                expected=digest_pixels(new)
                if path.exists():
                    with Image.open(path) as saved:
                        if saved.mode!='RGB' or saved.format!='PNG' or digest_pixels(saved)!=expected:raise RuntimeError('Existing variant incompatible')
                else:
                    tmp=path.with_suffix('.tmp');new.save(tmp,format='PNG',compress_level=6);tmp.replace(path)
                images.append(dict(rec,id=iid,path=str(path.relative_to(root)),sha256=sha256(path),pixel_sha256=expected,transform=suffix,parent=job['id'],params=params))
    def add(p,right,category,transform='identity'):
        left=p['prompt_id']+'_s0'
        pairs.append(dict(pair_id=f'{category}/{left}/{right}',left=left,right=right,category=category,transform=transform,
                          prompt_id=p['prompt_id'],family=p['family'],topic=p['topic'],split=p['split']))
    for p in prompts:
        pid=p['prompt_id'];add(p,pid+'_s0','SELF')
        for t in config['transforms']:add(p,pid+'_s0_'+t,'A',t)
        for k in range(1,4):
            add(p,f'{pid}_s{k}','B_raw')
            for t in config['transforms']:add(p,f'{pid}_s{k}_{t}','B_post',t)
        for donor in donor_ids(prompts,p):add(p,donor+'_s0','D')
    validate_manifest(images,pairs,prompts)
    write_jsonl_once(root/'data/stage03/manifest.jsonl',images)
    write_jsonl_once(root/'data/stage03/pairs.jsonl',pairs)
    # Opaque IDs and content hashes only; no generation or evaluation metadata reaches extraction.
    dump(root/'data/stage03/image_inputs.json',[{k:r[k] for k in ['id','path','sha256']} for r in images])
    create_grids(root,prompts,images)
    return images,pairs

def create_grids(root,prompts,images):
    out=root/'outputs/stage03/figures';out.mkdir(parents=True,exist_ok=True);table={r['id']:r for r in images}
    selected=[]
    for split in ['calibration','test']:
        canvas=Image.new('RGB',(4*256,6*282),'white');draw=ImageDraw.Draw(canvas)
        for row,topic in enumerate(TOPICS):
            p=min((p for p in prompts if p['topic']==topic and p['split']==split),key=lambda p:p['prompt_id']);selected.append(p['prompt_id'])
            for slot in range(4):
                im=Image.open(root/table[f"{p['prompt_id']}_s{slot}"]['path']);im.thumbnail((256,256))
                canvas.paste(im,(slot*256,row*282));draw.text((slot*256+3,row*282+257),f"{p['prompt_id']} {topic} slot {slot}",fill='black')
        canvas.save(out/f'prescore_{split}.jpg',quality=90)
    dump(out/'prescore_selection.json',dict(rule='lowest prompt_id per topic and split, fixed before feature scoring',prompt_ids=selected,
          visual_review_status='pending',use_for_selection=False))
