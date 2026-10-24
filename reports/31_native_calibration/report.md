# 更正版 Imprint 原生代码校准：运行中

状态快照：2026-10-24 19:08 UTC。此文件没有目标结果，不能作为完整论文复现结论。

已发布源码 `bb3642f32df998b4f0c880ba58a3fb574ed6a76e`、运行清单 `a8912952e7a1520df58d200033f935b58e723986`。固定[执行协议](../../protocols/31_native_calibration_execution.json)，控制清单SHA256 `d1749a198fd94e7ba33eb69cb09dd85f404c7cc07697142df6dabec8d09b035d`。CPU检查8项通过，档案4418文件通过；真实权重GPU轨迹等价尚未独立证明。

指定服务器run：`/data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z`，控制器PID7784，19:04:16 UTC启动。参考生成PID7823已完成4张图。任务1 PID8949、任务2 PID8947于19:06:49 UTC启动，首两次实际更新有限。GPU0 UUID `GPU-aafaf524-a6f4-f646-a2b5-7d243e80c8a5`；GPU1 UUID `GPU-af8ecfa2-a36f-798c-9762-0a3cfb8a1fcd`。各子进程模型导入前独立验证空闲并UUID绑定，排除GPU6。启动前累计相关文件811119062字节。

保留官方更正版ca68950的参考RGB01输入与载体[-1,1]非对称路径，原生latent/MSE/Adam0.01，无mask，原参数requires_grad状态，直接抽取官方循环5条更新语句执行151次。实际20/50/100/150/151各保存一次；151为官方CLI Step150主端点，150为论文文字端点，两者均报告且不择优。20张候选全部封存后再评估4参考、4干净载体及20候选，共28张PNG。记录实际时间步、PNG/latent/Adam状态、同步耗时及失败。

只使用已有SDXL和Manojb SD2.1固定snapshot、首4官方COCO载体和首4官方提示词，新种子已事先固定。4任务沿官方offset0共享身份，不是独立密钥总体检验。只有10个现有COCO样本，不满足100对整表复现。镜像模型与论文原始SD2.1权重字节等价未知；无LPIPS AlexNet既有权重，LPIPS保留unknown。完整几何/SemBind接受和正式人工标签仍unknown。

预计两卡3.2–4.5小时；9000秒/攻击为工程watchdog，非缩短更新数。目标分数不用于调整参数、选择候选或决定继续。阶段30继续hold。本轮若失败则保留并停止，不自动重复相同已启动实验。
