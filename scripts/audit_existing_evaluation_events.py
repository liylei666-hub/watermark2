"""Reconcile stage07 PNG/CSV evidence into an evaluator-side event ledger."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

from summarize_evaluation_events import require, summarize

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/07_prompt_control_20261016T011923Z"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    protocol = json.loads((RUN / "protocol.json").read_text(encoding="utf-8"))
    require(digest(RUN / "protocol.json") == (RUN / "protocol.sha256").read_text().strip(), "Protocol changed")
    planned, records, sources = [], [], []
    for seed in protocol["seeds"]:
        for arm in protocol["arms_in_order"]:
            task = f"seed_{seed}_{arm}"
            run = RUN / task
            execution_path = run / "execution.json"
            execution = json.loads(execution_path.read_text(encoding="utf-8"))
            require(execution["exit_code"] == 0 and (run / "exit_code.txt").read_text().strip() == "0", "Historical task not complete")
            images = run / "evaluator_only/official_output/target_prompt_index=custom/attacker_prompt_index=custom"
            csv_path = images / "metrics.csv"
            with csv_path.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            require(len(rows) == 2, "Unexpected CSV row count")
            metrics = {int(row["step"]): row for row in rows}
            require(set(metrics) == {-1, 1}, "Unexpected CSV step semantics")
            for row in metrics.values():
                require(row["detection_successful"] in ("True", "False"), "Invalid recorded GS boolean")
                require((float(row["bit_accuracy"]) > protocol["gs_threshold"]) == (row["detection_successful"] == "True"), "CSV GS semantics mismatch")
            require(protocol["gs_comparator"] == ">", "Unexpected comparator")
            manifest_path = run / "evaluator_only/tensor_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            candidate = run / "evaluator_only/candidate_before_evaluation.png"
            require(digest(candidate) == digest(images / "attack_instance_step=1.png") == manifest["images"]["1"]["sha256"], "Frozen candidate differs from evaluated PNG")
            require(digest(images / "attack_instance_step=-1.png") == manifest["images"]["-1"]["sha256"], "Reference hash mismatch")
            planned.append({"task_id": task, "group": arm})
            records.append({"task_id": task, "group": arm, "run_status": "completed",
                "candidate": {"path": candidate.relative_to(ROOT).as_posix(), "sha256": digest(candidate)},
                "reference_valid": metrics[-1]["detection_successful"] == "True",
                "watermark_pass": metrics[1]["detection_successful"] == "True",
                "content_met": None, "forgery_in_scope": None, "full_defense_accept": None})
            for p in (execution_path, csv_path, manifest_path, candidate, images / "attack_instance_step=-1.png"):
                sources.append({"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p)})
    document = {"schema_version": 1, "scope": "single_output", "full_defense_protocol_complete": False,
                "planned_tasks": planned, "records": records}
    provenance = {"data_role": "retrospective_development_bookkeeping", "protocol_sha256": digest(RUN / "protocol.json"),
        "reference_valid_semantics": "Original GS only; does not imply validity under geometry or SemBind",
        "content_labels": "Not rated under a frozen rubric; previous visual descriptions do not supply booleans",
        "forgery_scope_labels": "Not adjudicated; same_prompt remains a separate diagnostic group",
        "candidate_hash_timing": "Original stage07 recording predates evaluation; this ledger is constructed retrospectively",
        "sources": sources}
    return document, provenance


def main():
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "", 'Set CUDA_VISIBLE_DEVICES=""')
    parser = argparse.ArgumentParser(description=__doc__)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--output", type=Path)
    destination.add_argument("--verify", type=Path, help="Rebuild and compare an existing audit without writing")
    args = parser.parse_args()
    document, provenance = build()
    result = summarize(document, ROOT)
    if args.verify is not None:
        for name, expected in (("input.json", document), ("provenance.json", provenance)):
            require(json.loads((args.verify / name).read_text(encoding="utf-8")) == expected, "Audit mismatch: " + name)
        result["input_sha256"] = digest(args.verify / "input.json")
        require(json.loads((args.verify / "summary.json").read_text(encoding="utf-8")) == result, "Audit summary mismatch")
        print("Passed: raw CSV, execution status, PNG binding, event ledger and summary agree.")
        return
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("input.json", document), ("provenance.json", provenance)):
        with (args.output / name).open("x", encoding="utf-8", newline="\n") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
    result["input_sha256"] = digest(args.output / "input.json")
    with (args.output / "summary.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
