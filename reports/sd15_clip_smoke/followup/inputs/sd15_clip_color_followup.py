"""Fixed color edits and matched regeneration controls after the three-source smoke test."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from sd15_clip_smoke import sha, write_json, guard_gpu


def main():
    ap = argparse.ArgumentParser()
    for flag in ('config', 'base-run', 'sd-cache', 'clip-code', 'clip-weight', 'csi-code', 'output'):
        ap.add_argument('--' + flag, required=True)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / 'frozen.json').exists()
    preflight = guard_gpu(cfg)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', DIFFUSERS_OFFLINE='1',
                      TOKENIZERS_PARALLELISM='false', WANDB_MODE='disabled')
    import numpy as np
    import torch
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
    sys.path.insert(0, args.clip_code)
    import clip
    base = Path(args.base_run)
    base_metadata = json.loads((base / 'frozen.json').read_text())
    base_runtime = json.loads((base / 'runtime.json').read_text())
    for name, digest in base_runtime['file_hashes'].items():
        assert sha(base / name) == digest, name
    assert sha(args.clip_weight) == base_metadata['clip_weight_sha256']
    for name, digest in base_metadata['sd_file_hashes'].items():
        assert sha(Path(args.sd_cache) / name) == digest, name
    for name, digest in base_metadata['clip_source_hashes'].items():
        assert sha(Path(args.clip_code) / name) == digest, name
    inv = json.loads((Path(args.csi_code).parent / 'reports/reproduction_audit/csi_code_inventory.json').read_text())
    for f in inv['files']:
        assert sha(Path(args.csi_code) / f['path']) == f['sha256']
    write_json(out / 'frozen.json', {'config': cfg, 'script_sha256': sha(__file__),
        'config_sha256': sha(args.config), 'base_frozen_sha256': sha(base / 'frozen.json'),
        'base_arrays_sha256': sha(base / 'arrays.npz'), 'preflight': preflight,
        'logical_gpu': 0, 'posthoc_development': True})
    print('Frozen fixed follow-up verified; loading the same cached models', flush=True)
    start = time.perf_counter()
    pipe = StableDiffusionPipeline.from_pretrained(args.sd_cache, torch_dtype=torch.float16,
        local_files_only=True, use_safetensors=True)
    pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config)
    pipe.set_progress_bar_config(disable=True)
    pipe.to('cuda')
    backend = object.__new__(StableDiffusionBackend)
    backend.pipe, backend.device = pipe, 'cuda'
    backend.steps, backend.guidance, backend.invert_guidance = 50, 7.5, 1.0
    model, preprocess = clip.load(args.clip_weight, device='cuda', jit=False)
    model.eval()
    core = SealCore(k=1024, b=7, t_patch=2.0)
    key = Key(seed=42)
    saved = np.load(base / 'arrays.npz', allow_pickle=False)
    arrays, rows = {}, []
    for i in range(3):
        source = 's' + str(i)
        for name in ('registered_z', 'draft_feature'):
            arrays[source + '_' + name] = saved[source + '_' + name]
        copied_noise = saved[source + '_original_recon']
        for variant, prompt in [('process_control', cfg['prompts'][i]),
                                ('color_edit', cfg['edit_prompts'][i])]:
            t = time.perf_counter()
            image = backend.generate(prompt, z_T=copied_noise)
            image.save(out / (source + '_' + variant + '.png'))
            with torch.inference_mode():
                v = model.encode_image(preprocess(image).unsqueeze(0).to('cuda')).float()
                v = (v / v.norm(dim=-1, keepdim=True)).cpu().numpy().astype(np.float64).ravel()
            reference = core.noise_from_embedding(v, key)
            recon = backend.invert(image).z_T
            l2 = core.patch_l2(recon, reference)
            count = int((l2 <= 2.0).sum())
            prefix = source + '_' + variant
            arrays.update({prefix + '_feature': v, prefix + '_reference': reference,
                           prefix + '_recon': recon, prefix + '_l2': l2})
            rows.append({'source': source, 'variant': variant, 'prompt': prompt, 'match_count': count,
                'fallback_accepted': count >= 10, 'operating_point_provenance': 'unchecked',
                'registration_reference_matches': core.match_count(recon, arrays[source + '_registered_z']),
                'wall_seconds': time.perf_counter() - t})
            print(json.dumps(rows[-1]), flush=True)
            write_json(out / 'partial_scores.json', rows)
            np.savez_compressed(out / 'partial_arrays.npz', **arrays)
    write_json(out / 'scores.json', rows)
    np.savez_compressed(out / 'arrays.npz', **arrays)
    hashes = {p.name: sha(p) for p in out.iterdir() if p.suffix in ('.json', '.npz', '.png')}
    write_json(out / 'runtime.json', {'wall_seconds': time.perf_counter() - start,
        'max_cuda_allocated_bytes': torch.cuda.max_memory_allocated(0),
        'max_cuda_reserved_bytes': torch.cuda.max_memory_reserved(0),
        'generated_images': 6, 'verified_versions': 6, 'weights_downloaded_bytes': 0,
        'gpu_uuid': cfg['physical_gpu_uuid'], 'file_hashes': hashes})
    print('Completed fixed post-hoc color follow-up; thresholds unchanged', flush=True)


if __name__ == '__main__':
    main()
