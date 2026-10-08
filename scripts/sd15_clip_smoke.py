"""Real-image smoke test of an explicitly separate SD1.5/CLIP binding configuration."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')


def guard_gpu(cfg):
    uuid = cfg['physical_gpu_uuid']
    assert cfg['physical_gpu'] == 7
    assert uuid == 'GPU-9644fb82-cb6f-7311-8017-eaee41409bb7'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == uuid, 'GPU isolation must precede Python startup'
    cmd = ['nvidia-smi', '-i', '7', '--query-gpu=index,uuid,name,memory.free,utilization.gpu',
           '--format=csv,noheader,nounits']
    gpu = subprocess.check_output(cmd, text=True).strip()
    fields = [x.strip() for x in gpu.split(',')]
    assert fields[0] == '7' and fields[1] == uuid and int(fields[3]) >= 12000, gpu
    procs = subprocess.check_output(['nvidia-smi', '-i', '7',
        '--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader,nounits'], text=True).strip()
    assert not procs, 'GPU7 has a compute process; do not interfere'
    return {'gpu_query': gpu, 'compute_process_query': procs, 'cuda_visible_devices': uuid}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--sd-cache', required=True)
    ap.add_argument('--clip-code', required=True)
    ap.add_argument('--clip-weight', required=True)
    ap.add_argument('--csi-code', required=True)
    ap.add_argument('--csi-inventory', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / 'frozen.json').exists(), 'Never overwrite a frozen run'
    preflight = guard_gpu(cfg)
    # No model loader is reached before the physical GPU check above.
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      DIFFUSERS_OFFLINE='1', WANDB_MODE='disabled', TOKENIZERS_PARALLELISM='false')
    import numpy as np
    import torch
    from PIL import Image
    from diffusers import DDIMScheduler, StableDiffusionPipeline
    assert torch.cuda.device_count() == 1
    assert torch.cuda.get_device_name(0) == 'NVIDIA GeForce RTX 3090'
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    sys.path.insert(0, args.csi_code)
    from csi.backends.sd import StableDiffusionBackend
    from csi.schemes.seal import SealCore
    from csi.types import Key
    inv = json.loads(Path(args.csi_inventory).read_text())
    assert inv['commit'] == '8723e362835a6a61efd11b61f677b3321face3fa'
    for f in inv['files']:
        assert sha(Path(args.csi_code) / f['path']) == f['sha256'], f['path']
    sys.path.insert(0, args.clip_code)
    import clip
    from clip.clip import _MODELS
    clip_hash = sha(args.clip_weight)
    assert clip_hash == _MODELS['ViT-B/32'].split('/')[-2], 'Cached CLIP is not the named official artifact'
    sd = Path(args.sd_cache)
    assert 'license: creativeml-openrail-m' in (sd / 'README.md').read_text()
    assert 'MIT License' in (Path(args.clip_code) / 'LICENSE').read_text()
    weights = [sd / 'unet/diffusion_pytorch_model.safetensors',
               sd / 'vae/diffusion_pytorch_model.safetensors',
               sd / 'text_encoder/model.safetensors',
               sd / 'safety_checker/model.safetensors']
    metadata = {'config': cfg, 'config_sha256': sha(args.config), 'script_sha256': sha(__file__),
        'preflight': preflight, 'logical_gpu': 0, 'torch': torch.__version__,
        'numpy': np.__version__, 'clip_weight_sha256': clip_hash,
        'clip_source_hashes': {str(p.relative_to(args.clip_code)): sha(p)
             for p in Path(args.clip_code).glob('clip/*.py')},
        'sd_file_hashes': {str(p.relative_to(sd)): sha(p) for p in weights},
        'sd_snapshot': sd.name, 'csi_commit': inv['commit'],
        'scope': cfg['scope'], 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    write_json(out / 'frozen.json', metadata)
    start = time.perf_counter()
    print('Frozen inputs verified; loading cached models', flush=True)
    # Keep the cached SD safety checker. Use fp32 artifact files converted on
    # load, since this cache lacks the fp16 UNet file. No cache writes/downloads.
    pipe = StableDiffusionPipeline.from_pretrained(str(sd), torch_dtype=torch.float16,
                                                   local_files_only=True, use_safetensors=True)
    pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config)
    pipe.set_progress_bar_config(disable=True)
    pipe.to('cuda')
    backend = object.__new__(StableDiffusionBackend)
    backend.pipe, backend.device = pipe, 'cuda'
    backend.steps, backend.guidance, backend.invert_guidance = 50, 7.5, 1.0
    model, preprocess = clip.load(args.clip_weight, device='cuda', jit=False)
    model.eval()
    core = SealCore(k=1024, b=7, t_patch=cfg['core']['t_patch'])
    key = Key(seed=cfg['key_seed'])
    arrays, rows, images, embeddings = {}, [], [], []

    @torch.inference_mode()
    def feature(image):
        v = model.encode_image(preprocess(image).unsqueeze(0).to('cuda')).float()
        v = v / v.norm(dim=-1, keepdim=True)
        return v.cpu().numpy().astype(np.float64).ravel()

    def verify(image, source, variant, registered_z):
        t = time.perf_counter()
        v = feature(image)
        reference = core.noise_from_embedding(v, key)
        recon = backend.invert(image).z_T
        l2 = core.patch_l2(recon, reference)
        row = {'source': source, 'variant': variant, 'match_count': int((l2 <= core.t_patch).sum()),
               'fallback_accepted': bool((l2 <= core.t_patch).sum() >= cfg['core']['fallback_matches']),
               'operating_point_provenance': 'unchecked',
               'registration_reference_matches': core.match_count(recon, registered_z),
               'wall_seconds': time.perf_counter() - t}
        arrays[source + '_' + variant + '_feature'] = v
        arrays[source + '_' + variant + '_reference'] = reference
        arrays[source + '_' + variant + '_recon'] = recon
        arrays[source + '_' + variant + '_l2'] = l2
        return row

    for i, (prompt, seed) in enumerate(zip(cfg['prompts'], cfg['draft_seeds'])):
        source = 's' + str(i)
        t = time.perf_counter()
        draft = backend.generate(prompt, z_T=backend.random_latents(seed=seed))
        draft.save(out / (source + '_draft.png'))
        v = feature(draft)
        z = core.noise_from_embedding(v, key)
        image = backend.generate(prompt, z_T=z)
        image.save(out / (source + '_original.png'))
        images.append(image)
        embeddings.append(v)
        arrays[source + '_registered_z'] = z
        arrays[source + '_draft_feature'] = v
        row = verify(image, source, 'original', z)
        row['registration_seconds'] = time.perf_counter() - t - row['wall_seconds']
        rows.append(row)
        buf = io.BytesIO()
        image.save(buf, format='JPEG', quality=70, subsampling=2)
        jpeg = Image.open(io.BytesIO(buf.getvalue())).convert('RGB')
        jpeg.save(out / (source + '_jpeg70.png'))
        rows.append(verify(jpeg, source, 'jpeg70', z))
        write_json(out / 'partial_scores.json', rows)
        np.savez_compressed(out / 'partial_arrays.npz', **arrays)
        print(json.dumps(rows[-2:]), flush=True)
    # A database-free scheme does not bind the verifier to a source credential.
    # Reusing its public key on another marked image cannot be labelled a
    # different-source rejection test. Record that limitation rather than a
    # misleading cyclic-donor acceptance metric.
    np.savez_compressed(out / 'arrays.npz', **arrays)
    write_json(out / 'scores.json', rows)
    file_hashes = {p.name: sha(p) for p in out.iterdir() if p.suffix in ('.png', '.npz', '.json')}
    write_json(out / 'runtime.json', {'wall_seconds': time.perf_counter() - start,
        'max_cuda_allocated_bytes': torch.cuda.max_memory_allocated(0),
        'max_cuda_reserved_bytes': torch.cuda.max_memory_reserved(0),
        'weights_downloaded_bytes': 0, 'generated_images': 6, 'verified_versions': 6,
        'gpu_uuid': cfg['physical_gpu_uuid'], 'file_hashes': file_hashes})
    print('Completed alternative configuration; thresholds remain unchecked', flush=True)


if __name__ == '__main__':
    main()
