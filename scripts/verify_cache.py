"""Verify a transferred cache without importing model or GPU libraries."""
import hashlib
import json
from pathlib import Path

ROOT = Path('/data0/liyanlei/watermark_research')
RUN = ROOT/'runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z'
manifest = json.loads((RUN/'model_manifest_verified.json').read_text())
for model in manifest:
    base = ROOT/'cache/huggingface/hub'/('models--'+model['repo'].replace('/', '--'))
    assert (base/'refs/main').read_text().strip() == model['revision']
    for item in model['files']:
        path = base/'snapshots'/model['revision']/item['rfilename']
        assert path.stat().st_size == item['size'], str(path)
        h = hashlib.sha256()
        with path.open('rb') as src:
            for block in iter(lambda: src.read(16*1024*1024), b''):
                h.update(block)
        assert h.hexdigest() == item['sha256'], str(path)
        print('VERIFIED', model['repo'], item['rfilename'], flush=True)
    model['actual_snapshot'] = str(base/'snapshots'/model['revision'])
with (RUN/'server_cache_verification.json').open('x') as out:
    json.dump({'all_verified': True, 'models': manifest}, out, indent=2)
print('ALL_SERVER_FILES_VERIFIED', flush=True)
