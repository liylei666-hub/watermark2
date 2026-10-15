# 文献与实现覆盖

核查日期：2026-10-16（Asia/Shanghai）。这是面向研究决策的定向检索，含引用追踪与版本核查；不是穷尽式系统综述。只以论文原文、出版方及作者仓库支持技术结论。阅读范围逐项列出，未作任何用户已阅读声明。

## 直接相关材料

| 材料与核查版本 | 本次/既有阅读范围 | 与本项目的关系及限制 |
|---|---|---|
| [Müller et al., Black-Box Forgery Attacks, CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/papers/Muller_Black-Box_Forgery_Attacks_on_Semantic_Watermarks_for_Diffusion_Models_CVPR_2025_paper.pdf) | 阶段 01 源码审计、阶段 02–05 复现；本轮 GS 源码复核 | Reprompting/Imprint 是必要基线。当前复现仅覆盖其部分条件。 |
| [Jain et al., Forging and Removing Latent-Noise Diffusion Watermarks Using a Single Image, 2504.20111v1](https://arxiv.org/html/2504.20111v1) | 摘要、§1、攻击概念；最新 arXiv 元数据为 v1 | 单参考图、代理 VAE 的潜表示匹配已存在；简单增加 latent consistency 不能直接宣称首创。未完成代码级权限审计。 |
| [Lee et al., Geometric Distortion Perspective, 2606.29807v1](https://arxiv.org/html/2606.29807v1) | 阶段 03 源码；本轮 §4、附录 B、C.1–C.4 | [PMLR 确认 ICML 2026](https://proceedings.mlr.press/v306/lee26bm.html)。结论依赖假设及参考原始潜变量；公开实现缺项。C.3 讨论 Reforge，未纳入实验比较。 |
| [Arabi et al., SEAL, ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/papers/Arabi_SEAL_Semantic_Aware_Image_Watermarking_ICCV_2025_paper.pdf) | 摘要、理论假设及攻击讨论片段、作者仓库目录 | 内容绑定防伪造已有先例，包含更强模型访问的攻击设置。须与本项目的受限代理设置分列。尚未完整复现。 |
| [Zhang et al., SemBind, 2601.20310v1](https://arxiv.org/html/2601.20310v1) | §2.3、方法概述、附录 D；作者 README 与目录 | 私有 semantic masker；附录有代理训练与像素覆盖实验。不能说现有防御没有自适应评估；这些组件实验也不等于穷尽所有端到端攻击。作者仓库标注 ICML 2026。 |
| [Gao et al., CSI, 2602.21593v1](https://arxiv.org/html/2602.21593v1) | §2、§3、最新摘要页 | 已做语义保留编辑、候选过滤；[元数据](https://arxiv.org/abs/2602.21593)标注 WWW 2026 Short Paper。CSW 分数及噪声获取权限需要核查，不能直接视为本项目零目标反馈设置的等价方法。 |
| [Nakra et al., Understanding Semantic Perturbations, 2603.27513v1](https://arxiv.org/html/2603.27513v1) | §2.3、§3、评估概述及版本页 | 研究语义改变与水印鲁棒性，目标包括降低可检测性；这是移除/鲁棒性方向，不能把其成功率混作伪造成功率。 |
| [Thietke et al., Towards A Correct Usage of Cryptography, 2503.11404v1](https://arxiv.org/html/2503.11404v1) | §1–2 与配置讨论 | GS 的随机化、nonce 与多图设置早已有分析。固定密文对应相同符号模式是配置性质；当前 CPU 结果不作为新密码学发现。 |
| [Lukovnikov et al., Layout Control, WMARK 2025](https://openreview.net/pdf?id=pFMNK403AH) | 题名、摘要、作者出版记录 | ControlNet 对 TR/GS 的影响已有工作。布局保留作为候选策略前仍需全文/代码核查。 |
| [Yang et al., Gaussian Shading++, 2504.15026v2](https://arxiv.org/abs/2504.15026) | 最新摘要、版本史 | 关注随机化种子、密钥管理与公开验证；不能将 GS++ 与当前固定 GS 配置合并报告。全文协议待查。 |
| [Liu et al., PAI, ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/51e2aaa731e8a5edfbda95fd8bd8948b-Abstract-Conference.html) | 出版方摘要与方法概述 | 轨迹层密钥耦合是另一类防伪造机制。仅扩大目标数量不足以形成方法贡献；具体实现待审计。 |
| [Tamim et al., Forging Tree-Ring, 2609.12909v1](https://arxiv.org/abs/2609.12909) | 最新摘要和版本史（2026-09-11） | 近期已有 Reprompt 复现与检测器插桩报告。说明“复现加保存中间量”已有近邻；尚未精读全文或复算其数值。 |
| [Feng et al., IRIS, 2608.03539](https://arxiv.org/abs/2608.03539) | v1 §5.2；最新版本状态 | **v2 于 2026-08-26 撤回，备注 Substantial revisions。** v1 仅作历史线索；不纳入有效 SOTA、已证实防御或实验目标清单。 |

另有边界材料：[随机密钥选择防伪造](https://www.toluwaniaremu.com/wm-forgery)涉及多样本/多密钥设置；[GhostVAE 的 USENIX 页面](https://www.usenix.org/conference/usenixsecurity26/presentation/liu-jinyuan)本轮直接读取超时，先前检索只定位题名。后门能力不同于本项目的代理攻击，未将它列为直接比较基线。

## 官方实现可用性

| 仓库 | 核查位置 | 本轮实际检查 | 仍待验证 |
|---|---|---|---|
| [semantic-forgery](https://github.com/and-mill/semantic-forgery) | `ca68950cd7b53b8438a49580f134b2a0db28d778` | 现有归档与源码；历史复现 | 更广模型/提示词/密钥条件 |
| [geodistort-wm](https://github.com/chengyi-chris/geodistort-wm) | `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622` | 公开 HEAD 与原审计版本相同 | 缺失模块、判定及参考关联；许可证未发现 |
| [SemBind](https://github.com/XinZhang1999/SemBind) | `337c9f90a150157ac1d410208ae20e6530ca8cdd` | HEAD、根目录、README、GitHub 许可证元数据 MIT | notebook 与论文等价性、masker checkpoint、DINOv2 等依赖；未下载 |
| [SEAL](https://github.com/Kasraarabi/SEAL) | `92d31b31b93a6e373fe88a584c640beafb68c6fa` | HEAD、根目录、README 摘要；存在攻击脚本 | 完整入口、阈值、依赖与许可文本。GitHub license 元数据为 null，不等同已证实无许可证 |
| [Jain 单图方法](https://github.com/anubhav1997/watermark_forgery_removal) | 本轮未固定 commit | 作者论文链接、仓库存在、默认分支 main | 方法权限、完整代码、许可及运行成本 |

这些检查未安装依赖、下载权重或执行任何上游入口。代码“存在”和代码“可忠实运行”分别记录。

## 检索范围与未覆盖项

本轮查询包括：`diffusion semantic watermark forgery geometric adaptive attack 2026 arxiv`；`semantic watermark forgery 2026` 加 CVF、OpenReview、USENIX 域名；2026 September/October 增量检索；各篇准确题名、作者代码、版本史；由 CSI/几何/SemBind 参考文献追踪单图攻击与密码学讨论。

没有声称检索无遗漏。尚未完成：全部引用和引用它们的新论文的穷尽追踪、所有预印本与最终会议版逐页比对、新基线代码权限审计、各目标的完整可执行评估协议。检索未明确找到更近论文不代表该论文不存在。最晚核实的直接相关新条目为 2026-09 的复现论文；研究决策以当前列出的证据范围为准。
