# 研究接续入口

更新：2026-10-18（Asia/Shanghai）。用户委托完整论文研究，授权自主继续直到需要协助，有用且核验过的进展正常提交GitHub。30分钟线程心跳已启用，id=`automation`。每次先核对真实进程、Git状态与机器账本，避免重复启动。

## 当前结果与活动任务

[Imprint交付路径诊断](reports/10_imprint_delivery/report.md)确定性revision3已完成：同一参考/cover、10次原生更新，内部损失下降0.595194，PNG交付损失下降0.544701，约91.52%的改善保留。交付差距由0.028210增至0.078703；最终浮点/PNG损失差仅0.000909。H1有单对图片的描述性支持，但差距不能直接称为主要瓶颈，更不能当新攻击收益。

四个检查点反演等价与内部重放通过，初始无记录重复梯度及记录前后梯度均逐位相同。53份原始文件中转哈希核对，CPU float64复算通过。原版API失败、revision2微小梯度差停止及冻结代码均保留。

**完整轨迹对照已经完成**：`runs/10_imprint_shadow_20261017T190952Z`，退出码0，402.741秒。相同初始化与10次更新、移除探测与中间记录后，最终z、路径张量、PNG及指标一致；8个输出文件逐字节相同。[核验](reports/10_imprint_delivery/shadow_verification.json)。这是同一开发样本的工程等价对照，不是独立攻击样本。

[阶段11固定点梯度诊断](reports/11_imprint_gradient/report.md)已完成：更新0/10两个依赖点余弦0.730945/0.675941，沿内部负梯度两项损失均下降，削弱方向冲突解释。8项差分核验通过6项；浮点交付目标沿自身方向相对差约10.0%/6.5%，原因unknown。固定半径0.001未调整，未优化或调用目标。交付方向像素变化也更大，不能宣称等代价收益。75份原始文件哈希及CPU张量复算通过。当前无活动模型进程；阶段07起16进程累计2114.525876435451秒，全部execution哈希与服务器一致。

下一项在相同点、已保存方向和半径下拆分VAE映射与反演的局部线性化残差，先定位数值疑点，再判断是否值得做优化干预。完整防御接受和跨模型收益仍未知。所有图像先固定哈希，不用目标分数选图或调参。

## 研究目标与完整性边界

核心问题：在参考关联明确、判定固定、零目标反馈条件下，代理端可计算的约束能否改善指定内容伪造的端到端结果，并解释来源。尚未形成新方法或顶会级证据；当前数据均为development_pilot。

- [完整评估契约](docs/EVALUATION_CONTRACT.md)：几何ICML最终版理论AND拒绝区域已查清，但公开实现、参考关联与固定工作点仍缺；不能以独立余弦替代完整接受。
- SemBind最终版E.1/Table17已有五组端到端代理masker测试Det.=0；不能说作者未考虑自适应攻击。公开代码不是完整GS-S验证器。
- [SEAL](docs/SEAL_EVALUATION_CONTRACT.md)：语义绑定数组、穷举布尔检测、百分位TPR路径不同；缺模型与固定语义协议。
- [PAI](docs/PAI_EVALUATION_CONTRACT.md)：全部5个公开提交及两版附录仍缺PCA参考与接口；暂不进入模型实验。
- [CSI](docs/CSI_INFORMATION_CONTRACT.md)会反馈检测失败，不能原样列入零目标反馈基线。Jain已有单图VAE表示匹配，外层GS汇总有方向问题，不能据此否定整篇论文。
- [PnP获取证据](reports/pnp_source_availability.json)：GitHub固定HEAD只有README入口，指向匿名实现；匿名HTTP403，完整性unknown。未运行或下载权重。

新颖性必须超出已有VAE匹配、条件恢复/语义编辑及BPDA等技术。见[方法假设](docs/METHOD_HYPOTHESIS.md)、[文献矩阵](docs/LITERATURE.md)、[研究审查](reports/research_review.md)。当前是有边界的定向检索，不是穷尽证明。

## 已有实验

- 阶段05：固定提示词8种子GS各通过8/8，参考/攻击余弦0.813845/0.347934，不能推断总体成功率。
- [阶段07](reports/07_prompt_control/report.md)：seeds101–103，同/异提示词六次；GS每组3/3，余弦0.290478/0.306216，差值方向不一致。
- [阶段08](reports/08_target_roundtrip/report.md)：目标自身往返六候选，余弦0.540099/0.518726，均高于代理，但不是单因素架构归因。
- [阶段09](reports/09_vae_roundtrip/report.md)：仅seeds101/102完成，目标/代理VAE余弦0.754408/0.510815；seed103预检停止。原组禁止重试或补样。
- [阶段01–05谱系](docs/PROJECT_STATE.md)保留历史10次正式进程；阶段02/04 seed1图片相同，不是两个独立样本。真实目标张量27份。

内容判据与伪造范围、原水印、完整防御、错误归属及报警按[比较契约](docs/BASELINE_COMPARISON_CONTRACT.md)分别报告。[人工内容评审](docs/CONTENT_ADJUDICATION.md)当前0份，助手视觉观察不可冒充人工标签。事件账本已接入阶段07六个真实任务，完整防御率null。

## 执行边界

仅 `liyanlei@172.18.185.249`、`/data0/liyanlei/watermark_research`；仅核对空闲的物理GPU0–2，一张卡、UUID绑定、程序内cuda:0、串行。禁止本机GPU及其他服务器实验。用户已取消GPU时间授权上限，实际时间仍记账；诊断保留1200秒工程watchdog。新增文件10GiB，无新模型下载。最新累计与活动进程见[project_state.json](project_state.json)，阶段切换不重置账本。

CPU进程显式CUDA_VISIBLE_DEVICES为空。保护原始数据、日志、配置和失败；上游代码固定。只访问授权本地模型/数据、指定服务器、公开学术材料和授权GitHub；不扫描网络、绕过验证、攻击生产服务、保存凭据或联系他人。

攻击端不得取得目标密钥、消息、原始噪声、RNG、内部反演或分数；当前共享机器接口不构成权限隔离。研究入口精简更新，原始证据保留。发布前更新清单并执行归档核验。

[当前计划](docs/RESEARCH_PLAN.md) / [导师Word](docs/advisor_briefing.docx) / [历史要求](prompts/README.md) / [原始证据导航](docs/ARTIFACT_GUIDE.md)。
