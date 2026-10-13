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
