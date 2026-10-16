"""CPU tests use mocks only; no upstream imports or model loading."""
import os
assert os.environ.get("CUDA_VISIBLE_DEVICES")==""
import random
import sys
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from recording import Recorder,wrap_sampling,wrap_generate,wrap_invert,wrap_validate,wrap_download,write_json
from diagnostic import independent_global_cosine_diagnostic as cosine
d=Path(sys.argv[1]); d.mkdir()
checks={}
a=np.array([1.,0.],dtype=np.float32).reshape(1,1,1,2)
for name,x,y,want in [("same",a,a,1),("opposite",a,-a,-1),
    ("orthogonal",a,a[...,::-1],0),("positive_scaling",a*7,a*3,1)]:
    assert abs(cosine(x,y)-want)<1e-12
    checks[name]=True
for name,x,y in [("zero",a*0,a),("nan",a*float("nan"),a),
    ("inf",a*float("inf"),a),("shape",a,a.reshape(1,1,2,1)),
    ("batch",np.ones((2,1,1,2)),np.ones((2,1,1,2)))]:
    try: cosine(x,y)
    except ValueError: checks[name]=True
    else: raise AssertionError(name)
r=Recorder(d,"mock_config","target")
z=torch.arange(16,dtype=torch.float32).reshape(1,1,4,4)
ref=Image.new("RGB",(8,8),(10,20,30))
forged=Image.new("RGB",(8,8),(90,80,70))
sample={"zT_torch":z}
outputs={"target":{"images_PIL":[ref]},"proxy":{"images_PIL":[forged]}}
inversions={id(ref):{"zT_torch":z+1},id(forged):{"zT_torch":z+2}}
result={"mock":True}
calls={"sampling":0,"generate":0,"invert":0,"validate":0}
class Provider:
    def __init__(self,name): self.pretrained_model_name_or_path=name
    def generate(self,prompts,latents):
        calls["generate"]+=1
        assert latents is z
        return outputs[self.pretrained_model_name_or_path]
    def invert_images(self,images,num_inference_steps):
        calls["invert"]+=1
        return inversions[id(images)]
def sampling():
    calls["sampling"]+=1
    return sample
def validate(out_dir,image_to_verify_PIL,pipe_provider_target,step):
    calls["validate"]+=1
    if step == 1:
        import json
        from recording import sha
        frozen = json.loads((d / "candidate_before_evaluation.json").read_text())
        assert sha(frozen["path"]) == frozen["sha256"]
        assert np.array_equal(np.asarray(Image.open(frozen["path"])), np.asarray(image_to_verify_PIL))
    value=pipe_provider_target.invert_images(image_to_verify_PIL,num_inference_steps=50)
    assert value is inversions[id(image_to_verify_PIL)]
    image_to_verify_PIL.save(Path(out_dir)/("attack_instance_step="+str(step)+".png"))
    return result
target,proxy=Provider("target"),Provider("proxy")
Provider.generate=wrap_generate(Provider.generate,r)
Provider.invert_images=wrap_invert(Provider.invert_images,r)
wrapped=wrap_validate(validate,r)
before=z.clone()
states=(random.getstate(),np.random.get_state(),torch.get_rng_state().clone())
assert wrap_sampling(sampling,r)() is sample
assert target.generate("ref",latents=z) is outputs["target"]
assert wrapped(str(d),ref,target,-1) is result
assert proxy.invert_images(ref,50) is inversions[id(ref)]
assert proxy.generate("forged",latents=z) is outputs["proxy"]
assert wrapped(str(d),forged,target,1) is result
r.finish()
assert calls=={"sampling":1,"generate":2,"invert":3,"validate":2}
assert torch.equal(z,before)
assert random.getstate()==states[0]
ns=np.random.get_state()
assert ns[0]==states[1][0] and np.array_equal(ns[1],states[1][1]) and ns[2:]==states[1][2:]
assert torch.equal(torch.get_rng_state(),states[2])
checks.update(call_counts=True,returned_objects_identical=True,input_unchanged=True,
              cpu_rng_states_unchanged=True,tensor_roundtrip=True,png_binding=True)
loaded=[]; expected={"id":str(d)}; counter=[]
def download(cls,model_id,*args,**kwargs):
    counter.append((cls,model_id,args,kwargs))
    return expected[model_id]
wrapped_download=wrap_download(download,expected,loaded)
assert wrapped_download(Provider,"id",local_files_only=True) is expected["id"]
assert len(counter)==1 and counter[0][3]=={"local_files_only":True}
checks["download_passthrough"]=True
write_json(d.parent/"cpu_tests.json",dict(passed=True,checks=checks,
    limitation="Mock/CPU tests and static review only; full instrumented/uninstrumented equivalence not tested"))
print("CPU_TESTS_PASSED")

