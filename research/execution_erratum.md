# 执行计数勘误与证据时间线

2026-10-09（UTC）。先前回复中的“0 新增反演、0 新增生成”是错误报告。限定 JPEG/配对 latent 阶段实际完成 **4 次反演、2 次生成**，另有一次 0 模型调用的 dtype 转换。科学结果以 [限定诊断报告](limited_codec_bypass.md) 和原始记录为准。本轮只做文件/代码/缓存元数据核查及文档整理，新增模型调用、生成、下载和训练均为 0。

## 为什么报告错了

在已授权的 2 次 JPEG 反演、2 次原图生成重放、2 次 bypass 反演预算内，一次本地工具请求包含配置/脚本写入、上传及 SSH 启动 JPEG。工具约 28.5 秒后返回 `exec-server transport disconnected`，外层错误包含 `Failed to create unified exec process`。我把“工具未返回成功回执”误判成“命令没有开始执行”，于是报告 0 新增；这个推断没有远端证据支持。它是连接/回执故障，不能当作自动审批拒绝，也不能当作远端任务未执行。

没有保存可靠的本地请求开始、报错或错误回复的 UTC 时间，故不编造这些时刻。下表任务起止来自服务器 frozen/runtime；回连时刻来自当时工具会话的只读 SSH 输出。没有修改服务器时钟，也没有独立校准两端时钟偏差。

## 已记录时间线

| 2026-10-09 UTC | 事件及证据 |
|---|---|
| 03:13:44–03:14:05 | 前一轮 6 次原生反演，Python PID 8172，属于 c1ffd556 聚焦诊断，非限定阶段新增。 |
| 03:28:19–03:28:22 | 前一轮 16 次 VAE 编码，PID 12178，属于 c1ffd556，非反演/生成。 |
| 03:50:54 | 限定阶段启动前只读查看指定 GPU7 空闲。 |
| 03:54:29–03:54:40 | **JPEG 已运行完成**：shell runner PID 19283、Python PID 19286，2 反演/0 生成，exit_code=0。 |
| 04:03:35 | 恢复后首次只读检查：GPU7 空闲、已有远端 runs/limited-v1/jpeg、无该项目模型进程。继而读取目录的 frozen/runtime/日志/退出码，确认完成早于恢复，取回同一目录，未再次发起 JPEG。 |
| 04:04:59–04:05:10 | 剩余预算原图重放：shell PID 22105、Python PID 22108，2 生成/0 反演，exit_code=0。 |
| 04:06:44–04:06:51 | 剩余预算 paired bypass：shell PID 22886、Python PID 22889，2 反演/0 生成，exit_code=0。 |
| 04:16:20–04:16:20 | dtype 直接转换核查，Python PID 26529，0 生成/反演/VAE 编码，exit_code=0。 |
| 04:17:20 | 最后一次指定 GPU7 检查：1 MiB、0% 利用率、无计算进程。 |
| 04:26:55.905 | d1e01be 的 main/research、旧备份、私有状态及无 CI 状态核验完成。 |
| 04:32:59 / 04:36:21 | 本轮缓存名称、stat 和包 metadata 只读核查，未导入 Torch 或加载模型。 |

三个限定模型阶段 wall 合计 28.908227 秒，计时边界为模型已加载后到结果保存，不是全部装载/SSH 耗时。

## 完成及取回原批次的证据

JPEG 的 [frozen](../reports/limited_codec_bypass/jpeg/frozen.json) 保存 Python PID、开始时间、配置和执行脚本 SHA；[runtime](../reports/limited_codec_bypass/jpeg/runtime.json) 保存结束时间、计数及输出 SHA；[退出码](../reports/limited_codec_bypass/jpeg/exit_status.json) 为 0。[日志](../reports/limited_codec_bypass/jpeg/execution.log) 依次记录 JPEG70 4:4:4 的 native/oracle/E=0/0/181、JPEG95 4:2:0 的 3/29/204，以 `Bounded phase complete` 结束。[runner.pid](../reports/limited_codec_bypass/jpeg/runner.pid) 为 19283，区别于 Python PID。

runtime 中 frozen SHA 为 `8300dc28f606032f9d6a48d8b25efac08f6e25294bc1df57e5be1c59a8343599`，results/partial_results 同为 `fab01cee85bd57af3e018e05fedf7377a1efc25e1f6a16d836eb9ecdd477cc24`；两份轨迹 NPZ：

- JPEG70 4:4:4：`be93670e043eade00dfca87353a43c12b476db5a5bec6b4a56fc647758cfb005`。
- JPEG95 4:2:0：`53427c4176711671648cd6cb3ea41d788ec2376537bfb14a5b97f41537e7813f`。

恢复后只归档、取回已有 JPEG 目录。三个模型阶段同一执行脚本 SHA 为 `6c3a3a0ac0f2ad2f70216dba46f3f380db4678ceac97cf36444e56a6fe24f0e0`。[启动器](../scripts/run_limited_codec_bypass.sh) 拒绝覆盖已存在目录；已取回 JPEG 的时间/PID/哈希保留，后两阶段分别有更晚的时间/PID。新的 [时间线核查](../reports/execution_erratum/timeline.json) 校验 4 阶段全部 runtime 绑定文件，并增加日志、退出码和 PID 文件 SHA 清单；这些附件原本不在 runtime 哈希表中，现结合 d1e01be Git blob 核查。

这是对已记录批次及恢复动作的确认，不把目录存在当作服务器所有可能未记录任务的穷尽证明。回执不确定时应先查 PID/退出码/日志和绑定产物；证据不足就报告“执行结果待核实”，不能报告 0，也不能立即重试生成。

原始实验文件保持 d1e01be 字节；旧 cal/test、聚焦诊断和 CPU pilot 保持此前提交字节。官方基线路线见 [下一步门槛](official_seal_baseline_route.md)。
