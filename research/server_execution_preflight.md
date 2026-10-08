# 服务器资源与缓存核查

日期：2026-10-08 UTC。[机器可读记录](../reports/server_preflight/20261008.json)。使用本机现存 SSH 密钥、非交互认证和严格主机密钥检查，成功登录 `liyanlei@172.18.185.249`，主机自报 `server249`。服务器检查均为只读。

| 资源 | 核查快照 | 执行判断 |
|---|---|---|
| 物理 GPU 5 | RTX 3090，24576 MiB总显存；空闲695 MiB，利用率96%，已有23552 MiB计算进程 | 当前占用，不启动本项目任务 |
| 物理 GPU 7 | RTX 3090，24576 MiB总显存；空闲24253 MiB，利用率0%，查询未见计算进程 | 可作为小规模推理候选，启动前重新确认占用 |
| RAM | 总270.12 GB，可用213.56 GB；swap已满 | RAM容量充分，监控实际峰值，不依赖swap |
| 磁盘 | `/data0`空闲577.46 GB，`/data1`空闲791.31 GB，根分区空闲61.86 GB | 模型和新实验优先置于用户的`/data0/liyanlei`目录 |

用户禁止使用物理GPU6。本轮两次设备查询均限定5、7，没有执行CUDA模型、GPU测试或全卡查询。未来任务只允许将`CUDA_VISIBLE_DEVICES`设为GPU7的完整UUID：`GPU-9644fb82-cb6f-7311-8017-eaee41409bb7`。该隔离方式计划把它映射到逻辑`cuda:0`；尚未初始化CUDA，运行时映射未验证。任何模型启动前应确认物理7的UUID/占用、环境变量及隔离后设备数，不能沿用旧脚本的设备参数。

## 工作副本和环境

旧副本位于`/data0/liyanlei/instance_authentication_research`，remote匹配watermark2，HEAD为`0c62854c4ae0c05a694f72193a84a87e4e9bbfbb`。其中有两处已跟踪修改和大量未跟踪stage03文件。保留现场；新目录候选`/data0/liyanlei/watermark2_instance_authenticity`尚未创建，其父目录可写。旧副本未执行pull、checkout、reset或文件修改。

现有`/data0/liyanlei/envs/stego_attack`提供Python3.10.20；通过包元数据核实PyTorch2.3.1+cu121、Diffusers0.29.2、Transformers4.41.2和Accelerate0.30.1。仅运行了Python版本查询，没有导入或初始化CUDA。完整依赖兼容性尚待独立环境检查，不更新其他课题环境。

## 缓存复用边界与下载预算

只检查用户默认缓存及已发现的用户项目/模型目录。发现SD1.5 snapshot `451f4fe16113bff5a5d2269ed5ad43b0592e9a14`，有UNet、VAE、文本编码器和配置；SDXL缓存不完整。另有SSCD、CLIP、DINO small。已检查范围内没有SD2.1、BLIP2、SEAL微调句向量、DINO giant或SemBind masker。

SD1.5可供另行登记的模型配置使用，不能据此声称复现SD2.1结果；CLIP/DINO small不能替代SEAL的caption/句向量步骤。[公开实现核查](public_reproduction_feasibility.md)中SEAL/CSI的目标权重总量18,787,983,390字节在已查缓存中仍未满足。下载后若另存BLIP2的fp16转换副本，预留约40 GB工作空间；服务器磁盘满足该容量。GPU7和RAM符合先前16–24 GB显存、32 GB RAM的规划建议，实际延迟及峰值尚未测量。

## 当前执行门槛

SD2.1镜像模型卡声明OpenRAIL++，BLIP2声明MIT，CSI代码声明Apache-2.0。本轮读取SEAL微调句向量的固定版本README（13,416字节）：元数据未声明许可证，正文保留注释中的`License: Unknown`。基础MPNet的许可不能自动代替作者微调checkpoint的未声明条件。SEAL官方代码许可缺口也保留在上轮报告中。

按本次授权“下载许可未知则报告具体缺口”的条件，未下载该权重或启动完整验证。下一步资源决策是确认作者发布许可与约18.79 GB下载/有限推理预算，或明确采用许可已核实的另一编码器并登记为不同验证配置。3张真实源图的原图、合法变换、事实修改和同流程事实不变控制尚未运行；已存在的stage03图像仍属于历史诊断数据。
