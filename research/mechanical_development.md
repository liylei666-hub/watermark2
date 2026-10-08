# 新源机械改色开发控制

2026-10-08：新增1个苹果源图及1对机械改色/同区域控制。主体果皮由红色变为绿色，控制保留红色；原图、JPEG70、缩放0.5三个版本均在评分前视觉审核。矩形背景改色和边界伪影明确保留，不能当作自然语义攻击。

## 处理与全部结果

[配置](../configs/sd15_clip_mechanical.json)固定新提示词和种子2026100821。仅运行1个新源，没有根据得分增加样本或修改阈值。此前3个无效改色保留；这4个源全部属于开发数据，不进入新的测试组。

[脚本](../scripts/sd15_clip_mechanical.py)分prepare和score。prepare只生成草图及水印源，不评分。目视确认红色主体后固定矩形xyxy=[80,100,287,317]，按预定义红色色相/饱和度选择30,077像素，占全图11.47%。[构造脚本](../scripts/prepare_mechanical_control.py)对控制和改色用相同RGB→HSV→RGB、相同掩码，仅色相偏移为0/85。控制最大像素差5，未压缩图掩码外逐像素不变。两成员同样应用JPEG Q70/subsampling2及BICUBIC缩小至256再恢复512，保留JPEG字节和解码PNG。

[评分前审核](../reports/mechanical_development/variants/visual_review.json)于17:34:05Z绑定9张图的SHA-256；score先校验再加载模型。审核由Codex完成，不是独立人工标注。[九图网格](../reports/mechanical_development/variants/review_grid.png)显示主体果皮红→绿，原有绿色中心斑块仍存在；同时可见背景和边界伪影。有效性仅指机械颜色事实改变。

| 匹配计数 | 原图 | JPEG70 | 缩放0.5 |
|---|---:|---:|---:|
| 水印源 | 51 | 10 | 23 |
| 同区域控制 | 50 | 9 | 23 |
| 机械改色 | 20 | 2 | 8 |

patch L2容差2.0、计数阈值10保持未经校准的开发设置。匹配越多越倾向接受，计数≥10接受。未压缩改色被原生检测器接受；JPEG控制、JPEG改色和缩放改色在最终计数阶段拒绝，其他步骤完成。JPEG源10与控制9处于边界，不支持稳定正常接受率结论。单一机械样例不能估计攻击成功率、FPR或跨防御表现。

原生流程是SD1.5/CLIP image features + CSI SealCore，以待检图派生参考噪声。没有caption、credential、payload、policy或实例认证输出，不是完整实例认证验证器。原注册latent仅为oracle诊断，掩码不进入原生判定。许可、来源及公开开发key见[基础报告](sd15_clip_smoke.md)。没有原SEAL复现、黑盒安全或新颖性主张。

## 执行与审计

物理GPU7以UUID绑定，逻辑cuda:0；不查询/初始化GPU6。prepare PID9586，冻结17:31:25Z，结束17:31:37Z，模型阶段12.3792秒，生成2张、验证0张；score结束17:34:53Z，24.5135秒，验证9张。两次exit_code=0，900秒上限未触发。prepare峰值allocated/reserved为3,783,135,744/4,005,560,320字节；score为3,548,317,696/3,735,027,712字节。权重下载0，付费0。17:41:43Z复查GPU7为1MiB/0%，无本次进程。执行服务断开后恢复仅取回结果，没有重跑模型。

完整证据位于[审计目录](../reports/mechanical_development/audit.json)：原始图片、数组、冻结文件、日志、退出码、runtime及输入字节快照均保留。[CPU审计](../scripts/audit_mechanical_control.py)核验19个哈希绑定文件，复建13个PNG/JPEG/掩码文件逐字节比较，复算9行参考噪声、patch L2、计数、接受和oracle诊断；全部通过。噪声差0，L2最大差1.7764e-15。这是同实现保存阶段复算，不是独立模型复现。

另加[图像/数组绑定](../reports/sd15_clip_smoke/artifact_bindings.json)，覆盖此前及本批21条记录；每图文件哈希、RGB像素、特征、参考噪声、反演和L2数组均绑定。原始输入字节快照保持冻结SHA，包括行尾。补充[当前环境及预处理哈希](../reports/sd15_clip_smoke/provenance_supplement_20261008.json)，记录diffusers0.29.2、transformers4.41.2、Pillow10.4.0，以及scheduler/config/tokenizer/feature-extractor等小文件；事后观察不能倒推此前执行时的全部包版本。旧原始产物未覆盖。

## 独立校准门槛

工程流水线可进入预先登记的新批次。固定12新源、6校准/6测试，JPEG70/JPEG90和缩放0.5/0.75；阈值只看校准允许变体，测试不重调。加入未加水印图及明确权限的错误参考诊断，只报告小样本实际观察；若原图和正常处理不稳定，先诊断稳定性。当前没有校准后的安全性结论。
