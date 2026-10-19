"""Read-only, standard-library provenance audit; never imports model code.

Run with CUDA_VISIBLE_DEVICES='' and --root pointing at the evidence tree.
The active run snapshot is observational, not a completion or efficacy verdict.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError("Path escapes evidence root: " + str(relative))
    return path


def verify_map(root, expected):
    errors = []
    for relative, digest in expected.items():
        path = inside(root, relative)
        if not path.is_file():
            errors.append({"path": relative, "error": "missing"})
        elif sha(path) != digest:
            errors.append({"path": relative, "error": "hash_mismatch"})
    return {"expected": len(expected), "verified": len(expected) - len(errors), "errors": errors}


def inheritance_check(root, meta):
    errors, records = [], []
    overlap = set(meta["completed"]) & set(meta["failed"])
    if overlap:
        errors.append({"error": "overlapping_inheritance", "tasks": sorted(overlap)})
    for category in ("completed", "failed"):
        for name, entry in sorted(meta[category].items()):
            folder = inside(root, entry["path"])
            path = folder / "execution.json"
            if sha(path) != entry["sha256"]:
                errors.append({"task": name, "error": "execution_hash_mismatch"})
            ex = read(path)
            successful = ex.get("completed") is True and ex.get("exit_code") == 0 and not ex.get("timed_out")
            if (category == "completed") != successful:
                errors.append({"task": name, "error": "completion_classification_mismatch"})
            if category == "failed" and (ex.get("exit_code") == 0 or (folder / "candidate.png").exists()):
                errors.append({"task": name, "error": "failed_task_has_success_or_candidate"})
            records.append({"task": name, "category": category, "path": entry["path"],
                            "execution_sha256": sha(path), "exit_code": ex["exit_code"],
                            "elapsed_seconds": ex["elapsed_seconds"]})
    return {"records": records, "errors": errors,
            "process_seconds": sum(r["elapsed_seconds"] for r in records)}


def audit(root):
    root = Path(root).resolve()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    runtime = root / "protocols/27_method_runtime_r4.json"
    cfg = read(runtime)
    source, current = inside(root, cfg["source_run"]), inside(root, cfg["run_dir"])
    frozen_design = read(root / "protocols/27_method_design.json")
    original = read(root / "protocols/27_method_runtime_r2.json")
    checks = {
        "runtime_sidecar_matches": sha(runtime) == runtime.with_suffix(".sha256").read_text().strip(),
        "scientific_design_unchanged": cfg["design"] == frozen_design == original["design"],
        "allowed_devices_unchanged": cfg["allowed_gpu_uuids"] == original["allowed_gpu_uuids"],
        "storage_cap_unchanged": cfg["max_new_bytes"] == original["max_new_bytes"] == 10 * 1024**3,
        "serial_no_downloads": cfg["serial"] is True and cfg["new_model_downloads"] is False,
        "live_inheritance_matches": read(current / "inheritance.json") == cfg["inheritance"],
        "launch_runtime_binding": read(current / "launch_intent.json")["runtime_sha256"] == sha(runtime),
    }
    maps = {
        "source_files": verify_map(source, cfg["source_files"]),
        "copied_files": verify_map(current, cfg["copied_files"]),
        "historical_execution_files": verify_map(root, cfg["historical_execution_hashes"]),
    }
    remote_prefix = "/data0/liyanlei/watermark_research/"
    mapped_code = {}
    for path, digest in cfg["code_hashes"].items():
        if not path.startswith(remote_prefix):
            raise ValueError("Unexpected code root")
        mapped_code[path[len(remote_prefix):]] = digest
    maps["runtime_code_files"] = verify_map(root, mapped_code)
    inherited = inheritance_check(root, cfg["inheritance"])
    source_inventory = {p.parent.relative_to(source).as_posix() for p in source.rglob("execution.json")}
    checks["all_original_processes_accounted"] = source_inventory == set(cfg["inheritance"]["completed"]) | set(cfg["inheritance"]["failed"])
    checks["failed_task_not_relaunched"] = all(not inside(current, name).exists() for name in cfg["inheritance"]["failed"])
    completed, unfinished = [], []
    for path in sorted(current.rglob("execution.json")):
        ex = read(path)
        completed.append({"task": path.parent.relative_to(current).as_posix(), "sha256": sha(path),
                          "completed": ex["completed"], "exit_code": ex["exit_code"], "elapsed_seconds": ex["elapsed_seconds"]})
    for path in sorted(current.rglob("process.json")):
        if not (path.parent / "execution.json").exists():
            process = read(path)
            unfinished.append({"task": path.parent.relative_to(current).as_posix(), "pid": process["pid"],
                               "started_at_utc": process["started_at_utc"]})
    optional = {}
    for name in ("scheduler_status.json", "status.json"):
        path = current / name
        optional[name] = read(path) if path.exists() else None
    passed = all(checks.values()) and not inherited["errors"] and all(not m["errors"] for m in maps.values())
    return {"schema": 1, "read_started_at_utc": started,
            "read_finished_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scope": "Immutable provenance checks plus a non-atomic active-run file snapshot; no process liveness or scientific endpoint verification.",
            "provenance_passed": passed, "runtime_sha256": sha(runtime), "source_run": cfg["source_run"],
            "continuation_run": cfg["run_dir"], "checks": checks, "hash_maps": maps,
            "inherited": inherited, "continuation_execution_records": completed,
            "unfinished_process_records": unfinished, "status_files": optional,
            "planned_denominators": {"tasks_per_method": 12, "candidate_slots": 36,
                "maximum_deliverable_candidates": 35, "maximum_target_inversions": 59,
                "primary_delivery_imprint_pairs": 12, "jain_failed_task_ids": [2]},
            "scientific_endpoint_verified": False, "models_loaded": False, "new_model_processes": 0,
            "full_defense_acceptance": None, "formal_human_labels": None}


if __name__ == "__main__":
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise SystemExit("CPU-only audit requires CUDA_VISIBLE_DEVICES=''")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
    raise SystemExit(0 if result["provenance_passed"] else 1)
