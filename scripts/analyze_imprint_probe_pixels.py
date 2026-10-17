"""Post-hoc CPU pixel-displacement audit of all frozen stage11 probes."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('Set CUDA_VISIBLE_DEVICES="" for this CPU audit')
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def pixels(path, expected_hash):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
    with Image.open(path) as image:
        image.load()
        assert image.mode == 'RGB' and image.size == (512, 512)
        return np.asarray(image).astype(np.int16)


def audit(run, protocol):
    cfg = load(protocol)
    root = protocol.resolve().parents[1]
    summary = load(run/'summary.json')
    rows = []
    for point in summary['points']:
        specification = next(x for x in cfg['points'] if x['step'] == point['step'])
        latent = cfg['inputs'][specification['latent']]['path']
        folder = (root/latent.removeprefix('/data0/liyanlei/watermark_research/')).parent
        baseline_hash = load(folder/'candidate_frozen.json')['sha256']
        baseline = pixels(folder/'candidate.png', baseline_hash)
        for probe in point['probes']:
            for sign, record in probe['signed_probes'].items():
                suffix = '_minus' if sign == '-1' else '_plus'
                path = run/f"point_{point['step']}"/(probe['direction']+suffix+'.png')
                candidate = pixels(path, record['png_sha256'])
                delta = candidate-baseline
                rows.append(dict(step=point['step'], direction=probe['direction'], sign=int(sign),
                    png_sha256=record['png_sha256'], baseline_png_sha256=baseline_hash,
                    rgb_coordinate_rmse_0_255=float(np.sqrt(np.mean(delta.astype(np.float64)**2))),
                    max_abs_rgb_difference=int(np.abs(delta).max()),
                    changed_rgb_coordinate_fraction=float(np.mean(delta != 0))))
    assert len(rows) == 8
    return dict(analysis_role='Post-hoc descriptive cost check; all predefined probes retained',
        pixel_range=[0,255], baseline='Unperturbed saved stage10 PNG at the same fixed point',
        rows=rows, content_validity=None, perceptual_equivalence=None,
        target_scores_used=False, verifier_gpu_used=False, models_loaded=False,
        limitation='Equal latent RMS does not imply equal pixel displacement; RGB error is not a semantic or perceptual judgment.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('protocol', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = audit(args.run, args.protocol)
    with args.output.open('x', encoding='utf-8', newline='\n') as file:
        json.dump(result,file,indent=2); file.write('\n')
    print(json.dumps(result,indent=2))
