"""Stage24 file contracts. Integrity and role checks do not isolate OS permissions."""
import hashlib
import json
import os
from pathlib import Path
import re

import numpy as np
from PIL import Image

SHAPE = (1, 4, 64, 64)
SPLITS = {
    'train': [f'proxy_train_{g}_{s}' for g in range(1, 5) for s in range(1, 5)],
    'validation': [f'proxy_validation_{g}_{s}' for g in range(1, 3) for s in range(1, 5)],
    'proxy_test': [f'proxy_test_{g}_{s}' for g in range(1, 5) for s in range(1, 3)],
    'target_test': [f'target_test_{g}_{s}' for g in range(1, 5) for s in range(1, 3)],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('Unexpected contract fields')


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=unique, parse_constant=reject)


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def checked_file(root, name):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Expected real bundle directory')
    if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_]+\.(npy|json|png)', name):
        raise ValueError('Only fixed flat bundle filenames are allowed')
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected regular bundle file')
    if path.stat().st_nlink != 1:
        raise ValueError('Bundle hard links are not allowed')
    return path


def inventory(root, expected):
    if {p.name for p in Path(root).iterdir()} != set(expected):
        raise ValueError('Unexpected bundle inventory')
    for name in expected:
        checked_file(root, name)


def array_record(path, dtype='float32'):
    path = Path(path)
    if path.stat().st_size > 200000:
        raise ValueError('Latent file exceeds expected size')
    value = np.load(path, allow_pickle=False)
    if value.shape != SHAPE or value.dtype != np.dtype(dtype) or not np.isfinite(value).all():
        raise ValueError('Invalid latent shape, dtype or values')
    return dict(path=path.name, sha256=sha(path), bytes=path.stat().st_size,
                shape=list(SHAPE), dtype=dtype)


def save_array(path, value, dtype):
    value = np.asarray(value)
    if value.dtype != np.dtype(dtype) or value.shape != SHAPE or not np.isfinite(value).all():
        raise ValueError('Array must already have the declared finite dtype and shape')
    with Path(path).open('xb') as stream:
        np.save(stream, value, allow_pickle=False)
    return array_record(path, dtype)


def png_record(path):
    path = Path(path)
    with Image.open(path) as image:
        image.load()
        if image.format != 'PNG' or image.mode != 'RGB' or image.size != (512, 512):
            raise ValueError('Expected RGB512 PNG')
    return dict(path=path.name, sha256=sha(path), bytes=path.stat().st_size)


def save_png_readback(image, path):
    """Return the saved image, requiring exact generated-PIL pixel equivalence."""
    if image.mode != 'RGB' or image.size != (512, 512):
        raise ValueError('Expected generated RGB512 image')
    before = image.tobytes()
    with Path(path).open('xb') as stream:
        image.save(stream, format='PNG')
    record = png_record(path)
    with Image.open(path) as saved:
        saved.load()
        if saved.tobytes() != before:
            raise ValueError('PNG roundtrip changed pixels')
        result = saved.copy()
    return result, record


def load_bundle(folder, split, manifest_sha256):
    """Load exactly one frozen split. Test bundles have inverse tensors only."""
    folder = Path(folder)
    manifest = checked_file(folder, 'bundle.json')
    if sha(manifest) != manifest_sha256:
        raise ValueError('Bundle manifest hash mismatch')
    data = read(manifest)
    keys(data, ['version', 'split', 'rows'])
    if type(data['version']) is not int or data['version'] != 1 or data['split'] != split or split not in SPLITS:
        raise ValueError('Wrong bundle role/version')
    if not isinstance(data['rows'], list) or len(data['rows']) != len(SPLITS[split]):
        raise ValueError('Incomplete fixed split')
    labels_allowed = split in ('train', 'validation')
    expected = {'bundle.json'}; result = []
    for sid, row in zip(SPLITS[split], data['rows']):
        fields = ['sample_id', 'estimate', 'original_noise'] if labels_allowed else ['sample_id', 'estimate']
        keys(row, fields)
        if row['sample_id'] != sid:
            raise ValueError('Changed, duplicate or reordered sample ID')
        loaded = {'sample_id': sid}
        for name in fields[1:]:
            rec = row[name]
            keys(rec, ['path', 'sha256', 'bytes', 'shape', 'dtype'])
            filename = sid + '_' + name + '.npy'
            if rec['path'] != filename:
                raise ValueError('Input filename mismatch')
            path = checked_file(folder, filename); expected.add(filename)
            if array_record(path) != rec:
                raise ValueError('Input array hash or metadata mismatch')
            loaded[name] = np.load(path, allow_pickle=False)
        if labels_allowed:
            loaded.update(role='proxy_train' if split == 'train' else 'proxy_validation', generator_role='proxy')
        result.append(loaded)
    inventory(folder, expected)
    if sha(manifest) != manifest_sha256:
        raise ValueError('Manifest changed during read')
    return result


def export_bundle(folder, split, entries):
    """Controller-only explicit copy. Caller must authenticate source generation records."""
    if split not in SPLITS or list(entries) != SPLITS[split]:
        raise ValueError('Source identities/order mismatch')
    folder = Path(folder); folder.mkdir()
    names = ['estimate', 'original_noise'] if split in ('train', 'validation') else ['estimate']
    rows = []
    for sid in SPLITS[split]:
        keys(entries[sid], names)
        row = {'sample_id': sid}
        for name in names:
            source = Path(entries[sid][name]); before = array_record(source)
            destination = folder / (sid + '_' + name + '.npy')
            with destination.open('xb') as stream:
                stream.write(source.read_bytes())
            rec = array_record(destination)
            if rec['sha256'] != before['sha256']:
                raise ValueError('Source changed while exporting')
            row[name] = rec
        rows.append(row)
    write(folder / 'bundle.json', dict(version=1, split=split, rows=rows))
    digest = sha(folder / 'bundle.json')
    load_bundle(folder, split, digest)
    return digest


def model_document(model):
    return dict(version=1, mean=model['mean'].tolist(), scale=model['scale'].tolist(),
                coefficients=model['coefficients'].tolist(), ridge=model['ridge'],
                train_sample_ids=model['train_sample_ids'])


def load_model(path, digest):
    if sha(path) != digest:
        raise ValueError('Fitted model hash mismatch')
    data = read(path)
    keys(data, ['version', 'mean', 'scale', 'coefficients', 'ridge', 'train_sample_ids'])
    if data['version'] != 1 or data['ridge'] != .001 or data['train_sample_ids'] != SPLITS['train']:
        raise ValueError('Fitted model contract mismatch')
    for name, shape in [('mean', (8,)), ('scale', (8,)), ('coefficients', (9, 4))]:
        data[name] = np.asarray(data[name], dtype=np.float64)
        if data[name].shape != shape or not np.isfinite(data[name]).all():
            raise ValueError('Invalid fitted model array')
    if np.any(data['scale'] < 1e-6):
        raise ValueError('Invalid fitted feature scale')
    return data


def seal(folder, filenames, metadata):
    folder = Path(folder)
    inventory(folder, filenames)
    payload = dict(version=1, files={name: sha(checked_file(folder, name)) for name in sorted(filenames)},
                   metadata=metadata)
    write(folder / 'seal.json', payload)
    return sha(folder / 'seal.json')


def verify_seal(folder, digest):
    folder = Path(folder)
    if sha(checked_file(folder, 'seal.json')) != digest:
        raise ValueError('Seal hash mismatch')
    value = read(folder / 'seal.json'); keys(value, ['version', 'files', 'metadata'])
    if value['version'] != 1 or not isinstance(value['files'], dict):
        raise ValueError('Invalid seal')
    inventory(folder, set(value['files']) | {'seal.json'})
    for name, expected in value['files'].items():
        if sha(checked_file(folder, name)) != expected:
            raise ValueError('Sealed artifact changed')
    return value
