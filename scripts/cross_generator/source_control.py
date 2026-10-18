"""Stage24 source phase: six serial model children, one fixed fit, no test generation."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU supervisor requires empty CUDA visibility')
import datetime
import fcntl
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import io_contract as c
from source_worker import r, jobs
from fit_source import main as fit_source

PYTHON = r.ROOT / 'envs/semantic_forgery_py310/bin/python'
SCRIPTS = r.ROOT / 'scripts/cross_generator'
RUNTIME = r.ROOT / 'protocols/24_cross_generator_source_runtime.json'
JOBS = r.ROOT / 'protocols/24_cross_generator_source_jobs.json'


def run_child(index, root, cfg):
    out = root / ('source_' + str(index)); out.mkdir()
    spec = importlib.util.spec_from_file_location('idle_gate', r.ROOT / 'scripts/gpu_preflight.py')
    gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
    chosen = None
    with (out / 'preflight.jsonl').open('x') as stream:
        def record(value):
            stream.write(json.dumps(value) + '\n'); stream.flush(); os.fsync(stream.fileno())
        for device, uuid in cfg['allowed_gpu_uuids'].items():
            try:
                gate.verify_idle(gate.snapshot, record, int(device), uuid, 'NVIDIA GeForce RTX 3090')
                chosen = (device, uuid); break
            except Exception as exc:
                record(dict(event='device_unavailable', index=device, reason=str(exc)))
    if chosen is None:
        raise RuntimeError('No idle authorized GPU; source study stopped')
    total = sum(p.stat().st_size for name in ['runs', 'reports', 'scripts', 'protocols', 'private_eval']
                for p in (r.ROOT / name).rglob('*') if p.is_file())
    group = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if total + 512 * 1024**2 >= cfg['max_new_bytes'] or group + 32 * 1024**2 >= cfg['max_group_new_bytes']:
        raise RuntimeError('Storage safety margin unavailable')
    r.verify_runtime(RUNTIME)
    env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID', CUDA_VISIBLE_DEVICES=chosen[1],
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1',
               HF_HOME=str(r.ROOT / 'cache/huggingface'), PYTHONDONTWRITEBYTECODE='1',
               TOKENIZERS_PARALLELISM='false', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    command = [str(PYTHON), str(SCRIPTS / 'source_worker.py'), str(RUNTIME), str(JOBS), str(index), str(out)]
    c.write(out / 'command.json', dict(argv=command, gpu_index=int(chosen[0]), gpu_uuid=chosen[1],
             runtime_sha256=c.sha(RUNTIME), watchdog_seconds=1200))
    start = time.monotonic(); at = datetime.datetime.now(datetime.timezone.utc).isoformat(); timed_out = False
    with (out / 'stdout.log').open('x') as stdout, (out / 'stderr.log').open('x') as stderr:
        proc = subprocess.Popen(command, env=env, cwd=r.ROOT, stdout=stdout, stderr=stderr, start_new_session=True)
        c.write(out / 'process.json', dict(pid=proc.pid, started_at_utc=at))
        try:
            code = proc.wait(timeout=1200)
        except subprocess.TimeoutExpired:
            timed_out = True; os.killpg(proc.pid, signal.SIGTERM)
            try: code = proc.wait(timeout=10)
            except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); code = proc.wait()
    elapsed = time.monotonic() - start
    complete = code == 0 and not timed_out and (out / 'summary.json').is_file()
    if complete:
        complete = c.read(out / 'summary.json').get('completed') is True and 'COMPLETED_SOURCE_BATCH' in (out / 'stdout.log').read_text()
    c.write(out / 'execution.json', dict(exit_code=code, timed_out=timed_out, elapsed_seconds=elapsed,
             started_at_utc=at, completed=complete, model_processes_started=1,
             gpu_index=int(chosen[0]), gpu_uuid=chosen[1]))
    print(json.dumps(dict(batch=index, completed=complete, elapsed_seconds=elapsed)), flush=True)
    if not complete:
        raise RuntimeError('Source child failed: ' + str(index))


def source_entries(root, plan):
    entries = {}
    for index, batch in enumerate(plan['batches']):
        out = root / ('source_' + str(index)); summary = c.read(out / 'summary.json')
        if summary['batch_index'] != index or summary['source_jobs_sha256'] != c.sha(JOBS) or summary['model'] != plan['model']:
            raise ValueError('Source summary provenance mismatch')
        if [row['task'] for row in summary['rows']] != batch:
            raise ValueError('Source tasks/provenance mismatch')
        for task, row in zip(batch, summary['rows']):
            folder = out / task['sample_id']
            if c.read(folder / 'record.json') != row or c.png_record(folder / 'reference.png') != row['image']:
                raise ValueError('Source record/image changed')
            if row['inversion_input'] != 'saved_png_readback' or row['png_pixel_equivalence'] is not True:
                raise ValueError('Saved-image delivery not verified')
            entries[task['sample_id']] = {}
            for name in ('estimate', 'original_noise'):
                path = folder / (name + '.npy')
                if c.array_record(path) != row[name]:
                    raise ValueError('Source tensor changed')
                entries[task['sample_id']][name] = path
    return entries


def main():
    cfg = r.verify_runtime(RUNTIME); plan = jobs(JOBS, cfg)
    with (r.ROOT / 'runs/.imprint_delivery.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for name, digest in cfg['historical_execution_hashes'].items():
            if c.sha(r.ROOT / name) != digest:
                raise ValueError('Historical execution changed')
        actual = {p.relative_to(r.ROOT).as_posix() for p in (r.ROOT / 'runs').rglob('execution.json')
                  if p.relative_to(r.ROOT / 'runs').parts[0][:2].isdigit()
                  and int(p.relative_to(r.ROOT / 'runs').parts[0][:2]) >= 7}
        if actual != set(cfg['historical_execution_hashes']):
            raise ValueError('Execution inventory changed before launch')
        if list((r.ROOT / 'runs').glob('24_cross_generator_*/launch_intent.json')):
            raise ValueError('Stage24 already attempted; inspect state instead of restarting')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        root = r.ROOT / 'runs' / ('24_cross_generator_' + stamp); root.mkdir()
        c.write(root / 'launch_intent.json', dict(stage='24', phase='source', planned_model_processes=6,
                 runtime_sha256=c.sha(RUNTIME), design_sha256=plan['design_sha256'], controller_pid=os.getpid()))
        print('RUN_DIR ' + str(root), flush=True)
        try:
            for index in range(6):
                run_child(index, root, cfg)
            entries = source_entries(root, plan)
            train = root / 'train_inputs'; validation = root / 'validation_inputs'
            ts = c.export_bundle(train, 'train', {sid: entries[sid] for sid in c.SPLITS['train']})
            vs = c.export_bundle(validation, 'validation', {sid: entries[sid] for sid in c.SPLITS['validation']})
            r.verify_runtime(RUNTIME)
            start = time.perf_counter()
            gate, digest = fit_source(train, ts, validation, vs, root / 'source_fit')
            c.write(root / 'source_cpu_execution.json', dict(completed=True, elapsed_seconds=time.perf_counter()-start,
                      source_seal_sha256=digest, model_processes_started=0))
            c.write(root / 'source_status.json', dict(status='source_passed_test_runtime_pending' if gate['pass'] else 'closed_source_gate_failed',
                      source_phase_completed=True, full_study_completed=not gate['pass'], model_processes_started=6,
                      source_gate_pass=gate['pass'], source_seal_sha256=digest, test_images_generated=0,
                      full_defense_acceptance=None, unchanged_retry_allowed=False))
        except BaseException as exc:
            c.write(root / 'source_status.json', dict(status='stopped', source_phase_completed=False,
                      error_type=type(exc).__name__, reason=str(exc),
                      model_processes_started=len(list(root.rglob('process.json'))), unchanged_retry_allowed=False))
            raise
    print('COMPLETED_SOURCE_PHASE', flush=True)


if __name__ == '__main__':
    if sys.argv[1:] != ['--run']:
        raise SystemExit('Explicit --run required')
    main()
