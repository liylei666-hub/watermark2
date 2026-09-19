"""CPU-only preparation, frozen-input verification and data contracts."""
import csv, hashlib, json, os
from collections import Counter, defaultdict
from pathlib import Path
from stage02.core import dump, sha256, HOST_GPUS, validate_gpu_config

TOPICS = ['objects','animals','indoor','architecture','vehicles','nature']
TRANSFORMS = ['jpeg90','jpeg70','scale0.75','scale0.5','brightness0.95','brightness1.05']
PREFLIGHT = [
    'A photograph of a ceramic bowl containing walnuts on a rustic shelf beside a folded cloth.',
    'A realistic photograph of a small garden shed with a wheelbarrow standing outside in daylight.',
    'A natural photograph of a robin perched on a low wooden railing above a grassy garden.',
    'An empty sewing room with a sewing machine and fabric rolls on a table, realistic photograph.']

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def stable_seed(prompt_id, slot):
    return int.from_bytes(hashlib.sha256(f'stage03-20260918/{prompt_id}/{slot}'.encode()).digest()[:4], 'big')

def save_once(path, obj):
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text()) != obj: raise ValueError('Incompatible existing artifact: '+str(path))
    else: dump(path, obj)

def write_jsonl_once(path, rows):
    path = Path(path); text = ''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows)
    if path.exists():
        if path.read_text() != text: raise ValueError('Incompatible JSONL: '+str(path))
    else:
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding='utf-8')

def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def build_prompts(root):
    with (root/'data/stage03/prompt_design.tsv').open() as f: design = list(csv.DictReader(f,delimiter='\t'))
    rows=[]
    for n, d in enumerate(design):
        pid=f'p{n:03d}'; seeds=[stable_seed(pid,k) for k in range(4)]
        # Whole families alternate within each topic, giving 5 families / 10 prompts per split.
        split='calibration' if int(d['family'][-2:])%2 else 'test'
        rows.append(dict(prompt_id=pid,prompt=d['prompt'],topic=d['topic'],family=d['family'],split=split,seeds=seeds,
                         roles=['reference','instance','instance','instance'],reference_slot=0,reference_seed=seeds[0],source='project constructed'))
    validate_prompts(rows)
    return rows

def validate_prompts(rows):
    if len(rows)!=120 or len({r['prompt_id'] for r in rows})!=120: raise ValueError('Expected 120 unique prompts')
    fam={}; allseeds=set()
    for r in rows:
        if r['topic'] not in TOPICS or r['split'] not in ['calibration','test']: raise ValueError('Unknown topic/split')
        if r['family'] in fam and fam[r['family']]!=r['split']: raise ValueError('Family split leakage')
        fam[r['family']]=r['split']
        expected=[stable_seed(r['prompt_id'],k) for k in range(4)]
        if r['seeds']!=expected or len(set(expected))!=4 or allseeds.intersection(expected): raise ValueError('Seed contract failed')
        allseeds.update(expected)
        if r['reference_slot']!=0 or r['reference_seed']!=expected[0] or r['roles']!=['reference','instance','instance','instance']: raise ValueError('Reference changed')
    if len(fam)!=60 or set(Counter(r['family'] for r in rows).values())!={2}: raise ValueError('Expected 60 two-prompt families')
    if Counter((r['topic'],r['split']) for r in rows)!=Counter({(t,s):10 for t in TOPICS for s in ['calibration','test']}): raise ValueError('Unbalanced splits')
    if len({r['prompt'].strip().lower() for r in rows})!=120: raise ValueError('Duplicate prompt text')
    return True

def generation_jobs(prompts, preflight=False):
    if preflight:
        prompts=[dict(prompt_id=f'pre{k}',prompt=p,topic='preflight',family=f'pre{k}',split='preflight',
                      seeds=[stable_seed(f'pre{k}',j) for j in range(4)]) for k,p in enumerate(PREFLIGHT)]
    return [dict(id=f"{p['prompt_id']}_s{k}",prompt_id=p['prompt_id'],prompt=p['prompt'],topic=p['topic'],family=p['family'],split=p['split'],
                 seed=s,slot=k,role='reference' if k==0 else 'instance') for p in prompts for k,s in enumerate(p['seeds'])]

def prepare(root, config):
    if config['transforms']!=TRANSFORMS or config['targets_frr']!=[.05,.01,.10]: raise ValueError('Unapproved protocol change')
    for task,idx in [('clip_sscd',5),('dinov2',7)]: validate_gpu_config(config,HOST_GPUS[idx],task)
    rows=build_prompts(root)
    write_jsonl_once(root/'data/stage03/prompts.jsonl',rows)
    save_once(root/'outputs/stage03/protocol_lock.json',dict(config=config,prompts_sha256=sha256(root/'data/stage03/prompts.jsonl'),
                  design_sha256=sha256(root/'data/stage03/prompt_design.tsv'),baselines=json.loads((root/'artifacts/models.json').read_text())))
    return rows

def donor_ids(prompts, p):
    ids=sorted(x['prompt_id'] for x in prompts if x['split']==p['split']); table={x['prompt_id']:x for x in prompts}
    pos=ids.index(p['prompt_id']); result=[]
    for offset in [1,7,19]:
        for step in range(len(ids)):
            candidate=ids[(pos+offset+step)%len(ids)]
            if candidate not in result and table[candidate]['family']!=p['family']:
                result.append(candidate); break
        else: raise ValueError('Insufficient D donors')
    return result

def validate_image_record(record, job, frozen_hash):
    for k,v in job.items():
        if record.get(k)!=v: raise ValueError('Generation provenance mismatch: '+k)
    if record.get('generation_config_sha256')!=frozen_hash or record.get('size')!=[1024,1024] or record.get('mode')!='RGB': raise ValueError('Image protocol mismatch')
    for k in ['sha256','pixel_sha256','path','runtime_sha256','seconds']:
        if k not in record: raise ValueError('Missing generation metadata: '+k)

def validate_manifest(images, pairs, prompts):
    if len(prompts)==120: validate_prompts(prompts)
    else:
        if not prompts or len({p['prompt_id'] for p in prompts})!=len(prompts) or len({p['family'] for p in prompts})*2!=len(prompts): raise ValueError('Invalid effective prompt subset')
        if any(p['split'] not in ['calibration','test'] for p in prompts): raise ValueError('Invalid effective split')
        families=defaultdict(list)
        for p in prompts: families[p['family']].append(p)
        if any(len(v)!=2 or len({p['split'] for p in v})!=1 for v in families.values()): raise ValueError('Effective subset contains incomplete or split-leaking family')
        for p in prompts:
            expected=[stable_seed(p['prompt_id'],k) for k in range(4)]
            if p.get('seeds')!=expected or p.get('reference_slot')!=0 or p.get('reference_seed')!=expected[0] or p.get('roles')!=['reference','instance','instance','instance']:
                raise ValueError('Effective subset provenance contract failed')
    table={r['id']:r for r in images}; pp={p['prompt_id']:p for p in prompts}
    if len(table)!=len(images): raise ValueError('Duplicate image IDs')
    pixel_splits={}
    for im in images:
        p=pp[im['prompt_id']]
        if (im['split'],im['family'],im['seed'])!=(p['split'],p['family'],p['seeds'][im['slot']]): raise ValueError('Derived provenance mismatch')
        old=pixel_splits.setdefault(im['pixel_sha256'],im['split'])
        if old!=im['split']: raise ValueError('Identical pixels across splits')
    if len({p['pair_id'] for p in pairs})!=len(pairs): raise ValueError('Duplicate pairs')
    for p in pairs:
        a,b=table[p['left']],table[p['right']]
        if a['split']!=b['split'] or a['split']!=p['split']: raise ValueError('Pair leakage')
        if a['slot']!=0 or a['transform']!='identity': raise ValueError('Reference mismatch')
        if p['category'] in ['A','B_raw','B_post','SELF'] and a['prompt_id']!=b['prompt_id']: raise ValueError('Within-prompt mismatch')
        if p['category']=='A' and (a['seed']!=b['seed'] or b['transform']=='identity'): raise ValueError('Invalid A')
        if p['category'].startswith('B') and (a['seed']==b['seed'] or a['pixel_sha256']==b['pixel_sha256']): raise ValueError('Invalid independent B')
        if p['category']=='D' and a['family']==b['family']: raise ValueError('D same family')
    return True
