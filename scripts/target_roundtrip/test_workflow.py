"""CPU mock verifies clone isolation, fixed calls, arm ordering and pre-evaluation freeze."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import unittest
from experiment import generate_and_measure

class Value:
    def __init__(self,value):self.value=value
    def clone(self):return Value(self.value)

class Tests(unittest.TestCase):
    def test_fixed_flow_and_input_isolation(self):
        events=[];source=Value(19);images={};frozen=set()
        class Provider:
            def generate(self,**kwargs):
                self_test.assertEqual(kwargs['num_inference_steps'],50)
                self_test.assertEqual(kwargs['guidance_scale'],7.5)
                self_test.assertIsNot(kwargs['latents'],source)
                self_test.assertEqual(kwargs['latents'].value,19)
                kwargs['latents'].value=-1
                image=object();images[kwargs['prompts']]=image
                events.append(('generate',kwargs['prompts']))
                return {'images_PIL':[image]}
            def invert_images(self,image,**kwargs):
                self_test.assertIn(image,frozen)
                self_test.assertEqual(kwargs,{'num_inference_steps':50})
                events.append(('invert',image))
                return {'zT_torch':Value(27)}
        def freeze(arm,image):events.append(('freeze',arm));frozen.add(image)
        def measure(arm,image,value):
            self.assertEqual(value.value,27);self.assertIn(image,frozen);return arm
        self_test=self
        got=generate_and_measure(Provider(),source,{'same_prompt':'tea','changed_prompt':'boat'},freeze,measure)
        self.assertEqual(got,{'same_prompt':'same_prompt','changed_prompt':'changed_prompt'})
        self.assertEqual(source.value,19)
        self.assertEqual([e[0] for e in events],['generate','freeze','invert']*2)
        self.assertEqual([e[1] for e in events if e[0]=='generate'],['tea','boat'])

if __name__=='__main__':unittest.main()
