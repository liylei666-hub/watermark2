"""Measure fixed saved endpoints with the cached proxy; no optimizer or evaluator."""
import sys
from pathlib import Path
from common import REMOTE, sha, write, validate_inputs, summarize

ROOT = Path(REMOTE)
sys.path.insert(0, str(ROOT / 'scripts/cover_pilot'))
import runtime as r


def main(protocol, output):
    cfg = r.check_device(protocol, output)
    paths = validate_inputs(cfg, ROOT)
    import typing
    import numpy as np
    import torch
    import PIL.Image
    from torchvision.transforms.functional import to_tensor, to_pil_image
    from torch.utils.checkpoint import checkpoint
    from diffusers import StableDiffusionPipeline, DDIMScheduler, DDIMInverseScheduler
    from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import retrieve_timesteps, rescale_noise_cfg
    r.deterministic(cfg['seed'])
    scope = dict(torch=torch, PIL=PIL, Optional=typing.Optional, Union=typing.Union, List=typing.List,
                 checkpoint=checkpoint, to_tensor=to_tensor, to_pil_image=to_pil_image,
                 retrieve_timesteps=retrieve_timesteps, rescale_noise_cfg=rescale_noise_cfg)
    r.definitions(r.UPSTREAM / 'utils/imprint_utils.py',
                  {'DiffPipe', 'UnetWrapper', 'latent_to_pil', 'pixel_to_latent'}, scope)
    snapshot = cfg['proxy']['snapshot']
    scheduler = DDIMScheduler.from_pretrained(snapshot, subfolder='scheduler', local_files_only=True)
    inverse = DDIMInverseScheduler.from_pretrained(snapshot, subfolder='scheduler', local_files_only=True)
    pipe = StableDiffusionPipeline.from_pretrained(snapshot, scheduler=scheduler, safety_checker=None,
        local_files_only=True, torch_dtype=torch.float32).to('cuda:0')
    pipe.set_progress_bar_config(disable=True)
    pipe.vae.requires_grad_(False)
    pipe.text_encoder.requires_grad_(False)
    diff = scope['DiffPipe'](pipe, scheduler=inverse, device='cuda:0')
    encode = lambda x: scope['pixel_to_latent'](x, pipe)

    def invert(z):
        old = pipe.scheduler
        pipe.scheduler = inverse
        try:
            return pipe(latents=z, num_inference_steps=50, prompt=[''], negative_prompt=[''],
                guidance_scale=1., width=512, height=512, output_type='latent', return_dict=False)[0]
        finally:
            pipe.scheduler = old

    def load_tensor(name, shape):
        a = np.load(paths[name], allow_pickle=False)
        if a.dtype != np.float32 or a.shape != shape or not np.isfinite(a).all():
            raise ValueError('Invalid saved tensor: ' + name)
        return torch.from_numpy(a).to('cuda:0')

    rows = []
    with torch.no_grad():
        for task in [1, 2, 3]:
            folder = output / str(task)
            folder.mkdir()
            tensors = {}
            for name in ['reference', 'cover', 'imprint_png', 'jain_png']:
                with PIL.Image.open(paths[f'{task}/{name}']) as im:
                    if im.size != (512, 512) or im.mode != 'RGB':
                        raise ValueError('Unexpected image geometry')
                    tensors[name + '_z'] = encode(im.copy())
            tensors['reference_inverse'] = invert(tensors['reference_z'])
            stored = load_tensor(f'{task}/reference_inverse', (1, 4, 64, 64))
            equal = torch.equal(stored, tensors['reference_inverse'])
            write(folder / 'reference_control.json', dict(bitwise_equal=equal,
                max_abs=float((stored - tensors['reference_inverse']).abs().max().cpu())))
            if not equal:
                raise RuntimeError('Reference proxy inversion differs from frozen attack state')
            for name in ['cover', 'imprint_png', 'jain_png']:
                tensors[name + '_inverse'] = invert(tensors[name + '_z'])
            tensors['imprint_native_z'] = load_tensor(f'{task}/imprint_z', (1, 4, 64, 64))
            native = diff(tensors['imprint_native_z'], '', guidance_scale=1., num_inference_steps=50)
            control = invert(tensors['imprint_native_z'])
            eq = torch.allclose(native, control, atol=cfg['atol'], rtol=cfg['rtol'])
            write(folder / 'inversion_equivalence.json', dict(allclose=eq,
                atol=cfg['atol'], rtol=cfg['rtol'], max_abs=float((native-control).abs().max().cpu())))
            if not eq:
                raise RuntimeError('Internal/pipeline inversion equivalence gate failed')
            tensors['imprint_native_inverse'] = native
            tensors['imprint_pipeline_control'] = control
            # Same official decode-to-PIL path as the fixed Imprint candidate.
            image = scope['latent_to_pil'](tensors['imprint_native_z'], pipe)[0]
            with PIL.Image.open(paths[f'{task}/imprint_png']) as fixed:
                image_equal = np.array_equal(np.asarray(image), np.asarray(fixed))
            write(folder / 'decode_control.json', dict(png_pixels_bitwise_equal=image_equal))
            if not image_equal:
                raise RuntimeError('Saved native latent does not decode to fixed candidate')
            raw = pipe.vae.decode(tensors['imprint_native_z'] / pipe.vae.config.scaling_factor, return_dict=False)[0]
            floats = (raw * .5 + .5).clamp(0, 1)
            tensors['imprint_float_z'] = encode(2 * floats - 1)
            tensors['imprint_float_inverse'] = invert(tensors['imprint_float_z'])
            initial_png = scope['latent_to_pil'](tensors['cover_z'], pipe)[0]
            tensors['initial_png_z'] = encode(initial_png)
            tensors['initial_png_inverse'] = invert(tensors['initial_png_z'])
            jain_float = load_tensor(f'{task}/jain_float', (1, 3, 512, 512))
            tensors['jain_float_z'] = encode(jain_float)
            records = {name: r.tensor(folder / (name + '.npy'), value) for name, value in tensors.items()}
            arrays = {name: value.cpu().numpy() for name, value in tensors.items()}
            row = dict(task_id=task, metrics=summarize(arrays), arrays=records)
            write(folder / 'metrics.json', row)
            rows.append(row)
            print('COMPLETED_PROXY_ENDPOINT_PAIR', task, flush=True)
    validate_inputs(cfg, ROOT)
    write(output / 'summary.json', dict(completed=True, rows=rows,
        scaling_factor=pipe.vae.config.scaling_factor, protocol_sha256=sha(protocol),
        target_model_loaded=False, target_scores_used=False, optimization_updates=0,
        new_candidate_images=0, full_defense_acceptance=None,
        interpretation='Exploratory fixed-endpoint proxy diagnostic, all three development pairs'))
    print('COMPLETED_ENDPOINT_RESIDUAL', flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
