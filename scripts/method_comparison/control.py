"""Execute the complete frozen method comparison serially under the shared experiment lock."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU supervisor requires empty visibility')
import datetime,fcntl,sys
from pathlib import Path
from common import c,r,METHODS,IDS,PARAMETERS,module,copy,validate_job,delivery,verify_delivery

RUNTIME=r.ROOT/'protocols/27_method_runtime.json'
ATTACK=r.ROOT/'protocols/27_method_attack_runtime.json'
EVAL=r.ROOT/'protocols/27_method_eval_runtime.json'

def main():
    cfg=r.verify_runtime(RUNTIME);root=r.ROOT/cfg['run_dir'];design=cfg['design']
    with (r.ROOT/'runs/.imprint_delivery.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        actual={p.relative_to(r.ROOT).as_posix():c.sha(p) for p in (r.ROOT/'runs').rglob('execution.json')
                if p.relative_to(r.ROOT/'runs').parts[0][:2].isdigit() and int(p.relative_to(r.ROOT/'runs').parts[0][:2])>=7}
        if actual!=cfg['historical_execution_hashes']:raise ValueError('Execution inventory changed')
        if list((r.ROOT/'runs').glob('27_method_comparison_*/launch_intent.json')):raise RuntimeError('Comparison already attempted')
        root.mkdir();private=r.ROOT/'private_eval'/root.name;private.mkdir(mode=0o700)
        c.write(root/'launch_intent.json',dict(stage='27',runtime_sha256=c.sha(RUNTIME),planned_model_processes=45,controller_pid=os.getpid()))
        c.write(root/'design.json',design);print('RUN_DIR '+str(root),flush=True)
        runner=module('stage27_launch',r.ROOT/'scripts/cover_pilot/control.py')
        runner.SCRIPTS=r.ROOT/'scripts/method_comparison';runner.RUNTIME=RUNTIME;runner.ATTACK_RUNTIME=ATTACK
        # Preparation/evaluation use evaluator runtime; global runtime verification retains supervisor pins.
        original_child=runner.run_child
        def child(name,script,args):
            # run_child uses its global RUNTIME for both verification and evaluator dispatch.
            runner.RUNTIME=EVAL if script!='attack.py' else RUNTIME
            r.verify_runtime(RUNTIME)
            return original_child(name,script,args,root,cfg)
        try:
            for role in ('reference','cover'):
                for batch in range(3):child(role+'_'+str(batch),'prepare.py',[role,batch,private])
            jobs=[];identities=[]
            for task in design['tasks']:
                sid=task['task_id'];folder=root/'attack_inputs'/str(sid);folder.mkdir(parents=True)
                for role in ('reference','cover'):
                    source=root/(role+'_'+str((sid-1)//4))/str(sid)
                    record=c.read(source/'record.json')
                    if record['seed']!=task[role+'_seed'] or record['prompt']!=task[role+'_prompt'] or record['image']!=c.png_record(source/(role+'.png')):raise ValueError('Preparation association changed')
                    copy(source/(role+'.png'),folder/(role+'.png'))
                    if role=='reference':identities.append(record['encryption_fingerprints'])
                for method in METHODS:
                    job=dict(version=1,task_id=sid,method=method,seed=task['attack_seed'],reference=c.png_record(folder/'reference.png'),
                             cover=c.png_record(folder/'cover.png'),proxy=design['proxy'],parameters=PARAMETERS[method])
                    path=folder/(method+'.json');c.write(path,job);validate_job(path)
                    jobs.append(dict(task_id=sid,method=method,path=path.relative_to(root).as_posix(),sha256=c.sha(path)))
            if any(len({x[k] for x in identities})!=12 for k in ('message','key','nonce')):raise ValueError('Repeated GS identity')
            c.write(root/'attack_plan.json',dict(jobs=jobs));plan_sha=c.sha(root/'attack_plan.json')
            c.write(root/'attack_plan_frozen.json',dict(sha256=plan_sha))
            for sid in IDS:
                # Rotate order by task to reduce method/order confounding; never inspect target scores.
                order=METHODS[(sid-1)%3:]+METHODS[:(sid-1)%3]
                for method in order:
                    job=next(j for j in jobs if j['task_id']==sid and j['method']==method)
                    if c.sha(root/job['path'])!=job['sha256']:raise ValueError('Frozen job changed')
                    child('attack_outputs/'+str(sid)+'/'+method,'attack.py',[root/job['path']])
            if c.sha(root/'attack_plan.json')!=plan_sha:raise ValueError('Plan changed')
            c.write(root/'delivery_sealed.json',dict(delivery=delivery(root),sealed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),target_detection_calls_before_seal=0))
            for batch in range(3):child('evaluate_'+str(batch),'evaluate.py',[root,batch,private])
            verify_delivery(root);r.verify_runtime(RUNTIME)
            c.write(root/'status.json',dict(completed=True,model_processes_started=45,candidates=36,target_inversions=60,
                      feedback_to_attack=False,private_material_published=False,full_defense_acceptance=None))
        except BaseException as exc:
            c.write(root/'status.json',dict(completed=False,error_type=type(exc).__name__,reason=str(exc),
                      model_processes_started=len(list(root.rglob('process.json'))),unchanged_retry_allowed=False))
            raise
    print('COMPLETED_METHOD_COMPARISON',flush=True)

if __name__=='__main__':
    if sys.argv[1:]!=['--run']:raise SystemExit('Explicit --run required')
    main()
