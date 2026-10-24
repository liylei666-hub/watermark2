import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU supervisor required')
import sys,time,concurrent.futures,threading,shutil
from pathlib import Path
from common31 import c,r,ROOT,HERE,launch,sched,validate_job,candidates
def status(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(__import__('json').dumps(value,indent=2)+'\n');temp.replace(path)
class Runner(launch.ProcessRunner):
    def __init__(self,path):super().__init__(ROOT,path,'',{},{});self.commands={}
    def command(self,job,device,out):return [sys.executable,str(HERE/self.commands[job.name][0])]+list(map(str,self.commands[job.name][1]))+[str(out)]
def run(runtime):
    launch.check_host(ROOT);cfg=r.verify_runtime(runtime);root=ROOT/cfg['run_dir'];private=ROOT/cfg['private_folder'];devices=[sched.Device(**d) for d in cfg['devices']]
    runner=Runner(runtime);finished=[];stop=threading.Event()
    def child(name,entry,args,role,device,marker,phase):
        while True:
            if stop.is_set():raise RuntimeError('Another owned task failed; no new launch')
            samples=[]
            if sched.verify_idle(device,launch.sample,samples.append):break
            status(root/f'gpu{device.index}_waiting.json',dict(state='waiting_resource',task=name,checked_at_utc=sched.now(),samples=samples));time.sleep(30)
        r.verify_runtime(runtime);rolepath=ROOT/cfg['per_device_runtime'][role][str(device.index)]
        if c.sha(rolepath)!=cfg['role_hashes'][role][str(device.index)]:raise ValueError('Role runtime changed')
        out=root/name;out.mkdir();c.write(out/'claim.json',dict(task=name,gpu_uuid=device.uuid,started_at_utc=sched.now()));c.write(out/'supervisor_preflight.json',samples)
        runner.commands[name]=(entry,[rolepath]+args);runner.jobs[name]=dict(watchdog_seconds=9000 if phase=='attack' else 1800,output_limit_bytes=512*1024**2,completion_marker=marker);runner.phases[name]='native_attack' if phase=='attack' else phase
        env=dict(CUDA_VISIBLE_DEVICES=device.uuid,CUDA_DEVICE_ORDER='PCI_BUS_ID',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HOME=str(ROOT/'cache/huggingface'),PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',CUBLAS_WORKSPACE_CONFIG=':4096:8')
        status(root/f'gpu{device.index}_status.json',dict(state='running',task=name,started_at_utc=sched.now()));start=sched.now();outcome=runner(sched.Job(name,c.sha(runtime)),device,out,env)
        c.write(out/'execution.json',dict(started_at_utc=start,outcome=outcome,gpu_index=device.index,gpu_uuid=device.uuid));c.write(out/'execution_seal.json',dict(sha256=c.sha(out/'execution.json')))
        if not outcome['completed']:stop.set();raise RuntimeError('Launched task failed; no retry: '+name)
        finished.append(name);print('CHILD_COMPLETED',name,flush=True)
    with sched.project_lock(ROOT/'runs/.imprint_delivery.lock'):
        if root.exists() or private.exists():raise ValueError('Existing run; no repeated launch')
        used=sum(launch.tree_bytes(ROOT/n) for n in ('runs','reports','scripts','protocols'))+sum(p.stat().st_size for p in ROOT.glob('*.zip'))
        if used+1024**3>10737418240 or shutil.disk_usage(ROOT).free<1024**3:raise ValueError('Storage preflight failed')
        root.mkdir();private.mkdir(mode=0o700);c.write(root/'launch_intent.json',dict(source_commit=cfg['source_commit'],runtime_sha256=c.sha(runtime),controller_pid=os.getpid(),started_at_utc=sched.now(),max_children=2,storage_before_bytes=used));c.write(root/'design.json',cfg['design'])
        try:
            status(root/'scheduler_status.json',dict(state='preparation',completed=finished));child('prepare','prepare31.py',[private],'evaluator',devices[0],'COMPLETED_NATIVE_PREPARE','preparation')
            inputs=root/'attack_inputs';inputs.mkdir()
            for task in cfg['design']['tasks']:
                sid=task['id'];folder=inputs/str(sid);folder.mkdir()
                for kind in ('reference','cover'):
                    with (folder/(kind+'.png')).open('xb') as f:f.write((root/'prepare'/str(sid)/(kind+'.png')).read_bytes())
                job=dict(schema=1,task_id=sid,seed=task['attack_seed'],reference=c.png_record(folder/'reference.png'),cover=c.png_record(folder/'cover.png'),proxy=cfg['design']['proxy'],native=cfg['design']['native'])
                c.write(folder/'job.json',job)
                validate_job(folder/'job.json',r.verify_runtime(ROOT/cfg['per_device_runtime']['attacker']['0']))
            c.write(root/'attack_inputs_sealed.json',{p.relative_to(inputs).as_posix():c.sha(p) for p in sorted(inputs.rglob('*')) if p.is_file()})
            status(root/'scheduler_status.json',dict(state='attacking',completed=finished,assignment={'1':0,'2':1,'3':0,'4':1}))
            def queue(device):
                try:
                    for sid in ([1,3] if device.index==0 else [2,4]):child(f'attack_{sid}','attack31.py',[inputs/str(sid)/'job.json'],'attacker',device,'COMPLETED_NATIVE_ATTACK','attack')
                except BaseException:stop.set();raise
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(queue,d) for d in devices]
                for f in concurrent.futures.as_completed(futures):f.result()
            c.write(root/'candidates_sealed.json',dict(rows=candidates(root),sealed_at_utc=sched.now(),target_scores_seen=0))
            status(root/'scheduler_status.json',dict(state='evaluating',completed=finished));child('evaluate','evaluate31.py',[root,private],'evaluator',devices[0],'COMPLETED_NATIVE_EVAL','evaluation')
            from analyze31 import analyze
            analyze(root,private);c.write(root/'results_sealed.json',dict(analysis_sha256=c.sha(root/'analysis.json'),executions={p.parent.name:c.sha(p) for p in root.glob('*/execution.json')},finished_at_utc=sched.now()));status(root/'scheduler_status.json',dict(state='completed',completed=finished))
        except BaseException as exc:
            stop.set();status(root/'scheduler_status.json',dict(state='stopped',completed=finished,reason=str(exc),retry_allowed=False,checked_at_utc=sched.now()));raise
if __name__=='__main__':run(Path(sys.argv[1]))
