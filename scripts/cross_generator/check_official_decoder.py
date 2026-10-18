"""CPU-only official GS scalar decoder compatibility check with synthetic material."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':raise SystemExit('CPU visibility required')
import json,sys
import numpy as np
from gs_batch import private_module,r
from evaluate_tests import quantizer_gate


def main():
    sys.path.insert(0,str(r.UPSTREAM))
    import torch
    from scipy.stats import norm
    np.random.seed(240101);torch.manual_seed(240101)
    private=private_module();wm=private.provider(bytes(range(80)),'cpu')
    z=wm.get_wm_latents()['zT_torch']
    assert float(wm.get_accuracies(z)['bit_accuracies'][0])==1.0
    array=z.numpy().astype(np.float64);array.reshape(-1)[::17]*=-1
    quantizer_gate(array)
    score64=float(wm.get_accuracies(torch.from_numpy(array))['bit_accuracies'][0])
    score32=float(wm.get_accuracies(torch.from_numpy(array.astype(np.float32)))['bit_accuracies'][0])
    assert score64==score32
    array.reshape(-1)[:4]=[-1e-8,0,1e-8,20.]
    quantizer_gate(array)
    try:quantizer_gate(np.full((1,4,64,64),-1e-30))
    except ValueError:pass
    else:raise AssertionError('CDF/sign disagreement must stop interpretation')
    assert not torch.cuda.is_initialized()
    print(json.dumps(dict(passed=True,cases=4,original_score=1.0,float64_tensor_supported=True,
        float64_float32_same_bits_score_agrees=True,near_zero_disagreement_rejected=True,
        models_loaded=False,gpu_used=False,material='synthetic_public_fixture')))


if __name__=='__main__':main()
