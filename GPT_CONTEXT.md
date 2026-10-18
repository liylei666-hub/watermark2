# 研究接续入口

更新：2026-10-18（Asia/Shanghai）。目标为扩散语义水印黑盒伪造的方法、充分实验、可复现代码和论文初稿。用户授权自主研究、核验后正常推送GitHub；30分钟线程心跳automation支持接续。每次先核对真实进程、Git与机器账本。

## 当前结果与下一项

阶段25配对交付协议与运行时已冻结，11项CPU检查在本机与249通过，56份既有执行记录重新核对一致。计划4个串行进程、16候选和24次目标反演；启动状态以真实run为准。[协议](protocols/25_delivery_design.json) / [准备核验](reports/25_delivery_transfer/preparation.json)。

[阶段24跨生成器诊断](reports/24_cross_generator/report.md)已完成：16训练/8源验证/8同域GS/8目标GS，固定估计器只拟合一次。SDXL组位错误均值从43.940735%降至43.641663%（8/8改善，平均降低0.299072个百分点），同域GS降低0.080872个百分点（5/8改善）。目标组消息准确率7/8改善、1/8下降，说明坐标位改善不保证重复投票改善。48份官方消息分数、全部预测和图像关联均经独立复核。全组12模型进程581.474425秒，累计56进程6870.670167秒；无活动模型进程。本组关闭，不调参补样。

事后代数分解将目标MSE下降的73.26%分摊给正通道缩放项；正缩放本身不改符号。目标位翻转有1181个有益、789个有害，净改善392/131072坐标。分解不是因果消融，空间坐标不是独立样本。未产生攻击候选或完整防御接受结论，线性代理监督也不作为创新方法。按[端到端交付契约](docs/DELIVERY_TRANSFER_CONTRACT.md)为已冻结校正建立配对评估协议，检验参考位恢复收益能否经过代理生成和目标反演保留下来；两种输出全部先封存后评估，保持参数固定，不作候选筛选。

## 已验证的研究依据

- [阶段17](reports/17_cover_pilot/report.md)：近似376秒核心预算，Imprint普通GS通过2/3、适配Jain0/3。三对共用一个加密身份；全部候选先封存。完整防御与正式内容标签unknown。
- [阶段18/19](reports/19_target_encoding/report.md)：六个固定端点的排序改变依赖任务、编码与反演，不能单因归属。该组三对六候选的微观诊断关闭。
- [阶段21](reports/21_directional_study/report.md)：4对新图、2身份，同像素失真下反演方向相对VAE方向的目标MSE改善差均为正，但仅3/4改善载体、20候选GS均未通过。8项中心差分均超25%门槛，一阶机制未建立；正反方向只能作有限步长描述。本组关闭。
- [阶段22](reports/22_decoder_contract/report.md)：MSE、取位、重复投票与最终阈值须分层。原论文已有bin resampling；逐图独立key/nonce与历史共享身份实验不同。
- [目标函数审查](docs/METHOD_HYPOTHESIS.md)：最近同符号集合距离等价平方hinge，零间隔不保证负符号；半正态随机目标MSE平均等价固定均值目标加常数。基础恒等式不构成新方法或迁移保证。
- [阶段10–15交付/成本与组件证据](docs/COVER_BASELINE_CONTRACT.md)以及[历史01–05](docs/PROJECT_STATE.md)保留原始结果和失败。[执行账本](reports/research_execution_ledger.json)现累计56进程，包含3个历史非零退出；原失败版本不重跑。

## 完整评估与新颖性边界

- [几何评估契约](docs/EVALUATION_CONTRACT.md)：最终版理论AND拒绝区域已查清，公开完整实现、参考关联和固定工作点仍缺。独立余弦不等于完整接受。
- SemBind最终版E.1/Table17已有5组端到端代理masker测试Det.=0；公开库不是完整GS-S验证器。
- [SEAL](docs/SEAL_EVALUATION_CONTRACT.md)需未缓存caption/embedding与固定语义协议；[PAI](docs/PAI_EVALUATION_CONTRACT.md)仍缺PCA参考和接口；不自造补全。
- [CSI](docs/CSI_INFORMATION_CONTRACT.md)使用检测失败反馈，不能原样作为零目标反馈基线。[PnP](reports/pnp_source_availability.json)匿名源403未绕过，完整性unknown。
- Jain已有单图VAE匹配与DCT限制，AdvPC/EOT/FIA已有相关机制；简单改损失、变换平均或自重建不是独立贡献。核对范围见[文献矩阵](docs/LITERATURE.md)，不能声称穷尽检索。
- [内容规则](docs/CONTENT_ADJUDICATION.md)正式人工评审0份，助手视觉观察不是人工标签。普通GS、内容、完整防御、错误归属和报警分别报告。

## 执行范围

仅liyanlei@172.18.185.249、/data0/liyanlei/watermark_research，物理GPU0–2中核对空闲的一张，每子进程核对UUID与占用，UUID绑定、cuda:0、串行。禁止本机GPU及其他服务器。用户已取消GPU时间授权上限，仍记录真实用量；各冻结协议保留1200秒工程watchdog。新增文件最多10GiB，不下载新模型，不终止他人进程。

CPU明确CUDA_VISIBLE_DEVICES为空。阶段09 seed103禁止重试或补样。保护原始run、失败、配置、图片和张量；工程失败保留后先CPU检查修复，再单独冻结版本。不得扫描网络、攻击生产服务、绕过SSH/TLS验证、存凭据或联系他人。

攻击/代理只读取获准参考图、输出提示词、代理配置及自身随机状态。目标密钥/消息/nonce、原始噪声、RNG、目标反演和分数属于评估端；候选或代理表示先封存哈希后评估，禁止分数反馈选候选或调参。阶段23私有材料在服务器private_eval，未传本机或Git；共享OS用户不构成权限隔离。

## 接续入口

[研究计划](docs/RESEARCH_PLAN.md) / [方法假设](docs/METHOD_HYPOTHESIS.md) / [机器状态](project_state.json) / [比较契约](docs/BASELINE_COMPARISON_CONTRACT.md) / [导师Word](docs/advisor_briefing.docx) / [原始证据](docs/ARTIFACT_GUIDE.md)。只发布确定、有用且复核过的进展；精简更新当前说明，保留所有原始证据。
