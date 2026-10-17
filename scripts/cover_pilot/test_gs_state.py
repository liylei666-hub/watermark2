"""CPU checks of the pinned official GS identity and stored-latent scoring."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility must be empty')
if os.environ.get('HF_HUB_OFFLINE')!='1':raise SystemExit('Offline mode required')
import argparse
import hashlib
import json
import sys
import unittest
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    root=args.root;upstream=root/'third_party/semantic-forgery'
    audit=json.loads((root/'reports/16_cover_preparation/gs_source_audit.json').read_text())
    for rec in audit['sources']:
        assert hashlib.sha256((upstream/rec['path']).read_bytes()).hexdigest()==rec['sha256']
    sys.path.insert(0,str(upstream))
    import numpy as np
    import torch
    from utils.wm.gs_provider import GsProvider
    from utils.utils import get_detection_threshold,check_if_detection_successful
    assert not torch.cuda.is_initialized()
    params=dict(latent_shape=(1,4,64,64),device='cpu',dtype=torch.float32,
                message_width_in_bytes=32,num_replications=64,l=1,offset=0)
    def provider():return GsProvider(**params)
    def identity(w):
        # Identity fingerprints only; never print/export raw message/key/nonce.
        return {name:hashlib.sha256(getattr(w,name)[0]).hexdigest() for name in ['messages','keys','nonces']}
    observations={}
    manifest=json.loads((root/'runs/04_reprompt_latent_diag_seed1_20261013T025322Z/evaluator_only/tensor_manifest.json').read_text())

    class Tests(unittest.TestCase):
        def test_fixed_identity_independent_of_sampling_seed(self):
            np.random.seed(11);a=provider();np.random.seed(12);b=provider()
            self.assertEqual(identity(a),identity(b));observations['identity_fingerprints']=identity(a)

        def test_sampling_changes_noise_preserves_identity(self):
            a=provider();np.random.seed(11);x=a.get_wm_latents()['zT_torch']
            np.random.seed(12);y=a.get_wm_latents()['zT_torch']
            self.assertFalse(torch.equal(x,y));self.assertTrue(torch.isfinite(x).all())
            self.assertEqual(a.get_accuracies(x)['bit_accuracies'],[1.0])
            self.assertEqual(provider().get_accuracies(y)['bit_accuracies'],[1.0])
            observations['synthetic_sampling_test']='distinct finite noise, same fixed identity, exact original-message recovery'

        def test_archived_latents_score_under_fresh_provider(self):
            expected={'target_original_wm_zT':1.0,'target_inverted_reference_zT':1.0,'target_inverted_forged_zT':0.953125}
            rows=[]
            for name,value in expected.items():
                rec=manifest['tensors'][name];p=Path(rec['path'])
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),rec['sha256'])
                array=np.load(p,allow_pickle=False)
                actual=float(provider().get_accuracies(torch.from_numpy(array))['bit_accuracies'][0])
                self.assertEqual(actual,value);rows.append(dict(name=name,sha256=rec['sha256'],bit_accuracy=actual))
            observations['archived_latent_readback']=rows

        def test_strict_threshold_boundary(self):
            threshold=get_detection_threshold('GS')
            self.assertEqual(threshold,181/256)
            self.assertFalse(check_if_detection_successful('GS',threshold,181/256))
            self.assertFalse(check_if_detection_successful('GS',threshold,180/256))
            self.assertTrue(check_if_detection_successful('GS',threshold,182/256))
            observations['threshold']=dict(value=threshold,operator='>')

        def test_no_cuda_or_pipeline_loaded(self):
            self.assertFalse(torch.cuda.is_initialized())
            self.assertNotIn('utils.pipe.pipe_utils',sys.modules)

    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert not torch.cuda.is_initialized()
    print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        observations=observations,gpu_used=False,pretrained_models_loaded=False,new_model_experiments_run=0,
        source_files_verified=len(audit['sources']),scope='Synthetic GS latent and historical saved-latent CPU checks; no new image generation/inversion'),indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
