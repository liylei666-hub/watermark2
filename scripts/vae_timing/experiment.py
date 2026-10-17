"""Fixed-prefix equivalence check of a pinned VAE-only attack core."""
import ast
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2, allow_nan=False)


def definitions(record, names):
    if sha(record['path']) != record['sha256']:
        raise ValueError('Source hash mismatch')
    tree = ast.parse(Path(record['path']).read_bytes())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if len(nodes) != len(names) or {n.name for n in nodes} != set(names) or any(n.decorator_list for n in nodes):
        raise ValueError('Definition boundary mismatch')
    return compile(ast.Module(body=nodes, type_ignores=[]), record['path'], 'exec')


def check_binding(cfg):
    if os.environ.get('CUDA_VISIBLE_DEVICES') not in cfg['allowed_gpu_uuids'].values():
        raise ValueError('Single authorized UUID required')
    if os.environ.get('CUDA_DEVICE_ORDER') != 'PCI_BUS_ID':
        raise ValueError('Device order required')
    for key in ['HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE']:
        if os.environ.get(key) != '1':
            raise ValueError('Offline loading required')
    if os.environ.get('CUBLAS_WORKSPACE_CONFIG') != ':4096:8':
        raise ValueError('Deterministic workspace required')


def main(protocol_path, output):
    cfg = json.loads(protocol_path.read_text())
    check_binding(cfg)
    import csv
    import subprocess
    import time
    import importlib.metadata
    uuid = os.environ['CUDA_VISIBLE_DEVICES']
    row = next(csv.reader([subprocess.check_output(['nvidia-smi', '-i', uuid,
        '--query-gpu=index,uuid,name,memory.used,utilization.gpu', '--format=csv,noheader,nounits'],
        text=True).strip()], skipinitialspace=True))
    apps = list(csv.reader(subprocess.check_output(['nvidia-smi',
        '--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader,nounits'],
        text=True).splitlines(), skipinitialspace=True))
    selected = [a for a in apps if a and a[0] == uuid]
    write(output/'device_preimport.json', dict(row=row, compute_apps=selected))
    if cfg['allowed_gpu_uuids'].get(row[0]) != row[1] or row[2] != 'NVIDIA GeForce RTX 3090' or int(row[3]) > 50 or int(row[4]) != 0 or selected:
        raise RuntimeError('Device not idle before imports')
    for rec in cfg['inputs'].values():
        if sha(rec['path']) != rec['sha256']:
            raise ValueError('Input changed')
    for path, expected in cfg['code_hashes'].items():
        if sha(path) != expected:
            raise ValueError('Code changed')
    for name, expected in cfg['versions'].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError('Version changed: '+name)
    import numpy as np
    import torch
    from PIL import Image
    from torchvision import transforms
    from diffusers import AutoencoderKL
    if torch.cuda.device_count() != 1:
        raise RuntimeError('Expected one visible GPU')
    torch.cuda.set_device(0)
    torch.manual_seed(cfg['seed'])
    np.random.seed(cfg['seed'])
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    scope = dict(torch=torch, Variable=torch.autograd.Variable, device=torch.device('cuda:0'), Image=Image, transforms=transforms)
    exec(definitions(cfg['inputs']['core'], {'pgd_attack_lamda', 'save_img'}), scope)
    exec(definitions(cfg['inputs']['preprocess'], {'transform_img'}), scope)
    images = {}
    for key in ['reference', 'cover']:
        with Image.open(cfg['inputs'][key]['path']) as im:
            im = im.convert('RGB')
            if im.size != (512,512):
                raise ValueError('Expected already square development input')
            im.save(output/(key+'_rgb.png'))
            images[key] = scope['transform_img'](im).unsqueeze(0).to('cuda:0')
        np.save(output/(key+'_input.npy'), images[key].cpu().numpy(), allow_pickle=False)
    t = time.perf_counter()
    vae = AutoencoderKL.from_pretrained(cfg['model_snapshot'], subfolder='vae',
        local_files_only=True, use_safetensors=True, torch_dtype=torch.float32).to('cuda:0').eval()
    torch.cuda.synchronize()
    load_seconds = time.perf_counter()-t
    results = {}
    # Each prefix starts again from the same cover. These are engineering replicas,
    # not independent candidates selected using an evaluator.
    for label, freeze in [('native', False)]:
        vae.requires_grad_(not freeze)
        # Warm the same encode/input-backward path before timings in each mode.
        warm = images['cover'].detach().clone().requires_grad_(True)
        warm_loss = vae.encode(warm).latent_dist.mode().square().mean()
        torch.autograd.grad(warm_loss, warm)
        del warm, warm_loss
        torch.cuda.synchronize()
        for steps in cfg['prefix_steps']:
            torch.cuda.reset_peak_memory_stats()
            t = time.perf_counter()
            x, delta = scope['pgd_attack_lamda'](images['cover'].clone(), images['reference'].clone(), vae,
                lamda=cfg['lambda'], alpha=cfg['alpha'], iters=steps, delta=0)
            torch.cuda.synchronize()
            elapsed = time.perf_counter()-t
            if not torch.isfinite(x).all() or not torch.isfinite(delta).all():
                raise RuntimeError('Nonfinite output')
            if any(p.grad is not None for p in vae.parameters()):
                raise RuntimeError('Unexpected parameter gradient accumulation')
            stem = label+'_'+str(steps)
            np.save(output/(stem+'.npy'), x.detach().cpu().numpy(), allow_pickle=False)
            np.save(output/(stem+'_delta.npy'), delta.detach().cpu().numpy(), allow_pickle=False)
            scope['save_img'](x, output/(stem+'.png'))
            results[stem] = dict(seconds=elapsed, peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                parameters_require_grad=any(p.requires_grad for p in vae.parameters()),
                png_sha256=sha(output/(stem+'.png')))
            write(output/(stem+'_timing.json'), results[stem])
            del x, delta
            print('PREFIX_COMPLETED', stem, flush=True)
    # Fixed endpoint diagnostics are proxy-only and do not select an output.
    final = torch.from_numpy(np.load(output/'native_100.npy', allow_pickle=False)).to('cuda:0')
    with torch.no_grad():
        zr = vae.encode(images['reference']).latent_dist.mode() * (1./vae.config.scaling_factor)
        zc = vae.encode(images['cover']).latent_dist.mode() * (1./vae.config.scaling_factor)
        zf = vae.encode(final).latent_dist.mode() * (1./vae.config.scaling_factor)
        initial_mse = torch.nn.functional.mse_loss(zc,zr).item()
        final_mse = torch.nn.functional.mse_loss(zf,zr).item()
        pixel_mse = torch.nn.functional.mse_loss(final,images['cover']).item()
    import math
    if not all(math.isfinite(x) for x in [initial_mse,final_mse,pixel_mse]):
        raise RuntimeError('Nonfinite endpoint diagnostic')
    write(output/'candidate_frozen.json', dict(files=[dict(path=p.name,sha256=sha(p)) for p in sorted(output.glob('*.png'))],purpose='Fixed 100-update timing endpoint; no target evaluation or selection'))
    write(output/'summary.json', dict(completed=True,timings=results,model_load_seconds=load_seconds,
        proxy_initial_latent_mse=initial_mse,proxy_final_latent_mse=final_mse,pixel_mse_minus1_to1=pixel_mse,
        proxy_final_total=final_mse+cfg['lambda']*pixel_mse,
        vae_scaling_factor=vae.config.scaling_factor,target_calls=0,full_defense_acceptance=None,
        protocol_sha256=sha(protocol_path),scope='One fixed 100-step development timing endpoint; no performance or transfer conclusion'))
    print('COMPLETED_VAE_TIMING',flush=True)


if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]),Path(sys.argv[2]))
