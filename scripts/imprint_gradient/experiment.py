"""Measure two fixed-point proxy gradients and finite differences; no optimization."""
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
    # Only latent z is optimized. Frozen text encoder avoids accumulating unused gradients.
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

    def float_reencode(value):
        raw = pipe.vae.decode(value / pipe.vae.config.scaling_factor, return_dict=False)[0]
        return encode(2 * (raw * .5 + .5).clamp(0, 1) - 1)

    def loss_value(value, objective):
        return torch.nn.functional.mse_loss(internal(value if objective == 'internal' else float_reencode(value)), target)

    from measures import summarize_gradients
    rows = []
    for point in cfg['points']:
        step = point['step']
        folder = output / ('point_' + str(step))
        folder.mkdir()
        z = torch.from_numpy(np.load(cfg['inputs'][point['latent']]['path'], allow_pickle=False)).to('cuda:0').requires_grad_(True)
        if z.dtype != torch.float32 or tuple(z.shape) != (1, 4, 64, 64) or not torch.isfinite(z).all():
            raise ValueError('Invalid saved latent')
        baseline = {}
        baseline_arrays = {}
        with torch.no_grad():
            for objective, old_name in [('internal', 'internal_noise'), ('float', 'float_noise')]:
                value = internal(z if objective == 'internal' else float_reencode(z))
                expected = torch.from_numpy(np.load(cfg['inputs'][point[old_name]]['path'], allow_pickle=False)).to('cuda:0')
                if not torch.equal(value, expected):
                    raise RuntimeError('Fixed point forward differs from saved stage10 tensor')
                baseline[objective] = mse(value, target)
                baseline_arrays[objective] = save_tensor(folder, objective + '_noise', value)
        gradients = {}
        gradient_arrays = {}
        backward_losses = {}
        for objective in ['internal', 'float']:
            z.grad = None
            loss = loss_value(z, objective)
            backward_losses[objective] = float(loss.detach().cpu())
            loss.backward()
            if z.grad is None or not torch.isfinite(z.grad).all():
                raise RuntimeError('Invalid fixed-point gradient')
            gradients[objective] = z.grad.detach().clone()
            gradient_arrays[objective] = save_tensor(folder, objective + '_gradient', gradients[objective])
            del loss
        metrics = summarize_gradients(*(gradients[k].cpu().numpy() for k in ['internal', 'float']))
        write(folder / 'gradients.json', dict(step=step, baseline=baseline,
            baseline_arrays=baseline_arrays, backward_losses=backward_losses,
            gradient_arrays=gradient_arrays, metrics=metrics))
        probes = []
        for name, gradient in gradients.items():
            rms = gradient.square().mean().sqrt()
            if not torch.isfinite(rms) or rms <= 0:
                raise RuntimeError('Cannot normalize gradient')
            direction = gradient / rms
            direction_record = save_tensor(folder, name + '_direction', direction)
            analytic = {key: float((g.double() * direction.double()).sum().cpu()) for key, g in gradients.items()}
            observed = {}
            for sign in [-1, 1]:
                with torch.no_grad():
                    perturbed = z.detach() + sign * cfg['probe_rms_radius'] * direction
                    image = namespace['latent_to_pil'](perturbed, pipe)[0]
                    path = folder / (name + ('_minus.png' if sign == -1 else '_plus.png'))
                    with path.open('xb') as file:
                        image.save(file, format='PNG')
                    reread = PIL.Image.open(path).convert('RGB')
                    if not np.array_equal(np.asarray(image), np.asarray(reread)):
                        raise RuntimeError('Probe PNG readback differs')
                    image_hash = sha(path)
                    # Freeze the probe image before its proxy measurements. No target calls occur.
                    write(path.with_suffix('.json'), dict(sha256=image_hash, role='predefined_directional_probe',
                        point_step=step, direction=name, sign=sign, radius=cfg['probe_rms_radius']))
                    native_noise = internal(perturbed)
                    float_noise = internal(float_reencode(perturbed))
                    png_noise = internal(encode(reread))
                    observed[str(sign)] = dict(internal=mse(native_noise, target),
                        float=mse(float_noise, target), png=mse(png_noise, target), png_sha256=image_hash,
                        arrays={key: save_tensor(folder, path.stem + '_' + key, value) for key, value in
                            [('latent', perturbed), ('internal_noise', native_noise), ('float_noise', float_noise), ('png_noise', png_noise)]})
            finite = {key: (observed['1'][key] - observed['-1'][key]) / (2 * cfg['probe_rms_radius'])
                      for key in ['internal', 'float', 'png']}
            agreement = {key: abs(finite[key] - analytic[key]) <= cfg['fd_atol'] + cfg['fd_rtol'] * abs(analytic[key])
                         for key in ['internal', 'float']}
            probes.append(dict(direction=name, direction_array=direction_record,
                analytic_derivatives=analytic, finite_difference_derivatives=finite,
                finite_difference_agreement=agreement, signed_probes=observed))
        row = dict(step=step, baseline=baseline, gradient_metrics=metrics, probes=probes,
            target_score=None, full_defense_accepted=None, optimization_updates=0)
        write(folder / 'summary.json', row)
        rows.append(row)
        print('COMPLETED_POINT', step, flush=True)
    write(output / 'summary.json', dict(points=rows, optimization_updates=0,
        target_model_loaded=False, target_scores_used=False, full_defense_acceptance=None,
        probe_images=8, method='Fixed central differences and exact float-path autograd; no PNG gradient approximation'))
    print('COMPLETED_IMPRINT_GRADIENT_DIAGNOSTIC', flush=True)


if __name__ == '__main__':
    import sys
    main(Path(sys.argv[1]), Path(sys.argv[2]))
