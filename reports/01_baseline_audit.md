# 阶段 01：官方基线代码审计

审计对象为 `/data0/liyanlei/watermark_research/third_party/semantic-forgery`，官方远程地址 `https://github.com/and-mill/semantic-forgery.git`，分支 `main`，完整 commit `ca68950cd7b53b8438a49580f134b2a0db28d778`，工作区 clean。许可证文件为 GPL-3.0 摘要（`LICENSE:1-20`）。本轮只读源码和 README，没有运行入口或安装脚本。

## 入口、模型和设备

- Reprompting 入口与参数在 `run_reprompting.py:32-66`；四段流程是目标模型生成 benign 图（`103-118`）、攻击模型反演（`151-152`）、攻击 prompt 重生成（`165-171`）、目标模型重新反演检测（`176-201`）。默认结果写入 `out/reprompt/` 并保存 `metrics.csv`（`68-71,203-205`）。
- Imprint-Forgery 入口为 `run_imprint_forgery.py:36-70`，默认 cover `images/stalin.jpg`，可选 mask；Imprint-Removal 入口为 `run_imprint_removal.py:35-68`。Forgery 的优化循环为固定 `range(args.steps)`，默认 151 步，每 10 步验证并写 CSV（`run_imprint_forgery.py:183-249`）。
- 代理模型准确 ID 是 `Manojb/stable-diffusion-2-1-base`（三脚本的 attacker 参数：`run_reprompting.py:52-56`、`run_imprint_forgery.py:55-59`）；默认目标是 `stabilityai/stable-diffusion-xl-base-1.0`，可选 `PixArt-alpha/PixArt-Sigma-XL-2-512-MS` 或 `black-forest-labs/FLUX.1-dev`（`run_reprompting.py:43-50`、`utils/pipe/pipe_utils.py:15-28`）。
- 入口使用未索引的 `cuda`（`run_reprompting.py:28-30`、`run_imprint_forgery.py:33`），没有设置 `CUDA_VISIBLE_DEVICES`。后续必须外部按 GPU UUID 限制；单卡暴露后代码内才应使用 `cuda:0`。
- provider 先由 model ID 选择，再 `from_pretrained(..., torch_dtype=self.get_dtype())` 和 `.to(self.device)`（`utils/pipe/pipe_utils.py:31-73`、`utils/pipe/pipe_provider.py:18,63-116,352-400`）。通用 dtype 是 `torch.float32`（`pipe_provider.py:18`）。Imprint attacker 的 scheduler、SD pipeline 也明确使用 float32 并 `.to(device)`（`utils/imprint_utils.py:24-51`）。
- Imprint 冻结 attacker UNet 参数并用 `torch.utils.checkpoint.checkpoint` 做梯度检查点（`utils/imprint_utils.py:54-68,70-83,157`）；优化变量 `z0` 用 Adam 更新（`run_imprint_forgery.py:118-121,183-197`）。未发现 DDP 或多卡切分。

## Tree-Ring 与 Gaussian Shading

- GS 默认 `message_width_in_bytes=32`、`num_replications=64`、`l=1`（`utils/wm/gs_provider.py:26-31`）。消息、ChaCha20 key、nonce 从固定列表导入（`gs_provider.py:93-101`）；消息复制、ChaCha20 加密、`np.random.uniform`/`norm.ppf` latent 生成在 `gs_provider.py:135-183`。检测从 latent 恢复 barcode，多数投票并计算 bit accuracy（`gs_provider.py:205-296,325-357`）。固定 GS 阈值为 `0.70703125`，判定为 `bit_accuracy > threshold`（`utils/utils.py:9-12,36-37,45-60`）。
- TR 默认 `w_seed=999999`、channel 3、ring/circle/radius 10、complex injection（`utils/wm/tr_provider.py:25-33`）。由 seed 构造 FFT ring pattern 和 mask（`tr_provider.py:63-80,122-195`），在 FFT mask 区域注入并逆变换取实部（`198-226`）。检测用 mask 区域与目标 patch 的 non-central chi-square p-value（`321-366`），判定为 `p_value < threshold`；SDXL/PixArt/FLUX 阈值为 `0.0261008646426459`、`0.015917123872865434`、`0.02185009852518841`（`utils/utils.py:14-22,45-60`）。源码称这些阈值来自经验 FPR 测量，本阶段未复测。

## 是否读取目标检测结果

`validate()` 先用目标模型反演，再调用 watermark provider 得到 bit accuracy/p-value（`utils/imprint_utils.py:336-350`）。三类入口把检测结果写入 `results`、打印日志并保存 CSV（Reprompting：`run_reprompting.py:138-146,193-205`；Forgery：`run_imprint_forgery.py:228-249`）。Imprint 循环固定步数，没有成功后的 `break`（`run_imprint_forgery.py:183-206`；Removal 对应 `171-203`）。优化 loss 是 inverted latent 与 retrieved latent 的 MSE（`run_imprint_forgery.py:186-197`），没有用 detector 值做候选选择或超参数调整。Reprompting 的 `--resample` 只是 GS latent 重采样（`run_reprompting.py:157-163`）；单次入口没有按检测结果选择多个候选。

## 随机性、数据和隐式资源访问

- `--seed` 默认 1；`set_random_seed()` 设置 PyTorch、CUDA、NumPy、Python random，使用 seed+0/+1/+2/+3/+4/+5（`run_reprompting.py:63-64`、`utils/utils.py:63-72`）。TR 初始化又按 `w_seed` 设置一次（`tr_provider.py:63-66`），GS 采样使用 NumPy 随机数（`gs_provider.py:170-183`）。
- prompt 列表位于 `utils/prompt_utils.py`，README 说明来源为 SD-Prompts/I2P（`README.md:64-68`）；cover 图来自仓库 `images/`，默认 `images/stalin.jpg`（`run_imprint_forgery.py:39-42,89-90`）。
- `from_pretrained` 会读取缓存或访问 Hugging Face Hub（`utils/imprint_utils.py:35-48`、`utils/pipe/pipe_provider.py:63-116,362-400`）。入口在解析参数后就创建 pipeline（Reprompting `run_reprompting.py:79-94`；Forgery `run_imprint_forgery.py:75-116`），直接运行可能下载权重并启动 GPU。Forgery 顶层初始化 LPIPS（`run_imprint_forgery.py:75-76`），其权重也可能需要缓存或下载。仅导入 prompt 列表没有发现自动下载完整数据集。

## README PSNR Correction 核查

README 只指出旧 commit `43eec7e` 的 PSNR 计算有问题（`README.md:72-73`），示例数值不是本地复现结果（示例位置 `README.md:97-105,139-145`）。当前实现的证据如下：

1. `validate()` 先调用 `psnr_PIL(image_to_verify_PIL, original_PIL)`，之后才保存 `original.png`、`generated.png` 和 `attack_instance_step=*.png`（`utils/imprint_utils.py:352-388`），所以指标基于保存前的内存图像，不是重新读取保存文件后的结果。
2. `psnr_PIL()` 把两幅 PIL 图像转为数组、按通道排列、除以 255，再使用 `PeakSignalNoiseRatio(data_range=1.0)`（`utils/image_utils.py:495-518`）。像素范围是 `[0,1]`；参考图是 `original_PIL`，待测图是 `image_to_verify_PIL`（`imprint_utils.py:297-305,352-354`）。
3. Reprompting 显式传 `do_psnr=False`（`run_reprompting.py:124-137,178-192`），所以其 metrics 中 PSNR 为 -1；Imprint 默认计算 PSNR。

## 阶段判断

以上“根据源码判断”支持：目标检测结果会被读取并记录成功状态，但没有作为 Imprint 候选选择或超参数调整信号；当前代码会隐式触发模型加载/下载和 GPU 使用。模型权重、依赖兼容性、最小 Reprompting 输出和论文质量数值均为“尚未验证”。下一阶段需在 GPU 3 或 GPU 7 的 UUID 限制下准备隔离环境，再考虑最小 Reprompting；本阶段停止执行。
