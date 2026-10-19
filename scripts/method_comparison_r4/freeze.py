"""CPU packaging of the continuation; execute once in the verified local publication checkout."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import datetime,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];REMOTE='/data0/liyanlei/watermark_research'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):
    with p.open('xb') as f:f.write((json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())

def main():
    original=read(ROOT/'protocols/27_method_runtime_r2.json');source=ROOT/original['run_dir']
    manifest=read(ROOT/'reports/27_method_comparison/stopped_artifacts.json')['files']
    source_files={}
    for entry in manifest:
        path=ROOT/entry['path']
        if path.is_relative_to(source):
            if sha(path)!=entry['sha256']:raise ValueError('Stopped evidence changed')
            source_files[path.relative_to(source).as_posix()]=entry['sha256']
    inherited=dict(completed={},failed={});historical=dict(original['historical_execution_hashes'])
    for p in source.rglob('execution.json'):
        x=read(p);name=p.parent.relative_to(source).as_posix();record=dict(path=p.parent.relative_to(ROOT).as_posix(),sha256=sha(p));historical[p.relative_to(ROOT).as_posix()]=sha(p)
        inherited['completed' if x['completed'] and x['exit_code']==0 else 'failed'][name]=record
    if len(inherited['completed'])!=9 or set(inherited['failed'])!={'attack_outputs/2/jain'} or len(historical)!=70:raise ValueError('Unexpected source launch inventory')
    skip={'execution.json','process.json','command.json','preflight.jsonl','device_preimport.json','stdout.log','stderr.log'}
    copied={}
    for rel,h in source_files.items():
        p=Path(rel)
        if rel in ('design.json','attack_plan.json','attack_plan_frozen.json') or p.parts[0]=='attack_inputs':copied[rel]=h
        elif any(rel.startswith(name+'/') for name in inherited['completed']) and p.name not in skip:copied[rel]=h
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    code=dict(original['code_hashes'])
    for p in Path(__file__).parent.glob('*.py'):code[REMOTE+'/'+p.relative_to(ROOT).as_posix()]=sha(p)
    cfg=dict(original,run_dir='runs/27_method_resume_'+stamp,source_run=original['run_dir'],source_files=source_files,copied_files=copied,inheritance=inherited,historical_execution_hashes=historical,code_hashes=code,
        private_folder='private_eval/'+source.name,prelaunch_revision=4,resource_recheck_seconds=300,
        continuation_policy='Reuse verified completed artifacts; preserve launched failure; start only never-launched tasks; wait for resources.',
        numerical_algorithm_changed=False,new_model_processes=35,target_inversions=59,failed_task_preserved='attack_outputs/2/jain',
        superseded_operational_rule='User 2026-10-20 replaces device_unavailable_policy with waiting_resource; frozen scientific decision rules remain unchanged.')
    attack=read(ROOT/'protocols/27_method_attack_runtime_r2.json');attack.update(code_hashes=code,prelaunch_revision=4)
    evaluation=read(ROOT/'protocols/27_method_eval_runtime_r2.json');evaluation.update(code_hashes=code,prelaunch_revision=4)
    for name,value in [('runtime',cfg),('attack_runtime',attack),('eval_runtime',evaluation)]:
        p=ROOT/('protocols/27_method_'+name+'_r4.json');write(p,value)
        with p.with_suffix('.sha256').open('x') as f:f.write(sha(p)+'\n')
    print(json.dumps(dict(run_dir=cfg['run_dir'],source_files=len(source_files),copied_files=len(copied),historical_executions=len(historical),runtime_sha256=sha(ROOT/'protocols/27_method_runtime_r4.json')),indent=2))

if __name__=='__main__':main()
