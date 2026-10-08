"""Two-stage new-source development control; score only after hash-bound visual review."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from sd15_clip_smoke import sha, write_json, guard_gpu

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=['prepare', 'score'])
    for flag in ('config', 'base-run', 'sd-cache', 'clip-code', 'clip-weight', 'csi-code', 'output'):
        ap.add_argument('--' + flag, required=True)
    ap.add_argument('--source-run')
    ap.add_argument('--variants')
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    assert cfg['source_count'] == 1 and cfg['split'] == 'development'
    assert cfg['core'] == {'k': 1024, 'b': 7, 't_patch': 2.0, 'fallback_matches': 10.0}
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / 'frozen.json').exists(), 'Do not overwrite'
    review = None
    if args.phase == 'score':
        variants = Path(args.variants)
        review = json.loads((variants / 'visual_review.json').read_text())
        assert review['reviewed_before_scoring'] and review['valid_fact_change']
        assert review['control_fact_unchanged'] and review['all_processing_facts_reviewed']
        assert len(review['image_hashes']) == 9
        for name, digest in review['image_hashes'].items():
            assert sha(variants / name) == digest
        assert not (variants / 'scores.json').exists()
    preflight = guard_gpu(cfg)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', DIFFUSERS_OFFLINE='1',
                      TOKENIZERS_PARALLELISM='false', WANDB_MODE='disabled')
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
    sys.path.insert(0, args.clip_code)
    import clip
    base = Path(args.base_run)
    base_meta = json.loads((base / 'frozen.json').read_text())
    assert sha(args.clip_weight) == base_meta['clip_weight_sha256']
    for name, digest in base_meta['sd_file_hashes'].items():
        assert sha(Path(args.sd_cache) / name) == digest
    for name, digest in base_meta['clip_source_hashes'].items():
        assert sha(Path(args.clip_code) / name) == digest
    inventory = json.loads((Path(args.csi_code).parent / 'reports/reproduction_audit/csi_code_inventory.json').read_text())
    for f in inventory['files']:
        assert sha(Path(args.csi_code) / f['path']) == f['sha256']
    meta = {'config': cfg, 'config_sha256': sha(args.config), 'script_sha256': sha(__file__),
            'phase': args.phase, 'pid': os.getpid(), 'preflight': preflight, 'logical_gpu': 0,
            'base_frozen_sha256': sha(base / 'frozen.json'),
            'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    if review:
        meta.update(visual_review=review, visual_review_sha256=sha(variants / 'visual_review.json'))
    write_json(out / 'frozen.json', meta)
    start = time.perf_counter()
    pipe = StableDiffusionPipeline.from_pretrained(args.sd_cache, torch_dtype=torch.float16,
        local_files_only=True, use_safetensors=True)
    assert pipe.safety_checker is not None
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

    @torch.inference_mode()
    def feature(image):
        v = model.encode_image(preprocess(image).unsqueeze(0).to('cuda')).float()
        return (v / v.norm(dim=-1, keepdim=True)).cpu().numpy().astype(np.float64).ravel()

    arrays, rows = {}, []
    if args.phase == 'prepare':
        # Generation uses the same backend call but saves the actual safety flags.
        @torch.inference_mode()
        def generate(z, name):
            result = pipe(cfg['prompt'], latents=backend._to_torch(z),
                          num_inference_steps=50, guidance_scale=7.5)
            result.images[0].save(out / (name + '.png'))
            flags = result.nsfw_content_detected
            assert flags is not None
            rows.append({'image': name, 'nsfw_content_detected': [bool(x) for x in flags]})
            assert not any(flags), 'Preserve failed safety result and stop'
            return result.images[0]
        draft = generate(backend.random_latents(seed=cfg['draft_seed']), 'draft')
        v = feature(draft)
        z = core.noise_from_embedding(v, key)
        generate(z, 'source')
        arrays.update(draft_feature=v, registered_z=z)
        write_json(out / 'safety_outputs.json', rows)
        np.savez_compressed(out / 'registration.npz', **arrays)
        generated, verified = 2, 0
    else:
        source_run = Path(args.source_run)
        source_runtime = json.loads((source_run / 'runtime.json').read_text())
        for name, digest in source_runtime['file_hashes'].items():
            assert sha(source_run / name) == digest
        source_arrays = np.load(source_run / 'registration.npz', allow_pickle=False)
        arrays.update(registered_z=source_arrays['registered_z'], draft_feature=source_arrays['draft_feature'])
        # No registration latent or mask enters the native decision below.
        for condition in ('source', 'control', 'edit'):
            for processing in cfg['processing']:
                name = condition + '_' + processing
                image = Image.open(variants / (name + '.png')).convert('RGB')
                t = time.perf_counter()
                v = feature(image)
                reference = core.noise_from_embedding(v, key)
                recon = backend.invert(image).z_T
                l2 = core.patch_l2(recon, reference)
                count = int((l2 <= 2.0).sum())
                arrays.update({name + '_feature': v, name + '_reference': reference,
                               name + '_recon': recon, name + '_l2': l2})
                rows.append({'source': 'apple_dev01', 'condition': condition, 'processing': processing,
                    'image_sha256': sha(variants / (name + '.png')), 'match_count': count,
                    'fallback_accepted': count >= 10, 'operating_point_provenance': 'unchecked',
                    'first_rejection_stage': None if count >= 10 else 'match_count_threshold',
                    'stages': {'decode_rgb': 'completed', 'clip_l2_feature': 'completed',
                               'keyed_reference_noise': 'completed', 'empty_prompt_ddim_inversion': 'completed',
                               'patch_l2': 'completed', 'match_count_threshold': 'accepted' if count >= 10 else 'rejected'},
                    'feature_norm': float(np.linalg.norm(v)),
                    'patch_l2_min': float(l2.min()), 'patch_l2_median': float(np.median(l2)),
                    'patch_l2_max': float(l2.max()),
                    'registration_reference_matches_oracle_only': core.match_count(recon, arrays['registered_z']),
                    'wall_seconds': time.perf_counter() - t})
                write_json(out / 'partial_scores.json', rows)
                np.savez_compressed(out / 'partial_arrays.npz', **arrays)
                print(json.dumps(rows[-1]), flush=True)
        write_json(out / 'scores.json', rows)
        np.savez_compressed(out / 'arrays.npz', **arrays)
        generated, verified = 0, 9
    hashes = {p.name: sha(p) for p in out.iterdir() if p.suffix in ('.json', '.npz', '.png')}
    write_json(out / 'runtime.json', {'wall_seconds': time.perf_counter() - start,
        'max_cuda_allocated_bytes': torch.cuda.max_memory_allocated(0),
        'max_cuda_reserved_bytes': torch.cuda.max_memory_reserved(0),
        'generated_images': generated, 'verified_versions': verified,
        'weights_downloaded_bytes': 0, 'gpu_uuid': cfg['physical_gpu_uuid'], 'file_hashes': hashes,
        'finished_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    print('Completed development phase; threshold unchanged and unchecked', flush=True)

if __name__ == '__main__':
    main()
