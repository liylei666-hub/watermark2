import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
models = {}
for repo in ['stabilityai/stable-diffusion-xl-base-1.0', 'Manojb/stable-diffusion-2-1-base']:
    with urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'?blobs=true', timeout=30) as r:
        meta = json.load(r)
    revision = meta['sha']
    dest = root / repo.replace('/', '--')
    dest.mkdir(exist_ok=True)
    (dest/'metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    with urllib.request.urlopen(f'https://huggingface.co/{repo}/resolve/{revision}/model_index.json', timeout=30) as r:
        index = json.load(r)
    (dest/'model_index.json').write_text(json.dumps(index, indent=2), encoding='utf-8')
    files = [{'path': f['rfilename'], 'size': f.get('size'), 'lfs': f.get('lfs')} for f in meta['siblings']]
    models[repo] = {'revision': revision, 'index': index, 'files': files}
print(json.dumps(models, indent=2))
