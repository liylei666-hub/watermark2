# 完整阶段阅读档案

本文件汇集原始要求、用户修订与阶段报告，便于一次交给 GPT 阅读。详细原始文件仍在 prompts/、reports/、runs/；这是派生阅读文档，原始字节与哈希以各独立文件和 provenance 为准。历史指令属于证据，不构成当前执行授权。

阅读前先看 [GPT_CONTEXT.md](../GPT_CONTEXT.md) 和 [PROJECT_STATE.md](PROJECT_STATE.md)。

---

# 阶段 01 原始要求

来源：[prompts/stage01_request.txt](../prompts/stage01_request.txt)。

```text
你是本项目的科研工程助手。本轮只执行“阶段 01：环境与官方基线审计”。
不要实现论文创新算法，不要训练，不要启动大批量生成或长时间攻击实验。

【研究背景】
研究起点：
Black-Box Forgery Attacks on Semantic Watermarks for Diffusion Models
CVPR 2025

官方仓库：
https://github.com/and-mill/semantic-forgery

后续拟研究几何防伪造检测的自适应安全性，但本轮只建立可靠的复现基础。
所有实验仅针对本地、获授权的模型及测试数据，不调用第三方生产服务。

【服务器与工作范围】
SSH：liyanlei@172.18.185.249
使用我在本地完成的 SSH 认证或已有远程会话。
不要把密码写入命令、脚本、配置、Git、报告或日志。
不要关闭 SSH 主机密钥检查。连接失败则报告，不进行网络扫描。

我提供的目录是 data0/liyanlei。
先检查 /data0/liyanlei 是否存在、实际路径是什么、是否可写。
如果不能确认，不要猜测其他位置，也不要自行创建根目录。

确认后使用子目录：
/data0/liyanlei/watermark_research

若该目录已存在，先检查已有内容和 Git 状态，不能覆盖、清空或重置。

【GPU 规则】
只允许使用 nvidia-smi 所显示的物理 GPU 5 和 7。
先记录这两张卡的型号、UUID、显存、当前占用和计算进程。
不要终止任何已有进程；占用情况不明确时，不运行 GPU 测试。

GPU 程序启动前必须限制 CUDA_VISIBLE_DEVICES。
优先使用经过核对的 GPU UUID，避免物理编号和 CUDA 逻辑编号错位。
单卡暴露后，程序内使用 cuda:0。
不得让未限制设备的代码默认占用物理 GPU 0。
本阶段不使用 DDP，不进行多卡模型切分。

【任务 1：非破坏性环境检查】
记录：
- 主机名、当前用户、工作目录；
- 操作系统、内存、工作盘剩余空间；
- NVIDIA 驱动、GPU 5/7 的状态；
- Python、Conda 或 venv 的可用情况；
- 当前环境中 torch、diffusers、transformers、accelerate、
  xformers 等包的版本。未安装就明确写未安装；
- 仅在本用户已知的缓存目录中检查 SD2.1、SDXL 等模型是否已有缓存。
  不扫描整个服务器，不读取令牌文件，不输出全部环境变量。

不使用 sudo，不修改系统 CUDA，不升级 base 或其他已有环境。
本轮不安装大型依赖、不下载模型权重或大型数据集。

【任务 2：获取并审计官方代码】
将官方仓库放入项目的 third_party/semantic-forgery。
已有仓库时先检查，不执行 reset --hard。
记录远程地址、当前分支、完整 commit SHA、工作区状态及许可证。
保持上游代码不变；先阅读源码，不直接运行入口脚本或安装脚本。

审计以下事项，每个结论附源码文件路径和行号：
1. Reprompting、Imprint-Forgery 的实际入口和参数。
2. 默认代理模型、目标模型及其准确 model ID。
3. 模型加载顺序、设备放置、精度、梯度检查点设置。
4. Tree-Ring、Gaussian Shading 的密钥/消息生成、检测和阈值计算。
5. 攻击流程是否读取目标检测结果：
   区分日志记录、提前停止、候选选择、超参数调整。
6. 随机种子、数据来源、结果保存方式。
7. 哪些 import 或入口操作可能隐式下载权重、数据或启动 GPU。

特别检查 README 的 PSNR Correction：
作者指出早期 commit 43eec7e 的 PSNR 计算存在问题。
请核查当前代码的 PSNR 实现、像素范围、归一化、参考图选择，
以及指标是在保存前还是重新读取图片后计算。
不要未经核查就把论文或 README 中的质量数值当作已复现结果。

审计时不要运行缺失依赖下的入口脚本来碰运气，
也不要自行替换模型、修改阈值来让实验“看起来成功”。

【任务 3：建立最小项目记录】
在不覆盖已有文件的前提下，建立必要目录，并输出：

AGENTS.md
- 写明仅 GPU 5/7、工作路径、禁止保存凭据；
- 禁止覆盖已有结果和编造实验数据；
- 后续攻击端与目标评估端必须隔离；
- 每次实验记录配置、代码版本、随机种子和运行状态。

scripts/preflight.py
- 可重复运行的轻量环境检查脚本；
- 无 GPU 时也能输出报告；
- 不能隐式下载资源；
- GPU 小张量测试只能显式启用，并先完成设备核对与占用检查。

reports/01_environment.md
reports/01_baseline_audit.md
reports/01_status.json

01_status.json 至少包含：
project_root、upstream_commit、gpu_status、
existing_environments、cached_models、blockers、next_step_proposal。

【完成标准与停止条件】
返回两个 Markdown 报告的主要内容及 JSON。
明确区分“实际检查过”“根据源码判断”“尚未验证”。

最后提出下一阶段运行一个最小 Reprompting 样例所需的环境、
准确模型 ID、预计下载项和潜在阻塞点，但不要执行该样例。
若网络、权限或路径有问题，准确记录；不要用虚构结果补全。

完成阶段 01 后停止，等待我提供下一阶段指令。
```

---

# 阶段 01 环境

来源：[reports/01_environment.md](../reports/01_environment.md)。

# 阶段 01：环境检查报告

检查日期：2026-10-13（Asia/Shanghai）。SSH 使用本机已有身份认证成功，未读取或记录私钥内容。没有运行模型入口、训练、批量生成或攻击实验。

## 已实际检查

- 主机 `server249`，用户 `liyanlei`，初始目录 `/home/liyanlei`。
- `/data0/liyanlei` 的实际路径就是 `/data0/liyanlei`，目录可写；项目根 `/data0/liyanlei/watermark_research` 已建立，原先不存在，因此没有覆盖既有结果。
- Ubuntu 18.04.6 LTS、Linux 5.4.0-146-generic、x86_64；内存 251 GiB，总 available 约 178 GiB；`/data0` 7.3T 总量、约 537G 可用、使用率 93%。
- 官方仓库已置于 `/data0/liyanlei/watermark_research/third_party/semantic-forgery`，分支 `main`，commit `ca68950cd7b53b8438a49580f134b2a0db28d778`，远程地址为官方 GitHub URL，工作区 clean。
- 远程主机直接执行 `git clone` 时出现 `gnutls_handshake() failed`；随后使用本地已核对的官方仓库对象通过已认证 SSH 传输到远程项目目录，并复核了远程 commit、远程地址和 clean 状态。该网络限制仍属于后续下载模型时的潜在阻塞。

## GPU 与进程

项目允许的物理 GPU 为 3、5、7（GPU 3 是本轮新增授权）。三张卡均为 NVIDIA GeForce RTX 3090、24,576 MiB：

| 物理卡 | UUID | 当前状态 |
|---:|---|---|
| 3 | `GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da` | 空闲；1 MiB、0%，约 24,253 MiB 可用 |
| 5 | `GPU-e6f35928-0155-f121-e707-1eaf3c14965c` | 忙；22,942 MiB、约 94%，PID 26242 属于 `[OTHER_SERVER_USER]`，运行 `[OTHER_USER_SCRIPT]` |
| 7 | `GPU-9644fb82-cb6f-7311-8017-eaee41409bb7` | 空闲；1 MiB、0%，约 24,253 MiB 可用 |

其他空闲卡为物理 GPU 0、1、2、6；GPU 4 也由 `[OTHER_SERVER_USER]` 的 `[OTHER_USER_SCRIPT]` 占用。没有终止或干预进程。GPU 程序后续必须先用 UUID 设置 `CUDA_VISIBLE_DEVICES`，单卡程序内使用 `cuda:0`。

## Python、环境与包

- 系统 `python`：2.7.17；系统 `python3`：3.6.9，pip 21.3.1。
- 系统 Python 3.6：`torch 1.10.2+cu113`；`diffusers`、`transformers`、`accelerate`、`xformers` 未安装。
- 已知 Conda：`/data0/liyanlei/ceramic_watermark/envs/miniconda`，仅有 `base`；其 Python 3.10.18、`torch 2.3.1+cu121`；上述四个包均未安装。
- 官方 requirements 固定 `torch 2.5.1`、`diffusers 0.31.0`、`transformers 4.46.3`、`accelerate 1.1.1` 等，现有环境不匹配。本轮没有安装或升级依赖。

## 已知缓存

只检查 `/home/liyanlei/.cache/huggingface/hub`、`/home/liyanlei/.cache/torch` 以及对应 `/data0/liyanlei/.cache` 路径。前两个目录存在但没有发现 SD2.1、SDXL、PixArt 或 FLUX 模型目录；后两个目录不存在。没有扫描服务器其他位置，也没有读取令牌文件或输出环境变量。

## 尚未验证、阻塞与下一步

尚未验证模型权重可用性、依赖导入兼容性、最小 Reprompting 运行、生成质量和论文指标。阻塞项是依赖缺失、模型缓存为空、GPU 5 被占用，以及 `/data0` 剩余空间约 537G。下一阶段应在 GPU 3 或 GPU 7 中确认空闲的一张卡上准备独立环境，使用准确的攻击模型 `Manojb/stable-diffusion-2-1-base` 与默认目标模型 `stabilityai/stable-diffusion-xl-base-1.0`；预计下载权重、tokenizer、scheduler/config，网络和下载量尚未验证。本阶段未执行样例。


---

# 阶段 01 基线审计

来源：[reports/01_baseline_audit.md](../reports/01_baseline_audit.md)。

# 阶段 01：官方基线代码审计

审计对象为 `/data0/liyanlei/watermark_research/third_party/semantic-forgery`，官方远程地址 `https://github.com/and-mill/semantic-forgery.git`，分支 `main`，完整 commit `ca68950cd7b53b8438a49580f134b2a0db28d778`，工作区 clean。许可证文件为 GPL-3.0 摘要（`LICENSE:1-20`）。本轮只读源码和 README，没有运行入口或安装脚本。

## 入口、模型和设备

- Reprompting 入口与参数在 `run_reprompting.py:32-66`；四段流程是目标模型生成 benign 图（`103-118`）、攻击模型反演（`151-152`）、攻击 prompt 重生成（`165-171`）、目标模型重新反演检测（`176-201`）。默认结果写入 `out/reprompt/` 并保存 `metrics.csv`（`68-71,203-205`）。
- Imprint-Forgery 入口为 `run_imprint_forgery.py:36-70`，默认 cover `images/stalin.jpg`，可选 mask；Imprint-Removal 入口为 `run_imprint_removal.py:35-68`。Forgery 的优化循环为固定 `range(args.steps)`，默认 151 步，每 10 步验证并写 CSV（`run_imprint_forgery.py:183-249`）。
- 代理模型准确 ID 是 `Manojb/stable-diffusion-2-1-base`（三脚本的 attacker 参数：`run_reprompting.py:52-56`、`run_imprint_forgery.py:55-59`）；默认目标是 `stabilityai/stable-diffusion-xl-base-1.0`，可选 `PixArt-alpha/PixArt-Sigma-XL-2-512-MS` 或 `black-forest-labs/FLUX.1-dev`（`run_reprompting.py:43-50`、`utils/pipe/pipe_utils.py:15-28`）。
- 入口使用未索引的 `cuda`（`run_reprompting.py:28-30`、`run_imprint_forgery.py:33`），没有设置 `CUDA_VISIBLE_DEVICES`。后续必须外部按 GPU UUID 限制；单卡暴露后代码内才应使用 `cuda:0`。
- provider 先由 model ID 选择，再 `from_pretrained(..., torch_dtype=self.get_dtype())` 和 `.to(self.device)`（`utils/pipe/pipe_utils.py:31-73`、`utils/pipe/pipe_provider.py:18,63-116,352-400`）。通用 dtype 是 `torch.float32`（`pipe_provider.py:18`）。Imprint attacker 的 scheduler、SD pipeline 也明确使用 float32 并 `.to(device)`（`utils/imprint_utils.py:24-51`）。
- Imprint 冻结 attacker UNet 参数并用 `torch.utils.checkpoint.checkpoint` 做梯度检查点（`utils/imprint_utils.py:54-68,70-83,157`）；优化变量 `z0` 用 Adam 更新（`run_imprint_forgery.py:118-121,183-197`）。未发现 DDP 或多卡切分。

## Tree-Ring 与 Gaussian Shading

- GS 默认 `message_width_in_bytes=32`、`num_replications=64`、`l=1`（`utils/wm/gs_provider.py:26-31`）。消息、ChaCha20 key、nonce 从固定列表导入（`gs_provider.py:93-101`）；消息复制、ChaCha20 加密、`np.random.uniform`/`norm.ppf` latent 生成在 `gs_provider.py:135-183`。检测从 latent 恢复 barcode，多数投票并计算 bit accuracy（`gs_provider.py:205-296,325-357`）。固定 GS 阈值为 `0.70703125`，判定为 `bit_accuracy > threshold`（`utils/utils.py:9-12,36-37,45-60`）。
- TR 默认 `w_seed=999999`、channel 3、ring/circle/radius 10、complex injection（`utils/wm/tr_provider.py:25-33`）。由 seed 构造 FFT ring pattern 和 mask（`tr_provider.py:63-80,122-195`），在 FFT mask 区域注入并逆变换取实部（`198-226`）。检测用 mask 区域与目标 patch 的 non-central chi-square p-value（`321-366`），判定为 `p_value < threshold`；SDXL/PixArt/FLUX 阈值为 `0.0261008646426459`、`0.015917123872865434`、`0.02185009852518841`（`utils/utils.py:14-22,45-60`）。源码称这些阈值来自经验 FPR 测量，本阶段未复测。

## 是否读取目标检测结果

`validate()` 先用目标模型反演，再调用 watermark provider 得到 bit accuracy/p-value（`utils/imprint_utils.py:336-350`）。三类入口把检测结果写入 `results`、打印日志并保存 CSV（Reprompting：`run_reprompting.py:138-146,193-205`；Forgery：`run_imprint_forgery.py:228-249`）。Imprint 循环固定步数，没有成功后的 `break`（`run_imprint_forgery.py:183-206`；Removal 对应 `171-203`）。优化 loss 是 inverted latent 与 retrieved latent 的 MSE（`run_imprint_forgery.py:186-197`），没有用 detector 值做候选选择或超参数调整。Reprompting 的 `--resample` 只是 GS latent 重采样（`run_reprompting.py:157-163`）；单次入口没有按检测结果选择多个候选。

## 随机性、数据和隐式资源访问

- `--seed` 默认 1；`set_random_seed()` 设置 PyTorch、CUDA、NumPy、Python random，使用 seed+0/+1/+2/+3/+4/+5（`run_reprompting.py:63-64`、`utils/utils.py:63-72`）。TR 初始化又按 `w_seed` 设置一次（`tr_provider.py:63-66`），GS 采样使用 NumPy 随机数（`gs_provider.py:170-183`）。
- prompt 列表位于 `utils/prompt_utils.py`，README 说明来源为 SD-Prompts/I2P（`README.md:64-68`）；cover 图来自仓库 `images/`，默认 `images/stalin.jpg`（`run_imprint_forgery.py:39-42,89-90`）。
- `from_pretrained` 会读取缓存或访问 Hugging Face Hub（`utils/imprint_utils.py:35-48`、`utils/pipe/pipe_provider.py:63-116,362-400`）。入口在解析参数后就创建 pipeline（Reprompting `run_reprompting.py:79-94`；Forgery `run_imprint_forgery.py:75-116`），直接运行可能下载权重并启动 GPU。Forgery 顶层初始化 LPIPS（`run_imprint_forgery.py:75-76`），其权重也可能需要缓存或下载。仅导入 prompt 列表没有发现自动下载完整数据集。

## README PSNR Correction 核查

README 只指出旧 commit `43eec7e` 的 PSNR 计算有问题（`README.md:72-73`），示例数值不是本地复现结果（示例位置 `README.md:97-105,139-145`）。当前实现的证据如下：

1. `validate()` 先调用 `psnr_PIL(image_to_verify_PIL, original_PIL)`，之后才保存 `original.png`、`generated.png` 和 `attack_instance_step=*.png`（`utils/imprint_utils.py:352-388`），所以指标基于保存前的内存图像，不是重新读取保存文件后的结果。
2. `psnr_PIL()` 把两幅 PIL 图像转为数组、按通道排列、除以 255，再使用 `PeakSignalNoiseRatio(data_range=1.0)`（`utils/image_utils.py:495-518`）。像素范围是 `[0,1]`；参考图是 `original_PIL`，待测图是 `image_to_verify_PIL`（`imprint_utils.py:297-305,352-354`）。
3. Reprompting 显式传 `do_psnr=False`（`run_reprompting.py:124-137,178-192`），所以其 metrics 中 PSNR 为 -1；Imprint 默认计算 PSNR。

## 阶段判断

以上“根据源码判断”支持：目标检测结果会被读取并记录成功状态，但没有作为 Imprint 候选选择或超参数调整信号；当前代码会隐式触发模型加载/下载和 GPU 使用。模型权重、依赖兼容性、最小 Reprompting 输出和论文质量数值均为“尚未验证”。下一阶段需在 GPU 3 或 GPU 7 的 UUID 限制下准备隔离环境，再考虑最小 Reprompting；本阶段停止执行。


---

# 阶段 01 状态

来源：[reports/01_status.json](../reports/01_status.json)。

```json
{
  "project_root": "/data0/liyanlei/watermark_research",
  "upstream_commit": "ca68950cd7b53b8438a49580f134b2a0db28d778",
  "upstream_branch": "main",
  "upstream_remote": "https://github.com/and-mill/semantic-forgery.git",
  "upstream_worktree": "clean",
  "gpu_status": {
    "allowed_physical_indices": [3, 5, 7],
    "gpu_3": {"uuid": "GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da", "name": "NVIDIA GeForce RTX 3090", "memory_total_mib": 24576, "memory_used_mib": 1, "memory_free_mib": 24253, "utilization_gpu_pct": 0, "compute_process": null},
    "gpu_5": {"uuid": "GPU-e6f35928-0155-f121-e707-1eaf3c14965c", "name": "NVIDIA GeForce RTX 3090", "memory_total_mib": 24576, "memory_used_mib": 22942, "memory_free_mib": 1311, "utilization_gpu_pct": 94, "compute_process": {"pid": 26242, "owner": "[OTHER_SERVER_USER]", "command": "/usr/bin/python3.6 [OTHER_USER_PROCESS_PATH]"}},
    "gpu_7": {"uuid": "GPU-9644fb82-cb6f-7311-8017-eaee41409bb7", "name": "NVIDIA GeForce RTX 3090", "memory_total_mib": 24576, "memory_used_mib": 1, "memory_free_mib": 24253, "utilization_gpu_pct": 0, "compute_process": null},
    "gpu_test_run": false
  },
  "existing_environments": [
    {"python": "/usr/bin/python3", "version": "3.6.9", "torch": "1.10.2+cu113", "diffusers": "NOT_INSTALLED", "transformers": "NOT_INSTALLED", "accelerate": "NOT_INSTALLED", "xformers": "NOT_INSTALLED"},
    {"python": "/data0/liyanlei/ceramic_watermark/envs/miniconda/bin/python", "version": "3.10.18", "torch": "2.3.1+cu121", "diffusers": "NOT_INSTALLED", "transformers": "NOT_INSTALLED", "accelerate": "NOT_INSTALLED", "xformers": "NOT_INSTALLED"}
  ],
  "cached_models": {"checked": ["/home/liyanlei/.cache/huggingface/hub", "/home/liyanlei/.cache/torch", "/data0/liyanlei/.cache/huggingface/hub", "/data0/liyanlei/.cache/torch"], "model_entries_observed": [], "scope": "known user cache directories only"},
  "blockers": ["GPU 5 is occupied; GPU 3 and GPU 7 were idle at inspection.", "Official dependency stack is absent or version-mismatched.", "Required model weights were not found in checked caches; download/network availability is unverified.", "Direct remote git clone hit a GnuTLS handshake failure; the verified repository was transferred over the authenticated SSH session.", "/data0 has about 537G available and is 93% used."],
  "next_step_proposal": "After confirming GPU 3 or 7 is still idle, prepare an isolated environment and run one minimal Reprompting sample with CUDA_VISIBLE_DEVICES set to that GPU UUID. Expected IDs: Manojb/stable-diffusion-2-1-base (attacker) and stabilityai/stable-diffusion-xl-base-1.0 (target). Expected downloads: model weights, tokenizer, scheduler/config files.",
  "stage": "01_environment_and_official_baseline_audit",
  "status": "complete_for_requested_audit; execution_not_started"
}
```

---

# 阶段 02 原始要求

来源：[prompts/stage02_request.txt](../prompts/stage02_request.txt)。

```text
执行“阶段 02：独立环境准备 + 单样本官方 Reprompting 复现”。

本轮目标：
在不改变官方攻击算法的前提下，运行一个
Gaussian Shading + SDXL 目标模型 + SD2.1 代理模型
的基础 Reprompting 样例。

本轮不实现新攻击、不实现几何防御、不做训练、
不做参数搜索、不做多样本实验。
环境、下载和运行中出现的问题必须如实记录。

一、读取项目状态

连接：
liyanlei@172.18.185.249

沿用已有 SSH 认证，不保存或输出密码、令牌、私钥；
不要关闭 SSH 主机密钥检查。

项目根：
/data0/liyanlei/watermark_research

先阅读现有 AGENTS.md 和阶段 01 报告，检查是否已有阶段 02
的文件或未结束进程，避免重复执行、覆盖结果。

上游目录：
third_party/semantic-forgery

固定 commit：
ca68950cd7b53b8438a49580f134b2a0db28d778

检查 commit 和 git status。
不要自动更新上游，不要 reset，不修改上游源码。
发现状态不符时先记录原因，不要猜测或强制修复。

二、GPU 和资源限制

本轮只使用物理 GPU 7，其上次记录的 UUID 为：
GPU-9644fb82-cb6f-7311-8017-eaee41409bb7

启动前重新用 nvidia-smi 核对 UUID、物理编号、型号、
显存占用、利用率和计算进程，并补充记录准确驱动版本。

GPU 7 有其他计算任务、占用异常或身份不能确认时，
停止 GPU 阶段并报告，不抢占，不自动换卡。

不使用 GPU 3、5 或其他卡，不终止别人的进程。
本轮不运行 DDP，也不做多卡模型切分。

每个 GPU 子进程启动前设置：
CUDA_DEVICE_ORDER=PCI_BUS_ID
CUDA_VISIBLE_DEVICES=GPU-9644fb82-cb6f-7311-8017-eaee41409bb7

程序内只有一张可见卡，逻辑编号应为 cuda:0。
不要在设置设备限制之前导入会初始化 CUDA 的项目模块。

重新检查磁盘剩余空间。
本轮环境、缓存及下载新增占用的预算上限为 80 GiB，
并至少保留 200 GiB 的工作盘剩余空间。
这是执行预算，不是对下载量的预测。
预计超过预算时先报告，不删除其他项目文件腾空间。

三、建立独立环境

优先使用以下已有 Python 仅作为创建 venv 的解释器：
/data0/liyanlei/ceramic_watermark/envs/miniconda/bin/python

在项目内建立独立环境，例如：
envs/semantic_forgery_py310

不得使用 --system-site-packages。
不修改原 Conda base、不升级系统 Python、不使用 sudo。
不修改系统 CUDA 或 NVIDIA 驱动。

以固定 commit 的 requirements.txt 为准安装依赖。
其中：
torch==2.5.1
torchvision==0.20.1
diffusers==0.31.0
transformers==4.46.3
accelerate==1.1.1

先检查驱动兼容性，再从 PyTorch 官方安装说明中选择
合适的 CUDA wheel；不要因为旧环境安装过 cu121，
就假定新环境一定兼容。

保留 requirements 中的版本要求。
未固定的传递依赖安装后记录实际版本。
不要无条件安装最新版，不自行增加 xformers，
不通过大规模升级依赖来掩盖错误。

若某个依赖冲突，定位具体包和报错。
需要改变官方版本要求时，写出拟议变更并停止，
不要静默降级或升级。

完成后：
1. 运行 pip check。
2. 测试必要模块导入。
3. 在设备核对通过后做一次小张量 CUDA 测试。
4. 保存 pip freeze、Python/PyTorch/CUDA runtime 版本。
5. 不输出完整环境变量或含凭据的配置。

四、准备模型缓存

只准备以下两个模型：

目标：
stabilityai/stable-diffusion-xl-base-1.0

代理：
Manojb/stable-diffusion-2-1-base

先验证模型仓库和所需文件是否可访问。
分别获取并记录准确的模型仓库 commit/revision，
后续下载及加载必须绑定到已记录的版本。

项目缓存可设为：
HF_HOME=/data0/liyanlei/watermark_research/cache/huggingface

使用 Hugging Face 下载接口或经过验证的已有缓存。
读取 model_index.json 和组件配置后，只下载当前 pipeline
实际需要的标准权重、配置、scheduler 和 tokenizer 文件。

不要同时下载多套 fp16/fp32/ONNX/Flax 权重，
不要下载无关根目录整合 checkpoint、SDXL refiner、
PixArt、FLUX 或完整提示词数据集。

本轮保持官方 float32 配置；
不能把仅有的 fp16 权重转成 float32 后，
宣称等价于原始 float32 权重。

固定的代理模型 ID 是上游当前使用的仓库，
报告中不要擅自声称已验证它与历史 Stability AI 权重逐字节一致。

若服务器下载失败：
- 记录具体 URL 所属资源、错误类型和已完成内容；
- 不关闭 TLS 证书验证；
- 不无限重试或轮换不明镜像；
- 若当前执行端具备本地下载能力，可以从相同官方来源下载，
  再通过已有 SSH 传输，核对文件大小及 SHA256；
- 不具备该能力就报告阻塞，不假装已传输。

模型准备好后，使用固定缓存版本运行。
可以使用离线模式避免入口临时下载其他版本，
但必须保证模型 ID 实际解析到刚才记录的 snapshot。
不要只记录 revision 而实际仍加载另一个 main 缓存。

五、运行一个官方样例

运行前再次阅读 run_reprompting.py 及相关 provider。
不要 import 入口脚本来获取 parser，以免触发顶层执行。

优先直接使用原始 run_reprompting.py。
官方实现已包含模型切换时的 stash_pipe()；
先利用原有逻辑，不要为本轮重写整套执行框架。

固定配置：

wm_type = GS
seed = 1
resolution = 512
num_inference_steps_target = 50
num_inference_steps_attacker = 50
guidance_scale_target = 7.5
guidance_scale_attacker = 7.5
scheduler_target = DDIM
scheduler_attacker = DDIM
resample = false

参考图提示词：
A studio photograph of a yellow ceramic teapot on a wooden table.

攻击图提示词：
A red sailboat on a calm blue lake, watercolor illustration.

不要使用默认 I2P 提示词。
两条提示词在首次运行前固定，不根据检测结果更换。

创建唯一 RUN_DIR，例如：
runs/02_reprompt_gs_sdxl_seed1_<timestamp>

记录完整启动命令、工作目录、开始时间和配置。
从官方仓库目录运行，命令参数如下；
先核对参数与固定版本源码一致：

python run_reprompting.py \
  --out_dir "$RUN_DIR" \
  --wm_type GS \
  --modelid_target stabilityai/stable-diffusion-xl-base-1.0 \
  --modelid_attacker Manojb/stable-diffusion-2-1-base \
  --resolution 512 \
  --seed 1 \
  --scheduler_target DDIM \
  --scheduler_attacker DDIM \
  --num_inference_steps_target 50 \
  --num_inference_steps_attacker 50 \
  --guidance_scale_target 7.5 \
  --guidance_scale_attacker 7.5 \
  --target_prompt "A studio photograph of a yellow ceramic teapot on a wooden table." \
  --attacker_prompt "A red sailboat on a calm blue lake, watercolor illustration."

不要添加 --resample。

保持官方自定义 scheduler、反演空提示词、反演 guidance、
VAE 编解码、GS 参数和检测阈值不变。
生成 guidance 和反演 guidance 不是同一个设置，
不要把反演 guidance 也改成 7.5。

保留官方 float32；不启用 autocast、量化或 torch.compile。
不为了跑通而减少步数、缩小分辨率、更换模型或放宽阈值。

若发生 OOM：
保存完整 traceback、出错阶段和显存记录，然后停止。
不要自动改成 fp16 或运行多个替代配置。
退出本轮自身进程并确认其显存已释放，不操作他人进程。

其他工程错误允许做不改变实验含义的定位和修复，
但必须保留失败日志、修改说明和原始结果，
不能通过挑 seed 或挑提示词来“修复”攻击失败。

六、监控和结果检查

使用轻量外部监控记录 GPU 7 的显存和利用率，
例如每 2 秒记录一次。
报告的是“监控采样到的峰值”，不能冒充精确瞬时峰值。

保存 stdout、stderr 和真实退出码。
使用 tee 时注意 pipefail，不能把 tee 的成功当作实验成功。
保留官方生成的原始 metrics.csv，不覆盖其内容。

检查：
1. 是否正常走完参考图生成、代理反演、
   代理重生成、目标反演检测四个阶段。
2. 原始 CSV 中参考图与攻击图对应的记录。
3. 两张图是否存在、能读取、大小为 512×512、
   不是全黑、全白或损坏文件。
4. 参考图是否被目标验证器判为带水印。
5. 攻击图的原始 bit_accuracy 和 detection_successful。

检查当前 GS 阈值应为 0.70703125，
判定使用严格大于 >，不是 >=。
若与固定源码不一致，报告差异，不自行更改。

Reprompting 中 PSNR/SSIM/LPIPS 的 -1 是未计算标记，
保留原始 CSV；另建汇总时可写 null 并注明原因。
不要把它解释为低画质或程序错误。

不能把 GS 的占位 p_value 当作有效 Tree-Ring 检测结果。
不能把一次针对指定水印的检测，
写成已复现 100k 用户归属实验或 FPR=10^-6。

区分以下状态：
- execution_ok：程序是否执行完成；
- reference_detected：参考图水印是否检测通过；
- forged_detected：本次攻击输出是否检测通过。

攻击未通过也是有效观察。
不要更换种子、提示词或重采样直到通过。
如果参考图本身未通过检测，标记基线有效性尚未建立，
不要将攻击图的结果解释为攻击有效性结论。

七、威胁模型记录

本轮直接复现官方入口，而不是重构严格隔离的评估框架。

明确记录：官方入口调用了目标模型和目标验证器，
其中参考图检测与攻击结果检测用于实验记录。
核查检测分数没有被用于攻击候选选择或参数调整。

不要因为攻击公式只使用代理模型，
就把整个复现程序描述为“完全没有访问目标模型”。

本轮不宣称已经实现进程级的攻击端/评估端隔离。
不新建根据目标检测分数自动重试、筛选或提前停止的逻辑。

八、交付和停止

保存：
reports/02_smoke_report.md
reports/02_status.json
本轮 RUN_DIR 下的：
- 完整运行配置和命令；
- 环境版本清单；
- 模型 revision 与实际 snapshot 路径；
- stdout/stderr、退出码、GPU 监控记录；
- 原始 metrics.csv；
- 参考图、攻击图及文件 SHA256。

报告注明真实输出文件名与路径，不根据猜测填图像路径。

02_status.json 至少包含：
stage
execution_ok
reference_detected
forged_detected
upstream_commit
model_revisions
gpu_uuid
environment_path
run_dir
metrics_path
reference_image_path
forged_image_path
reference_bit_accuracy
forged_bit_accuracy
threshold
wall_time_seconds
sampled_peak_gpu_memory_mib
deviations_from_upstream
blockers

未得到的结果写 null，不编造。
即使下载或运行失败，也输出实际完成部分和准确阻塞点。

结论最多说明：
“本次单样本流程已跑通/未跑通，
观察到/未观察到一次水印转移现象。”

不要声称完整复现论文，不报告总体成功率，
不宣称验证了创新点。
完成后停止，等待下一阶段指令。
```

---

# 跨阶段用户修订

来源：[prompts/amendments.json](../prompts/amendments.json)。

```json
[
  {
    "timestamp_utc": "2026-10-12T16:47:48.577Z",
    "role": "user",
    "session_line": 414,
    "text": "你也可以使用3号显卡\n"
  },
  {
    "timestamp_utc": "2026-10-12T17:12:41.870Z",
    "role": "user",
    "session_line": 554,
    "text": "还有gpu3\n"
  },
  {
    "timestamp_utc": "2026-10-12T17:16:18.317Z",
    "role": "user",
    "session_line": 611,
    "text": "明确要求改成本轮可以使用 GPU 3\n"
  },
  {
    "timestamp_utc": "2026-10-12T17:23:56.955Z",
    "role": "user",
    "session_line": 770,
    "text": "服务器如果下载不了就用本机中转\n"
  },
  {
    "timestamp_utc": "2026-10-12T17:35:05.932Z",
    "role": "user",
    "session_line": 1012,
    "text": "中转完了记得删掉本机的避免占空间\n"
  },
  {
    "timestamp_utc": "2026-10-13T02:48:08.473Z",
    "role": "user",
    "session_line": 2531,
    "text": "改为使用gpu3\n"
  }
]
```

---

# 阶段 02 报告

来源：[reports/02_smoke_report.md](../reports/02_smoke_report.md)。

# 阶段 02：独立环境与单样本 Reprompting

本次单样本流程已跑通，观察到一次水印转移现象。

## 实际运行记录

- 上游 commit：`ca68950cd7b53b8438a49580f134b2a0db28d778`；执行前后核对工作区状态。
- 独立环境：`/data0/liyanlei/watermark_research/envs/semantic_forgery_py310`；Python 3.10.18，torch 2.5.1+cu124，torchvision 0.20.1+cu124，diffusers 0.31.0，transformers 4.46.3，accelerate 1.1.1。
- NVIDIA 驱动 550.100，CUDA runtime 12.4；pip check、必要模块导入、小张量 CUDA 检查通过，证据在 RUN_DIR。
- 依赖完整清单见 pip_freeze.txt；未安装 xformers。兼容性依据：[PyTorch 历史版本安装说明](https://pytorch.org/get-started/previous-versions/)、[CUDA 12.4 发行说明](https://docs.nvidia.com/cuda/archive/12.4.0/cuda-toolkit-release-notes/index.html)。
- 物理 GPU 3 / `GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da`，单卡可见；启动前检查占用与 UUID。
- RUN_DIR：`/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z`。完整配置 `config.json`、启动命令 `command.sh`、依赖 `pip_freeze.txt`。
- 退出码 0，耗时 70.83 秒，每 2 秒监控采样到的峰值显存 16584 MiB。
- 固定 GS、seed=1、512×512、目标/代理各 50 步、生成 guidance=7.5、DDIM、float32、resample=false。
- 运行结束后 GPU 3 回到 1 MiB、0% 利用率，无本轮计算进程残留，见 post_run_gpu.json。
- 参考提示词：A studio photograph of a yellow ceramic teapot on a wooden table.
- 攻击提示词：A red sailboat on a calm blue lake, watercolor illustration.

## 模型与资源

- 服务器访问 Hugging Face API 出现 OpenSSL SSL_connect: SSL_ERROR_SYSCALL；本机从相同 Hugging Face 仓库固定 revision 下载后，经已认证 SSH 中转。未关闭 TLS 校验。
- 所选文件共 17.7328 GiB；仅标准权重与所需配置/tokenizer。逐文件大小与 SHA256 验证记录见 `server_cache_verification.json`。
- 实际读取 7 个 safetensors 文件头部：浮点张量均为 F32，SD2.1 文本编码器另有一个 I64 张量；详见 `weights_metadata.json`。
- 运行设置 HF_HOME 为项目缓存，并启用 HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1；refs/main 与实际 snapshot 均核对为下表版本。
- `stabilityai/stable-diffusion-xl-base-1.0`：`462165984030d82259a11f4367a4eed129e94a7b`；实际路径 `/data0/liyanlei/watermark_research/cache/huggingface/hub/models--stabilityai--stable-diffusion-xl-base-1.0/snapshots/462165984030d82259a11f4367a4eed129e94a7b`。
- `Manojb/stable-diffusion-2-1-base`：`0094d483a120f3f33dafbd187ea4aa60d10de75c`；实际路径 `/data0/liyanlei/watermark_research/cache/huggingface/hub/models--Manojb--stable-diffusion-2-1-base/snapshots/0094d483a120f3f33dafbd187ea4aa60d10de75c`。

## 结果与图像检查

- execution_ok：`True`；reference_detected：`True`；forged_detected：`True`。
- 原始 CSV：`/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv`；原始 stdout/stderr 与退出码均保留。
- 参考 bit accuracy：1.0；攻击 bit accuracy：0.953125；阈值 0.70703125，严格使用 `>`。
- PSNR/SSIM/MS-SSIM/LPIPS 在官方 Reprompting 中未计算，CSV 的 -1 保留；汇总用 null。GS p_value 为占位值。
- `/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/target_prompt_index=custom/attacker_prompt_index=custom/attack_instance_step=-1.png`：[512, 512]，可解码，nonblank=True，SHA256 `40fb928b1ca645455711d2ab3b538ea5704b18c4f892ba720610cc54d1ee8ac1`。
- `/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/target_prompt_index=custom/attacker_prompt_index=custom/attack_instance_step=1.png`：[512, 512]，可解码，nonblank=True，SHA256 `3e824454a9c6c89c395e94a45fd727825120a7095f2a77de3ec41f91f29edb7d`。
- `/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/target_prompt_index=custom/attacker_prompt_index=custom/original.png`：[512, 512]，可解码，nonblank=True，SHA256 `40fb928b1ca645455711d2ab3b538ea5704b18c4f892ba720610cc54d1ee8ac1`。

## 根据源码判断

- 官方入口执行目标生成、参考检测、代理反演/重生成和目标检测；目标检测结果用于日志和 CSV，未用于候选选择、超参数调整或检测分数驱动的重试（`run_reprompting.py:103-205`）。
- 反演使用空提示词、guidance=1.0；float32 与 stash_pipe 维持官方实现（`utils/pipe/pipe_provider.py:18,291-299,369-378`）。
- GS 阈值和严格比较来自 `utils/utils.py:9-12,45-60`。该进程包含目标模型与验证器访问，本轮没有建立进程级攻击端/评估端隔离。

## 工程记录与尚未验证

- 初次准备记录脚本因系统 Python 3.6 缺少 shlex.join 而失败；保留初始目录 02_reprompt_gs_sdxl_seed1_20261012T172610Z，使用独立 Python 3.10 完成当前 RUN_DIR。该失败未启动模型。
- 外部启动脚本首次读取小张量测试退出码时，因文件末尾换行触发字符串比较失败；读取时增加 strip() 后继续。该次未启动官方入口，失败日志与原脚本副本保留为 runner_prelaunch_failure.log 和 02_run_smoke.pre_exit_code_strip.py。
- 本轮使用用户授权的物理 GPU 3；官方算法、模型 ID、阈值、种子和提示词保持固定。
- 未验证总体成功率、100k 用户归属、FPR=10^-6、论文完整结果或创新方法；也未证明 Manojb 模型与历史 Stability AI 权重逐字节一致。
- 阻塞：无影响本次流程完成的剩余阻塞。
- stderr 保留了 Transformers 缓存迁移提示、离线 Hub 提示、scheduler 多余字段和 SDXL safety_checker 参数警告；实际从固定本地 snapshot 完成加载，官方入口正常退出。未因这些提示启用联网或改动配置。
- 本机已删除 7 个经服务器校验的权重文件，共 17.7283 GiB；保留小型配置、清单、日志。
- 结束时 /data0 可用 513.49 GiB，项目占用 23.38 GiB，低于 80 GiB 预算且保留超过 200 GiB。
- 本机中转清理记录：`relay_cleanup.json`。完成阶段 02 后停止。


---

# 阶段 02 状态

来源：[reports/02_status.json](../reports/02_status.json)。

```json
{
  "stage": "02",
  "execution_ok": true,
  "reference_detected": true,
  "forged_detected": true,
  "upstream_commit": "ca68950cd7b53b8438a49580f134b2a0db28d778",
  "model_revisions": {
    "stabilityai/stable-diffusion-xl-base-1.0": "462165984030d82259a11f4367a4eed129e94a7b",
    "Manojb/stable-diffusion-2-1-base": "0094d483a120f3f33dafbd187ea4aa60d10de75c"
  },
  "model_snapshots": {
    "stabilityai/stable-diffusion-xl-base-1.0": "/data0/liyanlei/watermark_research/cache/huggingface/hub/models--stabilityai--stable-diffusion-xl-base-1.0/snapshots/462165984030d82259a11f4367a4eed129e94a7b",
    "Manojb/stable-diffusion-2-1-base": "/data0/liyanlei/watermark_research/cache/huggingface/hub/models--Manojb--stable-diffusion-2-1-base/snapshots/0094d483a120f3f33dafbd187ea4aa60d10de75c"
  },
  "gpu_physical_index": 3,
  "gpu_uuid": "GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da",
  "environment_path": "/data0/liyanlei/watermark_research/envs/semantic_forgery_py310",
  "run_dir": "/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z",
  "metrics_path": "/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv",
  "reference_image_path": "/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/target_prompt_index=custom/attacker_prompt_index=custom/attack_instance_step=-1.png",
  "forged_image_path": "/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/target_prompt_index=custom/attacker_prompt_index=custom/attack_instance_step=1.png",
  "reference_bit_accuracy": 1.0,
  "forged_bit_accuracy": 0.953125,
  "threshold": 0.70703125,
  "threshold_comparator": ">",
  "wall_time_seconds": 70.83343678503297,
  "sampled_peak_gpu_memory_mib": 16584,
  "deviations_from_upstream": [],
  "blockers": [],
  "exit_code": 0,
  "phases_logged": {
    "1": true,
    "2": true,
    "3": true,
    "4": true
  },
  "images_valid": true,
  "quality_metrics": {
    "psnr": null,
    "ssim": null,
    "msssim": null,
    "lpips": null
  },
  "quality_metrics_reason": "Disabled by official Reprompting entry; original CSV retains -1.",
  "p_value_interpretation": "Gaussian Shading placeholder, not a Tree-Ring test result.",
  "local_relay_cleanup": {
    "server_all_files_verified": true,
    "local_model_weights_removed": true,
    "removed_file_count": 7,
    "removed_file_bytes": 19035655228.0,
    "removed_file_gib": 17.7283,
    "free_bytes_before": 52212027392,
    "free_bytes_after": 71247704064,
    "completed_at": "2026-10-12T19:06:10.1346793Z",
    "retained": "Small configs, manifests, scripts and logs",
    "cleanup_method": "Delete only the seven exact verified weight files"
  },
  "resources_after_run": {
    "disk_free_gib": 513.4853591918945,
    "project_used_gib": 23.38382339477539,
    "remote_interrupted_transfer_bytes_removed": 453181440,
    "upstream_commit": "ca68950cd7b53b8438a49580f134b2a0db28d778",
    "upstream_clean": true,
    "helper_sha256": {
      "02_run_smoke.py": "1cfc7debfa4aa0eefd7afff4683879d62cd3106709590f589111e49b1deaaeec",
      "summarize_run.py": "c6a40b16975f31c8087696a4d7d3fb2f3b9ed52dc633ac868cd53938ae9b626b",
      "verify_cache.py": "db45a31d2a9e83e404e7167f8ab43adc471b6b85639f41232857a133a2487d69",
      "resolve_cache.py": "58e5e20525fc9846e4b3f9343320be83fe1042b866cb07ae682749f8696e7302"
    }
  }
}
```

---

# 阶段 03 原始要求

来源：[prompts/stage03_request.txt](../prompts/stage03_request.txt)。

```text
你是本项目的科研工程助手。

本轮只执行：
“阶段 03：几何验证官方实现与攻击信息边界核查”。

【研究主线】

本项目研究：
扩散模型语义水印的黑盒伪造攻击与错误来源归属。

起点论文：
Black-Box Forgery Attacks on Semantic Watermarks for Diffusion Models
CVPR 2025

阶段 02 报告记录：
官方 Reprompting 单样本执行完成；
参考图 bit_accuracy=1.0；
攻击图 bit_accuracy=0.953125；
GS 阈值为严格大于 0.70703125。

这些是需要核对的已有记录，不是要求重新执行的任务。

本轮研究几何验证，是为了确定后续攻击方法的评估对象。
不要将项目转为新水印设计、检测器改进或防御端校准。

本轮不实现创新攻击、不训练、不搜索参数，
不运行模型生成或反演，不重新执行阶段 02，
不安装依赖，不下载模型权重或大型数据集。

一、连接与资源范围

通过已有 SSH 认证连接：
liyanlei@172.18.185.249

项目根：
/data0/liyanlei/watermark_research

不保存或输出密码、令牌、私钥。
不关闭 SSH 主机密钥检查。
连接或路径失败时如实报告，不扫描其他主机或目录。

先阅读 AGENTS.md 和阶段 02 报告。
不覆盖、不删除已有文件，不修改现有实验结果。

本轮仅使用 CPU。
自己启动的 Python 检查进程显式设置：
CUDA_VISIBLE_DEVICES=""

使用已有独立环境中的 Python：
/data0/liyanlei/watermark_research/envs/semantic_forgery_py310/bin/python

不要 import 官方运行入口，不加载 pipeline，
不要运行可能隐式下载权重或初始化 CUDA 的模块。

阶段 02 实际使用 GPU 3，按历史事实记录。
本轮不使用任何 GPU，也不修改后续 GPU 授权范围。

二、对阶段 02 做最小证据核对

读取：
reports/02_smoke_report.md
reports/02_status.json

根据其中记录的实际 RUN_DIR，检查：
- command.sh 和 config.json；
- 退出码及日志中的完成记录；
- 原始 metrics.csv；
- 参考图和攻击图的存在性、尺寸与 SHA256。

核对原始 CSV 的表头、行含义、bit_accuracy、
detection_successful，与阶段 02 报告是否一致。

每项只记录：
已核对一致 / 存在差异 / 证据缺失。

不重新运行验证器。
不根据文件存在就推断程序成功。
不把 bit_accuracy 解释为总体攻击成功率。

检查报告中的两张实际输出图片。
有可用视觉检查能力时，分别描述其可见内容，
检查是否大致对应固定提示词，以及是否只是参考图的复制。

没有视觉检查能力时，仅报告文件完整性，
将内容符合程度标记为“待人工检查”。
不得从文件名、提示词或 nonblank=True 推断实际画面。

发现差异时保留原文件，记录差异，
不要自动修改报告、CSV 或重跑样例。

三、获取几何论文与官方代码

论文：
Rethinking Forgery Attacks on Semantic Watermarks
in Black-Box Settings: A Geometric Distortion Perspective

指定阅读版本：
https://arxiv.org/html/2606.29807v1

官方仓库：
https://github.com/chengyi-chris/geodistort-wm

新仓库预定位置：
third_party/geodistort-wm

若目录已存在，先检查远程地址、commit 和工作区状态，
不要 reset、强制 checkout、自动覆盖或更新已有修改。

若目录不存在，可以获取公开代码。
禁止自动拉取 Git LFS 大文件、模型权重或递归子模块。
遇到网络问题可以通过已有认证的本机中转，
但必须核对来源与文件完整性；不关闭 TLS 校验。

记录：
- 获取时间；
- 论文版本；
- 仓库远程地址；
- 分支；
- 完整 commit SHA；
- 工作区状态；
- 许可证；
- 实际可用的文件和缺失部分。

没有找到许可证就写“未发现”，不要猜测许可类型。
README 写“即将发布”不等于没有实现；
看到运行脚本也不等于完整实现已经具备。

保持两个上游仓库不变。
本轮只阅读源码，不执行新仓库入口或安装脚本。

四、只围绕一个目标做源码对应性审计

目标：
判断能否忠实地使用该几何验证机制，
评估我们已经复现的 GS Reprompting 场景。

每个源码结论附：
完整 commit + 文件路径 + 行号。

每个论文结论附：
版本 + 章节或公式编号。

需要查清：

1. 检测入口与数据流
   - 哪个脚本生成正常水印样本？
   - 哪个脚本生成无水印对照？
   - 哪个脚本生成 Reprompting 样本？
   - 哪些函数实际计算几何分数？
   - 几何分数是否真的进入最终接受/拒绝判定，
     还是仅被记录用于离线分析？

2. 几何指标定义
   - G-Cos、L-SPD 或代码中对应指标的确切实现；
   - 输入张量、形状、归一化；
   - 局部划分、协方差计算和数值正则项；
   - 分数方向；
   - 多个分数如何组合。
   不凭指标名称推测实现。

3. 参考潜变量从哪里获得
   - 使用原始生成噪声、重建噪声还是其他参考？
   - 是逐图保存、由密钥和随机状态重建，
     还是通过其他方式获得？
   - 待验证图如何关联到相应参考？
   - 参考图、候选图和参考潜变量是否一一对应？
   - 论文描述与代码实现是否一致？

   无法从公开材料确定时标记 unknown。
   不自行补全缺失机制，不将疑点直接写成漏洞结论。

4. 阈值与评估协议
   - 阈值是固定值、校准结果，还是测试集扫描所得？
   - 校准集与测试集如何划分？
   - 正常样本误拒与伪造样本错误接受如何定义？
   - 原有水印验证与几何验证的判定关系是什么？

   不把 ROC/AUC 或离线扫描结果冒充现成部署阈值。
   不把我们当前 GS 阈值用于替代几何阈值。

5. 与现有基线的兼容性
   对照阶段 02 的真实配置检查：
   - 模型 ID 与 revision；
   - 分辨率；
   - VAE 编解码；
   - scheduler；
   - 生成步数和反演步数；
   - 生成 guidance 与反演 guidance；
   - 精度；
   - GS 参数、密钥/消息使用方式。

   区分：
   可以直接复用；
   需要明确适配；
   会改变实验含义；
   尚无法判断。

   不为凑齐配置而更换模型、精度、阈值或水印参数。

6. 已有自适应评估范围
   阅读论文相关讨论及附录 C.3。
   区分：
   作者讨论过的策略；
   有公开算法或代码的策略；
   真正进入实验比较的策略；
   没有足够证据确认的部分。

   不写“作者完全没考虑自适应攻击”。
   本轮不自动实现或运行这些策略。

五、写清楚后续攻击端和评估端的边界

输出一份 information_boundary.md。

本项目准备优先研究的设置是：
攻击端使用参考图、指定输出提示词和代理模型，
不依赖目标验证分数进行候选筛选或参数调整。

分别列出：
- 攻击端允许获得的输入；
- 评估端独有的数据；
- 本地复现程序为了实验控制而持有、
  但不能传给攻击算法的信息。

重点检查是否可能泄露：
目标水印密钥/消息；
目标原始生成潜变量；
目标生成随机状态；
目标内部反演结果；
目标检测分数；
其他由论文威胁模型限制的信息。

公开模型身份与目标模型内部调用权限要分开描述。

定义后续的候选输出交付方式：
攻击端先固定输出和文件哈希，
评估端再读取候选进行检测。
不将评估结果反馈用于本轮候选选择。

这只是接口与信息流设计，不是已实现安全隔离。
单纯拆成两个 Python 文件，
不等于已经建立权限隔离或证明没有信息泄漏。

六、检查能否复用现有单样本

仅检查阶段 02 RUN_DIR 已保存的真实文件。

明确回答：
- 现有图片是否能作为新验证器的输入？
- 新验证器还需要哪些潜变量、配置或元数据？
- 这些内容是否已经保存？
- 是否可以从已有记录准确恢复？
- 需要哪些新的计算才可以完成评估？

不使用随意生成的噪声代替缺失的参考潜变量。
不把代理端潜变量冒充目标端参考。
不凭相同种子就声称完整生成状态已被恢复。

本轮不做新的生成、反演或检测。
若缺少必要数据，准确列出缺项和获取方式。

七、交付物与停止

在 reports 下创建唯一的新目录，例如：
reports/03_geometry_audit_<UTC时间戳>/

保存：
03_audit.md
03_status.json
information_boundary.md

03_status.json 至少包含：
stage
checked_at_utc
stage02_evidence_consistent
geometry_paper_version
geometry_repo_path
geometry_repo_commit
geometry_repo_license
implementation_completeness
reference_latent_source
decision_rule_status
compatibility_with_stage02
missing_artifacts
gpu_used
models_loaded
new_experiments_run
blockers
next_step_proposal

未知信息写 null 或明确的 unknown，
不要用 false 代替未知。

本轮预期：
gpu_used = false
models_loaded = false
new_experiments_run = 0

最后只提出一个下一步：
“忠实运行一次该评估需要完成的最小动作”。

不要同时提出多条新攻击方向，
不要修改防御方法，不调整阈值，
不要因为代码不完整就自行发明替代验证器。

返回：
1. 阶段 02 原始记录是否一致；
2. 几何实现是否完整；
3. 最关键的信息依赖或缺失；
4. 03_status.json 全文；
5. 唯一的下一步建议。

完成后停止，等待下一阶段指令。
```

---

# 阶段 03 几何审计

来源：[reports/03_geometry_audit_20261013T020025Z/03_audit.md](../reports/03_geometry_audit_20261013T020025Z/03_audit.md)。

# 阶段 03：几何验证官方实现与攻击信息边界核查

核查日期：2026-10-13 UTC。项目：`/data0/liyanlei/watermark_research`。
审计目录：`/data0/liyanlei/watermark_research/reports/03_geometry_audit_20261013T020025Z`。

## 结论与证据等级

**实际检查过：**阶段 02 原始证据与报告一致；两张 PNG 完整且画面不同；两个上游工作区干净。已获取指定论文 v1 和完整 Git 对象，静态枚举公开文件、检查 import、比较源码哈希。
**根据源码判断：**公开几何实现不完整，缺少模型工厂和几何工具模块；现有接受/拒绝分支只使用原水印分数。现有图片可作为目标反演的图像输入，但不足以完成几何评估。
**尚未验证：**几何分数数值、部署阈值、完整参考潜变量恢复、跨模型版本等价性、误拒率/错误接受率及总体攻击成功率。本轮未加载模型、未使用 GPU、未运行生成、反演、检测或新实验。

## 1. 阶段 02 最小证据核对

实际 RUN_DIR：
`/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z`。

| 项目 | 状态 | 实际证据 |
|---|---|---|
| command.sh 与 config.json | 已核对一致 | 解析后的入口命令与 config.command 相同；固定 GS、seed=1、512、50/50 步、CFG 7.5/7.5、DDIM、resample=false |
| 退出记录与完成日志 | 已核对一致 | exit_code.txt=0；execution.json=0；stdout 有 phase 1–4 与最终 Harmful detection_success=True；没有仅凭图片存在判断成功 |
| 原始 CSV 与报告 | 已核对一致 | 两行：step=-1 与 step=1，见下表 |
| GS 阈值 | 已核对一致 | config/status 均记录 0.70703125，比较为严格 > |
| 历史 GPU | 已核对一致 | 阶段 02 使用物理 GPU 3，UUID GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da；本轮不用 GPU |
| PNG 存在、尺寸与 SHA256 | 已核对一致 | 均为可解码 RGB 512×512；哈希与原报告、image_checks.json 一致 |
| 两图可见内容与固定提示词 | 已核对一致 | 本轮实际查看经哈希核对的本地副本，描述如下 |

原始 CSV 路径：RUN_DIR 下 `target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv`。
表头原样为：
`[空列名],step,psnr,ssim,msssim,lpips,message_bits_str_initial,bit_accuracy,p_value,message_bits_str_recovered,detection_successful`。
首列是 pandas 行索引，不是额外实验编号。

| CSV 索引 | step/行含义 | bit_accuracy | detection_successful | 质量指标 | p_value |
|---|---|---:|---|---|---|
| 0 | -1，参考水印图 | 1.0 | True | 四项均 -1 | 0.0 |
| 1 | 1，Reprompting 攻击图 | 0.953125 | True | 四项均 -1 | 0.0 |

行含义由旧官方入口的参考验证 step=-1、攻击验证 step=1 及写 CSV 路径确认：[run_reprompting.py:124–146](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L124-L146)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）；[run_reprompting.py:179–205](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L179-L205)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。质量指标关闭，-1 是占位；GS 的 p_value 不表示几何检测结果。bit_accuracy 是单图消息位匹配比例，不是总体攻击成功率。

参考图 `attack_instance_step=-1.png`：
SHA256 `40fb928b1ca645455711d2ab3b538ea5704b18c4f892ba720610cc54d1ee8ac1`。
可见黄色有光泽的茶壶置于木板桌上，灰色背景，摄影风格；大致对应黄色陶瓷茶壶固定提示词。
攻击图 `attack_instance_step=1.png`：
SHA256 `3e824454a9c6c89c395e94a45fd727825120a7095f2a77de3ec41f91f29edb7d`。
可见蓝色水面上的红色大帆、船体和红白倒影，水彩插画风格；大致对应红帆船提示词。主体、构图和风格均不同，视觉上不是参考图复制。这是定性检查，不是语义一致性量化实验。
`original.png` 与参考图哈希相同。

完整取证清单、命令、配置、日志、图片信息在本目录 `stage02_evidence.json`。已有文件仅被读取；文件哈希终检记录在 `preservation_check.json`。

## 2. 论文与仓库来源

- 指定论文：[arXiv:2606.29807v1](https://arxiv.org/html/2606.29807v1)，2026-06-29 版本；本轮保存 HTML，SHA256 `8ed835b0eebdc1f9c31585de569790ae6663d0e20b395546580c28df3bc6443f`。
- 仓库：`https://github.com/chengyi-chris/geodistort-wm.git`。
- 远程落盘位置：`/data0/liyanlei/watermark_research/third_party/geodistort-wm`。
- 分支 main；完整 commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`；工作区干净；远程获取完成时间 2026-10-13T02:07:57Z，静态证据时间 2026-10-13T02:09:21.968165Z。
- 服务器直接 clone 遇 TLS 握手错误；本机从指定官方 GitHub 获取，补全历史后通过已认证 SSH 中转 Git bundle。两端 bundle SHA256 同为 `409f7537bfdd1993a10a006ae1dac0a5d5cfb54fc0ade47fb26d0d31cab919d2`，服务端 git fsck --full 通过。未关闭 TLS/SSH 主机校验。
- 初次浅历史 bundle 缺父提交导致 clone 失败，失败后目标目录不存在；使用新的完整 bundle 完成获取，保留失败中转证据。服务器 Git 不支持 branch --show-current，改用只读 symbolic-ref --short HEAD，确认 main。
- **许可证：未发现许可证正文文件。** README 第 13 行有 MIT 徽章链接，不能据此将缺失许可正文记为已核实 MIT 授权。README 的“即将发布”仅是状态文字：[Readme.md:11–21](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/Readme.md#L11-L21)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
- 实际有 4 个运行脚本、7 类水印 provider、模型 provider、两个 DDIM scheduler、图像/提示词工具、文本元数据及公开水印 key 文件。完整文件路径、大小和 SHA256 见 `source_evidence.json`。未下载模型权重、图片数据集，未递归取子模块或启动 LFS 下载；未反序列化仓库 pkl 文件。
- **缺失：**`utils/pipe/pipe_utils.py`、`utils/finger_utils.py`、`utils/spd_utils.py`。前两者被活动 import 引用；第三个出现在几何注释代码中。空的 utils/pipe/__init__.py 未提供替代工厂。静态 AST 与 tracked 文件清单双重检查，没有发现 cosine/SPD/AIRM 几何函数定义。证据引用：[run_reprompting.py:23–33](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L23-L33)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:192–205](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L192-L205)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。这不是因 README 文案推断没有实现，也不是一次运行报错的猜测。

## 3. 检测入口与数据流

| 入口 | 源码实际表达的数据流 | 完整性/产物 |
|---|---|---|
| run_watermark.py | 建立 WM provider，取得原始 wm_zT，目标生成，再目标反演、原 WM 验证 | 原始噪声在循环前建立并跨提示词复用；几何计算及张量保存注释；活动 CSV 保存原 WM 结果 |
| run_no_watermark.py | randn(1,4,64,64) → 目标生成 → 目标反演 | 活动保存 zT_latents/ret_latents 到固定 gs_zT_latents_pairs.pt，按列表次序配对；名称不表示 GS 水印，生成路径没有 WM provider |
| run_reprompting.py | 每轮 wm_zT → 目标参考图 → 代理反演 → 代理按另一提示词生成 → 目标验证/再次反演 | 几何调用及几何 CSV、张量保存均注释；活动判定用原 WM 分数；图片固定 reprompt_img.png |
| run_imprint_forgery.py | 代理梯度优化，周期性目标 WM 验证 | 是已有优化基线，不能当作 C.3 Reforge 的实现 |

正常样本证据：[run_watermark.py:119–168](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L119-L168)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:187–262](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L187-L262)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:267–347](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L267-L347)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
无水印证据：[run_no_watermark.py:93–134](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_no_watermark.py#L93-L134)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；缺工厂 import：[run_no_watermark.py:10–12](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_no_watermark.py#L10-L12)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
Reprompting 证据：[run_reprompting.py:192–220](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L192-L220)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:254–304](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L254-L304)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:389–458](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L389-L458)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
Imprint 证据：[run_imprint_forgery.py:215–282](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_imprint_forgery.py#L215-L282)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

活动 validate 只执行目标反演、wm_provider.get_accuracies、质量指标和保存，没有几何分数调用：[utils/imprint_utils.py:355–445](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/imprint_utils.py#L355-L445)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。GS 最终判断为 bit_accuracy > 0.70703125：[utils/utils.py:9–12](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L9-L12)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/utils.py:58–115](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L58-L115)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:410–425](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L410-L425)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。所以当前几何分数既没有进入接受/拒绝，也没有在活动路径中被计算后记录；看到的几何 CSV 是被注释的离线分析草稿。

目标分数在 Reprompting 路径中用于参考检查、最终报告/CSV，没有基于它的提前停止、候选择优或超参数更新；代理生成依赖代理反演张量与提示词。源内共享进程能访问目标内部，并不等于攻击算法输入已隔离：[run_reprompting.py:223–299](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L223-L299)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:410–458](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L410-L458)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。旧单样本同样如此：[run_reprompting.py:138–201](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L138-L201)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。注释里的 sys.exit、flag、几何阈值不是活动流程。

入口还有非审计副作用：get_text_prompts 默认可能通过 datasets 下载 SDP；初始化 scheduler 的 from_pretrained 可以联网；generate/invert 会加载模型并按 device 放置；WM provider 默认 device=cuda；set_random_seed 含 CUDA 调用；多个水印模块被一次性 import。故本轮没有 import 这些入口或 provider。证据：[utils/prompt_utils.py:52–83](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/prompt_utils.py#L52-L83)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:37–51](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L37-L51)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:376–393](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L376-L393)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/wm_provider.py:12–36](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/wm_provider.py#L12-L36)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/utils.py:120–129](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L120-L129)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/wm_utils.py:3–9](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/wm_utils.py#L3-L9)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

## 4. 几何指标：论文定义与公开实现的对应性

论文依据均为 [v1 §4.3.2–4.3.3、§5.1](https://arxiv.org/html/2606.29807v1#S4.SS3)。

| 项目 | 论文定义 | 代码能确认到什么程度 |
|---|---|---|
| G-Cos | Definition 4.5 / Remark 4.7：原始与恢复噪声向量的点积除以两者 L2 范数；SAD 为 arccos(cos) | 仅见注释 latent_cosine(wm_zT,zT_retrieved)，实现缺失 |
| 输入 | 原始目标水印噪声与目标对图像恢复的噪声 | SDXL/SD 路径预期 [1,4,64,64]，但指标 flatten 轴、batch 汇聚、dtype/epsilon 未知 |
| 分数方向 | G-Cos 高表示方向接近；SAD/L-SPD 高表示偏差大 | 不能据注释函数名证明符号、截断或归一化实现 |
| 局部协方差 | Def.4.8：C(z)=M⁻¹Σ(tᵢ−均值)(tᵢ−均值)ᵀ+εI，ε>0 | token 定义/轴顺序、实际 M、通道归一化、ε数值、特征值截断均 unknown |
| SPD 距离 | §4.3.3：‖log(P₁⁻¹ᐟ²P₂P₁⁻¹ᐟ²)‖F | missing spd_utils，不能核实求解器和正则细节 |
| 分块与聚合 | §5.1：规则 16×16 spatial grid，局部差异 top-5 mean | 无可运行实现可确认网格映射；注释另有 n_parts=4、grid_size=4/topk=3、grid_size=8，不能当作论文参数 |
| 多分数融合 | §4.3.4 Theorem 4.10 讨论联合拒绝区域；Table 2/4 分列两项 AUC | 未发现活动融合规则、固定阈值或一图最终几何判定接口 |

对应源码：[run_watermark.py:228–243](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L228-L243)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:304–394](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L304-L394)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。形状由 provider 的 4 通道、resolution/VAE scale 计算：[utils/pipe/pipe_provider.py:18–19](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L18-L19)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:425–444](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L425-L444)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。上述 [1,4,64,64] 是当前 SDXL/SD 512 配置下的源码推导，未在本轮加载模型测量。

## 5. 参考潜变量来源与关联

源码比较参数中的 wm_zT 是 get_wm_latents 返回并用于目标生成的**原始目标噪声**，不是代理噪声，也不是目标对参考图反演的噪声。Reprompting 在同一循环中持有原始 wm_zT、参考图、攻击图，攻击图的 zT_retrieved 来自目标模型再反演；这是实验内位置关联，未发现对任意外部待检图片检索参考的接口。[run_reprompting.py:203–217](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L203-L217)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:284–314](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L284-L314)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

正常样本脚本在循环前产生一次 wm_zT，多个提示词共用它，因此该脚本不是逐图唯一潜变量协议；Reprompting 每轮新建 provider、再抽连续噪声，但默认固定 offset 与相同密钥/消息表。[run_watermark.py:125–168](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L125-L168)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/gs_provider.py:39–46](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L39-L46)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/gs_provider.py:93–108](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L93-L108)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/gs_provider.py:145–186](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L145-L186)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

GS 固定消息、key、nonce 决定加密分区；每个分量还使用 NumPy uniform，经 norm.ppf 得到连续值。因此知道 key/消息不等于知道原始连续噪声。公开表是实验固定材料，不能作为真实秘密安全性的证据。[utils/wm/gs_provider.py:145–182](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L145-L182)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

正常/Reprompting 的 wm_latents/ret_latents 保存代码均被注释；只有无水印脚本活动保存配对张量，且没有图像哈希关联清单。[run_watermark.py:232–243](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L232-L243)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:319–328](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L319-L328)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:429–438](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L429-L438)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_no_watermark.py:119–134](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_no_watermark.py#L119-L134)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

论文 v1 §4.1 说不逐图存原始生成特征，§4.3.1 与 C.4/Fig.8 又需要参考 zT 与恢复 zhatT。公开材料未交代参考如何持久化/由状态重建、候选如何找回对应参考，也未给出无原始噪声的等价实现。**关联机制与零存储主张的实现对应性为 unknown**，属于证据缺口，不直接认定为漏洞。[v1 §4.1、§4.3.1、C.4](https://arxiv.org/html/2606.29807v1#A3.SS4)

## 6. 阈值与评估协议

论文 v1 §5.1 对原水印报告固定 FPR 下 TPR，对几何报告阈值无关 AUC。§4.3.4 的理论拒绝区域不是已给出的部署阈值；公开代码也无 ROC/校准划分/几何阈值发布脚本。正常样本误拒率和伪造样本错误接受率不能从 AUC 或这个单样本得到。[v1 §5.1、§4.3.4](https://arxiv.org/html/2606.29807v1#S5.SS1)

本审计使用的概念区分：几何误拒是“正常样本被几何拒绝”；几何错误接受是“伪造样本通过几何”；若最终必须通过水印和几何，则最终错误接受是二者均通过的伪造比例。这些是指标含义说明，不是公开实现已经采用的组合公式。论文 C.4 规定几何先于 WM，§6.4 称为预警；活动代码仍只有 WM 判定。最终几何/WM 布尔关系、分数融合、校准集与测试集划分、ROC 正标签和实际部署阈值均 **unknown**。

注释中的 0.125、0.37、1.3 等没有活动路径或阈值来源，不能取消注释后称为作者发布协议：[run_reprompting.py:352–368](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L352-L368)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:239–259](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L239-L259)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。保留阶段 02 GS >0.70703125，但它只属于原 WM，不替代几何阈值：[utils/utils.py:9–12](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L9-L12)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/utils.py:102–103](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L102-L103)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。另有语义差异：该阈值源码注释注明 100k 用户的 multi-bit 设定，论文 v1 A.1 GS 段排除 attribution；本轮不改数值，也不据此声称复现了归属/FPR。

## 7. 与阶段 02 的兼容性

| 项目 | 阶段 02 真实配置 | 几何公开材料 | 判定 |
|---|---|---|---|
| 目标模型 | stabilityai/stable-diffusion-xl-base-1.0 @462165984030d82259a11f4367a4eed129e94a7b | 同 ID，未固定 revision | ID 可复用；需显式固定现有 snapshot；论文权重逐字节等价 unknown |
| 代理模型 | Manojb/stable-diffusion-2-1-base @0094d483a120f3f33dafbd187ea4aa60d10de75c | stabilityai/stable-diffusion-2-1-base，revision 未给 | 需要明确适配；换模型会改变攻击条件；现有候选评估不需重新调用代理 |
| 分辨率/形状 | RGB 512×512；预期噪声 1×4×64×64 | SDXL/SD 默认一致 | 图像格式可以直接复用 |
| VAE 编码 | [0,1] 转 [-1,1]，posterior.mean×scaling_factor | 基类表达式一致 | 公式可复用；保持目标 snapshot 与 VAE 配置，运行数值未验证 |
| VAE 解码/量化 | Diffusers SDXL/SD pipeline 返回 PIL，再 VAE 编码供反演 | 同 pipeline 类，增加可选 callback | 需保持版本和 PIL/RGB 数据流；不能把原始无量化 latent 当作 PNG 输入的等价物 |
| scheduler | 自定义 DDIM + DDIM inverse | 两个 scheduler 文件哈希与旧仓库相同 | 源码可以复用；缺工厂，代理 scheduler 参数未传入工厂调用，完整连线尚不能确认 |
| 生成/反演步数 | 目标50、代理50；同参数用于反演 | 默认50 | 可复用 |
| guidance | 生成7.5；反演空 prompt、1.0 | 基类相同 | 可复用 |
| 精度 | float32 | SD/SDXL 基类 float32 | 可复用；改半精度会改变比较条件 |
| GS 参数 | l=1，message_width_in_bytes=32，num_replications=64，offset=0、batch=1（入口未覆盖默认） | GS provider 与 wm_provider 及消息/key/nonce 表逐字节相同 | 默认参数/固定表可复用；不等于原始连续噪声已保存 |
| 提示词 | 固定茶壶→红帆船 | 入口忽略显式提示词参数，从 SDP 前/后取样 | 需要明确适配输入；替换现有图片/提示词改变实验；单样本不等同论文分布评估 |
| 阈值 | GS 严格 >0.70703125 | 原 WM 相同；几何 unknown | GS 可保留；几何不可代填 |
| 环境 | 记录 torch2.5.1、diffusers0.31.0、transformers4.46.3、accelerate1.1.1、numpy2.2.6 | requirements 要 accelerate1.9.0、numpy1.26.0，且全量 import 含其他 WM 依赖 | 不能称整仓库即装即用；本轮未安装或修改环境 |

模型参数/提示词证据：[run_reprompting.py:80–153](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L80-L153)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；旧代理映射：[utils/pipe/pipe_utils.py:15–39](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/pipe/pipe_utils.py#L15-L39)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。
VAE/精度：[utils/pipe/pipe_provider.py:18–19](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L18-L19)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:139–188](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L139-L188)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:239–261](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L239-L261)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:279–315](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L279-L315)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/image_utils.py:414–435](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/image_utils.py#L414-L435)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
基类 diff 仅 callback 透传及格式差异；SDXL 类额外包含 Anime provider，不据此推断 SDXL 主类改变。文件哈希对照见 source_evidence.json；SDXL 主类：[utils/pipe/SDXL_provider.py:1–18](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/SDXL_provider.py#L1-L18)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
GS 默认与采样：[utils/wm/gs_provider.py:28–46](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L28-L46)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/gs_provider.py:135–186](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L135-L186)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。依赖：[requirements.txt:1–36](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/requirements.txt#L1-L36)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
论文模型 ID、生成设置与提示词协议依据 [v1 D.1/Table 6、D.2](https://arxiv.org/html/2606.29807v1#A4.SS1)。

## 8. 已有自适应评估范围

| 层级 | 核查结果 |
|---|---|
| 作者讨论过 | v1 C.3 明确讨论 Reforge：净化后以代理重印；§6.4 讨论更强、相同目标/代理设置 |
| 提供公开算法/代码 | C.3 有两阶段概念描述；未给可复现净化强度、损失、停止规则或 Reforge 入口。本 commit 的 4 个入口及源码检索未发现 Reforge 策略实现 |
| 真正进入实验比较 | §5.1/Table 1–4 是 Reprompting/优化攻击；§6.4/Table 2 有相同模型设置。C.3 明确说 Reforge 未纳入比较 |
| 证据不足 | Reforge 在当前 GS→几何场景的数值表现、预算与自适应绕过率；本轮没有相关实验数据 |

论文依据：[v1 C.3、§6.4、§5.1](https://arxiv.org/html/2606.29807v1#A3.SS3)。源码边界：已有优化器及周期验证 [run_imprint_forgery.py:215–282](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_imprint_forgery.py#L215-L282)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`），不能将其等同 Reforge。作者对 Reforge 成本/画质/几何损伤的论述是讨论，不能升级成公开实验验证；也不能写作者完全没有考虑自适应攻击。

## 9. 现有单样本能否复用

**图片可以复用为图像输入，当前材料不足以忠实输出几何判定。**

| 所需材料 | RUN_DIR 实际情况 | 恢复或新计算条件 |
|---|---|---|
| 参考图、候选图与哈希 | 已保存并核对 | 原 PNG 可直接作为未来目标 VAE/反演输入；几何函数并非直接吃 PNG |
| 准确模型/revision、提示词、步数、CFG、精度、种子 | 配置、snapshot 记录、pip_freeze 已保存 | 可用于固定已有条件；不推定对应论文未公布 revision |
| GS 参数与消息 | 默认参数可由 commit 推导；CSV 有初始/恢复消息 | 密钥/nonce 表保留于上游，默认 offset=0；不用在报告或攻击交付物中复制其值 |
| 原始目标 wm_zT | 未保存；无张量文件或原张量哈希 | 有 seed 和固定采样源码，提供条件性重建线索；尚未证明可准确恢复 |
| 目标对参考/候选的反演噪声 | 未保存；CSV 只留分数 | 未来需目标 VAE 编码和各50步目标反演；本轮没有运行 |
| 完整 RNG 状态/连续采样 u/轨迹 | 未保存 | 同 seed 不足以证明完整生成状态恢复；需核对 RNG 消耗顺序、库版本和精度，取得可验证的原始参考 |
| 图像→原始潜变量映射 | 仅该 run 的逻辑对应关系 | 缺持久化 latent+hash 的可校验绑定 |
| 官方几何函数、数值参数、阈值协议 | 不在 RUN_DIR；新仓库也不完整 | 需作者完整材料，不能自行补函数/阈值 |

旧源码明确只把 wm_zT 放在进程内用于生成，验证返回分数后写 CSV 和 PNG：[run_reprompting.py:97–121](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L97-L121)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）；[utils/imprint_utils.py:338–347](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/imprint_utils.py#L338-L347)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）；[utils/imprint_utils.py:387–409](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/imprint_utils.py#L387-L409)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。
NumPy seed=seed+3，即当前 seed=1 对应种子4；GS 连续噪声还取决于之后的随机调用顺序。只有 seed 与固定 key/消息，不等于保留完整随机状态或证明原始张量可逐位重建：[utils/utils.py:63–72](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/utils.py#L63-L72)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）；[utils/wm/gs_provider.py:145–186](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/wm/gs_provider.py#L145-L186)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。本轮没有生成噪声来测试恢复。

若后续获得完整作者协议，完成一次评估仍需：取得正确且可验证的目标参考 wm_zT，针对两张原 PNG 进行目标反演，然后用冻结的作者几何函数与判定协议计算结果。新噪声、代理噪声、参考图反演噪声不能自动充当原始 wm_zT；缺项无法恢复时应保持“当前历史样本未能忠实评估”，不能悄悄生成另一个样本冒充本次记录。

## 10. 信息边界、阻塞与唯一下一步

具体输入、保密数据、哈希交付和评估后信息流见 `information_boundary.md`。这是接口设计，当前单进程官方程序尚未提供进程/权限安全隔离。

阻塞：完整几何实现/模型工厂缺失；参考噪声持久化或重建与关联机制未明确；现有 run 没有原始/恢复潜变量和 RNG 状态；几何阈值及融合/校准协议未公开；论文与阶段02代理 ID/revision 不完全对应。

**唯一下一步：取得并冻结作者与 v1 对应的完整单样本评估材料包，要求同时明确 G-Cos/L-SPD 实现、参考潜变量取得与关联方式，以及固定判定协议；据此决定历史样本能否忠实评估。** 在这些材料明确之前不补写替代验证器、不调整阈值。本阶段到此停止。



---

# 阶段 03 信息边界

来源：[reports/03_geometry_audit_20261013T020025Z/information_boundary.md](../reports/03_geometry_audit_20261013T020025Z/information_boundary.md)。

# 攻击端与目标评估端的信息边界

适用项目：`/data0/liyanlei/watermark_research`。
设置：攻击算法获得一张参考水印图、指定输出提示词和代理模型，在固定预算下产生预先固定的候选；目标检测结果不参与候选筛选或参数调整。
本文是后续接口与信息流设计；**尚未实现或验证安全隔离**。

## 1. 输入、权限与持有者

| 信息/能力 | 攻击算法 | 目标评估端 | 实验控制端 |
|---|---|---|---|
| 参考 PNG 及其公开样本 ID/图像 SHA256 | 可读 | 可读 | 登记 |
| 指定攻击输出提示词 | 可读 | 可用于报告解释 | 预先固定 |
| 代理模型 ID、revision、权重与代理调用 | 可用 | 可记录版本 | 管理代理环境 |
| 攻击自身 seed、固定预算/参数 | 可用 | 留档 | 在评估前固定 |
| 目标模型公开身份 | 可作为明确公布的元信息 | 知道准确身份 | 记录身份公开范围 |
| 目标模型内部 pipeline、VAE/反演调用权限 | 不提供 | 独有 | 仅为部署与审计持有 |
| 目标原始提示词 | 不提供 | 按协议持有 | 本地固定样例的控制变量 |
| 目标 WM key、nonce、原始消息或表索引 | 不提供 | 独有 | 仅管理/审计 |
| 原始目标生成噪声 wm_zT | 不提供 | 几何协议若需要则独有 | 保存与图像绑定及哈希 |
| 目标生成 seed、完整 RNG 状态、连续采样值 | 不提供 | 仅在明确恢复协议中使用 | 保存版本/状态，不能转入攻击配置 |
| 目标对参考/候选的内部反演噪声 | 不提供 | 独有 | 仅受控审计 |
| 原 WM 分数、几何分数、阈值结果、评估日志 | 固定输出前后均不回馈算法做本轮选择 | 计算并保存 | 可在冻结后做科研报告 |
| 校准/测试标签、参考检索库 | 不提供 | 按既定作者协议持有 | 冻结评估协议与划分 |
| 候选图及其 hash | 先生成并交付 | 再校验、读取 | 保存提交时间和状态 |

“公开模型身份”和“目标内部调用权”必须分别授权。知道 SDXL 的公开名称不代表攻击算法能调用本地目标 VAE、获取目标内部噪声或读取检测分数。即使目标权重公开可下载，本项目此设置也不因公开身份而自动允许把它作为额外攻击 oracle；若以后改变攻击能力，应另立设置并明确记录。

论文 v1 §4.1 假定攻击者不知道目标架构/参数及合法生成提示词；§3.2 又提及黑盒查询。我们的优先设置明确固定为参考图+输出提示词+代理，目标分数查询预算为零。若另行公开目标身份，属于需要标注的信息条件，不能声称与论文所有未知模型条件完全相同。[论文 v1 §3.2、§4.1](https://arxiv.org/html/2606.29807v1#S4.SS1)

## 2. 现有官方程序的信息流证据

阶段 02 旧官方 commit `ca68950cd7b53b8438a49580f134b2a0db28d778`：
[run_reprompting.py:97–146](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L97-L146) 在同一进程构造目标 WM、生成参考图并验证；
[run_reprompting.py:148–171](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L148-L171) 的未 resample 分支只把代理反演结果用于代理生成；
[run_reprompting.py:173–205](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L173-L205) 再做目标验证和日志/CSV。源码未用目标分数进行候选选择、提前停止或超参数调整，但单一进程确实持有所有目标敏感信息。

新几何 commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`：
[run_reprompting.py:203–220](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L203-L220) 持有 wm_zT；
[run_reprompting.py:254–302](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L254-L302) 同一作用域内包含代理操作、目标验证及目标内部反演；
[run_reprompting.py:389–425](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L389-L425) 的几何块注释、活动 WM 结果记录。它没有已经可供复用的权限隔离接口。

GS 实验使用公开固定 key/message/nonce 列表：
[utils/wm/gs_provider.py:93–108](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/wm/gs_provider.py#L93-L108)，完整 commit `ca68950cd7b53b8438a49580f134b2a0db28d778`。
这些表的公开性与算法“不使用它们”是两回事，不能把公开实验常量描述为已保密。以后若要求密钥不可知，需评估端专属材料与实际访问控制；不能仅拆成两个文件或靠约定证明攻击者拿不到它们。

## 3. 本地实验控制持有但不能传入攻击算法的材料

当前 RUN_DIR 的 config.json 包含目标生成 seed 和提示词；metrics.csv 包含初始消息位串、恢复消息位串和目标检测分数；日志及模型 snapshot 记录包含目标配置。完整 RUN_DIR 不能直接作为攻击进程的输入目录。

后续攻击输入应采用白名单：参考 PNG、reference_id、指定输出提示词、代理配置、攻击自身随机状态及固定预算。白名单不能嵌入目标消息/密钥、原始噪声、目标 seed、目标反演结果或检测分数，也不能给出通往这些文件的路径。攻击端自己的代理潜变量可以保留，但名称/类型应标明 proxy，评估端不能将其当作目标参考。

本地当前研究者已经能读这些历史数据，本文不声称消除了既往知识，也不保证源代码公开常量能保密。对于“算法无目标反馈”的结论，只能在明确代码路径与数据访问证据支持的范围内作出。

## 4. 候选交付与评估顺序

1. 实验控制端提前固定参考图哈希、输出提示词、代理模型版本、攻击配置与预算、输出数量和成功/失败记录规则。单样本交付一张候选；失败也保留状态，不按目标结果补抽。
2. 攻击端输出候选文件及 manifest：candidate_id、reference_id、reference_sha256、candidate_sha256、字节数、图像尺寸、攻击代码 commit、代理 revision、攻击 seed、配置哈希、退出码与时间。manifest 不含目标内部信息。
3. 攻击端关闭写入并提交；控制端冻结清单和图像内容。哈希证明所评估字节与承诺字节相同，本身不证明没有其他泄漏。
4. 评估端再读取被冻结候选，重新计算 SHA256；不匹配则记录交付失败。用评估端私有映射取得正确目标参考，运行冻结的作者验证器和原 WM 检测，另存 evaluator-only 记录。
5. 控制端报告结果，但本轮攻击算法不据此改图、选候选、调参数或重试。后续任何利用结果的研究都需要另定攻击设置，不将其混入本轮样本。

## 5. 未来隔离验证的范围

未来真正实施时，需要分别约束账号/容器挂载、文件读写权限、目标服务访问、网络访问和日志通道，并审计实际访问。CUDA_VISIBLE_DEVICES 只限制设备可见性，不能替代信息隔离；两个 Python 文件也不能替代权限边界。
本阶段只读代码并写接口设计，没有部署上述权限或运行攻击/评估流程。

## 6. 几何机制特有的未决依赖

论文 v1 §4.3.1、C.4/Fig.8 需要参考目标 zT，§4.1 又强调不逐图存原始特征。公开代码以同进程 wm_zT 作参考，没有发布外部候选到参考的检索/重建协议。
[论文 v1 C.4](https://arxiv.org/html/2606.29807v1#A3.SS4)；
[run_reprompting.py:203–217、301–314](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L203-L217)，完整 commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`。

因此不能把参考图库、原始噪声或目标随机状态悄悄加入攻击输入来“补齐验证”；这些只能是评估端的明确依赖。不能把 missing reference 标成验证拒绝或攻击失败，也不能拿随机噪声替代。当前状态应为“评估所需证据缺失/unknown”，与模型真实判定分开。



---

# 阶段 03 状态

来源：[reports/03_geometry_audit_20261013T020025Z/03_status.json](../reports/03_geometry_audit_20261013T020025Z/03_status.json)。

```json
{
  "stage": "03",
  "checked_at_utc": "2026-10-13T02:15:05Z",
  "project_root": "/data0/liyanlei/watermark_research",
  "report_dir": "/data0/liyanlei/watermark_research/reports/03_geometry_audit_20261013T020025Z",
  "stage02_evidence_consistent": true,
  "stage02_run_dir": "/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z",
  "stage02_check_status": "已核对一致：命令、配置、退出记录、完成日志、CSV、图片尺寸/哈希与可见内容",
  "stage02_historical_gpu": 3,
  "stage02_bit_accuracy": {
    "reference": 1,
    "forged": 0.953125
  },
  "geometry_paper_version": "arXiv:2606.29807v1",
  "geometry_repo_path": "/data0/liyanlei/watermark_research/third_party/geodistort-wm",
  "geometry_repo_remote": "https://github.com/chengyi-chris/geodistort-wm.git",
  "geometry_repo_branch": "main",
  "geometry_repo_commit": "72880c9bb1cee0b04bcb2433deb2ab2cc95ff622",
  "geometry_repo_license": "未发现许可证正文；README 有 MIT 徽章",
  "implementation_completeness": "不完整：缺少 pipe_utils、finger_utils、spd_utils；几何计算及保存路径被注释",
  "reference_latent_source": {
    "source_in_code": "目标原始生成水印噪声 wm_zT",
    "candidate_reference_lookup": "unknown",
    "stage02_original_latent_saved": false,
    "exact_recovery_verified": null
  },
  "decision_rule_status": {
    "active_rule": "仅原水印；GS bit_accuracy > 0.70703125",
    "geometry_final_rule": "unknown",
    "geometry_threshold": null,
    "calibration_test_split": "unknown"
  },
  "compatibility_with_stage02": "图片格式与 GS/调度器源码可复用；代理 ID/revision、缺失工厂、参考潜变量与几何判定协议需明确，尚不能忠实评估",
  "missing_artifacts": [
    "完整官方几何指标实现及数值配置",
    "目标参考潜变量持久化/恢复与图像关联协议",
    "阶段02原始目标噪声、目标反演噪声及完整 RNG 状态",
    "固定几何阈值、分数组合与校准/测试协议"
  ],
  "gpu_used": false,
  "models_loaded": false,
  "new_experiments_run": 0,
  "blockers": [
    "公开实现不完整",
    "历史样本参考潜变量恢复尚未验证",
    "几何接受/拒绝协议未知",
    "论文代理模型版本与现有配置等价性未确认"
  ],
  "next_step_proposal": "取得并冻结作者与 v1 对应的完整单样本评估材料包，明确几何实现、参考潜变量取得与关联方式、固定判定协议，再判断历史样本能否忠实评估。"
}
```

---

# 阶段 04 原始要求

来源：[prompts/stage04_request.txt](../prompts/stage04_request.txt)。

```text
你是本项目的科研工程助手。

本轮只执行：
“阶段 04：单样本潜变量留存与全局余弦诊断”。

研究主线：
扩散模型语义水印的黑盒伪造攻击。
本轮不设计新水印、不改进检测器、不校准防御阈值。

本轮目标：
在不改变官方 Reprompting 攻击计算的前提下，
新运行一个固定样例，保存实际使用的目标原始噪声、
目标对参考图和攻击图的反演噪声，
然后在 CPU 上独立计算两个全局余弦分数。

这不是完整官方几何验证的复现。
不实现 L-SPD，不补全未知几何规则，不宣称绕过几何防护。
不训练，不做参数搜索，不批量生成，不按结果重试。

一、读取已有状态

通过已有 SSH 认证连接：
liyanlei@172.18.185.249

项目根：
/data0/liyanlei/watermark_research

不保存或输出密码、令牌、私钥。
不关闭 SSH 主机密钥检查，不扫描其他主机。
连接或路径失败时停止并报告。

先阅读：
AGENTS.md
reports/02_smoke_report.md
reports/02_status.json
reports/03_geometry_audit_20261013T020025Z/03_audit.md
reports/03_geometry_audit_20261013T020025Z/information_boundary.md
reports/03_geometry_audit_20261013T020025Z/03_status.json

若文件位置与记录不符，只在项目 reports 内定位，
不要扫描整个服务器。

检查是否已有本阶段运行或未结束进程。
已经完成时返回已有记录；正在运行时报告状态；
不要自动重复执行或覆盖任何文件。

保持两个上游仓库不变。
本轮不运行 geodistort-wm 的入口，不补写其缺失模块。

二、固定环境与设备

使用已有独立环境：
/data0/liyanlei/watermark_research/envs/semantic_forgery_py310

使用原始官方仓库：
third_party/semantic-forgery

预期完整 commit：
ca68950cd7b53b8438a49580f134b2a0db28d778

核对 commit 和工作区。
状态不符时记录并停止，不 reset，不自动更新。

本轮只使用物理 GPU 7：
GPU-9644fb82-cb6f-7311-8017-eaee41409bb7

启动前重新核对物理编号、UUID、型号、占用和计算进程。
GPU 7 忙、身份不符或授权有冲突时停止，不自动换卡。
阶段 02 使用 GPU 3 只作为历史事实，不据此扩大本轮范围。

所有 GPU 子进程在导入项目模块之前设置：
CUDA_DEVICE_ORDER=PCI_BUS_ID
CUDA_VISIBLE_DEVICES=GPU-9644fb82-cb6f-7311-8017-eaee41409bb7

程序内使用单张可见卡 cuda:0。
不使用 DDP、不做多卡切分、不终止他人进程。

CPU 单元测试及事后分数计算进程设置：
CUDA_VISIBLE_DEVICES=""

沿用项目已有模型缓存、离线模式及以下 snapshot：
目标：
stabilityai/stable-diffusion-xl-base-1.0
revision=462165984030d82259a11f4367a4eed129e94a7b

代理：
Manojb/stable-diffusion-2-1-base
revision=0094d483a120f3f33dafbd187ea4aa60d10de75c

核对实际加载路径，不仅记录模型 ID。
缓存缺失时报告，不重新下载。
不安装依赖，不调整现有包版本，不下载新模型。

本轮新增文件预算上限 1 GiB；
启动前确认工作盘至少剩余 200 GiB。
不要复制模型权重或清理其他项目腾空间。

三、只添加记录，不重写攻击算法

在项目自有代码目录建立最小记录入口。
优先采用薄封装或少量可审查的记录改动，
不要重写整套 pipeline。

可以在项目自有目录保存官方入口的记录版，
但必须保留来源 commit、原文件哈希及完整差异。
不得修改 third_party 内的文件。

先静态确认：
1. wm_provider.get_wm_latents() 的真实调用位置；
2. 传入目标生成的 wm_zT；
3. validate(step=-1) 中目标反演的返回值；
4. validate(step=1) 中目标反演的返回值。

本轮必须从这些真实计算位置捕获数据，
不能事后凭相同 seed 猜测生成噪声。

只增加旁路记录：
- 不改参数、返回值、调用顺序和原有随机数消耗；
- 不原地修改被记录张量；
- 不移动或替换模型正在使用的原始张量；
- 用独立 CPU 副本保存，保留原 dtype；
- 不增加额外的生成、反演或水印检测调用；
- 不提前算几何分数影响后续流程；
- 不使用目标分数做分支选择、优化或重试。

不要为了记录而改变：
res_1 到代理反演的输入类型与数据流；
VAE 编解码、PIL/RGB 转换；
自定义 scheduler；
stash_pipe() 顺序；
生成与反演的 guidance；
水印参数和检测规则。

若无法在保持上述条件下完成记录，
先报告具体原因，不自动更换实验方案。

在小型 mock/CPU 测试中检查记录包装：
调用次数不增加、返回对象和数值不被替换、
原输入不被修改、记录不推进随机状态。
不要为测试包装而提前加载模型。

这些测试和源码检查不等于已经完成
“有记录/无记录”的完整数值等价实验；
报告必须保留这一限制。

四、固定本次运行

这是新的、独立标识的运行，不是阶段 02 的历史恢复。

建立唯一目录，例如：
runs/04_reprompt_latent_diag_seed1_<UTC时间戳>

首次模型调用前冻结配置和记录代码。
固定：
wm_type=GS
seed=1
resolution=512
num_inference_steps_target=50
num_inference_steps_attacker=50
guidance_scale_target=7.5
guidance_scale_attacker=7.5
scheduler_target=DDIM
scheduler_attacker=DDIM
resample=false
float32

参考提示词：
A studio photograph of a yellow ceramic teapot on a wooden table.

攻击提示词：
A red sailboat on a calm blue lake, watercolor illustration.

沿用官方反演设置，不把反演 guidance 改成 7.5。
不启用 autocast、量化、torch.compile 或新优化组件。
只允许一次正式单样本模型运行。

保持原 GS 检测规则：
bit_accuracy > 0.70703125

保留原始 metrics.csv 及未计算质量指标的占位值。

发生 OOM 或其他模型运行错误：
保留日志、traceback、真实退出码和已完成产物后停止。
不得自动降精度、减步数、换提示词、换 seed 或追加样本。
工程问题可以定位，但本轮不自动启动第二次模型运行。

五、保存实际张量与对应关系

至少保存以下三个真实张量：
target_original_wm_zT
target_inverted_reference_zT
target_inverted_forged_zT

其中 target_original_wm_zT 必须是
实际传入目标生成的原始水印噪声，
不是代理噪声、参考图反演噪声，
也不是另一次重新采样得到的噪声。

后两个必须来自本次官方 validate 的既有目标反演，
分别绑定 step=-1、step=1。

可以额外留存原水印采样之前的 RNG 状态，
但只能读取状态，不能推进或重设官方随机序列。
不能因为保存了 seed/RNG 就声称恢复了阶段 02 历史张量。

采用现有依赖支持的非 pickle 张量格式，
例如 safetensors 或不含 object 的 NPY。
保存后在 CPU 重新读取，核对形状、dtype 和数值一致性。

为每个张量记录：
- 实际文件路径和 SHA256；
- 形状、dtype；
- 捕获函数与对应源码位置；
- 目标/代理角色；
- 所关联的 reference_id/candidate_id；
- 本次配置哈希；
- 对应图像文件的 SHA256。

参考图和攻击图由本次官方流程保存。
核对被验证的 PIL 图像与落盘 PNG 解码后的像素一致性，
避免张量实际对应 A 图，而清单关联到 B 图。

目标潜变量、RNG、原始 CSV 及目标评估记录放入
evaluator_only 目录或明确标记为评估端产物。
不得将这些内容加入攻击输入清单。

本轮仍是在官方复现框架上增加记录，
不声称已建立进程级或权限级信息隔离。
目录名、文件权限和哈希本身不证明隔离成立。

六、CPU 全局余弦诊断

仅在候选图已经保存并冻结 SHA256 后，
由独立 CPU 进程读取本次实际张量计算。

实现名称明确使用：
independent_global_cosine_diagnostic

论文依据：
arXiv:2606.29807v1
Definition 4.5 与 Remark 4.7

计算定义：
cosine(z, zhat) = dot(z, zhat) / (norm(z) * norm(zhat))

本轮采用的明确实现约定：
- 输入必须是相同形状且有限的数值张量；
- batch=1，每样本展平全部 C/H/W；
- 不做均值中心化、不逐通道求均值、不重采样；
- 原张量保持 float32 保存；
- 只在 CPU 诊断计算时转换为 float64；
- 零范数、非有限值、形状不符必须报错，
  不用默认分数或 epsilon 掩盖无效输入。

CPU 单元测试至少覆盖：
同向向量=1；
反向向量=-1；
正交向量=0；
正比例缩放不改变余弦；
零范数与非有限输入被拒绝。

计算并保存：
gcos_reference =
cos(target_original_wm_zT, target_inverted_reference_zT)

gcos_forged =
cos(target_original_wm_zT, target_inverted_forged_zT)

gcos_gap_reference_minus_forged =
gcos_reference - gcos_forged

不预设差值应为正，不根据结果修改实现。
不实现 L-SPD，不添加融合规则。
不设置几何阈值，不输出几何通过/拒绝判定。

报告说明：
这是按照明确公式实施的独立全局分数诊断；
与作者缺失函数的逐项数值等价性尚未验证；
不是完整官方几何检测结果；
一个样本不能证明总体可分性或总体攻击成功率。

七、日志、交付与停止

记录真实退出码、stdout/stderr、完整命令、
配置、代码差异和版本、实际模型 snapshot。
GPU 监控沿用每 2 秒采样，注明是采样峰值。
结束后仅确认本轮进程退出，不操作他人进程。

在唯一的新报告目录保存：
04_report.md
04_status.json

RUN_DIR 保存：
原始 CSV、图片、日志、配置；
张量文件与对应清单；
CPU 测试和诊断结果；
记录代码的来源与差异。

04_status.json 至少包含：
stage
run_dir
upstream_commit
recording_code_path
recording_code_sha256
recording_changes
gpu_uuid
model_snapshots
execution_ok
reference_detected
forged_detected
reference_bit_accuracy
forged_bit_accuracy
tensor_capture_complete
tensor_manifest_path
image_tensor_binding_verified
cpu_metric_tests_passed
gcos_reference
gcos_forged
gcos_gap_reference_minus_forged
geometry_threshold
geometry_accepted
full_official_geometry_evaluation_completed
instrumentation_equivalence_status
wall_time_seconds
sampled_peak_gpu_memory_mib
blockers

其中：
geometry_threshold=null
geometry_accepted=null
full_official_geometry_evaluation_completed=false

其他未得到的值写 null，不把未知写成失败。
若参考图原水印检测未通过，
标记基线有效性未建立，不能宣称攻击有效。

可以记录本次与阶段 02 图像哈希是否相同，
但不同就如实记录，不修改参数去追求相同；
任何结果都不得覆盖阶段 02。

最终返回：
1. 本次原水印检测结果；
2. 三个真实张量是否完整留存；
3. 两个全局余弦分数及其差值；
4. 实验限制与阻塞；
5. 04_status.json 全文。

本轮不再追加样本，不开始优化攻击，
不自动发送邮件或发布 GitHub issue。
完成后停止。
```

---

# 阶段 04 初次执行前停止

来源：[reports/04_latent_diag_20261013T024515Z/04_report.md](../reports/04_latent_diag_20261013T024515Z/04_report.md)。

# 阶段 04：启动前检查与阻塞记录

检查时间：2026-10-13T02:45:15Z。
状态：**blocked_before_execution**。本阶段实验尚未执行。

## 实际检查结果

已通过已有 SSH 认证连接指定服务器，确认项目路径，并读取 AGENTS.md、阶段 02 报告/状态、阶段 03 审计报告、信息边界和状态记录。
在项目 runs、reports、scripts 的限定深度目录检查中未发现阶段 04 记录；本用户进程列表没有未结束的阶段 04 运行。

原官方仓库 commit 为 `ca68950cd7b53b8438a49580f134b2a0db28d778`，工作区干净，与预期一致。
几何仓库 commit 为 `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`，工作区干净。
工作盘可用 551182262272 字节，约 513.33 GiB，满足至少 200 GiB 要求。

## 停止条件

GPU 7 身份核对一致：
`GPU-9644fb82-cb6f-7311-8017-eaee41409bb7`，NVIDIA GeForce RTX 3090，24576 MiB。
检查时显存已使用 **12399 MiB**，GPU 利用率 **100%**。

| PID | 进程名 | 计算进程显存 |
|---|---|---:|
| 6655 | python | 9866 MiB |
| 35230 | python | 2522 MiB |

这些是已有进程的占用，不是本阶段采样峰值。没有操作这些进程。
用户要求“GPU 7 忙、身份不符或授权有冲突时停止，不自动换卡”，因此在预检查处停止。

## 本轮产物与未执行项

只创建本次唯一报告目录和检查记录。未创建 RUN_DIR、记录入口、张量或新模型运行。
未启动 Python/GPU 测试、模型加载、生成、反演、检测、CPU 余弦诊断；未安装依赖或下载模型。
模型 snapshot 的实际路径检查尚未执行，不能把阶段 02 历史路径写成本轮已验证加载路径。

原水印检测、三个潜变量留存、图像绑定、CPU 测试与余弦结果均为 null（未执行），不标记成实验失败或伪造分数。
完整官方几何评估未完成，几何阈值和接受判定保持 null。
尚未开展记录包装的 mock 测试，也未开展有/无记录的完整数值等价实验。

本次仅写入几 KB 报告文件，低于新增 1 GiB 预算；两个上游及已有实验文件均未修改。
阶段 04 当前阻塞于指定 GPU 占用，已停止，等待用户后续指令。



---

# 阶段 04 完成报告

来源：[reports/04_latent_diag_20261013T025322Z/04_report.md](../reports/04_latent_diag_20261013T025322Z/04_report.md)。

# 阶段 04：单样本潜变量留存与全局余弦诊断

本次新的独立单样本运行已完成。RUN_DIR：`/data0/liyanlei/watermark_research/runs/04_reprompt_latent_diag_seed1_20261013T025322Z`。
记录代码：`/data0/liyanlei/watermark_research/scripts/04_latent_diag_20261013T024856Z/run_recorded.py`，SHA256 `143107fa006698a9e0063ca1576764c830a7bc6d22d8d0c76c057b66a9e9f877`。
上游 commit：`ca68950cd7b53b8438a49580f134b2a0db28d778`，两个上游工作区保持干净。

## 运行与原水印检测

用户本轮授权物理 GPU 3；UUID `GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da`。启动前身份/占用复核通过，单卡可见，程序内 cuda:0。
正式模型进程仅启动一次，PID 44410，退出码 0，耗时 73.181185 秒。
每 2 秒采样 GPU 总显存占用，采样峰值 16632 MiB；不是连续监测的精确峰值。结束后该子进程已退出，GPU 3 回到 1 MiB、0% 利用率，未操作其他进程。
环境沿用已有 Python 3.10 独立环境；未安装/升级依赖或下载模型。

固定 GS、seed=1、512×512、目标/代理各50步、生成CFG=7.5、DDIM、float32、resample=false。
官方反演仍为空提示词、CFG=1.0；保留原 res_1 images_torch 到代理反演的数据流、VAE、scheduler、stash_pipe 顺序。
GS 参数：l=1、32字节消息、64次重复、offset=0。
参考提示词：A studio photograph of a yellow ceramic teapot on a wooden table.
攻击提示词：A red sailboat on a calm blue lake, watercolor illustration.

| 图像 | bit_accuracy | 原 GS 判定 |
|---|---:|---|
| 参考 | 1.0 | True |
| 攻击 | 0.953125 | True |

阈值保持 bit_accuracy > 0.70703125。参考水印检测通过；本次观察到一次原 GS 水印转移。
原始 CSV 在 `/data0/liyanlei/watermark_research/runs/04_reprompt_latent_diag_seed1_20261013T025322Z/evaluator_only/official_output/target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv`，未修改。PSNR/SSIM/MS-SSIM/LPIPS 仍为官方未计算占位 -1，GS p_value=0 是占位。
bit_accuracy 不是总体攻击成功率。

实际加载路径通过旁路记录 Diffusers 0.31.0 的 DiffusionPipeline.download 返回值核对。其 from_pretrained 在 pipeline_utils.py:719–743 把此返回值作为 cached_folder 使用；包装保持参数和返回值原样。两个实际 snapshot 与冻结配置一致：
- stabilityai/stable-diffusion-xl-base-1.0：
  /data0/liyanlei/watermark_research/cache/huggingface/hub/models--stabilityai--stable-diffusion-xl-base-1.0/snapshots/462165984030d82259a11f4367a4eed129e94a7b
- Manojb/stable-diffusion-2-1-base：
  /data0/liyanlei/watermark_research/cache/huggingface/hub/models--Manojb--stable-diffusion-2-1-base/snapshots/0094d483a120f3f33dafbd187ea4aa60d10de75c

stderr 保留官方 safety_checker/scheduler 字段警告和离线 Hub 提示；最终从固定缓存正常加载。完整 stdout/stderr、退出码、commands.json、command.sh 与 config.json 均留存。

## 捕获位置与算法保持

官方来源：[run_reprompting.py:109–117](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L109-L117) 从 get_wm_latents 获得 wm_zT 并传入目标生成。包装检查这是同一个对象，再保存 CPU 副本。
参考验证 step=-1 位于 [run_reprompting.py:124–137](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L124-L137)，攻击验证 step=1 位于 [179–192](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L179-L192)。
两次恢复噪声均截取自 [utils/imprint_utils.py:338–343](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/imprint_utils.py#L338-L343) 已有目标反演的返回字典。

本次调用计数：{"sampling": 1, "target_generate": 1, "proxy_generate": 1, "target_invert": 2, "proxy_invert": 1, "validate": 2}。
没有增加生成、反演或水印检测调用，也没有分数驱动的候选选择/重试。
捕获使用 detach().to(cpu,copy=True)，不修改、移动或替换原始张量；原 dtype 保持 float32。
source_provenance.json 保存源文件哈希、完整 commit 和空 upstream diff；instrumentation.diff 包含新增包装/运行/测试代码的完整差异。
冻结 config.json 的 SHA256 为 `2656f195b3d22a15115635767c12b0bade693d19518c606d35c3d9ff27a449fb`，运行前后代码哈希一致。

## 三个实际张量

均为非 pickle NPY、shape=[1,4,64,64]、float32，位于 RUN_DIR/evaluator_only。
保存后 CPU 重读核对 shape/dtype/逐元素数值一致；独立诊断再核对文件哈希与有限性。

| 张量 | SHA256 | 关联 step |
|---|---|---:|
| target_original_wm_zT | 5faf9fe454f30f87980dddaf163e649fd556f5f17570e7973cf1ed28dc654ebc | -1 |
| target_inverted_reference_zT | cc4a878185ebe7e186d554c6ef08e82d14115c40a45079d791d51b9cc20fec80 | -1 |
| target_inverted_forged_zT | 71cb73613dd3ef5ed562e62e8a4ad2af3ace2483c0adf58e7e948366c7dce30a | 1 |

清单 `/data0/liyanlei/watermark_research/runs/04_reprompt_latent_diag_seed1_20261013T025322Z/evaluator_only/tensor_manifest.json` 逐张量保存路径、形状、dtype、源码捕获位置、角色、reference_id/candidate_id、配置哈希和图像哈希。
验证前读取 PIL 像素副本，validate 返回后与其原流程保存的 PNG 解码像素逐元素比较，两个 step 均一致。
参考图 SHA256：`40fb928b1ca645455711d2ab3b538ea5704b18c4f892ba720610cc54d1ee8ac1`。
攻击图 SHA256：`3e824454a9c6c89c395e94a45fd727825120a7095f2a77de3ec41f91f29edb7d`。

本次两张图片与阶段 02 的文件哈希均相同：{'reference': True, 'forged': True}。
这是新运行的输出一致性记录，不表示恢复了阶段 02 历史张量，也不能代替完整记录等价实验。

## 独立 CPU 余弦诊断

实现名：independent_global_cosine_diagnostic。
依据：[arXiv:2606.29807v1 Definition 4.5 与 Remark 4.7](https://arxiv.org/html/2606.29807v1#S4.SS3.SSS2)。
公式 dot(z,zhat)/(norm(z)*norm(zhat))。输入同形状、batch=1；每样本展平全部 C/H/W；
不中心化、不逐通道平均、不重采样，仅在 CPU 计算时转 float64；零范数、非有限、形状错误均报错，不加 epsilon。
候选 PNG 已保存并写入 candidate_frozen.json 后，模型子进程退出，独立 CUDA_VISIBLE_DEVICES="" 进程才读取张量计算：

| 指标 | 实际数值 |
|---|---:|
| gcos_reference | 0.8201082797320761 |
| gcos_forged | 0.3506198907446562 |
| reference − forged | 0.4694883889874199 |

分数未参与攻击计算或选择。没有设置几何阈值，没有几何接受/拒绝结论，也未实现 L-SPD 或融合规则。

## 测试、完整性与限制

CPU mock 测试通过：调用次数保持、原返回对象保持、输入未改变、Python/NumPy/Torch CPU 随机状态未推进，张量往返及 PNG 绑定正确；
余弦测试覆盖同向=1、反向=-1、正交=0、正比例缩放不变以及零范数、NaN、Inf、形状/batch错误拒绝。
构造非有限测试输入时产生一条 NumPy RuntimeWarning，测试按预期拒绝该输入，退出码0；原始日志保留。
这些测试与源码审查不等于有记录/无记录的完整数值等价实验；未做该等价实验。
与作者缺失几何函数的逐项数值等价性尚未验证；本结果不是完整官方几何检测复现，不证明总体可分性、总体攻击成功率或几何防护绕过。

目标张量、原始 CSV、实际模型加载记录和评分均位于 evaluator_only；没有把它们加入攻击输入清单。
运行仍在官方单进程框架内，目录命名、文件哈希不能证明进程/权限隔离。
已有 54 个受保护文件哈希均未改变，两个上游工作区干净。
报告生成前新增文件合计 1209881 字节，报告完成后另作预算终检，要求低于 1 GiB。
当前剩余阻塞：无影响本轮规定诊断完成的阻塞；完整官方几何规则的缺失仍是下一阶段边界。

阶段 04 完成并停止；没有追加样本、优化攻击或外部消息。


---

# 阶段 04 完成状态

来源：[reports/04_latent_diag_20261013T025322Z/04_status.json](../reports/04_latent_diag_20261013T025322Z/04_status.json)。

```json
{
  "stage": "04",
  "status": "completed",
  "run_dir": "/data0/liyanlei/watermark_research/runs/04_reprompt_latent_diag_seed1_20261013T025322Z",
  "upstream_commit": "ca68950cd7b53b8438a49580f134b2a0db28d778",
  "recording_code_path": "/data0/liyanlei/watermark_research/scripts/04_latent_diag_20261013T024856Z/run_recorded.py",
  "recording_code_sha256": "143107fa006698a9e0063ca1576764c830a7bc6d22d8d0c76c057b66a9e9f877",
  "recording_changes": [
    "原官方入口通过 runpy 原样执行；项目自有包装记录真实采样对象与目标生成输入的同一性",
    "在既有两次 validate 的目标反演返回处保存独立 CPU float32 NPY 副本",
    "核对被验证 PIL 与原流程保存 PNG 的像素及哈希；旁路记录实际模型缓存路径",
    "候选哈希冻结后由独立 CPU 进程计算 float64 全局余弦"
  ],
  "gpu_uuid": "GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da",
  "gpu_physical_index": 3,
  "model_snapshots": {
    "stabilityai/stable-diffusion-xl-base-1.0": "/data0/liyanlei/watermark_research/cache/huggingface/hub/models--stabilityai--stable-diffusion-xl-base-1.0/snapshots/462165984030d82259a11f4367a4eed129e94a7b",
    "Manojb/stable-diffusion-2-1-base": "/data0/liyanlei/watermark_research/cache/huggingface/hub/models--Manojb--stable-diffusion-2-1-base/snapshots/0094d483a120f3f33dafbd187ea4aa60d10de75c"
  },
  "execution_ok": true,
  "reference_detected": true,
  "forged_detected": true,
  "reference_bit_accuracy": 1.0,
  "forged_bit_accuracy": 0.953125,
  "tensor_capture_complete": true,
  "tensor_manifest_path": "/data0/liyanlei/watermark_research/runs/04_reprompt_latent_diag_seed1_20261013T025322Z/evaluator_only/tensor_manifest.json",
  "image_tensor_binding_verified": true,
  "cpu_metric_tests_passed": true,
  "gcos_reference": 0.8201082797320761,
  "gcos_forged": 0.3506198907446562,
  "gcos_gap_reference_minus_forged": 0.4694883889874199,
  "geometry_threshold": null,
  "geometry_accepted": null,
  "full_official_geometry_evaluation_completed": false,
  "instrumentation_equivalence_status": "源码检查与 mock/CPU 测试通过；未完成有记录/无记录的完整数值等价实验",
  "wall_time_seconds": 73.18118523410521,
  "sampled_peak_gpu_memory_mib": 16632,
  "blockers": [],
  "formal_model_runs_started": 1,
  "model_exit_code": 0,
  "diagnostic_name": "independent_global_cosine_diagnostic",
  "stage02_image_hashes_equal": {
    "reference": true,
    "forged": true
  }
}
```

---

# 阶段 05 原始要求

来源：[prompts/stage05_request.txt](../prompts/stage05_request.txt)。

```text
你是本项目的科研工程助手。

本轮只执行：
“阶段 05：固定提示词下的八种子攻击基线诊断”。

研究主线：
扩散模型语义水印的黑盒伪造攻击。

本轮目的：
检查官方 Reprompting 在固定模型、固定提示词对下，
是否反复出现“原水印检测通过，但攻击图全局余弦
低于参考图”的现象。

这是一组开发性小规模实验，不是新攻击方法，
不是完整官方几何验证，不是最终独立测试集。

不训练，不优化攻击，不搜索参数，不校准检测阈值，
不实现 L-SPD，不下载新模型，不安装或升级依赖。

一、读取状态与保护已有结果

使用已有 SSH 认证连接：
liyanlei@172.18.185.249

项目根：
/data0/liyanlei/watermark_research

不得保存或输出密码、令牌、私钥。
不得关闭 SSH 主机密钥检查。
连接或路径失败时停止，不扫描其他主机或目录。

先阅读 AGENTS.md 和阶段 04 的报告、状态文件。

阶段 04 RUN_DIR：
runs/04_reprompt_latent_diag_seed1_20261013T025322Z

阶段 04 记录入口：
scripts/04_latent_diag_20261013T024856Z/run_recorded.py

预期 SHA256：
143107fa006698a9e0063ca1576764c830a7bc6d22d8d0c76c057b66a9e9f877

检查本阶段是否已有执行目录或未结束进程。
已有完成结果时只返回已有结果。
已有运行或中断记录时报告状态，不重复启动整组实验。

不得覆盖阶段 01—04 的文件。
保持两个 third_party 仓库不变。
不要重新做全仓库审计。

二、环境、模型与 GPU

使用已有环境：
/data0/liyanlei/watermark_research/envs/semantic_forgery_py310

官方攻击仓库：
third_party/semantic-forgery

固定 commit：
ca68950cd7b53b8438a49580f134b2a0db28d778

核对 commit 和工作区状态。
不符时停止，不 reset、不自动更新。

沿用阶段 04 已验证的实际模型 snapshot：

目标：
stabilityai/stable-diffusion-xl-base-1.0
revision=462165984030d82259a11f4367a4eed129e94a7b

代理：
Manojb/stable-diffusion-2-1-base
revision=0094d483a120f3f33dafbd187ea4aa60d10de75c

使用项目缓存及离线模式。
记录实际加载路径；缺少缓存就报告，不联网补下载。

本轮只使用物理 GPU 7：
GPU-9644fb82-cb6f-7311-8017-eaee41409bb7

每个正式子进程启动前，重新核对物理编号、UUID、
型号、占用和计算进程。
GPU 7 忙、身份不符或授权存在冲突时停止，
不自动换 GPU 3、5 或其他设备。

在导入可能初始化 CUDA 的模块前设置：
CUDA_DEVICE_ORDER=PCI_BUS_ID
CUDA_VISIBLE_DEVICES=GPU-9644fb82-cb6f-7311-8017-eaee41409bb7

程序内使用 cuda:0。
串行执行，不用 DDP，不多卡切分，不并行抢占显存。
不终止他人进程。

CPU 检查和事后统计进程设置：
CUDA_VISIBLE_DEVICES=""

本轮新增文件预算上限 2 GiB；
开始前工作盘至少保留 200 GiB。
整组正式实验墙钟预算为 30 分钟，
单个模型进程超时上限为 5 分钟。
超时或资源异常时，仅结束明确属于本轮的进程并报告。
不要删除其他项目文件。

三、实验开始前冻结协议

创建唯一目录，例如：
runs/05_reprompt_seed_pilot_<UTC时间戳>/

预先保存 pilot_protocol.json 和其 SHA256。
必须在第一个正式模型进程启动之前完成。

明确：
planned_seeds = [2,3,4,5,6,7,8,9]
planned_runs = 8
samples_per_seed = 1
prompt_pairs = 1
data_role = development_pilot

阶段 02、04 的 seed=1 不并入本阶段八种子的统计。
它们对应同一组已观察输出，只作为历史背景。

固定所有其他条件：
wm_type=GS
resolution=512
num_inference_steps_target=50
num_inference_steps_attacker=50
guidance_scale_target=7.5
guidance_scale_attacker=7.5
scheduler_target=DDIM
scheduler_attacker=DDIM
resample=false
float32

反演保持官方空提示词、guidance=1.0。
不更换 VAE、scheduler、图像数据流或精度。

GS 保持既有设置：
l=1
message_width_in_bytes=32
num_replications=64
offset=0

参考提示词：
A studio photograph of a yellow ceramic teapot on a wooden table.

攻击提示词：
A red sailboat on a calm blue lake, watercolor illustration.

原 GS 判定保持：
bit_accuracy > 0.70703125

种子使用官方 set_random_seed 路径，
不另加随机调用或改变其内部偏移规则。

说明这些运行共用基础水印设置：
不同种子不等于不同用户、不同消息或不同密钥。
本轮不修改或增加密钥管理机制。

四、复用阶段 04 记录代码

优先直接复用已验证的记录入口。

只检查它是否能够通过参数正确设置：
seed、输出目录、样本 ID。

若存在固定为 seed=1 或旧 RUN_DIR 的硬编码，
可以在项目自有目录建立参数化副本，
仅修改上述实验管理项，保留完整 diff 和来源哈希。

不得修改上游源码或重写攻击流程。
不得为了观察分数增加模型调用。

保留阶段 04 的记录位置和定义：
target_original_wm_zT
target_inverted_reference_zT
target_inverted_forged_zT

原始目标张量必须来自本次实际生成输入；
两份恢复张量来自本次既有的 validate 调用。

继续保存非 pickle、float32 的独立 CPU 副本，
核对图像、张量、配置与样本 ID 的绑定关系。

仅在必要时运行轻量 CPU/mock 测试，
检查参数传递、独立输出目录、调用次数和返回值不变。
不为测试额外启动 GPU 样例。

正式实验前冻结记录代码哈希。
整组运行中不得根据观察结果改代码。

五、执行八个预定种子

每个种子一个独立模型进程和唯一子目录。
按 2 到 9 的固定顺序串行执行。

每个种子仅允许一次正式模型运行。
保存命令、配置、开始/结束时间、
stdout/stderr、真实退出码和每两秒 GPU 监控。

运行完成后：
- 保留原始 metrics.csv；
- 保存原始参考图、攻击图及 SHA256；
- 保存三个实际张量及绑定清单；
- 候选图哈希冻结、模型进程退出后，
  才由独立 CPU 进程计算余弦。

原水印检测失败、参考图检测失败、
攻击图余弦较高或差值为负，
都是需要保留的科学观察：
不换 seed、不换提示词、不补抽、不选图。
程序正常完成时，继续预定的下一个种子。

但出现 OOM、超时、缓存/代码错误、
张量错绑、文件覆盖风险或 GPU 被占用等工程异常时，
停止整组运行，保留已完成部分。
本轮不自动修复后重跑失败种子。

不要将 reference_detected=false 的样本隐藏或删除。
保留其原始数据，并标记该样本参考有效性未建立。

六、余弦定义与单样本输出

沿用阶段 04 的：
independent_global_cosine_diagnostic

每样本展平全部 C/H/W；
CPU float64 计算；
不中心化、不逐通道平均、不添加 epsilon；
拒绝零范数、非有限值和形状不符。

计算：
gcos_reference
gcos_forged
gcos_gap = gcos_reference - gcos_forged

检查公式和有效输入，不预设 gap 必须为正。
不修改公式来追求与阶段 04 相近的结果。

每个种子的汇总至少包含：
seed
run_dir
execution_ok
reference_detected
forged_detected
reference_bit_accuracy
forged_bit_accuracy
tensor_capture_complete
image_tensor_binding_verified
gcos_reference
gcos_forged
gcos_gap
reference_sha256
forged_sha256
original_latent_sha256
wall_time_seconds
sampled_peak_gpu_memory_mib
failure_reason

缺失结果写 null，不把未知写成 false。

检查不同种子之间是否出现重复图像或原始噪声哈希。
发现重复时如实标记，不重新生成来消除重复，
不直接宣称样本独立。

七、只做描述性汇总

先完整列出八个预定种子的逐样本结果，
包含失败或未执行记录。

分别报告：
- 计划数；
- 已启动数；
- 正常完成数；
- 张量与绑定有效的成对样本数；
- 参考图通过原 GS 的数量；
- 参考有效样本中攻击图通过原 GS 的数量；
- 工程失败、参考无效、未执行的数量。

数量必须写明分母。
不把单图 bit_accuracy 当作攻击成功率，
不把八样本比例描述为总体可靠成功率。

对有效成对结果，以及其中“参考 GS 通过”的子集，
分别报告三个余弦量的：
均值、中位数、最小值、最大值；
样本数至少为 2 时才计算样本标准差。

报告 gap > 0、=0、<0 的样本数量。
这只是数值方向统计，不是几何检测阈值。

本轮不计算或宣称：
几何通过/拒绝；
完整防护绕过率；
AUC/ROC；
总体误报率或误拒率；
统计显著性；
跨提示词、跨密钥或跨模型泛化。

geometry_threshold = null
geometry_accepted = null
full_official_geometry_evaluation_completed = false

八个种子不是参数搜索。
不得把最高分的种子选为下一轮唯一展示样例。

八、信息边界与研究解释

攻击计算不读取目标原始噪声、目标恢复噪声、
目标分数或其他评估端材料。

目标张量、CSV、诊断结果和完整目标配置
保留在 evaluator_only，
不加入攻击输入清单。

继续明确：
当前基于官方共享进程的复现框架；
旁路记录和独立事后统计，不等于权限级隔离；
“本轮不根据目标分数选图”
不等于“整个研究从未接触目标信息”。

这批结果用于开发诊断。
一旦用于后续方法选择，不得再作为未见过的最终测试集。

不从正差值推断完整防护一定有效；
不从某个负差值推断新攻击已经成功；
不从公开代码缺项推断论文存在已证实漏洞。

九、交付与停止

在唯一的新报告目录保存：
05_report.md
05_status.json
per_seed_metrics.csv
summary.json

05_status.json 至少包含：
stage
data_role
experiment_root
planned_seeds
planned_runs
started_runs
completed_runs
valid_tensor_pairs
reference_valid_pairs
joint_reference_and_forged_wm_pass_count
failed_runs
unstarted_seeds
gpu_uuid
upstream_commit
recording_code_sha256
protocol_sha256
per_seed_metrics_path
summary_path
duplicate_artifacts
geometry_threshold
full_official_geometry_evaluation_completed
total_wall_time_seconds
blockers

报告明确分成：
实际完成；
观察到的结果；
本试验不能回答的问题。

最后只返回：
1. 逐种子结果表；
2. 三个余弦量的描述性汇总；
3. 原 GS 接受情况与准确分母；
4. 工程问题和实验限制；
5. 05_status.json 全文。

不追加种子，不增加提示词对，
不开始新的优化攻击，不校准防御。
完成后停止。
```

---

# 阶段 05 GPU 3 修订

来源：[prompts/stage05_gpu3_amendment.txt](../prompts/stage05_gpu3_amendment.txt)。

```text
阶段 05 设备授权修订】

用户明确要求：本轮使用物理 GPU 3。
本指令替代上一份阶段 05 提示词中“只使用 GPU 7”的规定。
其他实验条件、样本数、预算、停止条件与交付要求全部不变。

一、唯一允许的 GPU

物理编号：3
预期 UUID：
GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da

每个 GPU 子进程启动前，使用 nvidia-smi 重新核对：
物理编号、UUID、型号、显存占用、利用率及计算进程。

身份不匹配、存在其他计算任务或占用情况不明确时停止并报告。
不抢占、不终止他人进程，不自动换 GPU 5、7 或其他卡。

二、设备限制

在导入可能初始化 CUDA 的模块前设置：

export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES=GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da

程序内只使用单张可见卡 cuda:0，不使用 cuda:3。
CPU 单元测试及事后统计进程仍设置：
CUDA_VISIBLE_DEVICES=""

八个种子串行运行，不增加并发。

三、同步修订本轮配置

同步更新阶段 05 的启动配置、GPU 预检查、
监控对象及状态报告中的物理编号与 UUID。

若 AGENTS.md 仍保留旧设备限制，
追加“用户本轮明确授权阶段 05 仅使用 GPU 3”的记录，
不删除其他约束，不改写历史实验报告。

正式运行尚未启动时：
保留已有配置版本，更新本轮设备字段，
在启动前重新冻结协议与配置哈希。
不修改阶段 04 记录代码来伪造原有哈希。

若阶段 05 已经启动：
不要重复启动、强行迁移或自动重跑；
先报告当前进程、实际设备和已完成种子，
保留真实记录，等待下一步指令。

四、实验范围保持不变

仍只执行 seed=[2,3,4,5,6,7,8,9]，
每个种子一次，使用原定提示词、模型、精度与参数。
不追加样本，不搜索参数，不调整阈值。

完成后按原阶段 05 要求交付报告并停止。
```

---

# 阶段 05 报告

来源：[reports/05_reprompt_seed_pilot_20261013T041832Z/05_report.md](../reports/05_reprompt_seed_pilot_20261013T041832Z/05_report.md)。

# 阶段 05：固定提示词下的八种子攻击基线诊断

## 实际完成

实验根：`/data0/liyanlei/watermark_research/runs/05_reprompt_seed_pilot_20261013T041832Z`。数据角色：development_pilot。
计划8；启动 8/8；模型正常完成 8/8；张量/绑定和分数有效 8/8。
工程失败 0/8；参考无效 0/8；未执行 0/8。
物理 GPU 3，UUID GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da；单可见卡 cuda:0；每个进程启动前复查，逐种子串行。
整组正式执行及逐样本CPU诊断墙钟 619.766 秒；上限1800秒，每模型进程上限300秒。
协议 SHA256：`6f038640c41afddd8545b7747da20668daed72ba90f87a32a4f649ffdf3c1629`。入口 SHA256：`e12eb2ab2db7afec9d29e6ee07bf72c2f44bad140ea36ca9b994bd195943e3cd`。
来源阶段04入口 SHA256：`143107fa006698a9e0063ca1576764c830a7bc6d22d8d0c76c057b66a9e9f877`，原文件未改。原官方 commit：`ca68950cd7b53b8438a49580f134b2a0db28d778`。
记录副本只修改配置位置和样本 ID；seed/输出目录继续用原配置参数。来源哈希及完整逐文件 diff 在 experiment_root/evaluator_only。
diagnostic.py 与阶段04逐字节相同。CPU mock/参数测试检查了种子2–9的参数绑定、16个唯一ID、8个独立输出目录、调用次数与返回对象。
固定提示词：黄色陶瓷茶壶摄影图 → 蓝色湖面红帆船水彩图；完整文字、模型snapshot、GS参数、精度、步数、CFG与调度器在冻结协议中。
GS阈值严格 >0.70703125；图像和原始CSV保留，质量指标 -1 为未计算占位。实际加载路径逐进程记录并核对固定snapshot。
三个 float32 NPY 张量来自真实目标生成输入和既有两次目标validate反演；图像像素、哈希、配置哈希和ID绑定逐样本核对。
配置、张量、CSV及目标记录位于每种子 evaluator_only；该命名不表示已经实现权限隔离。

## 观察到的结果

| seed | 执行 | 参考BA | 攻击BA | 参考GS | 攻击GS | Gcos参考 | Gcos攻击 | gap |
|---|---|---|---|---|---|---|---|---|
| 2 | True | 1.0 | 0.96875 | True | True | 0.8407059236857535 | 0.37610987595360995 | 0.4645960477321435 |
| 3 | True | 1.0 | 0.9296875 | True | True | 0.7921230332917748 | 0.29597624797547384 | 0.49614678531630096 |
| 4 | True | 1.0 | 0.9375 | True | True | 0.8475045383889511 | 0.27749777082810034 | 0.5700067675608508 |
| 5 | True | 1.0 | 0.9765625 | True | True | 0.8240551802862213 | 0.34653140482642636 | 0.4775237754597949 |
| 6 | True | 1.0 | 0.98828125 | True | True | 0.8450810426962856 | 0.4025877704210808 | 0.4424932722752048 |
| 7 | True | 1.0 | 0.98046875 | True | True | 0.8619446787598377 | 0.4112479326909924 | 0.4506967460688453 |
| 8 | True | 1.0 | 0.94140625 | True | True | 0.7392502488155508 | 0.3126645414631086 | 0.42658570735244217 |
| 9 | True | 1.0 | 0.96484375 | True | True | 0.7600974480847823 | 0.3608544840807366 | 0.3992429640040457 |

参考 GS 通过 8/8；参考有效成对样本中攻击 GS 通过 8/8。
上述比例只描述这批固定提示词开发样本，bit_accuracy 是单图位匹配比例。

| 子集 | 指标 | n | 均值 | 中位数 | 最小值 | 最大值 | 样本标准差 |
|---|---|---|---|---|---|---|---|
| 全部有效配对 | gcos_reference | 8 | 0.8138452617511447 | 0.8323805519859874 | 0.7392502488155508 | 0.8619446787598377 | 0.044996842850652294 |
| 全部有效配对 | gcos_forged | 8 | 0.3479337535299411 | 0.35369294445358146 | 0.27749777082810034 | 0.4112479326909924 | 0.04908197216653044 |
| 全部有效配对 | gcos_gap | 8 | 0.46591150822120353 | 0.4576463969004944 | 0.3992429640040457 | 0.5700067675608508 | 0.051627354804688545 |

全部有效配对 gap方向数量：{"positive": 8, "zero": 0, "negative": 0, "denominator": 8}

| 子集 | 指标 | n | 均值 | 中位数 | 最小值 | 最大值 | 样本标准差 |
|---|---|---|---|---|---|---|---|
| 参考GS通过子集 | gcos_reference | 8 | 0.8138452617511447 | 0.8323805519859874 | 0.7392502488155508 | 0.8619446787598377 | 0.044996842850652294 |
| 参考GS通过子集 | gcos_forged | 8 | 0.3479337535299411 | 0.35369294445358146 | 0.27749777082810034 | 0.4112479326909924 | 0.04908197216653044 |
| 参考GS通过子集 | gcos_gap | 8 | 0.46591150822120353 | 0.4576463969004944 | 0.3992429640040457 | 0.5700067675608508 | 0.051627354804688545 |

参考GS通过子集 gap方向数量：{"positive": 8, "zero": 0, "negative": 0, "denominator": 8}

重复哈希检查：{"reference_sha256": [], "forged_sha256": [], "original_latent_sha256": [], "all_images": []}

## 本试验不能回答的问题

这是开发性小规模诊断；种子1的阶段02/04输出未计入统计。种子改变不等于用户、消息或密钥改变，基础WM设置及固定表共用。
不同种子或未见哈希重复不证明统计独立；不能据此宣称跨提示词、跨密钥、跨模型泛化。
余弦为独立CPU float64展平诊断；没有L-SPD、融合或几何阈值，也没有完整几何接受/拒绝、绕过率、ROC/AUC、误报率或显著性结论。
正gap只是数值方向，不证明完整防护有效；负gap也不自动证明新攻击成功。作者函数逐项等价性仍未验证。
当前是官方共享进程框架。旁路记录、事后CPU诊断与本轮不依分数选图，不等于权限隔离或整个研究从未接触目标信息。
一旦这批结果用于后续方法选择，就不能再称为未见的最终独立测试集；不挑选最高分种子作为唯一后续展示。
源码检查和mock测试不替代完整有记录/无记录数值等价实验。

工程记录：[]
原日志保留离线缓存/官方参数警告；若有异常，逐种子 failure_reason 及 engineering_failure.json 保留真实证据。
阶段04受保护文件 57 个哈希未变；两个上游工作区干净。AGENTS仅追加本轮授权说明，原字节已备份。
阶段05八个预定种子全部完成，正式实验已停止。


---

# 阶段 05 状态

来源：[reports/05_reprompt_seed_pilot_20261013T041832Z/05_status.json](../reports/05_reprompt_seed_pilot_20261013T041832Z/05_status.json)。

```json
{
  "stage": "05",
  "data_role": "development_pilot",
  "experiment_root": "/data0/liyanlei/watermark_research/runs/05_reprompt_seed_pilot_20261013T041832Z",
  "planned_seeds": [
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9
  ],
  "planned_runs": 8,
  "started_runs": 8,
  "completed_runs": 8,
  "valid_tensor_pairs": 8,
  "reference_valid_pairs": 8,
  "joint_reference_and_forged_wm_pass_count": 8,
  "failed_runs": 0,
  "unstarted_seeds": [],
  "gpu_uuid": "GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da",
  "gpu_physical_index": 3,
  "upstream_commit": "ca68950cd7b53b8438a49580f134b2a0db28d778",
  "recording_code_sha256": "e12eb2ab2db7afec9d29e6ee07bf72c2f44bad140ea36ca9b994bd195943e3cd",
  "protocol_sha256": "6f038640c41afddd8545b7747da20668daed72ba90f87a32a4f649ffdf3c1629",
  "per_seed_metrics_path": "/data0/liyanlei/watermark_research/reports/05_reprompt_seed_pilot_20261013T041832Z/per_seed_metrics.csv",
  "summary_path": "/data0/liyanlei/watermark_research/reports/05_reprompt_seed_pilot_20261013T041832Z/summary.json",
  "duplicate_artifacts": {
    "reference_sha256": [],
    "forged_sha256": [],
    "original_latent_sha256": [],
    "all_images": []
  },
  "geometry_threshold": null,
  "geometry_accepted": null,
  "full_official_geometry_evaluation_completed": false,
  "total_wall_time_seconds": 619.7655127081089,
  "blockers": []
}
```

---

# 阶段 05 完整描述统计

来源：[reports/05_reprompt_seed_pilot_20261013T041832Z/summary.json](../reports/05_reprompt_seed_pilot_20261013T041832Z/summary.json)。

```json
{
  "data_role": "development_pilot",
  "counts": {
    "planned": 8,
    "started": {
      "count": 8,
      "denominator": 8
    },
    "completed": {
      "count": 8,
      "denominator": 8
    },
    "valid_tensor_pairs": {
      "count": 8,
      "denominator": 8
    },
    "reference_wm_pass": {
      "count": 8,
      "denominator": 8
    },
    "reference_valid_pairs": {
      "count": 8,
      "denominator": 8
    },
    "forged_wm_pass_among_reference_valid": {
      "count": 8,
      "denominator": 8
    },
    "engineering_failed": {
      "count": 0,
      "denominator": 8
    },
    "reference_invalid": {
      "count": 0,
      "denominator": 8
    },
    "unstarted": {
      "count": 0,
      "denominator": 8
    }
  },
  "valid_pairs": {
    "n": 8,
    "gcos_reference": {
      "mean": 0.8138452617511447,
      "median": 0.8323805519859874,
      "min": 0.7392502488155508,
      "max": 0.8619446787598377,
      "sample_std": 0.044996842850652294
    },
    "gcos_forged": {
      "mean": 0.3479337535299411,
      "median": 0.35369294445358146,
      "min": 0.27749777082810034,
      "max": 0.4112479326909924,
      "sample_std": 0.04908197216653044
    },
    "gcos_gap": {
      "mean": 0.46591150822120353,
      "median": 0.4576463969004944,
      "min": 0.3992429640040457,
      "max": 0.5700067675608508,
      "sample_std": 0.051627354804688545
    },
    "gap_direction_counts": {
      "positive": 8,
      "zero": 0,
      "negative": 0,
      "denominator": 8
    }
  },
  "reference_gs_pass_subset": {
    "n": 8,
    "gcos_reference": {
      "mean": 0.8138452617511447,
      "median": 0.8323805519859874,
      "min": 0.7392502488155508,
      "max": 0.8619446787598377,
      "sample_std": 0.044996842850652294
    },
    "gcos_forged": {
      "mean": 0.3479337535299411,
      "median": 0.35369294445358146,
      "min": 0.27749777082810034,
      "max": 0.4112479326909924,
      "sample_std": 0.04908197216653044
    },
    "gcos_gap": {
      "mean": 0.46591150822120353,
      "median": 0.4576463969004944,
      "min": 0.3992429640040457,
      "max": 0.5700067675608508,
      "sample_std": 0.051627354804688545
    },
    "gap_direction_counts": {
      "positive": 8,
      "zero": 0,
      "negative": 0,
      "denominator": 8
    }
  },
  "duplicate_artifacts": {
    "reference_sha256": [],
    "forged_sha256": [],
    "original_latent_sha256": [],
    "all_images": []
  },
  "geometry_threshold": null,
  "geometry_accepted": null,
  "full_official_geometry_evaluation_completed": false
}
```
