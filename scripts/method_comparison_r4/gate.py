"""Three strict idle samples before any CUDA-capable import."""
import csv,datetime,json,os,subprocess,time
from pathlib import Path
from common import c,r

def gate_functions():
    scope=dict(csv=csv,datetime=datetime,json=json,subprocess=subprocess,time=time)
    r.definitions(r.ROOT/'scripts/gpu_preflight.py',{'snapshot','verify_idle'},scope)
    return scope

def check_device(runtime_path,output):
    cfg=r.verify_runtime(runtime_path);uuid=os.environ.get('CUDA_VISIBLE_DEVICES')
    if uuid not in cfg['allowed_gpu_uuids'].values():raise ValueError('Expected authorized GPU UUID')
    for key,value in dict(CUDA_DEVICE_ORDER='PCI_BUS_ID',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8').items():
        if os.environ.get(key)!=value:raise ValueError('Environment mismatch: '+key)
    index=int(next(k for k,v in cfg['allowed_gpu_uuids'].items() if v==uuid));scope=gate_functions()
    with (Path(output)/'child_preflight.jsonl').open('x') as f:
        def record(value):f.write(json.dumps(value)+'\n');f.flush();os.fsync(f.fileno())
        final=scope['verify_idle'](scope['snapshot'],record,index,uuid,'NVIDIA GeForce RTX 3090')
    row=final['row'];c.write(Path(output)/'device_preimport.json',dict(rows=[[row[i] for i in (0,1,2,4,5)]],compute_apps=final['compute_apps'],verification='three_consecutive_strict_idle_samples'))
    return cfg
