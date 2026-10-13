# 扩散模型语义水印：黑盒伪造攻击研究记录

本仓库保存阶段 01–05 的用户提示词、审计、实验代码与真实输出，供研究复核和 GPT 接续阅读。

**给 GPT 的入口：[GPT_CONTEXT.md](GPT_CONTEXT.md)**。想完整阅读全文，可打开 [FULL_RECORD.md](docs/FULL_RECORD.md)；希望查某个值的来源，使用 [证据导航](docs/ARTIFACT_GUIDE.md)。

## 当前完成

| 阶段 | 内容 | 报告 |
|---|---|---|
| 01 | 环境与官方基线审计 | [环境](reports/01_environment.md) / [源码审计](reports/01_baseline_audit.md) |
| 02 | 官方 GS Reprompting 单样本 | [02_smoke_report.md](reports/02_smoke_report.md) |
| 03 | 几何论文、实现与信息边界核查 | [03_audit.md](reports/03_geometry_audit_20261013T020025Z/03_audit.md) |
| 04 | 单样本真实潜变量与全局余弦 | [04_report.md](reports/04_latent_diag_20261013T025322Z/04_report.md) |
| 05 | 固定提示词八种子开发诊断 | [05_report.md](reports/05_reprompt_seed_pilot_20261013T041832Z/05_report.md) |

## 最新观察

阶段 05 预定 8 次、启动 8 次、正常完成 8 次、有效张量配对 8 次。参考图 GS 通过 8/8；参考有效配对中的攻击图 GS 通过 8/8；攻击图 cosine 均低于对应参考图。模型为固定版本的 SDXL 目标与 SD2.1 代理，GPU 3 串行执行。

| seed | 参考 BA | 攻击 BA | 参考 cosine | 攻击 cosine | gap |
|---:|---:|---:|---:|---:|---:|
| 2 | 1.0 | 0.96875 | 0.840706 | 0.376110 | 0.464596 |
| 3 | 1.0 | 0.9296875 | 0.792123 | 0.295976 | 0.496147 |
| 4 | 1.0 | 0.9375 | 0.847505 | 0.277498 | 0.570007 |
| 5 | 1.0 | 0.9765625 | 0.824055 | 0.346531 | 0.477524 |
| 6 | 1.0 | 0.98828125 | 0.845081 | 0.402588 | 0.442493 |
| 7 | 1.0 | 0.98046875 | 0.861945 | 0.411248 | 0.450697 |
| 8 | 1.0 | 0.94140625 | 0.739250 | 0.312665 | 0.426586 |
| 9 | 1.0 | 0.96484375 | 0.760097 | 0.360854 | 0.399243 |

这是 development_pilot：一个固定提示词对、共用基础水印设置。cosine 是独立 CPU 诊断；完整官方几何检测仍未完成，几何阈值与接受结果为 null。阶段 02/04 的 seed=1 没有并入这八个样本。详细统计、分母和限制见 [summary.json](reports/05_reprompt_seed_pilot_20261013T041832Z/summary.json)。

## 原始产物

[runs/](runs/05_reprompt_seed_pilot_20261013T041832Z/../) 保存真实 PNG、原始 CSV、float32 NPY、配置、命令、退出状态、stdout/stderr、GPU 监控和绑定清单。图片示例来自阶段 05 seed=2，其他七个种子全部保留：

| 参考图 | 攻击图 |
|---|---|
| ![seed 2 reference](runs/05_reprompt_seed_pilot_20261013T041832Z/seed_2/evaluator_only/official_output/target_prompt_index=custom/attacker_prompt_index=custom/attack_instance_step=-1.png) | ![seed 2 forged](runs/05_reprompt_seed_pilot_20261013T041832Z/seed_2/evaluator_only/official_output/target_prompt_index=custom/attacker_prompt_index=custom/attack_instance_step=1.png) |

## 目录

- [prompts/](prompts/README.md)：五份阶段原始要求、设备修订和来源哈希。
- [conversation/](conversation/transcript.md)：本会话用户指令及阶段交付记录。
- [docs/](docs/PROJECT_STATE.md)：项目状态、实验谱系、完整阅读档案和证据导航。
- [reports/](reports/) 与 [runs/](runs/)：报告与原始证据，包含执行前停止记录。
- [scripts/](scripts/)：实际运行、记录和诊断代码；[archive/local_work/](archive/local_work/)：本机准备与中转工具。
- [third_party/](THIRD_PARTY.md)：两个上游的固定 Git submodule 引用。
- [provenance/](provenance/PUBLICATION.md)：来源、公开副本处理和 SHA256 完整性清单。

## 只读核验

Python 3.10+，仅标准库；不安装依赖、不初始化子模块、不联网、不加载模型：

```bash
CUDA_VISIBLE_DEVICES="" python tools/verify_archive.py
```

PowerShell：`$env:CUDA_VISIBLE_DEVICES=''; python tools/verify_archive.py`。

核验检查文件清单、来源哈希、原始 CSV、张量/图片/配置绑定和已存余弦。历史 GPU 脚本包含服务器绝对路径，不能当作跨机器一键入口。环境、缓存和模型权重不在 Git；准确版本与下载/校验清单完整保留。后续实验需要新的用户指令与预算。
