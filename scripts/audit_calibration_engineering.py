"""Audit split, source/stage hashes, cal-only threshold and benign source-level outcomes."""
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
from PIL import Image
from runtime_provenance import array_binding,file_sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--csi-code',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();root=Path(args.run)
    sys.path.insert(0,args.csi_code)
    from csi.schemes.seal import SealCore
    from csi.types import Key
    cfg=json.loads((root/'inputs/sd15_clip_calibration.json').read_text())
    core=SealCore(k=1024,b=7,t_patch=2.0);key=Key(seed=42)
    sources=cfg['sources'];calids=[s['id'] for s in sources if s['split']=='calibration'];testids=[s['id'] for s in sources if s['split']=='test']
    assert len(calids)==len(testids)==6 and not set(calids)&set(testids)
    assert len({s['family'] for s in sources})==len({s['seed'] for s in sources})==12
    assert not {s['seed'] for s in sources}&{2026100801,2026100802,2026100803,2026100821}
    checked=0;frozen={}
    for phase in ('prepare','calibration','test'):
        folder=root/phase;frozen[phase]=json.loads((folder/'frozen.json').read_text())
        fr=frozen[phase];rt=json.loads((folder/'runtime.json').read_text())
        assert fr['config']==cfg and fr['config_sha256']==file_sha(root/'inputs/sd15_clip_calibration.json')
        assert fr['script_sha256']==file_sha(root/'inputs/sd15_clip_calibration.py')
        assert fr['helper_sha256']==file_sha(root/'inputs/runtime_provenance.py')
        assert fr['logical_gpu']==0 and fr['preflight']['cuda_visible_devices']==cfg['physical_gpu_uuid']
        assert json.loads((folder/'exit_status.json').read_text())['exit_code']==0
        assert rt['weights_downloaded_bytes']==0
        for name,digest in rt['file_hashes'].items():assert file_sha(folder/name)==digest;checked+=1
    review=json.loads((root/'prepare/visual_review.json').read_text())
    assert review['reviewed_before_scoring'] and review['all_benign_facts_unchanged']
    assert len(review['image_hashes'])==60 and review['scores_available_at_review'] is False
    for phase in ('calibration','test'):
        assert frozen[phase]['visual_review_sha256']==file_sha(root/'prepare/visual_review.json')
        assert review['reviewed_utc']<=frozen[phase]['started_utc']
    for name,digest in review['image_hashes'].items():assert file_sha(root/'prepare'/name)==digest
    safety=json.loads((root/'prepare/safety_outputs.json').read_text())
    assert len(safety)==24 and not any(any(r['nsfw_content_detected']) for r in safety)
    registrations={}
    for s in sources:
        a=np.load(root/'prepare'/(s['id']+'_registration.npz'),allow_pickle=False)
        assert np.array_equal(core.noise_from_embedding(a['draft_feature'],key),a['registered_z'])
        registrations[s['id']]=a['registered_z']
    scores={};max_delta=0.;stored={}
    for phase,ids in [('calibration',calids),('test',testids)]:
        rows=json.loads((root/phase/'scores.json').read_text());scores[phase]=rows
        variants=cfg['benign_variants']+(['unmarked'] if phase=='test' else [])
        assert {(r['source'],r['variant']) for r in rows}=={(sid,v) for sid in ids for v in variants}
        assert len(rows)==len(ids)*len(variants)
        for sid in ids:
            stored[sid]=np.load(root/phase/(sid+'_arrays.npz'),allow_pickle=False)
            assert np.array_equal(stored[sid]['registered_z'],registrations[sid])
        for r in rows:
            sid=r['source'];v=r['variant'];a=stored[sid]
            image=root/'prepare'/(sid+'_'+v+'.png')
            assert file_sha(image)==r['input_image_sha256']
            assert array_binding(np.array(Image.open(image).convert('RGB')))==r['decoded_rgb']
            for suffix in ('feature','reference','recon','l2'):assert array_binding(a[v+'_'+suffix])==r['stage_bindings'][suffix]
            ref=core.noise_from_embedding(a[v+'_feature'],key)
            assert np.array_equal(ref,a[v+'_reference'])
            l2=core.patch_l2(a[v+'_recon'],ref);delta=float(np.abs(l2-a[v+'_l2']).max());assert delta<=1e-12;max_delta=max(delta,max_delta)
            count=int((l2<=2.0).sum());assert count==r['match_count'] and (count>=10)==r['unchecked_fallback_accepted']
            for field,actual in [('patch_l2_min',l2.min()),('patch_l2_median',np.median(l2)),('patch_l2_max',l2.max())]:assert abs(r[field]-actual)<=1e-12
    minima={sid:min(r['match_count'] for r in scores['calibration'] if r['source']==sid) for sid in calids}
    required=math.ceil(cfg['target_source_bundle_acceptance']*6)
    threshold=sorted(minima.values(),reverse=True)[required-1]
    op=json.loads((root/'calibration/operating_point.json').read_text())
    assert op['source_bundle_min_counts']==minima and op['count_threshold']==threshold
    assert op['cal_scores_sha256']==file_sha(root/'calibration/scores.json') and op['selected_without_test_scores']
    assert frozen['test']['operating_point']==op and frozen['test']['operating_point_sha256']==file_sha(root/'calibration/operating_point.json')
    assert op['frozen_utc']<=frozen['test']['started_utc']
    for r in scores['test']:
        ok=r['match_count']>=threshold
        assert r['calibrated_accepted']==ok and r['first_rejection_stage']==(None if ok else 'match_count_threshold')
    metrics={'count_threshold':threshold,'target_cal_source_bundle_acceptance':cfg['target_source_bundle_acceptance'],
        'degenerate_zero_threshold':threshold==0,'source_profiles':{},'benign_acceptance':{},'negative_controls':{}}
    for phase,ids in [('calibration',calids),('test',testids)]:
        rows=scores[phase];profiles={}
        for sid in ids:
            counts={r['variant']:r['match_count'] for r in rows if r['source']==sid and r['kind']=='benign_marked'}
            minimum=min(counts.values())
            profiles[sid]={'counts':counts,'minimum':minimum,'bundle_accepted':minimum>=threshold,'bundle_accepted_at_unchecked10':minimum>=10}
        metrics['source_profiles'][phase]=profiles
        variants={}
        for v in cfg['benign_variants']:
            selected=[r for r in rows if r['variant']==v]
            variants[v]={'calibrated_accepted':sum(r['match_count']>=threshold for r in selected),
                'unchecked10_accepted':sum(r['match_count']>=10 for r in selected),'sources':6}
        metrics['benign_acceptance'][phase]={'per_variant':variants,'source_bundle_accepted':sum(p['bundle_accepted'] for p in profiles.values()),
            'source_bundle_accepted_at_unchecked10':sum(p['bundle_accepted_at_unchecked10'] for p in profiles.values()),'sources':6}
    neg=[r for r in scores['test'] if r['variant']=='unmarked']
    metrics['negative_controls']['unmarked_draft']={'counts':{r['source']:r['match_count'] for r in neg},
        'accepted':sum(r['match_count']>=threshold for r in neg),'accepted_at_unchecked10':sum(r['match_count']>=10 for r in neg),'sources':6,
        'scope':'same-generator fixed draft negatives; correlated with registration; not broad FPR estimate'}
    wrong=[]
    for i,sid in enumerate(testids):
        donor=testids[(i+1)%len(testids)]
        l2=core.patch_l2(stored[sid]['original_recon'],stored[donor]['original_reference'])
        count=int((l2<=2.).sum())
        wrong.append({'source':sid,'reference_donor':donor,'count':count,'accepted':count>=threshold,
            'accepted_at_unchecked10':count>=10,'patch_l2':array_binding(l2)})
    metrics['negative_controls']['wrong_reference_diagnostic']={'rows':wrong,'accepted':sum(r['accepted'] for r in wrong),'sources':6,
        'scope':'CPU cyclic other-query reference mismatch; R1-style diagnostic, not native instance authentication or FPR'}
    result={'status':'passed','sources':12,'calibration_rows':30,'test_rows':36,'hash_bound_files_checked':checked,
        'max_reference_noise_delta':0.,'max_patch_l2_delta':max_delta,'cal_only_threshold_frozen_before_test':True,
        'metrics':metrics,'scope':'same-implementation CPU stored-stage recomputation and engineering split audit; no independent model reproduction or security estimate'}
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
