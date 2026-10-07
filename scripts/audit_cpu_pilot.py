"""Audit persisted pilot outputs without model inference; features are optional local evidence."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/cpu_pilot'


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def audit():
    cfg=json.loads((ROOT/'configs/cpu_pilot.json').read_text(encoding='utf-8'))
    manifest=read('manifest.json');metrics=read('metrics.json')['metrics'];thresholds=read('thresholds.json')['values']
    rows=list(csv.DictReader((OUT/'scores.csv').open(encoding='utf-8',newline='')))
    groups={}
    for r in manifest:
        groups.setdefault(r['source_id'],set()).add(r['split'])
    assert len(groups)==18 and all(len(v)==1 for v in groups.values())
    assert len(rows)==162 and len({(r['source_id'],r['variant']) for r in rows})==162
    cells=0
    for method,split_metrics in metrics.items():
        cal=sorted(float(r[method]) for r in rows if r['split']=='calibration' and r['variant'] in cfg['allowed'])
        assert thresholds[method]==cal[math.floor(cfg['target_frr']*len(cal))]
        for split,categories in split_metrics.items():
            for cat,saved in categories.items():
                selected=[r for r in rows if r['split']==split and (r['variant'] in cfg['allowed'] if cat=='allowed_pooled' else r['variant']==cat)]
                accepted=sum(float(r[method])>=thresholds[method] for r in selected)
                assert (accepted,len(selected))==(saved['accepted'],saved['total'])
                assert math.isclose(accepted/len(selected),saved['rate'])
                cells+=1
    runtime=read('runtime.json')
    assert runtime['device']=='cpu' and runtime['CUDA_VISIBLE_DEVICES']==''
    assert runtime['score_sha256']==hashlib.sha256((OUT/'scores.csv').read_bytes()).hexdigest()
    assert read('metrics.json')['full_watermark_verifier'] is False
    local_pixels=0
    for r in manifest:
        path=ROOT/r['path']
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256'];local_pixels+=1
    follow=OUT/'followup'
    follow_cells=0
    if (follow/'metrics.json').exists():
        follow_metrics=json.loads((follow/'metrics.json').read_text(encoding='utf-8'))
        follow_rows=list(csv.DictReader((follow/'scores.csv').open(encoding='utf-8',newline='')))
        assert len(follow_rows)==108
        assert follow_metrics['threshold_sha256']==hashlib.sha256((OUT/'thresholds.json').read_bytes()).hexdigest()
        assert follow_metrics['score_sha256']==hashlib.sha256((follow/'scores.csv').read_bytes()).hexdigest()
        for method,categories in follow_metrics['metrics'].items():
            for cat,saved in categories.items():
                edit,post=cat.split('+')
                selected=[r for r in follow_rows if r['split']=='test' and r['modification']==edit and r['postprocess']==post]
                assert (sum(float(r[method])>=thresholds[method] for r in selected),len(selected))==(saved['accepted'],saved['total'])
                follow_cells+=1
        for r in json.loads((follow/'manifest.json').read_text(encoding='utf-8')):
            path=ROOT/r['path']
            if path.exists():
                assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256'];local_pixels+=1
    return dict(status='passed',source_groups=18,score_rows=len(rows),checked_metric_cells=cells,followup_checked_cells=follow_cells,
                local_image_hashes_checked=local_pixels,scope='persisted-score recalculation and source split; no authenticity security claim')


if __name__=='__main__':print(json.dumps(audit(),indent=2))
