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
