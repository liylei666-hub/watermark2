"""Fixed image inventory for evaluator-side target encoding."""
import hashlib
import json
from pathlib import Path

REMOTE = '/data0/liyanlei/watermark_research'
RUN = 'runs/17_cover_pilot_20261017T214442Z'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)


def expected_inputs():
    return {f'{task}/{role}': f'{RUN}/attack_inputs/{task}/{role}.png'
        if role in ['reference','cover'] else f'{RUN}/attack_outputs/{task}/{role}/candidate.png'
        for task in [1,2,3] for role in ['reference','cover','imprint','jain']}


def validate(cfg, root):
    expected = expected_inputs()
    if set(cfg['inputs']) != set(expected): raise ValueError('Expected all twelve fixed images')
    paths = {}
    for key,relative in expected.items():
        rec = cfg['inputs'][key]
        if set(rec) != {'path','sha256'} or rec['path'] != REMOTE+'/'+relative:
            raise ValueError('Input not in fixed image inventory')
        p = Path(root)/relative
        if sha(p) != rec['sha256']: raise ValueError('Fixed image changed')
        paths[key] = p
    return paths
