# Imprint 与单图 VAE 匹配的可执行比较契约

2026-10-18，版本1。性质：固定源码审计、CPU适配检查与实验设计；不是模型效果结果或可直接启动的预注册配置。

研究问题是：在相同参考与指定载体、零目标反馈、明确计算和图像代价下，完整代理反演匹配相对只做VAE表示匹配提供了什么额外收益？这是判断后续方法贡献的基线问题。阶段10–12的单对图片诊断不能回答它，也不作为独立确认集。

## 1. 两个可比较的核心

固定 Imprint commit `ca68950cd7b53b8438a49580f134b2a0db28d778`，Jain commit `04433962437cbf08ad701b7b43124de07df0b666`。后者8个来源文件已核对Git blob和SHA256，未发现许可证文件；本仓库保存来源与自写检查，不复制整份上游实现。见[来源记录](../reports/cover_baseline_contract/source_audit.json)。

| 项目 | Imprint | Jain GS 单图VAE匹配 |
|---|---|---|
| 攻击输入 | 参考图r、载体c、代理模型 | 参考图r、载体c、代理VAE |
| 变量与初始化 | z=代理确定性编码(c)，优化潜变量 | x=c，优化归一化到[-1,1]的像素 |
| 目标 | 代理反演(z)与参考图代理反演的MSE | 代理VAE mode/s表示MSE，加λ×像素MSE |
| 更新 | Adam，默认lr=0.01 | 普通梯度下降，核心没有取梯度符号 |
| 图像约束 | 可选潜变量和像素mask；无mask分支无显式像素惩罚 | 每步裁剪至[-1,1]；不是围绕载体的L∞投影 |
| 输出 | 潜变量解码、范围映射/裁剪，再转PIL | 最后更新后的像素，范围映射/裁剪后转uint8 |
| 目标反馈 | 固定源码周期检测仅记日志；本项目需离线评估固定输出 | 核心不读目标；原入口同时持有目标和检测对象 |

Imprint依据：[初始化:119–121](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_imprint_forgery.py#L119-L121)、[更新及输出:186–233](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_imprint_forgery.py#L186-L233)。Jain依据：[核心:261–299](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/my_utils.py#L261-L299)。

两个核心的参数化、优化器、损失和图像约束同时不同。直接比较它们得到的是方法整体差异；不能把差异单独归因为“是否包含反演”。后续若要做组件因果消融，必须另立协议，不能将改写版本称作官方原样基线。

## 2. 预算与参数来源

| 配置来源 | Jain λ | Jain更新数 | Jain步长 | 模型设置 |
|---|---:|---:|---:|---|
| helper默认 | 0.03 | 10 | 0.0001 | 由调用者提供VAE |
| CLI默认 | 2 | 15000 | 5/255≈0.019608 | 目标/代理均SD1.4 |
| README GS命令 | 10000 | 继承15000 | 继承5/255 | 目标`stabilityai/stable-diffusion-2-base`，代理`CompVis/stable-diffusion-v1-4` |
| 论文v1 | Table1分列10000/20000/50000 | 附录11.3为15000 | 附录11.3为0.020 | 表格涉及SD1.4和SD2.0 |

依据：[README:31–36](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/README.md#L31-L36)、[CLI:35–109](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/forgery.py#L35-L109)、[论文v1 §4.3、Table1、附录11.3](https://arxiv.org/html/2504.20111v1)。裸CLI与README的λ相差5000倍。论文公式(3)写L2范数，固定代码实际为均值平方误差；二者不能未经核对当作完全相同的数值目标。后续应明确“固定代码配置”与“论文设置”的区别，保留代码数值，不自行换算以追求效果。

Imprint代码默认151次更新，验证索引0、10、…、150；最后索引150对应第151次更新。固定代码参考：[参数:65–67](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_imprint_forgery.py#L65-L67)、[循环:186–205](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_imprint_forgery.py#L186-L205)。阶段10的10次更新是诊断预算，不能代替完整默认预算结果。

每个方法分别记录参考预处理、冷启动、暖机、优化、导出及评估用时。Jain核心每任务一次参考编码，加每更新一次编码/输入反向；Imprint每次更新包括整段可微反演及检查点重计算。相同更新数不是相同计算成本。实际速度和完整预算在本环境的可运行性尚未测定，不能用CPU合成测试推算GPU耗时。

## 3. 实际交付与检测对象

Jain入口在[forgery.py:242–251](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/forgery.py#L242-L251)先把优化后的浮点张量送入检测，再调用[save_img:139–143](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/my_utils.py#L139-L143)转uint8并存PNG。8位转换是非负值截断，不是四舍五入。CPU合成张量检查确认保存重读后与原浮点输入不同；对真实检测结果影响尚未测试。

独立的[eval_gs.py:78–104](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/evaluation/eval_gs.py#L78-L104)确实读取PNG计算图像距离，但ASR取自**文件名中此前保存的检测分数**，并未对PNG重新执行水印检测。它以`>=0.71484375`计数，与入口打印的`<=0.05`方向不同。缺失或读取失败文件被跳过，分母是实际进入统计的文件数。公开代码不能据此证明论文所有表格使用哪条路径，更不能证明论文结果错误。

公平比较的主产物统一为已保存PNG：攻击端先写图并固定SHA256，评估端重读同一字节对应的像素，再执行既有官方GS验证；两个攻击共享同一评估实现、身份和参数。浮点张量结果只能作为辅助诊断。图像质量也基于同一PNG与同一载体计算。不得将文件名分数当作重新检测结果。

Jain入口的有效预处理来自较晚导入的[image_utils.py:17–26](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/image_utils.py#L17-L26)：Resize短边、CenterCrop、ToTensor、映射到[-1,1]；Imprint入口是直接resize为正方形。因此先冻结共同RGB 512×512载体，避免非方图裁剪差异成为混杂因素。必须记录原图、规范化输入和交付图各自哈希。

## 4. 能直接复用和需要明确适配的部分

已检查本用户项目缓存目录，仅存在SD2.1与SDXL的模型目录；未发现SD1.4。它只说明该已知缓存范围，未扫描其他用户或全服务器。当前不下载模型。因此README原始模型组合无法直接复现。

可研究的**共同代理设置**是：两者使用同一已有SD2.1 snapshot，Jain只用其VAE，Imprint使用VAE和UNet；目标沿用现有SDXL/GS评估。这是明确的模型情境适配，不是Jain原论文数值复现，也不能因模型都叫SD就视为相同条件。准确snapshot与版本沿用现有存档，但正式启动仍须重新冻结。

Jain的表示`mode/s`、λ、梯度步长与像素范围应原样保留。其原有目标反演helper同样使用`mode/s`；见[my_utils.py:44–62](https://github.com/anubhav1997/watermark_forgery_removal/blob/04433962437cbf08ad701b7b43124de07df0b666/Gaussian-Shading/my_utils.py#L44-L62)。共同评估使用本项目固定的官方目标管线，不能混入这个不同的反演实现。共同GS阈值保持严格`BA>0.70703125`；Jain的0.71484375不用于替换它。两者的原始水印配置也不等价，统一比较只隔离攻击核心。

## 5. 已完成的CPU适配核验

通过AST仅提取固定源码函数，不导入上游入口、pipeline、open_clip或权重。使用显式CPU和合成线性编码器检查六项：三步闭式更新、冻结模型参数前后输入更新一致、范围裁剪语义、真实导出字节、有效预处理、无pipeline导入。

第二版检查6/6通过。第一版有一项测试预期值错误：以双精度实数算术结果比较FP32范围映射，误差约5.94e-8；已保留原脚本及失败记录。修正版显式采用FP32计算预期值，未改变上游算法或放宽容差。见[原记录](../reports/cover_baseline_contract/cpu_checks.json)、[修复记录](../reports/cover_baseline_contract/cpu_checks_r2.json)。

源码的`vae.requires_grad=False`是普通属性赋值，并未冻结参数的`requires_grad`标记。合成检查确认改用真正参数冻结时，三步输入更新相同；但这不构成真实VAE的数值等价证明。后续[真实VAE检查](../reports/13_vae_core/report.md)已确认：参数冻结未通过逐位等价，而原参数状态三步输出跨进程一致。执行基线保留上游参数标记。

该CPU审计新增预训练模型实验0，GPU使用0；17份历史execution与服务器逐一核对，累计2206.407460845541秒不变。来源、测试和运行核对见[审计目录](../reports/cover_baseline_contract/)。

## 6. 下一次实验的准入设计

已完成共同代理情境下的三步核心等价与重放检查，后续保留原参数状态。[阶段14/15](../reports/15_imprint_timing/report.md)已完成100步VAE核心计时与Imprint原生循环计时，给出Imprint10步/Jain447步的近似开发预算。下一项完成[三组任务设计](PAIRED_COVER_PILOT.md)的输入生成、信息接口和CPU核验，再连同预算冻结执行配置及代码。该开发比较不替代完整151/15000步论文预算。

通过后，才冻结独立载体/参考组合的成对比较。作者代码预算与相同计算预算作为不同视图；匹配计算预算前可做独立的无目标反馈计时检查，随后锁定更新数。不能观察目标检测结果后延长某一方法、修改λ或挑选检查点。

图像代价同时报告保存PNG相对载体的RGB MSE、PSNR、L∞和独立内容合格标签。失真阈值若要作为成功条件，必须在确认集前由任务要求固定；当前阈值为null，不能根据所得结果倒推。较低代理损失、较少更新或更高单次GS位准确率都不能单独证明方法更优。

每任务每方法只交付预定最终图片，失败也保留在预定分母并单列。普通GS端点为水印迁移，完整几何/SemBind接受保持unknown。只有同任务、同信息权限、可核查成本与完整判定共同成立时，才能进一步讨论新方法贡献；相同函数拆成两个文件仍不构成系统权限隔离。


## 2026-10-24接续纠正：原生入口参考路径与完整预算

[PSNR及原生路径审查](../reports/psnr_reproducibility/report.md)已确认旧PSNR uint8回绕并定位其官方修复。另有真实CPU函数证据表明：官方入口PIL_to_torch→invert_image(image_pt)把RGB01直接送入参考VAE，而项目pixel_to_latent(PIL)送入[-1,1]。此前项目native10只复用了原生优化结构，不能因此声称完整CLI参考路径等价。既有实验保持其实际实现及开发结果，不重写历史。

原生校准固定150次实际更新、Adam0.01、无mask，保留默认CLI151与论文150的索引区别；主案明确保留官方RGB01参考路径，待父线程审阅后才实施。全100对复现尚缺齐备资产。参见[固定提案](../protocols/31_native_calibration_proposal.json)。
