"""External bookkeeping and one execution of the unmodified upstream CLI."""
import argparse
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time

ROOT = Path('/data0/liyanlei/watermark_research')
UP = ROOT/'third_party/semantic-forgery'
PY = ROOT/'envs/semantic_forgery_py310/bin/python'
UUID = 'GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da'
SHA = 'ca68950cd7b53b8438a49580f134b2a0db28d778'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def output(cmd): return subprocess.check_output(cmd, text=True).strip()
def write(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def gpu():
    raw=output(['nvidia-smi','--query-gpu=index,uuid,name,driver_version,memory.total,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'])
    apps=output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory,process_name','--format=csv,noheader,nounits'])
    rows=list(csv.reader(raw.splitlines(),skipinitialspace=True))
    target=next(r for r in rows if r[1]==UUID)
    return {'time':now(),'row':target,'compute_apps':apps}
def guard():
    g=gpu()
    assert g['row'][0]=='3' and g['row'][2]=='NVIDIA GeForce RTX 3090',g
    assert UUID not in g['compute_apps'],'Selected GPU occupied'
    assert int(g['row'][5])<=50 and int(g['row'][7])==0,'Unexpected GPU use'
    assert shutil.disk_usage(ROOT).free>=200*1024**3,'Disk reserve below 200 GiB'
    used=int(output(['du','-s','-B1',str(ROOT)]).split()[0])
    assert used<80*1024**3,'Project footprint exceeds budget (conservative includes phase01)'
    assert output(['git','-C',str(UP),'rev-parse','HEAD'])==SHA
    assert output(['git','-C',str(UP),'status','--porcelain'])=='','Upstream dirty'
    return g
def safe_env():
    env=os.environ.copy()
    env.update(CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES=UUID,
               HF_HOME=str(ROOT/'cache/huggingface'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
               HF_HUB_DISABLE_IMPLICIT_TOKEN='1',TMPDIR=str(ROOT/'tmp'),PYTHONUNBUFFERED='1',
               MPLCONFIGDIR=str(ROOT/'cache/matplotlib'))
    return env
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mode',choices=['prepare','check','run']); ap.add_argument('--run-dir'); a=ap.parse_args()
    if a.mode=='prepare':
        run=ROOT/'runs'/('02_reprompt_gs_sdxl_seed1_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        run.mkdir(parents=True,exist_ok=False)
        cfg=dict(wm_type='GS',modelid_target='stabilityai/stable-diffusion-xl-base-1.0',
                 modelid_attacker='Manojb/stable-diffusion-2-1-base',resolution=512,seed=1,
                 scheduler_target='DDIM',scheduler_attacker='DDIM',num_inference_steps_target=50,
                 num_inference_steps_attacker=50,guidance_scale_target=7.5,guidance_scale_attacker=7.5,
                 target_prompt='A studio photograph of a yellow ceramic teapot on a wooden table.',
                 attacker_prompt='A red sailboat on a calm blue lake, watercolor illustration.')
        cmd=[str(PY),'run_reprompting.py','--out_dir',str(run)]
        for k,v in cfg.items(): cmd.extend(['--'+k,str(v)])
        write(run/'config.json',{'arguments':cfg,'resample':False,'dtype':'float32','threshold':0.70703125,
            'threshold_comparator':'>','command':cmd,'cwd':str(UP),'gpu_uuid':UUID,'upstream_commit':SHA,'created_at':now()})
        (run/'command.sh').write_text('cd '+shlex.quote(str(UP))+'\n'+
            'CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES='+UUID+
            ' HF_HOME='+str(ROOT/'cache/huggingface')+' HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 '+shlex.join(cmd)+'\n')
        write(run/'initial_resource_check.json',guard()); print(run,flush=True); return
    run=Path(a.run_dir); cfg=json.loads((run/'config.json').read_text())
    env=safe_env()
    if a.mode=='check':
        checks=[('pip_check',[str(PY),'-m','pip','check']),
                ('pip_freeze',[str(PY),'-m','pip','freeze']),
                ('imports',[str(PY),'-c',"import torch,torchvision,diffusers,transformers,accelerate,torchmetrics,lpips,scipy,pandas,cryptography; from utils.pipe import pipe_utils; from utils.imprint_utils import validate; from utils.utils import GS_THRESHOLDS; assert GS_THRESHOLDS==0.70703125; print('IMPORTS_OK'); print('torch',torch.__version__,'runtime',torch.version.cuda)"])]
        for name,cmd in checks:
            with (run/(name+'.stdout')).open('x') as so,(run/(name+'.stderr')).open('x') as se:
                p=subprocess.run(cmd,cwd=str(UP),env=env,stdout=so,stderr=se)
            (run/(name+'.exit_code')).write_text(str(p.returncode)); assert p.returncode==0,name+' failed'
        write(run/'pre_cuda_check.json',guard())
        cmd=[str(PY),'-c',"import json,sys,torch; assert torch.cuda.device_count()==1; x=torch.ones(8,device='cuda:0'); torch.cuda.synchronize(); print(json.dumps(dict(python=sys.version,torch=torch.__version__,cuda_runtime=torch.version.cuda,visible_count=torch.cuda.device_count(),device=torch.cuda.get_device_name(0),sum=x.sum().item())))"]
        with (run/'cuda_test.stdout').open('x') as so,(run/'cuda_test.stderr').open('x') as se:
            p=subprocess.run(cmd,env=env,stdout=so,stderr=se)
        (run/'cuda_test.exit_code').write_text(str(p.returncode)); assert p.returncode==0,'CUDA check failed'
        print('ENVIRONMENT_CHECKS_OK'); return
    assert (run/'cuda_test.exit_code').read_text()=='0'
    manifest=json.loads((run/'model_manifest_verified.json').read_text())
    for m in manifest:
        base=ROOT/'cache/huggingface/hub'/('models--'+m['repo'].replace('/','--'))
        assert (base/'refs/main').read_text()==m['revision']
        snap=base/'snapshots'/m['revision']
        for f in m['files']:
            file=snap/f['rfilename']; assert file.stat().st_size==f['size']
        m['actual_snapshot']=str(snap)
    write(run/'model_snapshots.json',manifest)
    write(run/'pre_run_check.json',guard())
    # The sole child that performs model execution is the original upstream script.
    start=time.monotonic()
    with (run/'stdout.log').open('x') as so,(run/'stderr.log').open('x') as se,(run/'gpu_monitor.jsonl').open('x') as mon:
        p=subprocess.Popen(cfg['command'],cwd=str(UP),env=env,stdout=so,stderr=se)
        write(run/'process.json',{'pid':p.pid,'started_at':now()})
        peak=0
        while True:
            try:
                g=gpu(); peak=max(peak,int(g['row'][5])); mon.write(json.dumps(g)+'\n');mon.flush()
            except Exception as exc: mon.write(json.dumps({'monitor_error':type(exc).__name__})+'\n')
            if p.poll() is not None: break
            time.sleep(2)
        rc=p.wait()
    (run/'exit_code.txt').write_text(str(rc))
    write(run/'execution.json',{'exit_code':rc,'finished_at':now(),'wall_time_seconds':time.monotonic()-start,'sampled_peak_gpu_memory_mib':peak})
    write(run/'post_run_gpu.json',gpu())
    print('EXECUTION_EXIT_CODE',rc,flush=True)
if __name__=='__main__': main()
