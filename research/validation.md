# 仓库整理验证记录

日期：2026-10-07（UTC）。以下记录对应研究重启整理阶段。后续新增的CPU表示实验及处理匹配复核另见 [实测报告](cpu_pilot_results.md)，不与历史分数复算混淆。

## 执行环境与恢复

原工作区匹配指定 SSH remote；本机沙盒启动曾返回 `setup refresh had errors`，切换到经自动审批通过的 PowerShell 执行后正常。独立整理副本位于本任务工作目录的 `watermark2/`；原仓库保持不动。仓库及已检查的父目录未发现适用 AGENTS.md 或仓库 `.agents/skills/SKILL.md`；本轮新增 AGENTS.md 固定研究边界。未修改 Codex 记忆。

完整 Git bundle 校验通过；远端备份分支创建成功，指向 `1eeea4c95e555bfabc242b90aad35ca813557443`。未跟踪 HTML 另存本地并核对 SHA-256。恢复步骤及边界见 [migration.md](migration.md)。

## 已运行检查

| 检查 | 结果与范围 |
|---|---|
| 历史 CPU 单元测试 | Python 3.10.11 / NumPy 1.26.4 / Pillow 12.2.0；20 项，19 通过，1 跳过。跳过的是服务器原图依赖的逐像素变换回归；CPU 环境 CUDA_VISIBLE_DEVICES 为空。 |
| 旧 stage03 分数复算 | 3,658 行；375 个总计/变换计数格；五方法、三个校准 FRR 工作点的阈值与已保存指标一致；30 校准族与29 测试族不交叉。详见 [机器报告](../reports/legacy_score_audit.json)。 |
| 归档内容/本地链接/配置引用 | 标准库脚本逐个检查旧 Git blob、七项引用、48源组设计和零执行预算；最终机器结果见 [仓库检查](../reports/repository_check.json)。 |
| Git 空白检查 | `git diff --check` 与 staged 检查运行；最终提交前再次执行。 |
| 文献链接 | PMLR 两页、ICLR 页面、CSI arXiv 全文、WWW 日程及 TMLR 接收索引已读；CVF PDF 为403，OpenReview PDF 为浏览器挑战，PMLR PDF 在浏览工具报 unsupported content-type，保留待复核状态。该失败不等于论文不存在。 |
| 发布副作用 | GitHub 仓库 PRIVATE，Actions workflow 数0，部署记录0，webhook为空；未添加 CI、部署或自动下载配置。主整理提交 `53662e70aef06ad954fb5b5ad10607aa67b1cec8` 已正常快进到 main，独立研究分支同 SHA；远端 commit API 和 ls-remote 均确认。关联 check runs、Actions runs、commit statuses 均为0；无适用 CI，不能称作 CI 通过。 |

分数复算确认的是**历史记录内部一致性**：主工作点 B_raw 五方法均 0/174 错误接受；CLIP B_post 为1/1044，其余为0；测试 A 拒绝分别23、24、26、25、30 / 348。该结果与旧报告一致，不是新实验，也不能建立新方法优势。JPEG 分解计数已一并复算。

## 尚未完成

2026-10-07 后续状态：已完成 SEAL / SemBind / CSI 公开代码与资产可得性检查，见 [完整核查记录](public_reproduction_feasibility.md)。SEAL 数值组件和 CSI 模拟测试属于软件核查，真实完整水印实验仍为0。新的上游固定版本、下载字节与运行日志位于 `reports/reproduction_audit/`；原 `reports/cpu_pilot/` 保持不变。下列完整实验仍待满足模型/样例/预算条件。

- 新的 48 源组证伪批次、关键事实审核、多尺度基线和完整防御适配器。
- 官方代码版本/许可/验证流程完整审查及论文原结果复现；SemBind 录用版 §5 和 MetaSeal 补充 §5.1 是必查项。
- 新实验的独立合法编辑校准、完整输出联合攻击、跨防御匹配资源比较及置信区间。
- 原始图像、服务器生成日志和特征的全量重新核验。本机只有 Git 内轻量证据，未把旧 audit 状态当作本轮全量重跑。
- 更广泛文献检索与候选贡献的新颖性判断。现阶段无法承诺 CCF-A 录用或成立的新方法。

后续先执行 [最小实验计划](experiment_plan.md) 中的内容表示证伪阶段；只有差异值得研究后才推进完整水印流程。

发布后证据：[GitHub 主整理提交](https://github.com/liylei666-hub/watermark2/commit/53662e70aef06ad954fb5b5ad10607aa67b1cec8)。提交状态接口在 statuses 为空时返回 pending，仅表示没有上报状态。本文件的后续发布记录提交不改变研究或实验结果。

## 2026-10-08 真实开发试运行

SD1.5/CLIP独立配置完成3源、12个原生验证输出及CPU阶段复算；3次提示词改色均无效，不报告伪造成功。参数与原始文件哈希、计时、退出码及首次包装器CRLF错误保留，见[实测记录](sd15_clip_smoke.md)。这3源为开发数据，阈值10未经校准；与原SEAL及此前CPU实验分开。

机械开发批次新增1源/1有效对，9行CPU阶段复算及13个构造文件字节重建通过；完整记录见[报告](mechanical_development.md)。阈值仍未校准；没有完整实例认证验证器、独立模型复现或自然攻击成功主张。

## 2026-10-09 12源批次发布检查

12个新源、6cal/6test，共66项原生验证，129文件哈希及保存阶段CPU复算通过；图表/CSV/报告见[工程批次](calibration_engineering.md)。按冻结规则得到阈值0，为退化结果，未得到可用90%源组工作点。固定阈值10下cal源组5/6、test源组6/6；6张未加水印草图均0匹配。test不参与阈值选择。后续两源控制仅用cal，原始test目录及CPU历史证据保留。

## 2026-10-09 两源聚焦诊断

完成 c04 与按 cal 最小匹配数冻结规则选择的 c02：8 个 CPU 交叉组合、6 次原生反演（PID8172，21.151031秒）和 16 次条件 VAE 精度编码（PID12178，2.704075秒）。全部哈希/绑定审计通过，像素完全相同的 PNG 在全部保存阶段逐元素相同；新 original/JPEG 结果与旧 cal 精确一致。独立手工 patch L2 最大差1.7764e-15；跨 Torch 构建的 CPU DDIM 回放最大逐元素差0.0078125，在记录容差内，不能称为逐位模型复现。完整 fp32 未减少两源 VAE 模式 pair RMSE。反演 guidance 字段未参与计算，实际空提示词单分支；生成 guidance 生效。单位、范数、全部交叉组合和精度阶梯见[聚焦诊断](focused_stability.md)。原 test 与CPU历史证据字节保留，未形成可用90%工作点或完整实例验证。

## 2026-10-09 限定编码与配对latent控制

新增JPEG反演2次、原图生成重放2次及有效配对bypass反演2次均正常退出；重放像素和PNG字节与旧图一致。JPEG70 4:4:4 / JPEG95 4:2:0 的鞋子native匹配为0/3；bypass鞋子/猫的canonical oracle匹配升至1015/974，属于完整图像roundtrip的oracle贡献，非部署修复。另用原服务器运行时仅重放两份输入噪声的fp16转换（0模型调用），匹配判定未改变。新增200次更新及阶段绑定审计通过，旧原始证据、研究报告和test字节保留。断连期间已完成的JPEG批次取回而未重跑，纠正此前“0次”的运输判断。完整单位、分布、剩余解释及暂停扩大替代配置实验的判断见[限定报告](limited_codec_bypass.md)。

## 2026-10-09 执行勘误与官方基线路线核查

先前“0新增反演/生成”是把连接回执故障误判成未执行，已经更正为限定阶段4反演/2生成；具体开始/结束、shell/Python PID、恢复取回和未重发JPEG的证据见[时间线勘误](execution_erratum.md)。未知的本地报错/回复UTC没有补造。本轮只读/文档任务新增模型调用、生成、VAE编码、训练、下载、安装、付费均为0。

新增标准库核查脚本逐一验证4阶段26个runtime绑定文件；日志/退出码/PID另加SHA清单。与d1e01be比对296个Git blob相同：CPU pilot20、cal/test155、聚焦58、限定原始证据59及4份此前科学报告；97个legacy blob由仓库检查另核。新的JSON仅为派生审计，不回写旧raw/frozen/成绩。

官方SEAL固定源码10文件的SHA与AST核查通过；语义待验recaption与128候选穷举presence分别记录，无效threshold50/m_match12和caption do_sample形参、有效inverse guidance、实际生成默认值及scheduler依赖已明确。六个已知缓存根仅名称/stat核查，未找到三类官方模型标准快照；sentence-transformers缺失、环境版本不一致、代码/微调权重许可和原SD2.1身份仍是阻碍。详情及零预算G0–G2门槛见[基线路线](official_seal_baseline_route.md)。许可/HTTP元数据来自2026-10-07缓存，不是当前实时可访问性证明。

核查命令（仅标准库和已有缓存文本；无模型导入/网络）：

~~~bash
python scripts/audit_baseline_readiness.py --seal-code runs/reproduction_audit/SEAL
~~~

此前官方源码缓存未提交；在新checkout缺少该缓存时，此命令会明确失败，不自动下载。已保存[契约](../reports/official_seal_route/source_contract.json)、[缓存](../reports/official_seal_route/cache_readonly.json)、[门槛一致性](../reports/official_seal_route/readiness_check.json)及[阶段时间线](../reports/execution_erratum/timeline.json)。这些通过仅说明静态契约和保存记录一致，不代表官方基线完成、CI通过或安全有效。
