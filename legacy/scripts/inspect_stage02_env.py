import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import datetime, json, platform, subprocess, sys
from pathlib import Path
import torch, torchvision, numpy, PIL, matplotlib
root=Path(__file__).resolve().parents[1]
commands=[['uname','-a'],['cat','/etc/os-release'],['df','-h',str(root)],['nvidia-smi','-i','5,7','--query-gpu=index,uuid,pci.bus_id,name,memory.total,memory.used,memory.free,utilization.gpu','--format=csv'],['nvidia-smi','-i','5,7','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv'],['git','-C',str(root),'status','--short','--branch']]
info=dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),host=platform.node(),project=str(root),python=sys.executable,version=sys.version,prefix=sys.prefix,base_prefix=sys.base_prefix,torch=torch.__version__,torchvision=torchvision.__version__,cuda_build=torch.version.cuda,cudnn=torch.backends.cudnn.version(),numpy=numpy.__version__,pillow=PIL.__version__,matplotlib=matplotlib.__version__,CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],virtual_env=os.environ.get('VIRTUAL_ENV'),conda_prefix=os.environ.get('CONDA_PREFIX'),note='Absolute environment Python used. No package/environment modifications. CUDA hidden for this CPU inspection.')
lines=['Stage 02 server environment inspection',json.dumps(info,indent=2,ensure_ascii=False)]
for cmd in commands:
    r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    lines.extend(['COMMAND: '+' '.join(cmd),f'EXIT: {r.returncode}',r.stdout])
(root/'research/02_server_environment.txt').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(info,indent=2))
