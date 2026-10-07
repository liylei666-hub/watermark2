# 文献矩阵与新颖性边界

核查日期：2026-10-07。范围为指定起点和直接相关的六项工作，共七项；这是有界相关工作审查，不是穷尽式系统综述。元数据和访问状态见 [references.json](references.json)。论文作者的结果与本项目复现结果分开；本轮没有复现论文攻击。

| 引用 ID / 来源 | 已有贡献与本课题关系 | 必须检查的差异 | 本轮证据范围 |
|---|---|---|---|
| muller2025 / [CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/papers/Muller_Black-Box_Forgery_Attacks_on_Semantic_Watermarks_for_Diffusion_Models_CVPR_2025_paper.pdf) | 语义水印黑盒伪造为本项目起点 | 一张合法图、代理模型权限、查询预算、目标水印判定的具体定义 | 任务前序已核实；本轮 CVF 返回 403，完整协议重读待办 |
| seal2025 / [SEAL, ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/papers/Arabi_SEAL_Semantic_Aware_Image_Watermarking_ICCV_2025_paper.pdf) | 已研究语义感知的图像水印和内容绑定 | 必须复现其真实验证器，不能只替换为通用图像相似度 | 前序已核实；本轮 CVF 返回 403；CSI 正文也直接讨论此防御 |
| sembind2026 / [SemBind, ICML 2026](https://proceedings.mlr.press/v306/zhang26hj.html), [录用全文](https://raw.githubusercontent.com/mlresearch/v306/main/assets/zhang26hj/zhang26hj.pdf) | 对比训练语义 masker，将扩散水印与图像语义关联；同义提示词代码近似不变 | 录用版 §5 排除拥有部署 masker/bind/unbind 的全白盒对手；区分语义与实例，记录 mask ratio | 本轮官方元数据/摘要；录用版限制由同任务独立审阅提供，本机全文重读与代码核验待办 |
| metaseal2026 / [MetaSeal PDF](https://openreview.net/pdf?id=8i3ErmCfdJ), [TMLR 接收索引](https://jmlr.org/tmlr/papers/) | 语义与密码验证组合为直接相关方向 | 完整恢复签名消息与图像语义比对，特别是补充 §5.1；不能仅以签名通过判断实例安全 | 官方接收索引；PDF 当前受浏览器挑战，§5.1 信息来自前序核查，待本地复现 |
| geometry2026 / [ICML 2026](https://proceedings.mlr.press/v306/lee26bm.html) | 潜空间几何失真与验证前识别；理论为高斯、共享协方差、MSE 等假设下的 surrogate | 已包含同模型测试，不能称为仅适用跨模型；联合适应前置过滤与验证，并匹配参考 latent 权限 | 本轮官方元数据/摘要；理论限制及同模型测试由同任务独立审阅提供，实现待审 |
| pai2026 / [PAI, ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/51e2aaa731e8a5edfbda95fd8bd8948b-Abstract-Conference.html) | 密钥条件去噪轨迹偏转，包含归属验证、攻击检测与语义篡改定位 | 篡改图保留作者归属但标记改变可以是正确行为，须评完整输出；局部检测已有先例 | 官方元数据与摘要及同任务独立审阅；定位/验证阈值和代码待审 |
| csi2026 / [CSI 全文](https://arxiv.org/html/2602.21593v1), [WWW 官方日程](https://www2026.thewebconf.org/program/full-schedule.html) | 保留全局语义锚点、用 LLM 引导连贯细粒度修改；直接攻击 SEAL | 查询与私有模型权限、候选筛选分母、事实有效性、合法编辑接受率、完整验证适应性 | 原文 §§2–3、Table 1；官方 Short Papers 日程；DOI 10.1145/3774904.3792912 |

CSI Table 1 报告 SEAL 下 81% 攻击接受，作者定义为篡改图像仍被检测为有水印的比例；这是论文报告值。本课题没有复现该数值。原文涉及候选筛选及复制噪声，后续须核查完整尝试分母与可比权限。仅再次展示“全局语义相近但局部事实改变”不构成独立新颖性。

## 候选缺口及证据等级

**已有文献覆盖：** 通用语义绑定、局部定位、签名组合、保持全局锚点的局部语义攻击。

**本项目推断：** 明确合法编辑规则、对齐正常接受率和信息预算、联合适应完整验证流程，可能暴露单指标评测无法表达的实例真实性边界。这是比较协议层面的候选问题；七项文献范围不足以证明无人研究。

**尚需验证：** 逐篇完整流程和代码核查、其他自适应水印认证研究补充检索、独立源图的最小复现、相同资源下强全局基线。未满足这些条件前不使用“首次”“解决”“优于 SOTA”等贡献声明。

签名的消息不可伪造与图像实例绑定是不同的证明对象；EUF-CMA 本身不能覆盖所有解析、感知匹配与策略步骤。这是对安全模型的分析，不是对 MetaSeal 的已证实攻击。
