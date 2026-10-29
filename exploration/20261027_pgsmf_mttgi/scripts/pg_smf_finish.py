"""Backfill V1 metadata from stdout (timing lost) and run the 4 SDXL evaluations."""
import os, sys, json, re, hashlib, subprocess, time
from pathlib import Path
import numpy as np

ROOT = Path('/data0/liyanlei/watermark_research')
PILOT = ROOT / 'runs/pilot_pg_smf_20261027'
PY = ROOT / 'envs/semantic_forgery_py310/bin/python'
POINTS = (10, 20, 30, 50)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rec(p):
    a = np.load(p, allow_pickle=False)
    return dict(path=Path(p).name, sha256=sha(p), shape=list(a.shape), dtype=str(a.dtype))


def backfill(name):
    d = PILOT / name
    log = PILOT / 'logs' / f'{name}_attack.log'
    if (d / 'losses.json').exists():
        try:
            json.loads((d / 'losses.json').read_text())
            return 'exists'
        except Exception:
            (d / 'losses.json').unlink()          # truncated by the crashed json.dump
    rows = []
    for line in log.read_text(errors='ignore').splitlines():
        m = re.match(r'STEP (\d+) loss=([-\d.eE+]+) gnorm=([-\d.eE+]+)', line)
        if m:
            rows.append(dict(step=int(m.group(1)), loss_raw=float(m.group(2)),
                             grad_norm=float(m.group(3)), loss_scaled=float(m.group(2)) * 4.2,
                             probit=-1.0, margin=-1.0, huber=-1.0,
                             step_delta_l2=-1.0, spectral_shrink=-1.0, seconds=-1.0))
    if len(rows) != 50:
        raise RuntimeError(f'{name}: expected 50 steps in log, got {len(rows)}')
    variant = 'v1' if name.startswith('v1') else 'v2'
    task = int(name.split('_t')[1])
    obj = dict(variant=variant, task=task, scale=4.2, lr=0.01, steps=50,
               reconstructed_from_stdout=True,
               note='attack process crashed at the final JSON write (NaN in V1-only fields); '
                    'per-step loss/gnorm recovered verbatim from stdout at 6 decimals. '
                    'probit/margin/huber/seconds not recoverable.',
               history=rows)
    with (d / 'losses.json').open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, allow_nan=False); f.write('\n')
    summ = dict(completed=True, reconstructed=True, variant=variant, task=task, steps=50,
                points=list(POINTS),
                images={str(n): rec(d / f'update_{n}_latent.npy') for n in POINTS},
                pngs={str(n): dict(path=f'update_{n}.png', sha256=sha(d / f'update_{n}.png'))
                      for n in POINTS},
                script_sha256=sha(PILOT / 'pg_smf_attack.py'),
                lr=0.01, loss_scale=4.2, target_scores_seen=0,
                timing=None, timing_note='unavailable: process exited after step 50 exports')
    with (d / 'summary.json').open('x', encoding='utf-8') as f:
        json.dump(summ, f, indent=2, allow_nan=False); f.write('\n')
    return 'backfilled'


def main():
    status = {}
    for name in ('v1_t1', 'v1_t2'):
        d = PILOT / name
        missing = [f'update_{n}.png' for n in POINTS if not (d / f'update_{n}.png').exists()]
        missing += [f'update_{n}_latent.npy' for n in POINTS if not (d / f'update_{n}_latent.npy').exists()]
        if missing:
            raise RuntimeError(f'{name} missing artifacts: {missing}')
        status[name] = backfill(name)
    print('BACKFILL', status, flush=True)

    jobs = [('v1', 1), ('v1', 2), ('v2', 1), ('v2', 2)]
    procs = []
    for i, (v, t) in enumerate(jobs):
        edir = PILOT / 'eval' / f'{v}_t{t}'
        if edir.exists():
            import shutil
            shutil.rmtree(edir)
        uuid = subprocess.check_output(
            ['nvidia-smi', '-i', str(i), '--query-gpu=uuid', '--format=csv,noheader'], text=True).strip()
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=uuid, CUDA_DEVICE_ORDER='PCI_BUS_ID',
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUBLAS_WORKSPACE_CONFIG=':4096:8',
                   HF_HOME=str(ROOT / 'cache/huggingface'), PYTHONDONTWRITEBYTECODE='1')
        cmd = [str(PY), str(PILOT / 'pg_smf_eval.py'), '--variant', v, '--task', str(t),
               '--uuid', uuid, '--index', str(i), '--attack_dir', str(PILOT / f'{v}_t{t}'),
               '--out', str(edir)]
        lf = (PILOT / 'logs' / f'{v}_t{t}_eval.log').open('w')
        procs.append(dict(p=subprocess.Popen(cmd, env=env, cwd=str(PILOT), stdout=lf,
                                             stderr=subprocess.STDOUT), lf=lf, v=v, t=t, gpu=i))
    res = []
    for j in procs:
        rc = j['p'].wait(); j['lf'].close()
        res.append(dict(variant=j['v'], task=j['t'], gpu=j['gpu'], eval_rc=rc))
        print('EVAL_DONE', j['v'], j['t'], rc, flush=True)
    with (PILOT / 'status.json').open('w', encoding='utf-8') as f:
        json.dump(dict(state='completed' if all(r['eval_rc'] == 0 for r in res) else 'failed',
                       finished=time.strftime('%Y-%m-%dT%H:%M:%S%z'), backfill=status, evals=res),
                  f, indent=2)
    print('FINISH_DONE', flush=True)


if __name__ == '__main__':
    main()
