# 文献与实现覆盖

核查日期：2026-10-18（Asia/Shanghai）。这是面向研究决策的定向检索，含引用追踪与版本核查；不是穷尽式系统综述。只以论文原文、出版方及作者仓库支持技术结论。阅读范围逐项列出，未作任何用户已阅读声明。

## 直接相关材料

| 材料与核查版本 | 本次/既有阅读范围 | 与本项目的关系及限制 |
|---|---|---|
| [Müller et al., Black-Box Forgery Attacks, CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/papers/Muller_Black-Box_Forgery_Attacks_on_Semantic_Watermarks_for_Diffusion_Models_CVPR_2025_paper.pdf) | 正文与补充 C 的设置、Tables 1–3/基线、Figure 4；固定代码与 PSNR 重读 | Reprompting/Imprint 是必要基线。当前复现仅覆盖其部分条件。 |
| [Jain et al., Forging and Removing Latent-Noise Diffusion Watermarks Using a Single Image, 2504.20111v1](https://arxiv.org/html/2504.20111v1) | v1 §4.3、Table1、附录11.3；固定源码GS核心、README及离线统计脚本 | 单参考图、代理 VAE 的潜表示匹配已存在；简单增加 latent consistency 不能直接宣称首创。核心优化无目标查询；入口ASR方向与独立统计脚本不同；后者仍读文件名旧分数而非重新检测PNG。参数与交付差异见[载体比较契约](COVER_BASELINE_CONTRACT.md)。 |
| [Lee et al., Geometric Distortion Perspective, 2606.29807v1](https://arxiv.org/html/2606.29807v1) | 固定源码；最终 PMLR PDF §4、§5.1、Tables 1–2、C.3–C.4 与 v1 关键段核对 | [PMLR 确认 ICML 2026](https://proceedings.mlr.press/v306/lee26bm.html)。结论依赖假设及参考原始潜变量；公开实现缺项。C.3 讨论 Reforge，未纳入实验比较。 |
| [Arabi et al., SEAL, ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/papers/Arabi_SEAL_Semantic_Aware_Image_Watermarking_ICCV_2025_paper.pdf) | 摘要、理论假设及攻击讨论片段、作者仓库目录 | 内容绑定防伪造已有先例，包含更强模型访问的攻击设置。须与本项目的受限代理设置分列。尚未完整复现。 |
| [Zhang et al., SemBind, ICML 2026 最终版](https://proceedings.mlr.press/v306/zhang26hj.html) | 最终 PDF §3–4、Tables 1–4、E.1–E.2、Table 17、F/G；全文件符号检索与 notebook/model/inversion 关键路径阅读 | E.1 有端到端代理 masker GS-S 测试，5 组 Det.=0；不能仅按早期 v1 附录 D 称其组件评估。具体消息/密钥身份与完整公开验证仍待澄清。 |
| [Gao et al., CSI, 2602.21593v1](https://arxiv.org/html/2602.21593v1) | §2、§3、作者主页与公开库固定 SHA `8723e362835a6a61efd11b61f677b3321face3fa` | WWW 2026 Short Paper；公开库 code 模式有检测失败反馈，paper 模式另用生成端语义参考。区分原始论文与整理库的结果，见 [信息契约](CSI_INFORMATION_CONTRACT.md)。 |
| [Nakra et al., Understanding Semantic Perturbations, 2603.27513v1](https://arxiv.org/html/2603.27513v1) | §2.3、§3、评估概述及版本页 | 研究语义改变与水印鲁棒性，目标包括降低可检测性；这是移除/鲁棒性方向，不能把其成功率混作伪造成功率。 |
| [Thietke et al., Towards A Correct Usage of Cryptography, 2503.11404v1](https://arxiv.org/html/2503.11404v1) | §1–2 与配置讨论 | GS 的随机化、nonce 与多图设置早已有分析。固定密文对应相同符号模式是配置性质；当前 CPU 结果不作为新密码学发现。 |
| [Lukovnikov et al., Layout Control, WMARK 2025](https://openreview.net/pdf?id=pFMNK403AH) | 题名、摘要、作者出版记录 | ControlNet 对 TR/GS 的影响已有工作。布局保留作为候选策略前仍需全文/代码核查。 |
| [Yang et al., Gaussian Shading++, 2504.15026v2](https://arxiv.org/abs/2504.15026) | 最新摘要、版本史 | 关注随机化种子、密钥管理与公开验证；不能将 GS++ 与当前固定 GS 配置合并报告。全文协议待查。 |
| [Liu et al., PAI, ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/51e2aaa731e8a5edfbda95fd8bd8948b-Abstract-Conference.html) | ICLR最终版 §5.1–5.2、§6.5、A.4.2/A.6.1/A.6.3/A.6.4；10个官方源码/说明文件及完整树 | 普通MSE规则已明确，完整稳健PCA材料和端到端接口缺项；已有白盒自适应评估。详见[PAI契约](PAI_EVALUATION_CONTRACT.md)。 |
| [Tamim et al., Forging Tree-Ring, 2609.12909v1](https://arxiv.org/abs/2609.12909) | 最新摘要和版本史（2026-09-11） | 近期已有 Reprompt 复现与检测器插桩报告。说明“复现加保存中间量”已有近邻；尚未精读全文或复算其数值。 |
| [Feng et al., IRIS, 2608.03539](https://arxiv.org/abs/2608.03539) | v1 §5.2；最新版本状态 | **v2 于 2026-08-26 撤回，备注 Substantial revisions。** v1 仅作历史线索；不纳入有效 SOTA、已证实防御或实验目标清单。 |

另有边界材料：[随机密钥选择防伪造](https://www.toluwaniaremu.com/wm-forgery)涉及多样本/多密钥设置；[GhostVAE 的 USENIX 页面](https://www.usenix.org/conference/usenixsecurity26/presentation/liu-jinyuan)本轮直接读取超时，先前检索只定位题名。后门能力不同于本项目的代理攻击，未将它列为直接比较基线。

## 交付路径假设的近邻方法

2026-10-17补充定向阅读：

| 来源 | 阅读范围与方法 | 对研究设计的约束 |
|---|---|---|
| [PnP，2506.06018v1](https://arxiv.org/html/2506.06018v1) | §3.1–3.2：代理反演估计噪声，利用 cover 视觉/文本条件驱动预训练恢复扩散模型 | 保持内容的噪声迁移已有先例；[官方仓库](https://github.com/chaoyitud/PnP-Watermark-Forgery/tree/4db431692e73ff065ba6bd1659d016a44c9f5db8)当前列表只有README，指向匿名实现；匿名入口本次HTTP403，完整性unknown。[获取证据](../reports/pnp_source_availability.json)，未执行代码或下载模型 |
| [WMCopier，2503.22330v3](https://arxiv.org/html/2503.22330v3) | §4.1–4.3：水印图像集合训练无条件扩散模型，浅层反演/去噪和细化 | 数据量和训练权限与单参考图不同；不把 no-box 等同于无训练 |
| [Athalye et al.，BPDA，ICML 2018](https://proceedings.mlr.press/v80/athalye18a.html) | §4.1：不可微前向配合可微反向近似 | 若对图像离散转换使用近似梯度，须引用并验证，而不是独立创新 |

[方法假设](METHOD_HYPOTHESIS.md)区分源码事实、未测量的交付差距与未验证的迁移收益。本轮补充查询包括 diffusion watermark forgery VAE cycle consistency quantization、semantic watermark round-trip、WMCopier/Reforge 与 decoder re-encoding；定向检索没有构成新颖性证明。

## 官方实现可用性

| 仓库 | 核查位置 | 本轮实际检查 | 仍待验证 |
|---|---|---|---|
| [semantic-forgery](https://github.com/and-mill/semantic-forgery) | `ca68950cd7b53b8438a49580f134b2a0db28d778` | 现有归档与源码；历史复现 | 更广模型/提示词/密钥条件 |
| [geodistort-wm](https://github.com/chengyi-chris/geodistort-wm) | `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622` | 公开 HEAD 与原审计版本相同 | 缺失模块、判定及参考关联；许可证未发现 |
| [SemBind](https://github.com/XinZhang1999/SemBind) | `337c9f90a150157ac1d410208ae20e6530ca8cdd` | HEAD、完整代码树与 Python/notebook、LICENSE 正文 MIT；官方 checkpoint 链接已存在但未下载 | 缺完整 GS-S 嵌入/解绑/判定入口；exact_inversion 默认 inv_order=1 与论文 0 需显式对齐；DINOv2/checkpoint 未验证 |
| [SEAL](https://github.com/Kasraarabi/SEAL) | `92d31b31b93a6e373fe88a584c640beafb68c6fa` | 完整递归目录和 17 个源码/说明文件；语义数组、穷举布尔判定和百分位阈值路径已区分；未发现许可证正文 | 语义固定工作点/salt 协议、精确模型快照、未缓存 BLIP2/embedding；ICCV 最终 PDF 本次 403，论文按 v1 审计 |
| [Jain 单图方法](https://github.com/anubhav1997/watermark_forgery_removal) | `04433962437cbf08ad701b7b43124de07df0b666` | GS 入口与核心 VAE 优化、返回 BA 的分数语义已核查 | 其余水印分支、论文全部表格对应、运行成本未验证；本轮未跑代码 |
| [PAI](https://github.com/QingyuLiu/PAI) | `9ebc58d1a106e7155347f0d1f186e67313a4b0cf` | 10个源码/说明文件blob哈希、9个Python AST、普通与稳健判定、参考关联 | 缺PCA参考/拟合协议，模型revision与接口待补齐；许可证未发现 |

这些检查未安装依赖、下载权重或执行任何上游入口。代码“存在”和代码“可忠实运行”分别记录。

## 检索范围与未覆盖项

本轮查询包括：`diffusion semantic watermark forgery geometric adaptive attack 2026 arxiv`；`semantic watermark forgery 2026` 加 CVF、OpenReview、USENIX 域名；2026 September/October 增量检索；各篇准确题名、作者代码、版本史；由 CSI/几何/SemBind 参考文献追踪单图攻击与密码学讨论。

没有声称检索无遗漏。尚未完成：全部引用和引用它们的新论文的穷尽追踪、所有预印本与最终会议版逐页比对、其余新基线代码权限审计、各目标的完整可执行评估协议。检索未明确找到更近论文不代表该论文不存在。最晚核实的直接相关新条目为 2026-09 的复现论文；研究决策以当前列出的证据范围为准。

当前关键协议与源码行号详见 [评估契约](EVALUATION_CONTRACT.md)。最终会议版新增覆盖以本次证据为准；论文 PDF 和源码字节哈希见 [来源记录](../reports/evaluation_contract_evidence.json)。

SEAL 逐文件行号、分数及判定关系见 [专门契约](SEAL_EVALUATION_CONTRACT.md)。代码哈希见 [来源清单](../reports/seal_source_evidence.json)。

## 补充：细粒度语义绑定与成功事件

[SLICE, arXiv:2603.12749v1](https://arxiv.org/html/2603.12749v1)，2026-03-13 预印本。本次核查 §3.1–3.3、§6.1 与定理4.4：按语义因素绑定潜变量分区，并将来源识别和内容完整性分成不同状态。Table 1 ASR 文字对应 watermark present，不能直接读作完整真实性绕过；逐样本状态映射和官方实现尚未核查。详见 [比较契约](BASELINE_COMPARISON_CONTRACT.md)。仅补充原始文献审查，未纳入实验对象。

2026-10-17补充：[SLICE作者页](https://xiaoyulics.com/papers/slice-image-watermarking/)列BMVC 2026 Oral，会议录状态尚未独立核查；arXiv仍仅v1。该作者页未给Code链接，固定CSI库仅注册TR/GS/SEAL，不能视为已有SLICE验证器；检索范围不构成无公开代码的穷尽证明。

## 代理迁移稳定性的先例（2026-10-18）

| 原文与阅读范围 | 方法边界 |
|---|---|
| [AdvPC，ECCV2020，§3 Eq.(5)–(6)、§4 Table1](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123570239.pdf) | 将AE重建后的分类损失纳入攻击，测试点云跨网络迁移；重建后有效性这一思路已有先例，不能直接称作新水印方法。 |
| [EOT，ICML2018，§2.1](https://proceedings.mlr.press/v80/athalye18b/athalye18b.pdf) | 变换分布上的期望目标与失真约束；变换鲁棒性与未知目标模型迁移须区分。 |
| [FIA，2107.14185v1，§4.1–4.2、Algorithm1](https://arxiv.org/html/2107.14185v1)；[ICCV2021出版页](https://openaccess.thecvf.com/content/ICCV2021/html/Wang_Feature_Importance-Aware_Transferable_Adversarial_Attacks_ICCV_2021_paper.html) | 随机掩码梯度聚合与重要特征加权；使用稳定梯度的通用思路已有先例，分类与水印目标不同。CVF PDF读取报错，公式按arXiv v1核对。 |

Jain v1 §8.2 Eq.(6)的DCT高频掩码及§11.3原预算已重新核对。[证据清单](../reports/transfer_stability_audit.json)保存四份实际获取文本的SHA256与阅读范围，源文件留在本地学术缓存，未复制整篇论文进入Git。没有执行这些新来源的代码。以上是有边界的定向阅读；[方法假设](METHOD_HYPOTHESIS.md)区分既有技术、基础数学条件和待检验的方向干预，不声称已证明新颖性。

## 原始噪声估计与参考信息（2026-10-18）

新增FARI（ICLR2026）、ROAR（ICCV2025）、EDICT、ReNoise、GS with EDICT及There and Back Again的定向核查，具体版本、阅读范围和源码行号统一见[参考信息审查](REFERENCE_INFORMATION_AUDIT.md)。FARI固定commit为c08064222366842bf962998506c4815b0a2cbe63，13文本文件blob核验、9个Python AST通过；未获取权重或执行入口。ROAR全文直接访问403，完整协议与代码仍unknown。

这些先例覆盖已知生成噪声监督、图像恢复/再生成、耦合数值求逆、迭代再加噪，以及平滑区域和早期步骤误差。它们不自动证明当前跨模型伪造设置的收益；也使单纯减小反演误差、训练一步反演器或发现纹理相关误差不足以作为本项目新贡献。
