# Stage 31 原生 Imprint 代码审计与 Stage 27 delivery 公式对照

**性质：** 只读代码审计。未修改任何冻结资产、未启动任何 GPU 进程、未重新生成任何图像或张量。  
**审计对象：** `/data0/liyanlei/watermark_research`（server249）  
**审计时间：** 2026-10-27（Asia/Shanghai）  
**上游代码：** `third_party/semantic-forgery`，commit `ca68950cd7b53b8438a49580f134b2a0db28d778`（PSNR 修正 `d5885a3a01f0ea4ce8cd9afc0dabb56df77e7a90`）

---

## 0. 路径索引

| 角色                  | 绝对路径                                                                        |
| ------------------- | --------------------------------------------------------------------------- |
| Stage31 执行入口        | `/data0/liyanlei/watermark_research/scripts/native_calibration/attack31.py` |
| Stage31 共享契约        | `.../scripts/native_calibration/common31.py`                                |
| Stage31 评估器         | `.../scripts/native_calibration/evaluate31.py`                              |
| **真正算法（官方）**        | `.../third_party/semantic-forgery/run_imprint_forgery.py`                   |
| 可微管道                | `.../third_party/semantic-forgery/utils/imprint_utils.py`                   |
| 攻击端运行时清单            | `.../protocols/31_attacker_0_runtime.json`                                  |
| 评估端运行时清单            | `.../protocols/31_evaluator_0_runtime.json`                                 |
| 执行协议                | `.../protocols/31_native_calibration_execution.json`                        |
| 运行根目录               | `.../runs/31_native_calibration_20261024T190323Z/`                          |
| 交付诊断                | `.../scripts/analyze_imprint_delivery.py`                                   |
| 端点残差诊断              | `.../scripts/endpoint_residual/{common,control,experiment}.py`              |
| Stage27 delivery 实现 | `.../scripts/method_comparison/attack.py`                                   |
| Stage27 参数表         | `.../scripts/cover_pilot/contract.py`                                       |

> 注：`scripts/analyze_endpoint_residual.py` 与 `reports/18_endpoint_residual/` 在服务器上**不存在**，仅存在于 GitHub `research/stage27-recovery-20261019` 分支。服务器上的等价实现是 `scripts/endpoint_residual/`，数学核心在 `common.py:summarize()`。

---

## 1. Stage 31 核心 Imprint 攻击

### 1.1 启动方式

Stage 31 **不使用官方 argparse 入口**。`attack31.py` 从 `run_imprint_forgery.py` 里用 AST 抽取优化循环后自行执行，参数由 `job.json` 与代码常量冻结。

实测命令（`runs/31_native_calibration_20261024T190323Z/attack_1/process.json`）：

```bash
env CUDA_VISIBLE_DEVICES=GPU-aafaf524-a6f4-f646-a2b5-7d243e80c8a5 \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
    HF_HOME=/data0/liyanlei/watermark_research/cache/huggingface \
    PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false \
    CUBLAS_WORKSPACE_CONFIG=:4096:8 \
/data0/liyanlei/watermark_research/envs/semantic_forgery_py310/bin/python \
  /data0/liyanlei/watermark_research/scripts/native_calibration/attack31.py \
  /data0/liyanlei/watermark_research/protocols/31_attacker_0_runtime.json \
  /data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z/attack_inputs/1/job.json \
  /data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z/attack_1
```

官方 CLI 等价参数（仅供对照，未被调用）：

```
--lr 1e-2 --steps 151 --validation_steps 10 --seed 31301
--modelid_attacker Manojb/stable-diffusion-2-1-base
--scheduler_attacker DDIM --num_inference_steps_attacker 50
--wm_type GS --resolution 512
--cover_image_path <cover.png> --cover_mask_path None
```

### 1.2 代码抽取机制

`common31.py:10-17` 用 AST 从官方脚本取出循环体，并**强制断言恰好 5 条语句**，一旦上游改动就 raise：

```python
def update_code(path):
    tree = ast.parse(Path(path).read_bytes())
    loop = next(n for n in tree.body
                if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'step')
    body = []
    for node in loop.body:
        if isinstance(node, ast.If):
            break
        body.append(node)
    if len(body) != 5:
        raise ValueError('Official update changed')
    return compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec')
```

### 1.3 核心优化循环

对应官方 `run_imprint_forgery.py:186-196`：

```python
for step in tqdm.tqdm(range(args.steps)):
    optim.zero_grad()

    inverted_latent = diffpipe(z0, "", guidance_scale=1.)

    # get loss in zT space
    l = torch.nn.functional.mse_loss(inverted_latent, zT_retrieved.detach())

    # do update
    l.backward()
    optim.step()
```

`attack31.py:32-39` 的驱动：

```python
code = update_code(r.UPSTREAM / 'run_imprint_forgery.py')
state = dict(optim=optim, diffpipe=diff, z0=z0, torch=torch, zT_retrieved=target)
for actual in range(1, 152):
    exec(code, state)                       # 每步重放 5 条官方语句
    if not torch.isfinite(z0).all() or not torch.isfinite(state['l']):
        raise RuntimeError('Nonfinite original update')
    history.append(dict(actual_update=actual,
                        loss_before_update=float(state['l'].detach()), ...))
```

### 1.4 超参数

| 项           | 值                                                                | 来源                         |
| ----------- | ---------------------------------------------------------------- | -------------------------- |
| 可训变量        | 仅 `z0`，`(1,4,64,64)` float32                                     | `attack31.py:25`           |
| `z0` 初值     | `pixel_to_latent(cover)` = VAE `posterior.mean × scaling_factor` | `imprint_utils.py:228-244` |
| 优化器         | `torch.optim.Adam([z0], lr=0.01)`                                | `attack31.py:25`           |
| 学习率调度       | 无（常数）                                                            | —                          |
| 权重衰减 / 梯度裁剪 | 无                                                                | —                          |
| 更新步数        | **151**（`range(1,152)`）                                          | `attack31.py:34`           |
| Loss        | **z_T 空间纯 MSE**                                                  | 官方 192 行                   |
| 冻结参数        | UNet `requires_grad=False`，VAE 不建图                               | `imprint_utils.py:67-68`   |
| 梯度实现        | `torch.utils.checkpoint` 重入式检查点                                  | `imprint_utils.py:157`     |
| 确定性         | `use_deterministic_algorithms(True)`、TF32 关闭、cuDNN benchmark 关闭  | `runtime.py:42-51`         |

### 1.5 z_T 的对齐方式

两条 z_T 位于**同一空间、同一路径、同一步数、全确定性**：

```python
# imprint_utils.invert_image()：参考图 → z_T（目标，无梯度）
posterior = pipe.vae.encode(image_pt).latent_dist
z0_ref = posterior.mean * pipe.vae.config.scaling_factor     # 取均值，不采样
zT_retrieved = pipe(latents=z0_ref, num_inference_steps=50, prompt=[""],
                    negative_prompt=[""], guidance_scale=1.,
                    width=512, height=512, output_type='latent')[0]
```

对齐要点：

1. **同一潜空间**：proxy（SD2.1）VAE 潜空间，`(1,4,64,64)`，同为 `posterior.mean × scaling_factor`，非采样。
2. **同一时间轴**：均用 `DDIMInverseScheduler`，50 步。`common31.guard()` 硬断言实际时间步数组：
   ```python
   if ts != list(range(1, 982, 20)):
       raise ValueError('Unexpected actual inverse timestep array')
   ```
   即 `1, 21, 41, …, 981`，并记录 `endpoint_alpha_cumprod`。
3. **无 CFG**：`guidance_scale=1.0` → `do_classifier_free_guidance = (1.0 > 1.) = False`，单批次前向，`prompt=""` 的文本嵌入仍参与。
4. **噪声缩放**：`latents = latents * scheduler.init_noise_sigma`（DDIM 为 `1.0`，恒等但在路径上）。
5. **无 RNG**：对齐过程不消耗随机数；唯一随机性来自 `seed = 31300 + task_id` 的参考图生成。

---

## 2. 4-pair 结果目录中的潜变量张量

目录：`runs/31_native_calibration_20261024T190323Z/attack_{1,2,3,4}/`

**每个任务 17 个 `.npy`，全部 `(1, 4, 64, 64)` float32：**

| 文件                                      | 语义                               | 是否 z_T |
| --------------------------------------- | -------------------------------- | ------ |
| `initial_z0.npy`                        | 载体 VAE 编码，优化前                    | 否（z₀）  |
| **`reference_proxy_inverse.npy`**       | **优化目标 z_T(x_ref)**，参考图 proxy 反演 | **是**  |
| `update_{20,50,100,150,151}_latent.npy` | 该检查点的 **z0**（被优化量）               | 否（z₀）  |
| `update_{N}_adam_avg.npy`               | Adam 一阶矩                         | 否      |
| `update_{N}_adam_sq.npy`                | Adam 二阶矩                         | 否      |

### 结论

- **伪造端的 z_T(x_forged) 没有落盘。** `diffpipe(z0)` 只在前向图内存在，持久化的只有标量 `optimization.json → updates[].loss_before_update`（151 条）。
- **目标域的 z_T 存在**：`evaluate/{sid}_{label}/target_inverse.npy`，共 28 个目录（4 任务 × {reference, cover, 20, 50, 100, 150, 151}），同样 `(1,4,64,64)` float32，由 `evaluate31.py:22` 用 **SDXL 目标 provider** 的 `invert_images()` 生成。
- 因此若新算法需要 proxy 空间的 z_T(x_forged)，必须重算一次前向（单次 50 步反演，无需重新优化）。

### 收敛与开销

| task | L₁       | L₁₅₁     | core 秒 | peak 显存  |
| ---- | -------- | -------- | ------ | -------- |
| 1    | 1.809677 | 0.156945 | 5680.2 | 11.46 GB |
| 2    | 1.800351 | 0.169358 | 5732.5 | 11.46 GB |
| 3    | 1.831161 | 0.153931 | 5704.3 | 11.46 GB |
| 4    | 1.821258 | 0.138401 | 5717.5 | 11.46 GB |

---

## 3. 两个数学诊断脚本

### 3.1 `scripts/analyze_imprint_delivery.py`（存在，CPU-only）

强制 `CUDA_VISIBLE_DEVICES=""`。对 z_T 空间做 **float64 MSE 三层分解**，把「内部改善」与「交付改善」拆开：

```python
values = {name: mse(arrays[array], target) for name, array in [
    ('internal_loss',       'internal_noise'),   # 优化图内 50 步反演结果
    ('float_delivery_loss', 'float_noise'),      # 导出为 float 后再反演
    ('png_delivery_loss',   'png_noise')]}       # PNG 存盘读回后再反演
values.update({name: mse(arrays[a], arrays[b]) for name, a, b in [
    ('float_latent_displacement',        'float_z', 'z'),
    ('png_latent_displacement',          'png_z',   'z'),
    ('quantization_latent_displacement', 'png_z',   'float_z')]})
```

汇总指标：

```
improvement[name]                = first[name] - last[name]              # name ∈ {internal, float_delivery, png_delivery}
improvement_internal_minus_png   = improvement['internal_loss'] - improvement['png_delivery_loss']
png_minus_internal               = png_delivery_loss - internal_loss     # 交付环节引入的绝对损失
png_vs_float_noise_mse           = mse(png_noise, float_noise)           # 8-bit 量化在 z_T 空间的影响
```

**解读方式：** `improvement_internal_minus_png` 为正 = 内部优化收益没有传导到最终交付；`quantization_latent_displacement` 度量 8-bit PNG 往返造成的潜变量漂移。

### 3.2 端点残差诊断（服务器上是 `scripts/endpoint_residual/common.py`）

```python
def summarize(arrays):
    zr, nr = arrays['reference_z'], arrays['reference_inverse']
    cover_vae   = mse(arrays['cover_z'], zr)          # VAE 空间到参考的距离
    cover_noise = mse(arrays['cover_inverse'], nr)    # z_T 空间到参考 z_T 的距离
    vae   = {n: mse(arrays[n + '_z'],       zr) for n in ['cover','imprint_png','jain_png','jain_float']}
    noise = {n: mse(arrays[n + '_inverse'], nr) for n in ['cover','initial_png','imprint_native','imprint_png','imprint_float','jain_png']}

    native_improvement = cover_noise - noise['imprint_native']
    png_improvement    = noise['initial_png'] - noise['imprint_png']
    return dict(
        vae_mse=vae,
        vae_relative_reduction={k: relative_drop(cover_vae, v) for k, v in vae.items()},
        inversion_mse=noise,
        inversion_reduction_from_cover={k: relative_drop(cover_noise, v) for k, v in noise.items()},
        imprint_native_improvement=native_improvement,
        imprint_png_improvement=png_improvement,
        imprint_png_improvement_retained=png_improvement / native_improvement,   # ★ 关键
        imprint_final_delivery_gap=noise['imprint_png'] - noise['imprint_native'],
        imprint_float_delivery_gap=noise['imprint_float'] - noise['imprint_native'],
        imprint_quantization_loss_difference=noise['imprint_png'] - noise['imprint_float'],
        jain_float_to_png_vae_difference=vae['jain_png'] - vae['jain_float'])
```

核心量是 **`imprint_png_improvement_retained`（内部改善保留率）**。Stage 18 实测 87%–94%，但 2/3 任务出现 proxy 与 target 的候选排序反转。

---

## 4. Stage 27 `delivery` 的公式改动

实现：`scripts/method_comparison/attack.py:20-64`。参数：`updates=10, learning_rate=0.01, inversion_steps=50, inversion_guidance=1.0`。

### 4.1 公式对照

|                       | 目标函数                                                  | 可微路径                                              |
| --------------------- | ----------------------------------------------------- | ------------------------------------------------- |
| **native Imprint**    | `L = MSE( Inv_p(z₀), z_T(x_ref) )`                    | `z₀ → DDIM⁻¹(50) → z_T`                           |
| **delivery（Stage27）** | `L = MSE( Inv_p( E( clamp( D(z₀) ) ) ), z_T(x_ref) )` | `z₀ → VAE 解码 → clamp → VAE 编码 → DDIM⁻¹(50) → z_T` |


其中：

```python
def mapping(value):                                     # ← delivery 唯一新增项
    raw = pipe.vae.decode(value / pipe.vae.config.scaling_factor, return_dict=False)[0]
    return scope['pixel_to_latent'](2 * (raw * .5 + .5).clamp(0, 1) - 1, pipe)
    #      ↑ pixel_to_latent = VAE.encode().latent_dist.mean * scaling_factor

inverse_fn = lambda value: diff(value, '', guidance_scale=1., num_inference_steps=50)
```

即 `E(·)` 是 `posterior.mean × scaling`，`D(·)` 是 `vae.decode(z / scaling)`，`clamp(·, 0, 1)` 模拟像素域截断。**8-bit 量化本身不在目标内**（`quantization_backward='not_in_objective'`），只有连续 clamp。

### 4.2 梯度实现：`split_exact_chain`

```python
def split_gradient(z, mapping, inverse, target):
    with torch.no_grad():
        encoded = mapping(z)                       # 前向不建图，省显存
    leaf = encoded.detach().requires_grad_(True)
    loss = torch.nn.functional.mse_loss(inverse(leaf), target)
    loss.backward()                                # 只回传到 encoded
    downstream = leaf.grad.detach().clone()
    mapped = mapping(z)                            # 重新建图
    mapped.backward(downstream)                    # 再回传到 z
```

设计意图是避免同时持有 `E` 与 `DDIM⁻¹` 两张图；数学上与端到端链式求导等价（除重计算引入的浮点差异）。

### 4.3 失败结果

来源：`reports/27_method_resume_20261019T173017Z/report.md:7,14`

| 指标 | 结果 |
|---|---|
| 普通 GS 通过 | **6/12（delivery） vs 8/12（imprint）** |
| 平均消息位准确率 | 低 **1.8229** 个百分点 |
| 中位配对像素 MSE 比（delivery/imprint） | **0.908971**（<1，delivery 更接近载体） |
| 核心时间比 | 1.051660 |
| 预注册门槛「至少多通过 3 个」 | 实际 **−2 → 判负关闭** |

**注意：** Stage 27 中 imprint 与 delivery 都是 **10 步**（`cover_pilot/contract.py:10`），预算一致，差异不能归因于步数。

### 4.4 机制解读（审计者读法，非项目结论）

`E ∘ D` 是压缩映射，且 `clamp` 在饱和区梯度为 0。优化器因此可以在 `E(D(z))` 几乎不变的方向上继续降低 loss——**潜变量在动，交付图像没动**。等效于给目标函数加了一个「回到载体流形」的强正则：同样 10 步内 z_T 位移更小，于是像素 MSE 更低（质量更好）而 BA 更低（伪造更弱）。

这是一次**质量–鲁棒性权衡被无意写进目标函数**，而非优化失败。项目自身的边界声明也一致：该固定候选关闭、不调参、不推广为「所有同类方法无效」。

---

## 5. 对设计新算法的直接约束

1. **z_T 目标不可改**：`z_T(x_ref)` 必须仍由 proxy 的 `posterior.mean × scaling` + 50 步 `DDIMInverseScheduler`（`1..981`，prompt `""`，guidance 1.0）确定，否则与历史所有阶段不可比。
2. **评估边界**：攻击端只能看到参考图、载体图、proxy 配置与自身随机状态；目标密钥/消息/nonce、目标反演、GS 分数属于评估端，**不得进入优化循环**（当前 `target_scores_seen=0`）。
3. **预算定义**：核心预算 = 参考反演 + 载体编码 + 优化步，不含模型加载与导出。现有参照：151 步 ≈ 5700 s / 对（11.46 GB 峰值）；10 步 ≈ 376 s。
4. **可复用的中间量**：`update_*_latent.npy` 与 `evaluate/*/target_inverse.npy` 已存在，任何「z_T 位移 vs 交付位移」的新诊断可**零 GPU** 起步，先用这 4 对做 CPU 侧假设检验。
5. **可复用的诊断口径**：`improvement_retained = png_improvement / native_improvement` 与 `quantization_latent_displacement` 应作为新方法的必报指标，避免重犯 delivery 的「内部改善自嗨」。

---

## 附录：只读复核命令

```bash
# 1. 环境（不加载模型）
/data0/liyanlei/watermark_research/envs/semantic_forgery_py310/bin/python -c \
  "import torch; print(torch.__version__, torch.cuda.is_available())"

# 2. 张量清单与 shape（只读 header，不整载）
/data0/liyanlei/watermark_research/envs/semantic_forgery_py310/bin/python - <<'EOF'
import numpy as np, glob, os
base='/data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z'
for d in ['attack_1','attack_2','attack_3','attack_4']:
    print('##', d)
    for f in sorted(glob.glob(os.path.join(base, d, '*.npy'))):
        a = np.load(f, mmap_mode='r')
        print('  ', os.path.basename(f), a.shape, a.dtype)
EOF

# 3. 损失轨迹与耗时
/data0/liyanlei/watermark_research/envs/semantic_forgery_py310/bin/python - <<'EOF'
import json
base='/data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z'
for t in [1,2,3,4]:
    o=json.load(open(f'{base}/attack_{t}/optimization.json')); u=o['updates']
    s=json.load(open(f'{base}/attack_{t}/summary.json'))
    print(t, len(u), u[0]['loss_before_update'], u[-1]['loss_before_update'], s['timing']['core_seconds'])
EOF
```
