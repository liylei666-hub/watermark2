"""Proxy-only inversion of a strict image bundle; no target generator configuration."""
from pathlib import Path
import sys
import time
from PIL import Image
import io_contract as c
from source_worker import r
from phase_contract import image_bundle


def main(runtime, folder, bundle_sha, batch, output):
    output = Path(output); folder = Path(folder)
    cfg = r.check_device(Path(runtime), output)
    bundle = image_bundle(folder, bundle_sha); batch = int(batch)
    if batch not in (0,1): raise ValueError('Unknown image batch')
    import torch
    r.deterministic(0); start = time.perf_counter(); provider = r.official_provider(cfg['proxy'])
    torch.cuda.synchronize(); loading = time.perf_counter() - start
    rows = []
    for row in bundle['rows'][batch*4:batch*4+4]:
        sid = row['sample_id']; out = output / sid; out.mkdir()
        path = folder / row['image']['path']
        with Image.open(path) as stored: image = stored.copy()
        start = time.perf_counter()
        with torch.no_grad(): inverse = provider.invert_images(image, num_inference_steps=50)['zT_torch']
        torch.cuda.synchronize(); seconds = time.perf_counter() - start
        rows.append(dict(sample_id=sid, image_sha256=row['image']['sha256'], inversion_seconds=seconds,
                         estimate=c.save_array(out / 'estimate.npy', inverse.detach().cpu().numpy(), 'float32')))
    image_bundle(folder, bundle_sha)
    c.write(output / 'summary.json', dict(completed=True, rows=rows, image_bundle_sha256=bundle_sha,
            model=cfg['proxy'], model_loading_seconds=loading, dtype=str(provider.get_dtype())))
    print('COMPLETED_TEST_INVERSION', flush=True)


if __name__ == '__main__': main(*sys.argv[1:])
