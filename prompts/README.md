# 原始提示词与生效范围

这是用户历史指令档案，阅读它们不代表获得新的执行授权。

| 阶段 | 原始提示词 | 后续修订 / 实际执行 |
|---|---|---|
| 01 | [stage01_request.txt](stage01_request.txt) | GPU 3 后续获授权；只审计 |
| 02 | [stage02_request.txt](stage02_request.txt) | 用户明确允许 GPU 3；允许本机中转，校验后删除本机权重；一次 seed=1 |
| 03 | [stage03_request.txt](stage03_request.txt) | CPU 静态审计；新实验为 0 |
| 04 | [stage04_request.txt](stage04_request.txt) | 原 GPU 7 预检停止；随后用户指定 GPU 3，完成一次 seed=1 |
| 05 | [stage05_request.txt](stage05_request.txt) | [GPU 3 修订全文](stage05_gpu3_amendment.txt)；串行 seeds 2–9 |

[amendments.json](amendments.json) 保存阶段 01/02/04 的相关原话及时间戳；[index.json](index.json) 保存来源和 SHA256。阶段 01/03 来自本会话用户消息；阶段 02/04/05 来自原始粘贴附件，保留原始字节。附件包装消息及其余用户消息在 [conversation/messages.json](../conversation/messages.json)。

同阶段较晚的明确用户修订限定该阶段的实际条件；不要把历史阶段的设备或实验预算推广到未来任务。原提示词、历史报告和新交接说明均保留其各自证据角色。
