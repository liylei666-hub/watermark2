"""Fit once using proxy labels, seal fit, then evaluate the fixed source gate."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise RuntimeError('CPU fitting requires empty CUDA visibility')
import sys
import time
from pathlib import Path
from io_contract import load_bundle, write, sha, model_document, save_array, seal
from linear_probe import fit, predict, source_gate


def main(train, train_sha, validation, validation_sha, output):
    output = Path(output); output.mkdir()
    started = time.perf_counter()
    records = load_bundle(train, 'train', train_sha)
    model = fit(records)
    write(output / 'model.json', model_document(model))
    model_sha = sha(output / 'model.json')
    # The fitted coefficients are recorded before reading validation labels.
    write(output / 'fit_record.json', dict(model_sha256=model_sha, train_sha256=train_sha,
          fitting_seconds=time.perf_counter() - started, fit_count=1,
          feature_code_sha256=sha(Path(__file__).with_name('linear_probe.py'))))
    rows = load_bundle(validation, 'validation', validation_sha)
    baseline = [row['estimate'] for row in rows]
    originals = [row['original_noise'] for row in rows]
    corrected = [predict(model, value) for value in baseline]
    filenames = ['model.json', 'fit_record.json', 'source_gate.json']
    for row, value in zip(rows, corrected):
        name = row['sample_id'] + '_corrected.npy'
        save_array(output / name, value, 'float64'); filenames.append(name)
    gate = source_gate(baseline, corrected, originals)
    gate.update(sample_ids=[row['sample_id'] for row in rows], validation_sha256=validation_sha,
                model_sha256=model_sha, target_labels_read=False)
    write(output / 'source_gate.json', gate)
    digest = seal(output, filenames, dict(kind='source_gate', train_sha256=train_sha,
                 validation_sha256=validation_sha, model_sha256=model_sha,
                 feature_code_sha256=sha(Path(__file__).with_name('linear_probe.py'))))
    print('COMPLETED_SOURCE_FIT ' + digest, flush=True)
    return gate, digest


if __name__ == '__main__':
    if len(sys.argv) != 6:
        raise SystemExit('train train_sha validation validation_sha output required')
    main(*sys.argv[1:])
