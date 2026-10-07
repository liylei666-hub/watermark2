# 公开实现与完整验证器可行性核查

核查日期：2026-10-07 UTC。基于提交 `17c326da430ed079a16768c9cb92753e2d39de0b` 继续；该提交的 CPU 实验原始记录保持不变。本轮执行的是公开代码、数值组件和记录接口核查，真实水印图像实验数为 **0**。

## 结论与可复核范围

已找到 SEAL、SemBind 和 CSI 的作者公开仓库，固定版本并下载 152 个小型文本文件，共 830,430 字节。没有下载模型权重或图像集合。三仓库当前树及 GitHub releases 均未提供本轮可用的、逐图带配置/密钥/反演结果的真实实验包；仓库中的 teaser、logo、展示拼图不能作为独立测试样本。SemBind 笔记本保存输出数为 0。此结论限于固定版本、README 外链和 releases 的检查范围，不断言作者没有其他数据。

| 方法 | 固定代码与许可 | 完整流程与阻碍 |
|---|---|---|
| SEAL | [92d31b3](https://github.com/Kasraarabi/SEAL/tree/92d31b31b93a6e373fe88a584c640beafb68c6fa)；根目录无许可证，GitHub license=null | 生成草图→BLIP2 描述→微调句向量→SimHash 噪声→生成水印图→重新描述/反演→分块距离。官方组件已做 CPU 数值检查；本机缺对应生成、描述、句向量模型和真实输出包。 |
| SemBind | [337c9f9](https://github.com/XinZhang1999/SemBind/tree/337c9f90a150157ac1d410208ae20e6530ca8cdd)；代码 MIT | notebook 演示 DINOv2 giant CLS→学习哈希；另有反演和 PRC 工具，但未找到把 masker、bind/unbind、密钥、检测阈值接成完整评估的公开入口。README 明示逐步发布。本地 DINOv2 small 的维度/权重不匹配。 |
| CSI | [8723e36](https://github.com/ZhengGao-30/CSI-Attack/tree/8723e362835a6a61efd11b61f677b3321face3fa)；Apache-2.0 | 作者 NOTICE 明示为整理后的库，非原实验目录归档；真实后端需要扩散、BLIP2、指定句向量、LLM 提案或已有 replay。已检查官方测试和模拟接口；没有用模拟 ASR 支持真实结论。 |

代码来源、文件大小与 SHA-256：[SEAL/SemBind 清单](../reports/reproduction_audit/public_code_inventory.json)、[CSI 清单](../reports/reproduction_audit/csi_code_inventory.json)。上游源代码仅缓存在忽略目录 `runs/reproduction_audit/`，本仓库提交清单、核查程序和结果；许可不明的代码没有被重新发布。

## 已执行的轻量验证

[组件结果](../reports/reproduction_audit/component_checks.json)记录环境、退出码与运行时；[CSI 测试日志](../reports/reproduction_audit/csi_pytest.stdout.txt)和[模拟日志](../reports/reproduction_audit/csi_simulated_selftest.stdout.txt)保存原始输出。首次缺 pytest 及随后 Windows GBK 解码失败的记录均独立保留；在本仓库忽略目录安装 pytest 8.4.2 及轻量依赖，启用 PYTHONUTF8=1 后，CSI 81 项测试全部通过（18.56秒）。模拟流程通过（2.43秒）；这些均不构成真实水印复现。没有修改系统环境。

SEAL 只提取并执行五个已审阅函数的 AST 定义，避免执行入口和全模块副作用。对确定性 768 维数值输入，生成 `(1,4,64,64)` 噪声两次完全相同；仅给第一个 2×2×4 块加 1，分块距离返回一个变化块，L2=4。此处输入不是图像语义，测试验证函数和块索引，不测语义质量或抗伪造率。

相同向量、seed=42 和形状下，官方 SEAL 与 CSI 的噪声 RMSE=1.4193096723，字节不相同。CSI 使用 NumPy/SplitMix64；本次固定的 SEAL 使用 PyTorch/SHA-256。CSI 文档还描述更早的 Python 内置 hash 路径，不能据此认定与当前官方版本完全一致。**官方 SEAL 图像不能直接交给 CSI 重实现噪声流判定；二者必须分别注册、生成和校准，或先证明兼容。** 此数值差异不构成任何攻击成功结果。

SEAL `SEAL.py` 默认 k=1024、b=7、seed=42，执行两次生成及反演；`--threshold`、`--save_each` 等参数在该入口未形成完整判决/证据输出。`generate_caption` 默认设备仍为 CUDA，而调用处没有显式传 CPU；入口还启用 wandb。后续适配需记录设备、精度、scheduler、caption 参数、patch tolerance 与最终 match 阈值，禁用联网日志并补齐逐图输出。公开固定 seed 是实现配置，不应表述为已证实的秘密密钥安全性。

CSI 默认 `code` 与可选 `paper` 模式不同。作者明确未以 `paper` 模式完整组合产生公开实验行；README 的 49/60 和论文的 81% 仍是作者报告，当前树缺对应原始记录，本轮没有重算这些数值。其校准主要控制未水印负样本 FPR，不能替代本项目合法编辑下的接受率校准。后续必须补 P0 编辑、事实有效性和完整判决，而非直接复用 ASR 表。

## 权重与运行预算

下表为公开元数据字节数，**不是已下载体量**；[模型版本/文件清单](../reports/reproduction_audit/model_inventory.json)保留查询结果。GB 按 10^9 字节计。

| 部件 | 选定文件体量 | 状态 |
|---|---:|---|
| SD2.1 Base，CSI 指定的 Manojb 镜像，三部件 fp16 safetensors | 2,580,061,174 B | openrail++ 元数据；官方 stabilityai 路径匿名请求401。镜像身份不等于已证明与论文 checkpoint 字节相同。 |
| BLIP2 flan-t5-xl，两片 safetensors | 15,769,954,544 B | MIT 元数据；未下载。读取后可转换精度，但公开下载字节仍如此。 |
| SEAL 微调 caption encoder | 437,967,672 B | 模型卡许可字段为空，需核查使用条款；未下载。 |
| DINOv2 giant safetensors | 4,546,005,432 B | Apache-2.0 元数据；未下载。 |
| SemBind masker Google Drive checkpoint | 886,343,333 B | [公开页面元数据](../reports/reproduction_audit/sembind_checkpoint_metadata.json)；文件级许可未单独确认，未下载。 |

SEAL/CSI 所列权重合计 18,787,983,390 B（18.79 GB），还不含配置/运行缓存；CPU float32 权重内存按模型结构约需 21.37 GB，激活和加载峰值另计，因此不能把下载大小当作峰值 RAM。SemBind 的 masker 在 meta device 上计数得到 221,444,096 参数、886,292,632 字节 float32 state tensors，与公开 checkpoint 体量相符；这不是加载权重成功。其 DINO+masker 约 5.43 GB，若从头生成还需扩散栈。

旧本机 SDXL 缓存只有部分文本编码器和 UNet，缺 VAE/完整 tokenizer，且模型不同，不能充当上述 SD2.1。SSCD、CLIP 和 DINO small 也不能替代这些验证步骤。本轮不执行 GPU、训练或付费 LLM，不估造秒/图。一次 SEAL 源图注册至少两次50步生成；每个待验版本另需50步反演及 caption，完整48源 P0轮需约96次生成、240次反演（原图加4合法变换），攻击预算额外计算。精确时长须在已批准模型栈上先实测单图。

## 可继续的最小路径

优先取得小型、可核对的真实输出包，而不是继续合成标牌。每个样本必须包含原始水印图、来源/使用许可、注册 key ID/参数、checkpoint 和代码 SHA、反演 latent、重新提取的 caption/embedding 或 masker bits、所有阈值及最终判决；CSI 还需原始提案 replay 和全部失败尝试。保存输出重算只能支持数值阶段，不等同于重新执行 caption/反演。

第一门槛是最多3张真实注册图的逐步骤一致性检查；不汇报攻击率。只有图像与完整验证路径成立，才冻结独立开发/校准/留出来源，进入原计划48源（16/16/16），按相同合法接受率比较。3张检查样本不得再进入校准或留出。权重、许可或图像/密钥缺任一项，状态保持 blocked；不得以随机哈希模型或模拟 backend 补齐。

离线可重跑：

```bash
python scripts/fetch_public_audit_sources.py
# 仅在缺pytest时：python -m pip install --target runs/reproduction_audit_dependencies pytest==8.4.2
python scripts/audit_public_implementations.py
```

下载脚本仅允许清单中的固定提交文本，单文件≤200 KB、总量≤1 MB，并校验 SHA-256；不下载模型或图像。真实运行尚未启动。

## 新颖性更新

[SLICE, arXiv:2603.12749v1](https://arxiv.org/abs/2603.12749)已明确将 subject/environment/action/detail 分别绑定到 latent 分区，并区分完整、局部篡改、无水印三种判决。其 §4 界限依赖语义稳定/分离及条件独立等假设；不能直接套用于自适应编辑。本轮确认其为公开预印本，未核实正式录用，未复现实验。分因子绑定与局部判决已形成直接先行工作，因此继续保留“允许编辑策略、匹配接受率、完整自适应评估”为待验证协议问题，尚不主张新方法贡献。
