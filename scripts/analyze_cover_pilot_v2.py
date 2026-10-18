"""CPU readback of a complete sealed pilot; no model imports or candidate selection."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only analysis')
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent/'cover_pilot'))
import contract as c
import bundle as b


def pixels(path):
    with Image.open(path) as im:
        if im.mode!='RGB' or im.size!=(512,512):raise ValueError('Unexpected image')
        return np.asarray(im).copy()


def analyze(root):
    root=Path(root).resolve()
    status=c.read(root/'status.json')
    if status.get('status')!='completed' or status.get('completed') is not True:
        raise ValueError('Pilot has not completed; report engineering state separately')
    c.verify_delivery(root,root/'attack_plan.json');queue=b.evaluation_queue(root,root/'attack_plan.json')
    results=c.read(root/'evaluator_results/summary.json')
    if results['delivery_seal_sha256']!=c.sha(root/'delivery_sealed.json'):raise ValueError('Evaluator used a different seal')
    if results['threshold']!=181/256 or results['decision']!='bit_accuracy > threshold':raise ValueError('Wrong decision rule')
    rows=results['rows']
    if [x['input'] for x in rows]!=queue:raise ValueError('Evaluated inputs differ from the fixed queue')
    expected={'evaluator_private/reference/execution.json','evaluator_private/cover/execution.json','evaluator_results/execution.json'}
    expected.update('attack_outputs/'+str(task)+'/'+method+'/execution.json' for task in [1,2,3] for method in c.METHODS)
    actual={p.relative_to(root).as_posix() for p in root.rglob('execution.json')}
    if actual!=expected:raise ValueError('Execution inventory differs from the nine fixed children')
    executions=[]
    for name in sorted(expected):
        path=root/name
        d=c.read(path)
        if d['exit_code']!=0 or d['completed'] is not True or d['timed_out']:raise ValueError('Child not successful')
        if not math.isfinite(d['elapsed_seconds']) or d['elapsed_seconds']<=0:raise ValueError('Invalid elapsed time')
        executions.append(dict(path=path.relative_to(root).as_posix(),sha256=c.sha(path),seconds=d['elapsed_seconds'],gpu_index=d['gpu_index'],gpu_uuid=d['gpu_uuid']))
    if len(executions)!=9:raise ValueError('Expected nine model process records')
    analyzed=[];lookup={(row['input']['task_id'],row['input']['kind']):row for row in rows}
    for row in rows:
        inp=row['input'];result=row['result'];task=inp['task_id'];kind=inp['kind'];ba=result['bit_accuracy']
        if not math.isfinite(ba) or not 0<=ba<=1 or result['gs_detected']!=(ba>181/256):raise ValueError('GS decision inconsistency')
        arrpath=root/'evaluator_results'/str(task)/kind/'target_inverse.npy'
        if c.sha(arrpath)!=result['target_inverse']['sha256']:raise ValueError('Inverse hash mismatch')
        arr=np.load(arrpath,allow_pickle=False)
        if arr.shape!=(1,4,64,64) or arr.dtype!=np.float32 or not np.isfinite(arr).all():raise ValueError('Invalid target inverse')
        if kind not in c.METHODS:continue
        image=pixels(root/inp['path']);cover=pixels(root/lookup[(task,'cover')]['input']['path']);ref=pixels(root/lookup[(task,'reference')]['input']['path'])
        diff=image.astype(np.float64)-cover.astype(np.float64);mse=float(np.mean((diff/255)**2))
        summary=c.read(root/'attack_outputs'/str(task)/kind/'summary.json');timing=summary['timing']
        if summary['task_id']!=task or summary['method']!=kind or summary['candidate']['candidate']['sha256']!=inp['sha256']:
            raise ValueError('Attack summary binding mismatch')
        core=timing['reference_encoding_and_optimization_seconds'] if kind=='jain' else timing['reference_and_cover_preparation_seconds']+timing['optimization_seconds']
        if kind=='jain':
            x=np.load(root/'attack_outputs'/str(task)/kind/'final_float.npy',allow_pickle=False)
            if x.shape!=(1,3,512,512) or x.dtype!=np.float32 or not np.isfinite(x).all():raise ValueError('Invalid floating candidate')
            expected=(np.clip(x/2+.5,0,1)*255).astype(np.uint8)[0].transpose(1,2,0)
            if not np.array_equal(image,expected):raise ValueError('Jain serialized pixels do not match saved floating output')
        analyzed.append(dict(task_id=task,method=kind,candidate_sha256=inp['sha256'],bit_accuracy=ba,gs_detected=result['gs_detected'],
            png_to_cover_mse_0_1=mse,png_to_cover_psnr_db=None if mse==0 else -10*math.log10(mse),identical_to_cover=bool(np.array_equal(image,cover)),
            png_to_cover_linf_8bit=int(np.abs(diff).max()),identical_to_reference=bool(np.array_equal(image,ref)),
            core_seconds=core,timing=timing,reference_bit_accuracy=lookup[(task,'reference')]['result']['bit_accuracy'],
            cover_bit_accuracy=lookup[(task,'cover')]['result']['bit_accuracy'],content_pass=None,full_defense_accepted=None,joint_success=None))
    stats={m:dict(planned_tasks=3,candidates=3,ordinary_gs_pass=sum(x['gs_detected'] for x in analyzed if x['method']==m),
        content_pass_count=None,joint_success_count=None,full_defense_accept_count=None) for m in c.METHODS}
    result=dict(status='readback_verified',rows=analyzed,descriptive_counts=stats,executions=executions,
        model_processes=9,model_process_seconds=sum(x['seconds'] for x in executions),
        target_inverse_files_verified=12,gs_score_cpu_recomputed=False,
        gs_score_note='Detector values read from official evaluator outputs; threshold booleans recomputed. Separate retained-latent CPU score check may be added.',
        analysis_gpu_used=False,analysis_models_loaded=False,data_role='development_pilot',identity_count=1,
        candidate_seal_sha256=c.sha(root/'delivery_sealed.json'),analysis_code_sha256=c.sha(__file__))
    return result


def main(root,output):
    result=analyze(root)
    c.write(output,result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    main(args.root,args.output)
