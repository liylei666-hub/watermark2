# MANIFEST — 探索归档 20261027_pgsmf_mttgi

**创建：** 2026-10-28（Asia/Shanghai）
**作者：** WorkBuddy AI（自动化研究执行），研究者：Li YanLei
**性质：** 探索性归档，非冻结协议、非正式阶段报告

## 目录内容

| 文件 | 内容 |
|---|---|
| `README.md` | 全部五个阶段的合并记录（含所有关键数值表与结论） |
| `reports/stage31_imprint_code_audit_20261027.md` | Stage31 原生 Imprint 代码审计（路径、超参、z_T 对齐、张量清单） |
| `reports/stage31_crossmodel_transfer_diag_20261027.md` | 跨模型传递诊断 v1（逐任务、逐通道、分位、FFT 三档） |
| `reports/stage31_eval_chain_and_transfer_v2_20261027.md` | 评估链路解剖 + 4-pair 全表 + 传递诊断 v2 |
| `reports/pg_smf_pilot_report_20261027.md` | PG-SMF Pilot（V1/V2）完整结果与完整性说明 |
| `reports/stage31_vs_pgsmf_tensor_anatomy_20261028.md` | +6.25pp 的张量级解剖（三张表） |
| `scripts/pg_smf_loss.py` | V1/V2 损失与频域算子（纯函数，CPU 可测） |
| `scripts/pg_smf_attack.py` | V1/V2 攻击进程 |
| `scripts/pg_smf_eval.py` | 与 `evaluate31.py` 同链路的 SDXL 评估器 |
| `scripts/pg_smf_finish.py` | V1 元数据回填 + 4 组评估调度 |
| `scripts/pg_smf_supervise.py` | V1/V2 调度器（空闲 GPU 门禁 + 一卡一进程） |
| `scripts/mt_tgi_attack.py` | V3/V4 攻击进程（含多视界轨迹捕获） |
| `scripts/mt_tgi_eval.py` | V3/V4 评估器 |
| `scripts/mt_tgi_supervise.py` | V3/V4 调度器（工作池 + 队列） |

## 服务器原始产物

| 内容 | 路径 |
|---|---|
| PG-SMF Pilot | `/data0/liyanlei/watermark_research/runs/pilot_pg_smf_20261027/` |
| MT-TGI Pilot | `/data0/liyanlei/watermark_research/runs/pilot_mt_tgi_20261028/` |
| Native 基线（Stage31） | `/data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z/` |
| 事后 LPIPS | `/data0/liyanlei/watermark_research/reports/31_native_calibration_lpips_20261025/rows.jsonl` |
| 私有 GS 材料 | `/data0/liyanlei/watermark_research/private_eval/31_native_calibration_20261024T190323Z/` |

## 复现约定

```bash
# 环境
env CUDA_VISIBLE_DEVICES=<GPU_UUID> \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    CUBLAS_WORKSPACE_CONFIG=:4096:8 \
    HF_HOME=/data0/liyanlei/watermark_research/cache/huggingface \
    /data0/liyanlei/watermark_research/envs/semantic_forgery_py310/bin/python \
    mt_tgi_attack.py --variant v3 --task 1 --uuid <GPU_UUID> --index <IDX> --out <DIR>
```

**门禁**（每个子进程启动前）：`nvidia-smi` 查 `memory.used < 500 MB`、`utilization.gpu == 0`、无他人计算进程；排除物理 GPU 6；每卡 1 进程。

## 已知缺陷记录

| 事件 | 影响 | 处理 |
|---|---|---|
| V1 攻击写 `losses.json` 时 NaN 崩溃 | `probit/margin/huber/seconds` 与 timing 丢失 | 从 stdout 回填 loss/gnorm（6 位小数），标注 `reconstructed_from_stdout` |
| V2 首轮评估 `zref_np` 变量名被误改 | 评估中断 | 修复后重跑全部 4 组 |
| V4 攻击 `z0_init` 未在 `no_grad` 下计算 | 第 2 步 backward 图复用崩溃 | 加 `no_grad` + `detach`；并由此发现 Adam 尺度不变性使 V4 ≡ V3 |

## 引用注意

本目录内所有数字均为 **n=2 任务 × 1 加密身份** 的开发数据结果，不得作为总体统计、论文复现或 SOTA 声明引用。引用时必须同时引用 `README.md` §7「边界与数据完整性」。
