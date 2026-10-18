# 代理交付目标与既有方法的对应契约

核查：2026-10-18 UTC。结论：生成器约束下的代理反演匹配是可定义的研究对象，但目前没有建立独立方法贡献或跨模型迁移保证。阶段25已证明，本组参考噪声估计的改善不等于最终图像的普通GS改善。当前采用源码核查和四项合成CPU检查，没有新增模型运行。

## 变量与实际计算路径

设参考图为 r，代理VAE编码/解码为 E_s、D_s，DDIM潜变量反演为 R_s，完整图像反演 F_s=R_s∘E_s，提示词条件生成器为 G_s(u,p)。Q 表示浮点像素截断、转8位像素和保存后读取；PNG对已经量化的像素是无损存储。下面的范数可按元素数归一化，不影响对应关系。

| 目标 | 表达式 | 变量与含义 |
|---|---|---|
| 官方Imprint原生目标 | ‖R_s(z₀)−F_s(r)‖² | 优化cover初始化的VAE潜变量z₀；包含UNet反演，梯度循环内不包含D_s→Q→E_s |
| 图片交付目标 | ℓ(x)=‖F_s(Q(x))−F_s(r)‖² | 在实际交付图片上定义代理匹配；尚不是目标水印判定 |
| 生成器参数化的交付目标 | ℓ(G_s(u,p)) | 优化生成器输入，候选被限制在该生成器、提示词和参数化的可达集合 |

生成和反演的条件必须分别记录。现有基线生成使用指定提示词、CFG7.5；反演使用空提示词、CFG1.0，均为50步。不能把这两个过程当作同条件的精确互逆。

## 固定源码与论文对应

Imprint/Reprompting全部源码结论对应完整commit **ca68950cd7b53b8438a49580f134b2a0db28d778**；源码SHA256及核验范围见[证据记录](../reports/26_delivery_objectives/source_audit.json)。

| 方法 | 已有机制及证据 | 与上述目标的关系 |
|---|---|---|
| Imprint-Forgery | [run_imprint_forgery.py:119–145](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_imprint_forgery.py#L119-L145)初始化cover潜变量和参考反演；[186–202](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_imprint_forgery.py#L186-L202)反演MSE、反向传播及可选掩码；[205–249](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_imprint_forgery.py#L205-L249)解码、目标检测和记录在更新之外 | 反演匹配已经存在。补入解码/再编码路径属于明确的计算路径变化，其收益、新颖性和迁移须另证。所读循环没有按目标分数提前停止或选择候选；共享程序仍持有评估权限 |
| Reprompting | [run_reprompting.py:151–190](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L151-L190)用代理反演参考，按可选resample规则处理后用新提示词生成，再独立验证 | 以参考反演噪声为生成起点已有先例；串接Imprint必须作为组合基线比较 |
| Jain单图匹配 | commit **04433962437cbf08ad701b7b43124de07df0b666**，[Gaussian-Shading/my_utils.py:261–299](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/my_utils.py#L261-L299)；VAE表示MSE加像素失真项，可选低频约束，像素梯度更新后截断。论文[2504.20111v1 §4.1、§4.3](https://arxiv.org/html/2504.20111v1) | 优化不包含UNet反演；需要按同任务、实际失真和计算预算比较，而非只按迭代数 |
| PnP | [2506.06018v1 §3.1、§3.2.2 Eq.(1)–(4)](https://arxiv.org/html/2506.06018v1)：参考图估计噪声与cover条件共同驱动预训练再生成模型，再解码 | 将生成器和参考噪声组合并非空白。此前匿名源码获取403；本轮阅读论文，不宣称公开完整代码已核验 |
| 已知噪声监督反演 | FARI的标签、训练和移除权限见[参考信息审查](REFERENCE_INFORMATION_AUDIT.md) | 自生成图像配对原噪声监督已有先例；阶段24/25的固定线性诊断不能仅凭监督来源主张创新 |

Imprint编码/解码细节：[utils/imprint_utils.py:211–244](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/imprint_utils.py#L211-L244)中latent_to_pil使用no_grad、detach、VAE解码、clamp与to_pil_image；pixel_to_latent采用VAE后验均值和scaling_factor。因此不能把原生更新称为完整PNG交付路径求导。

## 数学边界与已执行检查

对可微的连续替代目标，链式法则给出 ∇_uℓ(G_s(u))=J_Gᵀ∇_xℓ。若G_s局部二阶可微，小步更新在图像空间近似为 Δx=−ηJ_GJ_Gᵀ∇_xℓ+O(η²)。这改变方向与可达集合，不等于与像素优化具有相同轨迹或相同最优解，也没有引入目标模型的信息。即使像素损失非零，生成器限制也可能产生参数梯度为零的点。

如果另行假设**相同条件下精确互逆** F_s^p∘G_s^p=id，且忽略VAE和量化损失，则循环匹配退化为 ‖u−F_s^p(r)‖²；取u=F_s^p(r)已经零损失。该条件在当前生成/反演配置中不成立；这是检查机制论证的理想极限，不是实际扩散结果。

Q在量化格内部局部常数，边界处通常不连续。连续替代、直通估计或其他反向近似必须声明各自定义；其梯度不能称为真实8位交付函数的精确梯度。阶段21有限步长核验没有建立真实扩散导数的有效性，本轮合成代数检查也不补足它。

| 冻结CPU检查 | 结果 | 能说明的范围 |
|---|---|---|
| 线性生成器重参数化 | 链式梯度最大差1.2651e−9，小步诱导更新误差1.2490e−16 | 合成线性计算一致 |
| 同条件精确逆 | 复合/直接损失均0.725，参考起点损失0 | 理想假设的代数退化 |
| 秩受限生成器 | 损失1但参数梯度0 | 可达集合造成驻点的反例 |
| 示例8位量化 | 格内差分0、连续梯度0.802；边界差分随步长敏感 | 连续替代与实际离散交付有区别 |

[冻结协议](../protocols/26_delivery_objectives_cpu.json)、[代码](../scripts/check_delivery_objectives.py)、[原始CPU输出](../reports/26_delivery_objectives/cpu_checks.json)。这些是基础代数与合成反例，不能作为论文方法创新或模型实测。

## 后续机制的准入条件

下一项工作先形成一份**代理可观测量→交付后迁移预测**的可证伪契约：说明该量包含什么信息、为何超出已有反演匹配、在何种模型差异下预计有效，以及什么结果会否定它。未能提出这一预测时，不启动端到端损失优化试验。

候选机制必须同时给出：允许输入和离线成本；相对Reprompting、原生Imprint、交付路径Imprint及其组合的唯一受控变化；独立提示词/种子/身份划分；全部预定候选的交付与内容端点；失败后关闭规则。目标密钥、消息、原噪声、RNG、内部反演和分数不得用于选择机制参数或候选。候选先封存哈希再评估，现有共享OS流程不声称权限隔离。

阶段25两组普通GS均8/8通过但消息准确率下降，说明二值通过存在饱和；应同时报告预定连续端点与完整判定，不调整阈值制造收益。完整几何/SemBind仍缺官方可运行协议；其接受状态保持unknown。阶段23–25已关闭开发组不补样，不把目标标签再用于拟合。

## 本轮定向文献筛查范围

已阅读原始攻击论文[2412.03283v2 §3.1–3.3](https://arxiv.org/html/2412.03283v2)和上述Jain/PnP章节。另查看[OptMark摘要](https://arxiv.org/abs/2508.21727)的推理时水印嵌入优化、[GhostVAE摘要](https://arxiv.org/abs/2608.00543)的VAE后门权限，以及[CSGuard 2605.01479v1 §3.2、§4](https://arxiv.org/html/2605.01479v1)的压缩感知防伪造机制；这些阅读范围不构成代码、结果或部署协议复现。CSGuard官方完整实现未在本轮有限检索中确认，保持unknown。

SEAL会议补充材料的搜索索引可见，但[最终PDF](https://openaccess.thecvf.com/content/ICCV2025/supplemental/Arabi_SEAL_Semantic_Aware_ICCV_2025_supplemental.pdf)直接访问仍返回403，未读取全文；不据索引片段补全正式协议。这是定向排重，不能声称穷尽最新工作或已经证明新颖性。
