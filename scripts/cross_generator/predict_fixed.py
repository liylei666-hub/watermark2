"""CPU prediction from sealed source fit and inverse-only test bundles."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise RuntimeError('CPU prediction requires empty CUDA visibility')
import sys
from pathlib import Path
from io_contract import verify_seal, load_model, load_bundle, read, sha, save_array, seal, SPLITS
from linear_probe import predict


def source_model(folder, seal_sha):
    folder = Path(folder); value = verify_seal(folder, seal_sha)
    meta = value['metadata']
    if meta.get('kind') != 'source_gate':
        raise ValueError('Expected source seal')
    if meta['feature_code_sha256'] != sha(Path(__file__).with_name('linear_probe.py')):
        raise ValueError('Feature code changed after source fit')
    gate = read(folder / 'source_gate.json')
    if gate.get('pass') is not True or gate['sample_ids'] != SPLITS['validation']:
        raise ValueError('Source validation gate did not pass')
    if gate['model_sha256'] != meta['model_sha256'] or gate['validation_sha256'] != meta['validation_sha256']:
        raise ValueError('Source receipt mismatch')
    return load_model(folder / 'model.json', meta['model_sha256'])


def main(source, source_sha, inputs, split, inputs_sha, output):
    if split not in ('proxy_test', 'target_test'):
        raise ValueError('Test prediction requires one complete test split')
    model = source_model(source, source_sha)
    rows = load_bundle(inputs, split, inputs_sha)
    output = Path(output); output.mkdir()
    filenames = []
    for row in rows:
        sid = row['sample_id']
        for suffix, value, dtype in [('baseline', row['estimate'], 'float32'),
                                      ('corrected', predict(model, row['estimate']), 'float64')]:
            name = sid + '_' + suffix + '.npy'
            save_array(output / name, value, dtype); filenames.append(name)
    # Inputs are checked again before publishing the prediction seal.
    load_bundle(inputs, split, inputs_sha)
    verify_seal(source, source_sha)
    digest = seal(output, filenames, dict(kind='predictions', split=split,
                  input_sha256=inputs_sha, source_seal_sha256=source_sha,
                  sample_ids=SPLITS[split], target_labels_read=False))
    print('COMPLETED_FIXED_PREDICTIONS ' + digest, flush=True)
    return digest


if __name__ == '__main__':
    if len(sys.argv) != 7:
        raise SystemExit('source source_sha inputs split inputs_sha output required')
    main(*sys.argv[1:])
