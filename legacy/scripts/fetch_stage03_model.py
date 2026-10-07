"""Fetch one pinned official SDXL fp16 pipeline with a persisted transfer budget."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import json, sys, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stage02.core import dump, sha256

REPO = 'stabilityai/stable-diffusion-xl-base-1.0'
FILES = ['model_index.json', 'scheduler/scheduler_config.json']
for name in ['text_encoder', 'text_encoder_2', 'unet', 'vae']:
    FILES += [name+'/config.json', name+('/model.fp16.safetensors' if name.startswith('text') else '/diffusion_pytorch_model.fp16.safetensors')]
for name in ['tokenizer', 'tokenizer_2']:
    FILES += [name+'/'+f for f in ['merges.txt', 'vocab.json', 'special_tokens_map.json', 'tokenizer_config.json']]

def main():
    out = ROOT/'outputs/stage03'; out.mkdir(parents=True, exist_ok=True)
    regpath = out/'generator_files.json'; budgetpath = out/'download_budget.json'
    budget = json.loads(budgetpath.read_text()) if budgetpath.exists() else dict(transferred_bytes=0, limit_bytes=15_000_000_000)
    if regpath.exists():
        reg = json.loads(regpath.read_text())
        if reg['model_id'] != REPO: raise RuntimeError('Existing generator selection differs; do not replace its registry')
    else:
        with urllib.request.urlopen('https://huggingface.co/api/models/'+REPO+'?blobs=true', timeout=30) as r:
            info = json.load(r)
        table = {x['rfilename']: x for x in info['siblings']}
        selected = [table[f] for f in FILES]
        total = sum(x['size'] for x in selected)
        if total > budget['limit_bytes']: raise RuntimeError('Selected model exceeds download budget')
        reg = dict(model_id=REPO, revision=info['sha'], selected_bytes=total, files=selected, status='downloading')
        dump(regpath, reg)
    folder = ROOT/'weights/stage03_sdxl'/reg['revision']; folder.mkdir(parents=True, exist_ok=True)
    for meta in reg['files']:
        rel = meta['rfilename']; dst = folder/rel; dst.parent.mkdir(parents=True, exist_ok=True)
        expected = meta.get('lfs', {}).get('sha256')
        if dst.exists():
            actual = sha256(dst)
            if dst.stat().st_size != meta['size'] or (expected and actual != expected) or (meta.get('sha256') and actual != meta['sha256']):
                raise RuntimeError('Existing file incompatible: '+rel)
        else:
            part = dst.with_suffix(dst.suffix+'.part')
            # Files from interrupted attempts remain partial; a new request uses HTTP Range.
            for attempt in range(3):
                offset = part.stat().st_size if part.exists() else 0
                if offset == meta['size']: break
                if offset > meta['size']: raise RuntimeError('Oversized partial file')
                url = 'https://huggingface.co/'+REPO+'/resolve/'+reg['revision']+'/'+rel+'?download=true'
                req = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
                try:
                    with urllib.request.urlopen(req, timeout=60) as response:
                        if offset and response.status != 206: raise RuntimeError('Server refused range resume')
                        with part.open('ab' if offset else 'wb') as f:
                            while True:
                                chunk = response.read(4*1024*1024)
                                if not chunk: break
                                # Count bytes received, including interrupted/retried transfers.
                                budget['transferred_bytes'] += len(chunk); dump(budgetpath, budget)
                                if budget['transferred_bytes'] > budget['limit_bytes']: raise RuntimeError('Download budget exhausted')
                                f.write(chunk)
                    break
                except Exception:
                    if attempt == 2 or budget['transferred_bytes'] >= budget['limit_bytes']: raise
                    time.sleep(2)
            if part.stat().st_size != meta['size']: raise RuntimeError('Incomplete download: '+rel)
            actual = sha256(part)
            if expected and actual != expected: raise RuntimeError('Official LFS SHA mismatch: '+rel)
            part.replace(dst)
        meta.update(sha256=actual, path=str(dst.relative_to(ROOT)))
        dump(regpath, reg); print(rel, meta['size'], actual, flush=True)
    reg.update(status='complete', local_path=str(folder.relative_to(ROOT)))
    dump(regpath, reg); dump(budgetpath, budget)

if __name__ == '__main__': main()
