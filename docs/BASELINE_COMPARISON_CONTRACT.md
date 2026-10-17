# 攻击比较契约：权限、预算与成功事件

版本：1；核查日期：2026-10-16。性质：源码与论文静态审计、后续比较设计；不是新实验预注册或启动配置。当前没有新方法的性能结论。

## 比较单位与信息权限

一个任务由预先固定的参考图片、内容要求、目标验证身份及攻击预算构成。攻击者获得参考图、输出内容要求、代理模型和自身随机状态；目标消息/密钥、原始噪声、内部反演、语义绑定参考与检测结果由评估端持有。参考有效性由评估端在攻击前确定，按预定规则形成任务集；筛除数量和原因同时报告。

比较按两条任务轨道分层：指定提示词重生成；指定载体内容保留。Reprompting 原生属于前者，Imprint/Jain 原生属于后者。若让重生成方法服务于载体任务，或先生成载体再运行优化方法，必须明确包装步骤并计入预算。这种任务适配不能混同原算法原样复现。

信息设置至少分别记录 `target_model_access`、`target_score_feedback`、`target_decision_feedback`、`generation_context_access`。检测反馈为零不意味着评估端不做检测；代理与目标具有相同架构也不意味着获得目标内部状态。源代码共享对象权限与算法实际读取的信息分别审计。

## 固定版本的比较表

| 方法 | 主要攻击输入与计算 | 反馈与输出 | 预算及比较限制 |
|---|---|---|---|
| Reprompting | 参考图代理反演，以新提示词从恢复噪声生成 | 固定入口对参考/候选做目标检测并记录；候选生成不消费分数 | 基础方法每任务一个输出；代理反演和生成步数分别计；原论文基本版每目标模型 1000 个参考 |
| Reprompt+ | 多提示词；GS 增加 bin resampling | 论文以同一参考的任一候选通过计成功；不是交付前的零反馈择优规则 | 论文每目标模型 100 个参考；TR 为 3 候选、GS 为 9 候选。与基础版样本数及预算均不同 |
| Imprint-Forgery | 参考图与载体图；优化载体 z0，使代理整段反演接近参考反演 | 固定代码周期验证，无基于检测值的活动早停分支；论文 §3.1 则描述按准确率停止 | 固定代码默认 steps=151、validation_steps=10。循环索引 0–150，每轮先优化再验证；最后索引150对应第151次更新。论文报告的150步与代码索引须分列 |
| Jain GS LFA | 参考图与载体图；优化像素，使代理 VAE mode/scaling_factor 表示接近参考，加像素 MSE | 核心函数固定迭代，无目标检测；外层有参考/载体/最终检测 | 入口默认 n_iters=15000，与 helper 默认10不同。GS 外层把 BA 按 <=0.05 累计 ASR，不能直接复用其打印值 |
| CSI code 模式 | 参考图 caption、语义锚点、LLM 提案；文本/视觉过滤后生成与检测 | 检测失败信息进入下一轮；可选成功早停默认关闭；第三层 CSW 禁用 | 默认60轮、每轮10提案、每参考最多5次生成。不是每个提案各生成5张；过滤淘汰与查询须分别计数 |
| CSI paper 模式 | 在上述流程加入指定修改意图及 CSW 过滤 | 第三层使用生成端保存的语义参考；同一检测反馈路径 | 更强的信息访问设置；库声明不等于原始论文实验档案，不能由此推定所有论文运行权限 |

上表来源：

- 原攻击固定 commit `ca68950cd7b53b8438a49580f134b2a0db28d778`：[Reprompting 入口](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L161-L205)、[Imprint 优化与验证](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_imprint_forgery.py#L186-L251)。论文 CVPR 2025 最终版 [§3.1、§4.2、§4.4/Table 3](https://openaccess.thecvf.com/content/CVPR2025/papers/Muller_Black-Box_Forgery_Attacks_on_Semantic_Watermarks_for_Diffusion_Models_CVPR_2025_paper.pdf)。源码默认参数本次通过 GitHub 固定 ref 重新读取。
- Jain commit `04433962437cbf08ad701b7b43124de07df0b666`：[入口参数](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/forgery.py#L75-L100)、[外层检测/汇总](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/forgery.py#L199-L253)、[优化核心](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/my_utils.py#L261-L299)。表示尺度约定详见 [评估契约 §5.1](EVALUATION_CONTRACT.md)。
- CSI commit `8723e362835a6a61efd11b61f677b3321face3fa`：[默认预算](https://github.com/ZhengGao-30/CSI-Attack/blob/8723e362835a6a61efd11b61f677b3321face3fa/csi/record.py#L352-L358)、[生成计数与反馈](https://github.com/ZhengGao-30/CSI-Attack/blob/8723e362835a6a61efd11b61f677b3321face3fa/csi/attack.py#L245-L379)。模式、参考和后端详见 [CSI 契约](CSI_INFORMATION_CONTRACT.md)。

## 必须分开的预算

每任务记录：提案数、实际生成图片数、交付图片数、代理反演次数/步数、优化更新数、攻击者可见检测查询数、评估端检测次数、GPU进程秒、失败/超时状态。优化中一次反演的前后向不能按一次普通生成记等价成本；相同更新数也不等于相同算力。

主设置交付一张固定哈希图片，攻击者可见检测查询数为0。若内部产生多个候选，生成数仍全部计入，选择规则须仅用允许信息且提前固定。多候选 any-of-k 单独报告为集合指标；不能把其中通过的图当作零反馈算法自行选出的输出。确定性、随机选择或代理分数选择均需在评估前声明，不能读完目标分数再决定。

Imprint 周期检查即使不驱动优化，也需要区分两种执行：原样共享控制器检查；隔离后评估端离线检查。后者是接口适配，仍须核对图像数值等价，不能仅据删除调用宣称忠实复现。固定输出应由预先声明的更新次数决定，不从各检查点择优。

## 成功事件与分母

对任务 i，令 R 表示参考在冻结验证身份下有效；O 表示按预算完成并交付合法产物；C 表示独立核查的指定内容达成；F 表示属于预定伪造范围；W 表示底层水印判定；D 表示完整防伪造规则对声明内容的接受。对于来源归属研究，另加 A 表示匹配指定受害者身份，不能用“任意有效水印”代替。

完整内容伪造成功事件为 `O AND C AND F AND W AND D`；声称用户归属伪造时还须 `AND A`。若官方 D 已含 W，记录这一逻辑关系。不存在独立内容认证功能的普通 GS 任务仅报告水印迁移事件，D=null。几何/SemBind 的完整规则尚未闭合，D=null，不产生完整成功率。

| 指标 | 分母与解释 |
|---|---|
| 原水印候选通过率 | 预定有效参考任务数；同时报告交付/失败数及原始BA。不能解释为完整防御绕过 |
| 完整单输出成功率 | 预先固定的有效参考任务数 N；产物失败计流程不成功并单列；内容/判定未知保持 unknown |
| 交付后条件通过率 | 仅已交付样本；用于诊断，必须连同交付率给出，不能替代上行 |
| any-of-k | 每个参考最多 k 次生成，任一候选满足相应完整事件；单列 k、查询权限及提前停止策略 |
| CSI campaign 原始 ASR | 至少一候选 success 的参考数 / 全部 victims；不先筛 genuine 检测有效参考 |
| CSI 单 run 默认 ASR | 通过检测数 / 到达检测器数；视觉/CSW过滤失败不在分母，与全部生成数不同 |

CSI 分母依据：[campaign.py:70–83](https://github.com/ZhengGao-30/CSI-Attack/blob/8723e362835a6a61efd11b61f677b3321face3fa/csi/campaign.py#L70-L83)、[record.py:523–558](https://github.com/ZhengGao-30/CSI-Attack/blob/8723e362835a6a61efd11b61f677b3321face3fa/csi/record.py#L523-L558)；候选 success 仅检测布尔值见 [record.py:224–226](https://github.com/ZhengGao-30/CSI-Attack/blob/8723e362835a6a61efd11b61f677b3321face3fa/csi/record.py#L224-L226)。这不能证明指定修改意图已达成。

未知处理：若 N 个预定有效参考任务中 s 个完整成功、u 个完整事件尚不能确定，可报告描述性范围 `[s/N, (s+u)/N]`，明确它不是置信区间；N=0 时为 null。参考有效性未知的任务另报，不悄然丢弃或混入条件分母。完整规则整体缺失时直接报告未可计算，而不是用上述范围装饰为性能结果。

内容核查标准需在正式实验前冻结：指定属性完成、应保留内容、允许改动范围分别判定；不能把与参考 caption 相似直接当作任务完成。[内容评审规则v1](CONTENT_ADJUDICATION.md)已定义逐项判据及unknown处理；具体任务判据尚未冻结，尚无评审结果，不新增任意阈值。

## 新文献对评估语义的约束

[SLICE, arXiv:2603.12749v1](https://arxiv.org/html/2603.12749v1) §3.1–3.3 将主体、环境、动作、细节分别绑定到潜变量分区；§3.3 区分 State I（来源与完整性通过）、State II（仍有来源证据但局部篡改被标记）、State III（无水印或严重损坏）。§6.1 的文字 ASR 定义使用 watermark present；定理4.4将该事件对应 State I 或 II。因此“仍识别水印”与“篡改未报警”必须分列；Table 1 的19%不能直接改写成 State-I 绕过率。逐样本状态映射、官方代码和工作点尚未核查，不能据文字差异断言实验有误。

此处仅将其纳入文献与成功事件审计，未指定为新的实验对象，也未实现该验证器。

## 当前可执行决定

1. 后续方法比较使用上述信息权限、任务轨道和预算字段；原算法结果保留原始分母，统一比较另起可追溯统计。
2. 当前开发样本只支持原GS与诊断结论；没有完整几何/SemBind成功标签。不能追认为正式确认集。
3. 下一项工作是核对可获得官方防御材料中的参考关联、完整判定及状态到表格的映射，形成一份可执行单样本契约；在此之前继续源码/材料核查，不以自造验证器填空。

本次新增模型进程0、GPU使用0、模型下载0。默认 SSH 认证失败，未取得服务器当前进程快照；现有757.62238442339 GPU进程秒为此前核验记录，本次未重新核算。定时任务保持关闭。

## 可执行记账检查

单输出字段和未知值处理已由`scripts/summarize_evaluation_events.py`实现，阶段07真实存档接入和复算见[报告](../reports/evaluation_events_20261017/report.md)。工具消费已有标签，不验证标签语义，不替代完整官方检测或权限隔离。
