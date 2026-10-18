"""Evaluator-side CPU identity checks against the pinned GS provider.

Only fingerprints leave this process. No pipeline is imported or loaded.
"""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '' or os.environ.get('HF_HUB_OFFLINE') != '1':
    raise SystemExit('CPU/offline environment required')
import hashlib
import json
from pathlib import Path
import sys

root=Path('/data0/liyanlei/watermark_research')
upstream=root/'third_party/semantic-forgery'
audit=json.loads((root/'reports/16_cover_preparation/gs_source_audit.json').read_text())
for row in audit['sources']:
    if hashlib.sha256((upstream/row['path']).read_bytes()).hexdigest() != row['sha256']:
        raise ValueError('Pinned source changed')
sys.path.insert(0,str(upstream))
import numpy as np
import torch
from utils.wm.gs_provider import GsProvider
rows=[]
for offset in [0,1,2]:
    provider=GsProvider(latent_shape=(1,4,64,64),device='cpu',dtype=torch.float32,
        message_width_in_bytes=32,num_replications=64,l=1,offset=offset)
    fingerprints={name:hashlib.sha256(getattr(provider,name)[offset]).hexdigest()
        for name in ['messages','keys','nonces']}
    np.random.seed(900+offset)
    z=provider.get_wm_latents()['zT_torch']
    if not torch.isfinite(z).all():raise RuntimeError('Nonfinite synthetic noise')
    score=float(provider.get_accuracies(z)['bit_accuracies'][0])
    if score!=1.:raise RuntimeError('Synthetic original noise did not recover exactly')
    rows.append(dict(offset=offset,identity_fingerprints=fingerprints,synthetic_bit_accuracy=score))
for name in ['messages','keys','nonces']:
    if len({r['identity_fingerprints'][name] for r in rows})!=3:
        raise RuntimeError('Planned identities not distinct from historical offset0')
if torch.cuda.is_initialized() or 'utils.pipe.pipe_utils' in sys.modules:
    raise RuntimeError('Unexpected CUDA/pipeline initialization')
print(json.dumps(dict(status='passed',identities=rows,source_files_verified=len(audit['sources']),
    gpu_used=False,models_loaded=False,new_model_experiments_run=0,
    scope='three synthetic GS latents only; no images, generation, inversion or existing-candidate evaluation'),indent=2))
