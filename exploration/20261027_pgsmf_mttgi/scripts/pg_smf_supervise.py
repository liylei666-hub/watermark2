"""PG-SMF pilot supervisor: idle-GPU gate, one process per card, attack then eval."""
import os, sys, json, time, subprocess, argparse
from pathlib import Path

ROOT = Path('/data0/liyanlei/watermark_research')
PILOT = ROOT / 'runs/pilot_pg_smf_20261027'
PY = ROOT / 'envs/semantic_forgery_py310/bin/python'
HERE = Path(__file__).resolve().parent


def sh(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def idle_gpus():
    rows = sh(['nvidia-smi', '--query-gpu=index,uuid,memory.used,utilization.gpu',
               '--format=csv,noheader,nounits']).splitlines()
    apps = sh(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'])
    busy = {a.split(',')[0].strip() for a in apps.splitlines() if a.strip()}
    out = []
    for r in rows:
        i, u, mem, util = [x.strip() for x in r.split(',')]
        if int(i) == 6:
            continue
        if int(mem) < 500 and int(util) == 0 and u not in busy:
            out.append(dict(index=int(i), uuid=u, mem=int(mem), util=int(util)))
    return out


def write(p, obj):
    with Path(p).open('w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write('\n')


def run_job(card, variant, task, mode):
    name = f'{variant}_t{task}'
    adir = PILOT / name
    edir = PILOT / 'eval' / name
    logdir = PILOT / 'logs'
    logdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=card['uuid'], CUDA_DEVICE_ORDER='PCI_BUS_ID',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUBLAS_WORKSPACE_CONFIG=':4096:8',
               PYTHONDONTWRITEBYTECODE='1', TOKENIZERS_PARALLELISM='false',
               HF_HOME=str(ROOT / 'cache/huggingface'))
    cmd = [str(PY), str(HERE / 'pg_smf_attack.py'), '--variant', variant, '--task', str(task),
           '--uuid', card['uuid'], '--index', str(card['index']), '--out', str(adir)]
    if mode == 'smoke':
        cmd.append('--smoke')
    t0 = time.time()
    with (logdir / f'{name}_attack.log').open('w') as lf:
        rc = subprocess.call(cmd, env=env, cwd=str(HERE), stdout=lf, stderr=subprocess.STDOUT)
    rec = dict(variant=variant, task=task, gpu=card, attack_rc=rc,
               attack_seconds=time.time() - t0)
    if rc == 0 and mode != 'smoke':
        cmd2 = [str(PY), str(HERE / 'pg_smf_eval.py'), '--variant', variant, '--task', str(task),
                '--uuid', card['uuid'], '--index', str(card['index']),
                '--attack_dir', str(adir), '--out', str(edir)]
        with (logdir / f'{name}_eval.log').open('w') as lf:
            rc2 = subprocess.call(cmd2, env=env, cwd=str(HERE), stdout=lf, stderr=subprocess.STDOUT)
        rec.update(eval_rc=rc2)
    rec['total_seconds'] = time.time() - t0
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='full', choices=['full', 'smoke'])
    ap.add_argument('--only', default=None, help='optional comma list like v1:1')
    a = ap.parse_args()

    PILOT.mkdir(parents=True, exist_ok=True)
    cards = idle_gpus()
    write(PILOT / 'gpu_snapshot.json', dict(taken_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                                            idle=cards))
    if not cards:
        write(PILOT / 'status.json', dict(state='stopped_no_idle_gpu', started=None))
        print('NO_IDLE_GPU', flush=True)
        return 2

    jobs = [('v1', 1), ('v1', 2), ('v2', 1), ('v2', 2)]
    if a.only:
        sel = {tuple(x.split(':')) for x in a.only.split(',')}
        jobs = [(v, int(t)) for v, t in jobs if (v, t) in sel or (v, str(t)) in sel]
    if a.mode == 'smoke':
        jobs = [('v1', 1)]

    n = min(len(cards), len(jobs))
    print(f'IDLE={[c["index"] for c in cards]} JOBS={jobs[:n]}', flush=True)
    write(PILOT / 'status.json', dict(state='running', mode=a.mode,
                                      started=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                                      assignments=[dict(job=j, card=cards[i]) for i, j in enumerate(jobs[:n])]))

    procs, results = [], []
    for i, (v, t) in enumerate(jobs[:n]):
        name = f'{v}_t{t}' if a.mode != 'smoke' else f'smoke_{v}_t{t}'
        logdir = PILOT / 'logs'
        logdir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=cards[i]['uuid'], CUDA_DEVICE_ORDER='PCI_BUS_ID',
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUBLAS_WORKSPACE_CONFIG=':4096:8',
                   PYTHONDONTWRITEBYTECODE='1', TOKENIZERS_PARALLELISM='false',
                   HF_HOME=str(ROOT / 'cache/huggingface'))
        cmd = [str(PY), str(HERE / 'pg_smf_attack.py'), '--variant', v, '--task', str(t),
               '--uuid', cards[i]['uuid'], '--index', str(cards[i]['index']),
               '--out', str(PILOT / name)]
        if a.mode == 'smoke':
            cmd.append('--smoke')
        lf = (logdir / f'{name}_attack.log').open('w')
        p = subprocess.Popen(cmd, env=env, cwd=str(HERE), stdout=lf, stderr=subprocess.STDOUT)
        procs.append(dict(p=p, lf=lf, variant=v, task=t, card=cards[i], t0=time.time()))

    for j in procs:
        rc = j['p'].wait()
        j['lf'].close()
        rec = dict(variant=j['variant'], task=j['task'], gpu=j['card'], attack_rc=rc,
                   attack_seconds=time.time() - j['t0'])
        if rc == 0 and a.mode != 'smoke':
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=j['card']['uuid'],
                       CUDA_DEVICE_ORDER='PCI_BUS_ID', HF_HUB_OFFLINE='1',
                       TRANSFORMERS_OFFLINE='1', CUBLAS_WORKSPACE_CONFIG=':4096:8',
                       HF_HOME=str(ROOT / 'cache/huggingface'))
            cmd2 = [str(PY), str(HERE / 'pg_smf_eval.py'), '--variant', j['variant'],
                    '--task', str(j['task']), '--uuid', j['card']['uuid'],
                    '--index', str(j['card']['index']),
                    '--attack_dir', str(PILOT / f'{j["variant"]}_t{j["task"]}'),
                    '--out', str(PILOT / 'eval' / f'{j["variant"]}_t{j["task"]}')]
            with (PILOT / 'logs' / f'{j["variant"]}_t{j["task"]}_eval.log').open('w') as lf:
                rc2 = subprocess.call(cmd2, env=env, cwd=str(HERE), stdout=lf, stderr=subprocess.STDOUT)
            rec['eval_rc'] = rc2
        rec['total_seconds'] = time.time() - j['t0']
        results.append(rec)
        write(PILOT / 'status.json', dict(state='running', mode=a.mode, done=results,
                                          pending=[f"{x['variant']}_t{x['task']}"
                                                   for x in procs if x['p'].poll() is None]))
        print('JOB_DONE', j['variant'], j['task'], 'rc', rc, rec.get('eval_rc'), flush=True)

    ok = all(r['attack_rc'] == 0 and r.get('eval_rc', 0) == 0 for r in results)
    write(PILOT / 'status.json', dict(state='completed' if ok else 'failed', mode=a.mode,
                                      finished=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                                      results=results))
    print('SUPERVISOR_DONE', ok, flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
