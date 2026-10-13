# 上游来源、版本与材料边界

上游采用 Git submodule 固定到已审计版本；浏览 GitHub 目录会转到对应上游。普通 clone 不会自动初始化子模块，也不会下载模型。

| 来源 | 固定 commit | 许可核查 |
|---|---|---|
| [semantic-forgery](https://github.com/and-mill/semantic-forgery/tree/ca68950cd7b53b8438a49580f134b2a0db28d778) | ca68950cd7b53b8438a49580f134b2a0db28d778 | 上游有 MIT LICENSE 正文 |
| [geodistort-wm](https://github.com/chengyi-chris/geodistort-wm/tree/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622) | 72880c9bb1cee0b04bcb2433deb2ab2cc95ff622 | 未发现许可正文；README 徽章不能代替核实 |

研究起点：Black-Box Forgery Attacks on Semantic Watermarks for Diffusion Models，CVPR 2025。几何审计指定版本：[Rethinking Forgery Attacks on Semantic Watermarks in Black-Box Settings: A Geometric Distortion Perspective，arXiv:2606.29807v1](https://arxiv.org/html/2606.29807v1)。论文核查的章节、公式和源码行号见阶段 03 报告。

完整论文 HTML、两份上游 Git bundle 未在这里重分发；其原始 SHA256 和排除原因保留在 provenance/source_manifest.json。代码来源通过固定上游 commit 获取。模型权重、环境和缓存留在授权服务器；模型 ID、revision、文件大小/哈希清单、安装包版本在阶段 02 记录中。

本仓库没有为第三方代码、论文或权重重新赋予许可证。项目自有材料的统一开放许可尚未指定。
