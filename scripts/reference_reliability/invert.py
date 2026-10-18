"""Proxy-only reference inversion; input is an image-only fixed bundle."""
import sys
import time
from pathlib import Path
from common import r, write, sha
from boundary import validate_inputs

def main(runtime, jobs, steps, output):
    cfg = r.check_device(runtime, output)
    inputs = validate_inputs(jobs)
    if inputs['proxy'] != cfg['proxy'] or steps not in (25, 50, 100):
        raise ValueError('Unexpected proxy configuration')
    import torch
    from PIL import Image
    r.deterministic(0)
    provider = r.official_provider(cfg['proxy']); rows = []
    for row in inputs['rows']:
        folder = output / str(row['task_id']); folder.mkdir()
        path = jobs / row['image']['path']
        if sha(path) != row['image']['sha256']:
            raise ValueError('Input changed')
        with Image.open(path) as im:
            image = im.copy()
        start = time.perf_counter()
        with torch.no_grad():
            z = provider.invert_images(image, num_inference_steps=steps)['zT_torch']
        torch.cuda.synchronize()
        rows.append(dict(task_id=row['task_id'], inverse=r.tensor(folder / 'inverse.npy', z),
                         seconds=time.perf_counter() - start))
    validate_inputs(jobs)
    write(output / 'summary.json', dict(completed=True, rows=rows, steps=steps,
          input_jobs_sha256=sha(jobs / 'jobs.json'), model=cfg['proxy'],
          inverse_scheduler=type(provider.scheduler_inverse).__name__, dtype=str(provider.get_dtype()),
          vae_scaling_factor=provider.pipe.vae.config.scaling_factor, target_feedback_used=False))
    print('COMPLETED_REFERENCE_PROXY', flush=True)

if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
