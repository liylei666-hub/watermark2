"""Localize existing finite-difference residuals through a split chain-rule measurement."""
import ast
import hashlib
import json
import os
from pathlib import Path


EXPORTS = {'DiffPipe', 'UnetWrapper', 'latent_to_pil', 'pixel_to_latent'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)


def extract_definitions(path, expected_sha):
    if sha(path) != expected_sha:
        raise ValueError('Upstream helper hash changed')
    source = ast.parse(Path(path).read_bytes())
    nodes = [n for n in source.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
             and n.name in EXPORTS]
    if {n.name for n in nodes} != EXPORTS or len(nodes) != len(EXPORTS):
        raise ValueError('Expected helper definitions missing')
    return ast.Module(body=nodes, type_ignores=[])


def check_binding(config):
    visible = os.environ.get('CUDA_VISIBLE_DEVICES', '')
    if visible not in config['allowed_gpu_uuids'].values():
        raise ValueError('Expected one authorized GPU UUID')
    if os.environ.get('CUDA_DEVICE_ORDER') != 'PCI_BUS_ID':
        raise ValueError('Device order is not bound')
    for name in ['HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE']:
        if os.environ.get(name) != '1':
            raise ValueError('Offline mode required')


def main(protocol_path, output):
    cfg = json.loads(protocol_path.read_text())
    check_binding(cfg)  # Before any CUDA-capable import.
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise ValueError("Deterministic cuBLAS workspace required")
    import csv
    import subprocess
    uuid = os.environ['CUDA_VISIBLE_DEVICES']
    row = next(csv.reader([subprocess.check_output(['nvidia-smi', '-i', uuid,
        '--query-gpu=index,uuid,name,memory.used,utilization.gpu',
        '--format=csv,noheader,nounits'], text=True).strip()], skipinitialspace=True))
    apps = list(csv.reader(subprocess.check_output(['nvidia-smi',
        '--query-compute-apps=gpu_uuid,pid,used_gpu_memory',
        '--format=csv,noheader,nounits'], text=True).splitlines(), skipinitialspace=True))
    selected_apps = [a for a in apps if a and a[0] == uuid]
    write(output / 'device_preimport.json', dict(row=row, compute_apps=selected_apps))
    if (cfg['allowed_gpu_uuids'].get(row[0]) != row[1] or row[2] != 'NVIDIA GeForce RTX 3090'
            or int(row[3]) > 50 or int(row[4]) != 0 or selected_apps):
        raise RuntimeError('GPU is not verified idle before CUDA imports')
    for name, record in cfg['inputs'].items():
        if sha(record['path']) != record['sha256']:
            raise ValueError('Input hash mismatch: ' + name)
    for name, expected in cfg['code_hashes'].items():
        if sha(name) != expected:
            raise ValueError('Code hash mismatch')
    import importlib.metadata
    for name, expected in cfg['versions'].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError('Package version mismatch: ' + name)
    import typing
    import numpy as np
    import torch
    import PIL.Image
    from torchvision.transforms.functional import to_pil_image, to_tensor
    from torch.utils.checkpoint import checkpoint
    from diffusers import StableDiffusionPipeline, DDIMScheduler, DDIMInverseScheduler
    from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import retrieve_timesteps, rescale_noise_cfg
    if torch.cuda.device_count() != 1:
        raise RuntimeError('Expected one visible device')
    torch.cuda.set_device(0)
    torch.manual_seed(cfg['seed'])
    torch.cuda.manual_seed_all(cfg['seed'])
    np.random.seed(cfg['seed'])
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    namespace = dict(torch=torch, PIL=PIL, Optional=typing.Optional, Union=typing.Union,
                     List=typing.List, checkpoint=checkpoint, to_tensor=to_tensor,
                     to_pil_image=to_pil_image, retrieve_timesteps=retrieve_timesteps,
                     rescale_noise_cfg=rescale_noise_cfg)
    helper = cfg['inputs']['helper']
    exec(compile(extract_definitions(helper['path'], helper['sha256']), helper['path'], 'exec'), namespace)
    snapshot = cfg['model_snapshot']
    scheduler = DDIMScheduler.from_pretrained(snapshot, subfolder='scheduler', local_files_only=True)
    inverse = DDIMInverseScheduler.from_pretrained(snapshot, subfolder='scheduler', local_files_only=True)
    pipe = StableDiffusionPipeline.from_pretrained(snapshot, scheduler=scheduler,
        safety_checker=None, local_files_only=True, torch_dtype=torch.float32).to('cuda:0')
    pipe.set_progress_bar_config(disable=True)
    # Only input derivatives are requested; all model parameters remain frozen.
    pipe.text_encoder.requires_grad_(False)
    pipe.vae.requires_grad_(False)
    diff = namespace['DiffPipe'](pipe, scheduler=inverse, device='cuda:0')
    cover = PIL.Image.open(cfg['inputs']['cover']['path']).resize((512, 512)).convert('RGB')
    reference = PIL.Image.open(cfg['inputs']['reference']['path']).convert('RGB')
    if reference.size != (512, 512):
        raise ValueError('Reference size mismatch')
    encode = lambda im: namespace['pixel_to_latent'](im, pipe)

    def pipeline_inverse(z):
        old = pipe.scheduler
        pipe.scheduler = inverse
        try:
            return pipe(latents=z, num_inference_steps=50, prompt=[''], negative_prompt=[''],
                        guidance_scale=1., width=512, height=512,
                        output_type='latent', return_dict=False)[0]
        finally:
            pipe.scheduler = old

    def internal(z):
        return diff(z, '', guidance_scale=1., num_inference_steps=50)

    def mse(a, b):
        return float(torch.nn.functional.mse_loss(a, b).detach().cpu())

    def save_tensor(folder, name, value):
        arr = value.detach().cpu().contiguous().numpy()
        if arr.dtype != np.float32 or not np.isfinite(arr).all():
            raise ValueError('Nonfinite or non-float32 tensor')
        path = folder / (name + '.npy')
        with path.open('xb') as f:
            np.save(f, arr, allow_pickle=False)
        return dict(sha256=sha(path), shape=list(arr.shape), dtype=str(arr.dtype))

    with torch.no_grad():
        target = pipeline_inverse(encode(reference)).detach()
        z_init = encode(cover).detach()
    write(output / 'runtime.json', dict(device='cuda:0', gpu_uuid=os.environ['CUDA_VISIBLE_DEVICES'],
        name=torch.cuda.get_device_name(0), model_snapshot=snapshot, dtype=str(z_init.dtype),
        latent_shape=list(z_init.shape), scaling_factor=pipe.vae.config.scaling_factor,
        protocol_sha256=sha(protocol_path), deterministic_algorithms=torch.are_deterministic_algorithms_enabled(),
        cudnn_deterministic=torch.backends.cudnn.deterministic, cublas_workspace=os.environ['CUBLAS_WORKSPACE_CONFIG'],
        reference_proxy_noise=save_tensor(output, 'reference_proxy_noise', target)))
    reference_control = torch.from_numpy(np.load(cfg['inputs']['reference_control']['path'], allow_pickle=False)).to('cuda:0')
    if not torch.equal(target, reference_control):
        raise RuntimeError('Reference proxy inversion differs from stage10')

    def mapped(value):
        raw = pipe.vae.decode(value / pipe.vae.config.scaling_factor, return_dict=False)[0]
        pixels = raw * .5 + .5
        encoded = encode(2 * pixels.clamp(0, 1) - 1)
        return encoded, pixels

    def save_branch(folder, name, pixels):
        a = pixels.detach().cpu().numpy()
        if not np.isfinite(a).all():
            raise ValueError('Nonfinite decoded pixels')
        # Exact boundary coordinates retain clamp's interior derivative convention.
        branches = np.where(a < 0, 0, np.where(a > 1, 2, 1)).astype(np.uint8)
        path = folder / (name + '_branches.npz')
        with path.open('xb') as file:
            np.savez_compressed(file, branches=branches)
        return dict(sha256=sha(path), shape=list(branches.shape),
            raw_min=float(a.min()), raw_max=float(a.max()),
            exact_boundary_coordinates=int(np.count_nonzero((a == 0) | (a == 1))))

    def supplied(key):
        a = np.load(cfg['inputs'][key]['path'], allow_pickle=False)
        if a.dtype != np.float32 or a.shape != (1, 4, 64, 64) or not np.isfinite(a).all():
            raise ValueError('Invalid supplied array: ' + key)
        return torch.from_numpy(a).to('cuda:0')

    rows = []
    for point in cfg['points']:
        step = point['step']
        folder = output / ('point_' + str(step))
        folder.mkdir()
        z = supplied(point['latent']).requires_grad_(True)
        with torch.no_grad():
            base_y, base_pixels = mapped(z)
            if not torch.equal(base_y, supplied(point['encoded_latent'])):
                raise RuntimeError('Base VAE mapping differs from stage10')
            base_record = save_tensor(folder, 'encoded_latent', base_y)
            branch_record = save_branch(folder, 'baseline', base_pixels)
        y_leaf = base_y.detach().requires_grad_(True)
        noise = internal(y_leaf)
        if not torch.equal(noise.detach(), supplied(point['float_noise'])):
            raise RuntimeError('Inverse forward differs from stage11')
        loss = torch.nn.functional.mse_loss(noise, target)
        loss.backward()
        if y_leaf.grad is None or not torch.isfinite(y_leaf.grad).all():
            raise RuntimeError('Invalid downstream gradient')
        downstream = y_leaf.grad.detach().clone()
        del loss, noise
        gi_record = save_tensor(folder, 'downstream_gradient', downstream)
        mapped_z, _ = mapped(z)
        mapped_z.backward(downstream)
        if z.grad is None or not torch.isfinite(z.grad).all():
            raise RuntimeError('Invalid recomposed gradient')
        previous = supplied(point['float_gradient'])
        chain_record = save_tensor(folder, 'recomposed_gradient', z.grad)
        chain = dict(bitwise_equal=bool(torch.equal(z.grad, previous)),
            allclose=bool(torch.allclose(z.grad, previous, atol=cfg['chain_atol'], rtol=cfg['chain_rtol'])),
            max_abs_difference=float((z.grad-previous).abs().max().cpu()))
        del mapped_z
        probes = []
        for probe in point['probes']:
            with torch.no_grad():
                encoded, pix = mapped(supplied(probe['latent']))
                record = save_tensor(folder, probe['name'] + '_encoded', encoded)
                branch = save_branch(folder, probe['name'], pix)
            probes.append(dict(name=probe['name'], encoded=record, branches=branch))
        row = dict(step=step, encoded_latent=base_record, baseline_branches=branch_record,
            downstream_gradient=gi_record, recomposed_gradient=chain_record,
            chain_comparison=chain, probes=probes)
        write(folder / 'summary.json', row)
        rows.append(row)
        print('COMPLETED_COMPONENT_POINT', step, flush=True)
    write(output / 'summary.json', dict(points=rows, optimization_updates=0,
        target_model_loaded=False, target_scores_used=False, full_defense_acceptance=None,
        new_candidate_images=0, prior_probe_noise_reused=True))
    print('COMPLETED_IMPRINT_COMPONENT_DIAGNOSTIC', flush=True)


if __name__ == '__main__':
    import sys
    main(Path(sys.argv[1]), Path(sys.argv[2]))
