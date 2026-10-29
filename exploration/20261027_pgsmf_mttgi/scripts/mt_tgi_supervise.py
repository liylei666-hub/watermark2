"""MT-TGI pilot supervisor: idle-GPU gate, worker pool (1 process per card), attack then eval."""
import os, sys, json, time, subprocess, argparse
from pathlib import Path

ROOT = Path('/data0/liyanlei/watermark_research')
PILOT = ROOT / 'runs/pilot_mt_tgi_20261028'
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


def env_for(card):
    return dict(os.environ, CUDA_VISIBLE_DEVICES=card['uuid'], CUDA_DEVICE_ORDER='PCI_BUS_ID',
                HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUBLAS_WORKSPACE_CONFIG=':4096:8',
                PYTHONDONTWRITEBYTECODE='1', TOKENIZERS_PARALLELISM='false',
                HF_HOME=str(ROOT / 'cache/huggingface'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='full', choices=['full', 'smoke'])
    ap.add_argument('--jobs', default=None, help='e.g. v3:1,v3:2,v4:1')
    a = ap.parse_args()

    PILOT.mkdir(parents=True, exist_ok=True)
    (PILOT / 'logs').mkdir(exist_ok=True)
    cards = idle_gpus()
    write(PILOT / 'gpu_snapshot.json',
          dict(taken_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'), idle=cards))
    if not cards:
        write(PILOT / 'status.json', dict(state='stopped_no_idle_gpu'))
        print('NO_IDLE_GPU', flush=True)
        return 2

    jobs = [('v3', 1), ('v3', 2), ('v4', 1), ('v4', 2)]
    if a.mode == 'smoke':
        jobs = [('v3', 1)]
    if a.jobs:
        jobs = [(x.split(':')[0], int(x.split(':')[1])) for x in a.jobs.split(',')]
    print(f'IDLE={[c["index"] for c in cards]} JOBS={jobs}', flush=True)

    queue = list(jobs)
    running = []
    results = []
    while queue or running:
        while queue and len(running) < len(cards):
            used = {x['card']['index'] for x in running}
            free = [c for c in cards if c['index'] not in used]
            if not free:
                break
            v, t = queue.pop(0)
            card = free[0]
            name = f'{v}_t{t}' if a.mode != 'smoke' else f'smoke_{v}_t{t}'
            adir = PILOT / name
            cmd = [str(PY), str(HERE / 'mt_tgi_attack.py'), '--variant', v, '--task', str(t),
                   '--uuid', card['uuid'], '--index', str(card['index']), '--out', str(adir)]
            if a.mode == 'smoke':
                cmd.append('--smoke')
            lf = (PILOT / 'logs' / f'{name}_attack.log').open('w')
            p = subprocess.Popen(cmd, env=env_for(card), cwd=str(HERE),
                                 stdout=lf, stderr=subprocess.STDOUT)
            running.append(dict(p=p, lf=lf, v=v, t=t, card=card, name=name, t0=time.time()))
            print(f'START {name} on GPU{card["index"]}', flush=True)
            write(PILOT / 'status.json', dict(state='running', mode=a.mode,
                                              running=[x['name'] for x in running],
                                              queued=[f'{v}_t{t}' for v, t in queue],
                                              done=results))
        time.sleep(10)
        for j in list(running):
            if j['p'].poll() is None:
                continue
            j['lf'].close()
            rc = j['p'].returncode
            rec = dict(variant=j['v'], task=j['t'], gpu=j['card']['index'], attack_rc=rc,
                       attack_seconds=time.time() - j['t0'])
            if rc == 0 and a.mode != 'smoke':
                edir = PILOT / 'eval' / j['name']
                cmd2 = [str(PY), str(HERE / 'mt_tgi_eval.py'), '--variant', j['v'],
                        '--task', str(j['t']), '--uuid', j['card']['uuid'],
                        '--index', str(j['card']['index']),
                        '--attack_dir', str(PILOT / j['name']), '--out', str(edir)]
                with (PILOT / 'logs' / f'{j["name"]}_eval.log').open('w') as lf:
                    rec['eval_rc'] = subprocess.call(cmd2, env=env_for(j['card']),
                                                     cwd=str(HERE), stdout=lf,
                                                     stderr=subprocess.STDOUT)
            rec['total_seconds'] = time.time() - j['t0']
            results.append(rec)
            running.remove(j)
            print(f'JOB_DONE {j["name"]} attack_rc={rc} eval_rc={rec.get("eval_rc")}', flush=True)
            write(PILOT / 'status.json', dict(state='running', mode=a.mode,
                                              running=[x['name'] for x in running],
                                              queued=[f'{v}_t{t}' for v, t in queue],
                                              done=results))

    ok = all(r['attack_rc'] == 0 and r.get('eval_rc', 0) == 0 for r in results)
    write(PILOT / 'status.json', dict(state='completed' if ok else 'failed', mode=a.mode,
                                      finished=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                                      results=results))
    print('SUPERVISOR_DONE', ok, flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
