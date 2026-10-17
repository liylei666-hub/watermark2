"""CPU supervisor: explicit launch, one idle GPU, immutable protocol, no retries."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU supervisor requires CUDA_VISIBLE_DEVICES=""')
import datetime
import fcntl
import importlib.util
import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from experiment import sha, write

ROOT = Path('/data0/liyanlei/watermark_research')
PROTOCOL = ROOT / 'protocols/13_vae_core.json'
PYTHON = ROOT / 'envs/semantic_forgery_py310/bin/python'


def main():
    cfg = json.loads(PROTOCOL.read_text())
    expected = PROTOCOL.with_suffix('.sha256').read_text().strip()
    if sha(PROTOCOL) != expected:
        raise RuntimeError('Protocol hash changed')
    for name, h in cfg['code_hashes'].items():
        if sha(name) != h:
            raise RuntimeError('Code changed')
    for record in cfg['inputs'].values():
        if sha(record['path']) != record['sha256']:
            raise RuntimeError('Input changed')
    # Lock is local to this controller; it is not OS-level attack/evaluator isolation.
    with (ROOT / 'runs/.imprint_delivery.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        existing = list((ROOT / 'runs').glob('13_vae_core_*/process.json'))
        if existing:
            raise RuntimeError('A model process was already attempted; inspect without retry')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        output = ROOT / 'runs' / ('13_vae_core_' + stamp)
        output.mkdir()
        write(output / 'launch_intent.json', dict(protocol_sha256=expected, stage='13'))
        spec = importlib.util.spec_from_file_location('idle_gate', ROOT / 'scripts/gpu_preflight.py')
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        chosen = None
        with (output / 'preflight.jsonl').open('x') as f:
            def record(event):
                f.write(json.dumps(event) + '\n')
                f.flush()
                os.fsync(f.fileno())
            for index, uuid in cfg['allowed_gpu_uuids'].items():
                try:
                    gate.verify_idle(gate.snapshot, record, int(index), uuid, 'NVIDIA GeForce RTX 3090')
                    chosen = (index, uuid)
                    break
                except Exception as exc:
                    record(dict(event='device_unavailable', index=index, reason=str(exc)))
        if chosen is None:
            write(output / 'status.json', dict(status='waiting_for_idle_gpu', model_processes_started=0))
            print('NO_IDLE_AUTHORIZED_GPU', flush=True)
            return
        # Account for all newly created research files since stage07, including source and reports.
        folders = [ROOT / 'runs', ROOT / 'reports', ROOT / 'scripts', ROOT / 'protocols']
        total = sum(p.stat().st_size for folder in folders for p in folder.rglob('*') if p.is_file())
        if total >= cfg['max_new_bytes']:
            raise RuntimeError('Conservative research-file size gate exceeded')
        env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID', CUDA_VISIBLE_DEVICES=chosen[1],
            HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1',
            HF_HOME=str(ROOT / 'cache/huggingface'), PYTHONDONTWRITEBYTECODE='1',
            TOKENIZERS_PARALLELISM='false', CUBLAS_WORKSPACE_CONFIG=':4096:8')
        command = [str(PYTHON), str(Path(__file__).with_name('experiment.py')), str(PROTOCOL), str(output)]
        write(output / 'command.json', dict(argv=command, gpu_index=int(chosen[0]), gpu_uuid=chosen[1],
            protocol_sha256=expected, watchdog_seconds=cfg['watchdog_seconds']))
        start = time.monotonic()
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        timed_out = False
        with (output / 'stdout.log').open('x') as stdout, (output / 'stderr.log').open('x') as stderr:
            proc = subprocess.Popen(command, env=env, cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True)
            write(output / 'process.json', dict(pid=proc.pid, started_at_utc=started_at))
            try:
                code = proc.wait(timeout=cfg['watchdog_seconds'])
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    code = proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    code = proc.wait()
        seconds = time.monotonic() - start
        success = code == 0 and (output / 'summary.json').is_file() and \
            'COMPLETED_VAE_CORE_EQUIVALENCE' in (output / 'stdout.log').read_text()
        write(output / 'execution.json', dict(exit_code=code, timed_out=timed_out,
            elapsed_seconds=seconds, started_at_utc=started_at, completed=success,
            model_processes_started=1, gpu_index=int(chosen[0]), gpu_uuid=chosen[1]))
        print(json.dumps(dict(output=str(output), completed=success, elapsed_seconds=seconds)), flush=True)
        if not success:
            raise SystemExit(1)


if __name__ == '__main__':
    if sys.argv[1:] != ['--run']:
        raise SystemExit('Explicit --run required; this controller does not schedule or poll')
    main()
