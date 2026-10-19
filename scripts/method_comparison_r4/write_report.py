"""Publish verified fixed-comparison statistics and all image links; no model execution."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import csv,datetime,io,json,statistics,sys
from pathlib import Path

def number(value,digits=4):return 'unknown' if value is None else f'{value:.{digits}f}'
def flag(value):return 'unknown' if value is None else '通过' if value else '未通过'
def main(project,report_name):
    project=Path(project);report=project/'reports'/report_name;result=json.loads((report/'verification_private.json').read_text(encoding='utf-8'));cfg=json.loads((project/'protocols/27_method_runtime_r4.json').read_text(encoding='utf-8'));run=cfg['run_dir'];rows=result['rows']
    observed=json.loads((report/'candidate_visual_observations.json').read_text(encoding='utf-8'))
    if not result['verified'] or result['independent_gs_scores_checked']!=59 or observed['images_observed']!=35:raise ValueError('Verification or visual review incomplete')
    visual={(x['task_id'],x['method']):x for x in observed['rows']}
    if len(visual)!=35 or len(observed['rows'])!=35:raise ValueError('Visual observation inventory mismatch')
    reviewed=[]
    for row in rows:
        key=(row['task_id'],row['method'])
        if row['status']=='completed' and key not in visual:raise ValueError('Candidate visual observation missing')
        if row['status']=='completed':
            frozen=json.loads((project/run/'attack_outputs'/str(row['task_id'])/row['method']/'candidate_frozen.json').read_text())
            if visual[key]['image_sha256']!=frozen['image']['sha256']:raise ValueError('Visual observation image binding mismatch')
        reviewed.append(dict(row,model_assisted_visual_observation=visual[key]['observation'] if key in visual else None,visual_review_type='model_assisted' if key in visual else 'no_candidate',independent_human_review=False))
    fields=list(reviewed[0]);fields+=['failure_reason']
    output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader();writer.writerows(reviewed)
    reviewed_csv=report/'task_results_reviewed.csv';data=output.getvalue().encode()
    if reviewed_csv.exists():
        if reviewed_csv.read_bytes()!=data:raise ValueError('Existing reviewed CSV differs')
    else:
        with reviewed_csv.open('xb') as f:f.write(data)
    names=dict(imprint='原生 Imprint',jain='适配 Jain',delivery='交付路径 Imprint')
    decision={'close_this_fixed_candidate_without_parameter_tuning_or_supplement':'关闭这个固定候选',
              'promising_development_result_requires_independent_confirmation_and_novelty_evidence':'值得独立确认',
              'inconclusive_not_success':'因具体缺失暂时不能判断'}[result['decision']]
    text=['# 阶段27：完整方法比较结果','',f'研究决定：**{decision}**。这是4组提示词、每组3个独立种子与GS身份的12任务开发筛选。',
          '',f"共36次计划攻击尝试，35张候选完成，1次工程失败保留；24张参考/载体图和35张候选的59个普通GS分数均经独立CPU解码复核。主比较包含全部12个delivery/imprint配对；Jain任务2没有输出或检测结果。",
          '',f"delivery相对imprint的普通GS通过数差为{result['gs_pass_gain']}，平均消息位准确率差{result['mean_bit_accuracy_difference']*100:.4f}个百分点；中位配对像素MSE比{result['median_paired_pixel_mse_ratio']:.6f}、核心时间比{result['median_paired_core_time_ratio']:.6f}。",
          '', '## 冻结规则逐条判定','', '| 条件 | 实测值 | 判定 |','|---|---:|---|']
    values=[('12张参考均通过普通GS',f"{result['valid_references']}/12",'all_12_references_valid'),('delivery至少多通过3个',str(result['gs_pass_gain']),'minimum_3_additional_gs_passes'),('中位配对MSE比≤1.05',number(result['median_paired_pixel_mse_ratio'],6),'median_mse_ratio_at_most_1_05'),('中位配对核心时间比≤1.15',number(result['median_paired_core_time_ratio'],6),'median_core_time_ratio_at_most_1_15')]
    for label,value,key in values:text.append(f'| {label} | {value} | {flag(result["decision_gates"][key])} |')
    text+=['','规则来自[首次冻结设计](../../protocols/27_method_design.json)，未根据结果修改。任务2 Jain的缺失限制Jain辅助比较，不缺少delivery/imprint主比较所需的候选。若参考有效性条件或主比较所需指标缺失，按原规则为不能判断。',
           '', '## 方法汇总','', '| 方法 | 输出/计划 | 工程失败 | 交付且GS通过/全部计划 | 已交付BA均值 | 已交付MSE中位数 | 已交付PSNR均值(dB) | 核心时间中位数(s) | 全部尝试进程时间(s) |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for method,s in result['summary'].items():text.append(f"| {names[method]} | {s['delivered']}/12 | {s['failed']} | {s['gs_pass_count']}/12 | {s['conditional_mean_bit_accuracy']:.6f} | {s['conditional_median_pixel_mse']:.8f} | {s['conditional_mean_psnr_db']:.3f} | {s['conditional_median_core_seconds']:.3f} | {s['total_process_seconds']:.3f} |")
    text+=['','Jain连续指标仅覆盖11个已交付任务，工程失败没有被填成0或从计划分母移除。“交付且普通GS通过”是流程事件，不是完整语义防御成功率。等更新数不等于等算力；上表直接给出实际核心时间与进程时间。',
           '', '核心时间沿用冻结记录定义：Imprint/delivery为参考反演及载体编码准备加优化，Jain为参考编码及优化；不包含模型加载、导出及此前独立的共同载体生成。进程时间是对应攻击工作进程从启动到退出的墙钟时间，包含设备检查与加载。准备和目标检测的进程另计入全组用量，不摊入单方法核心预算。',
           '', '## 参考与无水印载体对照','', '| 任务 | 参考BA | 参考GS | 载体BA | 载体GS |','|---:|---:|---|---:|---|']
    score_by={(x['task_id'],x['kind']):x for x in result['scores']}
    for sid in range(1,13):
        ref=score_by[(sid,'reference')];cover=score_by[(sid,'cover')]
        text.append(f"| {sid} | {ref['bit_accuracy']:.6f} | {flag(ref['gs_detected'])} | {cover['bit_accuracy']:.6f} | {flag(cover['gs_detected'])} |")
    text+=[
           '', '## 全部逐任务结果','', '[含视觉观察的完整CSV](task_results_reviewed.csv) / [原始数值CSV](task_results.csv) / [完整复核JSON](verification_private.json)。MSE在重新读取最终PNG后计算RGB [0,1]像素差均值；PSNR=−10 log10(MSE)，参考是同任务载体，不是水印参考图。',
           '', '| 任务 | 方法 | 状态 | GS | BA | MSE | PSNR(dB) | 核心(s) | 进程(s) | 可见变化（模型辅助） |','|---:|---|---|---|---:|---:|---:|---:|---:|---|']
    for row in reviewed:
        observation=row['model_assisted_visual_observation'] or '无候选（工程失败）'
        text.append(f"| {row['task_id']} | {names[row['method']]} | {row['status']} | {flag(row['gs_detected'])} | {number(row['bit_accuracy'],6)} | {number(row['cover_mse_rgb01'],8)} | {number(row['cover_psnr_db'],3)} | {number(row['core_seconds'],3)} | {number(row['process_seconds'],3)} | {observation.replace('|','/')} |")
    text+=['','任务2 Jain：原进程在模型加载前因启动检查测得GPU利用率1%而失败；原退出码、日志与0.498398秒进程记录完整保留。本次未重跑。它不是Jain方法数值失效的证据。',
           '', '## 配对差异','', '方向均为delivery减imprint；比值为delivery/imprint。','', '| 任务 | BA差 | GS通过差 | 像素MSE比 | 核心时间比 |','|---:|---:|---:|---:|---:|']
    for p in result['paired_differences']:text.append(f"| {p['task_id']} | {p['bit_accuracy_difference']:+.6f} | {p['pass_difference']:+d} | {number(p['pixel_mse_ratio'],6)} | {number(p['core_time_ratio'],6)} |")
    by={(x['task_id'],x['method']):x for x in rows};paired_jain=[sid for sid in range(1,13) if by[(sid,'jain')]['status']=='completed']
    ba=sum(by[(sid,'jain')]['bit_accuracy']-by[(sid,'imprint')]['bit_accuracy'] for sid in paired_jain)/len(paired_jain)
    gain=sum(int(by[(sid,'jain')]['gs_detected'])-int(by[(sid,'imprint')]['gs_detected']) for sid in paired_jain)
    text+=['',f'Jain辅助共同任务比较仅覆盖同样可交付的11对（缺任务2）：相对Imprint平均BA差{ba*100:.4f}个百分点、普通GS通过数差{gain}。这是有缺失的辅助描述，不更改主比较去留规则。',
           '', '## 可见内容与全部图像','', '助手逐图观察属于模型辅助视觉检查，独立人工评审数为0。参考组存在拼图/风格化结果，部分载体未完全满足整物可见或坐姿要求；全部任务保留。具体观察与图像哈希见[参考/载体记录](control_visual_observations.json)和[候选记录](candidate_visual_observations.json)。以下缩略图用于总览，逐任务链接提供原始512×512 PNG。']
    text+=['',observed['overall_observation']]
    for group in range(4):text+=['',f'![任务{group*3+1}–{group*3+3}，依次为参考、载体、Imprint、Jain、delivery](contact_{group}.png)']
    text+=['','| 任务 | 参考 | 载体 | Imprint | Jain | delivery |','|---:|---|---|---|---|---|']
    for sid in range(1,13):
        links=[f'[PNG](../../{run}/attack_inputs/{sid}/{kind}.png)' for kind in ('reference','cover')]
        links += ['失败，无图片' if by[(sid,m)]['status']=='failed' else f'[PNG](../../{run}/attack_outputs/{sid}/{m}/candidate.png)' for m in ('imprint','jain','delivery')]
        text.append('| '+str(sid)+' | '+' | '.join(links)+' |')
    text+=['','## 实现、资源与边界','',
           '代理为Manojb/stable-diffusion-2-1-base（0094d483a120f3f33dafbd187ea4aa60d10de75c），目标为stabilityai/stable-diffusion-xl-base-1.0（462165984030d82259a11f4367a4eed129e94a7b）；FP32、512×512、官方DDIM。生成50步/CFG7.5，反演50步/空提示词/CFG1。普通GS判定严格BA>0.70703125，256消息位、64重复、每参考独立密钥/nonce/消息。',
           '12张水印参考由目标SDXL生成，12张无水印载体由代理SD2.1生成（原prepare.py及每个准备批次summary.json记录）。本组没有真实照片载体、额外生成器或未见确认集；四组提示词各三次重复不代表广泛内容覆盖。',
           'Imprint保持原生10次Adam更新、学习率0.01；Jain为共享代理适配的447次原参数状态更新。delivery同样10次更新，把连续VAE解码→截断→再编码纳入反演MSE优化，并以分段链式反传降低显存；优化中不含8位量化。最终检测均读取已封存PNG，未使用目标分数筛选候选或调参。',
           f"原始run加接续run合计45次模型工作进程启动、44次成功和1次加载前失败，记录的总进程墙钟时间为{result['model_process_seconds']:.6f}秒。它包含加载/检查/导出，不是GPU内核时间。继承文件没有重复记账；完整执行路径和SHA见复核JSON。",
           'r4修复仅涉及资源等待、严格连续空闲检查、证据继承和失败项保留；原生数值代码未修改。只使用249上获准的GPU0–2、逐进程UUID核对、单卡串行；无新模型下载。原12任务、随机种子、阈值与科学规则保持冻结。',
           '缺失项处理的定向源码检查：官方commit ca68950cd7b53b8438a49580f134b2a0db28d778的utils/pipe/SDXL_provider.py:7继承PipeProvider，utils/pipe/pipe_provider.py:155–156使用VAE后验均值。跳过没有候选的Jain任务不会通过VAE后验采样推进后续图像的随机序列；该检查没有新增模型调用。',
           '目标密钥/消息等材料留在服务器评估端；原始目标噪声、RNG和反演只作评估证据，不进入攻击接口。共享OS账号仍不构成权限隔离。完整几何/SemBind接受保持unknown，普通GS通过不能替代它。',
           '59个消息分数的独立解密复核在服务器CPU上使用评估端私有材料完成。公开档案可复核哈希、像素、时间与汇总统计；公开档案不包含水印密钥/消息，不能声称本机公开数据独立完成了相同的解密复核。',
           '', '## 研究决定与下一项','',observed['research_decision_text'],'',observed['next_decisive_work']]
    path=report/'report.md'
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(text)+'\n')
    print(path)

if __name__=='__main__':main(*sys.argv[1:])
