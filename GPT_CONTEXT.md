# 研究接续入口

**当前状态（2026-10-25 UTC）：**100 对确认资产 v1.1 已完成：100 张载体、100 条唯一文本和 100 个固定配对。恢复核查确认服务器 100 份原图、100 份 RGB512 PNG 的存在性、大小及 SHA256 全部匹配，315 项执行封存文件哈希通过。确定性选择与像素解码采用历史服务器回执，本次未重跑。[资产报告](reports/confirmation100_assets_v11_completed/report.md) / [恢复核验](reports/confirmation100_assets_v11_completed/recovery_verification_20261025.json).
**模型实验边界：**100 对模型实验尚未启动；Stage31 已完成的结果仅为 4 对共享身份 corrected native Imprint 校准及事后 CPU LPIPS，主端点 151 次更新普通 GS 4/4、平均 BA 0.919921875、PSNR 23.751050 dB、LPIPS 0.197920425。[Stage31 报告](reports/31_native_calibration/report.md) / [质量补充](reports/31_native_calibration_lpips_20261025/report.md)。完整论文复现尚未完成。
**下一项：**审阅完整 corrected native Imprint 100 对基线协议、独立私有 GS 材料及实际资源预算；资产按冻结清单使用，100 对模型实验尚未启动。Stage30、八攻击对照和 Jain 原设置保持 hold。
更新：2026-10-25 UTC。目标为扩散语义水印黑盒伪造的方法、充分实验、可复现代码和论文初稿。用户授权自主研究、核验后正常推送GitHub；研究心跳已按用户要求移除。每次先核对真实进程、Git与机器账本。

## 当前结果与下一项

阶段28和29已完成，两个固定假设均按冻结规则关闭。阶段28三组均4/4普通GS通过；分阶段平均BA为0.906250，低于固定短轨迹0.930664，相对native50的中位像素MSE比2.644049。阶段29在16对独立提示组、固定PNG质量与约760秒核心预算下，pixel50/pixel10通过10/16与9/16，平均BA差(pixel10−pixel50)为−0.00048828125，6对提高、2对持平，描述性配对bootstrap95%区间[−0.013671875,0.01318359375]。

完整证据与边界见[阶段28/29复核报告](reports/29_reconciliation/report.md)。阶段27也已关闭：原生Imprint/delivery为8/12、6/12；Jain任务2失败保留。

当前下一项：审阅完整 corrected native Imprint 100 对基线协议、独立私有 GS 材料及实际资源预算；资产按冻结清单使用，100 对模型实验尚未启动。Stage30、八攻击对照和 Jain 原设置保持 hold。

已保留的阶段30提案（hold）：[参考×载体交叉诊断](reports/30_crossed_proposal/proposal.md)，4区组、16次固定pixel50攻击；仅CPU设计与分析检查完成，待科学审阅与执行适配，尚未启动。

## 已验证的研究依据

- [阶段17](reports/17_cover_pilot/report.md)：近似376秒核心预算，Imprint普通GS通过2/3、适配Jain0/3。三对共用一个加密身份；全部候选先封存。完整防御与正式内容标签unknown。
- [阶段18/19](reports/19_target_encoding/report.md)：六个固定端点的排序改变依赖任务、编码与反演，不能单因归属。该组三对六候选的微观诊断关闭。
- [阶段21](reports/21_directional_study/report.md)：4对新图、2身份，同像素失真下反演方向相对VAE方向的目标MSE改善差均为正，但仅3/4改善载体、20候选GS均未通过。8项中心差分均超25%门槛，一阶机制未建立；正反方向只能作有限步长描述。本组关闭。
- [阶段22](reports/22_decoder_contract/report.md)：MSE、取位、重复投票与最终阈值须分层。原论文已有bin resampling；逐图独立key/nonce与历史共享身份实验不同。
- [目标函数审查](docs/METHOD_HYPOTHESIS.md)：最近同符号集合距离等价平方hinge，零间隔不保证负符号；半正态随机目标MSE平均等价固定均值目标加常数。基础恒等式不构成新方法或迁移保证。
- [阶段10–15交付/成本与组件证据](docs/COVER_BASELINE_CONTRACT.md)以及[历史01–05](docs/PROJECT_STATE.md)保留原始结果和失败。[执行账本](reports/research_execution_ledger.json)阶段27后累计105个历史模型进程，阶段28新增15、阶段29新增36个成功工作进程记录；新增记录与历史模型进程口径见复核报告，旧账本属于历史快照；原失败版本不重跑。

## 完整评估与新颖性边界

- [几何评估契约](docs/EVALUATION_CONTRACT.md)：最终版理论AND拒绝区域已查清，公开完整实现、参考关联和固定工作点仍缺。独立余弦不等于完整接受。
- SemBind最终版E.1/Table17已有5组端到端代理masker测试Det.=0；公开库不是完整GS-S验证器。
- [SEAL](docs/SEAL_EVALUATION_CONTRACT.md)需未缓存caption/embedding与固定语义协议；[PAI](docs/PAI_EVALUATION_CONTRACT.md)仍缺PCA参考和接口；不自造补全。
- [CSI](docs/CSI_INFORMATION_CONTRACT.md)使用检测失败反馈，不能原样作为零目标反馈基线。[PnP](reports/pnp_source_availability.json)匿名源403未绕过，完整性unknown。
- Jain已有单图VAE匹配与DCT限制，AdvPC/EOT/FIA已有相关机制；简单改损失、变换平均或自重建不是独立贡献。核对范围见[文献矩阵](docs/LITERATURE.md)，不能声称穷尽检索。
- [内容规则](docs/CONTENT_ADJUDICATION.md)正式人工评审0份，助手视觉观察不是人工标签。普通GS、内容、完整防御、错误归属和报警分别报告。

## 执行范围

本次工作限定为成果发布与协议审阅，不启动 GPU 作业，不下载模型。历史模型工作仅位于指定服务器，设备及并发范围按各阶段记录保留；100 对模型运行需先审阅完整协议和实际资源计划。CPU 命令 CUDA_VISIBLE_DEVICES 为空。阶段09 seed103及阶段27 Jain任务2保持禁止重试。

CPU明确CUDA_VISIBLE_DEVICES为空。阶段09 seed103禁止重试或补样。保护原始run、失败、配置、图片和张量；工程失败保留后先CPU检查修复，再单独冻结版本。不得扫描网络、攻击生产服务、绕过SSH/TLS验证、存凭据或联系他人。

攻击/代理只读取获准参考图、输出提示词、代理配置及自身随机状态。目标密钥/消息/nonce、原始噪声、RNG、目标反演和分数属于评估端；候选或代理表示先封存哈希后评估，禁止分数反馈选候选或调参。阶段23私有材料在服务器private_eval，未传本机或Git；共享OS用户不构成权限隔离。

## 接续入口

[研究计划](docs/RESEARCH_PLAN.md) / [方法假设](docs/METHOD_HYPOTHESIS.md) / [机器状态](project_state.json) / [比较契约](docs/BASELINE_COMPARISON_CONTRACT.md) / [导师Word](docs/advisor_briefing.docx) / [原始证据](docs/ARTIFACT_GUIDE.md)。只发布确定、有用且复核过的进展；精简更新当前说明，保留所有原始证据。


阶段30继续hold，输入生成与攻击均为0。相关审查和已完成校准见[PSNR版本与原生基线校准审查](reports/psnr_reproducibility/report.md)。官方旧uint8 PSNR bug已在2025-05-30修复；本项目当前版本含修复。现有10更新与受约束pixel变体不能代替原生150步整表复现。



## 已完成的阶段31原生校准

阶段31已完成，见[最终报告](reports/31_native_calibration/report.md)。
