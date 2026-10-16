"""CPU check of normalization and VAE inverse scaling; no CUDA libraries imported."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import unittest
from types import SimpleNamespace
from experiment import reconstruct

class Tests(unittest.TestCase):
    def test_mean_normalization_inverse_scaling_and_quantization(self):
        calls=[]
        class Vae:
            config=SimpleNamespace(scaling_factor=.125)
            def encode(self,x):
                calls.append(('encode',x));return SimpleNamespace(latent_dist=SimpleNamespace(mean=7.))
            def decode(self,x,return_dict):
                calls.append(('decode',x,return_dict));return [11.]
        class Processor:
            def postprocess(self,x,output_type):
                calls.append(('postprocess',x,output_type));return ['image']
        self.assertEqual(reconstruct(Vae(),.75,Processor()),'image')
        self.assertEqual(calls,[('encode',.5),('decode',7.,False),('postprocess',11.,'pil')])

if __name__=='__main__':unittest.main()
