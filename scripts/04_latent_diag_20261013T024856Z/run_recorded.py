"""Run the original entry verbatim with observation-only call wrappers."""
import os
assert os.environ.get("CUDA_VISIBLE_DEVICES")=="GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da"
assert os.environ.get("CUDA_DEVICE_ORDER")=="PCI_BUS_ID"
assert os.environ.get("HF_HUB_OFFLINE")=="1"
import sys
import json
import runpy
from pathlib import Path
from recording import Recorder,sha,write_json,wrap_sampling,wrap_generate,wrap_invert,wrap_validate,wrap_download

run=Path(sys.argv[1])
cfg=json.loads((run/"config.json").read_text())
up=Path(cfg["upstream_path"])
sys.path.insert(0,str(up))
import torch
assert torch.cuda.device_count()==1
torch.cuda.set_device(0)
write_json(run/"evaluator_only/device.json",dict(visible_count=1,logical_device="cuda:0",
    name=torch.cuda.get_device_name(0),uuid=os.environ["CUDA_VISIBLE_DEVICES"]))
from utils.wm.gs_provider import GsProvider
from utils.pipe.pipe_provider import PipeProvider
from utils import imprint_utils
from diffusers import DiffusionPipeline

r=Recorder(run/"evaluator_only",sha(run/"config.json"),cfg["arguments"]["modelid_target"])
GsProvider.get_wm_latents=wrap_sampling(GsProvider.get_wm_latents,r)
PipeProvider.generate=wrap_generate(PipeProvider.generate,r)
PipeProvider.invert_images=wrap_invert(PipeProvider.invert_images,r)
imprint_utils.validate=wrap_validate(imprint_utils.validate,r)
loaded=[]
DiffusionPipeline.download=classmethod(wrap_download(DiffusionPipeline.download.__func__,cfg["model_snapshots"],loaded))
sys.argv=[str(up/"run_reprompting.py"),"--out_dir",str(run/"evaluator_only/official_output")]
for k,v in cfg["arguments"].items(): sys.argv.extend(["--"+k,str(v)])
try:
    runpy.run_path(str(up/"run_reprompting.py"),run_name="__main__")
    r.finish()
finally:
    write_json(run/"evaluator_only/actual_model_loads.json",loaded)
    write_json(run/"evaluator_only/capture_progress.json",dict(counts=r.counts,tensors=r.records,images=r.images))

