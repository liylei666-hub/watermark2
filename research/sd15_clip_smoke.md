# SD1.5 + CLIP 真实图像开发试运行

2026-10-08：完成3个源图的生成、JPEG70验证和固定提示词改色尝试。原图匹配数为356/220/143，JPEG70为68/4/32；后续控制为69/11/13，改色请求输出为54/12/16。**3次改色均未改变目标物体颜色，有效编辑为0/3，不能报告伪造成功率。** 这些图像全部属于开发数据，不是留出测试集。结果只证明独立替代配置可执行，阈值未经校准。

## 配置、来源与权限

[基础配置](../configs/sd15_clip_smoke.json)、[基础脚本](../scripts/sd15_clip_smoke.py)、[改色配置](../configs/sd15_clip_color_followup.json)、[改色脚本](../scripts/sd15_clip_color_followup.py)均在对应模型执行前固定。3个源分别为红色杯子、绿色瓶子、蓝色玩具车，种子2026100801–03；没有根据得分筛掉源图或重试。

使用服务器已有SD1.5 snapshot `451f4fe16113bff5a5d2269ed5ad43b0592e9a14`。缓存模型卡标明CreativeML OpenRAIL M，见[模型卡](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5)及[许可证](https://huggingface.co/spaces/CompVis/stable-diffusion-license)。保留SD安全检查器。使用OpenAI CLIP ViT-B/32图像特征，512维、L2归一化，代码[MIT许可](https://github.com/openai/CLIP/blob/main/LICENSE)；权重SHA-256 `40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af`与官方下载注册表一致。水印核心及DDIM反演来自固定[CSI源码](https://github.com/ZhengGao-30/CSI-Attack/tree/8723e362835a6a61efd11b61f677b3321face3fa)，Apache-2.0，源码清单、LICENSE和NOTICE保留。缓存权重、CLIP源码的实际哈希见[冻结记录](../reports/sd15_clip_smoke/frozen.json)。本次新增权重下载0字节，付费调用0。

原生流程：固定提示词/种子生成草图 → CLIP草图特征 → CSI `SealCore.noise_from_embedding`构造带密钥噪声 → SD生成水印图 → 从待检图提取CLIP特征并重建参考噪声 → 空提示词、CFG1.0 DDIM反演待检图 → 分块L2 → 匹配计数。生成/反演均50步、512×512，生成CFG7.5；k=1024、b=7、patch容差2.0。没有caption、签名、载荷或实例凭证阶段，也没有策略判定/篡改定位输出；不虚构这些检查。它是独立的SD1.5/CLIP替代配置，不能称为原SEAL复现或漏洞证明。

匹配计数越高表示更多patch满足L2≤2.0；最终计数≥10标记`fallback_accepted`。10为固定但**未经校准**的回退阈值，不是FPR/正常接受率保证。查询图像自身派生参考噪声；原图注册latent不提供给原生验证器。`registration_reference_matches`只作可访问原注册latent的oracle诊断，不用于接受决策。测试密钥seed=42是公开开发参数；本次编辑者使用公开同模型及原图反演噪声，无查询预算攻击或私有模型黑盒安全主张。原生方案无实例数据库凭证，所以另一张合法水印图不能直接标作应拒绝的实例冒用。

## 全部观察值与编辑有效性

| 源 / 预定义事实 | 原图 | JPEG70 | 同提示词再生成控制 | 改色请求输出 | 颜色审核 |
|---|---:|---:|---:|---:|---|
| s0 红色杯身 → 蓝色 | 356 | 68 | 69 | 54 | 杯身仍红，编辑无效 |
| s1 绿色瓶身 → 红色 | 220 | 4 | 11 | 12 | 瓶身仍绿，编辑无效 |
| s2 蓝色车身 → 红色 | 143 | 32 | 13 | 16 | 车身仍蓝，编辑无效 |

原图3/3、JPEG70为2/3通过回退判定，仅是这3例的观察计数；JPEG瓶图在最终匹配计数阶段拒绝，其他原生步骤完成。改色和控制的6个输出均通过，但改色有效性0/3。后续先复制每源已恢复latent，再分别使用原提示词和固定颜色替换提示词全图再生成；这不是局部编辑，背景/车轮可发生变化。输出网格经Codex在评分后检查，见[视觉审核](../reports/sd15_clip_smoke/visual_review.json)、[基础网格](../reports/sd15_clip_smoke/review_grid.png)和[改色网格](../reports/sd15_clip_smoke/followup/review_grid.png)。审核不是独立人工标注，先评分后审核是此批开发流程的限制；下一批必须先确认事实再评分。

## 计时、资源与可复核证据

隔离工作区`/data0/liyanlei/watermark2_instance_authenticity`，基础输出`runs/smoke-v1/attempt1`，后续`runs/smoke-v1/color_followup1`。旧服务器仓库未pull/reset，原Git工作区修改和未跟踪内容保留。每次执行只查询物理GPU7、要求≥12000 MiB可用且无计算进程，再以UUID `GPU-9644fb82-cb6f-7311-8017-eaee41409bb7`绑定；进程仅见逻辑cuda:0、RTX3090。未触碰故障GPU6。

| 批次 | UTC / 进程证据 | 模型加载至结果计时 | 生成 / 完整原生验证 | 显存峰值allocated / reserved |
|---|---|---:|---:|---:|
| 基础 | 冻结17:03:49Z；Python PID962 | 39.7298秒 | 6 / 6 | 3,783,201,280 / 4,022,337,536字节 |
| 提示词改色 | 输出冻结17:12:15Z、退出17:12:54Z；外层PID4274，未保存Python PID | 37.3498秒 | 6 / 6 | 3,783,135,744 / 4,007,657,472字节 |

上述计时不含运行前权重哈希检查；每批900秒硬上限均未触发。17:17:36Z复查GPU7为1 MiB/0%，无本次进程。两批Python exit_code=0。首次SSH包装器因CRLF将退出码解释为`0\r`而返回非零，见[运输错误原记录](../reports/sd15_clip_smoke/launcher_transport.txt)；这与模型退出分开记录。后续保存LF shell脚本执行成功；没有为修复包装器重跑模型。

[基础原始分数](../reports/sd15_clip_smoke/scores.json)、[后续原始分数](../reports/sd15_clip_smoke/followup/scores.json)、两批`arrays.npz`、逐图PNG、冻结参数、runtime、exit_status、execution.log及partial恢复文件均保留。runtime文件清单分别绑定14和11个文件SHA-256。[CPU复核脚本](../scripts/audit_sd15_clip_smoke.py)重建参考噪声并复算patch L2、匹配数、回退接受和oracle字段；12行均通过，参考噪声差0，patch L2最大差1.7764e-15（容差1e-12）。见[基础复核](../reports/sd15_clip_smoke/audit.json)、[后续复核](../reports/sd15_clip_smoke/followup/audit.json)。这是保存阶段的CPU复算，没有重新执行CLIP、生成、反演或安全检查器。

## 后续门槛

先用新开发源图验证明确区域的机械改色与同区域处理控制，评分前审核事实改变，并同样施加JPEG/缩放。它只能检查流程完整性；自然关键事实攻击、独立校准、相同正常接受率比较、跨防御复现和自适应完整验证仍未完成。本次不存在新方法、攻击成功、安全性、鲁棒性或新颖性结论。
