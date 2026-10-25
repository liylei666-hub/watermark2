# 确认集数据：完整标注包已核验，冻结归属字段假设未通过

**下载及中转已完成；当前阻塞已不是网络。** Windows于2026-10-25 05:25:26 UTC取得完整标注包，05:26:20完成验证；服务器05:29:14的完整数据流SHA256一致。随后原冻结CPU选择器在下载任何单图前退出1：合格源数0。没有模型/GPU或攻击优化，没有生成水印秘密或认证凭据，100对确认集尚未完成。

## 真实取得链路与完整性

原域名的[两次服务器超时](../confirmation100_assets_v1_retry1/report.md)、[两次Windows证书错误](../confirmation100_assets_windows_retry1/report.md)保留。Google官方存储路径实际返回404，不写成成功。上海交大[机构记录](https://scidata.sjtu.edu.cn/records/7rp0x-d6e31)正常TLS下载取得138,097,663字节后curl56中断；同站续传不支持Range，curl33停止。新文件恢复收到79,839,232字节时发现可用官方S3入口，仅停止唯一命令行匹配本任务retry2文件的自有curl PID36000，保留部分文件；没有停止他人或模型进程。

只读DNS确认`images.cocodataset.org CNAME images.cocodataset.org.s3.amazonaws.com`；[AWS官方文档](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html)给出区域路径式HTTPS接口。该入口HEAD实测200，大小252,907,541、ETag `f4bbac642086de4f52a3fdda2de5fa2c`且支持Range。经正常TLS的`https://s3.us-east-1.amazonaws.com/images.cocodataset.org/annotations/annotations_trainval2017.zip`返回206，24.131735秒补齐114,809,878字节。既有138MB前缀SHA未变，不再完整重复下载。

完整包252,907,541字节、SHA256 **`113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268`**，与[TensorFlow Datasets校验表](https://raw.githubusercontent.com/tensorflow/datasets/master/tensorflow_datasets/url_checksums/coco_captions.txt)完全一致；MD5亦与SJTU页面一致。TFDS是独立校验来源，镜像MD5不冒充COCO签名。全部6个ZIP成员CRC通过，只读取`captions_val2017.json`，未把约834MB解压库落盘。

Windows完整ZIP经现有验证SSH身份送入服务器逐块哈希，服务器不保存第二份完整包。仅将字节不变的所需标注成员机械重打包后SCP：容器792,973字节，SHA256 `af4d72f25572038f51fe26d96fd67d9f865f06c4b80d5f70dea2ba2e23736e2f`。服务器文件名`metadata/annotations_trainval2017.zip`是这个子集容器，**不是252MB原包副本**。成员3,872,473字节、SHA256 `afe3b30e403dd7f228e2373023abbd60042a6e10ec6874d3652df034d289ebb9`两端一致。完整包及失败部分文件仍在Windows。原始HTTP头中的瞬态Cookie不进入Git；公开的是固定来源、传输字段、错误和哈希收据。

## 实际元数据发现：许可并非不足

核验COCO2017val 5,000个唯一图像ID、25,014条caption、8条许可定义。真实图像中857张被元数据声明为CC BY2.0，其他4,143张不在原CC BY白名单。**原先代码假设`flickr_url`是含作者账户的`flickr.com/photos/...`页；实际5,000项全部是`farm*.staticflickr.com`静态图像URL。**因此857张CC BY图像也被归属字段规则拒绝，原冻结合格数为0。例：COCO397133的原字段为`http://farm7.staticflickr.com/6116/6255196340_da26cf2c9e_z.jpg`，没有作者账户。不能把此结果解释为COCO没有足够CC BY图像或下载文件损坏。

[schema审计](schema_audit.json)、[5,000项拒绝清单](metadata_audit.json)和原始stderr均保留。修正归属字段处理需要新的明确协议版本；本次未放宽门槛、伪造作者或重跑该选择器。下一项先审查：能否从可信公开来源补齐photoID/作者，或明确未知作者信息如何标注；不能把未知归属写成已完整验证。种子、SHA排名、许可白名单、历史去重、PNG预处理和禁用目标反馈的规则继续保持。现有六张未像素匹配图片仍不自动成为未开发确认集。

## 核验与预算

[运输补充协议](../../protocols/confirmation100_relay_transport_v1.json)在CPU选择器启动前冻结，原选择协议SHA及历史覆盖清单不变。5项中转边界测试在Windows及服务器通过，4项原规则测试通过；早期Windows临时目录fixture权限错误及改用项目内部fixture的事实另记，不能把局部单元测试当成真实100对流程成功。原选择器11项执行封存、源哈希、ZIP/成员身份及统计已通过[公开证据复核](public_verification.json)。

按[存储审计](storage_audit.json)计入Windows完整包、保留失败部分文件、标注/子集、日志及服务器副本，合计342,095,188字节，低于536,870,912字节。工作区与服务器研究文件保守合计2,229,326,806字节，低于10GiB，排除已有cache/env/git。部分文件、完整包、传输量和落盘副本分别记账；原ZIP校验收据中的`windows_data_bytes`仅统计选定zip/json，不含保留`.part`，总量以本存储审计为准。网络协议开销未测量，不冒充精确线速用量。

Windows控制器PID41052和服务器CPU监督PID5783均终端，无单图下载。阶段31四对原生校准及事后LPIPS不变；100对模型实验、Jain原SD1.4设置、阶段30和八攻击对照均未启动。这不是完整论文复现或SOTA证据。
