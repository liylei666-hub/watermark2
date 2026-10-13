"""Read-only, standard-library verification of the published experiment archive."""
import os
if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
    raise SystemExit('Set CUDA_VISIBLE_DEVICES="" before running this CPU-only verifier.')
import ast
import csv
import hashlib
import json
import math
import statistics
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/data0/liyanlei/watermark_research/"
R5 = ROOT / "reports/05_reprompt_seed_pilot_20261013T041832Z"
U5 = ROOT / "runs/05_reprompt_seed_pilot_20261013T041832Z"
U4 = ROOT / "runs/04_reprompt_latent_diag_seed1_20261013T025322Z"
U2 = ROOT / "runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z"

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def resolve(path):
    assert path.startswith(REMOTE), "Unknown historical path prefix"
    p = (ROOT / path[len(REMOTE):]).resolve()
    assert p.is_relative_to(ROOT.resolve())
    return p

def float32_npy(path):
    """Only parse the known non-pickle C-contiguous float32 evidence format."""
    data = Path(path).read_bytes()
    assert data[:6] == b"\x93NUMPY"
    version = tuple(data[6:8])
    assert version in [(1, 0), (2, 0)]
    width, fmt = (2, "<H") if version == (1, 0) else (4, "<I")
    length = struct.unpack(fmt, data[8:8 + width])[0]
    offset = 8 + width + length
    header = ast.literal_eval(data[8 + width:offset].decode("latin1").strip())
    assert header["shape"] == (1, 4, 64, 64)
    assert header["fortran_order"] is False
    assert header["descr"] == "<f4"
    count = math.prod(header["shape"])
    assert len(data) - offset == count * 4
    values = struct.unpack("<" + str(count) + "f", data[offset:])
    assert all(math.isfinite(x) for x in values)
    return values

def cosine(a, b):
    aa = math.fsum(x * x for x in a)
    bb = math.fsum(x * x for x in b)
    assert aa > 0 and bb > 0 and len(a) == len(b)
    return math.fsum(x * y for x, y in zip(a, b)) / (math.sqrt(aa) * math.sqrt(bb))

def csv_metrics(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    result = {int(r["step"]): r for r in rows}
    assert set(result) == {-1, 1}
    for r in rows:
        assert (r["detection_successful"] == "True") == (float(r["bit_accuracy"]) > 0.70703125)
        assert all(float(r[k]) == -1 for k in ["psnr", "ssim", "msssim", "lpips"])
    return result

def check_recorded_run(run, cfg_path):
    d = run / "evaluator_only"
    cfg_hash = sha(cfg_path)
    manifest = load(d / "tensor_manifest.json")
    assert manifest["config_sha256"] == cfg_hash
    assert manifest["counts"] == {"sampling": 1, "target_generate": 1, "proxy_generate": 1, "target_invert": 2, "proxy_invert": 1, "validate": 2}
    assert manifest["original_sampling_object_is_generation_input"] is True
    assert load(run / "execution.json")["exit_code"] == 0
    assert (run / "exit_code.txt").read_text().strip() == "0"
    assert load(d / "diagnostic_exit.json")["exit_code"] == 0
    arrays = {}
    for name, record in manifest["tensors"].items():
        p = resolve(record["path"])
        assert sha(p) == record["sha256"]
        assert sha(resolve(record["image_path"])) == record["image_sha256"]
        assert record["config_sha256"] == cfg_hash
        assert record["role"] == "target" and record["dtype"] == "float32"
        assert record["shape"] == [1, 4, 64, 64] and record["cpu_roundtrip_equal"] is True
        arrays[name] = float32_npy(p)
    assert set(arrays) == {"target_original_wm_zT", "target_inverted_reference_zT", "target_inverted_forged_zT"}
    for r in manifest["images"].values():
        p = resolve(r["path"])
        assert sha(p) == r["sha256"]
        data = p.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == (512, 512)
        assert r["validated_pixels_equal_saved_png"] is True
    frozen = load(d / "candidate_frozen.json")
    assert sha(resolve(frozen["path"])) == frozen["sha256"]
    diag = load(d / "diagnostic.json")
    assert diag["geometry_threshold"] is None and diag["geometry_accepted"] is None
    a = arrays["target_original_wm_zT"]
    ref = cosine(a, arrays["target_inverted_reference_zT"])
    forged = cosine(a, arrays["target_inverted_forged_zT"])
    errors = [abs(ref - diag["gcos_reference"]), abs(forged - diag["gcos_forged"]), abs((ref - forged) - diag["gcos_gap_reference_minus_forged"])]
    assert max(errors) < 1e-12
    mr = csv_metrics(d / "official_output/target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv")
    return manifest, diag, mr, max(errors)

def main():
    published = load(ROOT / "provenance/published_manifest.json")
    for r in published["files"]:
        p = ROOT / r["path"]
        assert p.is_file() and p.stat().st_size == r["bytes"] and sha(p) == r["sha256"], r["path"]
    transformations = {r["path"]: r for r in load(ROOT / "provenance/publication_transformations.json")["files"]}
    sources = load(ROOT / "provenance/source_manifest.json")["files"]
    for r in sources:
        name = "provenance/execution_AGENTS.md" if r["path"] == "AGENTS.md" else r["path"]
        expected = transformations[name]["published_sha256"] if name in transformations else r["sha256"]
        assert sha(ROOT / name) == expected, name
        if name in transformations:
            assert transformations[name]["original_sha256"] == r["sha256"]
    for r in load(ROOT / "provenance/local_sources.json"):
        expected = transformations[r["path"]]["published_sha256"] if r["path"] in transformations else r["sha256"]
        assert sha(ROOT / r["path"]) == expected
    prompts = load(ROOT / "prompts/index.json")
    assert {r["stage"] for r in prompts} == {"01", "02", "03", "04", "05"}
    assert all(sha(ROOT / r["path"]) == r["sha256"] for r in prompts)
    for p in ROOT.rglob("*.json"):
        if ".git" not in p.parts:
            load(p)
    protocol = load(U5 / "pilot_protocol.json")
    assert sha(U5 / "pilot_protocol.json") == (U5 / "pilot_protocol.sha256").read_text().strip()
    assert protocol["planned_seeds"] == list(range(2, 10))
    assert protocol["gpu_physical_index"] == 3
    assert protocol["gpu_uuid"] == "GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da"
    for path, digest in protocol["code_hashes"].items():
        assert sha(resolve(path)) == digest
    group = load(U5 / "group_execution.json")
    assert group["started_seeds"] == group["completed_model_seeds"] == list(range(2, 10))
    assert group["blockers"] == []
    assert load(U5 / "group_started.json")["time"] > protocol["created_at"]
    rows = load(R5 / "per_seed_metrics.json")
    assert [r["seed"] for r in rows] == list(range(2, 10))
    numerical_errors = []
    for row in rows:
        run = U5 / ("seed_" + str(row["seed"]))
        manifest, diag, mr, error = check_recorded_run(run, run / "evaluator_only/config.json")
        numerical_errors.append(error)
        for prefix, step in [("reference", -1), ("forged", 1)]:
            assert row[prefix + "_bit_accuracy"] == float(mr[step]["bit_accuracy"])
            assert row[prefix + "_detected"] == (mr[step]["detection_successful"] == "True")
            assert row["gcos_" + prefix] == diag["gcos_" + prefix]
        assert row["gcos_gap"] == diag["gcos_gap_reference_minus_forged"]
        pre = load(run / "pre_run_check.json")["gpu"]
        assert pre["row"][:2] == ["3", protocol["gpu_uuid"]]
        assert pre["selected_gpu_compute_apps"] == []
        pid = load(run / "process.json")["pid"]
        for line in (run / "gpu_monitor.jsonl").read_text().splitlines():
            g = json.loads(line)
            assert g["row"][:2] == ["3", protocol["gpu_uuid"]]
            assert all(int(a[1]) == pid for a in g["selected_gpu_compute_apps"])
    summary = load(R5 / "summary.json")
    for group_name in ["valid_pairs", "reference_gs_pass_subset"]:
        stat = summary[group_name]
        assert stat["n"] == 8
        for metric in ["gcos_reference", "gcos_forged", "gcos_gap"]:
            values = [r[metric] for r in rows]
            expected = dict(mean=statistics.mean(values), median=statistics.median(values), min=min(values), max=max(values), sample_std=statistics.stdev(values))
            assert expected == stat[metric]
    _, _, _, err = check_recorded_run(U4, U4 / "config.json")
    numerical_errors.append(err)
    mr = csv_metrics(U2 / "target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv")
    assert float(mr[-1]["bit_accuracy"]) == 1.0 and float(mr[1]["bit_accuracy"]) == 0.953125
    for step in [-1, 1]:
        leaf = f"target_prompt_index=custom/attacker_prompt_index=custom/attack_instance_step={step}.png"
        assert sha(U2 / leaf) == sha(U4 / "evaluator_only/official_output" / leaf)
    return dict(status="passed", published_files_checked=len(published["files"]), remote_source_files_checked=len(sources), prompt_sources_checked=len(prompts), recorded_real_runs_checked=9, real_target_tensors_checked=27, stage05_runs_checked=8, max_abs_cosine_readback_error=max(numerical_errors), gpu_used=False, models_loaded=False, new_model_experiments_run=0, method="Read-only standard-library hashes, NPY parsing, stored-result arithmetic and configuration/CSV checks; no model imports or inference")

if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
