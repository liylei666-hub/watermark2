"""CPU-only evidence bookkeeping; consumes labels, never runs a detector."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re


EVENTS = ("reference_valid", "content_met", "forgery_in_scope", "watermark_pass", "full_defense_accept")
FIELDS = {"task_id", "group", "run_status", "candidate", *EVENTS}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tri_and(values):
    values = list(values)
    require(all(v is None or type(v) is bool for v in values), "Events must be bool or null")
    if any(v is False for v in values):
        return False
    return None if any(v is None for v in values) else True


def verified_candidate(root, candidate):
    require(type(candidate) is dict and set(candidate) == {"path", "sha256"}, "Invalid candidate fields")
    name, digest = candidate["path"], candidate["sha256"]
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name, "Use a repository-relative POSIX path")
    rel = PurePosixPath(name)
    require(not rel.is_absolute() and ".." not in rel.parts, "Candidate path escapes root")
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), "Candidate absent or outside root")
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "Invalid SHA256")
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "Candidate SHA256 mismatch")


def summarize(document, root):
    require(type(document) is dict and set(document) == {"schema_version", "scope", "full_defense_protocol_complete", "planned_tasks", "records"}, "Invalid document fields")
    require(type(document["schema_version"]) is int and document["schema_version"] == 1, "Unsupported schema")
    require(document["scope"] == "single_output", "Only single-output aggregation is supported")
    complete = document["full_defense_protocol_complete"]
    require(type(complete) is bool or complete is None, "Protocol availability must be bool or null")
    tasks, records = document["planned_tasks"], document["records"]
    require(type(tasks) is list and type(records) is list, "Tasks and records must be lists")
    require(all(type(t) is dict and set(t) == {"task_id", "group"} for t in tasks), "Invalid planned task")
    require(all(isinstance(t[k], str) and t[k] for t in tasks for k in ("task_id", "group")), "Empty task/group")
    planned = {t["task_id"]: t["group"] for t in tasks}
    require(len(planned) == len(tasks), "Duplicate planned task")
    seen = set()
    groups = {g: [] for g in planned.values()}
    for row in records:
        require(type(row) is dict and set(row) == FIELDS, "Invalid record fields")
        tid = row["task_id"]
        require(isinstance(tid, str) and tid in planned and tid not in seen, "Unexpected or duplicate task")
        require(row["group"] == planned[tid], "Group differs from frozen task list")
        seen.add(tid)
        require(row["run_status"] in ("completed", "failed", "not_started"), "Invalid run status")
        for key in EVENTS:
            require(row[key] is None or type(row[key]) is bool, "Event must be bool or null: " + key)
        require(complete is True or row["full_defense_accept"] is None, "Full defense label requires complete protocol")
        delivered = row["run_status"] == "completed"
        if delivered:
            verified_candidate(root, row["candidate"])
        else:
            require(row["candidate"] is None, "Failed/unstarted task cannot supply a delivered candidate")
            require(all(row[k] is None for k in EVENTS if k != "reference_valid"), "Undelivered task must not carry candidate labels")
        result = tri_and([delivered] + [row[k] for k in EVENTS if k != "reference_valid"])
        groups[row["group"]].append((row, delivered, result))
    require(seen == set(planned), "Missing planned task records; denominator cannot shrink")
    output = {}
    for group, entries in sorted(groups.items()):
        valid = [(r, d, s) for r, d, s in entries if r["reference_valid"] is True]
        n = len(valid)
        successes = sum(s is True for _, _, s in valid)
        unknown = sum(s is None for _, _, s in valid)
        wm_true = sum(d and r["watermark_pass"] is True for r, d, _ in valid)
        wm_unknown = sum(d and r["watermark_pass"] is None for r, d, _ in valid)
        output[group] = {
            "planned_tasks": len(entries),
            "reference_valid": n,
            "reference_invalid": sum(r["reference_valid"] is False for r, _, _ in entries),
            "reference_unknown": sum(r["reference_valid"] is None for r, _, _ in entries),
            "completed": sum(d for _, d, _ in entries),
            "failed": sum(r["run_status"] == "failed" for r, _, _ in entries),
            "not_started": sum(r["run_status"] == "not_started" for r, _, _ in entries),
            "watermark_pass_among_valid_references": wm_true,
            "watermark_outcome_unknown_among_valid_references": wm_unknown,
            "watermark_task_rate_among_valid_references": wm_true / n if n and not wm_unknown else None,
            "joint_success_known_true": successes,
            "joint_success_known_false": sum(s is False for _, _, s in valid),
            "joint_success_unknown": unknown,
            "full_defense_joint_rate": successes / n if complete is True and n and not unknown else None,
            "descriptive_identification_bounds": [successes / n, (successes + unknown) / n] if complete is True and n else None,
        }
    return {"schema_version": 1, "scope": "single_output", "full_defense_protocol_complete": complete,
            "groups": output, "label_semantics_verified_by_tool": False,
            "gpu_used": False, "models_loaded": False, "new_model_experiments_run": 0}


def main():
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "", 'Set CUDA_VISIBLE_DEVICES=""')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(json.loads(args.input.read_text(encoding="utf-8")), args.root)
    result["input_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    with args.output.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
