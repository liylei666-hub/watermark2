# 研究进展统一口径（四分支对照）

编制：2026-10-30，仓库整理（分支 `chore/repo-cleanup-20261030`）。本文只汇总已有文档的说法，不新增实验、数值或科学结论。各分支说法互相冲突时，本文不做二选一，而是并列列出并注明证据来源（`分支@提交:路径`）。机器可读状态仍以各分支的 `project_state.json` 为准，本文没有改动它。

| 简称 | 分支 | 头提交 | 头提交时间 |
|---|---|---|---|
| **M** | `main` | `e457085` | 2026-10-26 01:55 +0800 |
| **R** | `research/stage27-recovery-20261019` | `e5c86c7` | 2026-10-26 01:51 +0800 |
| **IA** | `research/instance-authenticity` | `1837338` | 2026-10-09 13:44 +0800 |
| **W** | `workbuddy/exploration-pgsmf-mttgi-20261027` | `0d116bc` | 2026-10-29 20:11 +0800 |

## 1. 分支关系与各自的权威范围

| 分支 | 与 main 的 Git 关系 | 实际内容 | 分支自述的地位 |
|---|---|---|---|
| M | — | 阶段 01–27 的原始证据（runs/protocols/reports）在文件树内；阶段 28–31 与 100 对资产**不在树内**，只以固定提交 URL 指向 R@e5c86c7 | `M:project_state.json` `current_state_pointer.authority`：“Research branch contains verified current artifacts; main preserves separate historical evidence” |
| R | 共同祖先 `a68f38e`（阶段27调度提交）；M 领先 8 个提交（只更新文档指针），R 领先 22 个提交 | 阶段 28、29、30（hold）、31、31-LPIPS、PSNR 复核、confirmation100 v1/v1.1 的报告与 tools/ | M 的 README/GPT_CONTEXT/project_state 都把 R@e5c86c7 写成“当前研究提交” |
| IA | **是 M 的祖先**（M 领先 61 个提交，R 领先 0 个），但 M 的提交 `41f8758`（2026-10-13，“Archive semantic watermark forgery research stages 01-05”）整树替换了内容；两者只共有 `.gitattributes/.gitignore/AGENTS.md/README.md` 四个路径，内容也不同 | 另一条研究线：允许编辑策略下的实例真实性，围绕 SEAL/SemBind/CSI 展开；包括 `research/ configs/ legacy/ scripts/ tests/`（共 577 个文件） | M 上没有任何文档说明这条线已关闭或被取代（见冲突 C9） |
| W | M@e457085 之后加 2 个提交，只新增 `exploration/20261027_pgsmf_mttgi/` | PG-SMF（V1/V2）与 MT-TGI（V3/V4）的探索记录，结论为负结果；原始产物不在 Git 中 | `W:…/WORKBUDDY.md` 与提交 `0d116bc`：“Not merged, and not planned to be.” 不建议作为正式引用来源 |

## 2. 统一阶段时间线

数值照抄来源文件，不做重算。“状态”沿用来源文件的措辞。

| 阶段 | 状态 | 关键结果（原文数值） | 来源 |
|---|---|---|---|
| 01–05 | 完成 | 环境/代码审计；官方 GS Reprompting 复现；阶段05八个种子原 GS 均通过，参考/攻击余弦均值 0.813845 / 0.347934（开发数据，development_pilot） | `M:README.md`、`M:docs/PROJECT_STATE.md`、`M:reports/05_*` |
| 06 | 完成（CPU） | 分离消息解码、坐标符号与幅值；几何接受与阈值为 null | `M:reports/06_cpu_diagnostics/report.md` |
| 07 | 完成 | 6 次运行；同/换提示词候选余弦 0.290478 / 0.306216；原 GS 各 3/3 | `M:reports/07_prompt_control/report.md` |
| 08 | 完成 | 目标自身往返在六对上均高于代理往返 | `M:reports/08_target_roundtrip/report.md` |
| 09 | **未完成** | 在 seed103 设备预检处停止；禁止重试或补样 | `M:reports/09_vae_roundtrip/report.md`、`M:project_state.json` `incomplete_stages` |
| 10 | 完成（含 2 次失败） | r1 梯度记录器与 reentrant checkpoint 不兼容（exit 1）；r2 梯度逐位检查失败（exit 1）；r3 完成 10 步，PNG 保留 91.52% 内部改善 | `M:reports/10_imprint_delivery/report.md` |
| 11–12 | 完成 | 梯度余弦 0.731/0.676；有限步长残差集中在 VAE decode/clamp/encode 组合 | `M:reports/11_*`、`M:reports/12_*` |
| 13 | 完成（含门槛失败） | 冻结参数等价检查没有通过预定的逐位门槛（保留，不重试）；原参数状态跨进程一致 | `M:reports/13_vae_core/report.md` |
| 14–15 | 完成 | Imprint 参考+10 步 375.33 s；Jain 参考+100 步 83.91 s；15 的首版协议因阶段标签更正从未启动 | `M:reports/14_*`、`M:reports/15_imprint_timing/report.md`、`M:protocols/15_imprint_timing_r2.json` |
| 16 | 完成（CPU） | 35 个 CPU 用例通过，冻结阶段17 | `M:reports/16_cover_preparation/` |
| 17 | 完成 | 约 376 s 核心预算：Imprint 普通 GS 通过 2/3，Jain 0/3 | `M:reports/17_cover_pilot/report.md` |
| 18–19 | 完成，已关闭 | 两对出现代理/目标排序反转；排序变化依赖任务与指标 | `M:reports/18_*`、`M:reports/19_*` |
| 20–22 | 完成 | 20 为 CPU 准备；21 中 20 个候选的普通 GS 全部未通过，8 项中心差分均超容差；22 为解码契约 | `M:reports/20_*`–`22_*` |
| 23–26 | 完成 | 23 主端点为负；24 平均降低 0.2991 个百分点位错误；25 消息准确率 0.937012→0.882812，7/8 下降；26 为静态目标审查 | `M:reports/23_*`–`26_*` |
| 27 | 完成，固定交付候选关闭 | 原生 Imprint / delivery / Jain 普通 GS 通过 8/12 / 6/12 / 3/12；Jain 任务2在加载模型前失败，保留不重跑 | `M:reports/27_method_resume_20261019T173017Z/report.md` |
| 28 | 完成，固定候选关闭 | 15 个工作进程，5003.48 s；三组均 4/4 普通 GS | `R:project_state.json` `stage28`；`R:reports/29_reconciliation/report.md` |
| 29 | 完成，固定候选关闭 | 16 对；pixel50/pixel10 通过 10/16 与 9/16；36 个工作进程，25126.69 s；源码提交 `4cbed8b` 的祖先关系**未核实**（`git_ancestry_verified: false`） | `R:project_state.json` `stage29`；`R:reports/29_reconciliation/report.md` |
| 30 | **hold** | 交叉诊断提案；启动模型数 0 | `R:project_state.json` `held_stage30_design`；`M:project_state.json` `pending_design.stage30` |
| 31 | 完成（仅校准） | 4 对共享身份；151 步主端点平均 BA 0.919921875，GS 4/4，PSNR 23.751050 dB；6 个模型进程，0 失败；**不是**完整论文复现 | `M:project_state.json` `stage31`；`R:reports/31_native_calibration/report.md` |
| 31-LPIPS | 事后 CPU 补算 | 151 步均值 0.1979204248636961，不是预注册主指标 | `M:project_state.json` `current_state_pointer`；`R:reports/31_native_calibration_lpips_20261025/report.md` |
| confirmation100 v1.1 | 资产就绪，模型未启动 | 100 张载体 / 100 条唯一 caption / 100 个配对；manifest sha256 `a41bbad8…8220`；图像再分发许可未确认（`image_redistribution_cleared: false`） | `M:project_state.json` `confirmation100_assets`；`R:reports/confirmation100_assets_v11_completed/report.md` |
| W：PG-SMF / MT-TGI | 探索，负结果，n=2 | 50 步 BA：native 0.8516，V1 0.8535，V2 0.8027，V3 0.8418，V4 0.8340；四个变体都没有严格优于 native | `W:exploration/20261027_pgsmf_mttgi/README.md`、`…/reports/pg_smf_pilot_report_20261027.md` |
| IA：实例真实性 | 暂停扩展；G0 阻塞 | 12 源批次的 90% 源组规则只能选出退化阈值 0；官方 SEAL 端到端基线未执行，执行预算 0 | `IA:README.md`、`IA:research/official_seal_baseline_route.md` |

## 3. 当前状态与下一项（各处一致）

> 审阅完整 corrected native Imprint 100 对基线协议、独立私有 GS 材料及实际资源预算；100 对模型实验尚未启动。Stage30、八攻击对照和 Jain 原设置保持 hold。

这句话在 `M:README.md`、`M:GPT_CONTEXT.md`、`M:docs/RESEARCH_PLAN.md`、`M:project_state.json`（`next_action`、`next_step_proposal`）中逐字一致。R 的同名字段多了一句“资产按冻结清单使用”。M 的 `current_task_scope` 为 `publication_and_protocol_planning_only_no_model_launch`，`allowed_gpu_physical_indices` 为 `[]`，也就是说当前不授权任何 GPU 作业。

## 4. 冲突与不一致（并列给出，不做裁决）

**C1 累计进程数与 GPU 进程秒**
- M 的账本：105 个进程，22027.065950 s，4 个非零退出，截至 2026-10-19T21:23Z。来源：`M:reports/research_execution_ledger.json`；`M:GPT_CONTEXT.md` 写的“阶段27历史账本累计105进程”与此一致。
- M 的 project_state：`current_round_model_processes_started` = 105，但 `current_round_usage_scope` 注明“do not treat as reconciled current totals”。
- R 的 project_state：156 个进程，52157.23254724406 s。差值 51 / 30130.17 s 正好等于阶段28与29之和（15+36 / 5003.48+25126.69），见 `R:project_state.json` `usage_note`。
- R 的账本：60 个进程，7251.676560431719 s，3 个非零退出，截至 2026-10-18T05:19Z。这与 `M:project_state.json` `stage26.cumulative_model_processes` 相同，说明 R 的账本文件是阶段27之前的快照，R 自身的 project_state 与账本也不一致。
- 阶段31 的 6 个进程（模型进程墙钟 23417.041 s，见 R 的阶段31报告）既不在 105 里，也不在 156 里。这是本文按字段算术得出的推断，没有找到原文确认。

**C2 `data_role`**：M 为 `development_pilot`；R 为 `frozen_baseline_confirmation_assets_with_finite_historical_exclusion_audit`。来源：两边的 `project_state.json`。两者可能各自指不同的数据集（阶段05开发数据 vs 100 对资产），但字段本身没有说明适用范围。

**C3 `paper_priority`**
- M：`corrected_native_imprint_full100_baseline_confirmation`（状态 `protocol_and_resources_review`）；同时保留 `historical_paper_priority_stage27` = `coarse_to_full_inversion_optimization_hypothesis`。
- R：仍为 `delivery_path_imprint`（`runtime_protocol_frozen: true`），但 R 的阶段27记录已经关闭了 delivery 候选，属于 R 内部的过时字段。
- 来源：两边的 `project_state.json`。

**C4 `latest_preflight_run` / `latest_static_audit`**：M 为 `runs/27_method_resume_20261019T173017Z` / `reports/cross_generator_contract.json`；R 为 `runs/19_target_encoding_20261018T005251Z` / `reports/psnr_reproducibility/report.md`。R 的预检指针较旧，静态审计指针较新。

**C5 M 的 project_state 内部**：`completed_stages` 已包含 28、29、31，但 `formal_model_runs_by_stage` 只到 27（R 有 `"28": 15, "29": 36, "31": 6`）。阶段30（hold）没有出现在 `incomplete_stages`，只出现在 `pending_design`。

**C6 SEAL 语义判定规则是否已明确**
- IA（2026-10-09，依据作者 arXiv v4，2026-05-18）：“语义决策已核实为未归一化 per-patch L2<2.3、匹配数≥12（k=1024、b=7）”，并认为 Figure 6 的 0.896 是 Spatial Test 检测器的平均 ROC-AUC。来源：`IA:research/official_seal_baseline_route.md` 第 3、25、29 行。
- M（2026-10-16，只读了 arXiv v1；最终版 PDF 返回 403）：语义绑定路径“未将 `--threshold` 接入最终布尔判定”，τ=2.3、m_match=12 只出现在穷举路径；仍需“完整语义路径的固定 τ/m_match 及其校准来源”。`M:project_state.json` `blockers` 也把“SEAL semantic fixed decision/salt protocol”列为未解决。来源：`M:docs/SEAL_EVALUATION_CONTRACT.md` 第 9、17–18、45 行。
- 两边读的论文版本不同（v4 vs v1），本文不判断哪一方正确。

**C7 W 的执行条件与 M 的 AGENTS.md 规则**
- W 的记录：“server249，GPU 0/1/2/3（每卡 1 进程）”，“攻击 35m33s（4 进程并发）”。来源：`W:…/reports/pg_smf_pilot_report_20261027.md` 第 3、6 行。
- M 的规则：物理 GPU 只能用 0、1、2，并且单卡串行执行。来源：`M:AGENTS.md` 2026-10-16、2026-10-17、2026-10-20 各节。
- W 只写了“研究指导 Li YanLei”，没有给出这次扩大设备范围的授权记录。本文**无法核实**是否另有授权。W 的原始产物只在服务器 `runs/pilot_*`，Git 中没有图像、张量或哈希清单。

**C8 W 内部**：README 摘要表第 25 行把 V4 标为“（运行中）”，第 225 行写“v3_t1 / v3_t2 / v4_t1 / v4_t2 ✅ 全部完成”；产物索引第 269 行只列出 `v3_t1/v3_t2/v4_t1`，没有 `v4_t2`。另外，W 的 native 50 步 BA 0.8516（Task1/2）与阶段31 的 151 步 BA 0.9199（4 对）步数不同、子集不同，两者并不矛盾，但很容易被当成同一个基线。

**C9 IA 研究线在 M 上的去向**：M 在 `41f8758` 整树替换后，没有任何文档说明实例真实性研究线（IA README：“当前暂停扩大替代配置实验”）是关闭、暂停还是被并入。M 上只剩下 `docs/SEAL_EVALUATION_CONTRACT.md` 把 SEAL 当作评估对象契约。状态：**未记录**。

**C10 AGENTS.md 的授权段落与当前范围**：`M:AGENTS.md` 中时间最新的段落是“Current continuation decision (2026-10-20)”，授权继续 stage27，并允许使用空闲的 GPU0–2；而 `M:README.md` 页首与 `M:project_state.json` 写的是本轮只做发布和审阅、不启动 GPU。AGENTS.md 没有一节明确收回 2026-10-20 的授权。另外，AGENTS.md 各节并没有按时间排序（2026-10-20 一节排在 2026-10-16 之前）。

**C11 “正式结论请引用 main 上的阶段报告”**：W 的 WORKBUDDY.md 这样写，但阶段31等报告本身并不在 M 的文件树里，只在 R 上（见第 1 节）。

## 5. 已记录的勘误与修正（索引）

| 事项 | 内容摘要 | 来源 |
|---|---|---|
| PSNR uint8 溢出 | 官方旧版在 uint8 上做减法；修复提交 `d5885a3` 改为 float32；项目固定的 `ca68950` 已包含修复 | `R:reports/psnr_reproducibility/report.md` |
| 参考归一化不等价 | 官方 `run_imprint_forgery.py` 的输入范围为 [0,1]，项目 `cover_pilot/attack.py` 为 [-1,1] | 同上 |
| Flickr URL 解析（v1→v1.1） | 项目分析错误，不是资产缺陷；v1.1 支持三种 URL 形式 | `R:reports/confirmation100_assets_v11_completed/report.md` |
| 阶段10 r1/r2 失败 | 见第 2 节；原代码与失败目录均保留 | `M:reports/10_imprint_delivery/report.md` |
| 阶段15 首版协议 | 启动前把阶段标签从 10 更正为 15，首版从未启动 | `M:protocols/15_imprint_timing_r2.json` |
| 阶段17 分析器 | v1 的相对路径参数导致 ValueError；v2 修复，v1 保留 | `M:reports/17_cover_pilot/analysis_invocation_failure.json` |
| 阶段21 控制器 | v1 因 NameError（`spei`）在启动模型前退出；`control_r2.py` 修复 | `M:reports/21_directional_study/report.md` 第 64 行 |
| 阶段27 Jain 任务2 | 在加载模型前失败；保留为缺失，不重跑 | `M:project_state.json` `stage27.failed_tasks` |
| IA 执行勘误 | 见 IA 分支时间线 | `IA:research/execution_erratum.md` |

## 6. 汇总的未决问题

1. 新方法与实质贡献尚未建立：`M:project_state.json` `top_tier_contribution_demonstrated: false`、`novel_attack_method: null`；W 的四个变体均为负结果。
2. 完整官方几何判定、SemBind 完整 GS-S 验证器、SEAL 固定语义判定/salt 协议仍缺（`M:project_state.json` `blockers`；SEAL 一项见 C6）。
3. 100 对模型实验未启动，运行协议未冻结（`paper_priority.runtime_protocol_frozen: false`）。
4. 阶段 28–31 与 confirmation100 的证据只在 R 上，M 只有 URL 指针（第 1 节）。
5. 正式独立人工内容评审为 0 份（`M:GPT_CONTEXT.md`）。
