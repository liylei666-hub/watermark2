# Stage 31 评估链路解剖 + 4-pair 全表 + 跨模型传递诊断（v2）

**运行：** server249，`CUDA_VISIBLE_DEVICES=""`，纯 CPU，只读；脚本经 stdin 管道执行，**服务器零落盘**。总耗时 < 2 s。
**脚本：** `diag_transfer31_v2.py` ｜ **原始输出：** `diag_out_v2.txt`（105 行）
**数据源：** `/data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z`、`reports/31_native_calibration_lpips_20261025/rows.jsonl`
**执行时间：** 2026-10-27 19:20 CST

---

# 1. `evaluate31.py` 与 `common31.py` 全文 + 算子细节

## 1.1 `scripts/native_calibration/evaluate31.py`（33 行，完整）

```python
import sys,time,math
from pathlib import Path
from common31 import c,r,module,gate,candidates,guard,BASE,POINTS
def main(runtime,root,private_folder,output):
    root=Path(root);out=Path(output);cfg=gate(runtime,out)
    if cfg['role']!='evaluator':raise ValueError('Wrong evaluator role')
    seal=c.read(root/'candidates_sealed.json')
    if seal['rows']!=candidates(root):raise ValueError('Candidates changed')
    import numpy as np,torch
    from PIL import Image
    from skimage.metrics import structural_similarity
    from torchmetrics.image import MultiScaleStructuralSimilarityIndexMeasure,PeakSignalNoiseRatio
    private=module('native_eval_private',BASE/'reference_reliability/private_state.py');r.deterministic(0)
    provider=r.official_provider(cfg['design']['target']);arrays=[];guard(provider.scheduler_inverse,arrays);provider.scheduler_inverse.set_timesteps(50,device='cuda:0');rows=[]
    for task in cfg['design']['tasks']:
        sid=task['id'];record=c.read(root/'prepare'/str(sid)/'record.json');raw=private.load(Path(private_folder),sid,record['encryption_fingerprints']);wm=private.provider(raw,'cuda:0')
        with Image.open(root/'prepare'/str(sid)/'cover.png') as im:cover=im.convert('RGB').copy()
        for label,path in [('reference',root/'prepare'/str(sid)/'reference.png'),('cover',root/'prepare'/str(sid)/'cover.png')]+[(str(n),root/f'attack_{sid}'/f'update_{n}.png') for n in POINTS]:
            folder=out/(str(sid)+'_'+label);folder.mkdir()
            with Image.open(path) as im:image=im.convert('RGB')
            start=time.perf_counter()
            with torch.no_grad():z=provider.invert_images(image,num_inference_steps=50)['zT_torch']
            torch.cuda.synchronize();inverse_seconds=time.perf_counter()-start;ba=float(wm.get_accuracies(z)['bit_accuracies'][0])
            a=np.asarray(image,dtype=np.float64)/255;b=np.asarray(cover,dtype=np.float64)/255;mse=float(np.mean((a-b)**2));psnr=None if mse==0 else -10*math.log10(mse)
            gray1=np.asarray(image.convert('L'));gray2=np.asarray(cover.convert('L'));ssim=float(structural_similarity(gray1,gray2,data_range=255))
            ta=torch.from_numpy(a).permute(2,0,1).unsqueeze(0).float();tb=torch.from_numpy(b).permute(2,0,1).unsqueeze(0).float()
            official_psnr=float(PeakSignalNoiseRatio(data_range=1.0)(ta,tb))
            ms=float(MultiScaleStructuralSimilarityIndexMeasure(data_range=1.0)(ta,tb))
            row=dict(task_id=sid,label=label,image=c.png_record(path),inverse=r.tensor(folder/'target_inverse.npy',z),bit_accuracy=ba,gs_detected=ba>.70703125,mse_rgb01=mse,psnr_db=psnr,official_torchmetrics_psnr_db=None if mse==0 else official_psnr,psnr_infinite=mse==0,ssim_grayscale=ssim,ms_ssim_rgb=ms,lpips=None,inversion_seconds=inverse_seconds)
            c.write(folder/'metrics.json',row);rows.append(dict(**row,folder=folder.name));print('EVALUATED',sid,label,flush=True)
    if seal['rows']!=candidates(root):raise ValueError('Candidate changed')
    c.write(out/'summary.json',dict(completed=True,rows=rows,candidate_seal_sha256=c.sha(root/'candidates_sealed.json'),scheduler_calls=arrays,lpips_status='unknown_no_admitted_backbone'));print('COMPLETED_NATIVE_EVAL',flush=True)
if __name__=='__main__':main(*sys.argv[1:])
```

## 1.2 `scripts/native_calibration/common31.py`（47 行，完整）

```python
"""Native calibration contracts. Importing does not initialize CUDA/model libraries."""
import ast,importlib.util,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
sys.path.insert(0,str(BASE/'cover_pilot'));import contract as c;import runtime as r
sys.path.insert(0,str(BASE/'parallel_execution'));import launcher as launch;import scheduler as sched
ROOT=r.ROOT;POINTS=(20,50,100,150,151)
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def update_code(path):
    tree=ast.parse(Path(path).read_bytes());loop=next(n for n in tree.body if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='step')
    body=[]
    for node in loop.body:
        if isinstance(node,ast.If):break
        body.append(node)
    if len(body)!=5:raise ValueError('Official update changed')
    return compile(ast.Module(body=body,type_ignores=[]),str(path),'exec')
def gate(runtime,out):
    launch.check_host(ROOT);cfg=r.verify_runtime(Path(runtime));d=sched.Device(**cfg['device'])
    expected=dict(CUDA_VISIBLE_DEVICES=d.uuid,CUDA_DEVICE_ORDER='PCI_BUS_ID',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    if d.index==6 or any(os.environ.get(k)!=v for k,v in expected.items()):raise ValueError('Wrong environment')
    rows=[];idle=sched.verify_idle(d,launch.sample,rows.append);c.write(Path(out)/'device_preimport.json',dict(device=d.__dict__,idle=idle,samples=rows))
    if not idle:raise RuntimeError('Child device busy, preserve no retry')
    return cfg
def guard(scheduler,records):
    original=scheduler.set_timesteps
    def checked(*a,**kw):
        result=original(*a,**kw);ts=scheduler.timesteps.tolist()
        if ts!=list(range(1,982,20)):raise ValueError('Unexpected actual inverse timestep array')
        records.append(dict(timesteps=ts,endpoint_alpha_cumprod=float(scheduler.alphas_cumprod[ts[-1]])));return result
    scheduler.set_timesteps=checked
def validate_job(path,cfg):
    path=Path(path);j=c.read(path);c.keys(j,['schema','task_id','seed','reference','cover','proxy','native'])
    if j['schema']!=1 or j['task_id'] not in (1,2,3,4) or j['seed']!=31300+j['task_id'] or j['proxy']!=cfg['proxy'] or j['native']!=cfg['native']:raise ValueError('Frozen native job changed')
    for kind in ('reference','cover'):
        if j[kind]!=c.png_record(path.parent/(kind+'.png')):raise ValueError('Input changed')
    return j
def candidates(root):
    rows=[]
    for sid in range(1,5):
        out=root/f'attack_{sid}';job=root/'attack_inputs'/str(sid)/'job.json';frozen=c.read(out/'candidates_frozen.json')
        if frozen['job_sha256']!=c.sha(job) or not c.read(out/'execution.json')['outcome']['completed']:raise ValueError('Unsealed job')
        for n in POINTS:
            record=c.png_record(out/f'update_{n}.png')
            if frozen['images'][str(n)]!=record:raise ValueError('PNG changed')
            rows.append(dict(task_id=sid,actual_update=n,path=out.name+f'/update_{n}.png',image=record))
    return rows
```

## 1.3 `target_inverse.npy` 是怎么生成的

```python
z = provider.invert_images(image, num_inference_steps=50)['zT_torch']   # evaluate31.py:22, 无梯度
r.tensor(folder/'target_inverse.npy', z)                                 # 落盘为 float32 .npy
```

- `provider` = `runtime.official_provider(design['target'])`，即 **SDXL**（`stabilityai/stable-diffusion-xl-base-1.0`，revision `462165984030d82259a11f4367a4eed129e94a7b`）官方 `PIPE_PROVIDERS` 封装，`resolution=512`。
- 调度器为 `provider.scheduler_inverse`，**DDIM Inverse，50 步**；`common31.guard()` 在 `set_timesteps` 上打补丁并硬断言时间步为 `list(range(1,982,20))`（1, 21, …, 981），同时记录 `endpoint_alpha_cumprod`。
- 输出是 **`zT_torch`，shape `(1, 4, 64, 64)`，dtype float32**（512/8 = 64；SDXL VAE 同为 4 通道）。写入磁盘的 `.npy` 与 `metrics.json.inverse.shape` 完全一致，实测无例外。
- 与 proxy 端 `reference_proxy_inverse.npy`（同为 `(1,4,64,64)`）**网格一一对应**，本次诊断因此按元素直接比较，无需重采样。

## 1.4 BA（Bit Accuracy）的完整计算链

`ba = wm.get_accuracies(z)['bit_accuracies'][0]`，`wm` 由 `private_state.provider(raw)` 构造：

```python
GsProvider(latent_shape=(1,4,64,64), device='cuda:0', dtype=torch.float32,
           message_width_in_bytes=32, num_replications=64, l=1, offset=0,
           message=raw[:32], key=raw[32:64], nonce=raw[64:])   # raw 为 80 字节私有材料
```

**逐层拆解（`utils/wm/gs_provider.py`）：**

| 层 | 操作 | 代码 |
|---|---|---|
| ① 反高斯量化 | 对 16384 个元素逐点做 `y = int(norm.cdf(z) * 2^l)`，`l=1` | `__recover_messages_from_latents:229-236` |
| ② 等价于符号判别 | `norm.cdf(0)=0.5`，故 `y=1 ⟺ z ≥ 0`，`y=0 ⟺ z < 0`；`y==2` 的极罕见情况钳到 1 | 同上 `233-235` |
| ③ 位串拼接 | 16384 个 1-bit 串成 `encrypted_bits_str` | `240-243` |
| ④ 字节化 | 每 8 bit 打包成 1 byte，得 2048 bytes | `247-254` |
| ⑤ ChaCha20 解密 | `Cipher(ChaCha20(key, nonce))` 解密，得 2048 bytes 明文 | `259-261` |
| ⑥ 重排 barcode | 2048 bytes → 16384 bits → 64 行 × 256 列 | `264-275` |
| ⑦ 多数表决 | 对 256 个位置各数 64 行里的 `1`，过半取 1 | `279-284` |
| ⑧ 位准确率 | 与原始 256-bit message 逐位比对，`matching/256` | `__calculate_bit_accuracy:311-320` |
| ⑨ 阈值判定 | `gs_detected = ba > 0.70703125`（= **181/256**，严格大于） | `evaluate31.py:29` |

**关键推论：** GS 的解码本质是**潜变量逐元素过零判别**，不是 DCT、不是能量比、也没有学习阈值。256 个消息位各被复制 **64 次**再做多数表决，所以单元素翻转率即使高达 40% 仍可能几乎不影响 BA —— 这解释了为什么 §3(a) 的 SignAgr 只有 0.594，而 BA 高达 0.92：**元素级误差高度相关地落在同一个消息位的复制组内**，多数表决吃掉了大部分随机翻转。

---

# 2. Stage 31 全量指标表

GS 阈值 0.70703125，严格 `>`。`||Δz0||` 为 `update_{label}_latent - initial_z0`（`cover` 行为 0，因为参照就是自身）。

## 2.1 逐 task

```
--- task 1 ----------------------------------------------------------------------------------------------------------------
  label  loss_b4_upd         BA   GS  PSNR_f64    LPIPS  ||dz0||2 ||dz0||inf
  cover          nan 0.51171875 fail       inf  0.00000    0.0000     0.0000
     20     0.858876 0.77343750 PASS   26.1796  0.09805   19.0238     0.2109
     50     0.473059 0.86718750 PASS   24.8153  0.13698   32.6701     0.6067
    100     0.254228 0.91796875 PASS   23.7775  0.18233   45.5869     1.1004
    150     0.158298 0.92578125 PASS   23.0743  0.21901   54.3851     1.5326
    151     0.156945 0.93359375 PASS   23.0619  0.21968   54.5301     1.5413

--- task 2 ----------------------------------------------------------------------------------------------------------------
  cover          nan 0.51171875 fail       inf  0.00000    0.0000     0.0000
     20     0.879112 0.76953125 PASS   27.4764  0.09779   19.2506     0.2107
     50     0.487710 0.83593750 PASS   26.1471  0.13939   33.3686     0.5847
    100     0.263356 0.86718750 PASS   25.0978  0.18494   46.2306     1.0857
    150     0.170636 0.89843750 PASS   24.2624  0.22527   54.6717     1.5663
    151     0.169358 0.88671875 PASS   24.2454  0.22591   54.8112     1.5757

--- task 3 ----------------------------------------------------------------------------------------------------------------
  cover          nan 0.48046875 fail       inf  0.00000    0.0000     0.0000
     20     0.886570 0.82812500 PASS   25.1381  0.10941   19.2329     0.2110
     50     0.473993 0.89453125 PASS   23.9697  0.15640   33.5691     0.5747
    100     0.240790 0.92968750 PASS   23.0319  0.20981   46.6140     1.2602
    150     0.155018 0.92187500 PASS   22.3898  0.23928   54.5068     1.6551
    151     0.153931 0.93359375 PASS   22.3794  0.23978   54.6330     1.6575

--- task 4 ----------------------------------------------------------------------------------------------------------------
  cover          nan 0.52343750 fail       inf  0.00000    0.0000     0.0000
     20     0.757702 0.83203125 PASS   30.3227  0.04381   17.9191     0.2105
     50     0.391993 0.86718750 PASS   28.2403  0.06542   29.7908     0.5824
    100     0.206512 0.90625000 PASS   26.5210  0.08688   39.9954     1.1634
    150     0.139300 0.93750000 PASS   25.3373  0.10596   46.1116     1.5748
    151     0.138401 0.92578125 PASS   25.3174  0.10632   46.2085     1.5837
```

## 2.2 四任务均值

| label | loss_before_update | BA | GS 通过 | PSNR_f64 (dB) | LPIPS | ‖Δz0‖₂ | ‖Δz0‖∞ |
|---|---|---|---|---|---|---|---|
| cover | — | 0.50683594 | 0/4 | inf | 0.00000 | 0.0000 | 0.0000 |
| 20 | 0.845565 | 0.80078125 | **4/4** | 27.2792 | 0.08726 | 18.8566 | 0.2108 |
| 50 | 0.456689 | 0.86621094 | **4/4** | 25.7931 | 0.12455 | 32.3497 | 0.5871 |
| 100 | 0.241222 | 0.90527344 | **4/4** | 24.6070 | 0.16599 | 44.6067 | 1.1524 |
| 150 | 0.155813 | 0.92089844 | **4/4** | 23.7659 | 0.19738 | 52.4188 | 1.5822 |
| 151 | 0.154659 | 0.91992188 | **4/4** | 23.7511 | 0.19792 | 52.5457 | 1.5896 |

**读法：**
- `loss` 与 `BA` 单调反向（loss ↓，BA ↑），但 **151 步 loss 继续降（0.15581→0.15466）而 BA 反而回落（0.92090→0.91992）**，task2/task4 是回落来源。
- `‖Δz0‖∞` 在 20→151 步从 0.21 涨到 1.59，**7.5 倍**；同期 `‖Δz0‖₂` 从 18.9 到 52.5，仅 **2.8 倍**。说明后期位移集中在少数极值坐标上（max 涨得比 L2 快得多）。
- 4 个任务在 20 步就 4/4 通过 GS 阈值，后续 130 步主要在换 PSNR/LPIPS。

---

# 3. Proxy(SD2.1) ↔ Target(SDXL) 传递诊断（4 任务均值）

## (a) 全张量对齐度（T_lbl vs T_ref）

| label | MSE | CosSim | SignAgr |
|---|---|---|---|
| cover | 1.508050 | −0.00556 | 0.49878 |
| 20 | 1.290772 | 0.15351 | 0.55142 |
| 50 | 1.192850 | 0.21966 | 0.57169 |
| 100 | 1.124704 | 0.26214 | 0.58493 |
| 150 | 1.093014 | 0.28135 | 0.59337 |
| 151 | 1.090213 | 0.28282 | 0.59421 |

## (b) 通道不均衡性

| label | Cos_c0 | Cos_c1 | Cos_c2 | Cos_c3 | SA_c0 | SA_c1 | SA_c2 | SA_c3 |
|---|---|---|---|---|---|---|---|---|
| cover | 0.00462 | −0.01300 | −0.00816 | −0.00203 | 0.50171 | 0.49481 | 0.49841 | 0.50018 |
| 20 | 0.26847 | 0.14540 | 0.08603 | 0.14169 | 0.58954 | 0.54681 | 0.52600 | 0.54333 |
| 50 | 0.35227 | 0.22985 | 0.13513 | 0.19276 | 0.61359 | 0.57074 | 0.54071 | 0.56171 |
| 100 | 0.40891 | 0.27442 | 0.16979 | 0.23169 | 0.63092 | 0.58472 | 0.55139 | 0.57269 |
| 150 | 0.42693 | 0.29485 | 0.19080 | 0.24896 | 0.63690 | 0.59064 | 0.56531 | 0.58063 |
| 151 | 0.42695 | 0.29562 | 0.19448 | 0.25000 | 0.63806 | 0.58997 | 0.56860 | 0.58020 |

**排序在所有 label 上完全稳定：ch0 > ch1 > ch3 > ch2。** 151 步 ch0 的 CosSim 是 ch2 的 **2.20 倍**（0.4270 vs 0.1945），SA 差 **6.9 个百分点**（0.6381 vs 0.5686）。通道权重不应均匀。

## (c) 幅值分位数贡献

**basis = |T_ref|**

| label | SA_Low | SA_Mid | SA_High | SAgain_L | SAgain_M | SAgain_H | SSE%_L | SSE%_M | SSE%_H |
|---|---|---|---|---|---|---|---|---|---|
| cover | 0.50193 | 0.49906 | 0.49146 | — | — | — | 16.29 | 49.17 | 34.54 |
| 20 | 0.51699 | 0.55355 | 0.61249 | 3.02 | 10.88 | **23.80** | 18.47 | 50.31 | 31.22 |
| 50 | 0.51816 | 0.57660 | 0.66070 | 3.26 | 15.48 | **33.28** | 19.23 | 51.05 | 29.71 |
| 150 | 0.52803 | 0.60029 | 0.69864 | 5.24 | 20.21 | **40.74** | 19.75 | 51.36 | 28.89 |

**basis = |P_ref|**

| label | SA_Low | SA_Mid | SA_High | SAgain_L | SAgain_M | SAgain_H | SSE%_L | SSE%_M | SSE%_H |
|---|---|---|---|---|---|---|---|---|---|
| cover | 0.49995 | 0.49864 | 0.49695 | — | — | — | 28.89 | 54.34 | 16.77 |
| 20 | 0.53866 | 0.55460 | 0.56530 | 7.74 | 11.16 | 13.59 | 29.49 | 54.09 | 16.42 |
| 50 | 0.55453 | 0.57416 | 0.59693 | 10.91 | 15.06 | 19.87 | 29.26 | 54.51 | 16.23 |
| 150 | 0.57701 | 0.59200 | 0.63110 | 15.41 | 18.62 | **26.67** | 29.46 | 54.40 | 16.13 |

**两种基准都支持离群值假说**：High 桶的符号一致率提升率始终最大（|T_ref| 基准 40.74%，|P_ref| 基准 26.67%），且 **High 桶的 SSE 占比随步数下降**（|T_ref| 34.54%→28.89%），说明误差在从极值点向外围扩散。但注意 |T_ref| 基准下 **15% 的元素承担了 34.5% 的初始误差**——极值点仍是最大的误差源，只是它在被修得最快。

## (d) 2D-FFT 径向频带

**相干性（复数余弦，T_lbl vs T_ref，逐通道后取均值）**

| label | Coh_low (r≤6) | Coh_mid (6<r≤16) | Coh_high (r>16) |
|---|---|---|---|
| cover | 0.04094 | −0.00874 | −0.00581 |
| 20 | 0.20507 | 0.19501 | 0.15069 |
| 50 | 0.27819 | 0.26104 | 0.21749 |
| 100 | 0.30633 | 0.31204 | 0.26037 |
| 150 | 0.32636 | 0.32926 | 0.28011 |
| 151 | 0.32780 | 0.33136 | 0.28121 |

**`delta_z0` 能量占比**

| step | E_low% | E_mid% | E_high% |
|---|---|---|---|
| 20 | 2.67 | 16.77 | **80.57** |
| 50 | 2.85 | 16.29 | **80.86** |
| 100 | 3.27 | 15.64 | **81.09** |
| 150 | 3.64 | 15.16 | **81.20** |
| 151 | 3.65 | 15.15 | **81.20** |

**81% 的优化位移能量在高频（r>16），而高频恰恰是相干性最低的频带**（0.281 vs 低/中频 0.328/0.331）。低频只占 3.65% 能量却拿到最高相干性。频带间的绝对差距不大（0.281–0.331），但**能量分布与相干性排序完全反向**——这是当前目标函数与跨模型可传递性之间的结构性错配。

---

# 4. 边界声明

- 4 对共享同一加密身份的开发数据；非总体统计、非论文复现、非 SOTA 结论。
- 全部为事后描述性诊断；未用目标分数选点或调参（`target_scores_seen=0` 未破）。
- 分位数（30/85）与频带（r≤6 / 6<r≤16 / r>16）为本次预先固定，未按结果调整。
- `cover` 的 PSNR 为 `inf`（与自身比较，`psnr_infinite=true`）；LPIPS=0。
- `loss_before_update[N]` 是第 N 次优化**之前**在 z0 上算的 loss。
