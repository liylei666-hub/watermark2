"""Post-run bookkeeping only. No model or upstream module imports."""
import os
assert os.environ.get("CUDA_VISIBLE_DEVICES")==""
import csv,datetime,hashlib,json,shutil,subprocess,sys
from pathlib import Path
import numpy as np
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p,v):
    with Path(p).open("x",encoding="utf-8") as f: json.dump(v,f,ensure_ascii=False,indent=2)
def git(p,*args): return subprocess.check_output(["git","-C",str(p),*args],text=True).strip()
run=Path(sys.argv[1]); root=run.parent.parent; d=run/"evaluator_only"
cfg=read(run/"config.json"); report=Path(cfg["report_dir"]); execution=read(run/"execution.json")
manifest=read(d/"tensor_manifest.json"); diag=read(d/"diagnostic.json"); tests=read(d/"cpu_tests.json")
assert execution["exit_code"]==0 and read(d/"diagnostic_exit.json")["exit_code"]==0
assert all(sha(p)==h for p,h in cfg["code_files"].items())
assert read(run/"formal_launch.json")["config_sha256"]==sha(run/"config.json")
previous=read(run/"prior_files_hashes.json")
changed=[p for p,h in previous.items() if not Path(p).is_file() or sha(p)!=h]
assert not changed,changed
repos={}
for name in ["semantic-forgery","geodistort-wm"]:
    p=root/"third_party"/name
    repos[name]=dict(commit=git(p,"rev-parse","HEAD"),status=git(p,"status","--porcelain"))
    assert repos[name]["status"]==""
assert repos["semantic-forgery"]["commit"]==cfg["upstream_commit"]
for v in manifest["tensors"].values():
    assert sha(v["path"])==v["sha256"]
    a=np.load(v["path"],allow_pickle=False)
    assert list(a.shape)==v["shape"]==[1,4,64,64] and str(a.dtype)==v["dtype"]=="float32"
    assert np.isfinite(a).all() and v["cpu_roundtrip_equal"]
    assert sha(v["image_path"])==v["image_sha256"]
official=d/"official_output/target_prompt_index=custom/attacker_prompt_index=custom"
with (official/"metrics.csv").open() as f: rows=list(csv.DictReader(f))
by={int(r["step"]):r for r in rows}
assert set(by)=={-1,1}
for r in rows:
    assert (float(r["bit_accuracy"])>cfg["threshold"])==(r["detection_successful"]=="True")
    assert all(float(r[k])==-1 for k in ["psnr","ssim","msssim","lpips"])
loads=read(d/"actual_model_loads.json")
assert {r["model_id"]:r["actual_snapshot"] for r in loads}==cfg["model_snapshots"]
old=read(root/"reports/02_status.json")
same={role:sha(manifest["images"][step]["path"])==sha(old[key])
    for role,step,key in [("reference","-1","reference_image_path"),("forged","1","forged_image_path")]}
code=Path(next(p for p in cfg["code_files"] if p.endswith("/run_recorded.py")))
byte_count=sum(p.stat().st_size for folder in [run,report,code.parent] for p in folder.rglob("*") if p.is_file())
assert byte_count<1024**3
post=read(run/"post_run_gpu.json")
proc=read(run/"process.json")
# Do not signal any process; the parent waited for this exact child.
write(run/"integrity_check.json",dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    protected_prior_file_count=len(previous),changed_prior_files=changed,repos=repos,
    frozen_code_hashes_match=True,config_hash_matches=True,stage02_image_hashes_equal=same,
    formal_child_pid=proc["pid"],formal_child_exited=execution["process_exited"],
    added_bytes_before_reports=byte_count,disk_free_bytes=shutil.disk_usage(root).free))
status=dict(stage="04",status="completed",run_dir=str(run),upstream_commit=cfg["upstream_commit"],
    recording_code_path=str(code),recording_code_sha256=sha(code),
    recording_changes=[
        "原官方入口通过 runpy 原样执行；项目自有包装记录真实采样对象与目标生成输入的同一性",
        "在既有两次 validate 的目标反演返回处保存独立 CPU float32 NPY 副本",
        "核对被验证 PIL 与原流程保存 PNG 的像素及哈希；旁路记录实际模型缓存路径",
        "候选哈希冻结后由独立 CPU 进程计算 float64 全局余弦"
    ],
    gpu_uuid=cfg["gpu_uuid"],gpu_physical_index=3,model_snapshots=cfg["model_snapshots"],
    execution_ok=True,reference_detected=by[-1]["detection_successful"]=="True",
    forged_detected=by[1]["detection_successful"]=="True",
    reference_bit_accuracy=float(by[-1]["bit_accuracy"]),forged_bit_accuracy=float(by[1]["bit_accuracy"]),
    tensor_capture_complete=True,tensor_manifest_path=str(d/"tensor_manifest.json"),
    image_tensor_binding_verified=all(v["validated_pixels_equal_saved_png"] for v in manifest["images"].values()),
    cpu_metric_tests_passed=tests["passed"],gcos_reference=diag["gcos_reference"],
    gcos_forged=diag["gcos_forged"],gcos_gap_reference_minus_forged=diag["gcos_gap_reference_minus_forged"],
    geometry_threshold=None,geometry_accepted=None,full_official_geometry_evaluation_completed=False,
    instrumentation_equivalence_status="源码检查与 mock/CPU 测试通过；未完成有记录/无记录的完整数值等价实验",
    wall_time_seconds=execution["wall_time_seconds"],sampled_peak_gpu_memory_mib=execution["sampled_peak_gpu_memory_mib"],
    blockers=[],formal_model_runs_started=1,model_exit_code=execution["exit_code"],
    diagnostic_name="independent_global_cosine_diagnostic",stage02_image_hashes_equal=same)
write(report/"04_status.json",status)
tensor_lines="\n".join("| "+name+" | "+v["sha256"]+" | "+str(v["step"])+" |" for name,v in manifest["tensors"].items())
model_lines="\n".join("- "+r["model_id"]+"：\n  "+r["actual_snapshot"] for r in loads)
text=f"""# 阶段 04：单样本潜变量留存与全局余弦诊断

本次新的独立单样本运行已完成。RUN_DIR：`{run}`。
记录代码：`{code}`，SHA256 `{sha(code)}`。
上游 commit：`{cfg['upstream_commit']}`，两个上游工作区保持干净。

## 运行与原水印检测

用户本轮授权物理 GPU 3；UUID `{cfg['gpu_uuid']}`。启动前身份/占用复核通过，单卡可见，程序内 cuda:0。
正式模型进程仅启动一次，PID {proc['pid']}，退出码 0，耗时 {execution['wall_time_seconds']:.6f} 秒。
每 2 秒采样 GPU 总显存占用，采样峰值 {execution['sampled_peak_gpu_memory_mib']} MiB；不是连续监测的精确峰值。结束后该子进程已退出，GPU 3 回到 1 MiB、0% 利用率，未操作其他进程。
环境沿用已有 Python 3.10 独立环境；未安装/升级依赖或下载模型。

固定 GS、seed=1、512×512、目标/代理各50步、生成CFG=7.5、DDIM、float32、resample=false。
官方反演仍为空提示词、CFG=1.0；保留原 res_1 images_torch 到代理反演的数据流、VAE、scheduler、stash_pipe 顺序。
GS 参数：l=1、32字节消息、64次重复、offset=0。
参考提示词：A studio photograph of a yellow ceramic teapot on a wooden table.
攻击提示词：A red sailboat on a calm blue lake, watercolor illustration.

| 图像 | bit_accuracy | 原 GS 判定 |
|---|---:|---|
| 参考 | {status['reference_bit_accuracy']} | {status['reference_detected']} |
| 攻击 | {status['forged_bit_accuracy']} | {status['forged_detected']} |

阈值保持 bit_accuracy > 0.70703125。参考水印检测通过；本次观察到一次原 GS 水印转移。
原始 CSV 在 `{official/'metrics.csv'}`，未修改。PSNR/SSIM/MS-SSIM/LPIPS 仍为官方未计算占位 -1，GS p_value=0 是占位。
bit_accuracy 不是总体攻击成功率。

实际加载路径通过旁路记录 Diffusers 0.31.0 的 DiffusionPipeline.download 返回值核对。其 from_pretrained 在 pipeline_utils.py:719–743 把此返回值作为 cached_folder 使用；包装保持参数和返回值原样。两个实际 snapshot 与冻结配置一致：
{model_lines}

stderr 保留官方 safety_checker/scheduler 字段警告和离线 Hub 提示；最终从固定缓存正常加载。完整 stdout/stderr、退出码、commands.json、command.sh 与 config.json 均留存。

## 捕获位置与算法保持

官方来源：[run_reprompting.py:109–117](https://github.com/and-mill/semantic-forgery/blob/{cfg['upstream_commit']}/run_reprompting.py#L109-L117) 从 get_wm_latents 获得 wm_zT 并传入目标生成。包装检查这是同一个对象，再保存 CPU 副本。
参考验证 step=-1 位于 [run_reprompting.py:124–137](https://github.com/and-mill/semantic-forgery/blob/{cfg['upstream_commit']}/run_reprompting.py#L124-L137)，攻击验证 step=1 位于 [179–192](https://github.com/and-mill/semantic-forgery/blob/{cfg['upstream_commit']}/run_reprompting.py#L179-L192)。
两次恢复噪声均截取自 [utils/imprint_utils.py:338–343](https://github.com/and-mill/semantic-forgery/blob/{cfg['upstream_commit']}/utils/imprint_utils.py#L338-L343) 已有目标反演的返回字典。

本次调用计数：{json.dumps(manifest['counts'],ensure_ascii=False)}。
没有增加生成、反演或水印检测调用，也没有分数驱动的候选选择/重试。
捕获使用 detach().to(cpu,copy=True)，不修改、移动或替换原始张量；原 dtype 保持 float32。
source_provenance.json 保存源文件哈希、完整 commit 和空 upstream diff；instrumentation.diff 包含新增包装/运行/测试代码的完整差异。
冻结 config.json 的 SHA256 为 `{sha(run/'config.json')}`，运行前后代码哈希一致。

## 三个实际张量

均为非 pickle NPY、shape=[1,4,64,64]、float32，位于 RUN_DIR/evaluator_only。
保存后 CPU 重读核对 shape/dtype/逐元素数值一致；独立诊断再核对文件哈希与有限性。

| 张量 | SHA256 | 关联 step |
|---|---|---:|
{tensor_lines}

清单 `{d/'tensor_manifest.json'}` 逐张量保存路径、形状、dtype、源码捕获位置、角色、reference_id/candidate_id、配置哈希和图像哈希。
验证前读取 PIL 像素副本，validate 返回后与其原流程保存的 PNG 解码像素逐元素比较，两个 step 均一致。
参考图 SHA256：`{manifest['images']['-1']['sha256']}`。
攻击图 SHA256：`{manifest['images']['1']['sha256']}`。

本次两张图片与阶段 02 的文件哈希均相同：{same}。
这是新运行的输出一致性记录，不表示恢复了阶段 02 历史张量，也不能代替完整记录等价实验。

## 独立 CPU 余弦诊断

实现名：independent_global_cosine_diagnostic。
依据：[arXiv:2606.29807v1 Definition 4.5 与 Remark 4.7](https://arxiv.org/html/2606.29807v1#S4.SS3.SSS2)。
公式 dot(z,zhat)/(norm(z)*norm(zhat))。输入同形状、batch=1；每样本展平全部 C/H/W；
不中心化、不逐通道平均、不重采样，仅在 CPU 计算时转 float64；零范数、非有限、形状错误均报错，不加 epsilon。
候选 PNG 已保存并写入 candidate_frozen.json 后，模型子进程退出，独立 CUDA_VISIBLE_DEVICES="" 进程才读取张量计算：

| 指标 | 实际数值 |
|---|---:|
| gcos_reference | {diag['gcos_reference']:.16f} |
| gcos_forged | {diag['gcos_forged']:.16f} |
| reference − forged | {diag['gcos_gap_reference_minus_forged']:.16f} |

分数未参与攻击计算或选择。没有设置几何阈值，没有几何接受/拒绝结论，也未实现 L-SPD 或融合规则。

## 测试、完整性与限制

CPU mock 测试通过：调用次数保持、原返回对象保持、输入未改变、Python/NumPy/Torch CPU 随机状态未推进，张量往返及 PNG 绑定正确；
余弦测试覆盖同向=1、反向=-1、正交=0、正比例缩放不变以及零范数、NaN、Inf、形状/batch错误拒绝。
构造非有限测试输入时产生一条 NumPy RuntimeWarning，测试按预期拒绝该输入，退出码0；原始日志保留。
这些测试与源码审查不等于有记录/无记录的完整数值等价实验；未做该等价实验。
与作者缺失几何函数的逐项数值等价性尚未验证；本结果不是完整官方几何检测复现，不证明总体可分性、总体攻击成功率或几何防护绕过。

目标张量、原始 CSV、实际模型加载记录和评分均位于 evaluator_only；没有把它们加入攻击输入清单。
运行仍在官方单进程框架内，目录命名、文件哈希不能证明进程/权限隔离。
已有 {len(previous)} 个受保护文件哈希均未改变，两个上游工作区干净。
报告生成前新增文件合计 {byte_count} 字节，报告完成后另作预算终检，要求低于 1 GiB。
当前剩余阻塞：无影响本轮规定诊断完成的阻塞；完整官方几何规则的缺失仍是下一阶段边界。

阶段 04 完成并停止；没有追加样本、优化攻击或外部消息。
"""
with (report/"04_report.md").open("x",encoding="utf-8") as f: f.write(text)
total=sum(p.stat().st_size for folder in [run,report,code.parent] for p in folder.rglob("*") if p.is_file())
assert total<1024**3
write(report/"artifact_checks.json",dict(new_bytes=total,
    report_sha256=sha(report/"04_report.md"),status_sha256=sha(report/"04_status.json"),
    report_writer_sha256=sha(__file__),checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
print(json.dumps(status,ensure_ascii=False,indent=2))

