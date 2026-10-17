"""Shared launch checks; importing this module does not initialize CUDA."""
import ast
import csv
import importlib.metadata
import os
from pathlib import Path
import subprocess
import contract as c

ROOT=Path('/data0/liyanlei/watermark_research')
UPSTREAM=ROOT/'third_party/semantic-forgery'


def verify_runtime(path):
    path=Path(path)
    if c.sha(path)!=path.with_suffix('.sha256').read_text().strip():raise ValueError('Runtime manifest changed')
    cfg=c.read(path)
    for name,h in cfg['code_hashes'].items():
        if c.sha(name)!=h:raise ValueError('Code hash mismatch: '+name)
    for name,version in cfg['versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('Package mismatch: '+name)
    return cfg


def check_device(runtime_path,output):
    cfg=verify_runtime(runtime_path)
    uuid=os.environ.get('CUDA_VISIBLE_DEVICES')
    if uuid not in cfg['allowed_gpu_uuids'].values():raise ValueError('Expected authorized UUID')
    for key,value in dict(CUDA_DEVICE_ORDER='PCI_BUS_ID',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8').items():
        if os.environ.get(key)!=value:raise ValueError('Environment mismatch: '+key)
    rows=list(csv.reader(subprocess.check_output(['nvidia-smi','-i',uuid,'--query-gpu=index,uuid,name,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).splitlines(),skipinitialspace=True))
    apps=list(csv.reader(subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True).splitlines(),skipinitialspace=True))
    selected=[a for a in apps if a and a[0]==uuid]
    c.write(Path(output)/'device_preimport.json',dict(rows=rows,compute_apps=selected))
    if len(rows)!=1:raise ValueError('GPU identity ambiguous')
    row=rows[0]
    if cfg['allowed_gpu_uuids'].get(row[0])!=row[1] or row[2]!='NVIDIA GeForce RTX 3090' or int(row[3])>50 or int(row[4])!=0 or selected:
        raise RuntimeError('GPU not verified idle')
    return cfg


def deterministic(seed):
    import random
    import numpy as np
    import torch
    if torch.cuda.device_count()!=1:raise ValueError('One visible GPU required')
    torch.cuda.set_device(0)
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.use_deterministic_algorithms(True)


def definitions(path,names,scope):
    tree=ast.parse(Path(path).read_bytes())
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    if len(nodes)!=len(names) or {n.name for n in nodes}!=set(names):raise ValueError('Source definitions missing')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)


def tensor(path,value):
    import numpy as np
    array=value.detach().cpu().contiguous().numpy()
    if array.dtype!=np.float32 or not np.isfinite(array).all():raise ValueError('Invalid tensor')
    with Path(path).open('xb') as f:np.save(f,array,allow_pickle=False)
    return dict(path=Path(path).name,sha256=c.sha(path),shape=list(array.shape),dtype=str(array.dtype))


def official_provider(model):
    import sys
    sys.path.insert(0,str(UPSTREAM))
    from utils.pipe import pipe_utils
    # Same official dispatch class, with the pinned local snapshot passed to every loader.
    return pipe_utils.PIPE_PROVIDERS[model['model_id']](pretrained_model_name_or_path=model['snapshot'],
        resolution=512,device='cuda:0',eager_loading=True,
        scheduler_classes=pipe_utils.SCHEDULER_CLASSES['DDIM'],
        unet_id_or_checkpoint_dir=None,lora_checkpoint_dir=None,vae_id=None,zero_unet=False,disable_tqdm=True)
