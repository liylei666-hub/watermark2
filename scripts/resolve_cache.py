import os
from pathlib import Path
import json

ROOT=Path('/data0/liyanlei/watermark_research')
RUN=ROOT/'runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z'
os.environ.update(HF_HOME=str(ROOT/'cache/huggingface'),HF_HUB_OFFLINE='1',
                  TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',
                  CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES='GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da')
from huggingface_hub import hf_hub_download, constants

manifest=json.loads((RUN/'model_manifest_verified.json').read_text())
result=[]
for m in manifest:
    path=Path(hf_hub_download(m['repo'],'model_index.json',local_files_only=True))
    expected=ROOT/'cache/huggingface/hub'/('models--'+m['repo'].replace('/','--'))/'snapshots'/m['revision']/'model_index.json'
    assert path.resolve()==expected.resolve(),str(path)
    result.append(dict(model_id=m['repo'],revision=m['revision'],resolved_model_index=str(path)))
with (RUN/'snapshot_resolution.json').open('x') as f:
    json.dump(dict(hub_cache=constants.HF_HUB_CACHE,offline=constants.HF_HUB_OFFLINE,models=result),f,indent=2)
print('OFFLINE_MODEL_IDS_RESOLVE_TO_PINNED_SNAPSHOTS')
