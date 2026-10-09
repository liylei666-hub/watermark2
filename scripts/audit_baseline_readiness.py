"""Read cached AST, saved run metadata and Git blobs; no models, GPU or network."""
import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "d1e01beccc5a49e3ce29cfe0c80af1dfea427476"
SEAL_COMMIT = "92d31b31b93a6e373fe88a584c640beafb68c6fa"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def git(*args, **kwargs):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], **kwargs)


def function(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return call_name(node.value) + "." + node.attr
    return "<expression>"


def calls(tree):
    return [{"name": call_name(n.func), "line": n.lineno} for n in ast.walk(tree) if isinstance(n, ast.Call)]


def arg_reads(tree, field):
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name) and n.value.id == "args"
            and n.attr == field and isinstance(n.ctx, ast.Load)]


def parser_default(tree, flag):
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "add_argument":
            if n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == flag:
                return ast.literal_eval(next(k.value for k in n.keywords if k.arg == "default"))
    raise AssertionError(flag)


def defaults(func):
    args = func.args.args
    return {a.arg: ast.literal_eval(v) for a, v in zip(args[-len(func.args.defaults):], func.args.defaults)
            if a.arg in {"num_inference_steps", "guidance_scale", "eta"}}


def preserved_blobs():
    directories = ["reports/cpu_pilot", "reports/calibration_engineering",
                   "reports/focused_stability", "reports/limited_codec_bypass"]
    docs = ["research/sd15_clip_smoke.md", "research/mechanical_development.md",
            "research/calibration_engineering.md", "research/focused_stability.md"]
    entries = git("ls-tree", "-r", BASE, "--", *directories, *docs).decode("utf-8").splitlines()
    paths, expected = [], []
    counts = {p: 0 for p in directories + docs}
    for line in entries:
        meta, path = line.split("\t", 1)
        assert (ROOT / path).is_file(), path
        paths.append(path)
        expected.append(meta.split()[2])
        key = next(p for p in counts if path == p or path.startswith(p + "/"))
        counts[key] += 1
    actual = git("hash-object", "--stdin-paths", input=("\n".join(paths) + "\n").encode()).decode().splitlines()
    assert actual == expected, "old evidence bytes changed"
    return {"base_commit": BASE, "identical_blobs": len(paths), "counts": counts}


def timeline():
    folder = ROOT / "reports/limited_codec_bypass"
    specs = [
        ("jpeg", 19283, 19286, "03:54:29", "03:54:40", 2, 0),
        ("replay", 22105, 22108, "04:04:59", "04:05:10", 0, 2),
        ("bypass", 22886, 22889, "04:06:44", "04:06:51", 2, 0),
        ("input_cast", None, 26529, "04:16:20", "04:16:20", 0, 0),
    ]
    stages = []
    for phase, shell_pid, python_pid, start, end, inv, gen in specs:
        p = folder / phase
        frozen, runtime, exit_status = read(p / "frozen.json"), read(p / "runtime.json"), read(p / "exit_status.json")
        assert frozen["pid"] == python_pid
        assert frozen["started_utc"] == "2026-10-09T" + start + "Z"
        assert runtime["finished_utc"] == "2026-10-09T" + end + "Z"
        assert (runtime["inversions"], runtime["generated_images"]) == (inv, gen)
        assert exit_status["exit_code"] == 0
        for name, digest in runtime["file_hashes"].items():
            assert sha(p / name) == digest, (phase, name)
        if shell_pid is not None:
            assert int((p / "runner.pid").read_text()) == shell_pid
            assert "Bounded phase complete" in (p / "execution.log").read_text(encoding="utf-8")
            assert frozen["script_sha256"] == "6c3a3a0ac0f2ad2f70216dba46f3f380db4678ceac97cf36444e56a6fe24f0e0"
        proof_names = ["frozen.json", "runtime.json", "exit_status.json", "execution.log", "results.json"]
        if shell_pid is not None:
            proof_names += ["runner.pid"]
        stages.append({
            "phase": phase, "shell_pid": shell_pid, "python_pid": python_pid,
            "started_utc": frozen["started_utc"], "finished_utc": runtime["finished_utc"],
            "inversions": inv, "generated_images": gen, "wall_seconds": runtime["wall_seconds"],
            "exit_code": 0, "runtime_bound_files_verified": len(runtime["file_hashes"]),
            "runtime_file_hashes": runtime["file_hashes"],
            "additional_proof_hashes": {n: sha(p / n) for n in proof_names},
            "proof_root": p.relative_to(ROOT).as_posix(),
        })
    log = (folder / "jpeg/execution.log").read_text(encoding="utf-8")
    assert '"match_count": 0' in log and '"match_count": 3' in log
    assert sha(folder / "jpeg/results.json") == sha(folder / "jpeg/partial_results.json")
    return {
        "status": "passed_saved_evidence_audit", "scope": "existing recorded batches, not a census of all possible unlogged server jobs",
        "stages": stages, "total_model_inversions": 4, "total_generated_images": 2,
        "model_stage_wall_seconds": sum(s["wall_seconds"] for s in stages[:3]),
        "this_documentation_task": {"model_calls": 0, "generations": 0, "download_bytes": 0},
        "client_incident": {
            "source": "delegated tool session; client failure/message UTC not reliably saved",
            "tool_error": "exec-server transport disconnected",
            "wrong_report": "0 added inversions / 0 generations",
            "error_cause": "mistaken inference that missing execution acknowledgement meant commands did not start",
            "first_recovery_readonly_server_utc": "2026-10-09T04:03:35Z",
            "recovery_action": "read and retrieve existing JPEG folder; no JPEG launch reissued",
            "source_note": "recovery timestamp/action from tool transcript, not encoded in runtime",
        },
        "raw_evidence_preservation": preserved_blobs(),
    }


def source_contract(code):
    inventory = read(ROOT / "reports/reproduction_audit/public_code_inventory.json")
    seal = next(r for r in inventory["repositories"] if r["repo"] == "Kasraarabi/SEAL")
    assert seal["commit"] == SEAL_COMMIT
    expected = {x["path"]: x for x in seal["files"]}
    names = ["SEAL.py", "utils.py", "inverse_stable_diffusion.py", "modified_stable_diffusion.py",
             "image_transformations.py", "image_transformations_exhaustive_tpr.py",
             "image_transformations_exhaustive_roc_auc.py", "requirements.txt", "README.md", "setup.sh"]
    verified, trees = {}, {}
    for name in names:
        p = code / name
        assert sha(p) == expected[name]["sha256"], name
        verified[name] = {"sha256": sha(p), "bytes": p.stat().st_size,
                          "url": "https://github.com/Kasraarabi/SEAL/blob/" + SEAL_COMMIT + "/" + name}
        if name.endswith(".py"):
            trees[name] = ast.parse(p.read_text(encoding="utf-8"))
    main = trees["SEAL.py"]
    primary = function(trees["image_transformations.py"], "compute_l2")
    caption = function(trees["utils.py"], "generate_caption")
    assert not arg_reads(main, "threshold") and parser_default(main, "--threshold") == 50
    primary_calls = calls(primary)
    assert {"generate_caption", "sentence_model.encode", "generate_initial_noise",
            "pipe.forward_diffusion", "calculate_patch_l2"} <= {c["name"] for c in primary_calls}
    assert not any(isinstance(n, ast.Name) and n.id == "do_sample" and isinstance(n.ctx, ast.Load)
                   for n in ast.walk(caption))
    inverse = function(trees["inverse_stable_diffusion.py"], "backward_diffusion")
    guidance_reads = [n.lineno for n in ast.walk(inverse) if isinstance(n, ast.Name)
                      and n.id == "guidance_scale" and isinstance(n.ctx, ast.Load)]
    assert len(guidance_reads) >= 2
    gen_defaults = defaults(function(trees["modified_stable_diffusion.py"], "__call__"))
    assert gen_defaults == {"num_inference_steps": 50, "guidance_scale": 7.5, "eta": 0.0}
    exhaustive = {}
    for name in ["image_transformations_exhaustive_tpr.py", "image_transformations_exhaustive_roc_auc.py"]:
        tree = trees[name]
        compute = function(tree, "compute_l2")
        names_called = {c["name"] for c in calls(compute)}
        assert "calculate_patch_l2_exhaustive" in names_called
        assert not {"generate_caption", "sentence_model.encode", "generate_initial_noise"} & names_called
        assert not arg_reads(tree, "threshold") and not arg_reads(tree, "m_match")
        assert parser_default(tree, "--tau") == 2.3
        comp = function(tree, "compute_match_score")
        assert any(isinstance(n, ast.Compare) and any(isinstance(o, ast.Lt) for o in n.ops)
                   for n in ast.walk(comp))
        exhaustive[name] = {"compute_l2_line": compute.lineno, "calls": calls(compute),
                            "tau": 2.3, "patch_comparator": "strict_lt",
                            "unused_args": ["threshold", "m_match"],
                            "model_id": parser_default(tree, "--model_id")}
    tpr = trees["image_transformations_exhaustive_tpr.py"]
    percentile = [n for n in ast.walk(tpr) if isinstance(n, ast.Call) and call_name(n.func) == "np.percentile"]
    assert len(percentile) == 1 and ast.literal_eval(percentile[0].args[1]) == 99
    requirements = {}
    for line in (code / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            if name in {"diffusers", "transformers", "accelerate", "numpy", "pillow",
                        "sentence-transformers", "wandb", "datasets"}:
                requirements[name] = version
    assert not any(x["path"].upper() in {"LICENSE", "NOTICE", "COPYING"} for x in seal["tree"])
    models = read(ROOT / "reports/reproduction_audit/model_inventory.json")
    wanted = [m for m in models if m["repo"] in {
        "stabilityai/stable-diffusion-2-1-base", "Manojb/stable-diffusion-2-1-base",
        "Salesforce/blip2-flan-t5-xl", "kasraarabi/finetuned-caption-embedding"}]
    return {
        "status": "passed_static_contract_audit", "scope": "cached text AST and pinned prior metadata; no module import, model execution or fresh HTTP check",
        "repo": seal["repo"], "commit": SEAL_COMMIT, "prior_code_metadata_utc": inventory["checked_utc"],
        "code_license_metadata": seal["license"], "root_license_notice_copying_files": [],
        "verified_files": verified, "python_files_parsed": len(trees),
        "semantic": {"main_model_id": parser_default(main, "--model_id"), "main_revision_alias": "fp16",
                     "compute_l2_line": primary.lineno, "calls": primary_calls,
                     "main_threshold_argument": 50, "main_threshold_reads": [],
                     "final_accept_endpoint": "not_implemented_in_main",
                     "generation_defaults_from_custom_call": gen_defaults},
        "caption": {"helper_line": caption.lineno, "do_sample_argument_loads": 0,
                    "generation_configuration": "model.generate defaults must be resolved and pinned"},
        "inverse": {"line": inverse.lineno, "guidance_scale_read_lines": guidance_reads,
                    "scheduler": "supplied snapshot scheduler; actual class/config/timesteps not yet frozen"},
        "exhaustive": exhaustive, "tpr_percentile_line": percentile[0].lineno,
        "tpr_negative_percentile": 99, "tpr_calibration_and_fpr_same_batch": True,
        "requirements_subset": requirements,
        "prior_model_metadata": [{k: v for k, v in m.items() if k != "siblings"} for m in wanted],
        "prior_model_metadata_observation": "2026-10-07 audit; not a live availability/license assertion",
    }


def readiness_gate():
    config = read(ROOT / "configs/official_seal_baseline_gate.json")
    assert config["status"] == "blocked_not_executed"
    assert all(v == 0 for v in config["execution_budget"].values())
    assert config["existing_substitute"]["role"] == "engineering_diagnostic_only"
    assert not config["existing_substitute"]["official_baseline"]
    assert config["baseline_source"]["commit"] == SEAL_COMMIT
    assert config["baseline_source"]["primary_endpoint"] != config["baseline_source"]["separate_control_endpoint"]
    assert config["project_instance_extension_status"] == "not_implemented"
    adapter = ROOT / "scripts/seal_paper_contract_adapter.py"
    fixture = ROOT / "tests/fixtures/seal_paper_contract_v1.json"
    assert adapter.is_file() and fixture.is_file()
    assert config["paper_contract_adapter"]["status"] == "implemented_cpu_unit_tested"
    assert config["threshold_policy"]["semantic_paper_contract"]["adapter_status"].startswith("implemented_cpu_unit_tested")
    cache = read(ROOT / "reports/official_seal_route/cache_readonly.json")
    assert len(cache["roots"]) == 6 and all(r["exists"] and not r["matching_names"] for r in cache["roots"])
    assert not cache["target_snapshots"]
    assert cache["versions_from_package_metadata"]["sentence-transformers"] is None
    return {"status": "passed_gate_consistency", "execution_budget": config["execution_budget"],
            "baseline_execution_state": config["status"], "cache_observed_utc": cache["observed_utc"],
            "paper_contract_adapter": {"status": config["paper_contract_adapter"]["status"],
                                        "path": "scripts/seal_paper_contract_adapter.py",
                                        "fixture_sha256": sha(fixture)}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal-code", type=Path, default=ROOT / "runs/reproduction_audit/SEAL")
    parser.add_argument("--write-reports", action="store_true", help="write derived audit JSON only")
    args = parser.parse_args()
    result = {"timeline": timeline(), "source_contract": source_contract(args.seal_code),
              "gate": readiness_gate()}
    if args.write_reports:
        save(ROOT / "reports/execution_erratum/timeline.json", result["timeline"])
        save(ROOT / "reports/official_seal_route/source_contract.json", result["source_contract"])
        save(ROOT / "reports/official_seal_route/readiness_check.json", result["gate"])
    print(json.dumps({"status": "passed", "runtime_bound_files": sum(s["runtime_bound_files_verified"]
                      for s in result["timeline"]["stages"]), "preserved": result["timeline"]["raw_evidence_preservation"],
                      "cached_source_files": len(result["source_contract"]["verified_files"]),
                      "gate": result["gate"]}, indent=2))
