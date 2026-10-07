# 资产审查与恢复

起点提交：`1eeea4c95e555bfabc242b90aad35ca813557443`。原 remote 与指定仓库一致；原工作树仅有未跟踪 `pelican-bike.html`，无已跟踪文件修改。原工作副本及其忽略文件保持原样。独立整理副本使用 `git clone --no-hardlinks`，避免共享对象硬链接。

## 保留与移出活动目录

| 旧资产 → 新位置 | 审查结论及用途 |
|---|---|
| stage02、stage03 → legacy/stage02、legacy/stage03 | 校准、有限性检查、族划分、缓存哈希、组级 bootstrap 可复用。特征模型为强参考基线；旧局部汇聚不具备已证实优势。GPU 绑定及服务器硬编码保留为历史实现，不用于新的默认入口。 |
| tests、scripts → legacy/tests、legacy/scripts | 旧 CPU 测试与审计可重用；下载、生成、服务器模型传输和训练环境操作退出活动入口。运行时工作目录为 legacy。 |
| data、configs、artifacts → legacy/ 对应目录 | 提示词、许可来源、版本与哈希清单是追溯资产。部分文件引用服务器上的大文件；清单存在不等于本机数据完整。 |
| outputs、research → legacy/ 对应目录 | 旧分数、阈值、诊断和失败记录完整归档，保留否定证据。GPU 日志和历史报告不代表本轮执行。 |
| README → legacy/README.md | 历史用法原样留存；活动 README 指向新课题问题、文献、计划和检查。旧 README 内一些相对链接原本已包含重复 research 前缀，使用对应 legacy/research 文件或恢复旧提交查看。 |

无旧 tracked 资产被永久删除。`scripts/check_repository.py` 将每个归档文件的 Git blob 与起点逐一比较。活动脚本仅做离线检查与旧分数重算。原有权重、第三方源码、原图、缓存、bundle 与未跟踪 HTML 不进入新提交。

## 恢复点

- GitHub 分支 [`backup/pre-restart-20261007`](https://github.com/liylei666-hub/watermark2/tree/backup/pre-restart-20261007) 指向起点提交，正常推送建立，未改写历史。
- 本地工作目录的相邻 `recovery/watermark2-before-restart.bundle` 包含旧仓库全部七个引用和完整历史，`git bundle verify` 通过。SHA-256：`5e535d5788e8736edd792a8356ea95d77078951471505a85e4bff0bf6978baf7`。
- `recovery/pelican-bike.html` 是未跟踪文件副本，SHA-256：`0a2b83a17ed3eb74c8f5a4846569fc485cf2002afa66cefa82973ead909b0fcd`；原文件仍在原工作区。忽略的大资产留在原工作区，没有声称已额外复制全部大资产。

恢复旧 tracked 工作树可在新目录执行 `git clone --branch backup/pre-restart-20261007 git@github.com:liylei666-hub/watermark2.git old-watermark2`；离线可 `git clone recovery/watermark2-before-restart.bundle old-watermark2`。使用新目录避免覆盖现有修改。恢复大资产按原工作区/服务器清单取回；bundle 不包含忽略文件。

## 本轮仓库边界

仓库可见性核实为 PRIVATE，未改权限；GitHub Actions workflow 数为 0，活动树未添加自动部署流程。推送前再次读取 main；若远端前进，则保留独立研究分支并报告，不覆盖别人提交。
