# 扩散语义水印的黑盒伪造研究

**当前状态（2026-10-25 UTC）：**100 对确认资产 v1.1 已完成：100 张载体、100 条唯一文本和 100 个固定配对。恢复核查确认服务器 100 份原图、100 份 RGB512 PNG 的存在性、大小及 SHA256 全部匹配，315 项执行封存文件哈希通过。确定性选择与像素解码采用历史服务器回执，本次未重跑。[资产报告](reports/confirmation100_assets_v11_completed/report.md) / [恢复核验](reports/confirmation100_assets_v11_completed/recovery_verification_20261025.json).
**模型实验边界：**100 对模型实验尚未启动；Stage31 已完成的结果仅为 4 对共享身份 corrected native Imprint 校准及事后 CPU LPIPS，主端点 151 次更新普通 GS 4/4、平均 BA 0.919921875、PSNR 23.751050 dB、LPIPS 0.197920425。[Stage31 报告](reports/31_native_calibration/report.md) / [质量补充](reports/31_native_calibration_lpips_20261025/report.md)。完整论文复现尚未完成。
**下一项：**审阅完整 corrected native Imprint 100 对基线协议、独立私有 GS 材料及实际资源预算；资产按冻结清单使用，100 对模型实验尚未启动。Stage30、八攻击对照和 Jain 原设置保持 hold。
研究目标：在明确的攻击信息边界下研究伪造方法与误差来源，形成可复现代码、充分实验和论文初稿。

**阶段27–29开发结果：固定候选已关闭，尚未建立新方法贡献。**

- [阶段28/29结果与独立公共复核](reports/29_reconciliation/report.md)：阶段28和29已完成，两个固定假设均按冻结规则关闭。阶段28三组均4/4普通GS通过；分阶段平均BA为0.906250，低于固定短轨迹0.930664，相对native50的中位像素MSE比2.644049。阶段29在16对独立提示组、固定PNG质量与约760秒核心预算下，pixel50/pixel10通过10/16与9/16，平均BA差(pixel10−pixel50)为−0.00048828125，6对提高、2对持平，描述性配对bootstrap95%区间[−0.013671875,0.01318359375]。
- 下一项：审阅完整 corrected native Imprint 100 对基线协议、独立私有 GS 材料及实际资源预算；资产按冻结清单使用，100 对模型实验尚未启动。Stage30、八攻击对照和 Jain 原设置保持 hold。

- [代理交付目标审查](docs/PROXY_DELIVERY_OBJECTIVE_CONTRACT.md)：核对Imprint、Reprompting、Jain和PnP，4项合成CPU检查通过；生成器参数化尚未建立新的跨模型迁移机制。
- [固定校正配对交付](reports/25_delivery_transfer/report.md)：参考位恢复改善没有传递到最终图像，消息准确率均值0.937012→0.882812，7/8下降、1/8持平。普通GS两组均8/8通过；按预定规则关闭该映射。
- [跨生成器位恢复诊断](reports/24_cross_generator/report.md)：固定代理监督在8张SDXL参考上平均降低0.2991个百分点坐标位错误；参考级结果与上述最终交付结果分别保留。
- [参考可靠性诊断](reports/23_reference_reliability/report.md)：4张独立加密参考，跨步数一致性在50%覆盖下四图均未优于幅值排序，平均位错误率高0.247个百分点；参考GS均1.0，代码、原始数据与独立复算齐备。
- [解码与采样契约](reports/22_decoder_contract/report.md)：区分连续距离、取位、重复投票与GS接受；明确逐图key/nonce与历史开发组的差异。
- [固定方向迁移诊断](reports/21_directional_study/report.md)：4对新图中反演方向相对VAE方向均更好，但只有3对改善原载体；20候选普通GS全部未通过，8项中心差分均超容差。一阶机制与新方法尚未建立。
- [三对载体试验](reports/17_cover_pilot/report.md)：约376秒核心预算下，Imprint普通GS通过2/3，适配的Jain通过0/3；全部候选固定后评估，192文件及12个分数核验通过。完整防御与正式内容标签仍未知。
- [基线计算成本](reports/15_imprint_timing/report.md)：Imprint参考准备+10步375.33秒，Jain参考编码+100步83.91秒；阶段17采用10/447步近似预算，完整输出轨迹核对通过。
- [真实VAE核心核验](reports/13_vae_core/report.md)：原参数状态三步输出跨进程一致；参数冻结等价检查未通过，保留原核心执行状态。
- [载体攻击比较契约](docs/COVER_BASELINE_CONTRACT.md)：核对Imprint/Jain预算、浮点与PNG检测对象、共享代理适配及成本；六项CPU核心检查通过。
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

PowerShell 先设置 `$env:CUDA_VISIBLE_DEVICES=''`。历史 GPU 脚本带有服务器路径，读取本仓库不授权执行。本次工作为成果发布与协议审阅，不启动 GPU；历史设备范围见各阶段协议及 [AGENTS.md](AGENTS.md)，下一轮资源须另行审阅。

[固定候选残差诊断](reports/18_endpoint_residual/report.md)：Imprint三对保留87%–94%的内部改善；两对出现代理与目标参考反演的候选排序反转。开发诊断已核验，完整防御接受仍未建立。

[目标编码定位](reports/19_target_encoding/report.md)完成12张固定图，发现候选排序差异的出现阶段依赖任务和指标；报告附四种表示空间的对比图。
