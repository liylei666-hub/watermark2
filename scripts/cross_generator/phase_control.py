"""Six serial stage24 test children followed by sealed CPU prediction and evaluation."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':raise SystemExit('CPU supervisor requires empty visibility')
import datetime,fcntl,importlib.util,json,signal,subprocess,sys,time
from pathlib import Path
import io_contract as c
from source_worker import r
from phase_contract import verify_source, export_images, SOURCE_FIT, seal_predictions, verify_predictions
from predict_fixed import main as predict

PYTHON=r.ROOT/'envs/semantic_forgery_py310/bin/python'
SCRIPTS=r.ROOT/'scripts/cross_generator'
RUNTIME=r.ROOT/'protocols/24_cross_generator_test_runtime.json'
PROXY_RUNTIME=r.ROOT/'protocols/24_cross_generator_test_proxy_runtime.json'
SOURCE=r.ROOT/'runs/24_cross_generator_20261018T044821Z'


def child(name,script,args,folder,cfg):
    out=folder/name;out.mkdir()
    spec=importlib.util.spec_from_file_location('idle_gate',r.ROOT/'scripts/gpu_preflight.py')
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate);chosen=None
    with (out/'preflight.jsonl').open('x') as stream:
        def record(value):stream.write(json.dumps(value)+'\n');stream.flush();os.fsync(stream.fileno())
        for index,uuid in cfg['allowed_gpu_uuids'].items():
            try:gate.verify_idle(gate.snapshot,record,int(index),uuid,'NVIDIA GeForce RTX 3090');chosen=(index,uuid);break
            except Exception as exc:record(dict(event='device_unavailable',index=index,reason=str(exc)))
    if chosen is None:raise RuntimeError('No idle authorized device')
    total=sum(p.stat().st_size for name in ['runs','reports','scripts','protocols','private_eval'] for p in (r.ROOT/name).rglob('*') if p.is_file())
    group=sum(p.stat().st_size for p in SOURCE.rglob('*') if p.is_file())
    if total+512*1024**2>=cfg['max_new_bytes'] or group+32*1024**2>=cfg['max_group_new_bytes']:raise RuntimeError('Storage gate failed')
    r.verify_runtime(RUNTIME);verify_source(SOURCE)
    runtime=PROXY_RUNTIME if script=='invert_test_images.py' else RUNTIME
    env=dict(os.environ,CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES=chosen[1],HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HOME=str(r.ROOT/'cache/huggingface'),
        PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    command=[str(PYTHON),str(SCRIPTS/script),str(runtime)]+list(map(str,args))+[str(out)]
    c.write(out/'command.json',dict(argv=command,runtime_sha256=c.sha(runtime),gpu_index=int(chosen[0]),gpu_uuid=chosen[1],watchdog_seconds=1200))
    start=time.monotonic();at=datetime.datetime.now(datetime.timezone.utc).isoformat();timed_out=False
    with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
        proc=subprocess.Popen(command,env=env,cwd=r.ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
        c.write(out/'process.json',dict(pid=proc.pid,started_at_utc=at))
        try:code=proc.wait(timeout=1200)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(proc.pid,signal.SIGTERM)
            try:code=proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);code=proc.wait()
    marker='COMPLETED_GS_BATCH' if script=='gs_batch.py' else 'COMPLETED_TEST_INVERSION'
    complete=code==0 and not timed_out and (out/'summary.json').exists() and marker in (out/'stdout.log').read_text()
    if complete:complete=c.read(out/'summary.json').get('completed') is True
    elapsed=time.monotonic()-start
    c.write(out/'execution.json',dict(exit_code=code,timed_out=timed_out,elapsed_seconds=elapsed,started_at_utc=at,
            completed=complete,model_processes_started=1,gpu_index=int(chosen[0]),gpu_uuid=chosen[1]))
    print(json.dumps(dict(child=name,completed=complete,elapsed_seconds=elapsed)),flush=True)
    if not complete:raise RuntimeError('Test child failed: '+name)


def main():
    cfg=r.verify_runtime(RUNTIME)
    with (r.ROOT/'runs/.imprint_delivery.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);verify_source(SOURCE)
        actual={p.relative_to(r.ROOT).as_posix():c.sha(p) for p in (r.ROOT/'runs').rglob('execution.json')
                if p.relative_to(r.ROOT/'runs').parts[0][:2].isdigit() and int(p.relative_to(r.ROOT/'runs').parts[0][:2])>=7}
        if actual!=cfg['historical_execution_hashes']:raise ValueError('Execution inventory changed')
        folder=SOURCE/'tests';folder.mkdir()
        c.write(folder/'launch_intent.json',dict(stage='24',phase='test',runtime_sha256=c.sha(RUNTIME),planned_model_processes=6,controller_pid=os.getpid()))
        private=r.ROOT/'private_eval'/(SOURCE.name+'_tests');private.mkdir(mode=0o700)
        print('TEST_DIR '+str(folder),flush=True)
        try:
            for job in cfg['jobs']:
                path=r.ROOT/job['path'];child(job['name'],'gs_batch.py',[path,job['sha256'],private],folder,cfg)
            proxy_entries={};image_paths={}
            for split,prefix in [('proxy_test','proxy'),('target_test','target')]:
                for i,sid in enumerate(c.SPLITS[split]):
                    source=folder/(prefix+'_generate_'+str(i//4))/sid;record=c.read(source/'record.json')
                    if record['task']['sample_id']!=sid or c.png_record(source/'reference.png')!=record['image']:raise ValueError('Reference association changed')
                    if split=='proxy_test':
                        if c.array_record(source/'estimate.npy')!=record['estimate']:raise ValueError('Proxy inverse changed')
                        proxy_entries[sid]={'estimate':source/'estimate.npy'}
                    else:image_paths[sid]=source/'reference.png'
            images_sha=export_images(folder/'target_images',image_paths)
            for batch in (0,1):child('target_inverse_'+str(batch),'invert_test_images.py',[folder/'target_images',images_sha,batch],folder,cfg)
            target_entries={}
            for i,sid in enumerate(c.SPLITS['target_test']):
                out=folder/('target_inverse_'+str(i//4));summary=c.read(out/'summary.json');row=summary['rows'][i%4]
                if row['sample_id']!=sid or row['image_sha256']!=c.sha(image_paths[sid]):raise ValueError('Inverse image association changed')
                if c.array_record(out/sid/'estimate.npy')!=row['estimate']:raise ValueError('Inverse tensor changed')
                target_entries[sid]={'estimate':out/sid/'estimate.npy'}
            started=time.perf_counter()
            for split,entries in [('proxy_test',proxy_entries),('target_test',target_entries)]:
                inputs=folder/(split+'_inputs');digest=c.export_bundle(inputs,split,entries)
                predict(SOURCE/'source_fit',SOURCE_FIT,inputs,split,digest,folder/(split+'_predictions'))
            seal_sha=seal_predictions(folder)
            c.write(folder/'prediction_cpu_execution.json',dict(completed=True,elapsed_seconds=time.perf_counter()-started,model_processes_started=0))
            r.verify_runtime(RUNTIME)
            from evaluate_tests import main as evaluate
            evaluate(folder,seal_sha,private,folder/'evaluation.json')
            verify_predictions(folder,seal_sha);verify_source(SOURCE)
            c.write(folder/'status.json',dict(completed=True,model_processes_started=6,gs_test_images=16,
                    prediction_seal_sha256=seal_sha,full_defense_acceptance=None,attack_success_rate=None))
        except BaseException as exc:
            c.write(folder/'status.json',dict(completed=False,error_type=type(exc).__name__,reason=str(exc),
                    model_processes_started=len(list(folder.rglob('process.json'))),unchanged_retry_allowed=False))
            raise
    print('COMPLETED_STAGE24_TESTS',flush=True)


if __name__=='__main__':
    if sys.argv[1:]!=['--run']:raise SystemExit('Explicit --run required')
    main()
