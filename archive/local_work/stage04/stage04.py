"""Bookkeeping launcher: one exclusive formal launch marker, no retries."""
import os
assert os.environ.get("CUDA_VISIBLE_DEVICES")==""
import csv,datetime,difflib,hashlib,json,shlex,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path("/data0/liyanlei/watermark_research")
UP=ROOT/"third_party/semantic-forgery"
CODE=Path(__file__).resolve().parent
PY=ROOT/"envs/semantic_forgery_py310/bin/python"
UUID="GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da"
SHA="ca68950cd7b53b8438a49580f134b2a0db28d778"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def out(c): return subprocess.check_output(c,text=True).strip()
def write(p,x):
    with Path(p).open("x",encoding="utf-8") as f: json.dump(x,f,ensure_ascii=False,indent=2)
def gpu():
    raw=out(["nvidia-smi","-i","3","--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu","--format=csv,noheader,nounits"])
    row=next(csv.reader([raw],skipinitialspace=True))
    apps=out(["nvidia-smi","--query-compute-apps=gpu_uuid,pid,used_gpu_memory","--format=csv,noheader,nounits"])
    return dict(time=now(),row=row,compute_apps=apps)
def guard():
    state=gpu()
    assert state["row"][0]=="3" and state["row"][1]==UUID
    assert UUID not in state["compute_apps"] and int(state["row"][4])<=50 and int(state["row"][5])==0,"GPU 3 occupied"
    assert shutil.disk_usage(ROOT).free>=200*1024**3
    assert out(["git","-C",str(UP),"rev-parse","HEAD"])==SHA
    assert out(["git","-C",str(UP),"status","--porcelain"])==""
    return state
def env(cpu=False):
    e=os.environ.copy()
    e.update(CUDA_DEVICE_ORDER="PCI_BUS_ID",CUDA_VISIBLE_DEVICES="" if cpu else UUID,
        HF_HOME=str(ROOT/"cache/huggingface"),HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",PYTHONDONTWRITEBYTECODE="1",PYTHONUNBUFFERED="1",
        TMPDIR=str(ROOT/"tmp"),MPLCONFIGDIR=str(ROOT/"cache/matplotlib"))
    return e
def main():
    mode=sys.argv[1]
    if mode=="prepare":
        state=guard()
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run=ROOT/"runs"/("04_reprompt_latent_diag_seed1_"+stamp); run.mkdir()
        d=run/"evaluator_only"; d.mkdir()
        report=ROOT/"reports"/("04_latent_diag_"+stamp); report.mkdir()
        write(run/"preflight.json",dict(gpu=state,disk_free_bytes=shutil.disk_usage(ROOT).free,checked_at=now()))
        prev=ROOT/"runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z"
        baseline=json.loads((prev/"config.json").read_text())
        manifest=json.loads((prev/"model_manifest_verified.json").read_text())
        snapshots={}
        for model in manifest:
            base=ROOT/"cache/huggingface/hub"/("models--"+model["repo"].replace("/","--"))
            assert (base/"refs/main").read_text().strip()==model["revision"]
            snap=base/"snapshots"/model["revision"]
            for file in model["files"]:
                p=snap/file["rfilename"]
                assert p.is_file() and p.stat().st_size==file["size"],str(p)
                if p.stat().st_size<1024**2: assert sha(p)==file["sha256"]
            snapshots[model["repo"]]=str(snap.resolve())
        args=baseline["arguments"]
        cfg=dict(stage="04",created_at=now(),upstream_commit=SHA,upstream_path=str(UP),
            arguments=args,resample=False,dtype="float32",inversion_guidance=1.0,inversion_prompt="",
            gs_parameters=dict(l=1,message_width_in_bytes=32,num_replications=64,offset=0),
            threshold=0.70703125,threshold_comparator=">",gpu_uuid=UUID,physical_gpu=3,
            model_snapshots=snapshots,model_revisions={m["repo"]:m["revision"] for m in manifest},
            code_files={str(p):sha(p) for p in sorted(CODE.glob("*.py"))},report_dir=str(report),
            implementation="independent_global_cosine_diagnostic",geometry_threshold=None,
            geometry_accepted=None,maximum_new_bytes=1024**3)
        write(run/"config.json",cfg)
        source_files=["run_reprompting.py","utils/imprint_utils.py","utils/pipe/pipe_provider.py","utils/wm/gs_provider.py"]
        write(run/"source_provenance.json",dict(commit=SHA,files={f:sha(UP/f) for f in source_files},
            original_entry_executed_verbatim=True,upstream_diff=out(["git","-C",str(UP),"diff"])))
        with (run/"instrumentation.diff").open("x") as f:
            for p in sorted(CODE.glob("*.py")):
                f.writelines(difflib.unified_diff([],p.read_text().splitlines(True),fromfile="/dev/null",tofile=str(p)))
        protected=[]
        for folder in [prev,ROOT/"reports/03_geometry_audit_20261013T020025Z"]:
            protected.extend(p for p in folder.rglob("*") if p.is_file() and p.suffix not in [".bundle"])
        protected.extend([ROOT/"AGENTS.md",ROOT/"reports/02_status.json",ROOT/"reports/02_smoke_report.md"])
        write(run/"prior_files_hashes.json",{str(p):sha(p) for p in protected})
        cmd=[str(PY),str(CODE/"run_recorded.py"),str(run)]
        with (run/"command.sh").open("x") as f:
            f.write("cd "+shlex.quote(str(UP))+"\n")
            f.write("CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES="+UUID+" HF_HOME="+str(ROOT/"cache/huggingface")+" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 PYTHONDONTWRITEBYTECODE=1 "+shlex.join(cmd)+"\n")
        write(run/"commands.json",dict(model=cmd,cpu_tests=[str(PY),str(CODE/"test_cpu.py"),str(d/"mock_tests")],
            diagnostic=[str(PY),str(CODE/"diagnostic.py"),str(run)]))
        print(run); return
    run=Path(sys.argv[2]); cfg=json.loads((run/"config.json").read_text()); d=run/"evaluator_only"
    commands=json.loads((run/"commands.json").read_text())
    if mode=="test":
        with (d/"cpu_tests.stdout").open("x") as so,(d/"cpu_tests.stderr").open("x") as se:
            p=subprocess.run(commands["cpu_tests"],env=env(True),stdout=so,stderr=se)
        write(d/"cpu_tests_exit.json",dict(exit_code=p.returncode)); print(p.returncode); return
    assert mode=="run"
    assert json.loads((d/"cpu_tests.json").read_text())["passed"]
    assert all(sha(p)==h for p,h in cfg["code_files"].items())
    write(run/"pre_run_check.json",guard())
    # Exclusive creation prevents even a failed formal execution being relaunched.
    write(run/"formal_launch.json",dict(started_at=now(),config_sha256=sha(run/"config.json")))
    start=time.monotonic()
    with (d/"stdout.log").open("x") as so,(d/"stderr.log").open("x") as se,(run/"gpu_monitor.jsonl").open("x") as mon:
        p=subprocess.Popen(commands["model"],cwd=UP,env=env(),stdout=so,stderr=se)
        write(run/"process.json",dict(pid=p.pid,started_at=now()))
        peak=0
        while True:
            g=gpu(); peak=max(peak,int(g["row"][4])); mon.write(json.dumps(g)+"\n"); mon.flush()
            if p.poll() is not None: break
            time.sleep(2)
        rc=p.wait()
    write(run/"execution.json",dict(exit_code=rc,wall_time_seconds=time.monotonic()-start,
        sampled_peak_gpu_memory_mib=peak,finished_at=now(),process_exited=True))
    with (run/"exit_code.txt").open("x") as f: f.write(str(rc)+"\n")
    write(run/"post_run_gpu.json",gpu())
    if rc==0:
        with (d/"diagnostic.stdout").open("x") as so,(d/"diagnostic.stderr").open("x") as se:
            q=subprocess.run(commands["diagnostic"],env=env(True),stdout=so,stderr=se)
        write(d/"diagnostic_exit.json",dict(exit_code=q.returncode))
    print("MODEL_EXIT_CODE",rc)
if __name__=="__main__": main()

