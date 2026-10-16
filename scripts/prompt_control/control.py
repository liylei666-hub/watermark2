"""Fixed paired prompt diagnostic; CPU supervisor, offline single-GPU children."""
import os
assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
import csv, datetime, difflib, fcntl, hashlib, importlib.util, json, shlex
import shutil, signal, statistics, subprocess, sys, time, traceback
from pathlib import Path

ROOT = Path('/data0/liyanlei/watermark_research')
CODE = Path(__file__).resolve().parent
OLD = ROOT / 'scripts/05_seed_pilot_20261013T041252Z'
UP = ROOT / 'third_party/semantic-forgery'
PY = ROOT / 'envs/semantic_forgery_py310/bin/python'
COMMIT = 'ca68950cd7b53b8438a49580f134b2a0db28d778'
UUID = 'GPU-aafaf524-a6f4-f646-a2b5-7d243e80c8a5'
SEEDS = [101, 102, 103]
ARMS = ['same_prompt', 'changed_prompt']
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p, obj):
    with Path(p).open('x', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, indent=2)
def save_text(p, s):
    with Path(p).open('x', encoding='utf-8') as f: f.write(s)
def out(cmd): return subprocess.check_output(cmd, text=True, timeout=30).strip()
spec = importlib.util.spec_from_file_location('historical_control', OLD/'stage05.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

def environment(cpu=True):
    e = os.environ.copy()
    e.update(CUDA_VISIBLE_DEVICES='' if cpu else UUID, CUDA_DEVICE_ORDER='PCI_BUS_ID',
             HF_HOME=str(ROOT/'cache/huggingface'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
             HF_HUB_DISABLE_IMPLICIT_TOKEN='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
             TMPDIR=str(ROOT/'tmp'), MPLCONFIGDIR=str(ROOT/'cache/matplotlib'))
    return e

def gpu():
    raw = out(['nvidia-smi', '-i', '0', '--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu', '--format=csv,noheader,nounits'])
    row = next(csv.reader([raw], skipinitialspace=True))
    apps_raw = out(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader,nounits'])
    apps = [r for r in csv.reader(apps_raw.splitlines(), skipinitialspace=True) if r and r[0] == UUID]
    assert row[:3] == ['0', UUID, 'NVIDIA GeForce RTX 3090'], 'GPU identity mismatch'
    return dict(at=now(), row=row, compute_apps=apps)

def byte_count(run):
    return sum(p.stat().st_size for folder in [run, CODE] for p in folder.rglob('*') if p.is_file())

def guard(run=None):
    g = gpu()
    assert not g['compute_apps'] and int(g['row'][4]) <= 50 and int(g['row'][5]) == 0, 'GPU occupied or unclear'
    assert shutil.disk_usage(ROOT).free > 20*1024**3, 'Less than 20 GiB free'
    assert out(['git','-C',str(UP),'rev-parse','HEAD']) == COMMIT
    assert not out(['git','-C',str(UP),'status','--porcelain']), 'Upstream modified'
    snapshots = old.cache_check()
    if run:
        p = read(run/'protocol.json')
        assert sha(run/'protocol.json') == (run/'protocol.sha256').read_text().strip()
        assert all(sha(f) == h for f,h in p['code_hashes'].items()), 'Frozen code changed'
        assert snapshots == p['model_snapshots']
        assert byte_count(run) < 10*1024**3
    return dict(gpu=g, checked_at=now(), disk_free_bytes=shutil.disk_usage(ROOT).free, model_snapshots=snapshots)

def prepare():
    assert not list((ROOT/'runs').glob('07_prompt_control_*')), 'Inspect existing experiment; do not repeat'
    pre = guard()
    run = ROOT/'runs'/('07_prompt_control_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    run.mkdir(); (run/'preparation').mkdir()
    write(run/'preflight.json', pre)
    protected = {str(p):sha(p) for folder in [ROOT/'runs', ROOT/'reports', OLD, ROOT/'scripts/04_latent_diag_20261013T024856Z']
                 for p in folder.rglob('*') if p.is_file() and not p.is_relative_to(run)}
    write(run/'preparation/protected_hashes.json', protected)
    sources = {}
    for name in ['run_recorded.py','recording.py','diagnostic.py','test_cpu.py']:
        source = (OLD/name).read_text(); data = source; sources[name] = sha(OLD/name)
        if name == 'run_recorded.py':
            assert source.count('GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da') == 1
            data = source.replace('GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da', UUID)
        if name == 'recording.py':
            needle = '        pixels = np.asarray(args_bound["image_to_verify_PIL"]).copy()'
            addition = '''
        if step == 1:
            candidate = recorder.directory / "candidate_before_evaluation.png"
            with candidate.open("xb") as stream:
                args_bound["image_to_verify_PIL"].save(stream, format="PNG")
            write_json(recorder.directory / "candidate_before_evaluation.json", dict(
                path=str(candidate), sha256=sha(candidate), candidate_id=recorder.candidate_id,
                config_sha256=recorder.config_hash, event="before_target_validate"))'''
            assert source.count(needle) == 1
            data = source.replace(needle, needle+addition)
        if name == 'test_cpu.py':
            needle = '    calls["validate"]+=1'
            addition = '''
    if step == 1:
        import json
        from recording import sha
        frozen = json.loads((d / "candidate_before_evaluation.json").read_text())
        assert sha(frozen["path"]) == frozen["sha256"]
        assert np.array_equal(np.asarray(Image.open(frozen["path"])), np.asarray(image_to_verify_PIL))'''
            assert source.count(needle) == 1
            data = source.replace(needle, needle+addition)
        save_text(CODE/name, data)
        save_text(run/'preparation'/(name+'.diff'), ''.join(difflib.unified_diff(source.splitlines(True), data.splitlines(True), fromfile=str(OLD/name), tofile=str(CODE/name))))
    write(run/'preparation/source_hashes.json', sources)
    agents = ROOT/'AGENTS.md'
    save_text(run/'preparation/AGENTS.before.md', agents.read_text())
    note = '\n\n## Resumed research: 2026-10-16\n\nThe user resumed research and authorized physical GPUs 0,1,2 for this round. Use one verified idle device at a time, serial execution. The 7200 GPU-process-second cumulative budget, 1200 seconds per process, 10 GiB new-file limit and no new model downloads remain in force. The fixed three-seed paired prompt diagnostic is development evidence; complete geometry and SemBind evaluation remain blocked on official protocol details. Preserve all historical evidence.\n'
    with agents.open('a', encoding='utf-8') as f: f.write(note)
    write(run/'preparation/authorization.json', dict(at=now(), allowed_gpu_physical_indices=[0,1,2], selected_gpu_physical_index=0,
        selected_gpu_uuid=UUID, cumulative_gpu_seconds_before=0, prior_model_processes_this_round=0,
        source='User resumed research and allowed physical GPUs 0-2; existing first-round budget retained', agents_sha256=sha(agents)))
    base = read(ROOT/'runs/05_reprompt_seed_pilot_20261013T041832Z/seed_2/evaluator_only/config.json')
    p = dict(stage='07', data_role='development_control', created_at=now(), seeds=SEEDS, arms_in_order=ARMS,
        planned_model_processes=6, retries=0, allowed_gpu_physical_indices=[0,1,2], gpu_physical_index=0, gpu_uuid=UUID,
        upstream_commit=COMMIT, model_snapshots=pre['model_snapshots'], model_revisions=base['model_revisions'],
        base_arguments=base['arguments'], gs_parameters=base['gs_parameters'], dtype='float32',
        inversion_prompt='', inversion_guidance=1., resample=False, gs_threshold=.70703125, gs_comparator='>',
        total_gpu_process_seconds_limit=7200, process_timeout_seconds=1200, new_bytes_limit=10*1024**3,
        new_model_downloads=False, serial=True, used_gpu_seconds_before=0,
        geometry_threshold=None, geometry_accepted=None, full_official_geometry_evaluation_completed=False,
        same_prompt_role='Controller-defined prompt control; original target prompt is not assumed attacker-visible',
        paired_identity_rule='reference PNG, original target latent, reference inversion hashes must match across arms',
        primary_contrasts=['same-minus-changed cosine','same-minus-changed coordinate sign agreement','same-minus-changed magnitude cosine'],
        scientific_stop_rule='Never select by scores; keep all planned observations',
        engineering_stop_rule='Stop group on failure, timeout, device conflict, budget or paired-identity failure; no retries',
        permission_isolation_implemented=False, selection_by_target_scores=False,
        candidate_freeze='PNG and SHA256 before target validation; official saved candidate must hash-match',
        upstream_public_heads={'geometry':'72880c9bb1cee0b04bcb2433deb2ab2cc95ff622','sembind':'337c9f90a150157ac1d410208ae20e6530ca8cdd'},
        code_hashes={str(f):sha(f) for f in sorted(CODE.glob('*.py'))} | {str(OLD/'stage05.py'):sha(OLD/'stage05.py')})
    write(run/'protocol.json', p); save_text(run/'protocol.sha256', sha(run/'protocol.json')+'\n')
    for seed in SEEDS:
        for arm in ARMS:
            d = run/f'seed_{seed}_{arm}'/'evaluator_only'; d.mkdir(parents=True)
            cfg = json.loads(json.dumps(base)); cfg.update(stage='07',data_role='development_control',
                gpu_physical_index=0,gpu_uuid=UUID,reference_id=f'control_{seed}_reference',candidate_id=f'control_{seed}_{arm}',
                protocol_sha256=sha(run/'protocol.json'),recording_code_sha256=sha(CODE/'run_recorded.py'))
            cfg['arguments']['seed'] = seed
            if arm == 'same_prompt': cfg['arguments']['attacker_prompt'] = cfg['arguments']['target_prompt']
            write(d/'config.json',cfg); save_text(d/'config.sha256',sha(d/'config.json')+'\n')
            cmd = [str(PY),str(CODE/'run_recorded.py'),str(d.parent)]
            write(d/'commands.json',dict(model=cmd,diagnostic=[str(PY),str(CODE/'diagnostic.py'),str(d.parent)]))
            exports = {k:environment(False)[k] for k in ['CUDA_DEVICE_ORDER','CUDA_VISIBLE_DEVICES','HF_HOME','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_IMPLICIT_TOKEN','PYTHONDONTWRITEBYTECODE','TMPDIR','MPLCONFIGDIR']}
            save_text(d/'command.sh','cd '+shlex.quote(str(UP))+'\n'+ ' '.join(k+'='+shlex.quote(v) for k,v in exports.items())+' '+shlex.join(cmd)+'\n')
    with (run/'preparation/cpu_tests.stdout').open('x') as so, (run/'preparation/cpu_tests.stderr').open('x') as se:
        result = subprocess.run([str(PY),str(CODE/'test_cpu.py'),str(run/'preparation/mock')],env=environment(),stdout=so,stderr=se,timeout=60)
    write(run/'preparation/cpu_tests_exit.json',dict(exit_code=result.returncode))
    assert result.returncode == 0, 'CPU mocks failed'
    # The only algorithm argument difference inside a pair must be the output prompt.
    for seed in SEEDS:
        a,b = [read(run/f'seed_{seed}_{arm}'/'evaluator_only/config.json')['arguments'] for arm in ARMS]
        assert {k for k in a if a[k]!=b[k]} == {'attacker_prompt'}
        assert a['seed'] == b['seed'] == seed
    write(run/'preparation/parameter_tests.json',dict(passed=True,seeds=SEEDS,arms=ARMS,allowed_argument_difference=['attacker_prompt']))
    print(run, flush=True)

def validate(run, protocol):
    man = old.validate_artifacts(run, protocol)
    d = run/'evaluator_only'
    pre = read(d/'candidate_before_evaluation.json')
    assert pre['event']=='before_target_validate'
    assert sha(pre['path']) == pre['sha256'] == man['images']['1']['sha256']
    assert read(d/'device.json')['uuid'] == UUID
    return man

def paired(run,seed,p):
    a,b = [validate(run/f'seed_{seed}_{arm}',p) for arm in ARMS]
    assert a['images']['-1']['sha256'] == b['images']['-1']['sha256'], 'Paired reference mismatch'
    for key in ['target_original_wm_zT','target_inverted_reference_zT']:
        assert a['tensors'][key]['sha256'] == b['tensors'][key]['sha256'], 'Paired target tensor mismatch'

def execute(run):
    lock = (ROOT/'runs/research_round.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    p = read(run/'protocol.json')
    assert read(run/'preparation/cpu_tests.json')['passed']
    assert read(run/'preparation/parameter_tests.json')['passed']
    guard(run)
    write(run/'started.json',dict(at=now(),pid=os.getpid(),protocol_sha256=sha(run/'protocol.json')))
    used = p['used_gpu_seconds_before']; started=[]; completed=[]; failures=[]
    for seed in SEEDS:
        for arm in ARMS:
            case = run/f'seed_{seed}_{arm}'; d=case/'evaluator_only'; child=None; clock=None
            try:
                assert used + 1200 <= 7200, 'Insufficient remaining worst-case process budget'
                write(case/'pre_run_gpu.json',guard(run))
                assert sha(d/'config.json')==(d/'config.sha256').read_text().strip()
                command=read(d/'commands.json')['model']
                write(case/'launch.json',dict(at=now(),command=command,config_sha256=sha(d/'config.json')))
                clock=time.monotonic(); reason=None
                with (d/'stdout.log').open('x') as so,(d/'stderr.log').open('x') as se,(case/'monitor.jsonl').open('x') as mo:
                    child=subprocess.Popen(command,cwd=UP,env=environment(False),stdout=so,stderr=se,start_new_session=True)
                    started.append(case.name)
                    write(case/'process.json',dict(pid=child.pid,started_at=now()))
                    print('STARTED '+case.name+' pid='+str(child.pid),flush=True)
                    try:
                        while child.poll() is None:
                            g=gpu(); mo.write(json.dumps(g)+'\n');mo.flush()
                            assert not any(int(a[1])!=child.pid for a in g['compute_apps']), 'Another compute task appeared'
                            assert time.monotonic()-clock < 1200, 'Process timeout'
                            assert used+time.monotonic()-clock < 7200, 'Round timeout'
                            assert byte_count(run)<10*1024**3, 'File budget exceeded'
                            assert shutil.disk_usage(ROOT).free>20*1024**3, 'Low disk space'
                            time.sleep(2)
                    except Exception as exc:
                        reason=str(exc);old.terminate_own(child)
                    rc=child.wait()
                elapsed=time.monotonic()-clock;used+=elapsed
                write(case/'execution.json',dict(exit_code=rc,wall_time_seconds=elapsed,cumulative_gpu_process_seconds=used,
                    finished_at=now(),engineering_failure=reason,process_exited=True))
                save_text(case/'exit_code.txt',str(rc)+'\n');write(case/'post_run_gpu.json',gpu())
                assert reason is None and rc==0, reason or ('Exit '+str(rc))
                validate(case,p)
                with (d/'diagnostic.stdout').open('x') as so,(d/'diagnostic.stderr').open('x') as se:
                    cpu=subprocess.run(read(d/'commands.json')['diagnostic'],env=environment(),stdout=so,stderr=se,timeout=60)
                write(d/'diagnostic_exit.json',dict(exit_code=cpu.returncode));assert cpu.returncode==0
                if arm=='changed_prompt': paired(run,seed,p)
                completed.append(case.name)
                print('COMPLETED '+case.name+' GPU_SECONDS='+str(round(used,3)),flush=True)
            except Exception as exc:
                if child is not None: old.terminate_own(child)
                if clock is not None and not (case/'execution.json').exists():
                    elapsed=time.monotonic()-clock;used+=elapsed
                    write(case/'execution.json',dict(exit_code=child.returncode if child else None,wall_time_seconds=elapsed,
                        cumulative_gpu_process_seconds=used,finished_at=now(),engineering_failure=str(exc)))
                fail=dict(case=case.name,at=now(),error=str(exc),traceback=traceback.format_exc())
                write(case/'failure.json',fail);failures.append(fail);break
        if failures: break
    write(run/'group_execution.json',dict(started=started,completed=completed,failures=failures,
        cumulative_gpu_process_seconds=used,remaining_gpu_process_seconds=7200-used,finished_at=now(),new_bytes=byte_count(run)))
    protected=read(run/'preparation/protected_hashes.json')
    changed=[f for f,h in protected.items() if sha(f)!=h]
    write(run/'historical_integrity.json',dict(checked=len(protected),changed=changed))
    assert not changed
    print(json.dumps(read(run/'group_execution.json')),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='prepare': prepare()
    elif sys.argv[1]=='run': execute(Path(sys.argv[2]))
    else: raise ValueError('prepare or run')
