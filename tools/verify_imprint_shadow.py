"""CPU, standard-library verification of the native trajectory recording control."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU verifier requires CUDA_VISIBLE_DEVICES=""')
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('recorded', type=Path)
    parser.add_argument('shadow', type=Path)
    parser.add_argument('protocol', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    for run in [args.recorded, args.shadow]:
        execution = load(run / 'execution.json')
        assert execution['completed'] and execution['exit_code'] == 0 and not execution['timed_out']
        assert 'COMPLETED_IMPRINT_DELIVERY_DIAGNOSTIC' in (run / 'stdout.log').read_text(encoding='utf-8')
    assert load(args.shadow / 'command.json')['protocol_sha256'] == sha(args.protocol)
    assert all(load(args.shadow / 'initial_control.json').values())
    assert load(args.shadow / 'trajectory_control.json')['final_latent_bitwise_equal']
    assert not list(args.shadow.glob('checkpoint_0'))
    leaves = ['reference_proxy_noise.npy', 'checkpoint_10/candidate.png']
    leaves += ['checkpoint_10/' + n + '.npy' for n in
               ['z', 'internal_noise', 'float_z', 'png_z', 'float_noise', 'png_noise']]
    results = []
    for leaf in leaves:
        recorded = sha(args.recorded / leaf)
        shadow = sha(args.shadow / leaf)
        assert recorded == shadow, leaf
        results.append(dict(path=leaf, sha256=recorded, bytewise_equal=True))
    assert load(args.recorded / 'checkpoint_10/metrics.json') == load(args.shadow / 'checkpoint_10/metrics.json')
    result = dict(status='passed', recorded_run=str(args.recorded), shadow_run=str(args.shadow),
        protocol_sha256=sha(args.protocol), equal_files=results,
        final_metrics_equal=True, gpu_used=False, models_loaded=False,
        inference_scope='One native ten-update trajectory in this pinned deterministic environment; not a universal equivalence proof')
    with args.output.open('x', encoding='utf-8') as file:
        json.dump(result, file, indent=2)
        file.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
