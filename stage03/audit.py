"""Independent post-run artifact checks on server CPU."""
import csv, json
from collections import Counter
import numpy as np
from PIL import Image
from stage02.core import METHODS, HOST_GPUS, calibrate, dump, scores, sha256
from .protocol import read_jsonl, validate_manifest, generation_jobs, validate_image_record
from .generate import digest_pixels

def audit(root,config):
    out=root/'outputs/stage03';prompts=read_jsonl(root/'data/stage03/prompts.jsonl');images=read_jsonl(root/'data/stage03/manifest.jsonl');pairs=read_jsonl(root/'data/stage03/pairs.jsonl')
    validate_manifest(images,pairs,prompts);table={im['id']:im for im in images};checks=[]
    expected_n=len(read_jsonl(root/'data/stage03/effective_prompts.jsonl')); assert len(images)==expected_n*28
    effective=read_jsonl(root/'data/stage03/effective_prompts.jsonl')
    expected_per_prompt={'A':6,'B_raw':3,'B_post':18,'D':3,'SELF':1}
    expected={f'{split}/{cat}':sum(1 for p in effective if p['split']==split)*n for split in ['calibration','test'] for cat,n in expected_per_prompt.items()}
    assert dict(Counter(p['split']+'/'+p['category'] for p in pairs))==expected
    assert len(pairs)==sum(expected.values())
    checks.append(f'{expected_n} effective prompts / {len({p["family"] for p in read_jsonl(root/"data/stage03/effective_prompts.jsonl")})} families; planned 120 prompts; incomplete fixed-seed groups retained separately')
    frozen=json.loads((out/'frozen_run.json').read_text())
    for job in generation_jobs(effective):validate_image_record(table[job['id']],job,frozen['generation_config_sha256'])
    for im in images:
        assert im['generation_config_sha256']==frozen['generation_config_sha256']
        assert im['runtime_sha256']==frozen['runtime_sha256']
        path=root/im['path'];assert sha256(path)==im['sha256']
        with Image.open(path) as decoded:
            assert decoded.mode=='RGB' and decoded.format=='PNG' and decoded.size==(1024,1024)
            assert digest_pixels(decoded)==im['pixel_sha256']
    checks.append('All image hashes, pixels, dimensions, RGB PNG and generation provenance verified')
    inputs=json.loads((root/'data/stage03/image_inputs.json').read_text())
    assert len(inputs)==len(images) and all(set(i)=={'id','path','sha256'} for i in inputs)
    checks.append('Feature input schema excludes prompts, seed fields, split, labels and masks')
    with (out/'pair_scores.csv').open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==len(pairs)
    for r in rows:
        for m in METHODS:r[m]=float(r[m]);assert np.isfinite(r[m])
        if r['category']=='SELF':assert all(abs(r[m]-1)<1e-5 for m in METHODS)
    thresholds=json.loads((out/'thresholds.json').read_text())['thresholds'];metrics=json.loads((out/'metrics.json').read_text())
    assert metrics['threshold_sha256']==sha256(out/'thresholds.json')
    for target in config['targets_frr']:
        for m in METHODS:
            t=calibrate([r[m] for r in rows if r['split']=='calibration' and r['category']=='A'],target)
            assert t==thresholds[str(target)][m]
            w=metrics['methods'][m]['working_points'][str(target)]
            for c in ['A','B_raw','B_post','D']:
                selected=[r for r in rows if r['split']=='test' and r['category']==c]
                count=sum(r[m]<t if c=='A' else r[m]>=t for r in selected)
                assert (w['test'][c]['count'],w['test'][c]['total'])==(count,len(selected))
                assert abs(w['test'][c]['prompt_mean']-count/len(selected))<1e-12
    checks.append('All three working points and error counts independently recomputed from CSV; SELF passed')
    indexes={m:json.loads((out/f'features_{m}.json').read_text()) for m in ['clip','sscd','dinov2']}
    for model,ix in indexes.items():
        assert set(ix)==set(table)
        for item in ix.values():
            a=np.load(root/item['path'],allow_pickle=False)
            assert a.shape==((256,384) if model=='dinov2' else (512,)) and a.dtype==np.float32
            assert np.isfinite(a).all() and np.allclose(np.linalg.norm(a,axis=-1),1,atol=1e-5)
            assert a.nbytes==item['bytes'] and (root/item['path']).stat().st_size==item['file_bytes']
    for r in rows[::137]:
        for model,ix in indexes.items():
            a,b=[np.load(root/ix[r[s]]['path'],allow_pickle=False) for s in ['left','right']]
            for m,v in scores(a,b,model).items():assert abs(v-r[m])<1e-6
    checks.append('All feature shapes/bytes/norms verified and deterministic sample of CSV recomputed through stage02 API')
    for task in ['clip_sscd','dinov2','generate_preflight','generate_main']:
        binding=json.loads((out/f'binding_{task}.json').read_text());idx=5 if task=='clip_sscd' else 7
        assert binding['CUDA_VISIBLE_DEVICES']==HOST_GPUS[idx] and binding['driver']['uuid']==HOST_GPUS[idx] and binding['driver']['count']==1
        assert binding.get('device',binding.get('torch_device'))=='cuda:0'
        if task.startswith('generate'):assert binding['pid_rows']
    budget=json.loads((out/'generation_budget.json').read_text());assert budget['charged_seconds']<=10800
    download=json.loads((out/'download_budget.json').read_text());assert download['transferred_bytes']<=15_000_000_000
    checks.append('UUID/device binding records and generation/download budgets verified')
    for path,expected_hash in json.loads((out/'stage02_preservation.json').read_text()).items():assert sha256(root/path)==expected_hash
    checks.append('Stage02 data/config/reports/results unchanged')
    dump(out/'audit.json',dict(status='passed',checks=checks,visual_review='See figures/visual_review.json separately; machine checks do not assess composition similarity'))
