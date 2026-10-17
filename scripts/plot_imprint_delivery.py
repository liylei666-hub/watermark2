"""Render verified measurements and unchanged candidate images as a research figure."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU plotting requires CUDA_VISIBLE_DEVICES=""')
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('analysis', type=Path)
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = json.loads(args.analysis.read_text(encoding='utf-8'))
    assert data['status'] == 'verified'
    rows = data['checkpoints']
    if args.output.exists():
        raise FileExistsError(args.output)
    fig = plt.figure(figsize=(12, 7), layout='constrained')
    grid = fig.add_gridspec(2, 4, height_ratios=[1, 1.15])
    loss = fig.add_subplot(grid[0, :2])
    gap = fig.add_subplot(grid[0, 2:])
    steps = [r['step'] for r in rows]
    for key, label, style in [('internal_loss', 'Internal latent', '-o'),
                              ('float_delivery_loss', 'Float decode / encode', '--s'),
                              ('png_delivery_loss', 'PNG delivery', ':^')]:
        loss.plot(steps, [r[key] for r in rows], style, label=label)
    loss.set(xlabel='Completed optimizer updates', ylabel='Proxy inversion MSE',
             title='Same latent, three measured paths', xticks=steps)
    loss.legend(fontsize=8)
    gap.plot(steps, [r['png_minus_internal'] for r in rows], '-o', color='#a34424')
    gap.axhline(0, color='gray', linewidth=.7)
    gap.set(xlabel='Completed optimizer updates', ylabel='PNG MSE minus internal MSE',
            title='Delivery gap', xticks=steps)
    for ax in [loss, gap]:
        ax.grid(alpha=.2)
    for column, row in enumerate(rows):
        ax = fig.add_subplot(grid[1, column])
        with Image.open(args.run / f"checkpoint_{row['step']}" / 'candidate.png') as im:
            ax.imshow(im)
        ax.set_title(f"Update {row['step']}")
        ax.axis('off')
    fig.suptitle('Native Imprint diagnostic: one development reference / cover pair\n'
                 'Proxy measurements; target detection and full defense acceptance unmeasured', fontsize=12)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
