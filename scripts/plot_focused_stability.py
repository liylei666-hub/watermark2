"""Plot already-audited cal-only trajectories; no model inference."""
import argparse, csv, json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    args = ap.parse_args()
    root = Path(args.run)
    audit = json.loads((root / 'trace_audit.json').read_text(encoding='utf8'))
    assert audit['status'] == 'passed'
    cpu = json.loads((root / 'cpu/cpu_results.json').read_text(encoding='utf8'))
    with (root / 'cross_swap_counts.csv').open('w', newline='', encoding='utf8') as f:
        names = ['source', 'recon_input', 'semantic_input', 'E', 'D', 'E_intersect_D', 'A', 'A_outside_E']
        w = csv.DictWriter(f, fieldnames=names, extrasaction='ignore')
        w.writeheader()
        w.writerows(cpu['rows'])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    colors = {'c04': '#b84437', 'c02': '#247b90'}
    names = {'c04': 'c04 shoe', 'c02': 'c02 cat (frozen control)'}
    trajectory_rows = []
    for sid in ('c04', 'c02'):
        d = audit['diagnostics'][sid]
        values = d['trajectory_pair_rmse']
        axes[0].plot(range(51), values, label=names[sid], color=colors[sid], lw=2)
        axes[1].plot(range(51), [x / values[0] for x in values], label=names[sid], color=colors[sid], lw=2)
        for i, v in enumerate(values):
            trajectory_rows.append({'source': sid, 'update_index': i, 'scaled_latent_pair_rmse': v, 'ratio_to_initial_rmse': v / values[0]})
    axes[0].set_ylabel('Original / JPEG70 pair RMSE\n(scaled latent coordinates)')
    axes[1].set_ylabel('Pair RMSE / initial pair RMSE\n(same coordinate space)')
    for ax in axes:
        ax.set_xlabel('Recorded inversion update index (0 = scaled VAE mode)')
        ax.grid(alpha=.22)
        ax.legend(frameon=False, fontsize=8)
    axes[0].set_title('Native fp16 trace: two calibration sources')
    axes[1].set_title('Relative trace divergence')
    fig.savefig(root / 'trajectory_rmse.png', dpi=180)
    fig.savefig(root / 'trajectory_rmse.svg')
    plt.close(fig)
    with (root / 'trajectory_rmse.csv').open('w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=list(trajectory_rows[0]))
        w.writeheader()
        w.writerows(trajectory_rows)
    print('saved cross-swap CSV and 102-state trajectory CSV/PNG/SVG')

if __name__ == '__main__':
    main()
