"""CPU readback of completed paired delivery; no model loading or candidate changes."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import datetime,json,sys
from pathlib import Path
import numpy as np
from common import c,IDS,METHODS,tasks,cast_input,bundle,summary


def verify(root,private_check=False):
    root=Path(root);cfg=c.read(root/'protocols/25_delivery_runtime.json');folder=root/cfg['run_dir']
    status=c.read(folder/'status.json')
    if status.get('completed') is not True or status['model_processes_started']!=4:raise ValueError('Incomplete study')
    sealed=c.read(folder/'candidates_sealed.json');bundle(folder/'attack_inputs',sealed['input_seal_sha256'],'attack_inputs')
    bundle(folder/'evaluation_images',sealed['image_seal_sha256'],'evaluation_images')
    if sealed['candidates']!=16 or sealed['target_calls_before_seal']!=0:raise ValueError('Candidate set changed')
    records=[];elapsed=0
    for phase in ('generate','evaluate'):
        for batch in (0,1):
            out=folder/(phase+'_'+str(batch));ex=c.read(out/'execution.json');cmd=c.read(out/'command.json')
            if ex['exit_code']!=0 or ex['timed_out'] or not ex['completed'] or ex['model_processes_started']!=1:raise ValueError('Child incomplete')
            if cfg['allowed_gpu_uuids'].get(str(ex['gpu_index']))!=ex['gpu_uuid'] or cmd['gpu_uuid']!=ex['gpu_uuid']:raise ValueError('Device association changed')
            gate=[json.loads(line) for line in (out/'preflight.jsonl').read_text().splitlines()]
            if gate[-1]['event']!='idle_verified':raise ValueError('No completed idle gate')
            for sample in gate[-4:-1]:
                g=sample['row']
                if sample['event']!='sample' or g[:3]!=[str(ex['gpu_index']),ex['gpu_uuid'],'NVIDIA GeForce RTX 3090'] or int(g[4])>50 or int(g[5])!=0 or sample['compute_apps']:raise ValueError('Idle evidence mismatch')
            device=c.read(out/'device_preimport.json')
            if len(device['rows'])!=1 or device['compute_apps'] or device['rows'][0][:3]!=[str(ex['gpu_index']),ex['gpu_uuid'],'NVIDIA GeForce RTX 3090'] or int(device['rows'][0][3])>50 or int(device['rows'][0][4])!=0:raise ValueError('Pre-import GPU evidence mismatch')
            if phase=='evaluate' and datetime.datetime.fromisoformat(ex['started_at_utc'])<=datetime.datetime.fromisoformat(sealed['sealed_at_utc']):raise ValueError('Evaluation preceded seal')
            expected_runtime='attack' if phase=='generate' else 'evaluation'
            if cmd['runtime_sha256']!=c.sha(root/('protocols/25_delivery_'+expected_runtime+'_runtime.json')):raise ValueError('Runtime changed')
            marker='COMPLETED_DELIVERY_GENERATION' if phase=='generate' else 'COMPLETED_DELIVERY_EVALUATION'
            if marker not in (out/'stdout.log').read_text() or not c.read(out/'summary.json')['completed']:raise ValueError('Completion evidence missing')
            elapsed+=ex['elapsed_seconds'];records.append(dict(path=(out/'execution.json').relative_to(root).as_posix(),sha256=c.sha(out/'execution.json'),gpu_process_wall_seconds=ex['elapsed_seconds'],exit_code=0))
    decoded_count=0;rows=[];image_comparisons=[]
    if private_check:
        from gs_batch import private_module
        from verify_message_scores import decode
        private=private_module();ev=c.read(root/'protocols/25_delivery_evaluation_runtime.json')
    for i,sid in enumerate(IDS):
        row={'sample_id':sid};pair_dirs=[]
        for method in METHODS:
            old=cfg['inputs'][sid][method];path=root/old['path']
            if c.sha(path)!=old['sha256']:raise ValueError('Original estimator input changed')
            expected=cast_input(np.load(path,allow_pickle=False));actual=folder/'attack_inputs'/(sid+'_'+method+'.npy')
            if not np.array_equal(expected,np.load(actual,allow_pickle=False)):raise ValueError('Generation input mismatch')
            gen=folder/('generate_'+str(i//4))/(sid+'_'+method);rec=c.read(gen/'record.json');pair_dirs.append(gen)
            if rec['input']!=c.array_record(actual) or rec['task']!=tasks()[i] or rec['method']!=method:raise ValueError('Task identity changed')
            if rec['image']!=c.png_record(gen/'candidate.png'):raise ValueError('Candidate changed')
            if c.sha(gen/'candidate.png')!=c.sha(folder/'evaluation_images'/(sid+'_'+method+'.png')):raise ValueError('Evaluated wrong candidate')
        if c.read(pair_dirs[0]/'rng_before_generation.json')!=c.read(pair_dirs[1]/'rng_before_generation.json'):raise ValueError('Paired Python/numpy RNG differs')
        with np.load(pair_dirs[0]/'rng_before_generation.npz',allow_pickle=False) as a,np.load(pair_dirs[1]/'rng_before_generation.npz',allow_pickle=False) as b:
            if a.files!=b.files or not all(np.array_equal(a[k],b[k]) for k in a.files):raise ValueError('Paired RNG arrays differ')
        ref=folder/'evaluation_images'/(sid+'_reference.png')
        if c.sha(ref)!=cfg['inputs'][sid]['reference']['sha256']:raise ValueError('Reference changed')
        if private_check:raw=private.load(Path(ev['private_folder']),sid,ev['identities'][sid])
        for method in ('reference',)+METHODS:
            out=folder/('evaluate_'+str(i//4))/(sid+'_'+method);metric=c.read(out/'metrics.json')
            if metric['image']!=c.png_record(folder/'evaluation_images'/(sid+'_'+method+'.png')) or metric['inverse']!=c.array_record(out/'inverse.npy'):raise ValueError('Evaluation evidence changed')
            if metric['sample_id']!=sid or metric['method']!=method:raise ValueError('Metric identity changed')
            score=metric['bit_accuracy']
            if metric['gs_detected']!=(score>.70703125):raise ValueError('Strict decision mismatch')
            if private_check:
                if decode(np.load(out/'inverse.npy',allow_pickle=False),raw)!=score:raise ValueError('Independent message decoding mismatch')
                decoded_count+=1
            row[method]=score
        rows.append(row)
        from PIL import Image
        pixels={m:np.asarray(Image.open(folder/'evaluation_images'/(sid+'_'+m+'.png'))) for m in ('reference',)+METHODS}
        image_comparisons.append(dict(sample_id=sid,baseline_equals_reference=bool(np.array_equal(pixels['baseline'],pixels['reference'])),
            corrected_equals_reference=bool(np.array_equal(pixels['corrected'],pixels['reference'])),baseline_equals_corrected=bool(np.array_equal(pixels['baseline'],pixels['corrected']))))
    result=dict(rows=rows,summary=summary(rows))
    if result!=c.read(folder/'results.json'):raise ValueError('Stored summary differs from raw scores')
    return dict(verified=True,checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),result=result,model_process_seconds=elapsed,
        execution_records=records,official_scores_independently_decoded=decoded_count,private_material_exported=False,
        candidate_pairs=8,images_checked=24,paired_rng_equal=True,input_casts_verified=16,
        image_equalities=image_comparisons,models_loaded=False,gpu_used=False)

if __name__=='__main__':print(json.dumps(verify(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='--private-check'),indent=2))
