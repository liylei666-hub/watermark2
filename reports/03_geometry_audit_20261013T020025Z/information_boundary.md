# 攻击端与目标评估端的信息边界

适用项目：`/data0/liyanlei/watermark_research`。
设置：攻击算法获得一张参考水印图、指定输出提示词和代理模型，在固定预算下产生预先固定的候选；目标检测结果不参与候选筛选或参数调整。
本文是后续接口与信息流设计；**尚未实现或验证安全隔离**。

## 1. 输入、权限与持有者

| 信息/能力 | 攻击算法 | 目标评估端 | 实验控制端 |
|---|---|---|---|
| 参考 PNG 及其公开样本 ID/图像 SHA256 | 可读 | 可读 | 登记 |
| 指定攻击输出提示词 | 可读 | 可用于报告解释 | 预先固定 |
| 代理模型 ID、revision、权重与代理调用 | 可用 | 可记录版本 | 管理代理环境 |
| 攻击自身 seed、固定预算/参数 | 可用 | 留档 | 在评估前固定 |
| 目标模型公开身份 | 可作为明确公布的元信息 | 知道准确身份 | 记录身份公开范围 |
| 目标模型内部 pipeline、VAE/反演调用权限 | 不提供 | 独有 | 仅为部署与审计持有 |
| 目标原始提示词 | 不提供 | 按协议持有 | 本地固定样例的控制变量 |
| 目标 WM key、nonce、原始消息或表索引 | 不提供 | 独有 | 仅管理/审计 |
| 原始目标生成噪声 wm_zT | 不提供 | 几何协议若需要则独有 | 保存与图像绑定及哈希 |
| 目标生成 seed、完整 RNG 状态、连续采样值 | 不提供 | 仅在明确恢复协议中使用 | 保存版本/状态，不能转入攻击配置 |
| 目标对参考/候选的内部反演噪声 | 不提供 | 独有 | 仅受控审计 |
| 原 WM 分数、几何分数、阈值结果、评估日志 | 固定输出前后均不回馈算法做本轮选择 | 计算并保存 | 可在冻结后做科研报告 |
| 校准/测试标签、参考检索库 | 不提供 | 按既定作者协议持有 | 冻结评估协议与划分 |
| 候选图及其 hash | 先生成并交付 | 再校验、读取 | 保存提交时间和状态 |

“公开模型身份”和“目标内部调用权”必须分别授权。知道 SDXL 的公开名称不代表攻击算法能调用本地目标 VAE、获取目标内部噪声或读取检测分数。即使目标权重公开可下载，本项目此设置也不因公开身份而自动允许把它作为额外攻击 oracle；若以后改变攻击能力，应另立设置并明确记录。

论文 v1 §4.1 假定攻击者不知道目标架构/参数及合法生成提示词；§3.2 又提及黑盒查询。我们的优先设置明确固定为参考图+输出提示词+代理，目标分数查询预算为零。若另行公开目标身份，属于需要标注的信息条件，不能声称与论文所有未知模型条件完全相同。[论文 v1 §3.2、§4.1](https://arxiv.org/html/2606.29807v1#S4.SS1)

## 2. 现有官方程序的信息流证据

阶段 02 旧官方 commit `ca68950cd7b53b8438a49580f134b2a0db28d778`：
[run_reprompting.py:97–146](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L97-L146) 在同一进程构造目标 WM、生成参考图并验证；
[run_reprompting.py:148–171](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L148-L171) 的未 resample 分支只把代理反演结果用于代理生成；
[run_reprompting.py:173–205](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L173-L205) 再做目标验证和日志/CSV。源码未用目标分数进行候选选择、提前停止或超参数调整，但单一进程确实持有所有目标敏感信息。

新几何 commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`：
[run_reprompting.py:203–220](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L203-L220) 持有 wm_zT；
[run_reprompting.py:254–302](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L254-L302) 同一作用域内包含代理操作、目标验证及目标内部反演；
[run_reprompting.py:389–425](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L389-L425) 的几何块注释、活动 WM 结果记录。它没有已经可供复用的权限隔离接口。

GS 实验使用公开固定 key/message/nonce 列表：
[utils/wm/gs_provider.py:93–108](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/wm/gs_provider.py#L93-L108)，完整 commit `ca68950cd7b53b8438a49580f134b2a0db28d778`。
这些表的公开性与算法“不使用它们”是两回事，不能把公开实验常量描述为已保密。以后若要求密钥不可知，需评估端专属材料与实际访问控制；不能仅拆成两个文件或靠约定证明攻击者拿不到它们。

## 3. 本地实验控制持有但不能传入攻击算法的材料

当前 RUN_DIR 的 config.json 包含目标生成 seed 和提示词；metrics.csv 包含初始消息位串、恢复消息位串和目标检测分数；日志及模型 snapshot 记录包含目标配置。完整 RUN_DIR 不能直接作为攻击进程的输入目录。

后续攻击输入应采用白名单：参考 PNG、reference_id、指定输出提示词、代理配置、攻击自身随机状态及固定预算。白名单不能嵌入目标消息/密钥、原始噪声、目标 seed、目标反演结果或检测分数，也不能给出通往这些文件的路径。攻击端自己的代理潜变量可以保留，但名称/类型应标明 proxy，评估端不能将其当作目标参考。

本地当前研究者已经能读这些历史数据，本文不声称消除了既往知识，也不保证源代码公开常量能保密。对于“算法无目标反馈”的结论，只能在明确代码路径与数据访问证据支持的范围内作出。

## 4. 候选交付与评估顺序

1. 实验控制端提前固定参考图哈希、输出提示词、代理模型版本、攻击配置与预算、输出数量和成功/失败记录规则。单样本交付一张候选；失败也保留状态，不按目标结果补抽。
2. 攻击端输出候选文件及 manifest：candidate_id、reference_id、reference_sha256、candidate_sha256、字节数、图像尺寸、攻击代码 commit、代理 revision、攻击 seed、配置哈希、退出码与时间。manifest 不含目标内部信息。
3. 攻击端关闭写入并提交；控制端冻结清单和图像内容。哈希证明所评估字节与承诺字节相同，本身不证明没有其他泄漏。
4. 评估端再读取被冻结候选，重新计算 SHA256；不匹配则记录交付失败。用评估端私有映射取得正确目标参考，运行冻结的作者验证器和原 WM 检测，另存 evaluator-only 记录。
5. 控制端报告结果，但本轮攻击算法不据此改图、选候选、调参数或重试。后续任何利用结果的研究都需要另定攻击设置，不将其混入本轮样本。

## 5. 未来隔离验证的范围

未来真正实施时，需要分别约束账号/容器挂载、文件读写权限、目标服务访问、网络访问和日志通道，并审计实际访问。CUDA_VISIBLE_DEVICES 只限制设备可见性，不能替代信息隔离；两个 Python 文件也不能替代权限边界。
本阶段只读代码并写接口设计，没有部署上述权限或运行攻击/评估流程。

## 6. 几何机制特有的未决依赖

论文 v1 §4.3.1、C.4/Fig.8 需要参考目标 zT，§4.1 又强调不逐图存原始特征。公开代码以同进程 wm_zT 作参考，没有发布外部候选到参考的检索/重建协议。
[论文 v1 C.4](https://arxiv.org/html/2606.29807v1#A3.SS4)；
[run_reprompting.py:203–217、301–314](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L203-L217)，完整 commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`。

因此不能把参考图库、原始噪声或目标随机状态悄悄加入攻击输入来“补齐验证”；这些只能是评估端的明确依赖。不能把 missing reference 标成验证拒绝或攻击失败，也不能拿随机噪声替代。当前状态应为“评估所需证据缺失/unknown”，与模型真实判定分开。

