# watermark2 — 允许编辑策略下的实例真实性

以 Müller 等 CVPR 2025 **Black-Box Forgery Attacks on Semantic Watermarks for Diffusion Models** 为起点，研究生成图像在经过明确允许的编辑后，完整验证流程能否区分合法派生图与改变关键事实的冒认图。

当前阶段：已完成18个源图的本机CPU表示诊断及处理匹配复核，共270张新派生图。固定2×2多尺度SSCD没有显示稳定收益。数据为许可照片上的构造事实标记，尚非自然图像语义编辑或完整水印实验。目标为 CCF-A 级研究贡献，新颖性仍待验证。CSI 已研究保持全局语义锚点的细粒度语义改动；下一阶段需要跨防御、完整验证和匹配正常接受率的证据。

## 阅读顺序

1. [问题、威胁模型与可证伪假设](research/problem.md)
2. [来源可追溯文献矩阵](research/literature.md)
3. [最小验证实验与停止条件](research/experiment_plan.md)
4. [旧资产复用、归档与恢复](research/migration.md)
5. [本轮验证记录及未完成项](research/validation.md)
6. [新CPU实测结果与限制](research/cpu_pilot_results.md)
7. [SEAL / SemBind / CSI 官方实现、组件测试与复现阻碍](research/public_reproduction_feasibility.md)
8. [指定服务器、GPU7与缓存核查](research/server_execution_preflight.md)
9. [SD1.5 + CLIP真实开发试运行及失败改色](research/sd15_clip_smoke.md)
10. [新源机械改色开发控制](research/mechanical_development.md)

公开实现核查已完成：固定三个上游版本，执行离线组件测试并核对权重体量。已完成独立SD1.5/CLIP替代配置的真实开发验证；3次提示词改色均无效，阈值未校准。原SEAL完整路线仍待许可明确的配套模型。SLICE 已纳入直接先行工作，分因子绑定和局部判决不能作为本项目的新颖性依据。

机器可读协议：[configs/pilot.json](configs/pilot.json)；来源索引：[research/references.json](research/references.json)。

## 轻量检查

Python 3.10+，以下检查仅需标准库，不下载数据或调用 GPU：

```bash
python scripts/check_repository.py
python scripts/audit_legacy_scores.py
python scripts/audit_cpu_pilot.py
python -m unittest discover -s tests -v
```

历史 CPU 单元测试另需 NumPy、Pillow：

```bash
cd legacy
# PowerShell: $env:CUDA_VISIBLE_DEVICES=''
# Linux/macOS: export CUDA_VISIBLE_DEVICES=''
python -m unittest discover -s tests -v
```

`legacy/` 保存原有代码、数据清单、轻量结果、报告和配置，运行历史工具时以该目录为工作目录。历史 GPU 入口含特定服务器路径及设备绑定，不能直接视为本课题实验入口。完整图片、特征和权重没有复制或下载。

新实验入口为 `scripts/cpu_pilot.py`（prepare → 打分前视觉审核 → score）及 `scripts/cpu_followup.py`。需要既有许可源图目录、通过SHA校验的SSCD权重、NumPy/Pillow/PyTorch；无自动下载。以 `--asset-root` 指定原项目目录，prepare另需 `--font` 指定Arial字体。固定配置见 `configs/cpu_pilot.json`，已有完成结果不会被prepare覆盖。用于重跑时应使用独立工作副本/新运行目录，保留当前证据。原始PNG与特征在本机 `runs/cpu_pilot/`，轻量记录在 `reports/cpu_pilot/`。

## 已有证据的用途

[旧同提示词诊断](legacy/research/03_same_prompt_diagnostic.md)记录了全局表示对自然重生成实例的低错误接受，以及 JPEG 造成的较高误拒；局部 DINO 未显示优势。这些是旧工作中有限分布上的表示诊断，未包含真实关键事实编辑、载荷恢复、签名或自适应攻击。本轮只重算已保存分数并检查归档一致性。

远端恢复分支：[`backup/pre-restart-20261007`](https://github.com/liylei666-hub/watermark2/tree/backup/pre-restart-20261007)，旧主分支提交为 `1eeea4c95e555bfabc242b90aad35ca813557443`。Git 历史持续保留。
