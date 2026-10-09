# 官方 SEAL 基线路线与当前阻碍

2026-10-09（UTC）。建议先补齐 **SEAL 官方语义验证路径的组件与判定契约**。SD1.5/image CLIP/CSI 已退为工程诊断工具，暂停扩展攻击和调阈值；其 12 源诊断没有非退化 90% 源组接受点，不能据此判断实例真实性方法优劣。本轮仅做静态源码、缓存 metadata 与旧产物审计，官方端到端基线尚未执行。

[门槛配置](../configs/official_seal_baseline_gate.json)的执行预算为 0。G0–G2 是可审阅的未来计划，不授权或启动计算、下载或安装。已执行批次勘误见[时间线](execution_erratum.md)。

## 固定来源及两条检测路径

代码固定为 [Kasraarabi/SEAL@92d31b31](https://github.com/Kasraarabi/SEAL/tree/92d31b31b93a6e373fe88a584c640beafb68c6fa)。此前已读 arXiv v4/代码；ICCV 录用版段落/补充图仍需逐项对齐。以下是源码契约，不能直接等同于论文图表协议。

| 路径 | 注册/嵌入 | 待验图处理 | 输出/判定 |
|---|---|---|---|
| SEAL.py / image_transformations.compute_l2（语义） | SD2.1 草图→BLIP2 描述→微调句向量→官方 SimHash 噪声→标记图 | **重新描述待验图**、句向量和重建噪声；VAE mode→空文本逆扩散→与该语义噪声逐 patch 比较 | 1024 个 L2。SEAL.py 的 threshold=50 仅解析未读取；all_min_l2 只在内存中，无完整持久化/接受接口。 |
| image_transformations_exhaustive_tpr / roc_auc（穷举） | 仍用 BLIP2+微调句向量注册 | VAE mode→空文本逆扩散；每 patch 在 2^b=128 个候选噪声取最小距离；**检测函数无待验图 recaption** | tau=2.3、严格 L2<tau；TPR 脚本取同批 negative score 第99百分位为 count 边界，count≥boundary 接受，并报告实际 FPR。m_match=12 和 threshold=50 均未读取。 |

证据：[语义函数](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/image_transformations.py#L22)、[主入口](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/SEAL.py#L42)、[穷举](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/image_transformations_exhaustive_tpr.py#L25)、[经验边界与实际 FPR](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/image_transformations_exhaustive_tpr.py#L165)。ties/离散计数可使实际 FPR≠名义1%。源码未实现本项目独立 cal/test；复现原协议与增加独立校准须分别标记。

主要拟复现接口命名为 seal_semantic_recaption；穷举另命名 seal_exhaustive_presence。穷举 presence 通过不能代表语义绑定通过；穷举的注册阶段仍需 captioner/句向量。

## 必须冻结的组件契约

[静态核查 JSON](../reports/official_seal_route/source_contract.json)校验 10 个缓存文件与此前 SHA 清单，提取 AST 行号，没有导入官方模块。

- 主入口 SD 为 stabilityai/stable-diffusion-2-1-base、fp16、revision='fp16'；穷举默认 Manojb/stable-diffusion-2-1-base、fp16、未固定 revision。必须解析不可变权重身份。
- captioner：Salesforce/blip2-flan-t5-xl processor/model；句向量：kasraarabi/finetuned-caption-embedding，不能替换成 image CLIP 或基础 MPNet。注册/待验向量 L2 归一化。
- k=1024、b=7、seed42。[utils](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/utils.py#L481)用 Torch 随机超平面、tuple 的 SHA256→32bit key、设备上的 Torch.randn。此前组件比较已证实 CSI NumPy/Splitmix 实现不等价。
- [生成 __call__](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/modified_stable_diffusion.py#L41)默认50steps/CFG7.5/eta0，主入口沿用；scheduler.step 属于实际载入 scheduler。需保存配置、类及真实 timesteps，不能移植替代配置 DDIM。
- [预处理](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/utils.py#L41)：短边 Resize512+CenterCrop512+RGB tensor×2−1；非方图不同于直接拉伸。VAE mode×0.18215；inverse 空文本、guidance1、50steps。
- [官方 inverse](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/inverse_stable_diffusion.py#L102)实际读取 guidance，>1 双分支；此处1为单分支。此前 CSI guidance 变量未使用。custom backward_ddim 的 timesteps/alpha/sigma 依赖载入 scheduler，50参数不保证50次 UNet。
- [caption helper](https://github.com/Kasraarabi/SEAL/blob/92d31b31b93a6e373fe88a584c640beafb68c6fa/utils.py#L466)的 do_sample=False 形参未转发给 model.generate；需冻结真实 generation_config/processor/decode 默认，不假定形参保证确定性。
- set_random_seed 调用 CUDA.manual_seed_all；未来须在导入 Torch 前用指定 UUID 限制可见设备。当前未执行这些函数。保留官方安全检查器的实际配置/拒绝/结果，不更改安全设置。

## 缓存、许可和获取限制

许可/HTTP 观测来自[2026-10-07 清单](../reports/reproduction_audit)。本轮没有新查询 HF 或下载权重；旧401不能证明删除/永久不可用，元数据许可不是当前完整条款的替代。

| 组件 | 已观测版本/许可 | 当前状态 |
|---|---|---|
| 官方代码 | 92d31b31…；license=null，根树无 LICENSE/NOTICE/COPYING | 本地缓存文本可供阅读；代码使用/分发许可范围待明确。本次只发布派生契约/哈希/链接，不复制源码。 |
| 主入口 SD2.1 | stabilityai API 此前401；fp16 alias 未解析不可变 commit | 六个已知根未找到标准快照；访问/论文权重身份待核实。 |
| 穷举 SD2.1 镜像 | Manojb@0094d483a120f3f33dafbd187ea4aa60d10de75c；openrail++、gated=false | 未找到缓存；官方脚本采用镜像不证明与主入口/论文权重逐字节一致。 |
| BLIP2 | 0eb0d3b46c14c1f8c7680bca2693baafdb90bb28；MIT、gated=false | 未找到快照；processor/tokenizer/generation_config 须完整。两份 safetensors 合计15,769,954,544B。 |
| SEAL微调句向量 | 1f155d6a17f7a176d7d269f7ec04bcfa376ce297；license=null、gated=false | 未找到快照，model card 许可未明确；基础 MPNet 许可不能覆盖证明微调权重。437,967,672B；还需 modules/pooling/tokenizer。 |
| 官方 prompt corpus | Gustavosta/Stable-Diffusion-Prompts/train | 两个已知默认 datasets 根的检查未返回目标数据记录；数据版本/索引/分割待冻结。现有自有提示词只能另标工程验证。 |
| 现有 SD1.5 | snapshot 451f4fe16113bff5a5d2269ed5ad43b0592e9a14 | stat确认 UNet/VAE/text encoder。只能支持替代诊断；即使 VAE 大小与镜像相同也不能证明同一权重。 |

[04:32:59 缓存核查](../reports/official_seal_route/cache_readonly.json)范围仅六个已授权根、深度≤3 名称/stat：无目标模型名或标准 snapshots，不代表整机任意别名/深层目录不存在。[04:36:21 SD1.5 核查](../reports/official_seal_route/available_cache_readonly.json)核对三个小配置 SHA、三份权重存在/大小，没有重新哈希大型权重。

所选 SD2.1 镜像 fp16 核心权重2,580,061,174B，与 BLIP2、句向量合计 **18,787,983,390B（18.79GB）**；不含额外组件/安装/缓存，不是当前允许下载量。

包 metadata：Torch2.3.1+cu121、Diffusers0.29.2、Transformers4.41.2、Accelerate0.30.1、NumPy1.26.4、Pillow10.4、torchvision0.18.1+cu121、datasets2.18.0；sentence-transformers/wandb 未安装。官方 requirements 分别为 Diffusers0.20.2、Transformers4.47.1、Accelerate1.2.1、sentence-transformers3.3.1 等，兼容性未验证。stock 入口无条件导入/初始化 wandb；未来可做离线持久化适配器，但须证明数值路径一致。当前未安装或执行 setup.sh，其系统安装/force-reinstall 不应直接作用共享环境。

## 完整端点的必要输出

register/verify 适配器尚未实现。register packet 需绑定自有 source、draft/marked RGB、真实 caption/embedding/key/noise、dtype/seed、模型/代码身份、生成 scheduler 和实际末端 latent。verify 必须保存：

1. 请求/图像字节/RGB、decode/Resize/Crop、processor 输入及异常。
2. **待验图** caption、generation_config、微调句向量/norm、官方 key/noise；不能借注册 caption 或 oracle 噪声当 native。
3. VAE input/mode/scaling、空文本 embedding、真实 timestep/alpha/sigma、UNet input/output、更新和最终反演噪声。
4. 全1024 L2、比较符/count、事先冻结 scheme-specific 判定、accept/reject/error、实际正常/negative 接受率。
5. semantic_recaption/exhaustive_presence 路径标识。SEAL这些原生端点没有 payload、签名、credential、编辑policy或实例认证输出，记为 native 不适用；项目扩展仍未实现，不能默认缺失字段成功。

注册噪声/真实末端 latent 的 oracle 另列，不计 native 流程。“完整官方验证”是待验 RGB 到指定 SEAL 判定，不等于候选课题 policy-aware 实例认证。

## 最小门槛与停止条件

| 门槛 | 未来工作/验收依据 | 当前状态 |
|---|---|---|
| G0 资产与契约 | 权重身份/权限、代码许可、全configs/processor/tokenizer、论文路径和阈值/比较符、数据；独立离线环境；显式预算/设备UUID/保存接口 | **阻塞**：3类快照缺失，许可范围、原SD2.1访问/身份、缺包/版本、语义最终判定和官方数据尚未解决。 |
| G1 最多1官方源 | G0和未来预算通过后：draft→caption→微调embedding→官方noise→marked→待验recaption→inverse→L2；逐阶段对齐官方函数，预声明dtype容差，保存拒绝/失败，不循环重试 | **未执行**。可先核对作者提供的绑定中间产物，但它不能代替新端到端运行。 |
| G2 最多3开发源 | 与旧cal/test不同family/prompt/seed；P0 original、JPEG70/90 sub2、bicubic0.5/0.75恢复512；评分前事实审查；每源draft negative、完整native和全部失败；原图可接受、negative可区分的事先声明工程门槛成立才继续 | **未执行、无预算**。3源不能估可靠FPR/正常接受率；绑定错误/退化则停，不扩攻击或反复调阈值。 |

G2复用 unmarked draft 作工程negative时，拟上限6生成/18反演/21caption（3注册+18待验），需保存真实 scheduler 调用数；这是工程检查，不等于官方 next-prompt negative 协议，论文复现需另冻原协议。所有拟预算都不是本轮执行授权。

之后才规划独立 cal/test，按[问题定义](problem.md)的正常接受率、置信区间、合法编辑和完整自适应口径比较。旧90%源组诊断与正式协议分开；不能从无效parser推断threshold50，不能移植CSI patch≤2/count10。开发成功/oracle改善/静态核查不能充当安全贡献或CCF-A新颖性。

**无下载可完成**：源码/AST/许可记录核查、旧产物CPU文件审计、接口字段与协议设计。现有缓存仅能支撑SD1.5替代诊断；缺captioner/微调句向量/SD2.1，无法无下载完成新的官方register、recaption或端到端验证。本轮保持此边界。
