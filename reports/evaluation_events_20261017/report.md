# 单输出评估事件：真实存档接入与统计完整性

日期：2026-10-17（Asia/Shanghai）。本次完成可运行的评估端结果记账工具，并接入阶段07的全部六个计划任务。没有新生成、反演、检测或模型加载；本报告不是新的攻击性能实验。

## 实际完成

`scripts/summarize_evaluation_events.py` 消费评估端已取得的标签，核对交付文件SHA256、计划任务、组别与标签类型，计算单输出指标。`scripts/audit_existing_evaluation_events.py` 从原始protocol、execution、metrics.csv与PNG建立追溯关系；核对CSV两行语义、严格GS阈值、参考图哈希，以及验证前候选和已评估PNG逐字节相同。没有读取潜变量NPY、密钥或消息。

本工具强制区分：参考有效、产物完成、内容达成、属于伪造范围、原水印通过、完整防御接受。完整协议缺失时，完整成功率及其范围为null；不会把原GS检测值搬过去填空。失败/未启动任务须保留记录，不因缺少候选而从计划表消失。多候选any-of-k不由这个单输出汇总器处理。

## 真实存档的输出

| 组别 | 计划/完成 | 原GS有效参考 | 候选原GS通过 | 完整事件未知 | 完整防御成功率 |
|---|---:|---:|---:|---:|---|
| 更换提示词 | 3/3 | 3 | 3 | 3 | null |
| 相同提示词诊断 | 3/3 | 3 | 3 | 3 | null |

`joint_success_known_true=0` 表示没有证实完整成功的标签；不是已测得0%成功率。两组各3个未知也不表示攻击失败。组间复用三个参考，不能称为六个独立参考。same_prompt保持诊断组身份，不并入改变内容的伪造结果。

既有视觉描述没有冻结的内容判定量表，因此content_met和forgery_in_scope保持null。本次没有把旧描述转换成确定标签，也没有事后改变内容要求来提高通过率。当前reference_valid仅代表原GS有效；它不证明普通GS图是几何/SemBind/SLICE的合格正样本。

## 检验及边界

12项CPU测试通过，覆盖哈希篡改、路径越界、缺失任务缩小分母、重复候选、未知标签、内容失败、完整协议缺失、流程失败计数、未知参考、字符串/整数冒充布尔值和未识别字段。测试使用明确标记的合成字节，不作为真实图片或实验数据。真实六任务另外从存档构建并复算。

工具只核对输入一致性和统计语义，不判断图片内容，不验证外部检测器的正确性，不实现几何/SemBind验证器。`full_defense_protocol_complete`是调用者的有出处声明，不能由一个true自动证明；输出明确标记`label_semantics_verified_by_tool=false`。它是评估端记账接口，不是攻击/评估的操作系统权限隔离；严格字段集合也不能证明任意字符串中没有秘密信息。候选先固定哈希的时间顺序来自阶段07原始记录，这个新账本是事后建立的。

将工具输出用于论文前，还需冻结具体内容量表、身份归属规则及完整验证协议，明确独立确认集和人/模型评审来源。当前只处理内容伪造事件；用户身份归属需要另行记录目标身份一致性，不能由WM布尔值代替。

## 官方材料复查

本次GitHub主分支、分支列表与release列表只读检查：几何仍为`72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`，SemBind仍为`337c9f90a150157ac1d410208ae20e6530ca8cdd`；两者仅返回main，无release条目。因此此前固定版本的实现缺项仍在，没有可直接追加运行的完整官方验证器。

[SLICE作者页面](https://xiaoyulics.com/papers/slice-image-watermarking/)现列为BMVC 2026 Oral；这是作者页面信息，尚未用会议录独立核对。[arXiv版本页](https://arxiv.org/abs/2603.12749)仍只列v1。本次核查该作者页没有Code入口，固定CSI库的`csi/schemes/__init__.py:15–23`也只注册TR、GS、SEAL，不能把CSI插件当成SLICE实现。没有作“所有地方均无代码”的穷尽断言。

## 资源与研究决定

已用服务器专用SSH认证读取当前进程：本用户没有模型进程。2026-10-17 05:20:30 UTC从07–09共11份原始execution重新核算，累计757.62238442339 GPU进程秒，剩余6442.37761557661秒；预算未重置。GPU2在当次观察为空闲，但本次未启动GPU程序。阶段09继续保留未完成状态，不补样。

当前科学瓶颈仍是一个完整、可执行且符合信息边界的防伪造评估对象，而不是缺少更多原GS通过样本。新增工具解决结果汇总的工程前提，不作为方法创新。下一步应完成该评估对象的材料闭合或明确可复现的公开实现范围，再冻结与现有基线有实质区别的新方法试验。

## 复算

在仓库根目录设置`CUDA_VISIBLE_DEVICES=""`，运行：

```text
python -m unittest discover -s scripts -p test_evaluation_events.py -v
python scripts/audit_existing_evaluation_events.py --verify reports/evaluation_events_20261017
```

生成另一份核对产物时使用`--output <尚不存在的目录>`。入口拒绝覆盖已有输出。输入和来源分别见[input.json](input.json)、[provenance.json](provenance.json)，结果见[summary.json](summary.json)。
