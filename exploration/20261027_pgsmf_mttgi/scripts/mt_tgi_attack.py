"""MT-TGI pilot attacker (V3 = MT-Traj, V4 = MT-TGI-Full).

Read-only w.r.t. all existing assets; writes only under runs/pilot_mt_tgi_20261028/.
Everything outside the optimizer is identical to Stage31 / pg_smf: same proxy
snapshot, same 50-step DDIM inverse (t = 1,21,...,981), prompt "", guidance 1.0,
same RGB01 reference path, same Adam(lr=0.01), same determinism.

Multi-horizon anchors are captured by wrapping the inverse scheduler's step(),
so the final target tensor is produced by the untouched official invert_image()
code path and must be bit-identical to Stage31 reference_proxy_inverse.npy.
"""
import os, sys, json, time, hashlib, argparse
from pathlib import Path

ROOT = Path('/data0/liyanlei/watermark_research')
PILOT = ROOT / 'runs/pilot_mt_tgi_20261028'
SRC = ROOT / 'runs/31_native_calibration_20261024T190323Z'
UP = ROOT / 'third_party/semantic-forgery'
PROXY_SNAPSHOT = ('/data0/liyanlei/watermark_research/cache/huggingface/hub/'
                  'models--Manojb--stable-diffusion-2-1-base/snapshots/'
                  '0094d483a120f3f33dafbd187ea4aa60d10de75c')

sys.path.insert(0, str(ROOT / 'scripts/cover_pilot'))
import runtime as r

POINTS = (10, 20, 30, 50)
TOTAL = 50
LR = 0.01
IDX_MID1, IDX_MID2 = 24, 37          # t = 481, 741
W_FIN, W_M2, W_M1 = 0.70, 0.20, 0.10
COS_W = 0.25


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


class TrajCapture:
    """Wrap inverse_scheduler.step to record latents at given 0-based step indices."""

    def __init__(self, sched, idxs):
        self.sched = sched
        self.idxs = set(idxs)
        self.i = -1
        self.store = {}
        self._orig = sched.step
        sched.step = self.hook

    def reset(self):
        self.i = -1
        self.store = {}

    def hook(self, noise_pred, t, latents, **kw):
        out = self._orig(noise_pred, t, latents, **kw)
        self.i += 1
        if self.i in self.idxs:
            z = out[0] if isinstance(out, tuple) else out.samples
            self.store[self.i] = z
        return out


def gate(uuid, index, out):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', required=True, choices=['v3', 'v4'])
    ap.add_argument('--task', type=int, required=True, choices=[1, 2])
    ap.add_argument('--uuid', required=True)
    ap.add_argument('--index', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--smoke', action='store_true')
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    gate(a.uuid, a.index, out)

    import typing
    import numpy as np
    import torch
    import torch.nn.functional as F
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

    job = json.loads((SRC / 'attack_inputs' / str(a.task) / 'job.json').read_text())
    inp = SRC / 'attack_inputs' / str(a.task)
    for kind in ('reference', 'cover'):
        if job[kind].get('sha256') and sha(inp / (kind + '.png')) != job[kind]['sha256']:
            raise ValueError(f'{kind}.png differs from Stage31 job.json')

    t0 = time.perf_counter()
    pipe, scheduler, inverse = scope['load_attacker_pipe'](
        modelid=PROXY_SNAPSHOT, scheduler='DDIM', device='cuda:0')
    diff = scope['DiffPipe'](pipe, scheduler=inverse, device='cuda:0')
    inverse.set_timesteps(50, device='cuda:0')
    ts = inverse.timesteps.tolist()
    if ts != list(range(1, 982, 20)):
        raise ValueError('Unexpected inverse timesteps')
    if (ts[IDX_MID1], ts[IDX_MID2], ts[-1]) != (481, 741, 981):
        raise ValueError('Anchor timestep mismatch')
    cap = TrajCapture(inverse, (IDX_MID1, IDX_MID2))
    torch.cuda.synchronize()
    load_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    with PIL.Image.open(inp / 'cover.png') as im:
        cover = im.convert('RGB')
    with PIL.Image.open(inp / 'reference.png') as im:
        reference = im.convert('RGB')
    with torch.no_grad():
        z0_init = scope['pixel_to_latent'](cover, pipe).detach()
    gen = px['PIL_to_torch']([reference], dtype=torch.float32, device='cuda:0')
    if gen.min() < 0 or gen.max() > 1:
        raise ValueError('Official RGB01 reference path violated')

    cap.reset()
    with torch.no_grad():
        tgt_final = scope['invert_image'](pipe=pipe, image_pt=gen, scheduler=inverse,
                                          num_inference_steps=50)
    tgt_mid1 = cap.store[IDX_MID1].detach()
    tgt_mid2 = cap.store[IDX_MID2].detach()
    cap.reset()
    torch.cuda.synchronize()
    prep_s = time.perf_counter() - t1

    # bit-identity contract vs Stage31
    ref_np = np.load(SRC / f'attack_{a.task}' / 'reference_proxy_inverse.npy')
    got = tgt_final.detach().cpu().numpy()
    if not np.array_equal(ref_np, got):
        d = float(np.max(np.abs(ref_np.astype(np.float64) - got.astype(np.float64))))
        raise AssertionError(f'tgt_final not bit-identical to Stage31 (max|diff|={d})')

    r.tensor(out / 'initial_z0.npy', z0_init)
    r.tensor(out / 'reference_proxy_inverse.npy', tgt_final)
    r.tensor(out / 'target_mid1_t481.npy', tgt_mid1)
    r.tensor(out / 'target_mid2_t741.npy', tgt_mid2)

    # ---------------- V4 mask (fixed, RMS == 1) ----------------
    mask_info = None
    if a.variant == 'v4':
        with torch.no_grad():
            cov_t = px['PIL_to_torch']([cover], dtype=torch.float32, device='cuda:0')
            patches = cov_t.unfold(2, 8, 8).unfold(3, 8, 8)
            rgb_std = patches.std(dim=(-2, -1)).mean(dim=1, keepdim=True)
            rgb_std = F.avg_pool2d(F.pad(rgb_std, (1, 1, 1, 1), mode='replicate'),
                                   kernel_size=3, stride=1)
            raw = 0.55 + torch.pow(rgb_std / (rgb_std.mean() + 1e-8), 0.75)
            m_tex = raw / torch.sqrt(torch.mean(raw ** 2))
            ch_raw = torch.tensor([1.12, 1.04, 0.86, 0.98], device='cuda',
                                  dtype=torch.float32).view(1, 4, 1, 1)
            m_ch = ch_raw / torch.sqrt(torch.mean(ch_raw ** 2))
            M_total = m_tex * m_ch
            mask_info = dict(rms=float(torch.sqrt(torch.mean(M_total ** 2))),
                             tex_min=float(m_tex.min()), tex_max=float(m_tex.max()),
                             ch=[float(x) for x in m_ch.flatten()])
            r.tensor(out / 'M_tex.npy', m_tex)
            r.tensor(out / 'M_total.npy', M_total)

    def align(pred, tgt):
        mse = F.mse_loss(pred, tgt)
        cs = F.cosine_similarity(pred.flatten(1), tgt.flatten(1), dim=1).mean()
        return mse + COS_W * (1.0 - cs), float(mse.detach()), float(cs.detach())

    if a.variant == 'v3':
        param = torch.nn.Parameter(z0_init.detach().clone())
        optim = torch.optim.Adam([param], lr=LR)
    else:
        param = torch.nn.Parameter(torch.zeros_like(z0_init))
        optim = torch.optim.Adam([param], lr=LR)

    def current():
        return param if a.variant == 'v3' else (z0_init + M_total * param)

    hist, images = [], {}
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    t2 = time.perf_counter()
    steps = 3 if a.smoke else TOTAL
    for step in range(1, steps + 1):
        tick = time.perf_counter()
        optim.zero_grad()
        z0_curr = current()
        cap.reset()
        z_final = diff(z0_curr, '', guidance_scale=1.)
        z_mid1 = cap.store[IDX_MID1]
        z_mid2 = cap.store[IDX_MID2]
        l1, m1, c1 = align(z_mid1, tgt_mid1)
        l2, m2, c2 = align(z_mid2, tgt_mid2)
        lf, mf, cf = align(z_final, tgt_final)
        l = W_FIN * lf + W_M2 * l2 + W_M1 * l1
        l.backward()
        if not torch.isfinite(param.grad).all():
            raise RuntimeError('Nonfinite gradient')
        gnorm = float(param.grad.norm())
        optim.step()
        with torch.no_grad():
            z0_now = current()
            if not torch.isfinite(z0_now).all():
                raise RuntimeError('Nonfinite latent')
            d = (z0_now - z0_init)
            n2, ni = float(d.norm()), float(d.abs().max())
        torch.cuda.synchronize()
        hist.append(dict(step=step, loss=float(l.detach()),
                         l_final=float(lf.detach()), l_mid2=float(l2.detach()),
                         l_mid1=float(l1.detach()),
                         mse_final=mf, cos_final=cf, mse_mid2=m2, cos_mid2=c2,
                         mse_mid1=m1, cos_mid1=c1,
                         grad_norm=gnorm, dz_l2=n2, dz_inf=ni,
                         seconds=time.perf_counter() - tick))
        print(f'STEP {step} loss={float(l.detach()):.6f} cosF={cf:.5f} dz2={n2:.3f}', flush=True)
        if step in POINTS:
            rec = r.tensor(out / f'update_{step}_latent.npy', z0_now)
            img = scope['latent_to_pil'](z0_now, pipe)[0]
            with (out / f'update_{step}.png').open('xb') as f:
                img.save(f, format='PNG')
            images[str(step)] = rec

    torch.cuda.synchronize()
    opt_s = time.perf_counter() - t2

    if not a.smoke:
        write_x(out / 'losses.json', dict(variant=a.variant, task=a.task, steps=TOTAL,
                                          lr=LR, weights=[W_FIN, W_M2, W_M1], cos_w=COS_W,
                                          anchors=[IDX_MID1, IDX_MID2], history=hist))
        write_x(out / 'summary.json', dict(
            completed=True, variant=a.variant, task=a.task, steps=TOTAL, points=list(POINTS),
            images=images, script_sha256=sha(__file__), proxy_snapshot=PROXY_SNAPSHOT,
            seed=seed, lr=LR, weights=dict(final=W_FIN, mid2=W_M2, mid1=W_M1), cos_w=COS_W,
            anchors=dict(mid1_idx=IDX_MID1, mid1_t=481, mid2_idx=IDX_MID2, mid2_t=741),
            tgt_final_bit_identical_to_stage31=True, mask=mask_info,
            timing=dict(model_load_seconds=load_s, preparation_seconds=prep_s,
                        optimization_seconds=opt_s, core_seconds=prep_s + opt_s,
                        peak_allocated_bytes=torch.cuda.max_memory_allocated()),
            target_scores_seen=0))
    print('MT_TGI_ATTACK_DONE', flush=True)


if __name__ == '__main__':
    main()
