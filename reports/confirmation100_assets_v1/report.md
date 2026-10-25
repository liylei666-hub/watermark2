# 100对确认集资产：规则已冻结，官方元数据连接阻塞

本任务仅数据准备，未运行模型/GPU、未生成参考图、攻击、目标评分、密钥/消息或服务认证凭据。**尚未取得100张载体或100条caption，不能标作数据就绪或论文复现完成。**

2026-10-25 03:13:55 UTC开始的唯一请求：`https://images.cocodataset.org/annotations/annotations_trainval2017.zip`。TLS握手超时，03:14:41 UTC停止；未收到HTTP响应，不能据此断言文件不存在、需要登录或官方所有线路均不可用。没有自动重试、降级连接、替代镜像、认证、付费或接受新条款。数据worker退出码1是获取阻塞，不是模型实验失败。原始stderr、events、status、execution与封存均保留。

## 冻结顺序及可复核材料

[选择协议](../../protocols/confirmation100_assets_v1.json)及SHA256 sidecar在请求前固定：`561fd8b5be87e364a59b3b09a941ef4cf0409da52c27a3656e23699df8c65648`。执行源SHA256 `0432e5418d669059554a37e5d0aff28ee3b3b47e10d25510132008137eb76fa0`。历史覆盖清单于03:13:55.288421 UTC封存，第一次fetch于03:13:55.401097 UTC发起；覆盖SHA256 `a8bbd98d20797e58da8edd4f949f75d779078437cc9cb159c6eb3216daae48fe`。未根据目标分数、图像语义或结果改变规则。

4项CPU规则检查在本地及指定服务器通过；没有模型导入。后续官方元数据schema/许可筛选、100图选择和caption配对分支在本次并未实际执行，不把单元检查夸称完整获取验证。[公开核验](public_verification.json)核对8份执行产物、源/协议/覆盖哈希、时序、单次请求及0字节结果；不再联网或下载。

## 固定选择与排除规则

- 官方COCO2017标注包最多256MiB，仅提取`annotations/captions_val2017.json`；不取1GB验证图像整库。图片逐张获取，每张上限8MiB，最多150候选，数据合计最多512MiB。
- 只接受元数据声明的CC BY2.0/3.0/4.0，并要求Flickr账户与photoID来源字段；保存COCO ID、原coco_url、有效获取URL、许可URL、账户ID与源链接。显示名未知时保留null，不伪造作者名或声称实时权利认证。原图不在GitHub批量转载。[官方条款](https://github.com/cocodataset/cocodataset.github.io/blob/master/dataset/termsofuse.htm)把标注CC BY4.0与各原图版权分开；[官方获取页](https://github.com/cocodataset/cocodataset.github.io/blob/master/dataset/download.htm)。
- seed固定`wm-native100-20261025-v1`，按SHA256(seed|cover|十进制COCO_ID)排序；caption独立使用caption域。先排除已知历史COCO ID，再检查文件SHA256、原RGB像素、统一RGB512像素及pHash。pHash为32灰度DCT的8×8低频、DC位0、其余63位中位数阈值，距离≤4排除；同时对已选载体去重。
- captions来自与载体及其他caption来源均不重复的COCO ID/Flickr photoID；按独立哈希排序，在每来源中选最低ID的非空、非历史且不重复caption。文本按NFKC、casefold和空白归一化去重，但保存并使用原始caption文本。目标100图、100唯一caption和100个固定顺序配对。
- 载体预处理固定Pillow11 `Image.open(...).resize((512,512)).convert('RGB')`，不加EXIF修正或语义改变；保留原JPEG与PNG及各自字节/像素哈希。失败、排除和部分文件均保留；不放宽规则追求100个结果。

确认集仅供已冻结基线确认，不可选择新方法或调参，不在开发阶段查看目标评分。任何后续取得数据的执行修订应保留本次失败，引用同一冻结规则及覆盖清单；若覆盖信息需要纠正，明确另立版本，不暗改旧清单。本v1不自动恢复/重复已有目录。

## 覆盖范围与独立性限制

扫描项目内579张历史图片，解码失败0；2626份公开run/report/protocol元数据，109条已知提示词归一化哈希。排除cache、envs、private_eval、datasets和.git。原COCO编号能明确映射的历史ID为0；匿名`COCO_1..10`不是原COCO ID，不能把1–10硬当来源ID排除。

这些有限字节/像素/感知哈希/元数据检查不能证明完全未参与开发。裁剪、旋转、有损变体、未记录或范围外使用可能逃逸，也不证明基础模型训练未见。现有六张无像素匹配同样不自动获得确认资格。由于本次未取得官方元数据，实际许可/归属及200个来源不重叠检查仍未完成，公开目录没有虚构100对清单。

## 体积与发布范围

获取前研究产物995831336字节；获取后复核996593973字节。统计为项目普通文件逻辑字节，保守计入既有研究原始记录，排除既有model cache/env/git；10GiB上限未触及。数据目录普通文件数0、文件内容0字节，未取得标注或图片；额外体积是协议、代码及审计记录。获取前可用磁盘547846967296字节，后测547846152192字节；共享磁盘变化不等于本任务写入量。

GitHub仅发布协议、源代码、检查和来源/哈希审计；`datasets/confirmation100_v1/`已加入忽略规则。没有发布原JPEG、预处理PNG或标注zip。版本后测Pillow11.0.0、NumPy2.2.6、SciPy1.13.1，注明为失败后环境观察，不倒称更早预封存。

下一步先由协调方处理指定服务器到该官方HTTPS来源的通信或审查经核实的官方传输方案；不得把本次阻塞当作已获替代源、降级或重跑授权。100对模型实验、Jain缺SD1.4、阶段30和八攻击对照均未启动。[阶段31结果](../31_native_calibration/report.md)及[事后CPU质量](../31_native_calibration_lpips_20261025/report.md)不变。
