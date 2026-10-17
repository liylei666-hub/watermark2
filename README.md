# 扩散语义水印的黑盒伪造研究

研究目标：在明确的攻击信息边界下研究伪造方法与误差来源，形成可复现代码、充分实验和论文初稿。

**当前判断：方向有条件可行，已有结果尚不足以构成顶刊顶会贡献。已完成提示词和目标往返对照，并留存未完成的 VAE 组件诊断；完整防御协议仍有明确缺项。**

- [组件残差定位](reports/12_imprint_components/report.md)：链式梯度逐位一致，较大有限步长残差主要在VAE组合映射；贡献与目标迁移收益尚待证明。
- [固定点梯度诊断](reports/11_imprint_gradient/report.md)：两个点梯度余弦0.731/0.676，原生下降仍改善交付目标；交付自方向的两项差分核验超出容差，原因待定位。
- [Imprint交付路径诊断](reports/10_imprint_delivery/report.md)：10步原生优化已完成，PNG保留91.52%的内部损失改善；包含失败证据、确定性核验与完整轨迹对照。
- [研究审查](reports/research_review.md)：可行性、创新空间、理论问题与继续/停止条件。
- [导师讨论 Word](docs/advisor_briefing.docx) / [可检索正文](docs/advisor_briefing.md)：原论文、两篇 ICML 2026 防御、结果与研究问题。
- [评估对象与威胁模型契约](docs/EVALUATION_CONTRACT.md)：最终会议版与固定源码核查，参考、判定、基线差异及明确缺项。
- [可运行的评估事件检查](reports/evaluation_events_20261017/report.md)：候选哈希、计划分母、未知标签与真实CSV接入。
- [PAI 验证契约](docs/PAI_EVALUATION_CONTRACT.md)：普通阈值、密钥/时间戳参考、稳健PCA缺项与接口阻塞。
- [内容评审规则](docs/CONTENT_ADJUDICATION.md)：逐项可见内容、未知判定与独立评审记录表。
- [攻击比较契约](docs/BASELINE_COMPARISON_CONTRACT.md)：任务轨道、信息权限、计算预算与成功分母。
- [当前计划](docs/RESEARCH_PLAN.md)：正在解决的问题与证据门槛。
- [文献矩阵](docs/LITERATURE.md)：截至 2026-10-17 的核查范围、版本状态和实现缺项。
- [GPT 接续入口](GPT_CONTEXT.md) / [机器可读状态](project_state.json)。

## 已有证据

阶段 01–05 完成环境与代码审计、官方 GS Reprompting 复现、真实潜变量留存。阶段 05 八种子在固定配置下原 GS 均通过，参考/攻击余弦均值为 0.813845 / 0.347934。这是固定提示词、共享基础水印设置的开发数据。

[CPU 诊断](reports/06_cpu_diagnostics/report.md)进一步区分消息解码、坐标符号和幅值，并量化参考关联敏感性。完整官方几何判定仍未复现，几何接受结果与阈值为 null；当前没有新攻击成功结论。

[三种子提示词配对诊断](reports/07_prompt_control/report.md)已完成 6 次运行：同提示词与更换提示词的候选余弦均值分别为 0.290478 与 0.306216，配对差值方向不一致；两组原 GS 各通过 3/3。保持茶壶提示词仍出现低余弦，因此不能把此前差距专门归因于主体类别变化。此结果仍是开发诊断，不能单独定位架构差异。

[目标模型自身往返](reports/08_target_roundtrip/report.md)在六个配对上均高于代理往返，但本身也损失余弦。[VAE 编解码对照](reports/09_vae_roundtrip/report.md)完成两个种子后按设备规则停止；已完成图像保持原茶壶外观，代理 VAE 后余弦仍降至约 0.51。结果支持研究处理流程敏感性，尚不构成完整防御错误接受/拒绝或新攻击贡献。

[SEAL 源码契约](docs/SEAL_EVALUATION_CONTRACT.md)进一步区分语义绑定与穷举判定，列明依赖和工作点缺项。

## 复核入口

[历史实验谱系](docs/PROJECT_STATE.md)、[证据导航](docs/ARTIFACT_GUIDE.md)、[原始要求](prompts/README.md)。`runs/` 保留原始图像、CSV、张量、配置和运行记录；模型权重和环境不进入 Git。当前入口持续更新，历史说明与决策由 Git 追溯。

Python 3.10+，标准库，只读核验：

```bash
CUDA_VISIBLE_DEVICES="" python tools/verify_archive.py
# 新往返诊断另需已有 Pillow
CUDA_VISIBLE_DEVICES="" python tools/verify_roundtrip_controls.py
CUDA_VISIBLE_DEVICES="" python -m unittest discover -s scripts -p test_cpu_latent_audit.py -v
```

PowerShell 先设置 `$env:CUDA_VISIBLE_DEVICES=''`。历史 GPU 脚本带有服务器路径，读取本仓库不授权执行。本轮设备为物理 GPU 0–2，单卡串行；预算与运行约束见 [AGENTS.md](AGENTS.md)。
