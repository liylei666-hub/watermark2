"""Strict proxy bundles and pre-evaluation seals; shared OS user is not isolation."""
from pathlib import Path
import numpy as np
from PIL import Image
from common import read, write, sha
from scores import score_vectors

def image_record(path):
    with Image.open(path) as image:
        image.load()
        if image.format != 'PNG' or image.mode != 'RGB' or image.size != (512, 512):
            raise ValueError('Expected RGB512 PNG')
    return dict(path=Path(path).name, sha256=sha(path))

def export_inputs(root, proxy):
    folder = Path(root) / 'proxy_inputs'; folder.mkdir()
    rows = []
    for task in range(1, 5):
        source = Path(root) / 'reference' / str(task) / 'reference.png'
        image_record(source)
        target = folder / (str(task) + '.png')
        with target.open('xb') as f:
            f.write(source.read_bytes())
        rows.append(dict(task_id=task, image=image_record(target)))
    write(folder / 'jobs.json', dict(version=1, proxy=proxy, steps=[25, 50, 100], rows=rows))
    write(Path(root) / 'inputs_sealed.json', dict(jobs_sha256=sha(folder / 'jobs.json')))

def validate_inputs(folder):
    folder = Path(folder); value = read(folder / 'jobs.json')
    if set(value) != {'version', 'proxy', 'steps', 'rows'} or value['version'] != 1 or value['steps'] != [25, 50, 100]:
        raise ValueError('Unexpected proxy job fields')
    expected = [dict(task_id=k, image=image_record(folder / (str(k) + '.png'))) for k in range(1, 5)]
    if value['rows'] != expected or {p.name for p in folder.iterdir()} != {'jobs.json', '1.png', '2.png', '3.png', '4.png'}:
        raise ValueError('Unexpected proxy inputs or hashes')
    return value

def load_inverse(path):
    array = np.load(path, allow_pickle=False)
    if array.dtype != np.float32 or array.shape != (1, 4, 64, 64) or not np.isfinite(array).all():
        raise ValueError('Expected finite float32 latent')
    return array

def collect(root):
    root = Path(root); validate_inputs(root / 'proxy_inputs')
    if read(root / 'inputs_sealed.json') != dict(jobs_sha256=sha(root / 'proxy_inputs/jobs.json')):
        raise ValueError('Inputs changed')
    paths = [root / 'proxy_inputs/jobs.json'] + [root / 'proxy_inputs' / (str(k) + '.png') for k in range(1, 5)]
    paths += [root / ('proxy_' + str(step)) / str(k) / 'inverse.npy' for step in (25, 50, 100) for k in range(1, 5)]
    paths += [root / 'scores' / str(k) / (name + '.npy') for k in range(1, 5) for name in ('baseline', 'consistency')]
    return {p.relative_to(root).as_posix(): sha(p) for p in paths}

def seal_scores(root):
    root = Path(root); (root / 'scores').mkdir()
    for k in range(1, 5):
        arrays = {step: load_inverse(root / ('proxy_' + str(step)) / str(k) / 'inverse.npy') for step in (25, 50, 100)}
        folder = root / 'scores' / str(k); folder.mkdir()
        for name, score in score_vectors(arrays).items():
            with (folder / (name + '.npy')).open('xb') as f:
                np.save(f, score, allow_pickle=False)
    write(root / 'proxy_sealed.json', collect(root))

def verify_seal(root):
    if read(Path(root) / 'proxy_sealed.json') != collect(root):
        raise ValueError('Proxy representations or scores changed')

def publishable_files(root):
    """Allowlisted run roots; private encryption material belongs outside this run."""
    root = Path(root)
    allowed_dirs = {'reference', 'proxy_inputs', 'proxy_25', 'proxy_50', 'proxy_100', 'scores', 'evaluation'}
    allowed_files = {'launch_intent.json', 'inputs_sealed.json', 'proxy_sealed.json', 'status.json'}
    paths = []
    for p in root.rglob('*'):
        if p.is_symlink():
            raise ValueError('Run contains symlink')
        if not p.is_file():
            continue
        parts = p.relative_to(root).parts
        if (len(parts) == 1 and parts[0] not in allowed_files) or (len(parts) > 1 and parts[0] not in allowed_dirs):
            raise ValueError('Unexpected publication path')
        if p.suffix == '.bin' or any(s in p.name for s in ('secret', 'material', 'key', 'nonce', 'message')):
            raise ValueError('Private material cannot be published')
        paths.append(p)
    return paths
