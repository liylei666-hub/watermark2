"""Generate four references with independent evaluator-owned GS states."""
import sys
import time
from pathlib import Path
from common import r, design, write, sha
from boundary import image_record
import private_state as private

def main(runtime, protocol, private_folder, output):
    r.check_device(runtime, output); cfg = design(protocol)
    import random
    import numpy as np
    import torch
    r.deterministic(0)
    start = time.perf_counter(); provider = r.official_provider(cfg['target'])
    torch.cuda.synchronize(); loading = time.perf_counter() - start
    from utils.utils import set_random_seed
    rows = []
    for task in cfg['tasks']:
        task_id = task['task_id']; folder = output / str(task_id); folder.mkdir()
        raw = private.create(private_folder, task_id)
        wm = private.provider(raw, 'cuda:0'); fingerprints = private.fingerprints(raw)
        set_random_seed(task['reference_seed'])
        for phase in ['before_noise', 'before_generation', 'after_generation']:
            if phase == 'before_generation':
                z = wm.get_wm_latents()['zT_torch']; original = z.detach().clone()
                noise = r.tensor(folder / 'original_noise.npy', original)
            if phase == 'after_generation':
                start = time.perf_counter()
                with torch.no_grad():
                    generated = provider.generate(prompts=[task['prompt']], num_inference_steps=50,
                                                  guidance_scale=7.5, latents=z, return_latents=False)
                torch.cuda.synchronize(); seconds = time.perf_counter() - start
                if not torch.equal(original, z):
                    raise RuntimeError('Generation mutated supplied noise')
                with (folder / 'reference.png').open('xb') as f:
                    generated['images_PIL'][0].save(f, format='PNG')
            state = np.random.get_state()
            with (folder / ('rng_' + phase + '.npz')).open('xb') as f:
                np.savez(f, numpy_state=state[1], torch_cpu=torch.get_rng_state().numpy(),
                         torch_cuda=torch.cuda.get_rng_state(0).cpu().numpy())
            write(folder / ('rng_' + phase + '.json'), dict(python=random.getstate(), numpy_algorithm=state[0],
                  numpy_position=state[2], numpy_has_gauss=state[3], numpy_cached_gaussian=state[4]))
        row = dict(task_id=task_id, seed=task['reference_seed'], prompt=task['prompt'],
                   encryption_fingerprints=fingerprints, image=image_record(folder / 'reference.png'),
                   original_noise=noise, generation_seconds=seconds)
        write(folder / 'record.json', row); rows.append(row)
    for name in ('message', 'key', 'nonce'):
        if len({row['encryption_fingerprints'][name] for row in rows}) != 4:
            raise RuntimeError('Encryption states not independent')
    write(output / 'summary.json', dict(completed=True, rows=rows, model=cfg['target'],
          model_loading_seconds=loading, scheduler=type(provider.scheduler).__name__,
          inverse_scheduler=type(provider.scheduler_inverse).__name__, dtype=str(provider.get_dtype()),
          vae_scaling_factor=provider.pipe.vae.config.scaling_factor, protocol_sha256=sha(protocol)))
    print('COMPLETED_REFERENCE_PREPARATION', flush=True)

if __name__ == '__main__':
    main(*map(Path, sys.argv[1:]))
