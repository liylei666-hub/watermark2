# 阶段 04：单样本潜变量留存与全局余弦诊断

本次新的独立单样本运行已完成。RUN_DIR：`/data0/liyanlei/watermark_research/runs/04_reprompt_latent_diag_seed1_20261013T025322Z`。
记录代码：`/data0/liyanlei/watermark_research/scripts/04_latent_diag_20261013T024856Z/run_recorded.py`，SHA256 `143107fa006698a9e0063ca1576764c830a7bc6d22d8d0c76c057b66a9e9f877`。
上游 commit：`ca68950cd7b53b8438a49580f134b2a0db28d778`，两个上游工作区保持干净。

## 运行与原水印检测

用户本轮授权物理 GPU 3；UUID `GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da`。启动前身份/占用复核通过，单卡可见，程序内 cuda:0。
正式模型进程仅启动一次，PID 44410，退出码 0，耗时 73.181185 秒。
每 2 秒采样 GPU 总显存占用，采样峰值 16632 MiB；不是连续监测的精确峰值。结束后该子进程已退出，GPU 3 回到 1 MiB、0% 利用率，未操作其他进程。
环境沿用已有 Python 3.10 独立环境；未安装/升级依赖或下载模型。

固定 GS、seed=1、512×512、目标/代理各50步、生成CFG=7.5、DDIM、float32、resample=false。
官方反演仍为空提示词、CFG=1.0；保留原 res_1 images_torch 到代理反演的数据流、VAE、scheduler、stash_pipe 顺序。
GS 参数：l=1、32字节消息、64次重复、offset=0。
参考提示词：A studio photograph of a yellow ceramic teapot on a wooden table.
攻击提示词：A red sailboat on a calm blue lake, watercolor illustration.

| 图像 | bit_accuracy | 原 GS 判定 |
|---|---:|---|
| 参考 | 1.0 | True |
| 攻击 | 0.953125 | True |

阈值保持 bit_accuracy > 0.70703125。参考水印检测通过；本次观察到一次原 GS 水印转移。
原始 CSV 在 `/data0/liyanlei/watermark_research/runs/04_reprompt_latent_diag_seed1_20261013T025322Z/evaluator_only/official_output/target_prompt_index=custom/attacker_prompt_index=custom/metrics.csv`，未修改。PSNR/SSIM/MS-SSIM/LPIPS 仍为官方未计算占位 -1，GS p_value=0 是占位。
bit_accuracy 不是总体攻击成功率。

实际加载路径通过旁路记录 Diffusers 0.31.0 的 DiffusionPipeline.download 返回值核对。其 from_pretrained 在 pipeline_utils.py:719–743 把此返回值作为 cached_folder 使用；包装保持参数和返回值原样。两个实际 snapshot 与冻结配置一致：
- stabilityai/stable-diffusion-xl-base-1.0：
  /data0/liyanlei/watermark_research/cache/huggingface/hub/models--stabilityai--stable-diffusion-xl-base-1.0/snapshots/462165984030d82259a11f4367a4eed129e94a7b
- Manojb/stable-diffusion-2-1-base：
  /data0/liyanlei/watermark_research/cache/huggingface/hub/models--Manojb--stable-diffusion-2-1-base/snapshots/0094d483a120f3f33dafbd187ea4aa60d10de75c

stderr 保留官方 safety_checker/scheduler 字段警告和离线 Hub 提示；最终从固定缓存正常加载。完整 stdout/stderr、退出码、commands.json、command.sh 与 config.json 均留存。

## 捕获位置与算法保持

官方来源：[run_reprompting.py:109–117](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L109-L117) 从 get_wm_latents 获得 wm_zT 并传入目标生成。包装检查这是同一个对象，再保存 CPU 副本。
参考验证 step=-1 位于 [run_reprompting.py:124–137](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L124-L137)，攻击验证 step=1 位于 [179–192](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/run_reprompting.py#L179-L192)。
两次恢复噪声均截取自 [utils/imprint_utils.py:338–343](https://github.com/and-mill/semantic-forgery/blob/ca68950cd7b53b8438a49580f134b2a0db28d778/utils/imprint_utils.py#L338-L343) 已有目标反演的返回字典。

本次调用计数：{"sampling": 1, "target_generate": 1, "proxy_generate": 1, "target_invert": 2, "proxy_invert": 1, "validate": 2}。
没有增加生成、反演或水印检测调用，也没有分数驱动的候选选择/重试。
捕获使用 detach().to(cpu,copy=True)，不修改、移动或替换原始张量；原 dtype 保持 float32。
source_provenance.json 保存源文件哈希、完整 commit 和空 upstream diff；instrumentation.diff 包含新增包装/运行/测试代码的完整差异。
冻结 config.json 的 SHA256 为 `2656f195b3d22a15115635767c12b0bade693d19518c606d35c3d9ff27a449fb`，运行前后代码哈希一致。

## 三个实际张量

均为非 pickle NPY、shape=[1,4,64,64]、float32，位于 RUN_DIR/evaluator_only。
保存后 CPU 重读核对 shape/dtype/逐元素数值一致；独立诊断再核对文件哈希与有限性。

| 张量 | SHA256 | 关联 step |
|---|---|---:|
| target_original_wm_zT | 5faf9fe454f30f87980dddaf163e649fd556f5f17570e7973cf1ed28dc654ebc | -1 |
| target_inverted_reference_zT | cc4a878185ebe7e186d554c6ef08e82d14115c40a45079d791d51b9cc20fec80 | -1 |
| target_inverted_forged_zT | 71cb73613dd3ef5ed562e62e8a4ad2af3ace2483c0adf58e7e948366c7dce30a | 1 |

清单 `/data0/liyanlei/watermark_research/runs/04_reprompt_latent_diag_seed1_20261013T025322Z/evaluator_only/tensor_manifest.json` 逐张量保存路径、形状、dtype、源码捕获位置、角色、reference_id/candidate_id、配置哈希和图像哈希。
验证前读取 PIL 像素副本，validate 返回后与其原流程保存的 PNG 解码像素逐元素比较，两个 step 均一致。
参考图 SHA256：`40fb928b1ca645455711d2ab3b538ea5704b18c4f892ba720610cc54d1ee8ac1`。
攻击图 SHA256：`3e824454a9c6c89c395e94a45fd727825120a7095f2a77de3ec41f91f29edb7d`。

本次两张图片与阶段 02 的文件哈希均相同：{'reference': True, 'forged': True}。
这是新运行的输出一致性记录，不表示恢复了阶段 02 历史张量，也不能代替完整记录等价实验。

## 独立 CPU 余弦诊断

实现名：independent_global_cosine_diagnostic。
依据：[arXiv:2606.29807v1 Definition 4.5 与 Remark 4.7](https://arxiv.org/html/2606.29807v1#S4.SS3.SSS2)。
公式 dot(z,zhat)/(norm(z)*norm(zhat))。输入同形状、batch=1；每样本展平全部 C/H/W；
不中心化、不逐通道平均、不重采样，仅在 CPU 计算时转 float64；零范数、非有限、形状错误均报错，不加 epsilon。
候选 PNG 已保存并写入 candidate_frozen.json 后，模型子进程退出，独立 CUDA_VISIBLE_DEVICES="" 进程才读取张量计算：

| 指标 | 实际数值 |
|---|---:|
| gcos_reference | 0.8201082797320761 |
| gcos_forged | 0.3506198907446562 |
| reference − forged | 0.4694883889874199 |

分数未参与攻击计算或选择。没有设置几何阈值，没有几何接受/拒绝结论，也未实现 L-SPD 或融合规则。

## 测试、完整性与限制

CPU mock 测试通过：调用次数保持、原返回对象保持、输入未改变、Python/NumPy/Torch CPU 随机状态未推进，张量往返及 PNG 绑定正确；
余弦测试覆盖同向=1、反向=-1、正交=0、正比例缩放不变以及零范数、NaN、Inf、形状/batch错误拒绝。
构造非有限测试输入时产生一条 NumPy RuntimeWarning，测试按预期拒绝该输入，退出码0；原始日志保留。
这些测试与源码审查不等于有记录/无记录的完整数值等价实验；未做该等价实验。
与作者缺失几何函数的逐项数值等价性尚未验证；本结果不是完整官方几何检测复现，不证明总体可分性、总体攻击成功率或几何防护绕过。

目标张量、原始 CSV、实际模型加载记录和评分均位于 evaluator_only；没有把它们加入攻击输入清单。
运行仍在官方单进程框架内，目录命名、文件哈希不能证明进程/权限隔离。
已有 54 个受保护文件哈希均未改变，两个上游工作区干净。
报告生成前新增文件合计 1209881 字节，报告完成后另作预算终检，要求低于 1 GiB。
当前剩余阻塞：无影响本轮规定诊断完成的阻塞；完整官方几何规则的缺失仍是下一阶段边界。

阶段 04 完成并停止；没有追加样本、优化攻击或外部消息。
