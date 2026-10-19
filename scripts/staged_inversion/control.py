"""Single-card bounded pilot; no retries, no four-card scale-up and no model polling service."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('Supervisor requires empty CUDA visibility')
import json,sys,time
from pathlib import Path
from common import c,r,launch,sched,ROOT,BASE,METHODS,schedule,validate_job,seal_rows,verify_seal


def atomic(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)


class PilotRunner(launch.ProcessRunner):
    def __init__(self,cfg,runtime_paths):
        super().__init__(ROOT,runtime_paths['controller'],'',{}, {})
        self.cfg=cfg;self.runtime_paths=runtime_paths;self.commands={}
    def command(self,job,device,output):
        script,args,role=self.commands[job.name]
        return [sys.executable,str(BASE/'staged_inversion'/script),str(self.runtime_paths[role])]+list(map(str,args))+[str(output)]


def run(runtime_path):
    launch.check_host(ROOT);cfg=r.verify_runtime(runtime_path);device=sched.Device(**cfg['device'])
    # First model validation uses exactly one GPU. Existing jobs hold the same lock.
    sched.validate((device,),(sched.Group('a',(sched.Job('a','0'*64),)),),(sched.Group('b',(sched.Job('b','0'*64),)),))
    root=c.inside(ROOT,cfg['run_dir']);private=c.inside(ROOT,cfg['private_folder'])
    paths={role:ROOT/path for role,path in cfg['runtime_paths'].items()}
    for role,digest in cfg['runtime_sha256'].items():
        if c.sha(paths[role])!=digest:raise ValueError('Role runtime changed')
    runner=PilotRunner(cfg,paths);finished=[]
    with sched.project_lock(ROOT/'runs/.imprint_delivery.lock'):
        if root.exists() or private.exists():raise ValueError('Existing pilot or private directory; no retry')
        used=sum(launch.tree_bytes(ROOT/name) for name in ('runs','reports','scripts','protocols'))
        if used+2*1024**3>cfg['max_new_bytes']:raise ValueError('Storage reservation exceeds 10 GiB')
        root.mkdir();private.mkdir(mode=0o700)
        c.write(root/'launch_intent.json',dict(runtime_sha256=c.sha(runtime_path),controller_pid=os.getpid(),
            source_commit=cfg['source_commit'],started_at_utc=sched.now(),max_concurrent_children=1))
        c.write(root/'design.json',cfg['design'])
        def child(name,script,args,role,phase,marker):
            records=[]
            if not sched.verify_idle(device,launch.sample,records.append):raise RuntimeError('Device busy before claim')
            r.verify_runtime(runtime_path)
            if c.sha(paths[role])!=cfg['runtime_sha256'][role]:raise ValueError('Role runtime changed before child')
            output=root/name;output.mkdir()
            c.write(output/'claim.json',dict(name=name,phase=phase,runtime_sha256=c.sha(runtime_path),gpu_uuid=device.uuid))
            c.write(output/'supervisor_preflight.json',records)
            runner.jobs[name]=dict(watchdog_seconds=cfg['watchdog_seconds'],output_limit_bytes=128*1024**2,completion_marker=marker)
            runner.phases[name]=phase;runner.commands[name]=(script,args,role)
            env=dict(CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES=device.uuid,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HOME=str(ROOT/'cache/huggingface'),PYTHONDONTWRITEBYTECODE='1',
                TOKENIZERS_PARALLELISM='false',CUBLAS_WORKSPACE_CONFIG=':4096:8')
            atomic(root/'scheduler_status.json',dict(state='running',task=name,completed=finished,started_at_utc=sched.now()))
            start=sched.now();outcome=runner(sched.Job(name,c.sha(runtime_path)),device,output,env)
            c.write(output/'execution.json',dict(started_at_utc=start,outcome=outcome,gpu_index=device.index,gpu_uuid=device.uuid))
            c.write(output/'execution_seal.json',dict(sha256=c.sha(output/'execution.json')))
            if not outcome['completed']:raise RuntimeError('Child failed; retain all evidence and stop: '+name)
            finished.append(name);print('CHILD_COMPLETED',name,flush=True)
        try:
            for role in ('reference','cover'):
                child('prepare_'+role,'prepare.py',[role,private],'evaluator','preparation','COMPLETED_STAGED_PREPARATION')
            attack_cfg=r.verify_runtime(paths['attacker'])
            inputs=root/'attack_inputs';inputs.mkdir()
            for task in cfg['design']['tasks']:
                sid=task['task_id'];folder=inputs/str(sid);folder.mkdir()
                for kind in ('reference','cover'):
                    with (folder/(kind+'.png')).open('xb') as stream:stream.write((root/('prepare_'+kind)/str(sid)/(kind+'.png')).read_bytes())
                for method in METHODS:
                    job=dict(schema=1,task_id=sid,method=method,seed=task['attack_seed'],proxy=cfg['design']['proxy'],
                        reference=c.png_record(folder/'reference.png'),cover=c.png_record(folder/'cover.png'),
                        schedule=schedule(method),learning_rate=.01)
                    c.write(folder/(method+'.json'),job);validate_job(folder/(method+'.json'),attack_cfg)
            c.write(root/'attack_inputs_sealed.json',{p.relative_to(inputs).as_posix():c.sha(p) for p in sorted(inputs.rglob('*')) if p.is_file()})
            for task in cfg['design']['tasks']:
                sid=task['task_id'];order=METHODS[(sid-1)%3:]+METHODS[:(sid-1)%3]
                for method in order:
                    child(f'attack_{sid}_{method}','attack.py',[inputs/str(sid)/(method+'.json')],
                          'attacker','attack','COMPLETED_STAGED_ATTACK')
            c.write(root/'candidates_sealed.json',dict(rows=seal_rows(root),sealed_at_utc=sched.now(),target_scores_seen_before_seal=0))
            child('evaluate','evaluate.py',[root,private],'evaluator','evaluation','COMPLETED_STAGED_EVALUATION')
            verify_seal(root)
            from analyze import analyze
            result=analyze(root,cfg,private)
            r.verify_runtime(runtime_path)
            c.write(root/'results_sealed.json',dict(analysis_sha256=c.sha(root/'analysis.json'),
                executions={p.parent.name:c.sha(p) for p in sorted(root.glob('*/execution.json'))},finished_at_utc=sched.now()))
            atomic(root/'scheduler_status.json',dict(state='completed',completed=finished,decision=result['decision']['decision'],finished_at_utc=sched.now()))
        except BaseException as exc:
            atomic(root/'scheduler_status.json',dict(state='stopped',completed=finished,error_type=type(exc).__name__,reason=str(exc),
                retry_allowed=False,checked_at_utc=sched.now()));raise
    print('COMPLETED_STAGED_PILOT',flush=True)


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--run':raise SystemExit('Expected --run frozen_runtime.json')
    run(Path(sys.argv[2]))
