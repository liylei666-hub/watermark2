# archive/ 说明与废弃脚本索引

编制：2026-10-30，仓库整理（分支 `chore/repo-cleanup-20261030`）。

## 为什么没有把废弃脚本物理移进 archive/

这个仓库里的脚本同时也是实验证据。每个脚本至少被以下一种方式按**路径或 SHA256** 绑定：

- `protocols/*.json` 的 `code_hashes` 以服务器路径 `/data0/liyanlei/watermark_research/scripts/<路径>` 为键记录哈希。`tools/verify_archive.py` 的 `resolve()` 会把这个前缀映射回仓库内的同一相对路径，再核对哈希。
- `runs/**/command.json`、`launch_intent.json` 记录了实际执行的脚本路径。
- `provenance/source_manifest.json`、`provenance/local_sources.json`、`provenance/07_remote_manifest.json` 记录了来源路径和哈希；`verify_archive.py` 会断言其中每个路径都存在，并且哈希一致。

整理时核对过：`scripts/` 与 `tools/` 下的 208 个文件中，没有一个是无人引用的。只要移动、改名或改写其中任何一个，上面的路径映射就会断开，原始协议也就无法再定位到它对应的代码。协议 JSON 属于不可修改的证据，不能跟着改路径。

因此，本次整理把废弃状态**记录在本文件里，文件本身留在原处**。下表的“当前位置”就是文件的实际路径。

## A. 已经在 archive/ 下的文件

`archive/local_work/` 是作者在 `41f8758`（2026-10-13）归档的阶段 01–05 本机准备、中转、审计与记录工具（见 `docs/ARTIFACT_GUIDE.md` 第 11 行），**不是另一组实验结果**。其中每个文件都列在 `provenance/local_sources.json` 中，并由 `verify_archive.py` 核对哈希，所以同样不能移动或删除。

| 子目录 | 内容 | 废弃原因 | 替代物 |
|---|---|---|---|
| `stage01/` | 阶段01 本机 AGENTS、审计报告、`preflight.py` | 阶段01 已完成；这里是本机工作副本 | 服务器副本 `scripts/preflight.py`（字节相同）；执行规则以根目录 `AGENTS.md` 和 `provenance/execution_AGENTS.md` 为准 |
| `stage02/` | 模型下载、中转、缓存核查脚本与日志（`download_models.py`、`parallel_download.py`、`relay.py`、`*.log` 等）；`run_smoke.py` 等 5 个脚本 | 阶段02 一次性的环境准备工具。根目录 `AGENTS.md` 当前规定“不下载新模型”，下载和中转工具已不适用 | 下载类工具没有替代物（不再需要）；5 个与 `scripts/` 字节相同的副本见 D 节 |
| `stage03/` | 阶段03 静态审计脚本、证据 JSON 与报告 | 阶段03 已完成 | 已发布结论见 `reports/03_geometry_audit_20261013T020025Z/` |
| `stage04/`、`stage04_preflight/` | 阶段04 本机脚本副本与预检报告 | 阶段04 已完成；本机副本 | 服务器副本 `scripts/04_latent_diag_20261013T024856Z/`（字节相同，见 D 节） |
| `stage05/` | `stage05.py`、`test_parameters.py` | 阶段05 已完成；本机副本 | `scripts/05_seed_pilot_20261013T041252Z/`（字节相同） |

## B. 已被取代的脚本（留在原处）

每一行的废弃原因都来自“证据”列中的失败记录或报告，不是推测。

| 当前位置 | 废弃原因 | 替代物 | 证据 |
|---|---|---|---|
| `scripts/analyze_cover_pilot.py` | 本地调用时把相对根路径与已解析的绝对路径混用，在 `scripts/cover_pilot/bundle.py:56` 抛出 ValueError，没有产出分析文件 | `scripts/analyze_cover_pilot_v2.py`（在函数入口解析绝对根路径） | `reports/17_cover_pilot/analysis_invocation_failure.json` |
| `scripts/test_cover_readback.py` | 对应已废弃的 v1 分析器；v2 增加了相对根路径的 CPU 回归测试 | `scripts/test_cover_readback_v2.py` | `reports/17_cover_pilot/readback_tests.json` 与 `readback_tests_v2.json`；`reports/17_cover_pilot/report.md` 第 32 行 |
| `scripts/test_cover_baseline_adapter.py` | 预处理 oracle 没有按声明的 dtype 计算；r2 改用显式 float32 运算，算法、源码和容差都没有变 | `scripts/test_cover_baseline_adapter_r2.py` | `reports/cover_baseline_contract/cpu_checks_r2.json` 的 `repair` 字段 |
| `scripts/imprint_timing/control.py` | 对应首版协议 `protocols/15_imprint_timing.json`；启动前把阶段标签从 10 更正为 15，首版**从未启动** | `scripts/imprint_timing/control_v2.py`（`protocols/15_imprint_timing_r2.json`） | `protocols/15_imprint_timing_r2.json` 的 `revision_reason` |
| `scripts/imprint_delivery/control.py`、`experiment.py` | 阶段10 r1：`torch.autograd.grad` 与上游 reentrant checkpoint 不兼容，在初始梯度记录处 exit 1，没有完成任何更新 | `scripts/imprint_delivery_r3/` | `reports/10_imprint_delivery/execution_status.json`；`runs/10_imprint_delivery_20261017T184646Z/` |
| `scripts/imprint_delivery/gradient_compatibility.patch`、`test_checkpoint_gradient.py` | 兼容补丁通过了 3 项 CPU 回归，但按冻结规则**没有应用**到冻结代码；后续改为另行冻结的 r2/r3 | `scripts/imprint_delivery_r3/` | 根目录 `AGENTS.md` 的“Stage10 execution status”一节；`reports/10_imprint_delivery/execution_status.json` |
| `scripts/imprint_delivery_r2/` | r2 运行 54.173 s 后梯度逐位检查失败（最大差 3.0268e-9），0 次更新 | `scripts/imprint_delivery_r3/`（加入确定性设置，10 次更新完成） | `reports/10_imprint_delivery/report.md` 第 45–48 行 |
| `scripts/directional_study/control.py` | 在 GPU 预检和模型启动前因标识符错误（`NameError: name 'spei' is not defined`）退出，启动模型数 0 | `scripts/directional_study/control_r2.py` | `runs/21_directional_20261018T023718Z/status.json`；`reports/21_directional_study/report.md` 第 64 行 |

**注意**：以上 B 节文件虽然已被取代，后续协议（例如 `protocols/21_directional_runtime_r2.json`）的 `code_hashes` 仍然记录了它们的哈希。所以它们**不能删除，也不能改写**。

## C. 名字像旧版、实际仍在使用的脚本（不是废弃）

| 位置 | 为什么不算废弃 |
|---|---|
| `scripts/method_comparison/attack.py`、`common.py` | `scripts/method_comparison_r4/attack.py` 第 5 行在运行时加载 `method_comparison/attack.py`；r4 协议的 `code_hashes` 也同时固定了两者 |
| `scripts/method_comparison/`（其余文件，含 `control.py`、`control_r2.py`） | 阶段27 原始运行 `runs/27_method_comparison_20261018T063355Z` 的产物由 r4 继承（`protocols/27_method_runtime_r4.json` 的 `inheritance` 字段），r4 协议也固定了这些文件的哈希 |
| `scripts/preflight.py` 与 `scripts/gpu_preflight.py` | 名字相近，但用途不同：前者是阶段01 环境预检，后者是之后各阶段使用的 GPU 空闲门禁，被 29 份协议引用 |
| `scripts/04_latent_diag_20261013T024856Z/`、`scripts/05_seed_pilot_20261013T041252Z/` | 目录名风格与其他目录不同（带时间戳），但 `provenance/source_manifest.json` 和 `runs/` 按这个路径引用它们 |

## D. 字节完全相同的副本

下列文件内容完全相同，但每个路径都被各自的证据文件单独引用，所以没有合并。“引用方”列出每个路径对应的证据文件。

| 内容 | 路径（引用方） |
|---|---|
| 阶段01 预检 | `scripts/preflight.py`（source_manifest、local_sources）；`archive/local_work/stage01/scripts/preflight.py`（local_sources） |
| 阶段02 工具 ×5 | `scripts/{final_resources,resolve_cache,summarize_run,verify_cache}.py`、`scripts/02_run_smoke.py`（source_manifest，run_smoke 另被 runs 引用）；`archive/local_work/stage02/` 下的同名文件（local_sources） |
| 阶段04 `diagnostic.py` | `scripts/04_latent_diag_20261013T024856Z/`、`scripts/05_seed_pilot_20261013T041252Z/`（source_manifest、runs）；`scripts/prompt_control/`（07_remote_manifest、runs）；`archive/local_work/stage04/`（local_sources） |
| 阶段04 `recording.py`、`run_recorded.py`、`stage04.py` | `scripts/04_latent_diag_20261013T024856Z/`（source_manifest、runs）；`archive/local_work/stage04/`（local_sources） |
| 阶段04/05 `test_cpu.py` | `scripts/04_latent_diag_…/`、`scripts/05_seed_pilot_…/`（source_manifest、runs）；`archive/local_work/stage04/`（local_sources） |
| 阶段05 `stage05.py`、`test_parameters.py` | `scripts/05_seed_pilot_20261013T041252Z/`（source_manifest、runs）；`archive/local_work/stage05/`（local_sources） |
| `test_contract.py` ×6 | `scripts/{imprint_components,imprint_delivery,imprint_delivery_r2,imprint_delivery_r3,imprint_gradient,imprint_shadow}/test_contract.py`（各自协议的 code_hashes） |

## E. 拿不准、保持原样的部分

- `scripts/method_comparison/control.py` 与 `control_r2.py` 分别对应阶段27 的哪一次启动：两个文件都被 r2/r4 协议固定，没有找到单独说明二者关系的记录，因此不作废弃判断。
- `scripts/` 根目录下的 `analyze_*.py`、`plot_*.py`、`check_*.py` 等单文件脚本：报告按路径引用它们，用来复算已发表的数值。它们没有被取代的记录，不列为废弃。
