"""Offline pinned-source component audit; never a real-image watermark experiment."""
import ast
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'runs/reproduction_audit'
OUT = ROOT / 'reports/reproduction_audit'


def main():
    os.environ.update(CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1',
                      TRANSFORMERS_OFFLINE='1', WANDB_MODE='disabled',
                      PYTHONIOENCODING='utf-8', PYTHONUTF8='1', OMP_NUM_THREADS='2')
    deps = ROOT / 'runs/reproduction_audit_dependencies'
    if deps.exists():
        os.environ['PYTHONPATH'] = str(deps)
    import numpy as np
    import torch
    torch.set_num_threads(2)
    inventories = json.loads((OUT / 'public_code_inventory.json').read_text())['repositories']
    inventories.append(json.loads((OUT / 'csi_code_inventory.json').read_text()))
    verified = 0
    for repo in inventories:
        for f in repo['files']:
            p = CACHE / repo['repo'].split('/')[1] / f['path']
            assert hashlib.sha256(p.read_bytes()).hexdigest() == f['sha256'], p
            verified += 1
    result = {'scope': 'offline component/interface checks; no real images or watermark ASR',
              'source_files_hash_verified': verified, 'torch': torch.__version__,
              'numpy': np.__version__, 'cuda_visible_devices': '', 'tests': []}
    for args, name in [(['-m', 'pytest', '-q'], 'csi_pytest'),
                       (['-m', 'csi', 'selftest', '--victims', '2', '--negatives', '4', '--json'], 'csi_simulated_selftest')]:
        t = time.perf_counter()
        p = subprocess.run([sys.executable, *args], cwd=CACHE / 'CSI-Attack',
                           capture_output=True, timeout=120, env=os.environ.copy())
        (OUT / (name + '.stdout.txt')).write_bytes(p.stdout)
        (OUT / (name + '.stderr.txt')).write_bytes(p.stderr)
        result['tests'].append({'name': name, 'exit_code': p.returncode,
                                'wall_seconds': time.perf_counter() - t})
        if p.returncode:
            print(p.stderr.decode('utf-8', errors='replace'))
    # Execute only these audited pure numerical function definitions, avoiding
    # module imports, model loaders, global ring construction and entrypoints.
    source = CACHE / 'SEAL/utils.py'
    wanted = {'set_random_seed', 'deterministic_hash', 'simhash',
              'generate_initial_noise', 'calculate_patch_l2'}
    nodes = [n for n in ast.parse(source.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert len(nodes) == len(wanted)
    ns = dict(torch=torch, np=np, random=random, math=math, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
    v = torch.arange(1, 769, dtype=torch.float32)
    v /= v.norm()
    z = ns['generate_initial_noise'](v, 1024, 7, 42, 'cpu')
    z_repeat = ns['generate_initial_noise'](v, 1024, 7, 42, 'cpu')
    self_l2 = ns['calculate_patch_l2'](z, z_repeat, 1024)
    z_changed = z.clone()
    z_changed[:, :, :2, :2] += 1
    changed_l2 = ns['calculate_patch_l2'](z, z_changed, 1024)
    assert max(self_l2) == 0 and sum(x != 0 for x in changed_l2) == 1
    assert changed_l2[0] == 4.0
    result['seal_numerical'] = {'fixture': 'deterministic 768D vector, not image embedding',
        'functions': sorted(wanted), 'shape': list(z.shape), 'self_max_l2': max(self_l2),
        'changed_patches': sum(x != 0 for x in changed_l2), 'changed_patch_l2': changed_l2[0],
        'noise_sha256': hashlib.sha256(z.numpy().tobytes()).hexdigest()}
    # Confirm CSI's independently reimplemented stream is incompatible with
    # the official stream, even for identical embedding/key/shape arguments.
    sys.path.insert(0, str(CACHE / 'CSI-Attack'))
    from csi.schemes.seal import SealCore
    from csi.types import Key
    csi_z = SealCore().noise_from_embedding(v.numpy(), Key(seed=42))
    result['cross_implementation'] = {
        'noise_equal': bool(np.array_equal(z.numpy(), csi_z)),
        'rmse': float(np.sqrt(np.mean((z.numpy() - csi_z)**2))),
        'interpretation': 'different hash and RNG streams; not interchangeable saved latents'}
    assert not result['cross_implementation']['noise_equal']
    spec = importlib.util.spec_from_file_location('sembind_model', CACHE / 'SemBind/model.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with torch.device('meta'):
        m = mod.AttnSupConHashingModel(input_dim=1536, feat_dim=8192, hash_dim=1024)
    result['sembind_architecture'] = {
        'parameters': sum(p.numel() for p in m.parameters()),
        'state_dict_fp32_tensor_bytes': sum(t.numel()*t.element_size() for t in m.state_dict().values()),
        'method': 'meta-device shape allocation only; no checkpoint loaded or inference'}
    notebook = json.loads((CACHE / 'SemBind/semantimark.ipynb').read_text())
    result['sembind_saved_outputs'] = sum(len(c.get('outputs', [])) for c in notebook['cells'])
    (OUT / 'component_checks.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, indent=2))
    assert all(t['exit_code'] == 0 for t in result['tests']), 'See preserved failure logs'


if __name__ == '__main__':
    main()
