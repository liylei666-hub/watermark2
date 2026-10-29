"""PG-SMF pilot evaluator: identical SDXL chain to scripts/native_calibration/evaluate31.py.

Reads the pilot attack outputs, inverts every exported PNG with the same SDXL
provider / 50-step DDIM inverse, then computes BA (private GS material),
float64 PSNR, SSIM, MS-MSIM, LPIPS and z_T alignment. Writes only under the
pilot directory.
"""
import os, sys, json, math, time, hashlib, argparse
from pathlib import Path

ROOT = Path('/data0/liyanlei/watermark_research')
PILOT = ROOT / 'runs/pilot_pg_smf_20261027'
SRC = ROOT / 'runs/31_native_calibration_20261024T190323Z'
PRIV = ROOT / 'private_eval/31_native_calibration_20261024T190323Z'
UP = ROOT / 'third_party/semantic-forgery'
LINEAR = ROOT / 'envs/semantic_forgery_py310/lib/python3.10/site-packages/lpips/weights/v0.1/alex.pth'

sys.path.insert(0, str(ROOT / 'scripts/cover_pilot'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r

POINTS = (10, 20, 30, 50)
THR = 0.70703125


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', required=True, choices=['v3', 'v4'])
    ap.add_argument('--task', type=int, required=True, choices=[1, 2])
    ap.add_argument('--uuid', required=True)
    ap.add_argument('--index', required=True)
    ap.add_argument('--attack_dir', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    exp = dict(CUDA_VISIBLE_DEVICES=a.uuid, CUDA_DEVICE_ORDER='PCI_BUS_ID',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    bad = {k: (os.environ.get(k), v) for k, v in exp.items() if os.environ.get(k) != v}
    if bad or int(a.index) == 6:
        raise ValueError(f'Environment/device violation: {bad}')

    import numpy as np
    import torch
    import PIL.Image
    from skimage.metrics import structural_similarity
    from torchmetrics.image import MultiScaleStructuralSimilarityIndexMeasure, PeakSignalNoiseRatio
    import lpips
    import importlib.util

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    att = Path(a.attack_dir)
    r.deterministic(0)

    design = json.loads((ROOT / 'protocols/31_native_calibration_execution.json').read_text())
    provider = r.official_provider(design['target'])
    provider.scheduler_inverse.set_timesteps(50, device='cuda:0')
    ts = provider.scheduler_inverse.timesteps.tolist()
    if ts != list(range(1, 982, 20)):
        raise ValueError('Unexpected target inverse timesteps')

    # private GS material (evaluator-only)
    spec = importlib.util.spec_from_file_location(
        'priv', ROOT / 'scripts/reference_reliability/private_state.py')
    private = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(private)
    rec = json.loads((SRC / 'prepare' / str(a.task) / 'record.json').read_text())
    raw = private.load(PRIV, a.task, rec['encryption_fingerprints'])
    wm = private.provider(raw, 'cuda:0')

    # official LPIPS helper (same function the Stage31 post-hoc tool used)
    src = (UP / 'utils/image_utils.py').read_bytes()
    import ast
    scope = dict(Image=PIL.Image, torch=torch, np=np, lpips=lpips)
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'lpips_PIL')
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(UP / 'utils/image_utils.py'), 'exec'), scope)
    metric = scope['lpips_PIL']
    loss_fn = lpips.LPIPS(net='alex', version='0.1', pretrained=True, pnet_rand=False,
                          model_path=str(LINEAR), eval_mode=True, verbose=False).to('cpu')
    loss_fn.eval()

    with PIL.Image.open(SRC / 'prepare' / str(a.task) / 'cover.png') as im:
        cover = im.convert('RGB').copy()

    items = [('reference', SRC / 'prepare' / str(a.task) / 'reference.png'),
             ('cover', SRC / 'prepare' / str(a.task) / 'cover.png')]
    items += [(str(n), att / f'update_{n}.png') for n in POINTS]

    rows = []
    zref = None
    for label, path in items:
        folder = out / f'{a.task}_{label}'
        folder.mkdir()
        with PIL.Image.open(path) as im:
            image = im.convert('RGB')
        t = time.perf_counter()
        with torch.no_grad():
            z = provider.invert_images(image, num_inference_steps=50)['zT_torch']
        torch.cuda.synchronize()
        inv_s = time.perf_counter() - t
        ba = float(wm.get_accuracies(z)['bit_accuracies'][0])
        if label == 'reference':
            zref = z.detach().clone()
        with torch.no_grad():
            lpv = float(metric(image, cover, loss_fn, torch.device('cpu')))
        aa = np.asarray(image, dtype=np.float64) / 255
        bb = np.asarray(cover, dtype=np.float64) / 255
        mse = float(np.mean((aa - bb) ** 2))
        psnr = None if mse == 0 else -10 * math.log10(mse)
        ssim = float(structural_similarity(np.asarray(image.convert('L')),
                                           np.asarray(cover.convert('L')), data_range=255))
        ta = torch.from_numpy(aa).permute(2, 0, 1).unsqueeze(0).float()
        tb = torch.from_numpy(bb).permute(2, 0, 1).unsqueeze(0).float()
        off_psnr = None if mse == 0 else float(PeakSignalNoiseRatio(data_range=1.0)(ta, tb))
        ms = float(MultiScaleStructuralSimilarityIndexMeasure(data_range=1.0)(ta, tb))
        zd = r.tensor(folder / 'target_inverse.npy', z)
        row = dict(task_id=a.task, variant=a.variant, label=label,
                   image=dict(path=path.name, sha256=sha(path)), inverse=zd, bit_accuracy=ba,
                   gs_detected=bool(ba > THR), mse_rgb01=mse, psnr_db=psnr,
                   official_torchmetrics_psnr_db=off_psnr, psnr_infinite=bool(mse == 0),
                   ssim_grayscale=ssim, ms_ssim_rgb=ms, lpips=lpv,
                   inversion_seconds=inv_s)
        write_x(folder / 'metrics.json', row)
        rows.append(row)
        print('EVAL', a.task, label, f'BA={ba:.6f}', f'PSNR={psnr}', f'LPIPS={lpv:.5f}', flush=True)

    # z_T alignment against the target-side reference inverse
    align = {}
    zref_np = None
    for label in ['reference', 'cover'] + [str(n) for n in POINTS]:
        zz = np.load(out / f'{a.task}_{label}' / 'target_inverse.npy').astype(np.float64)
        if label == 'reference':
            zref_np = zz
        d = zz - zref_np
        align[label] = dict(mse=float(np.mean(d ** 2)),
                            cos=float(np.dot(zz.ravel(), zref_np.ravel()) /
                                      (np.linalg.norm(zz) * np.linalg.norm(zref_np))),
                            sign_agree=float(np.mean(np.sign(zz) == np.sign(zref_np))))

    write_x(out / 'summary.json', dict(completed=True, variant=a.variant, task=a.task,
                                       rows=rows, alignment=align, gs_threshold=THR,
                                       target_model=design['target']['model_id'],
                                       script_sha256=sha(__file__)))
    print('PG_SMF_EVAL_DONE', flush=True)


if __name__ == '__main__':
    main()
