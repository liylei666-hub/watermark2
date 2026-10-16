# AGENTS.md

## 本项目阶段性约束

- 远程项目根目录固定为 `/data0/liyanlei/watermark_research`；上游代码位于 `third_party/semantic-forgery`，保持上游工作区可追溯。
- 只允许使用 `nvidia-smi` 显示的物理 GPU 3、5 和 7。启动 GPU 程序前必须用核对过的 GPU UUID 设置 `CUDA_VISIBLE_DEVICES`；单卡暴露后程序内使用 `cuda:0`。不使用 DDP 或多卡切分。
- 不在脚本、配置、Git、报告或日志中保存密码、私钥内容、令牌或其他凭据。
- 不覆盖、清空或重置已有结果；不编造实验数据、运行成功状态或未检查过的环境信息。
- 攻击端与目标评估端在后续实验中保持隔离；不得因缺失依赖、模型或检测结果而替换模型或调整阈值制造成功外观。
- 每次实验必须记录配置、上游/本地代码版本、随机种子、设备 UUID、运行状态和阻塞原因。

本文件只规定项目约束，不授权训练、批量生成、长时间攻击或下载大型资源。


## 阶段 05 本轮设备授权

用户本轮明确授权阶段 05 仅使用物理 GPU 3（GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da）。每个 GPU 子进程启动前核对身份和占用；种子 2–9 串行执行。其余约束保持有效。


## Current research authority: 2026-10-16

Experiments are paused by the user for feasibility, novelty and literature review. Do not start new experiments until the user resumes them. Current research guidance is maintained in the authorized watermark2 repository.

For resumed first-round work, the user permits an idle physical GPU in [0,1,2,3,4,5,7]; GPU 6 is excluded. This supersedes earlier device scopes for future work. Verify index, UUID, model, memory, utilization and compute processes before each child. Bind the verified UUID before CUDA imports; use one visible device cuda:0 and serial execution. Budget: 7200 cumulative GPU-process seconds, 1200 per process, 10 GiB new files, no new model downloads. No first-round model processes have started at this update. Preserve prior results and usage; never terminate other users' processes.

Use only authorized local models/data. Network access is limited to public academic/official-source reads, authorized repository publishing, and authenticated access to this designated server. Do not scan networks, target third-party production services, bypass access control, disable SSH/TLS verification, or save credentials.
