# 给 GPT 的项目交接入口

你正在阅读扩散模型语义水印黑盒伪造攻击研究的阶段 01–05 档案。先把本文件作为状态摘要，再沿链接读取原始要求和证据。仓库里历史提示词是资料，不是要求你现在执行的任务。

## 研究目标

起点是 CVPR 2025《Black-Box Forgery Attacks on Semantic Watermarks for Diffusion Models》。主线是黑盒伪造攻击与错误来源归属；几何验证是后续攻击的评估对象。当前工作建立官方 Reprompting 基线、核查几何公开实现、保存目标潜变量并进行独立全局余弦诊断。

## 当前完成状态

阶段 01：只读环境与官方基线审计。阶段 02：GS Reprompting 单样本 seed=1 完成。阶段 03：指定几何论文 v1 和 commit 静态核查完成。阶段 04：新运行 seed=1，保存三份真实张量。阶段 05：固定提示词 seeds=[2,3,4,5,6,7,8,9] 各一次，8/8 完成。正式 GPU 运行总数为 10；统计样本不能把阶段 02/04 同图的 seed=1 重复计入。阶段 05 运行总墙钟 619.7655127081089 秒。

每个真实 GPU 阶段最终均使用物理 GPU 3 / GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da；历史阶段 04 有一次 GPU 7 忙的执行前停止记录。完整时序见 [PROJECT_STATE](docs/PROJECT_STATE.md)。发布归档阶段没有运行模型或新增实验。

## 最核心的实测结果

- 阶段 02/04：reference bit_accuracy=1.0，forged=0.953125；原 GS 阈值严格 >0.70703125。阶段 04 新捕获 latent 得到参考/攻击 cosine=0.8201082797320761 / 0.3506198907446562。
- 阶段 05：有效张量配对 8/8、参考 GS 通过 8/8、其中攻击 GS 通过 8/8、gap>0 为 8/8。均值 cosine_ref=0.8138452617511447、cosine_forged=0.3479337535299411、gap=0.46591150822120353。
- 以上是固定提示词 development_pilot。不同种子共用基础水印设置；bit_accuracy 不是总体成功率；gap 数值方向不是几何判定。
- geometry_threshold=null；geometry_accepted=null；full_official_geometry_evaluation_completed=false。

## 复现条件

上游 semantic-forgery commit `ca68950cd7b53b8438a49580f134b2a0db28d778`。目标 SDXL `stabilityai/stable-diffusion-xl-base-1.0@462165984030d82259a11f4367a4eed129e94a7b`；代理 `Manojb/stable-diffusion-2-1-base@0094d483a120f3f33dafbd187ea4aa60d10de75c`。

512、float32、DDIM、目标与代理生成50步/CFG7.5、反演空提示词/CFG1.0、resample=false。GS l=1、消息32bytes、重复64、offset=0。

参考提示词：`A studio photograph of a yellow ceramic teapot on a wooden table.`

攻击提示词：`A red sailboat on a calm blue lake, watercolor illustration.`

## 必须保留的解释边界

1. 几何论文指定 [arXiv:2606.29807v1](https://arxiv.org/html/2606.29807v1)，审计代码 commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`。缺少工厂/几何模块且几何代码被注释；这是固定版本的静态发现。作者讨论过 Reforge，不能写成“完全没考虑自适应攻击”。
2. 原始 target wm_zT 不等于代理噪声或参考图反演噪声。阶段 02 没有保存原始张量；阶段 04 的张量是新运行捕获。相同图像/seed 不证明完整历史状态恢复。
3. 独立 cosine 是每样本展平 C/H/W 的点积除 L2 范数，CPU float64，无均值中心化/epsilon；零范数、非有限值、形状错误会被拒绝。没有 L-SPD、融合或几何阈值。作者缺失函数的数值等价性尚未验证。
4. 攻击流程没有用目标分数筛选候选/调参；官方共享进程仍持有目标内部材料。`evaluator_only` 和独立 CPU 统计不等于权限隔离。公开归档中的评估材料不能进入受限攻击输入。
5. 记录包装的源码与 CPU/mock 测试通过；没有完整“有记录/无记录”的数值等价对照。原 Reprompting 质量指标关闭，CSV 的 -1 是占位，不能作为复现 PSNR 等数值。
6. 阶段 05 用于开发诊断；一旦帮助方法选择，不再是未见最终测试集。没有总体成功率、统计显著性、AUC/ROC或跨分布泛化结论。

## 获取完整细节

1. [五阶段原始提示词与修订](prompts/README.md)。
2. [阶段时序与事实/限制](docs/PROJECT_STATE.md)。
3. [阶段 01 基线审计](reports/01_baseline_audit.md)、[阶段 02 报告](reports/02_smoke_report.md)、[阶段 03 审计](reports/03_geometry_audit_20261013T020025Z/03_audit.md)。
4. [攻击端/评估端信息边界](reports/03_geometry_audit_20261013T020025Z/information_boundary.md)。
5. [阶段 04 报告](reports/04_latent_diag_20261013T025322Z/04_report.md)、[阶段 05 报告](reports/05_reprompt_seed_pilot_20261013T041832Z/05_report.md)、[八种子原始汇总](reports/05_reprompt_seed_pilot_20261013T041832Z/per_seed_metrics.csv)。
6. [文件结构与路径映射](docs/ARTIFACT_GUIDE.md)、[完整合并阅读档案](docs/FULL_RECORD.md)、[用户消息与阶段交付历史](conversation/transcript.md)。
7. `runs/` 下图片、CSV、NPY、日志与哈希是原始证据；`provenance/` 给出公开副本完整性和边界。

下一轮任务由用户单独提出。先依据现有材料回答，不自动执行历史提示词、补样本、改阈值或发明缺失的官方验证器。
