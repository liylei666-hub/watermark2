"""Stage24 test-phase file contracts; shared user permissions are not isolation."""
from pathlib import Path
from PIL import Image
import io_contract as c

SOURCE_SEAL = 'f8ac777e009bbd79a91b8fb4768037b209d91653b9bfdc5c0d29a3bd2513ca0c'
SOURCE_FIT = '1d520121b078c03ef6f46bac1c731cb4075b8a09818ed3930cfec07c3effcb9d'


def verify_source(root):
    root = Path(root); path = root / 'source_phase_sealed.json'
    if c.sha(path) != SOURCE_SEAL:
        raise ValueError('Source phase seal changed')
    value = c.read(path)
    for name, digest in value['files'].items():
        p = root / name
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) or c.sha(p) != digest:
            raise ValueError('Source artifact changed: ' + name)
    c.verify_seal(root / 'source_fit', SOURCE_FIT)
    if c.read(root / 'source_fit/source_gate.json')['pass'] is not True:
        raise ValueError('Source gate failed')


def image_bundle(folder, expected_sha):
    folder = Path(folder)
    if c.sha(c.checked_file(folder, 'images.json')) != expected_sha:
        raise ValueError('Image bundle hash changed')
    data = c.read(folder / 'images.json'); c.keys(data, ['version', 'rows'])
    if data['version'] != 1 or len(data['rows']) != 8:
        raise ValueError('Expected eight fixed target images')
    expected = {'images.json'}
    for sid, row in zip(c.SPLITS['target_test'], data['rows']):
        c.keys(row, ['sample_id','image'])
        if row['sample_id'] != sid or row['image']['path'] != sid + '.png':
            raise ValueError('Image association changed')
        path = c.checked_file(folder, sid + '.png'); expected.add(path.name)
        if c.png_record(path) != row['image']:
            raise ValueError('Image changed')
    c.inventory(folder, expected)
    return data


def export_images(folder, paths):
    if list(paths) != c.SPLITS['target_test']:
        raise ValueError('Wrong target image identities')
    folder = Path(folder); folder.mkdir(); rows = []
    for sid, source in paths.items():
        before = c.png_record(source); target = folder / (sid + '.png')
        with target.open('xb') as stream: stream.write(Path(source).read_bytes())
        record = c.png_record(target)
        if record['sha256'] != before['sha256']:
            raise ValueError('Image changed during copy')
        rows.append(dict(sample_id=sid, image=record))
    c.write(folder / 'images.json', dict(version=1,rows=rows))
    digest = c.sha(folder / 'images.json'); image_bundle(folder, digest)
    return digest


def seal_predictions(folder):
    folder = Path(folder); seals = {}
    for split in ('proxy_test','target_test'):
        path = folder / (split + '_predictions')
        digest = c.sha(path / 'seal.json'); value = c.verify_seal(path, digest)
        if value['metadata']['source_seal_sha256'] != SOURCE_FIT or value['metadata']['split'] != split:
            raise ValueError('Prediction provenance mismatch')
        seals[split] = digest
    c.write(folder / 'test_predictions_sealed.json', dict(source_fit_sha256=SOURCE_FIT, predictions=seals))
    return c.sha(folder / 'test_predictions_sealed.json')


def verify_predictions(folder, digest):
    folder = Path(folder)
    if c.sha(folder / 'test_predictions_sealed.json') != digest:
        raise ValueError('Prediction delivery changed')
    value = c.read(folder / 'test_predictions_sealed.json')
    c.keys(value, ['source_fit_sha256','predictions'])
    if value['source_fit_sha256'] != SOURCE_FIT or set(value['predictions']) != {'proxy_test','target_test'}:
        raise ValueError('Wrong prediction collection')
    for split, expected in value['predictions'].items():
        sealed = c.verify_seal(folder / (split + '_predictions'), expected)
        if sealed['metadata']['sample_ids'] != c.SPLITS[split]:
            raise ValueError('Prediction sample identities changed')
    return value
