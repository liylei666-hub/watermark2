# 12新源校准/测试工程批次：未得到可用工作点

2026-10-08执行，2026-10-09补齐发布。固定SD1.5 + image CLIP / CSI SealCore替代配置，12个新源、6校准/6测试，原4个开发源不进入本批。按预定90%源组正常接受目标，规则选择计数阈值0，因为c04正常JPEG70为0匹配。**这是退化判定：任何非负计数都接受，没有得到可用工作点。** 不把6/6校准接受写成成功，也不报告该配置的有效攻击结果。

## 冻结协议与审核

[配置](../configs/sd15_clip_calibration.json)在生成前固定12个ID、提示词、种子、主对象类别及分组。家族按主要对象类别定义，各ID/类别/种子互异；这是人为选取的工程样本，不是IID总体样本。允许版本为original、JPEG70、JPEG90（subsampling2）、BICUBIC缩放0.5/0.75后恢复512；实际可见主体事实须保持。所有12源保留，24次生成，无重试或替换。

[评分前审核](../reports/calibration_engineering/prepare/visual_review.json)于17:55:55Z冻结60张正常图像SHA。Codex检查实际主体保持，非独立人工标注。提示词偏差保留：猫站立、鞋面白色/鞋底黄色、小提琴黑白特写、表盘偏暗、海滩多棵树。它们限制语义事实数据集用途；本批测实际图像的正常处理稳定性。[校准网格](../reports/calibration_engineering/prepare/calibration_review_grid.png)和[测试网格](../reports/calibration_engineering/prepare/test_review_grid.png)在评分前生成。

patch容差2.0、k1024、b7及公开开发key42不变。每个cal源取5版本的最低匹配数，选使ceil(0.9×6)=6个源组接受的最大非负整数计数阈值。仅cal正常分数参与选择。阈值于17:57:21Z写入[operating_point.json](../reports/calibration_engineering/calibration/operating_point.json)，测试模型阶段始于17:58:42Z，并绑定该文件SHA。测试和负例不选阈值，不重调。

## 全部正常计数

| 源 | 分组 | original | JPEG70 | JPEG90 | resize0.5 | resize0.75 | 最低 |
|---|---|---:|---:|---:|---:|---:|---:|
| c01 brick_house | cal | 89 | 53 | 69 | 22 | 60 | 22 |
| c02 tabby_cat | cal | 317 | 297 | 275 | 322 | 329 | 275 |
| c03 sailboat | cal | 350 | 167 | 314 | 244 | 333 | 167 |
| c04 sneaker | cal | 116 | 0 | 1 | 10 | 21 | 0 |
| c05 violin | cal | 227 | 69 | 122 | 119 | 175 | 69 |
| c06 bicycle | cal | 320 | 183 | 282 | 150 | 271 | 150 |
| t01 snow_forest | test | 329 | 254 | 290 | 224 | 291 | 224 |
| t02 butterfly | test | 192 | 33 | 60 | 88 | 132 | 33 |
| t03 pocket_watch | test | 309 | 143 | 236 | 232 | 285 | 143 |
| t04 library | test | 189 | 72 | 125 | 74 | 149 | 72 |
| t05 robot | test | 91 | 20 | 43 | 30 | 64 | 20 |
| t06 palm_beach | test | 268 | 226 | 206 | 194 | 271 | 194 |

[计数图](../reports/calibration_engineering/stability_counts.png)、[SVG](../reports/calibration_engineering/stability_counts.svg)、[源级CSV](../reports/calibration_engineering/source_counts.csv)和[负例CSV](../reports/calibration_engineering/negative_counts.csv)由审计结果生成。固定回退阈值10下，cal源组5/6通过，test源组6/6通过；cal JPEG70及JPEG90分别5/6通过，其他正常版本均6/6。源组要求该源5版本全通过，30个版本不是30个独立源。这些是观察计数，不能推断总体正常接受率。

6个test未加水印草图计数全部0：阈值10均拒绝，退化阈值0均接受。草图来自同生成器，并作为注册特征来源，不能代表广泛无水印分布或证明低FPR。另以各test原图反演对下一test图的query-derived参考噪声作CPU循环交换，计数为80/33/85/33/20/99；均≥10。它是人为错误参考的R1式诊断，非原生输入流程、实例凭证测试或伪造成功事件；不能将6/6误写为原生FPR。

## 保存阶段稳定性分解

[诊断脚本](../scripts/diagnose_calibration_stability.py)仅使用已有数组，所有源按固定patch容差分解，原注册latent只作oracle。[数据](../reports/calibration_engineering/stability_diagnostic.json)包含cosine、bucket一致数、注册latent接近数及距离摘要。c04：

| 版本 | native匹配 | oracle注册匹配 | query/draft bucket一致 | E∩D | A在E外 |
|---|---:|---:|---:|---:|---:|
| original | 116 | 614 | 209 | 116 | 0 |
| JPEG70 | 0 | 1 | 181 | 0 | 0 |
| JPEG90 | 1 | 11 | 200 | 1 | 0 |
| resize0.5 | 10 | 34 | 213 | 10 | 0 |
| resize0.75 | 21 | 138 | 215 | 21 | 0 |

E为query/draft bucket相同，D为recon到registered_z的patch L2≤2，A为native patch匹配。JPEG70 oracle接近patch由614降至1，而bucket一致只由209降至181，显示潜变量恢复损失是该例重要环节。完整因果位置仍需预处理/VAE/反演轨迹控制，不能凭CLIP cosine直接认定语义稳定或归因到单个组件。原注册latent不进入原生接受判定。

## 执行、证据及限制

仅GPU7 UUID隔离、逻辑cuda:0，缓存离线加载，无训练、下载权重或付费。三阶段900秒上限均未触发。

| 阶段 | Python PID | UTC起止 | 模型阶段秒 | 生成/验证 | allocated/reserved峰值字节 |
|---|---:|---|---:|---|---|
| prepare | 15787 | 17:52:02–17:53:17 | 74.4217 | 24/0 | 3,791,581,696 / 4,011,851,776 |
| cal | 17244 | 17:56:17–17:57:21 | 64.8140 | 0/30 | 3,548,317,696 / 3,735,027,712 |
| test | 18153 | 17:58:42–17:59:56 | 74.5419 | 0/36 | 3,555,821,568 / 3,745,513,472 |

计时不含启动前哈希检查。exit_code均0，24个生成安全检查输出均false。18:00:26Z及次日02:23:47Z复查GPU7为1MiB/0%，无本次进程。连接断开后只取回和审计，没有重跑模型。

原始图片/JPEG、每源注册和反演数组、输入字节快照、冻结配置、runtime/退出码/日志全部保留，约49MB；每条记录绑定图像文件及RGB、特征、参考、反演、L2数组。阶段冻结记录含实际依赖版本和model/config/tokenizer/scheduler/feature-extractor哈希。权重和来源许可沿用[基础报告](sd15_clip_smoke.md)。

[CPU审计](../reports/calibration_engineering/audit.json)核验129个文件哈希，30 cal+36 test行复算均通过，参考噪声差0，L2最大差1.7764e-15，并重算阈值及检查其在test前冻结。[审计脚本](../scripts/audit_calibration_engineering.py)是同实现保存阶段复核，不是独立模型复现。

此配置没有caption、credential、payload、policy或实例认证输出，不是官方SEAL或完整实例认证。上游阈值10和patch容差2.0均为未校准fallback。当前没有非退化90%校准工作点；保留原test冻结结果，后续修复只用cal/dev，新的泛化验证需fresh holdout。后续两源CPU控制、2×2交叉、6次聚焦反演和16次条件VAE精度编码已完成，见[聚焦诊断](focused_stability.md)；本批精度切换未降低JPEG模式差异。

## 2026-10-09 反演参数澄清

固定 CSI invert 在赋值后未使用 guidance 参数；实际采用空提示词、每步一次 UNet 调用的单分支反演。早期配置中的 invert_guidance=1.0 是未参与计算的字段，不能将其改动报告为 CFG 消融；生成 guidance=7.5 生效。静态核查及六次原生反演的 300 次实际调用记录见[聚焦诊断](focused_stability.md)。原冻结配置、分数和数组未改动。
