"""Serial stage25 controller; all outputs sealed before the first target call."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU supervisor requires empty visibility')
import datetime,fcntl,importlib.util,signal,subprocess,sys,time
from pathlib import Path
import numpy as np
from common import c,r,IDS,METHODS,tasks,cast_input,seal_bundle,bundle,summary

SCRIPTS=r.ROOT/'scripts/delivery_transfer'
RUNTIME=r.ROOT/'protocols/25_delivery_runtime.json'
PYTHON=r.ROOT/'envs/semantic_forgery_py310/bin/python'


def copy_checked(source,target,expected):
    source=Path(source)
    if source.is_symlink() or c.sha(source)!=expected:raise ValueError('Source changed')
    with Path(target).open('xb') as stream:stream.write(source.read_bytes())
    if c.sha(target)!=expected:raise ValueError('Copy integrity failed')


def prepare(folder,cfg):
    inputs=folder/'attack_inputs';inputs.mkdir();casts=[]
    for sid in IDS:
        for method in METHODS:
            source=cfg['inputs'][sid][method];path=r.ROOT/source['path']
            if c.array_record(path,source['dtype'])['sha256']!=source['sha256']:raise ValueError('Frozen latent changed')
            value=np.load(path,allow_pickle=False);cast=cast_input(value)
            record=c.save_array(inputs/(sid+'_'+method+'.npy'),cast,'float32')
            casts.append(dict(sample_id=sid,method=method,source_sha256=source['sha256'],source_dtype=source['dtype'],
                input=record,sign_changes=int(np.sum((value>=0)!=(cast>=0))),max_abs_cast_error=float(np.max(np.abs(value.astype('float64')-cast.astype('float64'))))))
    digest=seal_bundle(inputs,'attack_inputs');c.write(folder/'conversion.json',dict(rows=casts,input_seal_sha256=digest))
    return digest


def child(name,script,runtime,args,folder,cfg):
    out=folder/name;out.mkdir();r.verify_runtime(RUNTIME)
    spec=importlib.util.spec_from_file_location('idle_gate',r.ROOT/'scripts/gpu_preflight.py')
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate);chosen=None
    with (out/'preflight.jsonl').open('x') as stream:
        def record(value):stream.write(__import__('json').dumps(value)+'\n');stream.flush();os.fsync(stream.fileno())
        for index,uuid in cfg['allowed_gpu_uuids'].items():
            try:gate.verify_idle(gate.snapshot,record,int(index),uuid,'NVIDIA GeForce RTX 3090');chosen=(index,uuid);break
            except Exception as exc:record(dict(event='device_unavailable',index=index,reason=str(exc)))
    if chosen is None:raise RuntimeError('No idle authorized GPU')
    total=sum(p.stat().st_size for name in ['runs','reports','scripts','protocols','private_eval'] for p in (r.ROOT/name).rglob('*') if p.is_file())
    group=sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
    if total+512*1024**2>=cfg['max_new_bytes'] or group+32*1024**2>=cfg['max_group_new_bytes']:raise RuntimeError('Storage gate failed')
    env=dict(os.environ,CUDA_DEVICE_ORDER='PCI_BUS_ID',CUDA_VISIBLE_DEVICES=chosen[1],HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HOME=str(r.ROOT/'cache/huggingface'),PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',CUBLAS_WORKSPACE_CONFIG=':4096:8')
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
    marker='COMPLETED_DELIVERY_GENERATION' if script=='generate.py' else 'COMPLETED_DELIVERY_EVALUATION'
    complete=code==0 and not timed_out and (out/'summary.json').exists() and marker in (out/'stdout.log').read_text()
    if complete:complete=c.read(out/'summary.json').get('completed') is True
    elapsed=time.monotonic()-start
    c.write(out/'execution.json',dict(exit_code=code,timed_out=timed_out,elapsed_seconds=elapsed,started_at_utc=at,completed=complete,
        model_processes_started=1,gpu_index=int(chosen[0]),gpu_uuid=chosen[1]))
    print(__import__('json').dumps(dict(child=name,completed=complete,elapsed_seconds=elapsed)),flush=True)
    if not complete:raise RuntimeError('Delivery child failed: '+name)


def main():
    cfg=r.verify_runtime(RUNTIME);folder=r.ROOT/cfg['run_dir']
    with (r.ROOT/'runs/.imprint_delivery.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        actual={p.relative_to(r.ROOT).as_posix():c.sha(p) for p in (r.ROOT/'runs').rglob('execution.json')
            if p.relative_to(r.ROOT/'runs').parts[0][:2].isdigit() and int(p.relative_to(r.ROOT/'runs').parts[0][:2])>=7}
        if actual!=cfg['historical_execution_hashes']:raise ValueError('Execution inventory changed')
        for name,digest in cfg['source_hashes'].items():
            if c.sha(r.ROOT/name)!=digest:raise ValueError('Historical source changed')
        folder.mkdir();c.write(folder/'launch_intent.json',dict(stage='25',runtime_sha256=c.sha(RUNTIME),planned_model_processes=4,controller_pid=os.getpid()))
        print('RUN_DIR '+str(folder),flush=True)
        try:
            input_sha=prepare(folder,cfg)
            for batch in (0,1):child('generate_'+str(batch),'generate.py',r.ROOT/cfg['attack_runtime'],[folder/'attack_inputs',input_sha,batch],folder,cfg)
            images=folder/'evaluation_images';images.mkdir()
            for i,sid in enumerate(IDS):
                for method in METHODS:
                    source=folder/('generate_'+str(i//4))/(sid+'_'+method);rec=c.read(source/'record.json')
                    if rec['task']!=tasks()[i] or rec['method']!=method or rec['input']!=c.array_record(folder/'attack_inputs'/(sid+'_'+method+'.npy')):raise ValueError('Candidate association changed')
                    copy_checked(source/'candidate.png',images/(sid+'_'+method+'.png'),rec['image']['sha256'])
                source=cfg['inputs'][sid]['reference'];copy_checked(r.ROOT/source['path'],images/(sid+'_reference.png'),source['sha256'])
            image_sha=seal_bundle(images,'evaluation_images')
            c.write(folder/'candidates_sealed.json',dict(input_seal_sha256=input_sha,image_seal_sha256=image_sha,candidates=16,
                sealed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),target_calls_before_seal=0))
            for batch in (0,1):child('evaluate_'+str(batch),'evaluate.py',r.ROOT/cfg['evaluation_runtime'],[images,image_sha,batch],folder,cfg)
            rows=[]
            for i,sid in enumerate(IDS):
                row={'sample_id':sid}
                for method in ('reference',)+METHODS:
                    value=c.read(folder/('evaluate_'+str(i//4))/(sid+'_'+method)/'metrics.json')
                    if value['sample_id']!=sid or value['method']!=method:raise ValueError('Evaluation association changed')
                    row[method]=value['bit_accuracy']
                rows.append(row)
            bundle(images,image_sha,'evaluation_images');r.verify_runtime(RUNTIME)
            c.write(folder/'results.json',dict(rows=rows,summary=summary(rows)))
            c.write(folder/'status.json',dict(completed=True,model_processes_started=4,candidates=16,target_inversions=24,
                image_seal_sha256=image_sha,feedback_to_generator=False))
        except BaseException as exc:
            c.write(folder/'status.json',dict(completed=False,error_type=type(exc).__name__,reason=str(exc),
                model_processes_started=len(list(folder.rglob('process.json'))),unchanged_retry_allowed=False))
            raise
    print('COMPLETED_STAGE25',flush=True)

if __name__=='__main__':
    if sys.argv[1:]!=['--run']:raise SystemExit('Explicit --run required')
    main()
