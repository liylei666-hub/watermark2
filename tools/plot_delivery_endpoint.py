"""Plot the closed stage25 paired scores, without loading models or fitting data."""
import os
if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
    raise SystemExit("Set CUDA_VISIBLE_DEVICES='' for this CPU-only figure.")
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/25_delivery_transfer/verification.json"
OUT = ROOT / "reports/27_recovery_audit_20261019"
data = json.loads(SOURCE.read_text(encoding="utf-8"))
rows = data["result"]["rows"]
assert len(rows) == 8 and data["verified"] is True
threshold = data["result"]["summary"]["threshold"]
assert threshold == 0.70703125
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "svg.fonttype": "none", "pdf.fonttype": 42})
fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.5), gridspec_kw={"width_ratios": [1, 1.7]})
colors = ["#35618F", "#A85239", "#3C7C69", "#8066A6"]
for i, row in enumerate(rows):
    color = colors[i // 2]
    axes[0].plot([0, 1], [row["baseline"], row["corrected"]], color=color,
                 marker="o" if i % 2 == 0 else "s", markersize=4, alpha=0.85, linewidth=1.1)
axes[0].axhline(threshold, color="#555555", linestyle="--", linewidth=1)
axes[0].text(0.02, threshold + 0.008, "GS threshold (strict >)", color="#555555", fontsize=8)
axes[0].set(xticks=[0, 1], xticklabels=["Baseline", "Corrected"], xlim=(-0.12, 1.12),
            ylim=(0.69, 1.01), ylabel="Target message accuracy", title="a  Delivered-image scores")
differences = [100 * (r["corrected"] - r["baseline"]) for r in rows]
axes[1].barh(range(8), differences, color=[colors[i // 2] for i in range(8)], height=0.6)
axes[1].axvline(0, color="#444444", linewidth=0.8)
axes[1].set(yticks=range(8), yticklabels=[f"Group {i//2+1}, replica {i%2+1}" for i in range(8)],
            xlim=(-11, 0.8), xlabel="Corrected - baseline (percentage points)",
            title="b  Paired changes")
axes[1].invert_yaxis()
for i, value in enumerate(differences):
    axes[1].text(value - 0.15 if value < 0 else 0.15, i, f"{value:.2f}",
                 ha="right" if value < 0 else "left", va="center", fontsize=8)
fig.tight_layout(w_pad=2)
OUT.mkdir(parents=True, exist_ok=True)
for suffix in ("png", "svg", "pdf"):
    fig.savefig(OUT / ("delivery_endpoint." + suffix), dpi=220, bbox_inches="tight")
plt.close(fig)
svg = OUT / "delivery_endpoint.svg"
svg.write_bytes(("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n").encode("utf-8"))
manifest = {"source": SOURCE.relative_to(ROOT).as_posix(),
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "rows": 8, "message_accuracy_difference": sum(differences) / 800,
            "plotting_library": "matplotlib " + matplotlib.__version__,
            "files": {f"delivery_endpoint.{s}": hashlib.sha256((OUT / f"delivery_endpoint.{s}").read_bytes()).hexdigest()
                      for s in ("png", "svg", "pdf")}, "models_loaded": False, "gpu_used": False}
(OUT / "figure_manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
print(json.dumps(manifest))
