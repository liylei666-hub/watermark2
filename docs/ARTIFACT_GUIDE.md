# 证据与文件定位

## 阅读顺序与证据优先级

先读根目录 GPT_CONTEXT.md，再读 docs/PROJECT_STATE.md、各阶段 prompts 和 reports；需要核实数值时进入 runs。

1. `runs/` 中冻结配置、真实退出记录、原始 CSV、PNG、NPY、清单和日志是运行证据。
2. `reports/` 是按阶段形成的审计、统计和解释；保留当时状态。
3. `prompts/` 是原始用户要求及修订；历史要求不能触发自动重跑。
4. `conversation/` 是交付历史，可能含当时未解决状态和原本机文件链接；以运行证据复核。
5. `archive/local_work/` 保存本机准备、中转、审计与记录工具；它不是另一组实验结果。
6. `provenance/` 保存源文件哈希、公开副本处理记录、上游 pins、最终文件清单和验证结果。

## 单样本路径

- 阶段 02：`runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z/`。CSV 和 PNG 位于 `target_prompt_index=custom/attacker_prompt_index=custom/`；有 `config.json`、`command.sh`、`stdout.log`、`stderr.log`、`execution.json`、`exit_code.txt`、`pip_freeze.txt`、模型清单和本机中转清理记录。
- 阶段 04：`runs/04_reprompt_latent_diag_seed1_20261013T025322Z/`。`evaluator_only/` 有三个 NPY、`tensor_manifest.json`、绑定清单、`candidate_frozen.json`、实际加载路径、CPU/mock 测试和 `diagnostic.json`；原始 PNG/CSV 在 `evaluator_only/official_output/.../`。
- 阶段 05：`runs/05_reprompt_seed_pilot_20261013T041832Z/seed_{2..9}/`。每个种子一个 `evaluator_only/`，含同样的三个 NPY、原图/候选、CSV、配置及模型日志。子目录根有 GPU 预检、2 秒监控、PID/PGID、退出码与耗时。组根有预先冻结的 `pilot_protocol.json`、SHA256、CPU 测试及 `group_execution.json`。
- `evaluator_only/mock_tests/` 是 CPU/mock 记录，不属于真实样本；不要把其中 PNG/NPY 纳入科学统计。

## 张量语义

| 文件 | 含义 |
|---|---|
| target_original_wm_zT.npy | 本次实际进入目标生成的原始水印噪声 |
| target_inverted_reference_zT.npy | 本次目标 validate(step=-1) 对参考图反演的返回值 |
| target_inverted_forged_zT.npy | 本次目标 validate(step=1) 对攻击图反演的返回值 |

它们是非 pickle 的 float32 NPY，真实样本形状为 [1,4,64,64]。哈希/样本ID/配置/图像绑定在 tensor_manifest.json；代理噪声不是这些目标张量。

## 路径可移植性

历史绝对路径前缀 `/data0/liyanlei/watermark_research/` 可映射为本仓库根目录；其后的 reports/、runs/、scripts/ 文件保留相同相对路径。原始代码、配置和清单中的绝对路径保持原样以维持哈希。`tools/verify_archive.py` 用此映射只读验证，无需服务器路径存在。

`cache/`、`envs/`、`tmp/` 不在 Git 中。模型 snapshot 路径是当时加载证据；不能把在此 checkout 找不到权重理解为当时未加载成功。下载日志和安装工具只是历史文件，不能直接自动运行。上游子模块需要明确初始化才能在本地阅读；本次发布未初始化或执行它们。

## 公开材料与未来攻击边界

公开归档保留 evaluator_only 的潜变量、CSV 中的实验消息以及分数，以支持研究复核。这些开发材料已经公开，未来受限攻击必须采用独立输入白名单和新定义的实验边界；整个仓库不能挂载为攻击算法输入。目录名、候选哈希和事后 CPU 进程不等同权限级隔离。
