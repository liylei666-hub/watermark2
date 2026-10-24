import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image
repo=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
run=repo/'runs/29_quality_cost_20261020T000701Z'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
design=read(run/'design.json');assert design==read(repo/'protocols/29_quality_design.json')
analysis=read(run/'analysis.json');sealed=read(run/'results_sealed.json')
assert sha((run/'analysis.json').read_bytes())==sealed['analysis_sha256']
for name,h in sealed['executions'].items():
    p=run/name/'execution.json';assert sha(p.read_bytes())==h
    ex=read(p);assert ex['outcome']['completed'] and ex['outcome']['exit_code']==0
    for artifact,digest in ex['outcome']['artifacts'].items():assert sha((p.parent/artifact).read_bytes())==digest
seal=read(run/'candidates_sealed.json');assert len(seal['rows'])==32
assert read(run/'evaluate/execution.json')['started_at_utc']>seal['sealed_at_utc']
assert read(run/'endpoint_qualification.json')['qualified']
rows=[];errors=[];costs=[];linfs=[]
for sid in range(1,17):
    with Image.open(run/f'attack_inputs/{sid}/cover.png') as im:cover=np.asarray(im,dtype=np.int64)
    for kind in ('reference','cover','pixel50','pixel10'):
        folder=run/f'evaluate/{sid}_{kind}';metric=read(folder/'metrics.json')
        image=run/f'attack_inputs/{sid}/{kind}.png' if kind in ('reference','cover') else run/f'attack_{sid}_{kind}/candidate.png'
        assert sha(image.read_bytes())==metric['image']['sha256']
        assert sha((folder/'target_inverse.npy').read_bytes())==metric['inverse']['sha256']
        ba=metric['bit_accuracy'];assert 0<=ba<=1 and ba*256==int(ba*256) and metric['gs_detected']==(ba>design['gs_threshold'])
        row=dict(task_id=sid,kind=kind,bit_accuracy=ba,gs_detected=metric['gs_detected'],cover_mse_rgb01=None,core_seconds=None)
        if kind.startswith('pixel'):
            attack=run/f'attack_{sid}_{kind}';summary=read(attack/'summary.json');timing=summary['timing'];p=design['policy']
            f=read(attack/'candidate_frozen.json');assert f['image']==metric['image'] and sha((run/f'attack_inputs/{sid}/{kind}.json').read_bytes())==f['job_sha256']
            with Image.open(image) as im:delta=np.asarray(im,dtype=np.int64)-cover
            energy=int(np.sum(delta*delta));mse=energy/(65025*delta.size);linf=int(np.abs(delta).max());allowance=math.floor(p['mse_limit']*65025*delta.size)
            assert energy==summary['quality']['squared_byte_error']==allowance and linf<=p['linf_levels']
            core=sum(timing[k] for k in ('reference_and_cover_preparation_seconds','optimization_seconds','finalization_seconds'))
            assert abs(core-summary['core_seconds'])<1e-10 and .9*p['core_budget_seconds']<=core<=p['core_budget_seconds']
            row.update(cover_mse_rgb01=mse,core_seconds=core);costs.append(core);linfs.append(linf)
        old=next(r for r in analysis['rows'] if r['task_id']==sid and r['kind']==kind)
        if row['cover_mse_rgb01'] is not None:errors.append(abs(row['cover_mse_rgb01']-old['cover_mse_rgb01']))
        assert ba==old['bit_accuracy'] and row['gs_detected']==old['gs_detected'];rows.append(row)
by={(r['task_id'],r['kind']):r for r in rows}
diff=np.array([by[i,'pixel10']['bit_accuracy']-by[i,'pixel50']['bit_accuracy'] for i in range(1,17)])
rule=design['decision_rule'];rng=np.random.default_rng(rule['bootstrap_seed'])
interval=np.quantile(diff[rng.integers(0,16,size=(rule['bootstrap_resamples'],16))].mean(axis=1),[.025,.975]).tolist()
gates=dict(mean_gain=float(diff.mean())>=rule['minimum_mean_accuracy_gain'],interval_lower_positive=interval[0]>0,consistent_direction=int((diff>0).sum())>=rule['minimum_positive_pairs'])
decision='advance_quality_constrained_comparison_to_confirmation' if all(gates.values()) else 'close_fixed_short_efficiency_claim'
assert gates==analysis['decision']['gates'] and decision==analysis['decision']['decision']
assert interval==analysis['decision']['descriptive_paired_bootstrap_95_interval']
report=dict(status='passed',manifest_files=757,executions=len(sealed['executions']),planned_tasks=16,planned_candidates=32,delivered_candidates=32,evaluated_images=64,
    references_valid=sum(by[i,'reference']['gs_detected'] for i in range(1,17)),
    summary={m:dict(gs_passes=sum(by[i,m]['gs_detected'] for i in range(1,17)),denominator=16,mean_ba=float(np.mean([by[i,m]['bit_accuracy'] for i in range(1,17)]))) for m in ('pixel50','pixel10')},
    mean_difference=float(diff.mean()),positive_pairs=int((diff>0).sum()),ties=int((diff==0).sum()),bootstrap_95=interval,gates=gates,decision=decision,
    max_mse_readback_error=max(errors),core_seconds_range=[min(costs),max(costs)],linf_levels_range=[min(linfs),max(linfs)],
    private_decoder_rerun=False,score_validation='public sealed metrics binding, range, strict decision and arithmetic; private decryption not reproduced',
    new_model_experiments=0,source_git_ancestry='recorded stage29 SHAs unavailable from GitHub; byte hashes verified against runtime')
# report emitted to stdout; evidence remains read-only
print(json.dumps(report,indent=2))
