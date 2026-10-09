# 限定 JPEG 编码诊断与生成 latent 的 oracle roundtrip 控制

2026-10-09：完成 c04 鞋子的 JPEG70 4:4:4、JPEG95 4:2:0 两次新增反演；对 c04/c02 各一次原配置生成重放，图像像素及 PNG 字节均与旧原图一致，随后各一次配对 bypass 反演。未改变任何检测阈值。去掉色度下采样没有恢复鞋子匹配，高质量 JPEG95 也只有 3 个 native 匹配；bypass 明显改善两个原图的噪声恢复，但依赖真实生成 latent，仅能作为 oracle 机制控制。

**判断：保留 SD1.5/image CLIP/CSI 配置及本批证据作为工程调试工具，暂停扩展其攻防样本和阈值优化。当前没有非退化的 90% 正常接受率工作点，不能用它承载完整实例真实性或 CCF-A 安全贡献的比较。**

## 固定范围、参照和单位

本批[配置](../configs/limited_codec_bypass.json)只扩展 c04 的编码诊断；JPEG95 与 4:4:4 用于分析，不修改旧 P0 测试策略。c02 仍为前一轮按 cal 五版本最小匹配数选择的固定对照。该选择及后续分支均是 cal-only 自适应工程探索，非留出泛化实验。全部既有 cal/test、CPU pilot、聚焦原始证据和旧研究报告保留字节；没有用 test 选择参数。

k=1024、b=7、key42、patch L2≤2、未校准 count fallback=10 保持固定；原 cal 选择的 count=0 仍标为退化判定，不作为有效接受保证。native 参考由待检图像 CLIP 特征派生；canonical oracle 使用 float64 registered_z，仅作机制诊断。E、D、A 及 E∩D、A 在 E 外的定义沿用[两源报告](focused_stability.md)。所有匹配数以 1024 个 patch 为分母，不把 patch 当作独立样本。

RMSE 用 float64 计算 sqrt(mean((a−b)²))，遍历对应张量全部元素。RGB 为 512×512×3 的 [0,255] 颜色码值；VAE 输入为 1×3×512×512、RGB/255×2−1 后 fp16 的归一化颜色坐标；CLIP 预处理为 1×3×224×224，经 resize/crop 和通道 mean/std 标准化。mode 为 1×4×64×64 的未缩放 VAE 潜变量；scaled initial 为实际 mode×0.18215、sigma1 的缩放潜变量。不同空间的 RMSE 不计算“放大倍数”。patch L2 是每个 16 元素 patch 的未归一化欧氏范数，等于该 patch RMSE×4。

## 同一鞋子图的编码比较

原 Pillow10.4 运行时重新编码 JPEG70/subsampling2 后，JPEG 字节及解码 RGB 均与旧文件精确一致，见[编码绑定控制](../reports/limited_codec_bypass/jpeg/codec_control.json)。以同一旧原图保存 quality70/subsampling0 和 quality95/subsampling2；每种仅反演一次，不重试。新增每图保存 JPEG/PNG、实际 RGB、CLIP 预处理、特征、VAE 输入/mode、50 次 UNet 输入/epsilon、51 个轨迹状态、bucket、全部 native/oracle 距离和 E/D/A 掩码。

| c04 输入 | native A | oracle D | E | E∩D | A 在 E 外 | RGB 码值 RMSE | mode RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|
| original（既有） | 116 | 614 | 209 | 116 | 0 | 0 | 0 |
| JPEG70 4:2:0（既有） | 0 | 1 | 181 | 0 | 0 | 2.016757 | 2.323213 |
| JPEG70 4:4:4 | 0 | 0 | 181 | 0 | 0 | 1.808838 | 2.306790 |
| JPEG95 4:2:0 | 3 | 29 | 204 | 3 | 0 | 1.303042 | 1.150069 |

所有差异均相对同一 original。[完整阶段 CSV](../reports/limited_codec_bypass/codec_summary.csv)另列 VAE 输入、CLIP 预处理、scaled initial、最终反演 RMSE 和正规余弦相似度。JPEG70 4:4:4 的归一化输入/CLIP RMSE 为 0.0141855/0.0140814；JPEG95 4:2:0 为 0.0102193/0.0131400。CLIP cosine 相对 original 为 0.975203/0.990813，仍不能代替 bucket 和完整验证计数。

| 输入 | native L2 中位数 | oracle L2 中位数 | oracle L2 最小值 |
|---|---:|---:|---:|
| original | 5.018402 | 1.856916 | 0.806442 |
| JPEG70 4:2:0 | 5.188617 | 4.756789 | 1.908178 |
| JPEG70 4:4:4 | 5.140432 | 4.743742 | 2.419783 |
| JPEG95 4:2:0 | 5.087495 | 3.375549 | 1.436278 |

[全部 8,192 个排序距离及 ECDF](../reports/limited_codec_bypass/codec_distances.csv)、[PNG](../reports/limited_codec_bypass/codec_distance_ecdf.png)、[SVG](../reports/limited_codec_bypass/codec_distance_ecdf.svg)及[分位数审计](../reports/limited_codec_bypass/audit.json)保留。图中参考容差固定为 2，未通过曲线选择阈值。两项新增编码在 count10 下仍拒绝；原 count0 退化判定当然接受任意非负匹配数，不能把它写作成功。

去除色度下采样后仍失败，说明该设置不是这一个样本失稳的充分解释；高质量编码降低了一些差异但未恢复 fallback 接受。不能由此排除色度处理的部分作用，也不能推广到其他图像、JPEG 质量或官方 SEAL。

## 生成末端 latent 的配对与 bypass

旧注册 NPZ 只有 draft_feature 和起始 registered_z，没有实际生成末端 latent。只重放两个旧 cal 原图的水印生成，复用原提示词、注册噪声、50 步 DDIM、生成 guidance7.5、fp16 和同一缓存/运行时；没有重新生成草图或替换 source。正常 VAE 解码和安全检查器保留，两次安全标志均为 false。

在 callback_on_step_end 的 index49 直接保存 scheduler 更新后的 latent，回调原样返回 kwargs。随后捕获真实 decoder 输入并验证它等于该 latent 正向除以 scaling_factor0.18215 的结果。**没有由经过 fp16 除 scale 的 decoder 输入反推末端 latent。** c04/c02 重放的 RGB 与 PNG 文件字节均精确等于旧图，见[重放结果](../reports/limited_codec_bypass/replay/results.json)。因此该重放 latent 与旧图形成有效像素配对；它不事后证明未保存的旧执行 latent 本身逐位相同。

控制问题：从这份真实末端 latent 开始，跳过“VAE decode → 8位图像/PNG → VAE encode mode”边界，是否改善同一固定空提示词反演对生成输入噪声的恢复？仅在配对成立后，替换 pinned backend.encode_image 的返回值，后续 sigma1、时步、UNet 和 DDIM 更新保持原方法。原图 CLIP 特征、语义参考、bucket 和原生阈值固定；每例再反演一次。未向 native 验证器增加部署时可获得的新输入。

| 源 | native 原图 → bypass | canonical oracle 原图 → bypass | 固定 E | bypass E∩D | bypass A 在 E 外 |
|---|---|---|---:|---:|---:|
| c04 shoe | 116 → 204 | 614 → 1015 | 209 | 204 | 0 |
| c02 cat | 317 → 367 | 843 → 974 | 389 | 367 | 0 |

同一 scaled latent 空间的末端 latent/原图再编码差 RMSE：c04=0.214716，c02=0.150615。对 canonical registered_z 的最终反演 RMSE，c04 0.529887→0.262936、c02 0.390001→0.253970。[完整 CSV](../reports/limited_codec_bypass/bypass_summary.csv)包含 before/bypass native/oracle 距离分位数；[原始轨迹](../reports/limited_codec_bypass/bypass)保留。oracle 的明显改善支持完整图像 roundtrip 边界对原图噪声恢复误差有贡献；native 还受到语义 bucket 一致性的限制。

这一控制没有将某个 JPEG 的编码 latent 换成原图编码 latent；那是前一轮已有 CPU2×2 格。它也没有检验 JPEG 修复。真实生成 latent 依赖不可部署的 oracle 信息，不能将结果报告为防御或检测器改进。边界包含 decoder、8位量化、PNG 图像流程和 encoder，不能单独归因 encoder。

## 实际生成输入噪声的精度参照

生成时 supplied registered_z 经 pinned _to_torch 转为 CUDA fp16，pipeline.prepare_latents 再乘 DDIM init_noise_sigma=1。原生 canonical oracle 保持 float64 registered_z 定义不变；另以实际运行时 fp16 输入为机制参照。

CPU 核查发现 direct NumPy float64→fp16 与 Torch 转换并非全部相同。因此在原 Torch2.3.1 CUDA 运行时，用同一个 pinned _to_torch 对两份原注册数组仅重放类型转换，**不加载模型，0 生成、0 反演、0 VAE 编码**。保存 fp16 supplied noise 与 sigma1 后输入；源哈希、转换代码和[原 pipeline 片段](../reports/limited_codec_bypass/inputs/diffusers_prepare_latents.txt)均保留。它是同代码转换复核，不是原生成时额外保存的初始 UNet hook。

c04 direct NumPy 转换与服务器一致；c02 有 1/16,384 个坐标不同。以服务器转换为准，CPU Torch 结果也逐元素一致。注册 float64 与实际 fp16 输入的 RMSE 为 0.0002061/0.0002080。这项 dtype 核查没有改变以下匹配数：

| 源 | image roundtrip 对 fp16 输入匹配 / RMSE | bypass 对 fp16 输入匹配 / RMSE |
|---|---|---|
| c04 | 614 / 0.529889 | 1015 / 0.262938 |
| c02 | 843 / 0.390001 | 974 / 0.253969 |

[参照审计](../reports/limited_codec_bypass/generation_input_audit.json)、[CSV](../reports/limited_codec_bypass/generation_input_summary.csv)、[转换原始输出](../reports/limited_codec_bypass/input_cast)及[完整 fp16 参照距离](../reports/limited_codec_bypass/generation_input_controls.npz)保留。参照精度修正没有替换旧 native/oracle 判定，也没有调节容差。

## 证据边界、未排除解释与继续价值

已有 VAE 精度阶梯的恰当结论为“没有实质改善”：c04 arithmetic-only 分支的 mode pair RMSE 比原生降低 0.002862%，完整 fp32 则提高 0.028230%；c02 完整 fp32 提高 0.025746%。不能说所有分支完全没有下降。原始精度数据和旧报告保留，本轮未追加 fp32 反演。

累计工程证据表明：已检查的文件绑定、轴、缩放与判定错误没有被发现；这个鞋子样本的 JPEG70 失稳未因去掉色度下采样消失，JPEG95 仍拒绝；原图的图像 roundtrip 对恢复误差有明显贡献；纯 dtype 调整对 mode 差异没有实质改善。这些不是新攻击、普遍鲁棒性规律或论文新颖性证据。

仍未排除 decoder/encoder 的非互逆、8位或 JPEG 量化与 VAE 非线性相互作用、生成提示词/CFG7.5 与空提示词单分支反演之间的条件差、DDIM 近似/时步离散、数值精度及其交互。bypass 仍有 c04 9 个、c02 50 个 oracle patch 超容差；不能只归因 CFG。canonical oracle 的计数容差未独立校准，c02 也是按既有 cal 稳定性选择的对照。

后续优先核实有权使用的官方基线模型链、语义提取和反演约定，形成可审计且非退化的操作点，再用 fresh cal/dev 和新的 holdout 检查修改。现有 SD1.5/image CLIP/CSI 缺少 caption、credential、payload、签名、policy 和实例真实性输出，不能替代完整验证。候选“允许编辑规则下的实例真实性”问题保留；通用语义绑定、局部检测和签名组合已有工作的新颖性边界不变。本批到此停止扩样、训练和攻击。

## 真实资源、运输更正与复核

物理 GPU7 UUID GPU-9644fb82-cb6f-7311-8017-eaee41409bb7 绑定为唯一逻辑设备 cuda:0；每批启动前检查该卡空闲、可用显存和 UUID。没有查询或初始化 GPU6、修改其他服务器仓库、安全设置或下载权重。

| 阶段 | Python PID | UTC 起止 | wall 秒 | 模型操作 | allocated / reserved 峰值字节 |
|---|---:|---|---:|---|---|
| JPEG 两项 | 19286 | 03:54:29–03:54:40 | 11.269680 | 2 反演，0 生成 | 3,546,998,784 / 3,730,833,408 |
| 精确生成重放 | 22108 | 04:04:59–04:05:10 | 10.377752 | 2 生成，0 反演 | 3,422,841,856 / 3,646,947,328 |
| 配对 bypass | 22889 | 04:06:44–04:06:51 | 7.260796 | 2 反演，0 生成 | 2,940,952,576 / 3,093,299,200 |
| 输入 dtype 转换复核 | 26529 | 04:16:20–04:16:20 | 0.147898 | 0 模型调用 | 98,304 / 2,097,152 |

前三阶段计时为模型加载到结果保存；转换阶段计时为 dtype 操作到保存，均不含先行检查/进程初始化。前三批900秒、转换批120秒上限均未触发，exit_code均0。总新增模型操作为4次反演、2次生成；paid=0、新权重下载=0。04:17:20Z 复查 GPU7 为1 MiB/0%、无计算进程。

运输更正：上次本机命令通道返回断连错误后，最初报告新增反演0次；恢复后核查远端 frozen/runtime/exit_status 证明 JPEG 阶段已于03:54:40Z完成2次。该批取回、保留原时间/PID，未重跑；后续仅使用剩余2次生成与2次bypass预算。不能根据工具未返回成功回执推定远端未执行。

[新增审计](../reports/limited_codec_bypass/audit.json)通过4次反演的200次更新、文件/数组绑定、参考重建、独立 NumPy patch 范数、decoder 前向缩放及像素配对。patch L2 最大差1.7764e-15，scaled mode/decoder input CPU复算差0。GPU Torch2.3.1 与 CPU Torch2.1.2 的 DDIM 回放最大逐元素差0.0078125，在 rtol0.003/atol0.003 内；它不是逐位 UNet 重跑。旧300次轨迹和独立审计已完成的旧数据未作为新实验重跑。

~~~bash
python scripts/audit_limited_codec_bypass.py --run reports/limited_codec_bypass --base-run reports/calibration_engineering --trace-run reports/focused_stability/gpu --csi-code runs/reproduction_audit/CSI-Attack
python scripts/audit_generation_input_reference.py --run reports/limited_codec_bypass --trace-run reports/focused_stability/gpu --csi-code runs/reproduction_audit/CSI-Attack
~~~

两个命令只调用CPU；第二个读取已保存的CUDA类型转换输出，不重新启动GPU。脚本/配置快照和原始日志、退出码、全部阶段数组保存在 [reports/limited_codec_bypass](../reports/limited_codec_bypass)。

实际执行代码以 inputs 中 frozen SHA 对应的快照为准；活动脚本另增加运行前范围/预算断言，未因此重新运行模型。
