"""CPU-only bounded controller for evaluator target self-roundtrip."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import csv,datetime,fcntl,hashlib,importlib.util,json,shlex,shutil,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path('/data0/liyanlei/watermark_research');CODE=Path(__file__).resolve().parent
SOURCE=ROOT/'runs/07_prompt_control_20261016T011923Z'
spec=importlib.util.spec_from_file_location('control07',ROOT/'scripts/prompt_control/control.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
read,write,sha,out,now=c.read,c.write,c.sha,c.out,c.now

def total_bytes(run):
    return sum(p.stat().st_size for d in [SOURCE,ROOT/'scripts/prompt_control',run,CODE] for p in d.rglob('*') if p.is_file())
def guard(run):
    g=c.guard()
    p=read(run/'protocol.json')
    assert sha(run/'protocol.json')==(run/'protocol.sha256').read_text().strip()
    assert all(sha(f)==h for f,h in p['code_hashes'].items())
    assert all(sha(f)==h for f,h in p['input_hashes'].items())
    assert total_bytes(run)<10*1024**3
    return g

def prepare():
    assert not list((ROOT/'runs').glob('08_target_roundtrip_*')), 'Inspect existing stage08; no repetition'
    initial=c.guard();oldgroup=read(SOURCE/'group_execution.json')
    assert len(oldgroup['completed'])==6 and not oldgroup['failures']
    run=ROOT/'runs'/('08_target_roundtrip_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));run.mkdir()
    write(run/'preflight.json',initial)
    with (run/'cpu_test.stdout').open('x') as so,(run/'cpu_test.stderr').open('x') as se:
        q=subprocess.run([str(c.PY),str(CODE/'test_workflow.py')],env=c.environment(),stdout=so,stderr=se,timeout=60)
    write(run/'cpu_test.json',dict(exit_code=q.returncode));assert q.returncode==0
    inputs={};cfgs={}
    for seed in [101,102,103]:
        source=SOURCE/f'seed_{seed}_same_prompt'/'evaluator_only';cfg=read(source/'config.json');man=read(source/'tensor_manifest.json')
        selected=[source/'config.json',source/'tensor_manifest.json',Path(man['images']['-1']['path']),
                  Path(man['tensors']['target_original_wm_zT']['path']),Path(man['tensors']['target_inverted_reference_zT']['path'])]
        input_hashes={str(f):sha(f) for f in selected};inputs.update(input_hashes)
        rows=list(csv.DictReader((source/'official_output/target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv').open()))
        reference_ba=float(next(r['bit_accuracy'] for r in rows if int(r['step'])==-1))
        model=cfg['arguments']['modelid_target']
        cfgs[seed]=dict(stage='08',seed=seed,evaluation_only=True,upstream_path=str(c.UP),upstream_commit=c.COMMIT,
            model_id=model,model_revision=cfg['model_revisions'][model],model_snapshot=cfg['model_snapshots'][model],
            gpu_physical_index=0,gpu_uuid=c.UUID,gs_parameters=cfg['gs_parameters'],dtype='float32',
            resolution=512,generation_steps=50,inversion_steps=50,generation_guidance=7.5,inversion_guidance=1.,
            inversion_prompt='',scheduler='DDIM',gs_threshold=.70703125,gs_comparator='>',
            reference_png=man['images']['-1']['path'],original_latent=man['tensors']['target_original_wm_zT']['path'],
            reference_inversion=man['tensors']['target_inverted_reference_zT']['path'],reference_bit_accuracy=reference_ba,
            input_hashes=input_hashes,prompts={arm:read(SOURCE/f'seed_{seed}_{arm}'/'evaluator_only/config.json')['arguments']['attacker_prompt'] for arm in ['same_prompt','changed_prompt']})
    hashes={str(f):sha(f) for f in CODE.glob('*.py')}
    hashes.update({str(c.CODE/'control.py'):sha(c.CODE/'control.py'),str(c.OLD/'stage05.py'):sha(c.OLD/'stage05.py')})
    p=dict(stage='08',created_at=now(),data_role='evaluator_development_control',planned_seeds=[101,102,103],
        planned_model_processes=3,outputs_per_process=2,arms=['same_prompt','changed_prompt'],upstream_commit=c.COMMIT,
        model_snapshots=initial['model_snapshots'],code_hashes=hashes,input_hashes=inputs,
        prior_gpu_process_seconds=oldgroup['cumulative_gpu_process_seconds'],total_limit_seconds=7200,
        per_process_limit_seconds=1200,max_new_bytes=10*1024**3,allowed_gpus=[0,1,2],selected_gpu=0,uuid=c.UUID,
        retries=0,selection_by_target_score=False,geometry_threshold=None,geometry_accepted=None,
        rationale='Compare target self-roundtrip with frozen stage07 proxy roundtrip; same original reference and output prompts',
        reference_check='Recomputed reference inversion must be bitwise equal to saved target inversion before any generation',
        interpretation='Evaluator-only intervention; target internal calls are not attacker permissions',
        planned_contrasts=['target self minus proxy roundtrip cosine by seed and prompt','self-cycle cosine relative to reference inversion'],
        stop_rule='Any engineering/hash/reference-replay/device/budget failure stops group, no retry')
    write(run/'protocol.json',p);c.save_text(run/'protocol.sha256',sha(run/'protocol.json')+'\n')
    for seed,cfg in cfgs.items():
        case=run/f'seed_{seed}';case.mkdir();cfg['protocol_sha256']=sha(run/'protocol.json');write(case/'config.json',cfg)
        command=[str(c.PY),str(CODE/'experiment.py'),str(case)]
        write(case/'command.json',dict(argv=command,config_sha256=sha(case/'config.json')))
        e=c.environment(False);names=['CUDA_VISIBLE_DEVICES','CUDA_DEVICE_ORDER','HF_HOME','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_IMPLICIT_TOKEN','PYTHONDONTWRITEBYTECODE']
        c.save_text(case/'command.sh','cd '+shlex.quote(str(c.UP))+'\n'+' '.join(k+'='+shlex.quote(e[k]) for k in names)+' '+shlex.join(command)+'\n')
    print(run,flush=True)

def execute(run):
    lock=(ROOT/'runs/research_round.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    p=read(run/'protocol.json');assert read(run/'cpu_test.json')['exit_code']==0
    guard(run);write(run/'started.json',dict(at=now(),pid=os.getpid(),protocol_sha256=sha(run/'protocol.json')))
    used=p['prior_gpu_process_seconds'];started=[];completed=[];failures=[]
    for seed in p['planned_seeds']:
        case=run/f'seed_{seed}';child=None;clock=None
        try:
            assert used+1200<=7200
            write(case/'preflight.json',guard(run))
            command=read(case/'command.json');assert sha(case/'config.json')==command['config_sha256']
            clock=time.monotonic();reason=None
            with (case/'stdout.log').open('x') as so,(case/'stderr.log').open('x') as se,(case/'gpu_monitor.jsonl').open('x') as mo:
                child=subprocess.Popen(command['argv'],env=c.environment(False),cwd=c.UP,stdout=so,stderr=se,start_new_session=True)
                started.append(seed);write(case/'process.json',dict(pid=child.pid,started_at=now()))
                print('STARTED seed='+str(seed)+' pid='+str(child.pid),flush=True)
                try:
                    while child.poll() is None:
                        g=c.gpu();mo.write(json.dumps(g)+'\n');mo.flush()
                        assert not any(int(a[1])!=child.pid for a in g['compute_apps']), 'Other compute process'
                        assert time.monotonic()-clock<1200 and used+time.monotonic()-clock<7200,'Timeout'
                        assert total_bytes(run)<10*1024**3 and shutil.disk_usage(ROOT).free>20*1024**3,'Storage limit'
                        time.sleep(2)
                except Exception as exc:reason=str(exc);c.old.terminate_own(child)
                rc=child.wait()
            seconds=time.monotonic()-clock;used+=seconds
            write(case/'execution.json',dict(exit_code=rc,wall_time_seconds=seconds,cumulative_gpu_process_seconds=used,finished_at=now(),failure=reason))
            write(case/'postflight.json',c.gpu())
            assert reason is None and rc==0,reason or ('Exit '+str(rc))
            assert read(case/'reference_replay.json')['bitwise_equal']
            man=read(case/'tensor_manifest.json');assert len(man['arrays'])==3 and len(man['images'])==2
            assert all(sha(r['path'])==r['sha256'] for r in list(man['arrays'].values())+list(man['images'].values()))
            completed.append(seed);print('COMPLETED seed='+str(seed)+' cumulative='+str(round(used,3)),flush=True)
        except Exception as exc:
            if child is not None:c.old.terminate_own(child)
            if clock is not None and not (case/'execution.json').exists():
                seconds=time.monotonic()-clock;used+=seconds
                write(case/'execution.json',dict(exit_code=child.returncode if child else None,wall_time_seconds=seconds,cumulative_gpu_process_seconds=used,failure=str(exc),finished_at=now()))
            fail=dict(seed=seed,error=str(exc),at=now(),traceback=traceback.format_exc());write(case/'failure.json',fail);failures.append(fail);break
    write(run/'group_execution.json',dict(started=started,completed=completed,failures=failures,
        prior_gpu_process_seconds=p['prior_gpu_process_seconds'],stage_gpu_process_seconds=used-p['prior_gpu_process_seconds'],
        cumulative_gpu_process_seconds=used,remaining_gpu_process_seconds=7200-used,finished_at=now(),tracked_new_bytes_total=total_bytes(run)))
    assert all(sha(f)==h for f,h in p['input_hashes'].items())
    print(json.dumps(read(run/'group_execution.json')),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='run':execute(Path(sys.argv[2]))
    else:raise ValueError('prepare or run')
