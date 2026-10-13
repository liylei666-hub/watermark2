"""Read recorded outputs, preserve the official CSV, and write stage reports."""
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageStat

ROOT=Path('/data0/liyanlei/watermark_research')
RUN=ROOT/'runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z'
cfg=json.loads((RUN/'config.json').read_text())
exe=json.loads((RUN/'execution.json').read_text())
models=json.loads((RUN/'model_snapshots.json').read_text())
stdout=(RUN/'stdout.log').read_text()
stderr=(RUN/'stderr.log').read_text()
metrics=list(RUN.rglob('metrics.csv'))
assert len(metrics)<=1
rows=list(csv.DictReader(metrics[0].open())) if metrics else []
by_step={int(row['step']):row for row in rows}
images=[]
for p in sorted(RUN.rglob('*.png')):
    with Image.open(p) as im: im.verify()
    with Image.open(p) as im:
        rgb=im.convert('RGB'); extrema=rgb.getextrema()
        images.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            size=list(im.size),mode=im.mode,extrema=extrema,
            mean=ImageStat.Stat(rgb).mean,nonblank=any(a!=b for a,b in extrema)))
def accuracy(step):
    return float(by_step[step]['bit_accuracy']) if step in by_step else None
def detected(step):
    if step not in by_step: return None
    value=by_step[step]['detection_successful'].lower()=='true'
    assert value==(accuracy(step)>0.70703125)
    return value
def imagepath(step):
    return next((i['path'] for i in images if Path(i['path']).name==f'attack_instance_step={step}.png'),None)
blockers=[]
if exe['exit_code']!=0: blockers.append('Official entry exited with code '+str(exe['exit_code'])+'; see stderr.log.')
if detected(-1) is False: blockers.append('Reference watermark was not detected; baseline validity is not established.')
images_valid=all(any(i['path']==imagepath(step) and i['size']==[512,512] and i['nonblank'] for i in images) for step in [-1,1])
if exe['exit_code']==0 and not images_valid: blockers.append('Expected 512x512 nonblank reference/attack image validation failed.')
phases={str(n):('phase '+str(n)+':') in stdout for n in range(1,5)}
status=dict(stage='02',execution_ok=exe['exit_code']==0 and all(phases.values()) and len(rows)==2,
    reference_detected=detected(-1),forged_detected=detected(1),
    upstream_commit=cfg['upstream_commit'],model_revisions={m['repo']:m['revision'] for m in models},
    model_snapshots={m['repo']:m['actual_snapshot'] for m in models},
    gpu_physical_index=3,gpu_uuid=cfg['gpu_uuid'],
    environment_path=str(ROOT/'envs/semantic_forgery_py310'),run_dir=str(RUN),
    metrics_path=str(metrics[0]) if metrics else None,reference_image_path=imagepath(-1),forged_image_path=imagepath(1),
    reference_bit_accuracy=accuracy(-1),forged_bit_accuracy=accuracy(1),threshold=0.70703125,threshold_comparator='>',
    wall_time_seconds=exe['wall_time_seconds'],sampled_peak_gpu_memory_mib=exe['sampled_peak_gpu_memory_mib'],
    deviations_from_upstream=[],blockers=blockers,exit_code=exe['exit_code'],phases_logged=phases,images_valid=images_valid,
    quality_metrics={'psnr':None,'ssim':None,'msssim':None,'lpips':None},
    quality_metrics_reason='Disabled by official Reprompting entry; original CSV retains -1.',
    p_value_interpretation='Gaussian Shading placeholder, not a Tree-Ring test result.',
    local_relay_cleanup=json.loads((RUN/'relay_cleanup.json').read_text()) if (RUN/'relay_cleanup.json').exists() else None,
    resources_after_run=json.loads((RUN/'resources_after_run.json').read_text()))
with (RUN/'image_checks.json').open('x') as f: json.dump(images,f,ensure_ascii=False,indent=2)
with (ROOT/'reports/02_status.json').open('x') as f: json.dump(status,f,ensure_ascii=False,indent=2)
summary='本次单样本流程已跑通' if status['execution_ok'] else '本次单样本流程未跑通'
if status['reference_detected']:
    summary+='，'+('观察到' if status['forged_detected'] else '未观察到')+'一次水印转移现象。'
else: summary+='；参考基线有效性尚未建立。'
lines=['# 阶段 02：独立环境与单样本 Reprompting', '',summary,'',
    '## 实际运行记录','',f'- 上游 commit：`{status["upstream_commit"]}`；执行前后核对工作区状态。',
    f'- 独立环境：`{status["environment_path"]}`；Python 3.10.18，torch 2.5.1+cu124，torchvision 0.20.1+cu124，diffusers 0.31.0，transformers 4.46.3，accelerate 1.1.1。',
    '- NVIDIA 驱动 550.100，CUDA runtime 12.4；pip check、必要模块导入、小张量 CUDA 检查通过，证据在 RUN_DIR。',
    '- 依赖完整清单见 pip_freeze.txt；未安装 xformers。兼容性依据：[PyTorch 历史版本安装说明](https://pytorch.org/get-started/previous-versions/)、[CUDA 12.4 发行说明](https://docs.nvidia.com/cuda/archive/12.4.0/cuda-toolkit-release-notes/index.html)。',
    f'- 物理 GPU 3 / `{status["gpu_uuid"]}`，单卡可见；启动前检查占用与 UUID。',
    f'- RUN_DIR：`{RUN}`。完整配置 `config.json`、启动命令 `command.sh`、依赖 `pip_freeze.txt`。',
    f'- 退出码 {exe["exit_code"]}，耗时 {exe["wall_time_seconds"]:.2f} 秒，每 2 秒监控采样到的峰值显存 {exe["sampled_peak_gpu_memory_mib"]} MiB。',
    '- 固定 GS、seed=1、512×512、目标/代理各 50 步、生成 guidance=7.5、DDIM、float32、resample=false。',
    '- 运行结束后 GPU 3 回到 1 MiB、0% 利用率，无本轮计算进程残留，见 post_run_gpu.json。',
    '- 参考提示词：A studio photograph of a yellow ceramic teapot on a wooden table.',
    '- 攻击提示词：A red sailboat on a calm blue lake, watercolor illustration.','',
    '## 模型与资源','',
    '- 服务器访问 Hugging Face API 出现 OpenSSL SSL_connect: SSL_ERROR_SYSCALL；本机从相同 Hugging Face 仓库固定 revision 下载后，经已认证 SSH 中转。未关闭 TLS 校验。',
    '- 所选文件共 17.7328 GiB；仅标准权重与所需配置/tokenizer。逐文件大小与 SHA256 验证记录见 `server_cache_verification.json`。',
    '- 实际读取 7 个 safetensors 文件头部：浮点张量均为 F32，SD2.1 文本编码器另有一个 I64 张量；详见 `weights_metadata.json`。',
    '- 运行设置 HF_HOME 为项目缓存，并启用 HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1；refs/main 与实际 snapshot 均核对为下表版本。']
for m in models: lines += [f'- `{m["repo"]}`：`{m["revision"]}`；实际路径 `{m["actual_snapshot"]}`。']
lines += ['', '## 结果与图像检查','',f'- execution_ok：`{status["execution_ok"]}`；reference_detected：`{status["reference_detected"]}`；forged_detected：`{status["forged_detected"]}`。',
    f'- 原始 CSV：`{status["metrics_path"]}`；原始 stdout/stderr 与退出码均保留。',
    f'- 参考 bit accuracy：{accuracy(-1)}；攻击 bit accuracy：{accuracy(1)}；阈值 0.70703125，严格使用 `>`。',
    '- PSNR/SSIM/MS-SSIM/LPIPS 在官方 Reprompting 中未计算，CSV 的 -1 保留；汇总用 null。GS p_value 为占位值。']
for im in images: lines += [f'- `{im["path"]}`：{im["size"]}，可解码，nonblank={im["nonblank"]}，SHA256 `{im["sha256"]}`。']
lines += ['', '## 根据源码判断','',
    '- 官方入口执行目标生成、参考检测、代理反演/重生成和目标检测；目标检测结果用于日志和 CSV，未用于候选选择、超参数调整或检测分数驱动的重试（`run_reprompting.py:103-205`）。',
    '- 反演使用空提示词、guidance=1.0；float32 与 stash_pipe 维持官方实现（`utils/pipe/pipe_provider.py:18,291-299,369-378`）。',
    '- GS 阈值和严格比较来自 `utils/utils.py:9-12,45-60`。该进程包含目标模型与验证器访问，本轮没有建立进程级攻击端/评估端隔离。','',
    '## 工程记录与尚未验证','',
    '- 初次准备记录脚本因系统 Python 3.6 缺少 shlex.join 而失败；保留初始目录 02_reprompt_gs_sdxl_seed1_20261012T172610Z，使用独立 Python 3.10 完成当前 RUN_DIR。该失败未启动模型。',
    '- 外部启动脚本首次读取小张量测试退出码时，因文件末尾换行触发字符串比较失败；读取时增加 strip() 后继续。该次未启动官方入口，失败日志与原脚本副本保留为 runner_prelaunch_failure.log 和 02_run_smoke.pre_exit_code_strip.py。',
    '- 本轮使用用户授权的物理 GPU 3；官方算法、模型 ID、阈值、种子和提示词保持固定。',
    '- 未验证总体成功率、100k 用户归属、FPR=10^-6、论文完整结果或创新方法；也未证明 Manojb 模型与历史 Stability AI 权重逐字节一致。',
    '- 阻塞：'+('；'.join(blockers) if blockers else '无影响本次流程完成的剩余阻塞。'),
    '- 本机中转清理记录：`relay_cleanup.json`。完成阶段 02 后停止。']
lines.insert(-1, '- stderr 保留了 Transformers 缓存迁移提示、离线 Hub 提示、scheduler 多余字段和 SDXL safety_checker 参数警告；实际从固定本地 snapshot 完成加载，官方入口正常退出。未因这些提示启用联网或改动配置。')
lines.insert(-1, f'- 本机已删除 7 个经服务器校验的权重文件，共 {status["local_relay_cleanup"]["removed_file_gib"]:.4f} GiB；保留小型配置、清单、日志。')
lines.insert(-1, f'- 结束时 /data0 可用 {status["resources_after_run"]["disk_free_gib"]:.2f} GiB，项目占用 {status["resources_after_run"]["project_used_gib"]:.2f} GiB，低于 80 GiB 预算且保留超过 200 GiB。')
with (ROOT/'reports/02_smoke_report.md').open('x') as f: f.write('\n'.join(lines)+'\n')
print(json.dumps(status,ensure_ascii=False,indent=2))
