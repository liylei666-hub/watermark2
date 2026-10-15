"""Evaluator-only arithmetic on archived tensors; Python standard library only."""
import os
if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
    raise SystemExit('Set CUDA_VISIBLE_DEVICES="" for this CPU-only analysis.')
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import verify_archive as archive


def decomposition(a, b):
    if not a or len(a) != len(b):
        raise ValueError("Equal nonempty vectors required")
    if any(not math.isfinite(v) or v == 0 for v in (*a, *b)):
        raise ValueError("Finite nonzero coordinates required for sign accounting")
    products = [abs(x * y) for x, y in zip(a, b)]
    mass = math.fsum(products)
    denominator = math.sqrt(math.fsum(x*x for x in a)) * math.sqrt(math.fsum(y*y for y in b))
    magnitude_cosine = mass / denominator
    mismatch = [((x > 0) != (y > 0)) for x, y in zip(a, b)]
    weighted_error = math.fsum(p for p, bad in zip(products, mismatch) if bad) / mass
    cosine = archive.cosine(a, b)
    magnitude_deficit = 1 - magnitude_cosine
    sign_penalty = 2 * magnitude_cosine * weighted_error
    error = abs((1 - cosine) - (magnitude_deficit + sign_penalty))
    if error > 1e-12:
        raise ArithmeticError("Cosine decomposition identity failed")
    return dict(cosine=cosine, coordinate_sign_agreement=1-sum(mismatch)/len(a),
                magnitude_cosine=magnitude_cosine, weighted_sign_error=weighted_error,
                magnitude_deficit=magnitude_deficit, sign_penalty=sign_penalty,
                identity_absolute_error=error)


def vote_bounds(a, b, width=256, repetitions=64):
    """With l=1, stream-cipher XOR preserves errors; ties depend on message bits.

    Does not read keys/messages or implement the target detector. Returns bounds
    implied by archived sign errors, to compare with already recorded message BA.
    """
    if len(a) != len(b) or len(a) != width * repetitions:
        raise ValueError("Wrong repetition dimensions")
    counts = [sum((a[r*width+j] > 0) == (b[r*width+j] > 0)
                  for r in range(repetitions)) for j in range(width)]
    good = sum(n > repetitions/2 for n in counts)
    tied = sum(n == repetitions/2 for n in counts)
    return dict(vote_accuracy_lower=good/width, vote_accuracy_upper=(good+tied)/width,
                tied_message_positions=tied)


def summarize(rows):
    fields = ["cosine", "coordinate_sign_agreement", "magnitude_cosine", "weighted_sign_error",
              "magnitude_deficit", "sign_penalty", "recorded_message_bit_accuracy"]
    return {field: {"mean": statistics.mean(r[field] for r in rows),
                    "min": min(r[field] for r in rows), "max": max(r[field] for r in rows)}
            for field in fields}


def analyze():
    # Validate the full current manifest separately before publication. This
    # analysis validates each input binding even when output files are refreshed.
    data, rows, inputs = {}, [], []
    for seed in range(1, 10):
        run = archive.U4 if seed == 1 else archive.U5 / f"seed_{seed}"
        cfg = run / ("config.json" if seed == 1 else "evaluator_only/config.json")
        manifest, _, metrics, _ = archive.check_recorded_run(run, cfg)
        arrays = {}
        for name, record in manifest["tensors"].items():
            path = archive.resolve(record["path"])
            arrays[name] = archive.float32_npy(path)
            inputs.append(dict(seed=seed, role=name, path=path.relative_to(ROOT).as_posix(), sha256=archive.sha(path)))
        data[seed] = arrays
        z = arrays["target_original_wm_zT"]
        for role, step in [("reference", -1), ("forged", 1)]:
            y = arrays[f"target_inverted_{role}_zT"]
            row = dict(seed=seed, role=role, **decomposition(z, y), **vote_bounds(z, y))
            row["recorded_message_bit_accuracy"] = float(metrics[step]["bit_accuracy"])
            row["vote_bounds_match_recorded_accuracy"] = (row["vote_accuracy_lower"] <= row["recorded_message_bit_accuracy"] <= row["vote_accuracy_upper"])
            if not row["vote_bounds_match_recorded_accuracy"]:
                raise ArithmeticError("Archived BA inconsistent with sign-vote bounds")
            rows.append(row)
    cross = []
    for refseed in data:
        z = data[refseed]["target_original_wm_zT"]
        for candidateseed in data:
            for role in ["original", "reference", "forged"]:
                name = "target_original_wm_zT" if role == "original" else f"target_inverted_{role}_zT"
                y = data[candidateseed][name]
                d = decomposition(z, y)
                cross.append(dict(reference_seed=refseed, candidate_seed=candidateseed,
                                  role=role, cosine=d["cosine"],
                                  coordinate_sign_agreement=d["coordinate_sign_agreement"]))
    groups = {}
    for label, seeds in [("stage05_primary", list(range(2,10))), ("stage04_supplement", [1])]:
        group = {"seeds": seeds, "n": len(seeds)}
        for role in ["reference", "forged"]:
            group[role] = summarize([r for r in rows if r["seed"] in seeds and r["role"] == role])
        off = [r for r in cross if r["reference_seed"] in seeds and r["candidate_seed"] in seeds and r["reference_seed"] != r["candidate_seed"]]
        group["cross_reference"] = {}
        for role in ["original", "reference", "forged"]:
            subset = [r for r in off if r["role"] == role]
            diag = [r for r in cross if r["role"] == role and r["reference_seed"] == r["candidate_seed"] and r["reference_seed"] in seeds]
            group["cross_reference"][role] = dict(ordered_dependent_pairs=len(subset),
                off_diagonal_cosine_mean=statistics.mean(r["cosine"] for r in subset) if subset else None,
                diagonal_cosine_mean=statistics.mean(r["cosine"] for r in diag),
                off_diagonal_sign_agreement_mean=statistics.mean(r["coordinate_sign_agreement"] for r in subset) if subset else None)
        groups[label] = group
    summary = dict(analysis_role="exploratory_evaluator_diagnostic", groups=groups,
        all_vote_bounds_consistent=True, max_identity_error=max(r["identity_absolute_error"] for r in rows),
        existing_tensor_files_read=len(inputs), tensor_sources_sha256=inputs,
        gpu_used=False, models_loaded=False, new_model_experiments_run=0,
        geometry_threshold=None, geometry_accepted=None,
        full_official_geometry_evaluation_completed=False)
    return rows, cross, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows, cross, summary = analyze()
    args.output.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects earlier derived results. Use a temporary
    # output directory to verify reproducibility before replacing a report.
    for filename, records in [("per_sample.csv", rows), ("cross_reference.csv", cross)]:
        with (args.output / filename).open("x", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    with (args.output / "summary.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({k: v for k,v in summary.items() if k != "tensor_sources_sha256"}, indent=2))


if __name__ == "__main__":
    main()
