"""Target reference inversion and fixed ordinary GS check after proxy sealing."""
import sys
import time
from pathlib import Path
from common import r, design, read, write, sha
from boundary import verify_seal
import private_state as private

def main(runtime, protocol, root, private_folder, output):
    r.check_device(runtime, output); cfg = design(protocol); verify_seal(root)
    import torch
    from PIL import Image
    r.deterministic(0); provider = r.official_provider(cfg['target'])
    from utils.utils import check_if_detection_successful
    rows = []
    for task in cfg['tasks']:
        task_id = task['task_id']; folder = output / str(task_id); folder.mkdir()
        record = read(root / 'reference' / str(task_id) / 'record.json')
        raw = private.load(private_folder, task_id, record['encryption_fingerprints'])
        wm = private.provider(raw, 'cuda:0')
        # Evaluate exactly the PNG exposed to the proxy.
        path = root / 'proxy_inputs' / (str(task_id) + '.png')
        if sha(path) != record['image']['sha256']:
            raise ValueError('Reference association changed')
        with Image.open(path) as im:
            image = im.copy()
        start = time.perf_counter()
        with torch.no_grad():
            z = provider.invert_images(image, num_inference_steps=50)['zT_torch']
        torch.cuda.synchronize(); seconds = time.perf_counter() - start
        score = float(wm.get_accuracies(z)['bit_accuracies'][0])
        row = dict(task_id=task_id, inverse=r.tensor(folder / 'inverse.npy', z), seconds=seconds,
                   bit_accuracy=score, gs_detected=check_if_detection_successful('GS', .70703125, score),
                   full_defense_accepted=None)
        write(folder / 'metrics.json', row); rows.append(row)
    verify_seal(root)
    write(output / 'summary.json', dict(completed=True, rows=rows, model=cfg['target'],
          proxy_seal_sha256=sha(root / 'proxy_sealed.json'), protocol_sha256=sha(protocol),
          inverse_scheduler=type(provider.scheduler_inverse).__name__, dtype=str(provider.get_dtype()),
          vae_scaling_factor=provider.pipe.vae.config.scaling_factor, feedback_to_proxy=False))
    print('COMPLETED_REFERENCE_EVALUATION', flush=True)

if __name__ == '__main__':
    main(*map(Path, sys.argv[1:]))
