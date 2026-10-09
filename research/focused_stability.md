# 两个校准源的 JPEG 失稳定位与 VAE 精度控制

2026-10-09：完成 c04 鞋子与按冻结规则选择的 c02 猫的 CPU 控制、8 个参考/反演交叉组合、6 次原生反演和条件触发的 16 次 VAE 编码。c04 的 JPEG70 匹配数仍为 0；像素完全相同的 PNG 重编码在全部阶段逐元素一致。交叉组合表明，在这两例中，c04 的主要匹配丢失伴随反演路径变化；更换 JPEG 语义参考本身不能解释全部下降。VAE 模式已经出现明显的原图/JPEG 差异，完整 fp32 控制没有降低该差异。**这是一项替代管线、两个校准样本上的工程诊断，没有得到可用的 90% 正常接受率工作点。**

## 选择规则、数据边界与控制

只读取[12 源实验](calibration_engineering.md)的 cal 原始数组和图像。c04 由任务指定；对照规则是：其余 cal 源的五种合法版本匹配数均至少 10，选择其中最小匹配数最大的源，同值按 ID 排序。各源最小值为 c01=22、c02=275、c03=167、c04=0、c05=69、c06=150，因此选择 c02。规则和[配置](../configs/focused_stability.json)在交叉组合计算及新反演前保存；它是对既有 cal 结果的自适应工程选择，不能作为预注册的泛化实验。原 test 图像、数组和分数保持字节不变；没有用 test 选择阈值或分支。

[CPU 控制](../reports/focused_stability/cpu/cpu_results.json)核对源文件、解码 RGB、特征、参考噪声和反演数组的绑定；VAE 输入采用 RGB/255×2−1、NCHW=(1,3,512,512)。反演/注册噪声为 (1,4,64,64)，1024 个空间 patch，每个含 4 通道×2×2=16 个数值。独立手工轴映射和范数复核通过：相同 latent 全部匹配；常数偏移 0.49、0.5、0.50000001 分别得到 1024、1024、0 个匹配，距离为 4×偏移；单个像素坐标偏移 3 仅改变第一个 patch。判定边界为 L2≤2，包含等号。

两个原图以不同 PNG 压缩重新保存后，解码像素完全相同。这项控制随后参与实际 VAE、CLIP 和反演，不只检查文件哈希。CPU 原始 frozen 文件中的 started_utc=03:08:22Z 是计算结束时写入的封存时刻；不将它称作评分前冻结时间。cpu_results 中 gpu_inversions_triggered=false 表示该 CPU 脚本未运行 GPU，后续 GPU 阶段另有触发和执行记录。

## 2×2 交叉组合与匹配分解

使用同一个公开开发 key42，固定 k=1024、b=7、patch 容差 2。对每个 patch：

- E：查询语义参考与注册草图的 bucket ID 相同。
- D：反演结果与 registered_z 的 patch L2≤2。
- A：反演结果与查询图像派生语义参考的 patch L2≤2。

D 使用可访问的原注册噪声，仅为 oracle 诊断。原生接受只使用 A 的总数。E 内的两套参考噪声相同，所以 A 与 D 在 E 内一致；E 外也可能偶然匹配，必须单独记录，不能强行把 A 定义为 E∩D。

| 源 | 反演图像 | 语义参考图像 | E | D（oracle） | E∩D | A（native） | A 在 E 外 |
|---|---|---|---:|---:|---:|---:|---:|
| c04 shoe | original | original | 209 | 614 | 116 | 116 | 0 |
| c04 shoe | original | JPEG70 | 181 | 614 | 96 | 96 | 0 |
| c04 shoe | JPEG70 | original | 209 | 1 | 1 | 1 | 0 |
| c04 shoe | JPEG70 | JPEG70 | 181 | 1 | 0 | 0 | 0 |
| c02 cat | original | original | 389 | 843 | 317 | 317 | 0 |
| c02 cat | original | JPEG70 | 380 | 843 | 312 | 312 | 0 |
| c02 cat | JPEG70 | original | 389 | 797 | 297 | 297 | 0 |
| c02 cat | JPEG70 | JPEG70 | 380 | 797 | 297 | 297 | 0 |

[CSV](../reports/focused_stability/cross_swap_counts.csv)及[完整距离、bucket 和掩码](../reports/focused_stability/cpu/cross_swap_arrays.npz)保留。c04 原图反演配 JPEG 参考仍有 96 个匹配，JPEG 反演配原图参考只有 1 个。这满足预先记录的条件，触发两源各三次聚焦反演。10 仍是未校准的解释用 fallback，patch 容差 2.0 也未校准；这里没有重新选择阈值。8 个组合的 A 在 E 外均为 0，只是本批观察。

## 实际反演与记录范围

[固定 CSI 源码](https://github.com/ZhengGao-30/CSI-Attack/blob/8723e362835a6a61efd11b61f677b3321face3fa/csi/backends/sd.py)的 invert 在赋值后没有再读取 guidance。它调用空提示词的 text embedding，每一步只调用一次 UNet，没有拼接条件/无条件双分支，也没有计算 CFG 加权。静态 AST 核查与 300 次实际 UNet 调用的 batch=1 记录一致。改变这个参数不能被报告为 CFG 消融；生成阶段 guidance=7.5 仍生效。

对 c04/c02 各运行 original、lossless_pixel_identity、JPEG70；通过 hooks 记录原生 encode/invert 的输入和输出，DDIM 更新委托原函数计算，没有重写其运算。保存实际 CLIP 224×224 预处理张量、512 维归一化特征、VAE 输入、posterior mode、scaled latent、50 次 UNet 输入/epsilon、51 个轨迹状态、timesteps/alphas、条件张量绑定、bucket ID、完整 native/oracle patch 距离。CLIP/VAE/UNet 实际计算为 fp16，DDIM init_noise_sigma=1，latent scale=0.18215。反演算术和噪声核心来自 CSI；其 hash/RNG 与官方 SEAL 有差异。

| 源 | 输入 | native 匹配 | oracle 匹配 |
|---|---|---:|---:|
| c04 | original | 116 | 614 |
| c04 | lossless_pixel_identity | 116 | 614 |
| c04 | JPEG70 | 0 | 1 |
| c02 | original | 317 | 843 |
| c02 | lossless_pixel_identity | 317 | 843 |
| c02 | JPEG70 | 297 | 797 |

两源 original/identity 的全部保存数组以及 NPZ 文件哈希完全相同；新反演的 original/JPEG 特征、参考和最终 latent 与原 cal 运行逐元素一致。这是同实现、相同输入的重复执行证据，不是独立模型复现。

## 距离定义、单位和分阶段变化

所有下表 RMSE 用 float64 计算：RMSE(a,b)=sqrt(mean((a−b)²))，均值遍历该张量的全部元素。它是每个坐标的均方根差，不是总 L2；对 (1,4,64,64) 有 RMSE=总 L2/128。patch L2 则是每个 16 元素 patch 的未归一化欧氏范数，等于该 patch RMSE×4。

| 量 | 空间、归一化与单位 | c04 original/JPEG70 RMSE | c02 original/JPEG70 RMSE |
|---|---|---:|---:|
| 解码 RGB | 512×512×3，uint8 [0,255]；8 位颜色码值单位 | 2.016757 | 7.083403 |
| 实际 VAE 输入 | 1×3×512×512，RGB/255×2−1 后 fp16；归一化颜色坐标 | 0.0158165 | 0.0555555 |
| 实际 CLIP 输入 | 1×3×224×224，resize/crop、[0,1]及通道 mean/std 标准化；标准化颜色坐标 | 0.0178265 | 0.0556704 |
| VAE posterior mode | 1×4×64×64，未缩放；无量纲模型潜变量坐标 | 2.323213 | 0.570045 |
| 轨迹状态 0 | mode×0.18215，init_noise_sigma=1，fp16；缩放后的模型潜变量坐标 | 0.423172 | 0.103836 |
| 轨迹状态 50 | 最终反演 latent，同一缩放潜变量坐标系 | 1.153002 | 0.224450 |

像素、CLIP 输入和 VAE mode 属于不同空间、维数和归一化；不对它们直接作数值“放大倍数”解释。归一化 RGB 的 fp16 量化也使它与原始颜色差的线性关系并非逐元素精确。只能说：在这些输入上，VAE 模式已经呈现原图/JPEG 差异，反演过程之后还发生进一步分离；不能据此认定唯一根因是 VAE 或某个 JPEG 编码参数。

同一缩放潜变量坐标空间内，定义阶段相对变化 r_i=RMSE(z_i(original),z_i(JPEG70))/RMSE(z_0(original),z_0(JPEG70))。最终 r_50 为 c04=2.724668、c02=2.161577。这描述本批原生轨迹的数值分离，不是像素到潜变量的增益，也不等于失败概率。[完整 51 状态 CSV](../reports/focused_stability/trajectory_rmse.csv)、[图 PNG](../reports/focused_stability/trajectory_rmse.png)和[SVG](../reports/focused_stability/trajectory_rmse.svg)可复核；逐步 UNet epsilon 差亦保留在[轨迹审计](../reports/focused_stability/trace_audit.json)。

## 条件 VAE 精度阶梯

轨迹控制通过、像素同一性成立，且 c04 的模式差大于 c02 的两倍、归一化像素差反而较小，触发[限定精度控制](../configs/focused_vae_precision.json)。这一跨源排序仅用于决定是否检查数值精度，不是跨空间放大比或统计证据。只编码这两源的原图/JPEG70，共 16 次 VAE encode，没有新增 UNet 反演或生成。

四个分支依次控制：原生 fp16；把已 fp16 量化的权重和输入精确展开为 fp32，仅改变算术/backend dtype；重新加载缓存原始 fp32 权重而保留展开的 fp16 输入；最后从 RGB 直接构造 fp32 输入。CPU 审计核对实际输入的字节绑定和输出 dtype。各分支均使用 AttnProcessor2_0；精度改变也可能改变 CUDA 内核选择，不能进一步分离具体算子。

| 分支 | 权重 | 算术 / 输入 | c04 mode pair RMSE | c02 mode pair RMSE |
|---|---|---|---:|---:|
| native_fp16 | fp16 量化 | fp16 / fp16 | 2.323213 | 0.570045 |
| fp32_arithmetic_fp16_weights_fp16_input | fp16 值展开 | fp32 / fp16 值展开 | 2.323147 | 0.570136 |
| fp32_checkpoint_weights_fp16_input | 原 fp32 checkpoint | fp32 / fp16 值展开 | 2.323571 | 0.570194 |
| fp32_checkpoint_weights_fp32_input | 原 fp32 checkpoint | fp32 / 从 RGB 得到 fp32 | 2.323869 | 0.570192 |

pair RMSE 始终在同一未缩放 VAE mode 坐标空间计算。完整 fp32 相对原生的 pair RMSE 变化为 c04 +0.028230%、c02 +0.025746%；本批未观察到精度切换减少 JPEG 模式差。完整 fp32 输出相对同一输入的原生 mode RMSE：c04 原图/JPEG 为 0.010606/0.018352，c02 为 0.002770/0.002904。[逐分支完整 CSV](../reports/focused_stability/precision_counts.csv)同时给出 scaled latent pair RMSE 和单输入对原生的差异。

使用已核查 CreativeML OpenRAIL M 的 SD1.5 snapshot 451f4fe16113bff5a5d2269ed5ad43b0592e9a14；原缓存 VAE safetensors SHA-256 为 a2b5134f4dbc140d9c11f11cba3233099e00af40f262f136c691fb7d38d2194c，没有下载、分发模型权重。本次没有用 fp32 mode 执行反演、计算新 native 接受率或重新校准，因此不能声称 fp32 检测器鲁棒性已测定。

## 执行、审计与交付

两批都只在物理 GPU7 UUID GPU-9644fb82-cb6f-7311-8017-eaee41409bb7 上运行，进程只见逻辑 cuda:0；未查询、初始化 GPU6。运行前 GPU7 空闲，UUID、可用显存和计算进程检查通过；900 秒上限未触发。旧服务器仓库未修改。

| 批次 | Python PID | UTC 起止 | wall 秒 | 模型操作 | allocated / reserved 峰值字节 |
|---|---:|---|---:|---|---|
| 聚焦轨迹 | 8172 | 03:13:44–03:14:05 | 21.151031 | 6 次反演，0 生成 | 3,555,821,568 / 3,745,513,472 |
| VAE 精度 | 12178 | 03:28:19–03:28:22 | 2.704075 | 16 次编码，0 反演/生成 | 1,020,517,888 / 1,151,336,448 |

计时包括模型加载到结果保存，不含先行源/权重哈希检查。exit_code 均为 0；新增权重下载和付费调用为 0。03:31:54Z 复查 GPU7 为 1 MiB、0% 利用率、无计算进程。原始数据、脚本/配置快照、元数据、日志和退出码位于 [reports/focused_stability](../reports/focused_stability)，约 43.3 MB 加派生图表。

[独立手工 CPU 审计](../reports/focused_stability/cpu_audit.json)通过 8 个组合，patch L2 最大差 1.7764e-15；[六次反演审计](../reports/focused_stability/trace_audit.json)检查 300 次更新、哈希和阶段绑定；[精度审计](../reports/focused_stability/precision_audit.json)通过全部 16 次编码，输入绑定精确，CPU scaled-mode 复算最大差 0。VAE 输入归一化和初始缩放复算亦为 0 差。

GPU Torch 2.3.1+cu121 与本机 CPU Torch 2.1.2+cu121 的保存 epsilon/DDIM 公式回放最大逐元素差 0.0078125，在 rtol=0.003、atol=0.003 的记录容差内；它不是跨设备逐位一致，也不是重新运行 UNet。输入同一性和新旧模型执行逐元素一致的断言不使用该近似容差。

CPU 复核入口（需要 NumPy/Pillow；轨迹与精度审计另需 CPU Torch 和已固定 CSI 源码，不调用 CUDA）：

~~~bash
python scripts/audit_focused_cpu.py --run reports/focused_stability --base-run reports/calibration_engineering --output runs/focused_cpu_reaudit.json
python scripts/audit_focused_inversion.py --run reports/focused_stability --base-run reports/calibration_engineering --csi-code runs/reproduction_audit/CSI-Attack --output runs/focused_trace_reaudit.json
python scripts/audit_focused_vae_precision.py --run reports/focused_stability --output runs/focused_precision_reaudit.json
~~~

保留原始 trace_audit 的精确字节，因为 VAE 精度冻结记录绑定了它；新的复核输出写入 runs。源脚本与冻结 SHA 对应的快照均保留在 inputs，派生报告不改动原模型执行记录。

## 本轮界限与下一步

实际使用 SD1.5 + image CLIP + CSI 核心，缺少 caption、credential、payload、签名、policy 及实例真实性判定；原官方 SEAL 模型链仍有缓存缺失/访问及权属障碍。两源自适应诊断不能推广为所有生成图、官方 SEAL、压缩鲁棒性或新颖性结论。通用语义绑定、局部检测和签名组合的已有工作边界不变。

本轮不扩大 JPEG 质量/subsampling 扫描、不绕过 VAE，也不开展新的攻击或训练。已有证据足以记录：文件/轴/缩放/判定错误未被这些控制发现，JPEG 反演变化在 VAE 阶段已经出现，精度阶梯未消除模式差；具体原因仍未定位。后续若设计修正，先在独立 cal/dev 冻结实现和操作点，再使用新的 holdout 检查泛化；原冻结 test 继续保留。独立正常接受率、完整实例验证和攻击安全比较仍未完成。
