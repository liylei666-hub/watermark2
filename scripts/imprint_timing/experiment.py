"""Record native Imprint checkpoints and their delivery paths; no target evaluator."""
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
    import time
    torch.cuda.synchronize()
    loading_start = time.perf_counter()
    snapshot = cfg['model_snapshot']
    scheduler = DDIMScheduler.from_pretrained(snapshot, subfolder='scheduler', local_files_only=True)
    inverse = DDIMInverseScheduler.from_pretrained(snapshot, subfolder='scheduler', local_files_only=True)
    pipe = StableDiffusionPipeline.from_pretrained(snapshot, scheduler=scheduler,
        safety_checker=None, local_files_only=True, torch_dtype=torch.float32).to('cuda:0')
    torch.cuda.synchronize()
    loading_seconds = time.perf_counter()-loading_start
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

    torch.cuda.synchronize()
    setup_start = time.perf_counter()
    with torch.no_grad():
        target = pipeline_inverse(encode(reference)).detach()
        z_init = encode(cover).detach()
    torch.cuda.synchronize()
    setup_seconds = time.perf_counter()-setup_start
    write(output / 'runtime.json', dict(device='cuda:0', gpu_uuid=os.environ['CUDA_VISIBLE_DEVICES'],
        name=torch.cuda.get_device_name(0), model_snapshot=snapshot, dtype=str(z_init.dtype),
        latent_shape=list(z_init.shape), scaling_factor=pipe.vae.config.scaling_factor,
        protocol_sha256=sha(protocol_path), deterministic_algorithms=torch.are_deterministic_algorithms_enabled(),
        cudnn_deterministic=torch.backends.cudnn.deterministic, cublas_workspace=os.environ['CUBLAS_WORKSPACE_CONFIG'],
        reference_proxy_noise=save_tensor(output, 'reference_proxy_noise', target)))
    z = torch.nn.Parameter(z_init.clone())
    optimizer = torch.optim.Adam([z], lr=cfg['learning_rate'])

    def observe(step):
        folder = output / ('checkpoint_' + str(step))
        folder.mkdir()
        before = z.detach().clone()
        arrays = {}
        # Preserve CUDA/CPU RNG; no optimizer operations in the observer.
        with torch.random.fork_rng(devices=[0]), torch.no_grad():
            frozen = before.clone()
            native = internal(frozen)
            pipeline_value = pipeline_inverse(frozen)
            equivalent = torch.allclose(native, pipeline_value, atol=cfg['atol'], rtol=cfg['rtol'])
            write(folder / 'inversion_equivalence.json', dict(allclose=equivalent,
                max_abs=float((native - pipeline_value).abs().max().cpu()),
                atol=cfg['atol'], rtol=cfg['rtol']))
            if not equivalent:
                raise RuntimeError('DiffPipe/pipeline equivalence gate failed')
            raw = pipe.vae.decode(frozen / pipe.vae.config.scaling_factor, return_dict=False)[0]
            floats = (raw * .5 + .5).clamp(0, 1)
            float_z = encode(2 * floats - 1)
            image = namespace['latent_to_pil'](frozen, pipe)[0]
            from_same_decode = to_pil_image(floats[0])
            if not np.array_equal(np.asarray(image), np.asarray(from_same_decode)):
                raise RuntimeError('Repeated decode/PIL changed pixels')
            path = folder / 'candidate.png'
            with path.open('xb') as f:
                image.save(f, format='PNG')
            reread = PIL.Image.open(path).convert('RGB')
            if not np.array_equal(np.asarray(image), np.asarray(reread)):
                raise RuntimeError('PNG readback changed pixels')
            write(folder / 'candidate_frozen.json', dict(sha256=sha(path), size=list(reread.size),
                pixel_readback_equal=True, step=step, selection='predefined_checkpoint'))
            png_z = encode(reread)
            float_noise = internal(float_z)
            png_noise = internal(png_z)
            replay = internal(frozen)
            replay_equal = torch.equal(native, replay)
            for name, value in [('z', frozen), ('internal_noise', native), ('float_z', float_z),
                                ('png_z', png_z), ('float_noise', float_noise), ('png_noise', png_noise)]:
                arrays[name] = save_tensor(folder, name, value)
            metrics = dict(step=step, internal_loss=mse(native, target), float_delivery_loss=mse(float_noise, target),
                png_delivery_loss=mse(png_noise, target), float_latent_displacement=mse(float_z, frozen),
                png_latent_displacement=mse(png_z, frozen), quantization_latent_displacement=mse(png_z, float_z),
                cover_pixel_mse=mse(to_tensor(reread), to_tensor(cover)),
                reference_pixel_mse=mse(to_tensor(reread), to_tensor(reference)),
                content_pass=None, forgery_scope_pass=None, target_score=None, full_defense_accepted=None,
                internal_replay_bitwise_equal=replay_equal, arrays=arrays)
            write(folder / 'metrics.json', metrics)
            if not replay_equal:
                raise RuntimeError('Observer replay gate failed')
        if not torch.equal(z.detach(), before):
            raise RuntimeError('Observer mutated optimized latent')
        return metrics

    target_control = torch.from_numpy(np.load(cfg['inputs']['reference_proxy_noise_control']['path'], allow_pickle=False)).to('cuda:0')
    initial_control = torch.from_numpy(np.load(cfg['inputs']['initial_latent_control']['path'], allow_pickle=False)).to('cuda:0')
    initial_equal = torch.equal(z.detach(), initial_control)
    reference_equal = torch.equal(target, target_control)
    write(output / 'initial_control.json', dict(initial_latent_bitwise_equal=initial_equal,
        reference_proxy_noise_bitwise_equal=reference_equal))
    if not initial_equal or not reference_equal:
        raise RuntimeError('Shadow initial state differs from recorded run')
    rows = []
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    optimize_start = time.perf_counter()
    for step in range(1, cfg['optimization_steps'] + 1):
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(internal(z), target)
        loss.backward()
        optimizer.step()
    torch.cuda.synchronize()
    optimize_seconds = time.perf_counter()-optimize_start
    write(output/'timing.json', dict(model_loading_seconds=loading_seconds, reference_inversion_and_cover_encoding_seconds=setup_seconds, ten_native_updates_seconds=optimize_seconds, peak_allocated_bytes=torch.cuda.max_memory_allocated(), timing_excludes_final_equivalence_checks_and_observer=True))
    expected_final = torch.from_numpy(np.load(cfg['inputs']['final_latent_control']['path'], allow_pickle=False)).to('cuda:0')
    equal = torch.equal(z.detach(), expected_final)
    write(output / 'trajectory_control.json', dict(final_latent_bitwise_equal=equal,
        max_abs=float((z.detach() - expected_final).abs().max().cpu()),
        scope='Same initialization and ten native updates; no gradient probes or intermediate observers'))
    if not equal:
        raise RuntimeError('Full trajectory differs with intermediate recording removed')
    rows.append(observe(cfg['optimization_steps']))
    write(output / 'summary.json', dict(checkpoints=rows, target_model_loaded=False,
        target_scores_used=False, full_defense_acceptance=None, optimized_objective='official_native_latent_mse',
        generation_calls=0, optimization_steps=cfg['optimization_steps']))
    print('COMPLETED_IMPRINT_TIMING', flush=True)


if __name__ == '__main__':
    import sys
    main(Path(sys.argv[1]), Path(sys.argv[2]))
