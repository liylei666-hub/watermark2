"""CPU checks for paired denominator, cast boundaries and sealed role inventory."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('CPU visibility required')
import tempfile,unittest
from pathlib import Path
import numpy as np
from common import c,IDS,METHODS,cast_input,seal_bundle,bundle,summary

class ContractTests(unittest.TestCase):
    def test_cast_exact_sign(self):
        x=np.linspace(-2,2,np.prod(c.SHAPE)).reshape(c.SHAPE)
        self.assertTrue(np.array_equal(x>=0,cast_input(x)>=0))
    def test_cast_underflow(self):
        x=np.full(c.SHAPE,-1e-100)
        with self.assertRaises(ValueError):cast_input(x)
    def test_cast_overflow(self):
        with np.errstate(over='ignore'),self.assertRaises(ValueError):cast_input(np.full(c.SHAPE,1e100))
    def test_wrong_shape(self):
        with self.assertRaises(ValueError):cast_input(np.ones(4))
    def test_nonfinite(self):
        with self.assertRaises(ValueError):cast_input(np.full(c.SHAPE,np.nan))
    def test_strict_threshold_full_denominator(self):
        rows=[dict(sample_id=sid,reference=.5,baseline=.70703125,corrected=.7109375) for sid in IDS]
        result=summary(rows)
        self.assertEqual(result['ordinary_gs_pass_counts'],dict(baseline=0,corrected=8))
        self.assertEqual(result['pairs'],8);self.assertIsNone(result['reference_valid_secondary_mean'])
    def test_secondary_does_not_select_primary(self):
        rows=[dict(sample_id=sid,reference=1 if i==0 else 0,baseline=.5,corrected=.75 if i==0 else .25) for i,sid in enumerate(IDS)]
        result=summary(rows);self.assertEqual(result['mean_difference'],-.1875)
        self.assertEqual(result['reference_valid_secondary_mean'],.25)
    def test_missing_or_duplicate_pair(self):
        rows=[dict(sample_id=sid,reference=1,baseline=.5,corrected=.5) for sid in IDS]
        with self.assertRaises(ValueError):summary(rows[:-1])
        rows[-1]['sample_id']=IDS[0]
        with self.assertRaises(ValueError):summary(rows)
    def test_forged_score(self):
        rows=[dict(sample_id=sid,reference=1,baseline=.5,corrected=float('nan')) for sid in IDS]
        with self.assertRaises(ValueError):summary(rows)
    def test_input_bundle_integrity_and_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for sid in IDS:
                for m in METHODS:c.save_array(p/(sid+'_'+m+'.npy'),np.ones(c.SHAPE,dtype='float32'),'float32')
            digest=seal_bundle(p,'attack_inputs');bundle(p,digest,'attack_inputs')
            with self.assertRaises(ValueError):bundle(p,digest,'evaluation_images')
            (p/'target_scores.json').write_text('{}')
            with self.assertRaises(ValueError):bundle(p,digest,'attack_inputs')
    def test_missing_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):seal_bundle(Path(tmp),'evaluation_images')

if __name__=='__main__':unittest.main()
