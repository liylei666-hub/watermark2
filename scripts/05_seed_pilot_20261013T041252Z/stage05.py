"""Stage 05 fixed-seed execution and descriptive bookkeeping; CPU parent only."""
import os
assert os.environ.get("CUDA_VISIBLE_DEVICES")==""
import csv,datetime,difflib,hashlib,json,math,shlex,shutil,signal,statistics,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path("/data0/liyanlei/watermark_research")
CODE=Path(__file__).resolve().parent
OLD=ROOT/"scripts/04_latent_diag_20261013T024856Z"
UP=ROOT/"third_party/semantic-forgery"
PY=ROOT/"envs/semantic_forgery_py310/bin/python"
UUID="GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da"
COMMIT="ca68950cd7b53b8438a49580f134b2a0db28d778"
EXPECTED_ENTRY="143107fa006698a9e0063ca1576764c830a7bc6d22d8d0c76c057b66a9e9f877"
OLD_RUN=ROOT/"runs/04_reprompt_latent_diag_seed1_20261013T025322Z"
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p,x):
    with Path(p).open("x",encoding="utf-8") as f: json.dump(x,f,ensure_ascii=False,indent=2)
def textfile(p,s):
    with Path(p).open("x",encoding="utf-8") as f:f.write(s)
def out(c): return subprocess.check_output(c,text=True,timeout=20).strip()
def env(cpu=False):
    e=os.environ.copy()
    e.update(CUDA_DEVICE_ORDER="PCI_BUS_ID",CUDA_VISIBLE_DEVICES="" if cpu else UUID,
        HF_HOME=str(ROOT/"cache/huggingface"),HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",PYTHONDONTWRITEBYTECODE="1",PYTHONUNBUFFERED="1",
        TMPDIR=str(ROOT/"tmp"),MPLCONFIGDIR=str(ROOT/"cache/matplotlib"))
    return e
def gpu():
    raw=out(["nvidia-smi","-i","3","--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu","--format=csv,noheader,nounits"])
    row=next(csv.reader([raw],skipinitialspace=True))
    raw_apps=out(["nvidia-smi","--query-compute-apps=gpu_uuid,pid,used_gpu_memory","--format=csv,noheader,nounits"])
    apps=[r for r in csv.reader(raw_apps.splitlines(),skipinitialspace=True) if r and r[0]==UUID]
    assert row[:3]==["3",UUID,"NVIDIA GeForce RTX 3090"],"GPU identity mismatch"
    return dict(time=now(),row=row,selected_gpu_compute_apps=apps)
def budget_bytes(experiment,report):
    return sum(p.stat().st_size for folder in [experiment,report,CODE] for p in folder.rglob("*") if p.is_file())
def cache_check():
    manifest=read(ROOT/"runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/model_manifest_verified.json")
    snapshots={}
    for m in manifest:
        base=ROOT/"cache/huggingface/hub"/("models--"+m["repo"].replace("/","--"))
        assert (base/"refs/main").read_text().strip()==m["revision"]
        snap=base/"snapshots"/m["revision"]
        for f in m["files"]:
            p=snap/f["rfilename"]
            assert p.is_file() and p.stat().st_size==f["size"],"Missing/changed cached file: "+str(p)
        snapshots[m["repo"]]=str(snap.resolve())
    assert snapshots==read(OLD_RUN/"config.json")["model_snapshots"]
    return snapshots
def guard(experiment=None,protocol=None):
    g=gpu()
    assert not g["selected_gpu_compute_apps"] and int(g["row"][4])<=50 and int(g["row"][5])==0,"GPU 3 occupied/unclear"
    assert shutil.disk_usage(ROOT).free>=200*1024**3,"Disk reserve below 200 GiB"
    assert out(["git","-C",str(UP),"rev-parse","HEAD"])==COMMIT
    assert out(["git","-C",str(UP),"status","--porcelain"])=="","Upstream changed"
    assert sha(OLD/"run_recorded.py")==EXPECTED_ENTRY,"Stage04 source changed"
    snapshots=cache_check()
    if protocol:
        assert all(sha(p)==h for p,h in protocol["code_hashes"].items()),"Frozen code changed"
        assert sha(experiment/"pilot_protocol.json")== (experiment/"pilot_protocol.sha256").read_text().strip()
        assert budget_bytes(experiment,Path(protocol["report_dir"]))<2*1024**3,"New file budget exceeded"
        assert snapshots==protocol["model_snapshots"]
    return dict(gpu=g,disk_free_bytes=shutil.disk_usage(ROOT).free,model_snapshots=snapshots,checked_at=now())
def prepare():
    assert not list((ROOT/"runs").glob("05_reprompt_seed_pilot_*")),"Existing stage05 record: inspect, do not restart"
    initial=guard()
    timestamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    experiment=ROOT/"runs"/("05_reprompt_seed_pilot_"+timestamp); experiment.mkdir()
    ed=experiment/"evaluator_only"; ed.mkdir()
    report=ROOT/"reports"/("05_reprompt_seed_pilot_"+timestamp); report.mkdir()
    sources={}
    for name in ["run_recorded.py","recording.py","diagnostic.py","test_cpu.py"]:
        sources[name]=sha(OLD/name)
        data=(OLD/name).read_text()
        if name=="run_recorded.py":
            data=data.replace('run/"config.json"','run/"evaluator_only/config.json"')
            old='cfg["arguments"]["modelid_target"])'
            assert data.count(old)==1
            data=data.replace(old,'cfg["arguments"]["modelid_target"], reference_id=cfg["reference_id"], candidate_id=cfg["candidate_id"])')
        elif name=="recording.py":
            data=data.replace('def __init__(self, directory, config_hash, target_id):',
                'def __init__(self, directory, config_hash, target_id, reference_id="reference_0001", candidate_id="candidate_0001"):')
            data=data.replace('self.target_id = target_id','self.target_id = target_id\n        self.reference_id = reference_id\n        self.candidate_id = candidate_id')
            data=data.replace('reference_id="reference_0001", candidate_id="candidate_0001" if step==1 else None',
                'reference_id=self.reference_id, candidate_id=self.candidate_id if step==1 else None')
            data=data.replace('dict(candidate_id="candidate_0001",','dict(candidate_id=self.candidate_id,')
        textfile(CODE/name,data)
        textfile(ed/(name+".diff"),"".join(difflib.unified_diff((OLD/name).read_text().splitlines(True),
            data.splitlines(True),fromfile=str(OLD/name),tofile=str(CODE/name))))
    assert sha(CODE/"diagnostic.py")==sources["diagnostic.py"]
    write(ed/"recording_source.json",dict(source_directory=str(OLD),source_hashes=sources,
        upstream_commit=COMMIT,upstream_entry_sha256=sha(UP/"run_reprompting.py"),
        allowed_changes=["seed and output config delivery","unique reference/candidate IDs","config located in evaluator_only"]))
    # User-authorized additive device note; preserve exact preceding AGENTS bytes.
    agents=ROOT/"AGENTS.md"; before=agents.read_bytes()
    with (ed/"AGENTS.before.md").open("xb") as f:f.write(before)
    note="\n\n## 阶段 05 本轮设备授权\n\n用户本轮明确授权阶段 05 仅使用物理 GPU 3（GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da）。每个 GPU 子进程启动前核对身份和占用；种子 2–9 串行执行。其余约束保持有效。\n"
    with agents.open("a",encoding="utf-8") as f:f.write(note)
    write(ed/"agents_append.json",dict(before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=sha(agents),appended_text=note))
    oldcfg=read(OLD_RUN/"config.json")
    fixed=dict(oldcfg["arguments"]); fixed.pop("seed")
    codehashes={str(p):sha(p) for p in sorted(CODE.glob("*.py"))}
    protocol=dict(stage="05",data_role="development_pilot",created_at=now(),
        planned_seeds=list(range(2,10)),planned_runs=8,samples_per_seed=1,prompt_pairs=1,
        excluded_historical_seed=1,fixed_arguments=fixed,resample=False,dtype="float32",
        inversion_prompt="",inversion_guidance=1.0,gs_parameters=oldcfg["gs_parameters"],
        threshold=0.70703125,threshold_comparator=">",gpu_physical_index=3,gpu_uuid=UUID,
        expected_gpu_model="NVIDIA GeForce RTX 3090",logical_device="cuda:0",
        model_snapshots=initial["model_snapshots"],model_revisions=oldcfg["model_revisions"],
        upstream_commit=COMMIT,code_hashes=codehashes,recording_code_sha256=sha(CODE/"run_recorded.py"),
        source_recording_sha256=EXPECTED_ENTRY,metric_sha256=sha(CODE/"diagnostic.py"),
        report_dir=str(report),maximum_new_bytes=2*1024**3,
        group_wall_timeout_seconds=1800,model_timeout_seconds=300,monitor_interval_seconds=2,
        engineering_failure_policy="Stop whole group; preserve results; no retries",
        scientific_failure_policy="Retain observation and continue next planned seed",
        shared_watermark_message_key_nonce=True,
        geometry_threshold=None,geometry_accepted=None,full_official_geometry_evaluation_completed=False)
    write(experiment/"pilot_protocol.json",protocol)
    ph=sha(experiment/"pilot_protocol.json"); textfile(experiment/"pilot_protocol.sha256",ph+"\n")
    write(experiment/"preflight.json",initial)
    for seed in protocol["planned_seeds"]:
        run=experiment/("seed_"+str(seed)); run.mkdir(); d=run/"evaluator_only"; d.mkdir()
        args=dict(fixed,seed=seed)
        cfg=dict(stage="05",data_role="development_pilot",arguments=args,upstream_path=str(UP),
            upstream_commit=COMMIT,model_snapshots=protocol["model_snapshots"],
            model_revisions=protocol["model_revisions"],resample=False,dtype="float32",
            inversion_guidance=1.0,inversion_prompt="",gs_parameters=protocol["gs_parameters"],
            threshold=0.70703125,threshold_comparator=">",gpu_uuid=UUID,gpu_physical_index=3,
            reference_id="stage05_seed_"+str(seed)+"_reference",
            candidate_id="stage05_seed_"+str(seed)+"_candidate",
            protocol_sha256=ph,recording_code_sha256=protocol["recording_code_sha256"])
        write(d/"config.json",cfg);textfile(d/"config.sha256",sha(d/"config.json")+"\n")
        cmd=[str(PY),str(CODE/"run_recorded.py"),str(run)]
        cpu=[str(PY),str(CODE/"diagnostic.py"),str(run)]
        write(d/"commands.json",dict(model=cmd,diagnostic=cpu))
        textfile(d/"command.sh","cd "+shlex.quote(str(UP))+"\n"+
            "CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES="+UUID+" HF_HOME="+str(ROOT/"cache/huggingface")+
            " HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 PYTHONDONTWRITEBYTECODE=1 "+shlex.join(cmd)+"\n")
    protected={}
    for folder in [OLD,OLD_RUN,ROOT/"reports/04_latent_diag_20261013T025322Z"]:
        for p in folder.rglob("*"):
            if p.is_file(): protected[str(p)]=sha(p)
    write(ed/"protected_hashes.json",protected)
    print(experiment,flush=True)
def tests(experiment):
    ed=experiment/"evaluator_only"
    for name,cmd in [("cpu_mock",[str(PY),str(CODE/"test_cpu.py"),str(ed/"mock_tests")]),
                     ("parameters",[str(PY),str(CODE/"test_parameters.py"),str(experiment)])]:
        with (ed/(name+".stdout")).open("x") as so,(ed/(name+".stderr")).open("x") as se:
            p=subprocess.run(cmd,env=env(True),stdout=so,stderr=se,timeout=60)
        write(ed/(name+"_exit.json"),dict(exit_code=p.returncode))
        assert p.returncode==0,name
    print("PRE_RUN_CPU_TESTS_PASSED",flush=True)
def terminate_own(p):
    if p.poll() is None:
        os.killpg(p.pid,signal.SIGTERM)
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=10)
def validate_artifacts(run,protocol):
    d=run/"evaluator_only"; cfg=read(d/"config.json"); man=read(d/"tensor_manifest.json")
    assert sha(d/"config.json")==(d/"config.sha256").read_text().strip()
    assert man["config_sha256"]==sha(d/"config.json")
    assert man["counts"]==dict(sampling=1,target_generate=1,proxy_generate=1,target_invert=2,proxy_invert=1,validate=2)
    assert set(man["tensors"])=={"target_original_wm_zT","target_inverted_reference_zT","target_inverted_forged_zT"}
    for key,r in man["tensors"].items():
        assert r["reference_id"]==cfg["reference_id"]
        assert r["candidate_id"]==(cfg["candidate_id"] if key=="target_inverted_forged_zT" else None)
        assert r["shape"]==[1,4,64,64] and r["dtype"]=="float32" and r["cpu_roundtrip_equal"]
        assert sha(r["path"])==r["sha256"] and sha(r["image_path"])==r["image_sha256"]
        assert r["config_sha256"]==sha(d/"config.json")
    assert all(v["validated_pixels_equal_saved_png"] for v in man["images"].values())
    frozen=read(d/"candidate_frozen.json")
    assert frozen["candidate_id"]==cfg["candidate_id"] and sha(frozen["path"])==frozen["sha256"]
    loads=read(d/"actual_model_loads.json")
    assert {m["model_id"]:m["actual_snapshot"] for m in loads}==protocol["model_snapshots"]
    return man
def run_group(experiment):
    protocol=read(experiment/"pilot_protocol.json");ed=experiment/"evaluator_only"
    assert read(ed/"cpu_tests.json")["passed"] and read(ed/"parameter_tests.json")["passed"]
    assert not (experiment/"group_started.json").exists(),"Already started; inspect instead of restarting"
    guard(experiment,protocol)
    write(experiment/"group_started.json",dict(time=now(),pid=os.getpid(),protocol_sha256=sha(experiment/"pilot_protocol.json")))
    start=time.monotonic(); started=[];completed=[];blocking=[]
    for seed in protocol["planned_seeds"]:
        run=experiment/("seed_"+str(seed)); d=run/"evaluator_only"; p=None
        try:
            assert time.monotonic()-start<1800,"Group timeout"
            write(run/"pre_run_check.json",guard(experiment,protocol))
            assert sha(d/"config.json")==(d/"config.sha256").read_text().strip()
            commands=read(d/"commands.json")
            assert not (run/"formal_launch.json").exists(),"Existing launch marker"
            write(run/"formal_launch.json",dict(seed=seed,started_at=now(),config_sha256=sha(d/"config.json")))
            t=time.monotonic(); peak=0;reason=None
            with (d/"stdout.log").open("x") as so,(d/"stderr.log").open("x") as se,(run/"gpu_monitor.jsonl").open("x") as mon:
                p=subprocess.Popen(commands["model"],cwd=UP,env=env(),stdout=so,stderr=se,start_new_session=True)
                started.append(seed);write(run/"process.json",dict(pid=p.pid,process_group=p.pid,started_at=now()))
                print("STARTED seed="+str(seed)+" pid="+str(p.pid),flush=True)
                try:
                    while True:
                        g=gpu();peak=max(peak,int(g["row"][4]));mon.write(json.dumps(g)+"\n");mon.flush()
                        if p.poll() is not None:break
                        assert not any(int(a[1])!=p.pid for a in g["selected_gpu_compute_apps"]),"Other GPU compute process appeared"
                        assert time.monotonic()-t<300,"Model timeout"
                        assert time.monotonic()-start<1800,"Group timeout"
                        assert shutil.disk_usage(ROOT).free>=200*1024**3,"Disk reserve anomaly"
                        assert budget_bytes(experiment,Path(protocol["report_dir"]))<2*1024**3,"File budget exceeded"
                        time.sleep(2)
                except Exception as exc:
                    reason=type(exc).__name__+": "+str(exc);terminate_own(p)
                rc=p.wait()
            write(run/"execution.json",dict(seed=seed,exit_code=rc,started_at=read(run/"process.json")["started_at"],
                finished_at=now(),wall_time_seconds=time.monotonic()-t,sampled_peak_gpu_memory_mib=peak,
                process_exited=True,engineering_failure=reason))
            textfile(run/"exit_code.txt",str(rc)+"\n");write(run/"post_run_gpu.json",gpu())
            if reason:raise RuntimeError(reason)
            assert rc==0,"Model exit code "+str(rc)
            completed.append(seed)
            validate_artifacts(run,protocol)
            with (d/"diagnostic.stdout").open("x") as so,(d/"diagnostic.stderr").open("x") as se:
                q=subprocess.run(commands["diagnostic"],env=env(True),stdout=so,stderr=se,timeout=min(60,max(1,1800-(time.monotonic()-start))))
            write(d/"diagnostic_exit.json",dict(exit_code=q.returncode))
            assert q.returncode==0,"CPU diagnostic error"
            validate_artifacts(run,protocol)
            print("COMPLETED seed="+str(seed)+" elapsed="+str(round(time.monotonic()-t,2)),flush=True)
        except Exception as exc:
            if p is not None:terminate_own(p)
            failure=dict(seed=seed,reason=type(exc).__name__+": "+str(exc),at=now(),traceback=traceback.format_exc())
            write(run/"engineering_failure.json",failure);blocking.append(failure["reason"])
            print("STOPPED seed="+str(seed)+" reason="+failure["reason"],flush=True);break
    write(experiment/"group_execution.json",dict(started_seeds=started,completed_model_seeds=completed,
        total_wall_time_seconds=time.monotonic()-start,finished_at=now(),blockers=blocking))
    print("GROUP_FINISHED started="+str(len(started))+" completed="+str(len(completed)),flush=True)
def describe(rows):
    result={"n":len(rows)}
    for key in ["gcos_reference","gcos_forged","gcos_gap"]:
        values=[r[key] for r in rows]
        result[key]=dict(mean=statistics.mean(values) if values else None,median=statistics.median(values) if values else None,
            min=min(values) if values else None,max=max(values) if values else None,
            sample_std=statistics.stdev(values) if len(values)>=2 else None)
    result["gap_direction_counts"]=dict(positive=sum(r["gcos_gap"]>0 for r in rows),
        zero=sum(r["gcos_gap"]==0 for r in rows),negative=sum(r["gcos_gap"]<0 for r in rows),denominator=len(rows))
    return result
def summarize(experiment):
    protocol=read(experiment/"pilot_protocol.json");report=Path(protocol["report_dir"]);group=read(experiment/"group_execution.json")
    rows=[]
    fields=["seed","run_dir","execution_ok","reference_detected","forged_detected","reference_bit_accuracy",
        "forged_bit_accuracy","tensor_capture_complete","image_tensor_binding_verified","gcos_reference","gcos_forged",
        "gcos_gap","reference_sha256","forged_sha256","original_latent_sha256","wall_time_seconds","sampled_peak_gpu_memory_mib","failure_reason"]
    for seed in protocol["planned_seeds"]:
        run=experiment/("seed_"+str(seed)); d=run/"evaluator_only"; row={k:None for k in fields};row.update(seed=seed,run_dir=str(run))
        if (run/"execution.json").exists():
            ex=read(run/"execution.json");row.update(execution_ok=ex["exit_code"]==0,wall_time_seconds=ex["wall_time_seconds"],
                sampled_peak_gpu_memory_mib=ex["sampled_peak_gpu_memory_mib"])
        if (run/"engineering_failure.json").exists():row["failure_reason"]=read(run/"engineering_failure.json")["reason"]
        metrics=d/"official_output/target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv"
        if metrics.exists():
            with metrics.open() as f: mr={int(r["step"]):r for r in csv.DictReader(f)}
            for step,prefix in [(-1,"reference"),(1,"forged")]:
                if step in mr:
                    row[prefix+"_bit_accuracy"]=float(mr[step]["bit_accuracy"])
                    row[prefix+"_detected"]=mr[step]["detection_successful"]=="True"
                    assert row[prefix+"_detected"]==(row[prefix+"_bit_accuracy"]>0.70703125)
        if (d/"tensor_manifest.json").exists():
            try:
                man=validate_artifacts(run,protocol);row["tensor_capture_complete"]=True;row["image_tensor_binding_verified"]=True
                row.update(reference_sha256=man["images"]["-1"]["sha256"],forged_sha256=man["images"]["1"]["sha256"],
                    original_latent_sha256=man["tensors"]["target_original_wm_zT"]["sha256"])
            except Exception as exc:row["failure_reason"]=(row["failure_reason"] or "")+"; artifact validation: "+str(exc)
        if (d/"diagnostic.json").exists():
            diag=read(d/"diagnostic.json")
            for key in ["gcos_reference","gcos_forged"]:
                assert math.isfinite(diag[key]);row[key]=diag[key]
            row["gcos_gap"]=diag["gcos_gap_reference_minus_forged"]
            assert row["gcos_gap"]==row["gcos_reference"]-row["gcos_forged"]
        rows.append(row)
    valid=[r for r in rows if r["execution_ok"] is True and r["tensor_capture_complete"] is True and r["image_tensor_binding_verified"] is True and r["gcos_gap"] is not None]
    refvalid=[r for r in valid if r["reference_detected"] is True]
    joint=[r for r in refvalid if r["forged_detected"] is True]
    completed=[r for r in rows if r["execution_ok"] is True]
    refpass=[r for r in rows if r["reference_detected"] is True]
    refinval=[r for r in rows if r["reference_detected"] is False]
    unstarted=[s for s in protocol["planned_seeds"] if s not in group["started_seeds"]]
    failed=[r for r in rows if r["failure_reason"] is not None and r["seed"] in group["started_seeds"]]
    duplicate={}
    for key in ["reference_sha256","forged_sha256","original_latent_sha256"]:
        groups={}
        for r in rows:
            if r[key] is not None:groups.setdefault(r[key],[]).append(r["seed"])
        duplicate[key]=[dict(sha256=h,seeds=seeds) for h,seeds in groups.items() if len(seeds)>1]
    cross={}
    for r in rows:
        for role in ["reference","forged"]:
            if r[role+"_sha256"] is not None:cross.setdefault(r[role+"_sha256"],[]).append(dict(seed=r["seed"],role=role))
    duplicate["all_images"]=[dict(sha256=h,occurrences=x) for h,x in cross.items() if len(x)>1]
    summary=dict(data_role="development_pilot",counts={
        "planned":8,"started":{"count":len(group["started_seeds"]),"denominator":8},
        "completed":{"count":len(completed),"denominator":len(group["started_seeds"])},
        "valid_tensor_pairs":{"count":len(valid),"denominator":len(completed)},
        "reference_wm_pass":{"count":len(refpass),"denominator":sum(r["reference_detected"] is not None for r in rows)},
        "reference_valid_pairs":{"count":len(refvalid),"denominator":len(valid)},
        "forged_wm_pass_among_reference_valid":{"count":len(joint),"denominator":len(refvalid)},
        "engineering_failed":{"count":len(failed),"denominator":len(group["started_seeds"])},
        "reference_invalid":{"count":len(refinval),"denominator":sum(r["reference_detected"] is not None for r in rows)},
        "unstarted":{"count":len(unstarted),"denominator":8}},
        valid_pairs=describe(valid),reference_gs_pass_subset=describe(refvalid),duplicate_artifacts=duplicate,
        geometry_threshold=None,geometry_accepted=None,full_official_geometry_evaluation_completed=False)
    with (report/"per_seed_metrics.csv").open("x",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in rows:writer.writerow({k:("null" if v is None else v) for k,v in r.items()})
    write(report/"per_seed_metrics.json",rows);write(report/"summary.json",summary)
    status=dict(stage="05",data_role="development_pilot",experiment_root=str(experiment),
        planned_seeds=protocol["planned_seeds"],planned_runs=8,started_runs=len(group["started_seeds"]),
        completed_runs=len(completed),valid_tensor_pairs=len(valid),reference_valid_pairs=len(refvalid),
        joint_reference_and_forged_wm_pass_count=len(joint),failed_runs=len(failed),unstarted_seeds=unstarted,
        gpu_uuid=UUID,gpu_physical_index=3,upstream_commit=COMMIT,
        recording_code_sha256=protocol["recording_code_sha256"],protocol_sha256=sha(experiment/"pilot_protocol.json"),
        per_seed_metrics_path=str(report/"per_seed_metrics.csv"),summary_path=str(report/"summary.json"),
        duplicate_artifacts=duplicate,geometry_threshold=None,geometry_accepted=None,
        full_official_geometry_evaluation_completed=False,total_wall_time_seconds=group["total_wall_time_seconds"],
        blockers=group["blockers"])
    protected=read(experiment/"evaluator_only/protected_hashes.json")
    changes=[p for p,h in protected.items() if sha(p)!=h]
    assert not changes
    assert sha(ROOT/"AGENTS.md")==read(experiment/"evaluator_only/agents_append.json")["after_sha256"]
    repos={name:dict(commit=out(["git","-C",str(ROOT/"third_party"/name),"rev-parse","HEAD"]),
        status=out(["git","-C",str(ROOT/"third_party"/name),"status","--porcelain"])) for name in ["semantic-forgery","geodistort-wm"]}
    assert all(not r["status"] for r in repos.values())
    assert all(sha(p)==h for p,h in protocol["code_hashes"].items())
    write(report/"05_status.json",status)
    lines=["# 阶段 05：固定提示词下的八种子攻击基线诊断","",
        "## 实际完成","",f"实验根：`{experiment}`。数据角色：development_pilot。",
        f"计划8；启动 {len(group['started_seeds'])}/8；模型正常完成 {len(completed)}/{len(group['started_seeds'])}；张量/绑定和分数有效 {len(valid)}/{len(completed)}。",
        f"工程失败 {len(failed)}/{len(group['started_seeds'])}；参考无效 {len(refinval)}/{sum(r['reference_detected'] is not None for r in rows)}；未执行 {len(unstarted)}/8。",
        f"物理 GPU 3，UUID {UUID}；单可见卡 cuda:0；每个进程启动前复查，逐种子串行。",
        f"整组正式执行及逐样本CPU诊断墙钟 {group['total_wall_time_seconds']:.3f} 秒；上限1800秒，每模型进程上限300秒。",
        f"协议 SHA256：`{status['protocol_sha256']}`。入口 SHA256：`{status['recording_code_sha256']}`。",
        f"来源阶段04入口 SHA256：`{EXPECTED_ENTRY}`，原文件未改。原官方 commit：`{COMMIT}`。",
        "记录副本只修改配置位置和样本 ID；seed/输出目录继续用原配置参数。来源哈希及完整逐文件 diff 在 experiment_root/evaluator_only。",
        "diagnostic.py 与阶段04逐字节相同。CPU mock/参数测试检查了种子2–9的参数绑定、16个唯一ID、8个独立输出目录、调用次数与返回对象。",
        "固定提示词：黄色陶瓷茶壶摄影图 → 蓝色湖面红帆船水彩图；完整文字、模型snapshot、GS参数、精度、步数、CFG与调度器在冻结协议中。",
        "GS阈值严格 >0.70703125；图像和原始CSV保留，质量指标 -1 为未计算占位。实际加载路径逐进程记录并核对固定snapshot。",
        "三个 float32 NPY 张量来自真实目标生成输入和既有两次目标validate反演；图像像素、哈希、配置哈希和ID绑定逐样本核对。",
        "配置、张量、CSV及目标记录位于每种子 evaluator_only；该命名不表示已经实现权限隔离。",
        "", "## 观察到的结果","",
        "| seed | 执行 | 参考BA | 攻击BA | 参考GS | 攻击GS | Gcos参考 | Gcos攻击 | gap |",
        "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:lines.append("| "+" | ".join(str(r[k]) for k in ["seed","execution_ok","reference_bit_accuracy","forged_bit_accuracy","reference_detected","forged_detected","gcos_reference","gcos_forged","gcos_gap"])+" |")
    lines.extend(["",f"参考 GS 通过 {len(refpass)}/{sum(r['reference_detected'] is not None for r in rows)}；参考有效成对样本中攻击 GS 通过 {len(joint)}/{len(refvalid)}。",
        "上述比例只描述这批固定提示词开发样本，bit_accuracy 是单图位匹配比例。",
        "", "| 子集 | 指标 | n | 均值 | 中位数 | 最小值 | 最大值 | 样本标准差 |",
        "|---|---|---|---|---|---|---|---|"])
    for label,key in [("全部有效配对","valid_pairs"),("参考GS通过子集","reference_gs_pass_subset")]:
        stats=summary[key]
        for metric in ["gcos_reference","gcos_forged","gcos_gap"]:
            values=stats[metric]
            lines.append("| "+" | ".join([label,metric,str(stats["n"])]+[str(values[k]) for k in ["mean","median","min","max","sample_std"]])+" |")
        lines.extend(["",label+" gap方向数量："+json.dumps(stats["gap_direction_counts"],ensure_ascii=False),""])
    lines.extend(["重复哈希检查："+json.dumps(duplicate,ensure_ascii=False),"",
        "## 本试验不能回答的问题","",
        "这是开发性小规模诊断；种子1的阶段02/04输出未计入统计。种子改变不等于用户、消息或密钥改变，基础WM设置及固定表共用。",
        "不同种子或未见哈希重复不证明统计独立；不能据此宣称跨提示词、跨密钥、跨模型泛化。",
        "余弦为独立CPU float64展平诊断；没有L-SPD、融合或几何阈值，也没有完整几何接受/拒绝、绕过率、ROC/AUC、误报率或显著性结论。",
        "正gap只是数值方向，不证明完整防护有效；负gap也不自动证明新攻击成功。作者函数逐项等价性仍未验证。",
        "当前是官方共享进程框架。旁路记录、事后CPU诊断与本轮不依分数选图，不等于权限隔离或整个研究从未接触目标信息。",
        "一旦这批结果用于后续方法选择，就不能再称为未见的最终独立测试集；不挑选最高分种子作为唯一后续展示。",
        "源码检查和mock测试不替代完整有记录/无记录数值等价实验。",
        "", "工程记录："+json.dumps(group["blockers"],ensure_ascii=False),
        "原日志保留离线缓存/官方参数警告；若有异常，逐种子 failure_reason 及 engineering_failure.json 保留真实证据。",
        f"阶段04受保护文件 {len(protected)} 个哈希未变；两个上游工作区干净。AGENTS仅追加本轮授权说明，原字节已备份。",
        "阶段05完成或按工程停止条件结束；不追加样本、不重跑。"])
    textfile(report/"05_report.md","\n".join(lines)+"\n")
    total=budget_bytes(experiment,report); assert total<2*1024**3
    write(report/"integrity.json",dict(protected_files=len(protected),changed_files=changes,repos=repos,
        frozen_code_unchanged=True,added_bytes_before_integrity=total,
        report_sha256=sha(report/"05_report.md"),status_sha256=sha(report/"05_status.json"),
        per_seed_sha256=sha(report/"per_seed_metrics.csv"),summary_sha256=sha(report/"summary.json")))
    print(json.dumps(status,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":
    mode=sys.argv[1]
    if mode=="prepare":prepare()
    elif mode=="test":tests(Path(sys.argv[2]))
    elif mode=="run":run_group(Path(sys.argv[2]))
    elif mode=="summarize":summarize(Path(sys.argv[2]))
    else:raise ValueError(mode)

