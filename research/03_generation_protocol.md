# 阶段 3：同域 A/B/D 生成与评测协议

问题：同一提示词、同一生成模型、不同种子得到的实例，能否与同一实例的允许变体区分？采用完整参考特征作内容表示诊断。认证凭证、水印提取、自然局部替换 C 和自适应攻击均未纳入本阶段。

## 固定设置与来源

本轮唯一生成模型为服务器已有 SD 1.5，公开镜像标识 `stable-diffusion-v1-5/stable-diffusion-v1-5`，revision `451f4fe16113bff5a5d2269ed5ad43b0592e9a14`。缓存目录历史名含 runwayml，但随附 README 明确说明是社区镜像；按该公开镜像固定 revision 的 API 校验权重 LFS SHA256、配置 Git blob 和文件尺寸，不将其表述为 Runway 的签名背书。必要文件与实测 SHA-256 见 `outputs/stage03/generator_files.json`，使用现有完整缓存、生成模型新增下载为0。

模型选择理由与时点：优先检查 SDXL，已知缓存不存在；服务器直连官方 Hugging Face HTTPS 连接重置。本机下载并传输了部分官方 SDXL 文件，但中断后 UNet 续传约70 KB/s、剩余约2 GB，预计数小时。正式及预检查图像均为0时，按用户允许的缓存替代路径选定 SD 1.5；完整保留选择记录和原 SDXL 配置于 `outputs/stage03/asset_selection/`。已停止 SDXL 下载，部分文件不用于生成；下载预算保留中断请求完整预留，保守累计上界约9.91 GB，低于15 GB。依赖未安装或升级。所有图像生成、变换、模型推理、统计和测试均在 `/data0/liyanlei/instance_authentication_research` 内执行；本机用于文本编辑、传输和 Git。

1024×1024，30 steps，CFG=5，batch=1，空 negative prompt，`StableDiffusionPipeline`、模型随附的 `PNDMScheduler`，fp16 推理，保留默认 safety_checker；此 pipeline 无输出 watermarker。完整 scheduler 配置、版本、精度与默认组件记录在 `generator_runtime.json`；只有服务器成功加载后才写入这份证据。输出统一 RGB PNG、压缩等级6。安全检查标记导致停止并记录组不完整，不另换seed。SD 1.5 的后期训练分辨率为512×512；本轮保留用户指定1024输出，可能增加结构重复/畸变，因此结论只适用于此生成设置，不能外推至SDXL或所有生成模型。固定总览审核此局限，不按视觉偏好删除样本。

接口及来源核验：[固定镜像版本](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/tree/451f4fe16113bff5a5d2269ed5ad43b0592e9a14)、[Diffusers 0.29.2 StableDiffusionPipeline API](https://huggingface.co/docs/diffusers/v0.29.2/en/api/pipelines/stable_diffusion/text2img)、[官方随机数复现说明](https://huggingface.co/docs/diffusers/v0.29.2/en/using-diffusers/reusing_seeds)。实际软件版本以服务器记录为准。

## 数据预注册与分组

`data/stage03/prompt_design.tsv` 是项目自编的 120 条普通场景提示词，物体、动物、室内、建筑、交通、自然各 20 条；不宣称来自公开基准。每主题 10 个相关内容族，每族 2 条提示词；族编号奇数校准、偶数测试，各 60 提示词、30 族，每集合各主题 10 条。同主题可跨集合，关联族整体划分。

`prompts.jsonl` 由服务器生成，包含完整文本、主题、族、split、四个不同种子及 reference 角色。种子为 `SHA256("stage03-20260918/{prompt_id}/{slot}")` 前 4 字节的大端无符号整数；每图重新创建 CPU `torch.Generator`。slot 0 固定 reference，其他 3 个 slot 为独立生成实例。正式运行之前保存提示词文件 SHA、配置和权重信息；预检查通过后写入 `frozen_run.json`，已存在的不兼容产物拒绝覆盖。

额外 4 条独立工程预检查提示词，各 4 seeds 共 16 张，另重复第一张一次。检验不同 seed 像素去重、同 seed 重复误差、保存格式、三种基线预处理、耗时与显存。预检查不打分，也不按结果选择正式提示词。以均值耗时×480×1.15 预测主体成本，必须加已消耗预算后仍低于 10,800 秒。生成进程按次持久化时间预留；中断后未结算的预留保留计费。

## A/B/D 配对

每原始生成图独立施加六种变换：JPEG Q90/Q70（subsampling=2，真实 JPEG 编码解码后 PNG）、bicubic 缩小 0.75/0.5 后恢复、Pillow RGB 亮度 0.95/1.05。复用从阶段 2 提取的同一变换函数；与阶段 2 全部 120 个 A 变体逐像素回归。原图保持 1024 分辨率，不执行阶段 2 自然照片的最长边 512 操作。

|类别|每提示词对数|校准对数|测试对数|定义|
|---|---:|---:|---:|---|
|A|6|360|360|reference 对同实例六变体|
|B_raw|3|180|180|reference 对其他三个独立种子实例|
|B_post|18|1080|1080|reference 对其他实例的六变体|
|D|3|180|180|同集合其他提示词 reference|
|SELF|1|60|60|一致性检查，不参与 A 或校准|

计划为 480 原始图、2,880 派生图、3,360 个唯一推理文件、3,720 对含 SELF。D 根据同集合排序提示词，采用循环偏移 1/7/19；遇同族或重复供体顺延，规则不读取分数。图像证据清单为 `manifest.jsonl`，配对清单为 `pairs.jsonl`。失败保留记录；不替换提示词/seed 补齐。

## 五个冻结分数与阈值

沿用阶段 2 官方权重与预处理：CLIP ViT-B/32 全局512维、SSCD Disc Mixup 全局512维、DINOv2 ViT-S/14 的 256×384 归一化 patch。DINO_global 为 patch 均值再 L2；两个局部分数为同位置 patch 余弦的均值和 q10（NumPy linear）。DINO 三分数共享提取，未做实例匹配网络训练。输入比较器仅为特征数组；提取清单只含 ID、路径、文件哈希，模型不读取命名、提示词或类别。

`stage02/worker.py` 仅增加产物目录参数，默认仍为 stage02；模型、预处理、提取和缓存键不变。`stage02/data.py` 的六变换提为可复用函数。阶段 2 数据、配置、阈值、报告和结果全部逐文件哈希保护。代码原版本可由 Git 基准 `0c62854c4ae0c05a694f72193a84a87e4e9bbfbb` 获取。

阈值仅由校准 A 求得：升序数组索引 `floor(target*n)`，分数 `>= threshold` 接受，包括相等分数。主 target FRR=5%，辅助 1%/10% 预先固定；每方法各自校准。校准分数计算后先保存阈值及 SHA，再计算测试分数。所有测试结果包含实际 A FRR，不能以低 B 错误接受而忽略 A 拒绝。

所有类别报告 count/total/rate，A 和 B_post 分变换，另分主题；提供 prompt/family 数及组均值。1000 次 bootstrap 分别重采样校准与测试族，同一组索引用于全部方法，每次只从采样校准 A 重拟阈值。百分位区间为探索性估计，零错误退化区间不证明零 FAR。D 供体反复出现，其区间按源族重采样、条件于固定供体图，未完全表达交叉供体依赖。

参考数组 float32：CLIP/SSCD 2,048 B，DINO_global 1,536 B，两个局部分数各 393,216 B；另报实际 `.npy` 文件大小。局部信息量是 DINO 全局的 256 倍；完整参考特征尚未压缩、签名或嵌入。

## 执行、预算和审核

服务器已有解释器 `/data0/liyanlei/envs/stego_attack/bin/python`。CPU 控制器隐藏 CUDA，启动前重新读取宿主机 5/7 编号与 UUID，再给子进程单 UUID；内部设备 cuda:0；driver API 和 nvidia-smi PID 行核实。GPU 7 生成结束释放后运行 DINO；GPU 5 顺序 CLIP/SSCD、保留18%分配器上限。生成单独75%上限，24 GiB卡至少为分配器外开销保留6 GiB，启动要求空闲≥20,000 MiB。不改动原有进程。锁与阶段 2 共用，避免本项目同卡重叠。

统一入口：

```bash
cd /data0/liyanlei/instance_authentication_research
CUDA_VISIBLE_DEVICES= /data0/liyanlei/envs/stego_attack/bin/python scripts/run_stage03.py --config configs/stage03.json
```

工程检查可用 `--through preflight`，仅生成及派生数据可用 `--through generation`；默认运行至 audit。恢复时核验已有图像、配置和哈希；已验证图像不重新生成。不兼容文件拒绝覆盖。`run_status.json` 分 prepared/generated/features/evaluation/audit_complete，失败单列 incomplete 与具体错误，不能以已写代码代替完成标记。

预打分总览固定每主题每集合最小 prompt_id，共12组×4图；人工/视觉审核状态单列，不用于删样本。打分后最高 B 和实际错误另标 post hoc。输出 CSV、metrics、thresholds、GPU 绑定、figures、logs 均位于 `outputs/stage03/`。结果报告为 `research/03_same_prompt_diagnostic.md`。到本阶段结束停止，不自动扩展研究范围。
