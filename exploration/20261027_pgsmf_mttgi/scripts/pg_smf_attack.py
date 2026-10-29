"""PG-SMF pilot attacker (V1 = PG-Margin, V2 = PG-SMF-Full).

Read-only w.r.t. all existing research assets: only reads Stage31 inputs and the
pinned proxy snapshot; writes exclusively under runs/pilot_pg_smf_20261027/.

Everything outside the optimizer update is byte-identical in spirit to
scripts/native_calibration/attack31.py: same proxy snapshot, same DDIM inverse
scheduler (50 steps, timesteps 1..981), prompt "", guidance 1.0, same
RGB01 reference path, same target tensor, same Adam(lr=0.01), same determinism.
"""
import os, sys, json, time, hashlib, argparse
from pathlib import Path

ROOT = Path('/data0/liyanlei/watermark_research')
PILOT = ROOT / 'runs/pilot_pg_smf_20261027'
SRC = ROOT / 'runs/31_native_calibration_20261024T190323Z'
UP = ROOT / 'third_party/semantic-forgery'
PROXY_SNAPSHOT = ('/data0/liyanlei/watermark_research/cache/huggingface/hub/'
                  'models--Manojb--stable-diffusion-2-1-base/snapshots/'
                  '0094d483a120f3f33dafbd187ea4aa60d10de75c')

sys.path.insert(0, str(ROOT / 'scripts/cover_pilot'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r

POINTS = (10, 20, 30, 50)
TOTAL_STEPS = 50
LR = 0.01
LOSS_SCALE = 4.2
MARGIN_TAU = 0.65
BETA = 3.0
CONF_SCALE = 0.8
CH_W = (1.20, 1.05, 0.80, 0.95)
W_P, W_M, W_H = 0.55, 0.30, 0.15
DAMP = 0.92
CLAMP = 1.15
MASK_R0, MASK_S, MASK_FLOOR = 14.0, 8.0, 0.35


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write_x(p, obj):
    with Path(p).open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write('\n')


def gate(uuid, index, out):
    """Idle-GPU gate: env identity + nvidia-smi + no foreign compute process."""
    import subprocess
    exp = dict(CUDA_VISIBLE_DEVICES=uuid, CUDA_DEVICE_ORDER='PCI_BUS_ID',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               CUBLAS_WORKSPACE_CONFIG=':4096:8')
    bad = {k: (os.environ.get(k), v) for k, v in exp.items() if os.environ.get(k) != v}
    if bad:
        raise ValueError(f'Environment mismatch: {bad}')
    if int(index) == 6:
        raise ValueError('GPU index 6 is forbidden')
    q = subprocess.check_output(['nvidia-smi', '-i', str(index),
                                 '--query-gpu=index,uuid,memory.used,utilization.gpu',
                                 '--format=csv,noheader,nounits'], text=True).strip()
    i, u, mem, util = [x.strip() for x in q.split(',')]
    if u != uuid:
        raise ValueError(f'UUID mismatch: {u} != {uuid}')
    apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                                    '--format=csv,noheader,nounits'], text=True).strip()
    mine = [a for a in apps.splitlines() if a.split(',')[0].strip() == uuid]
    if int(mem) >= 500 or int(util) != 0 or mine:
        raise RuntimeError(f'GPU not idle: mem={mem} util={util} apps={mine}')
    write_x(Path(out) / 'device_gate.json',
            dict(index=int(i), uuid=u, memory_used_mb=int(mem), util=int(util),
                 foreign_apps=mine, checked_at=time.strftime('%Y-%m-%dT%H:%M:%S%z')))


def freq_mask(n=64):
    import torch
    i = torch.arange(n, dtype=torch.float32)
    rad = torch.sqrt((i.view(-1, 1) - n // 2) ** 2 + (i.view(1, -1) - n // 2) ** 2)
    m = torch.where(rad <= MASK_R0, torch.ones_like(rad),
                    MASK_FLOOR + (1 - MASK_FLOOR) * torch.exp(-((rad - MASK_R0) / MASK_S) ** 2))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', required=True, choices=['v1', 'v2'])
    ap.add_argument('--task', type=int, required=True, choices=[1, 2])
    ap.add_argument('--uuid', required=True)
    ap.add_argument('--index', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--smoke', action='store_true')
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    gate(a.uuid, a.index, out)
    script_sha = sha(__file__)

    import typing
    import numpy as np
    import torch
    import PIL.Image
    from torchvision import transforms
    from torchvision.transforms.functional import to_tensor, to_pil_image
    from torch.utils.checkpoint import checkpoint
    from diffusers import (StableDiffusionPipeline, DDIMScheduler, DDIMInverseScheduler,
                           DPMSolverMultistepScheduler, DPMSolverMultistepInverseScheduler)
    from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import (
        retrieve_timesteps, rescale_noise_cfg)

    seed = 31300 + a.task
    r.deterministic(seed)

    scope = dict(typing=typing, torch=torch, PIL=PIL.Image,
                 Optional=typing.Optional, Union=typing.Union, List=typing.List,
                 checkpoint=checkpoint, to_tensor=to_tensor, to_pil_image=to_pil_image,
                 retrieve_timesteps=retrieve_timesteps, rescale_noise_cfg=rescale_noise_cfg,
                 StableDiffusionPipeline=StableDiffusionPipeline,
                 DDIMScheduler=DDIMScheduler, DDIMInverseScheduler=DDIMInverseScheduler,
                 DPMSolverMultistepScheduler=DPMSolverMultistepScheduler,
                 DPMSolverMultistepInverseScheduler=DPMSolverMultistepInverseScheduler)
    r.definitions(UP / 'utils/imprint_utils.py',
                  {'load_attacker_pipe', 'DiffPipe', 'UnetWrapper', 'pixel_to_latent',
                   'latent_to_pil', 'invert_image'}, scope)
    px = dict(typing=typing, torch=torch, Image=PIL.Image, transforms=transforms)
    r.definitions(UP / 'utils/image_utils.py', {'PIL_to_torch'}, px)

    # ---- input identity vs Stage31 job.json
    job = json.loads((SRC / 'attack_inputs' / str(a.task) / 'job.json').read_text())
    inp = SRC / 'attack_inputs' / str(a.task)
    for kind in ('reference', 'cover'):
        rec = job[kind]
        p = inp / (kind + '.png')
        if rec.get('sha256') and sha(p) != rec['sha256']:
            raise ValueError(f'{kind}.png differs from Stage31 job.json')

    t0 = time.perf_counter()
    pipe, scheduler, inverse = scope['load_attacker_pipe'](
        modelid=PROXY_SNAPSHOT, scheduler='DDIM', device='cuda:0')
    diff = scope['DiffPipe'](pipe, scheduler=inverse, device='cuda:0')
    inverse.set_timesteps(50, device='cuda:0')
    ts = inverse.timesteps.tolist()
    if ts != list(range(1, 982, 20)):
        raise ValueError('Unexpected inverse timesteps')
    torch.cuda.synchronize()
    load_s = time.perf_counter() - t0

    fft_ok = True
    try:
        probe = torch.randn(1, 4, 64, 64, device='cuda')
        torch.fft.ifft2(torch.fft.fft2(probe)).real
        torch.cuda.synchronize()
    except Exception:
        torch.use_deterministic_algorithms(True, warn_only=True)
        fft_ok = False

    t1 = time.perf_counter()
    with PIL.Image.open(inp / 'cover.png') as im:
        cover = im.convert('RGB')
    with PIL.Image.open(inp / 'reference.png') as im:
        reference = im.convert('RGB')
    z0_init = scope['pixel_to_latent'](cover, pipe)
    z0 = torch.nn.Parameter(z0_init.detach().clone())
    optim = torch.optim.Adam([z0], lr=LR)
    gen = px['PIL_to_torch']([reference], dtype=torch.float32, device='cuda:0')
    if gen.min() < 0 or gen.max() > 1:
        raise ValueError('Official RGB01 reference path violated')
    with torch.no_grad():
        target = scope['invert_image'](pipe=pipe, image_pt=gen, scheduler=inverse,
                                       num_inference_steps=50)
    torch.cuda.synchronize()
    prep_s = time.perf_counter() - t1

    r.tensor(out / 'initial_z0.npy', z0)
    r.tensor(out / 'reference_proxy_inverse.npy', target)

    chw = torch.tensor(CH_W, device='cuda', dtype=torch.float32).view(1, 4, 1, 1)
    fmask = freq_mask(64).to('cuda') if a.variant == 'v2' else None
    z0_anchor = z0_init.detach().clone()

    hist, images = [], {}
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    t2 = time.perf_counter()
    steps = 3 if a.smoke else TOTAL_STEPS
    for step in range(1, steps + 1):
        tick = time.perf_counter()
        optim.zero_grad()
        inv = diff(z0, '', guidance_scale=1.)

        p_inv = torch.erf(inv / 1.4142135623730951)
        p_tgt = torch.erf(target / 1.4142135623730951)
        l_probit = (p_inv - p_tgt) ** 2
        s_tgt = torch.sign(target)
        conf = torch.tanh(target.abs() / CONF_SCALE)
        l_margin = conf * torch.nn.functional.softplus(BETA * (MARGIN_TAU - s_tgt * inv)) / BETA
        l_huber = torch.nn.functional.smooth_l1_loss(inv, target, beta=1.0, reduction='none')
        l_raw = (chw * (W_P * l_probit + W_M * l_margin + W_H * l_huber)).mean()
        l = LOSS_SCALE * l_raw
        l.backward()
        if not torch.isfinite(z0.grad).all():
            raise RuntimeError('Nonfinite gradient')
        gnorm = float(z0.grad.norm())

        if a.variant == 'v1':
            optim.step()
            d_ratio = -1.0
        else:
            z0_prev = z0.detach().clone()
            optim.step()
            with torch.no_grad():
                step_delta = z0 - z0_prev
                orig_norm = torch.norm(step_delta)
                d_fft = torch.fft.fftshift(torch.fft.fft2(step_delta), dim=(-2, -1))
                filt = torch.fft.ifft2(torch.fft.ifftshift(d_fft * fmask, dim=(-2, -1))).real
                fn = torch.norm(filt).clamp(min=1e-12)
                d_ratio = float(fn / orig_norm.clamp(min=1e-12))
                cal = filt * (DAMP * orig_norm / fn)
                delta = (z0_prev + cal) - z0_anchor
                delta = CLAMP * torch.tanh(delta / CLAMP)
                z0.copy_(z0_anchor + delta)

        if not torch.isfinite(z0).all():
            raise RuntimeError('Nonfinite latent')
        torch.cuda.synchronize()
        el = time.perf_counter() - tick
        hist.append(dict(step=step, loss_scaled=float(l.detach()),
                         loss_raw=float(l_raw.detach()),
                         probit=float(l_probit.mean().detach()),
                         margin=float(l_margin.mean().detach()),
                         huber=float(l_huber.mean().detach()),
                         grad_norm=gnorm, step_delta_l2=float((z0 - z0_prev).norm()) if a.variant == 'v2' else -1.0,
                         spectral_shrink=d_ratio, seconds=el))
        print(f'STEP {step} loss={float(l_raw.detach()):.6f} gnorm={gnorm:.5f}', flush=True)

        if step in POINTS:
            rec = r.tensor(out / f'update_{step}_latent.npy', z0)
            img = scope['latent_to_pil'](z0, pipe)[0]
            with (out / f'update_{step}.png').open('xb') as f:
                img.save(f, format='PNG')
            images[str(step)] = rec

    torch.cuda.synchronize()
    opt_s = time.perf_counter() - t2

    if not a.smoke:
        write_x(out / 'losses.json', dict(variant=a.variant, task=a.task, scale=LOSS_SCALE,
                                          lr=LR, steps=TOTAL_STEPS, history=hist))
        write_x(out / 'summary.json', dict(
            completed=True, variant=a.variant, task=a.task, steps=TOTAL_STEPS,
            points=list(POINTS), images=images, script_sha256=script_sha,
            proxy_snapshot=PROXY_SNAPSHOT, seed=seed, lr=LR, loss_scale=LOSS_SCALE,
            margin_tau=MARGIN_TAU, beta=BETA, conf_scale=CONF_SCALE, ch_weights=list(CH_W),
            spectral=dict(enabled=a.variant == 'v2', r0=MASK_R0, s=MASK_S, floor=MASK_FLOOR,
                          damp=DAMP, clamp=CLAMP, applied_to='adam_step_delta',
                          energy_preserving=True),
            fft_deterministic=fft_ok,
            timing=dict(model_load_seconds=load_s, preparation_seconds=prep_s,
                        optimization_seconds=opt_s, core_seconds=prep_s + opt_s,
                        peak_allocated_bytes=torch.cuda.max_memory_allocated()),
            target_scores_seen=0))
    print('PG_SMF_ATTACK_DONE', flush=True)


if __name__ == '__main__':
    main()
