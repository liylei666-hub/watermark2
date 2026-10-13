#!/usr/bin/env python3
"""Lightweight, non-downloading preflight for watermark_research.

GPU testing is opt-in: pass --gpu-test and an allowed GPU UUID. The test checks
nvidia-smi occupancy first, then exposes only that UUID to a child Python process.
"""
from __future__ import print_function
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys

ALLOWED_INDICES = {3, 5, 7}
KNOWN_CACHE_DIRS = [
    os.path.expanduser("~/.cache/huggingface/hub"),
    os.path.expanduser("~/.cache/torch"),
]
PACKAGES = ["torch", "diffusers", "transformers", "accelerate", "xformers"]


def run(cmd, env=None):
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True, env=env)
        out, _ = p.communicate()
        return p.returncode, out.strip()
    except Exception as exc:
        return 127, "{}: {}".format(type(exc).__name__, exc)


def package_versions():
    result = {}
    try:
        import importlib.metadata as metadata
        version = metadata.version
    except Exception:
        try:
            import pkg_resources
            version = lambda name: pkg_resources.get_distribution(name).version
        except Exception:
            version = None
    for name in PACKAGES:
        if version is None:
            result[name] = "UNKNOWN"
        else:
            try:
                result[name] = version(name)
            except Exception:
                result[name] = "NOT_INSTALLED"
    return result


def gpu_rows():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return [], "nvidia-smi not found"
    query = "index,name,uuid,memory.total,memory.used,memory.free,utilization.gpu"
    code, out = run([exe, "--query-gpu=" + query, "--format=csv,noheader,nounits"])
    if code != 0:
        return [], out
    rows = []
    for line in out.splitlines():
        fields = [x.strip() for x in line.split(",")]
        if len(fields) != 7:
            continue
        try:
            rows.append({"index": int(fields[0]), "name": fields[1], "uuid": fields[2],
                         "memory_total_mib": int(fields[3]), "memory_used_mib": int(fields[4]),
                         "memory_free_mib": int(fields[5]), "utilization_gpu_pct": int(fields[6])})
        except ValueError:
            pass
    return rows, None


def compute_apps():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    query = "gpu_uuid,pid,used_memory,process_name"
    code, out = run([exe, "--query-compute-apps=" + query, "--format=csv,noheader,nounits"])
    if code != 0:
        return []
    apps = []
    for line in out.splitlines():
        fields = [x.strip() for x in line.split(",")]
        if len(fields) != 4:
            continue
        try:
            pid = int(fields[1])
        except ValueError:
            continue
        owner = "unavailable"
        cmdline = "unavailable"
        try:
            with open("/proc/{}/status".format(pid)) as fh:
                for row in fh:
                    if row.startswith("Uid:"):
                        uid = row.split()[1]
                        owner = uid
                        try:
                            import pwd
                            owner = pwd.getpwuid(int(uid)).pw_name
                        except Exception:
                            pass
                        break
            with open("/proc/{}/cmdline".format(pid), "rb") as fh:
                cmdline = fh.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
        except Exception:
            pass
        apps.append({"gpu_uuid": fields[0], "pid": pid, "used_memory_mib": fields[2],
                     "process_name": fields[3], "owner": owner, "cmdline": cmdline})
    return apps


def cache_inventory():
    result = {}
    for path in KNOWN_CACHE_DIRS:
        if not os.path.isdir(path):
            result[path] = {"exists": False, "model_like_entries": []}
            continue
        names = []
        try:
            names = sorted(os.listdir(path))
        except OSError:
            pass
        model_like = [n for n in names if any(k in n.lower() for k in
                      ("stable", "sdxl", "sd-2", "diffusion", "pixart", "flux"))]
        result[path] = {"exists": True, "model_like_entries": model_like}
    return result


def optional_gpu_test(uuid, rows, apps):
    matching = [r for r in rows if r["uuid"] == uuid]
    if not matching:
        return {"status": "blocked", "reason": "UUID is not visible from nvidia-smi"}
    row = matching[0]
    if row["index"] not in ALLOWED_INDICES:
        return {"status": "blocked", "reason": "GPU index is outside the project allowlist"}
    if any(a["gpu_uuid"] == uuid for a in apps):
        return {"status": "blocked", "reason": "compute process is present on the requested GPU"}
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = uuid
    code, out = run([sys.executable, "-c",
                     "import torch; assert torch.cuda.is_available(); x=torch.ones(8,device='cuda:0'); print(x.sum().item())"], env)
    return {"status": "passed" if code == 0 else "failed", "returncode": code, "output": out}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu-test", action="store_true")
    parser.add_argument("--gpu-uuid")
    args = parser.parse_args()
    rows, gpu_error = gpu_rows()
    apps = compute_apps()
    report = {
        "host": platform.node(), "user": os.environ.get("USER") or os.environ.get("USERNAME"),
        "cwd": os.getcwd(), "python": sys.version, "platform": platform.platform(),
        "packages": package_versions(), "gpu_error": gpu_error, "gpus": rows,
        "compute_apps": apps, "known_model_caches": cache_inventory(),
        "gpu_test": {"status": "not_requested"},
    }
    if args.gpu_test:
        if not args.gpu_uuid:
            report["gpu_test"] = {"status": "blocked", "reason": "--gpu-uuid is required"}
        else:
            report["gpu_test"] = optional_gpu_test(args.gpu_uuid, rows, apps)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
