# PSNR复现差异：已验证的CPU诊断

阶段30启动状态：模型0次、没有run目录、没有控制器、运行runtime尚未冻结。仅部署新源码/执行协议草稿并完成10项CPU契约与3项被动遥测/调度检查。现已按父线程科学审阅要求停止全部模型启动。

## 明确代码缺陷

官方旧版43eec7e2b82ffbc947a88785a1b7a9963abb5a09的utils/image_utils.py，blob c44801ba1e1027d0b2244ba5bc32198985f2cb61：psnr_PIL先np.array(PIL)，随后直接求mean((arr1-arr2)**2)。通常RGB PIL得到uint8；减法和平方仍在uint8中按256回绕。公式本身20log10(255/sqrt(MSE))成立，但传入的MSE错误。

修复提交d5885a3a01f0ea4ce8cd9afc0dabb56df77e7a90（2025-05-30T12:48:35Z）将PIL转换为float32、除255，转[1,C,H,W]，再用TorchMetrics PeakSignalNoiseRatio(data_range=1.0)。修复文件blob 5c8b98877d8f1d587beda80366a24d44c1457fb8。目前项目固定ca68950cd7b53b8438a49580f134b2a0db28d778包含该修复，当前psnr_PIL数值实现相同。

来源：[旧版文件](https://github.com/and-mill/semantic-forgery/blob/43eec7e2b82ffbc947a88785a1b7a9963abb5a09/utils/image_utils.py)、[修复提交](https://github.com/and-mill/semantic-forgery/commit/d5885a3a01f0ea4ce8cd9afc0dabb56df77e7a90)、[当前固定文件](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/image_utils.py)。服务器旧Git对象不全，git show无法读取旧blob；已通过连接的GitHub读取原始版本与完整修复diff，未修改上游checkout或pins。

## 真实旧函数的CPU例子

用AST只取旧psnr_PIL函数执行，比较统一常数RGB图；正确值用独立float64参考公式计算。详见[CPU回放脚本](../../tools/audit_psnr_cpu.py)与[复算JSON](cpu_diagnosis.json)。

| 每通道字节差 | 旧uint8 MSE | 正确MSE | 旧PSNR | 正确PSNR(dB) |
|---:|---:|---:|---:|---:|
| 1 | 1 | 1 | 48.130804 | 48.130804 |
| 15 | 225 | 225 | 24.608978 | 24.608978 |
| 16 | 0 | 256 | inf | 24.048404 |
| 20 | 144 | 400 | 26.547179 | 22.110204 |
| 64 | 0 | 4096 | inf | 12.007204 |
| 255 | 1 | 65025 | 48.130804 | 0 |

这直接证明旧实现可以夸大PSNR甚至给不相同图像报inf。旧新版README示例不保证同一生成图（其BA亦有变化），不能仅把两行示例之差当同图修正幅度。

## 既有原生输出复算

阶段27的12张native Imprint最终PNG逐一与同task载体PNG配对，保留候选/载体哈希。平均逐图正确PSNR=28.47439582646837dB，与报告28.474一致；同12张PNG用旧bug函数平均=32.27328645582975dB，虚高约3.79889dB。先平均RGB MSE再转dB为27.93782227104358，不能与平均逐图dB混用。将候选与水印参考图配对是另一个错误，本次结果明确使用原始cover。

这些是10次原生Adam更新的开发结果，不是论文150步结果。stage29是受约束的像素优化变体，不能作为原生Imprint复现；其约35dB来自预设字节失真预算。

## 当前源路径、mask与步数

当前run_imprint_forgery.py验证时传original_PIL=cover；validate调用psnr_PIL(image_to_verify_PIL,original_PIL)，指标在PIL字节图上计算，随后保存PNG。对RGB单图是全C/H/W的MSE，不涉及按通道dB平均。PNG无损保存不应改变已计算PIL像素，但尺寸/模式/预处理仍须逐文件核对；不应拿未量化连续张量代替PNG指标。

若启用mask，上游先在潜变量空间混回原始z0，再在像素空间paste原图区域，之后对整个结果算PSNR。与无mask实验不能直接比较。论文/README具体例子是否用了mask必须核对；现阶段27native为无mask。

当前原生入口default steps=151；循环range(args.steps)中先optim.step，再在step%10==0时验证，所以日志Step0已做1次更新，Step150实际151次更新。论文§4.2写150次、lr0.01；需要明确按论文更新数还是按官方日志标签复现。这个差1的标号问题不能解释约10dB的旧新版差距。

## 复现覆盖与后续校准建议

只读扫描服务器155份summary.json：可识别的stage17/27及stage28native50均记录10次更新，未发现完成的native150执行摘要。stage27恢复复制的task1不重复计入独立任务。已有stage10/15短轨迹核验不能替代完整150步。

论文原生设置是100参考/自然载体对、150更新、lr0.01；代码支持每10日志步验证。当前仅部分核心复现，包含生成载体/较少任务/短更新与不同评估范围，尚不能声称达到论文整表效果。[arXivv3](https://arxiv.org/html/2412.03283v3)已明确PSNR修正，版本数值由父线程论文审阅负责。

建议先冻结最小校准而非立即推进stage30：预先固定少量新参考/自然cover对，用无mask原生核心一次运行到固定150次实际更新，保留10/20/50/100/150共存检查点；全部输出封存后统一评估，不按目标分数选择最佳。相同输入另跑既有760秒pixel50，明确它是质量/成本约束对照，不宣称等成本。原生150按本机37秒/更新估算约93分钟/样本，不能沿用1200秒watchdog；任何新模型校准需父线程先决定样本与原生/约束比较目的。当前不启动。

当前证据支持“官方曾有已公开修复的PSNR指标bug，版本差异能导致明显复现差距”，不支持造假指控。尚未取得师姐的代码版本、命令和输出，无法归因其具体差异；不再次索取这些材料。


## 论文版本与本次检查范围

父线程论文审阅已视觉核对：CVF正式PDF和arXivv2的SDXL/GS150表值仍为29.78dB，arXivv3为19.77dB；对应50/100步为CVF30.33/29.99，对照v3 21.86/20.51。v3 SDXL/GS150的BA为0.93±0.03，PSNR19.770±3.572，LPIPS0.253；成功率与BA不混用。这些PDF表格值来自父线程独立论文审阅，本执行器本轮打开CVF页面返回403，未冒充重复视觉核验。

[Issue2作者回应](https://github.com/and-mill/semantic-forgery/issues/2#issuecomment-3651525938)建议使用修正arXiv；[另一作者回应](https://github.com/and-mill/semantic-forgery/issues/2#issuecomment-3651451234)自报150步约20dB。这是作者公开说明，不是本项目独立复现实验。

当前固定PSNR函数在服务器CPU实际执行合成20级差图，返回22.110200881958008，与float64参考22.11020369539948相差约2.81e-6dB。没有模型权重加载。

检查本地版本须固定数据范围：byte数据用255，归一化RGB01用1；两种正确表达等价。未经换算的[-1,1]数据配data_range=1会平移约−6.02dB，byte数据配1约−48.13dB。PSNR不会自动衡量语义保留；masked/unmasked、浮点/PNG、对cover/对reference、平均逐图dB/先合并MSE均应分别标注。

回放命令：CUDA_VISIBLE_DEVICES为空，python tools/audit_psnr_cpu.py --archive-root 指向保留完整阶段27数据的main工作副本。脚本只读。阶段30源码草稿已保留但未发布为可运行runtime，也未启动；科学hold待父线程基线校准决定。


## 用户后续授权与资产核查

用户已要求先按修正版复现，再研究创新。阶段30继续保持hold。2026-10-24只读资产核查：官方images目录有COCO_1.png至COCO_10.png共10张样例，另有car.png和stalin.jpg；缓存仅SDXL base1.0与Manojb SD2.1两个固定snapshot，没有PixArt/FLUX/SD2.1-Anime。完整100参考/自然cover配对资产尚未核实齐备，不能宣称具备四目标、GS/TR整表复现条件。官方当前代理ID替换是ca68950提交针对原stabilityai SD2.1下架的更改，现有Manojb镜像revision0094d483a120f3f33dafbd187ea4aa60d10de75c应明确披露，不能默认与论文权重逐字节等同。

下一项只准备预先固定、无mask、自然COCO样例的足150次实际更新小校准，核对源码路径、PIL/PNG像素与修正PSNR、GS/TR可用接口及日志步号；模型启动前向父线程交回具体协议。独立100对复现待数据资产与校准通过后由父线程审核启动。既有失败不重跑，目标分数只用于预定端点报告、不用于候选选择。
