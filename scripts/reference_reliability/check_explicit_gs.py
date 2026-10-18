"""CPU/offline explicit-state compatibility check; publish fingerprints only."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '' or os.environ.get('HF_HUB_OFFLINE') != '1':
    raise SystemExit('CPU/offline required')
import json
import sys
import tempfile
from pathlib import Path
from common import r, sha
import private_state as private
sys.path.insert(0, str(r.UPSTREAM))
if sha(r.UPSTREAM/'utils/wm/gs_provider.py') != '233ff05fa47d18d5875577d2cd920bd21d8ceea05149f5f100c1fab32c524d99':
    raise ValueError('Upstream GS changed')
import numpy as np
import torch
from scores import cdf_bins
from scipy.stats import norm

rows=[]
with tempfile.TemporaryDirectory(dir=r.ROOT/'tmp') as tmp:
    folder=Path(tmp);folder.chmod(0o700)
    for k in range(4):
        raw=private.create(folder,k);fingerprints=private.fingerprints(raw)
        assert private.load(folder,k,fingerprints)==raw
        try:private.create(folder,k)
        except FileExistsError:pass
        else:raise AssertionError('Private state overwrite allowed')
        wm=private.provider(raw,'cpu');np.random.seed(2300+k)
        z=wm.get_wm_latents()['zT_torch']
        score=float(wm.get_accuracies(z)['bit_accuracies'][0])
        assert score==1. and torch.isfinite(z).all()
        assert wm.messages==[raw[:32]] and wm.keys==[raw[32:64]] and wm.nonces==[raw[64:]]
        vector=cdf_bins(z.numpy())
        scalar=np.array([min(int(norm.cdf(v)*2),1) for v in np.nditer(z.numpy())])
        assert np.array_equal(vector,scalar)
        rows.append(dict(fingerprints=fingerprints,original_bit_accuracy=score,scalar_cdf_agreement=True))
for name in ('message','key','nonce'):
    assert len({row['fingerprints'][name] for row in rows})==4
assert not torch.cuda.is_initialized() and 'utils.pipe.pipe_utils' not in sys.modules
print(json.dumps(dict(status='passed',rows=rows,gpu_used=False,models_loaded=False,
                     new_model_experiments_run=0,private_file_modes_verified=True),indent=2))
