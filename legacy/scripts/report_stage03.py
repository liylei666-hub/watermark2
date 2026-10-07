"""Render observed stage03 metrics; scientific interpretation is reviewed separately."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stage02.core import METHODS

def rstr(r):return f"{r['count']}/{r['total']} ({100*r['rate']:.2f}%)"

def main():
    out=ROOT/'outputs/stage03';metrics=json.loads((out/'metrics.json').read_text());pre=json.loads((out/'preflight.json').read_text());binding=json.loads((out/'gpu_binding.json').read_text());audit=json.loads((out/'audit.json').read_text());runtime=json.loads((out/'generator_runtime.json').read_text())
    lines=['# 阶段 3：真实生成图像同域实例区分诊断','',
           '完整参考特征下的内容表示诊断。阈值由校准 A 独立确定；同提示词不同种子是自然重生成负样本，不是自适应伪造攻击。真实局部编辑 C 未评测。','',
           '## 完成状态与数据','',
           f"机器审计：{audit['status']}。主体原图 {metrics['originals']} 张（计划480；p094所属族固定seed被安全检查/超时拦截而排除），推理图像 {metrics['images']} 张；有效 {metrics['prompts']} 提示词、{metrics['families']} 个完整族，校准/测试配对数见下表。独立预检查16张，另1张同种子重复，不进入主体数据。",'',
           '|类别|校准配对|测试配对|','|---|---:|---:|']
    for c in ['A','B_raw','B_post','D','SELF']:lines.append(f"|{c}|{metrics['counts']['calibration/'+c]}|{metrics['counts']['test/'+c]}|")
    lines+=['','同提示词并不保证构图相近。提示词是项目自编，主题覆盖六类；固定视觉总览按预注册规则选择，不能据此视为最困难冒认集。',
            '', '## 主工作点：校准目标 FRR=5%','',
            '|方法|阈值|校准 A FRR|测试 A FRR|测试 B_raw 错误接受|测试 B_post 错误接受|测试 D 错误接受|',
            '|---|---:|---:|---:|---:|---:|---:|']
    for m in METHODS:
        w=metrics['methods'][m]['working_points']['0.05'];t=w['test']
        lines.append(f"|{m}|{w['threshold']:.9f}|{rstr(w['calibration_A'])}|{rstr(t['A'])}|{rstr(t['B_raw'])}|{rstr(t['B_post'])}|{rstr(t['D'])}|")
    lines+=['','接受条件为 score≥threshold，等号接受。阈值取校准 A 升序数组第 floor(target×n) 项（0起始）。相同校准目标不保证测试 FRR 相同，以上不是相同测试 FRR 下的严格排名。','',
            '## 变换分解（5%校准工作点）','', '|方法|变换|测试 A 拒绝|测试 B_post 错误接受|','|---|---|---:|---:|']
    for m in METHODS:
        t=metrics['methods'][m]['working_points']['0.05']['test']
        for transform,r in t['A']['by_transform'].items():lines.append(f"|{m}|{transform}|{rstr(r)}|{rstr(t['B_post']['by_transform'][transform])}|")
    lines+=['','## 辅助工作点','', '|校准目标|方法|测试 A FRR|测试 B_raw|测试 B_post|测试 D|','|---|---|---:|---:|---:|---:|']
    for target in ['0.01','0.1']:
        for m in METHODS:
            t=metrics['methods'][m]['working_points'][target]['test']
            lines.append(f"|{float(target):.0%}|{m}|"+'|'.join(rstr(t[c]) for c in ['A','B_raw','B_post','D'])+'|')
    lines+=['','## 组级不确定性','',
            '1000次校准族与测试族分别有放回重采样；每次重新拟合校准阈值，方法共享索引。以下为主工作点95%经验百分位区间。每个测试类别来自60提示词、30族；派生图和配对不能视为独立试验。各组配对数相同，pair均值、prompt均值、family均值数值一致，具体组级统计已存metrics。','',
            '|方法|测试 A FRR 区间|B_raw 区间|B_post 区间|D 区间|','|---|---|---|---|---|']
    for m in METHODS:
        cells=[]
        for c in ['A','B_raw','B_post','D']:
            r=metrics['bootstrap']['intervals']['0.05'][m][c];cells.append(f"[{r['lower']:.2%}, {r['upper']:.2%}]"+('（退化）' if r['degenerate'] else ''))
        lines.append('|'+m+'|'+'|'.join(cells)+'|')
    lines+=['','退化零区间不能证明零错误概率或极低 FAR。这是有限提示词分布上的探索性估计。D按源族重采样且供体图固定，未完全处理交叉供体依赖；不能据其区间作强泛化声明。','',
            '## 信息与运行成本','', '|方法|float32 数组 B/参考图|实测 npy B/参考图|CPU评分总秒|','|---|---:|---:|---:|']
    for m in METHODS:
        r=metrics['methods'][m];lines.append(f"|{m}|{r['reference_array_bytes']:,}|{r['reference_npy_bytes']:,}|{metrics['scoring_seconds'][m]:.6f}|")
    lines+=['','DINO局部分数使用全局向量256倍的参考数组信息。两个局部分数共用patch余弦，但上表为各分数单独承担该共享计算的成本；不能相加作为实测总墙钟。模型加载、输入预处理、缓存读写与GPU计算另见下表。','',
            '|模型|宿主GPU|实际推理/缓存命中|加载秒|提取及缓存秒|峰值allocated MiB|峰值reserved MiB|','|---|---:|---|---:|---:|---:|---:|']
    for task,records in metrics['workers'].items():
        for model,r in records.items():lines.append(f"|{model}|{5 if task=='clip_sscd' else 7}|{r['inferred']}/{r['cache_hits']}|{r['load_seconds']:.3f}|{r['extract_cache_seconds']:.3f}|{r['peak_allocated_bytes']/2**20:.2f}|{r['peak_reserved_bytes']/2**20:.2f}|")
    lines+=['',f"生成预算保守计费共 {metrics['generation_budget']['charged_seconds']:.2f} 秒 / 10,800 秒（包括加载与重复检查，下载等待不计）。预检查均值 {pre['mean_seconds']:.3f} 秒/图；重复生成检查 {json.dumps(pre['repeat'],ensure_ascii=False)}。",'',
            'GPU采用单UUID隔离、内部cuda:0，启动和实际PID绑定记录见gpu_binding.json，前中后快照见logs资源JSONL。GPU 5 共享环境中的原有进程不属于本项目；其状态按本轮快照核实。生成结束后才在GPU 7运行DINO，GPU 5顺序CLIP/SSCD。','',
            '## 复现与证据','',
            '统一入口与固定设置见03_generation_protocol.md。stage02原始数据/阈值/结果的哈希审计通过；模型与评分沿用既有实现。实际19项单元测试日志在outputs/stage03/logs/unittest.log；audit.json覆盖清单、图像SHA、特征形状/范数、CSV复算、GPU绑定、预算及阶段2保存。', '',
            '服务器项目：/data0/liyanlei/instance_authentication_research。代码、清单、哈希、轻量结果和报告同步私有仓库；完整图像、权重和特征缓存留在服务器。实验完成和Git同步状态分别记录。', '',
            '### 本次生成运行时','', '```json',json.dumps(runtime,indent=2,ensure_ascii=False),'```','',
            '## 视觉与科学解释','',
            '## 结果解释与范围','',
            'B_raw 在5%校准工作点对全部五种表示均为0/174错误接受；B_post中只有CLIP_global出现1/1044错误接受，其余为0。这个结果说明在本次SD1.5同提示词重生成样本及有效编辑下，现成表示大多已能拒绝独立实例；不能据此声称对主动或自适应冒认有防护。零错误区间退化，不能解释为零FAR。',
            'A测试FRR为6.61%–8.62%，而JPEG Q70造成主要拒绝（各方法25.86%–43.10%）；亮度与缩放几乎未造成拒绝。局部q10在本数据上没有更低B错误接受，且A拒绝最高；局部参考数组为全局DINO的256倍。当前数据不支持把“同提示词实例区分”单独作为新方法动机，也不支持否定内容绑定或认证方向。',
            '固定总览的人工抽查记录于 figures/visual_review_early.json 与 visual_review_architecture.json：同提示词图像通常共享主题、颜色或粗粒度结构，但物体数量、位置和构图有明显差异；SD1.5在1024输出下出现重复结构和局部畸变。该观察未用于删样本或调参。',
            '本诊断没有水印载荷、签名、提取器、参考数据库或公开验证威胁模型，因此不能替代端到端认证防伪证明。最值得下一步验证的问题是：在保留真实允许编辑FRR的前提下，加入授权的内容替换/主动优化样本后，这些现成表示是否仍能区分实例；若SSCD或全局表示继续足够，应优先收窄问题而非训练新局部网络。']
    (ROOT/'research/03_same_prompt_diagnostic.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':main()
