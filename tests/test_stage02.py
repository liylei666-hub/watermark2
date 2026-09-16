import copy, os, unittest
import numpy as np
from stage02.core import METHODS,HOST_GPUS,cache_key,calibrate,fit_thresholds,normalize,rate,scores,validate_gpu_config,validate_manifest

class CoreTests(unittest.TestCase):
    def test_cpu_test_entry(self):self.assertEqual(os.environ.get('CUDA_VISIBLE_DEVICES'),'')
    def test_threshold_finite_rule_and_ties(self):
        self.assertEqual(calibrate(range(20)),1.)
        self.assertEqual(rate([0,1,1,2],1,True),dict(count=1,total=4,rate=.25))
        self.assertEqual(rate([0,1,1,2],1),dict(count=3,total=4,rate=.75))
        self.assertEqual(calibrate([.5]*20),.5)
        with self.assertRaises(ValueError):calibrate([])
        with self.assertRaises(ValueError):calibrate([np.nan])
    def test_test_data_cannot_change_thresholds(self):
        rows=[dict(split='smoke_calibration',category='A',**{m:i for m in METHODS}) for i in range(20)]
        test=[dict(split='smoke_test',category='D',**{m:100 for m in METHODS})]
        baseline=fit_thresholds(rows+test)
        test[0].update(category='A',**{m:-1000 for m in METHODS})
        self.assertEqual(baseline,fit_thresholds(rows+test))
    def test_quantile_linear_known(self):
        a=np.tile([1.,0.],(4,1));b=np.array([[0,1],[.2,np.sqrt(.96)],[.8,.6],[1,0]])
        s=scores(a,b,'dinov2');self.assertAlmostEqual(s['DINO_local_mean'],.5,places=6);self.assertAlmostEqual(s['DINO_local_q10'],.06,places=6)
    def test_normalization_and_self(self):
        a=normalize(np.array([[3.,4.],[4.,3.]],dtype='float32'))
        for v in scores(a,a,'dinov2').values():self.assertAlmostEqual(v,1,places=6)
        with self.assertRaises(ValueError):normalize([0,0])
        with self.assertRaises(ValueError):normalize([np.inf,0])
    def test_cache_invalidation(self):
        args=['image','model','weight','commit',{'resize':224}];key=cache_key(*args)
        for index,value in [(0,'other_image'),(2,'other_weight'),(3,'other_commit'),(4,{'resize':256})]:
            changed=copy.deepcopy(args);changed[index]=value;self.assertNotEqual(key,cache_key(*changed))
    def test_gpu_config_rejects_invalid_without_cuda(self):
        cfg={'gpu_uuids':{str(k):v for k,v in HOST_GPUS.items()}}
        self.assertEqual(validate_gpu_config(cfg,HOST_GPUS[5],'clip_sscd'),5)
        self.assertEqual(validate_gpu_config(cfg,HOST_GPUS[7],'dinov2'),7)
        for invalid in [None,'','0','5','6','7','GPU-mock-forbidden-6',HOST_GPUS[7],HOST_GPUS[5]+','+HOST_GPUS[7]]:
            with self.assertRaises(ValueError):validate_gpu_config(cfg,invalid,'clip_sscd')
        bad=copy.deepcopy(cfg);bad['gpu_uuids']['6']='GPU-mock-forbidden-6'
        with self.assertRaises(ValueError):validate_gpu_config(bad,HOST_GPUS[5],'clip_sscd')
    def manifest(self):
        return dict(images=[dict(id='a',group='a',pixel_sha256='1',split='smoke_calibration'),dict(id='aa',group='a',pixel_sha256='2',split='smoke_calibration'),dict(id='b',group='b',pixel_sha256='3',split='smoke_test')],pairs=[dict(pair_id='p',left='a',right='aa',category='A',split='smoke_calibration',donor=None)],near_duplicate_edges=[])
    def test_manifest_leakage_and_donor(self):
        m=self.manifest();self.assertTrue(validate_manifest(m))
        for mutate in [lambda m:m['images'][1].update(split='smoke_test'),lambda m:m['pairs'][0].update(donor='b'),lambda m:m['near_duplicate_edges'].append(['a','b']),lambda m:m['images'][2].update(pixel_sha256='1')]:
            m=self.manifest();mutate(m)
            with self.assertRaises(ValueError):validate_manifest(m)
    def test_self_not_A(self):
        m=self.manifest();m['pairs'][0]['right']='a'
        with self.assertRaises(ValueError):validate_manifest(m)

if __name__=='__main__':unittest.main()
