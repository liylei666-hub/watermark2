"""Four fixed proxy Gaussian pairs per child; invert the saved PNG through upstream."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cover_pilot'))
import runtime as r
import io_contract as c


def jobs(path, cfg):
    path = Path(path)
    if c.sha(path) != cfg['source_jobs_sha256']:
        raise ValueError('Source jobs changed')
    value = c.read(path)
    c.keys(value, ['version', 'model', 'batches', 'design_sha256'])
    if value['version'] != 1 or len(value['batches']) != 6:
        raise ValueError('Invalid source job plan')
    tasks = [task for batch in value['batches'] for task in batch]
    ids = c.SPLITS['train'] + c.SPLITS['validation']
    if [task['sample_id'] for task in tasks] != ids or any(len(batch) != 4 for batch in value['batches']):
        raise ValueError('Source tasks changed')
    for task in tasks:
        c.keys(task, ['sample_id', 'role', 'generator_role', 'prompt_group', 'prompt', 'seed', 'noise_distribution'])
        expected_role = 'proxy_train' if task['sample_id'] in c.SPLITS['train'] else 'proxy_validation'
        if task['role'] != expected_role or task['generator_role'] != 'proxy' or task['noise_distribution'] != 'gaussian':
            raise ValueError('Only proxy Gaussian source tasks are allowed')
    return value


def rng_record(folder, phase):
    import random
    import numpy as np
    import torch
    state = np.random.get_state()
    with (folder / ('rng_' + phase + '.npz')).open('xb') as stream:
        np.savez(stream, numpy_state=state[1], torch_cpu=torch.get_rng_state().numpy(),
                 torch_cuda=torch.cuda.get_rng_state(0).cpu().numpy())
    c.write(folder / ('rng_' + phase + '.json'), dict(python=random.getstate(), numpy_algorithm=state[0],
            numpy_position=state[2], numpy_has_gauss=state[3], numpy_cached_gaussian=state[4]))


def main(runtime, source_jobs, batch_index, output):
    output = Path(output); cfg = r.check_device(Path(runtime), output)
    plan = jobs(source_jobs, cfg); batch_index = int(batch_index)
    if batch_index not in range(6):
        raise ValueError('Unknown source batch')
    import torch
    r.deterministic(0)
    started = time.perf_counter(); provider = r.official_provider(plan['model'])
    torch.cuda.synchronize(); loading = time.perf_counter() - started
    if provider.get_dtype() != torch.float32 or str(provider.pipe.device) != 'cuda:0':
        raise ValueError('Provider precision/device mismatch')
    if type(provider.scheduler).__name__ != 'DDIMScheduler' or type(provider.scheduler_inverse).__name__ != 'DDIMInverseScheduler':
        raise ValueError('Provider scheduler mismatch')
    rows = []
    for task in plan['batches'][batch_index]:
        folder = output / task['sample_id']; folder.mkdir()
        r.deterministic(task['seed']); rng_record(folder, 'before_noise')
        z = torch.randn(c.SHAPE, device='cuda:0', dtype=torch.float32)
        original = z.detach().clone()
        c.save_array(folder / 'original_noise.npy', original.cpu().numpy(), 'float32')
        rng_record(folder, 'before_generation')
        started = time.perf_counter()
        with torch.no_grad():
            generated = provider.generate(prompts=[task['prompt']], num_inference_steps=50,
                                          guidance_scale=7.5, latents=z, return_latents=False)
        torch.cuda.synchronize(); generation_seconds = time.perf_counter() - started
        rng_record(folder, 'after_generation')
        if not torch.equal(z, original):
            raise RuntimeError('Generation changed supplied noise')
        reread, image = c.save_png_readback(generated['images_PIL'][0], folder / 'reference.png')
        started = time.perf_counter()
        with torch.no_grad():
            inverted = provider.invert_images(reread, num_inference_steps=50)['zT_torch']
        torch.cuda.synchronize(); inversion_seconds = time.perf_counter() - started
        if c.png_record(folder / 'reference.png') != image:
            raise RuntimeError('PNG changed during inversion')
        estimate = c.save_array(folder / 'estimate.npy', inverted.detach().cpu().numpy(), 'float32')
        row = dict(task=task, image=image, estimate=estimate,
                   original_noise=c.array_record(folder / 'original_noise.npy'),
                   generation_seconds=generation_seconds, inversion_seconds=inversion_seconds,
                   inversion_input='saved_png_readback', png_pixel_equivalence=True)
        c.write(folder / 'record.json', row); rows.append(row)
    c.write(output / 'summary.json', dict(completed=True, batch_index=batch_index, rows=rows,
            source_jobs_sha256=c.sha(source_jobs), model=plan['model'], model_loading_seconds=loading,
            dtype=str(provider.get_dtype()), scheduler=type(provider.scheduler).__name__,
            inverse_scheduler=type(provider.scheduler_inverse).__name__,
            vae_scaling_factor=provider.pipe.vae.config.scaling_factor))
    print('COMPLETED_SOURCE_BATCH', flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 5:
        raise SystemExit('runtime source_jobs batch_index output required')
    main(*sys.argv[1:])
