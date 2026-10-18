# 固定图像的目标编码定位

问题来自[阶段18](../reports/18_endpoint_residual/report.md)：两对固定候选在代理与目标参考反演的MSE和余弦排序不同。下一项定位要判断这种排序差异是否已经存在于目标VAE编码结果。这里的参考始终是相同模型对参考图的表示，不改用原始生成噪声。

## 已核对的调用路径

源码固定为`and-mill/semantic-forgery@ca68950cd7b53b8438a49580f134b2a0db28d778`，四文件内容与SHA256保留在[来源记录](../reports/18_endpoint_residual/target_encoding_source.json)。

|源码位置|实际行为|
|---|---|
|`utils/pipe/pipe_utils.py:16–19`|SDXL model ID映射到SDXLPipeProvider。|
|`utils/pipe/SDXL_provider.py:7–17`|继承PipeProvider，指定StableDiffusionXLPipeline；没有覆盖编码或反演函数。|
|`utils/pipe/pipe_provider.py:18,58–59,75–80`|默认FP32，并按该精度加载pipeline。|
|`utils/pipe/pipe_provider.py:330–338`|PIL转换后调用imgs_to_latents，再将所得z0传给invert_z0。|
|`utils/pipe/pipe_provider.py:431–440`及`utils/image_utils.py:344–365`|转换用torchvision ToTensor，移至配置的dtype/device；没有resize、crop或图像处理器归一化。|
|`utils/pipe/pipe_provider.py:176–189`|缺batch维则补维，调用vae_encode。|
|`utils/pipe/pipe_provider.py:146–159`|先映射`2*x-1`，VAE编码取posterior.mean，再乘VAE自身scaling_factor。|

阶段17评估脚本`scripts/cover_pilot/evaluate.py:24–30`读取RGB图片并调用该官方invert_images路径；只保存了zT反演结果。因此目标z0尚缺，需要一次新的编码计算，不能从原始生成噪声或代理z0替代恢复。

## 最小测量设计

采用阶段17全部12张固定图：每任务的参考、原载体、Imprint与Jain。评估端使用同一SDXL缓存revision、FP32和官方provider.imgs_to_latents接口，保存12份z0。只作VAE编码，候选保持原哈希；所有反演结果沿用阶段17。调用前固定输入、代码与模型配置，并完成设备预检。

CPU分析分别在代理z0、目标z0、代理zT、目标zT空间计算相对各自参考图的MSE、余弦与范数比。只比较各空间内的方法排序及其变化，不直接比较不同空间的绝对MSE。若目标z0已有排序反转，可将差异描述为“在编码阶段已出现”；若直到目标zT才反转，可描述为“编码到反演的组合路径改变排序”。两种观察均不是单组件干预或因果证明。

目标z0及评估结果属于评估端数据；不传给攻击算法，不据结果筛图或改变参数。全体样本为事后开发诊断，不构成新方法或独立确认集。完整几何/SemBind接受仍需其官方评估协议。

## 实际完成状态

[阶段19](../reports/19_target_encoding/report.md)已执行上述12图检查。任务3的双指标排序差异已在目标编码出现；任务2仅MSE在编码出现、余弦在反演后改变。任务1在两模型内均由编码Jain领先变成反演Imprint领先。保存目标编码及全部输入哈希，未更新候选。该组组件定位关闭，后续不追加同组探测寻求单一解释。
