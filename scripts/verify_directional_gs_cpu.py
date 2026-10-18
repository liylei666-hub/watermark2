"""CPU readback of saved stage21 inversions; no model construction or inference."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

def main(root, audit):
    upstream = root / 'third_party/semantic-forgery'
    sources = []
    for record in audit['sources']:
        actual = hashlib.sha256((upstream / record['path']).read_bytes()).hexdigest()
        assert actual == record['sha256'], record['path']
        sources.append(dict(path=record['path'], sha256=actual))
    sys.path.insert(0, str(upstream))
    import numpy as np
    import torch
    from utils.wm.gs_provider import GsProvider
    providers = {offset: GsProvider(latent_shape=(1,4,64,64), device='cpu', offset=offset,
        message_width_in_bytes=32, num_replications=64, l=1) for offset in (1,2)}
    run = root / 'runs/21_directional_r2_20261018T023922Z'
    rows = []
    for path in sorted((run / 'evaluator_results').glob('*/*/metrics.json')):
        metrics = json.loads(path.read_text())
        latent = path.parent / 'target_inverse.npy'
        digest = hashlib.sha256(latent.read_bytes()).hexdigest()
        assert digest == metrics['target_inverse']['sha256']
        task = int(path.parent.parent.name)
        score = float(providers[1 if task <= 2 else 2].get_accuracies(
            torch.from_numpy(np.load(latent, allow_pickle=False)))['bit_accuracies'][0])
        assert score == metrics['bit_accuracy']
        assert (score > 181/256) == metrics['gs_detected']
        rows.append(dict(path=path.relative_to(root).as_posix(), latent_sha256=digest,
            bit_accuracy=score, gs_detected=score > 181/256))
    assert len(rows) == 28
    assert not torch.cuda.is_initialized()
    return dict(checked_at_utc=datetime.now(timezone.utc).isoformat(), status='passed',
        rows=rows, sources=sources, gpu_used=False, models_loaded=False,
        new_model_experiments_run=0, cuda_initialized=False,
        scope='Official CPU bit decoding of existing arrays; no generation or inversion')

if __name__ == '__main__':
    root = Path(sys.argv[1])
    audit = json.loads(sys.stdin.read())
    print(json.dumps(main(root, audit), indent=2))
