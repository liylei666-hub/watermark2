"""Generate fixed independent GS references; only proxy references are inverted here."""
import importlib.util
from pathlib import Path
import sys
import time
import io_contract as c
from source_worker import r, rng_record


def private_module():
    path = Path(__file__).resolve().parents[1] / 'reference_reliability/private_state.py'
    spec = importlib.util.spec_from_file_location('stage24_private', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main(runtime, job_path, job_sha, private_folder, output):
    output = Path(output); cfg = r.check_device(Path(runtime), output)
    if c.sha(job_path) != job_sha or job_sha not in cfg['generation_job_hashes']:
        raise ValueError('Generation job changed')
    job = c.read(job_path); c.keys(job, ['version','split','model','tasks'])
    if job['version'] != 1 or job['split'] not in ('proxy_test','target_test') or len(job['tasks']) != 4:
        raise ValueError('Invalid generation batch')
    import torch
    private = private_module(); r.deterministic(0)
    start = time.perf_counter(); provider = r.official_provider(job['model'])
    torch.cuda.synchronize(); loading = time.perf_counter() - start
    if provider.get_dtype() != torch.float32:
        raise ValueError('Precision mismatch')
    rows = []
    for task in job['tasks']:
        sid = task['sample_id']; folder = output / sid; folder.mkdir()
        if sid not in c.SPLITS[job['split']] or task['noise_distribution'] != 'GS':
            raise ValueError('Unexpected test task')
        raw = private.create(Path(private_folder), sid); wm = private.provider(raw, 'cuda:0')
        r.deterministic(task['seed']); rng_record(folder, 'before_noise')
        z = wm.get_wm_latents()['zT_torch']; original = z.detach().clone()
        noise = c.save_array(folder / 'original_noise.npy', original.cpu().numpy(), 'float32')
        rng_record(folder, 'before_generation'); start = time.perf_counter()
        with torch.no_grad():
            generated = provider.generate(prompts=[task['prompt']], num_inference_steps=50,
                                          guidance_scale=7.5, latents=z, return_latents=False)
        torch.cuda.synchronize(); generation_seconds = time.perf_counter() - start
        rng_record(folder, 'after_generation')
        if not torch.equal(original, z): raise ValueError('Generation changed noise')
        image, image_rec = c.save_png_readback(generated['images_PIL'][0], folder / 'reference.png')
        row = dict(task=task, original_noise=noise, image=image_rec,
                   encryption_fingerprints=private.fingerprints(raw),generation_seconds=generation_seconds)
        if job['split'] == 'proxy_test':
            start = time.perf_counter()
            with torch.no_grad(): inverse = provider.invert_images(image, num_inference_steps=50)['zT_torch']
            torch.cuda.synchronize(); row['inversion_seconds'] = time.perf_counter() - start
            row['estimate'] = c.save_array(folder / 'estimate.npy', inverse.detach().cpu().numpy(), 'float32')
        if c.png_record(folder / 'reference.png') != image_rec:
            raise ValueError('Image changed during inversion')
        c.write(folder / 'record.json', row); rows.append(row)
    c.write(output / 'summary.json', dict(completed=True, rows=rows, job_sha256=job_sha,
            model=job['model'], model_loading_seconds=loading, dtype=str(provider.get_dtype()),
            scheduler=type(provider.scheduler).__name__, inverse_scheduler=type(provider.scheduler_inverse).__name__))
    print('COMPLETED_GS_BATCH', flush=True)


if __name__ == '__main__': main(*sys.argv[1:])
