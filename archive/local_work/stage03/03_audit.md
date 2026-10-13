# 阶段 03：几何验证官方实现与攻击信息边界核查

核查日期：2026-10-13 UTC。项目：`/data0/liyanlei/watermark_research`。
审计目录：`/data0/liyanlei/watermark_research/reports/03_geometry_audit_20261013T020025Z`。

## 结论与证据等级

**实际检查过：**阶段 02 原始证据与报告一致；两张 PNG 完整且画面不同；两个上游工作区干净。已获取指定论文 v1 和完整 Git 对象，静态枚举公开文件、检查 import、比较源码哈希。
**根据源码判断：**公开几何实现不完整，缺少模型工厂和几何工具模块；现有接受/拒绝分支只使用原水印分数。现有图片可作为目标反演的图像输入，但不足以完成几何评估。
**尚未验证：**几何分数数值、部署阈值、完整参考潜变量恢复、跨模型版本等价性、误拒率/错误接受率及总体攻击成功率。本轮未加载模型、未使用 GPU、未运行生成、反演、检测或新实验。

## 1. 阶段 02 最小证据核对

实际 RUN_DIR：
`/data0/liyanlei/watermark_research/runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z`。

| 项目 | 状态 | 实际证据 |
|---|---|---|
| command.sh 与 config.json | 已核对一致 | 解析后的入口命令与 config.command 相同；固定 GS、seed=1、512、50/50 步、CFG 7.5/7.5、DDIM、resample=false |
| 退出记录与完成日志 | 已核对一致 | exit_code.txt=0；execution.json=0；stdout 有 phase 1–4 与最终 Harmful detection_success=True；没有仅凭图片存在判断成功 |
| 原始 CSV 与报告 | 已核对一致 | 两行：step=-1 与 step=1，见下表 |
| GS 阈值 | 已核对一致 | config/status 均记录 0.70703125，比较为严格 > |
| 历史 GPU | 已核对一致 | 阶段 02 使用物理 GPU 3，UUID GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da；本轮不用 GPU |
| PNG 存在、尺寸与 SHA256 | 已核对一致 | 均为可解码 RGB 512×512；哈希与原报告、image_checks.json 一致 |
| 两图可见内容与固定提示词 | 已核对一致 | 本轮实际查看经哈希核对的本地副本，描述如下 |

原始 CSV 路径：RUN_DIR 下 `target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv`。
表头原样为：
`[空列名],step,psnr,ssim,msssim,lpips,message_bits_str_initial,bit_accuracy,p_value,message_bits_str_recovered,detection_successful`。
首列是 pandas 行索引，不是额外实验编号。

| CSV 索引 | step/行含义 | bit_accuracy | detection_successful | 质量指标 | p_value |
|---|---|---:|---|---|---|
| 0 | -1，参考水印图 | 1.0 | True | 四项均 -1 | 0.0 |
| 1 | 1，Reprompting 攻击图 | 0.953125 | True | 四项均 -1 | 0.0 |

行含义由旧官方入口的参考验证 step=-1、攻击验证 step=1 及写 CSV 路径确认：[run_reprompting.py:124–146](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L124-L146)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）；[run_reprompting.py:179–205](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L179-L205)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。质量指标关闭，-1 是占位；GS 的 p_value 不表示几何检测结果。bit_accuracy 是单图消息位匹配比例，不是总体攻击成功率。

参考图 `attack_instance_step=-1.png`：
SHA256 `40fb928b1ca645455711d2ab3b538ea5704b18c4f892ba720610cc54d1ee8ac1`。
可见黄色有光泽的茶壶置于木板桌上，灰色背景，摄影风格；大致对应黄色陶瓷茶壶固定提示词。
攻击图 `attack_instance_step=1.png`：
SHA256 `3e824454a9c6c89c395e94a45fd727825120a7095f2a77de3ec41f91f29edb7d`。
可见蓝色水面上的红色大帆、船体和红白倒影，水彩插画风格；大致对应红帆船提示词。主体、构图和风格均不同，视觉上不是参考图复制。这是定性检查，不是语义一致性量化实验。
`original.png` 与参考图哈希相同。

完整取证清单、命令、配置、日志、图片信息在本目录 `stage02_evidence.json`。已有文件仅被读取；文件哈希终检记录在 `preservation_check.json`。

## 2. 论文与仓库来源

- 指定论文：[arXiv:2606.29807v1](https://arxiv.org/html/2606.29807v1)，2026-06-29 版本；本轮保存 HTML，SHA256 `8ed835b0eebdc1f9c31585de569790ae6663d0e20b395546580c28df3bc6443f`。
- 仓库：`https://github.com/chengyi-chris/geodistort-wm.git`。
- 远程落盘位置：`/data0/liyanlei/watermark_research/third_party/geodistort-wm`。
- 分支 main；完整 commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`；工作区干净；远程获取完成时间 2026-10-13T02:07:57Z，静态证据时间 2026-10-13T02:09:21.968165Z。
- 服务器直接 clone 遇 TLS 握手错误；本机从指定官方 GitHub 获取，补全历史后通过已认证 SSH 中转 Git bundle。两端 bundle SHA256 同为 `409f7537bfdd1993a10a006ae1dac0a5d5cfb54fc0ade47fb26d0d31cab919d2`，服务端 git fsck --full 通过。未关闭 TLS/SSH 主机校验。
- 初次浅历史 bundle 缺父提交导致 clone 失败，失败后目标目录不存在；使用新的完整 bundle 完成获取，保留失败中转证据。服务器 Git 不支持 branch --show-current，改用只读 symbolic-ref --short HEAD，确认 main。
- **许可证：未发现许可证正文文件。** README 第 13 行有 MIT 徽章链接，不能据此将缺失许可正文记为已核实 MIT 授权。README 的“即将发布”仅是状态文字：[Readme.md:11–21](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/Readme.md#L11-L21)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
- 实际有 4 个运行脚本、7 类水印 provider、模型 provider、两个 DDIM scheduler、图像/提示词工具、文本元数据及公开水印 key 文件。完整文件路径、大小和 SHA256 见 `source_evidence.json`。未下载模型权重、图片数据集，未递归取子模块或启动 LFS 下载；未反序列化仓库 pkl 文件。
- **缺失：**`utils/pipe/pipe_utils.py`、`utils/finger_utils.py`、`utils/spd_utils.py`。前两者被活动 import 引用；第三个出现在几何注释代码中。空的 utils/pipe/__init__.py 未提供替代工厂。静态 AST 与 tracked 文件清单双重检查，没有发现 cosine/SPD/AIRM 几何函数定义。证据引用：[run_reprompting.py:23–33](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L23-L33)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:192–205](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L192-L205)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。这不是因 README 文案推断没有实现，也不是一次运行报错的猜测。

## 3. 检测入口与数据流

| 入口 | 源码实际表达的数据流 | 完整性/产物 |
|---|---|---|
| run_watermark.py | 建立 WM provider，取得原始 wm_zT，目标生成，再目标反演、原 WM 验证 | 原始噪声在循环前建立并跨提示词复用；几何计算及张量保存注释；活动 CSV 保存原 WM 结果 |
| run_no_watermark.py | randn(1,4,64,64) → 目标生成 → 目标反演 | 活动保存 zT_latents/ret_latents 到固定 gs_zT_latents_pairs.pt，按列表次序配对；名称不表示 GS 水印，生成路径没有 WM provider |
| run_reprompting.py | 每轮 wm_zT → 目标参考图 → 代理反演 → 代理按另一提示词生成 → 目标验证/再次反演 | 几何调用及几何 CSV、张量保存均注释；活动判定用原 WM 分数；图片固定 reprompt_img.png |
| run_imprint_forgery.py | 代理梯度优化，周期性目标 WM 验证 | 是已有优化基线，不能当作 C.3 Reforge 的实现 |

正常样本证据：[run_watermark.py:119–168](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L119-L168)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:187–262](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L187-L262)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:267–347](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L267-L347)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
无水印证据：[run_no_watermark.py:93–134](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_no_watermark.py#L93-L134)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；缺工厂 import：[run_no_watermark.py:10–12](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_no_watermark.py#L10-L12)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
Reprompting 证据：[run_reprompting.py:192–220](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L192-L220)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:254–304](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L254-L304)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:389–458](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L389-L458)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
Imprint 证据：[run_imprint_forgery.py:215–282](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_imprint_forgery.py#L215-L282)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

活动 validate 只执行目标反演、wm_provider.get_accuracies、质量指标和保存，没有几何分数调用：[utils/imprint_utils.py:355–445](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/imprint_utils.py#L355-L445)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。GS 最终判断为 bit_accuracy > 0.70703125：[utils/utils.py:9–12](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L9-L12)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/utils.py:58–115](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L58-L115)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:410–425](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L410-L425)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。所以当前几何分数既没有进入接受/拒绝，也没有在活动路径中被计算后记录；看到的几何 CSV 是被注释的离线分析草稿。

目标分数在 Reprompting 路径中用于参考检查、最终报告/CSV，没有基于它的提前停止、候选择优或超参数更新；代理生成依赖代理反演张量与提示词。源内共享进程能访问目标内部，并不等于攻击算法输入已隔离：[run_reprompting.py:223–299](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L223-L299)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:410–458](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L410-L458)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。旧单样本同样如此：[run_reprompting.py:138–201](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L138-L201)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。注释里的 sys.exit、flag、几何阈值不是活动流程。

入口还有非审计副作用：get_text_prompts 默认可能通过 datasets 下载 SDP；初始化 scheduler 的 from_pretrained 可以联网；generate/invert 会加载模型并按 device 放置；WM provider 默认 device=cuda；set_random_seed 含 CUDA 调用；多个水印模块被一次性 import。故本轮没有 import 这些入口或 provider。证据：[utils/prompt_utils.py:52–83](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/prompt_utils.py#L52-L83)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:37–51](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L37-L51)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:376–393](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L376-L393)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/wm_provider.py:12–36](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/wm_provider.py#L12-L36)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/utils.py:120–129](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L120-L129)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/wm_utils.py:3–9](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/wm_utils.py#L3-L9)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

## 4. 几何指标：论文定义与公开实现的对应性

论文依据均为 [v1 §4.3.2–4.3.3、§5.1](https://arxiv.org/html/2606.29807v1#S4.SS3)。

| 项目 | 论文定义 | 代码能确认到什么程度 |
|---|---|---|
| G-Cos | Definition 4.5 / Remark 4.7：原始与恢复噪声向量的点积除以两者 L2 范数；SAD 为 arccos(cos) | 仅见注释 latent_cosine(wm_zT,zT_retrieved)，实现缺失 |
| 输入 | 原始目标水印噪声与目标对图像恢复的噪声 | SDXL/SD 路径预期 [1,4,64,64]，但指标 flatten 轴、batch 汇聚、dtype/epsilon 未知 |
| 分数方向 | G-Cos 高表示方向接近；SAD/L-SPD 高表示偏差大 | 不能据注释函数名证明符号、截断或归一化实现 |
| 局部协方差 | Def.4.8：C(z)=M⁻¹Σ(tᵢ−均值)(tᵢ−均值)ᵀ+εI，ε>0 | token 定义/轴顺序、实际 M、通道归一化、ε数值、特征值截断均 unknown |
| SPD 距离 | §4.3.3：‖log(P₁⁻¹ᐟ²P₂P₁⁻¹ᐟ²)‖F | missing spd_utils，不能核实求解器和正则细节 |
| 分块与聚合 | §5.1：规则 16×16 spatial grid，局部差异 top-5 mean | 无可运行实现可确认网格映射；注释另有 n_parts=4、grid_size=4/topk=3、grid_size=8，不能当作论文参数 |
| 多分数融合 | §4.3.4 Theorem 4.10 讨论联合拒绝区域；Table 2/4 分列两项 AUC | 未发现活动融合规则、固定阈值或一图最终几何判定接口 |

对应源码：[run_watermark.py:228–243](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L228-L243)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:304–394](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L304-L394)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。形状由 provider 的 4 通道、resolution/VAE scale 计算：[utils/pipe/pipe_provider.py:18–19](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L18-L19)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:425–444](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L425-L444)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。上述 [1,4,64,64] 是当前 SDXL/SD 512 配置下的源码推导，未在本轮加载模型测量。

## 5. 参考潜变量来源与关联

源码比较参数中的 wm_zT 是 get_wm_latents 返回并用于目标生成的**原始目标噪声**，不是代理噪声，也不是目标对参考图反演的噪声。Reprompting 在同一循环中持有原始 wm_zT、参考图、攻击图，攻击图的 zT_retrieved 来自目标模型再反演；这是实验内位置关联，未发现对任意外部待检图片检索参考的接口。[run_reprompting.py:203–217](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L203-L217)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:284–314](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L284-L314)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

正常样本脚本在循环前产生一次 wm_zT，多个提示词共用它，因此该脚本不是逐图唯一潜变量协议；Reprompting 每轮新建 provider、再抽连续噪声，但默认固定 offset 与相同密钥/消息表。[run_watermark.py:125–168](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L125-L168)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/gs_provider.py:39–46](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L39-L46)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/gs_provider.py:93–108](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L93-L108)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/gs_provider.py:145–186](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L145-L186)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

GS 固定消息、key、nonce 决定加密分区；每个分量还使用 NumPy uniform，经 norm.ppf 得到连续值。因此知道 key/消息不等于知道原始连续噪声。公开表是实验固定材料，不能作为真实秘密安全性的证据。[utils/wm/gs_provider.py:145–182](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L145-L182)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

正常/Reprompting 的 wm_latents/ret_latents 保存代码均被注释；只有无水印脚本活动保存配对张量，且没有图像哈希关联清单。[run_watermark.py:232–243](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L232-L243)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:319–328](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L319-L328)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_reprompting.py:429–438](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L429-L438)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_no_watermark.py:119–134](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_no_watermark.py#L119-L134)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。

论文 v1 §4.1 说不逐图存原始生成特征，§4.3.1 与 C.4/Fig.8 又需要参考 zT 与恢复 zhatT。公开材料未交代参考如何持久化/由状态重建、候选如何找回对应参考，也未给出无原始噪声的等价实现。**关联机制与零存储主张的实现对应性为 unknown**，属于证据缺口，不直接认定为漏洞。[v1 §4.1、§4.3.1、C.4](https://arxiv.org/html/2606.29807v1#A3.SS4)

## 6. 阈值与评估协议

论文 v1 §5.1 对原水印报告固定 FPR 下 TPR，对几何报告阈值无关 AUC。§4.3.4 的理论拒绝区域不是已给出的部署阈值；公开代码也无 ROC/校准划分/几何阈值发布脚本。正常样本误拒率和伪造样本错误接受率不能从 AUC 或这个单样本得到。[v1 §5.1、§4.3.4](https://arxiv.org/html/2606.29807v1#S5.SS1)

本审计使用的概念区分：几何误拒是“正常样本被几何拒绝”；几何错误接受是“伪造样本通过几何”；若最终必须通过水印和几何，则最终错误接受是二者均通过的伪造比例。这些是指标含义说明，不是公开实现已经采用的组合公式。论文 C.4 规定几何先于 WM，§6.4 称为预警；活动代码仍只有 WM 判定。最终几何/WM 布尔关系、分数融合、校准集与测试集划分、ROC 正标签和实际部署阈值均 **unknown**。

注释中的 0.125、0.37、1.3 等没有活动路径或阈值来源，不能取消注释后称为作者发布协议：[run_reprompting.py:352–368](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L352-L368)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[run_watermark.py:239–259](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_watermark.py#L239-L259)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。保留阶段 02 GS >0.70703125，但它只属于原 WM，不替代几何阈值：[utils/utils.py:9–12](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L9-L12)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/utils.py:102–103](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/utils.py#L102-L103)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。另有语义差异：该阈值源码注释注明 100k 用户的 multi-bit 设定，论文 v1 A.1 GS 段排除 attribution；本轮不改数值，也不据此声称复现了归属/FPR。

## 7. 与阶段 02 的兼容性

| 项目 | 阶段 02 真实配置 | 几何公开材料 | 判定 |
|---|---|---|---|
| 目标模型 | stabilityai/stable-diffusion-xl-base-1.0 @462165984030d82259a11f4367a4eed129e94a7b | 同 ID，未固定 revision | ID 可复用；需显式固定现有 snapshot；论文权重逐字节等价 unknown |
| 代理模型 | Manojb/stable-diffusion-2-1-base @0094d483a120f3f33dafbd187ea4aa60d10de75c | stabilityai/stable-diffusion-2-1-base，revision 未给 | 需要明确适配；换模型会改变攻击条件；现有候选评估不需重新调用代理 |
| 分辨率/形状 | RGB 512×512；预期噪声 1×4×64×64 | SDXL/SD 默认一致 | 图像格式可以直接复用 |
| VAE 编码 | [0,1] 转 [-1,1]，posterior.mean×scaling_factor | 基类表达式一致 | 公式可复用；保持目标 snapshot 与 VAE 配置，运行数值未验证 |
| VAE 解码/量化 | Diffusers SDXL/SD pipeline 返回 PIL，再 VAE 编码供反演 | 同 pipeline 类，增加可选 callback | 需保持版本和 PIL/RGB 数据流；不能把原始无量化 latent 当作 PNG 输入的等价物 |
| scheduler | 自定义 DDIM + DDIM inverse | 两个 scheduler 文件哈希与旧仓库相同 | 源码可以复用；缺工厂，代理 scheduler 参数未传入工厂调用，完整连线尚不能确认 |
| 生成/反演步数 | 目标50、代理50；同参数用于反演 | 默认50 | 可复用 |
| guidance | 生成7.5；反演空 prompt、1.0 | 基类相同 | 可复用 |
| 精度 | float32 | SD/SDXL 基类 float32 | 可复用；改半精度会改变比较条件 |
| GS 参数 | l=1，message_width_in_bytes=32，num_replications=64，offset=0、batch=1（入口未覆盖默认） | GS provider 与 wm_provider 及消息/key/nonce 表逐字节相同 | 默认参数/固定表可复用；不等于原始连续噪声已保存 |
| 提示词 | 固定茶壶→红帆船 | 入口忽略显式提示词参数，从 SDP 前/后取样 | 需要明确适配输入；替换现有图片/提示词改变实验；单样本不等同论文分布评估 |
| 阈值 | GS 严格 >0.70703125 | 原 WM 相同；几何 unknown | GS 可保留；几何不可代填 |
| 环境 | 记录 torch2.5.1、diffusers0.31.0、transformers4.46.3、accelerate1.1.1、numpy2.2.6 | requirements 要 accelerate1.9.0、numpy1.26.0，且全量 import 含其他 WM 依赖 | 不能称整仓库即装即用；本轮未安装或修改环境 |

模型参数/提示词证据：[run_reprompting.py:80–153](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_reprompting.py#L80-L153)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；旧代理映射：[utils/pipe/pipe_utils.py:15–39](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/pipe/pipe_utils.py#L15-L39)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。
VAE/精度：[utils/pipe/pipe_provider.py:18–19](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L18-L19)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:139–188](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L139-L188)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:239–261](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L239-L261)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/pipe/pipe_provider.py:279–315](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/pipe_provider.py#L279-L315)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/image_utils.py:414–435](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/image_utils.py#L414-L435)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
基类 diff 仅 callback 透传及格式差异；SDXL 类额外包含 Anime provider，不据此推断 SDXL 主类改变。文件哈希对照见 source_evidence.json；SDXL 主类：[utils/pipe/SDXL_provider.py:1–18](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/pipe/SDXL_provider.py#L1-L18)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
GS 默认与采样：[utils/wm/gs_provider.py:28–46](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L28-L46)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）；[utils/wm/gs_provider.py:135–186](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/utils/wm/gs_provider.py#L135-L186)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。依赖：[requirements.txt:1–36](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/requirements.txt#L1-L36)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`）。
论文模型 ID、生成设置与提示词协议依据 [v1 D.1/Table 6、D.2](https://arxiv.org/html/2606.29807v1#A4.SS1)。

## 8. 已有自适应评估范围

| 层级 | 核查结果 |
|---|---|
| 作者讨论过 | v1 C.3 明确讨论 Reforge：净化后以代理重印；§6.4 讨论更强、相同目标/代理设置 |
| 提供公开算法/代码 | C.3 有两阶段概念描述；未给可复现净化强度、损失、停止规则或 Reforge 入口。本 commit 的 4 个入口及源码检索未发现 Reforge 策略实现 |
| 真正进入实验比较 | §5.1/Table 1–4 是 Reprompting/优化攻击；§6.4/Table 2 有相同模型设置。C.3 明确说 Reforge 未纳入比较 |
| 证据不足 | Reforge 在当前 GS→几何场景的数值表现、预算与自适应绕过率；本轮没有相关实验数据 |

论文依据：[v1 C.3、§6.4、§5.1](https://arxiv.org/html/2606.29807v1#A3.SS3)。源码边界：已有优化器及周期验证 [run_imprint_forgery.py:215–282](https://github.com/chengyi-chris/geodistort-wm/blob/72880c9bb1cee0b04bcb2433deb2ab2cc95ff622/run_imprint_forgery.py#L215-L282)（commit `72880c9bb1cee0b04bcb2433deb2ab2cc95ff622`），不能将其等同 Reforge。作者对 Reforge 成本/画质/几何损伤的论述是讨论，不能升级成公开实验验证；也不能写作者完全没有考虑自适应攻击。

## 9. 现有单样本能否复用

**图片可以复用为图像输入，当前材料不足以忠实输出几何判定。**

| 所需材料 | RUN_DIR 实际情况 | 恢复或新计算条件 |
|---|---|---|
| 参考图、候选图与哈希 | 已保存并核对 | 原 PNG 可直接作为未来目标 VAE/反演输入；几何函数并非直接吃 PNG |
| 准确模型/revision、提示词、步数、CFG、精度、种子 | 配置、snapshot 记录、pip_freeze 已保存 | 可用于固定已有条件；不推定对应论文未公布 revision |
| GS 参数与消息 | 默认参数可由 commit 推导；CSV 有初始/恢复消息 | 密钥/nonce 表保留于上游，默认 offset=0；不用在报告或攻击交付物中复制其值 |
| 原始目标 wm_zT | 未保存；无张量文件或原张量哈希 | 有 seed 和固定采样源码，提供条件性重建线索；尚未证明可准确恢复 |
| 目标对参考/候选的反演噪声 | 未保存；CSV 只留分数 | 未来需目标 VAE 编码和各50步目标反演；本轮没有运行 |
| 完整 RNG 状态/连续采样 u/轨迹 | 未保存 | 同 seed 不足以证明完整生成状态恢复；需核对 RNG 消耗顺序、库版本和精度，取得可验证的原始参考 |
| 图像→原始潜变量映射 | 仅该 run 的逻辑对应关系 | 缺持久化 latent+hash 的可校验绑定 |
| 官方几何函数、数值参数、阈值协议 | 不在 RUN_DIR；新仓库也不完整 | 需作者完整材料，不能自行补函数/阈值 |

旧源码明确只把 wm_zT 放在进程内用于生成，验证返回分数后写 CSV 和 PNG：[run_reprompting.py:97–121](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L97-L121)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）；[utils/imprint_utils.py:338–347](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/imprint_utils.py#L338-L347)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）；[utils/imprint_utils.py:387–409](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/imprint_utils.py#L387-L409)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。
NumPy seed=seed+3，即当前 seed=1 对应种子4；GS 连续噪声还取决于之后的随机调用顺序。只有 seed 与固定 key/消息，不等于保留完整随机状态或证明原始张量可逐位重建：[utils/utils.py:63–72](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/utils.py#L63-L72)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）；[utils/wm/gs_provider.py:145–186](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/wm/gs_provider.py#L145-L186)（commit `ca68950cd7b53b8438a49580f134b2a0db28d778`）。本轮没有生成噪声来测试恢复。

若后续获得完整作者协议，完成一次评估仍需：取得正确且可验证的目标参考 wm_zT，针对两张原 PNG 进行目标反演，然后用冻结的作者几何函数与判定协议计算结果。新噪声、代理噪声、参考图反演噪声不能自动充当原始 wm_zT；缺项无法恢复时应保持“当前历史样本未能忠实评估”，不能悄悄生成另一个样本冒充本次记录。

## 10. 信息边界、阻塞与唯一下一步

具体输入、保密数据、哈希交付和评估后信息流见 `information_boundary.md`。这是接口设计，当前单进程官方程序尚未提供进程/权限安全隔离。

阻塞：完整几何实现/模型工厂缺失；参考噪声持久化或重建与关联机制未明确；现有 run 没有原始/恢复潜变量和 RNG 状态；几何阈值及融合/校准协议未公开；论文与阶段02代理 ID/revision 不完全对应。

**唯一下一步：取得并冻结作者与 v1 对应的完整单样本评估材料包，要求同时明确 G-Cos/L-SPD 实现、参考潜变量取得与关联方式，以及固定判定协议；据此决定历史样本能否忠实评估。** 在这些材料明确之前不补写替代验证器、不调整阈值。本阶段到此停止。

