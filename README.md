# watermark2 — 允许编辑策略下的实例真实性

以 Müller 等 CVPR 2025 **Black-Box Forgery Attacks on Semantic Watermarks for Diffusion Models** 为起点，研究生成图像在经过明确允许的编辑后，完整验证流程能否区分合法派生图与改变关键事实的冒认图。

当前阶段：问题定义、文献核验和最小验证设计。目标为 CCF-A 级研究贡献；尚未提出经验证的新方法或取得新的攻击/防御实验结果。CSI 已研究保持全局语义锚点的细粒度语义改动；本项目下一步需要验证跨防御、完整验证联合适应及匹配正常接受率是否形成有价值的研究问题。

## 阅读顺序

1. [问题、威胁模型与可证伪假设](research/problem.md)
2. [来源可追溯文献矩阵](research/literature.md)
3. [最小验证实验与停止条件](research/experiment_plan.md)
4. [旧资产复用、归档与恢复](research/migration.md)
5. [本轮验证记录及未完成项](research/validation.md)

机器可读协议：[configs/pilot.json](configs/pilot.json)；来源索引：[research/references.json](research/references.json)。

## 轻量检查

Python 3.10+，以下两项仅需标准库，不下载数据或调用 GPU：

```bash
python scripts/check_repository.py
python scripts/audit_legacy_scores.py
```

历史 CPU 单元测试另需 NumPy、Pillow：

```bash
cd legacy
# PowerShell: $env:CUDA_VISIBLE_DEVICES=''
# Linux/macOS: export CUDA_VISIBLE_DEVICES=''
python -m unittest discover -s tests -v
```

`legacy/` 保存原有代码、数据清单、轻量结果、报告和配置，运行历史工具时以该目录为工作目录。历史 GPU 入口含特定服务器路径及设备绑定，不能直接视为本课题实验入口。完整图片、特征和权重没有复制或下载。

## 已有证据的用途

[旧同提示词诊断](legacy/research/03_same_prompt_diagnostic.md)记录了全局表示对自然重生成实例的低错误接受，以及 JPEG 造成的较高误拒；局部 DINO 未显示优势。这些是旧工作中有限分布上的表示诊断，未包含真实关键事实编辑、载荷恢复、签名或自适应攻击。本轮只重算已保存分数并检查归档一致性。

远端恢复分支：[`backup/pre-restart-20261007`](https://github.com/liylei666-hub/watermark2/tree/backup/pre-restart-20261007)，旧主分支提交为 `1eeea4c95e555bfabc242b90aad35ca813557443`。Git 历史持续保留。
