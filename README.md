# watermark2

生成图像实例级认证的表示诊断工具。当前完成阶段 2：真实预训练 CLIP、SSCD、DINOv2 的小规模基线闭环。比较接收图像与缓存的参考特征；尚未实现水印载荷、签名或主动攻击评估。

服务器工作目录：`/data0/liyanlei/instance_authentication_research`。

```bash
cd /data0/liyanlei/instance_authentication_research
export CUDA_VISIBLE_DEVICES=""
export PATH=/data0/liyanlei/envs/stego_attack/bin:$PATH
python scripts/run_stage02.py --config configs/stage02.json --refresh-features
```

入口执行 CPU 测试、清单校验、UUID 检查、两个隔离工作进程、阈值校准、测试集评估、图表和运行产物审计。宿主机 GPU 5 依次运行 CLIP/SSCD，GPU 7 运行 DINOv2，每进程内仅有 `cuda:0`。不传 `--refresh-features` 时复用通过哈希校验的缓存。已有输出按运行时间保存于 `outputs/runs/`。

首次准备官方代码、权重与小样本：

```bash
CUDA_VISIBLE_DEVICES="" python scripts/acquire_stage02.py --models --images
```

下载器受 1.5 GB 总预算限制，使用固定代码版本和 Commons 查询快照；仓库不存储模型权重。已有服务器环境无需安装或升级依赖。网络失败会报错，不替代模型或数据。

- [阶段 2 报告](research/02_baseline_smoke.md)
- [服务器环境](research/02_server_environment.txt)
- [数据来源及图像许可](research/02_sources.md)
- [模型来源与 SHA-256](artifacts/models.json)
- [逐对分数](outputs/stage02/pair_scores.csv)
- [指标](outputs/stage02/metrics.json)
- [GPU 绑定证据](outputs/stage02/gpu_binding.json)

校准与测试各 10 个原图组。五种分数均以校准 A 的目标 FRR 5% 独立设阈值；B（同提示不同随机种子）缺失，C_proxy 为粗糙贴片流程检查。当前结果不能证明实例防伪或现成特征汇聚的新颖性。
# 阶段 3：同域实例区分

执行协议见 [03_generation_protocol.md](research/03_generation_protocol.md)。所有实验计算在服务器 `/data0/liyanlei/instance_authentication_research`，沿用 `/data0/liyanlei/envs/stego_attack`。固定生成器和文件哈希见 `outputs/stage03/generator_files.json`，提示词与族划分见 `data/stage03/prompts.jsonl`。

```bash
CUDA_VISIBLE_DEVICES= /data0/liyanlei/envs/stego_attack/bin/python scripts/run_stage03.py --config configs/stage03.json
```

入口验证服务器路径、既有模型资产和 GPU 5/7 的 UUID；支持校验后续跑。`--through preflight` 运行独立工程预检查，默认运行至机器审计。结果状态在 `outputs/stage03/run_status.json`，最终分析在 `research/03_same_prompt_diagnostic.md`。完整图像和特征缓存不进入 Git。

本轮实际结果：472/480 计划原图完成，p094 所属 vehicles08 族的固定 seed 被安全检查/单图超时路径标记为不完整，118 条提示词、59 个完整族进入评测；状态为 `audit_complete`。结果 CSV、阈值、指标和审计证据均在 `outputs/stage03/`。
