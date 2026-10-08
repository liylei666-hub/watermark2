"""Audit persisted stages and exact mechanical image construction on CPU."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--run',required=True)
    ap.add_argument('--csi-code',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    root=Path(args.run)
    checked=0
    for phase in ('prepare','score'):
        folder=root/phase
        runtime=json.loads((folder/'runtime.json').read_text())
        for name,digest in runtime['file_hashes'].items():
            assert sha(folder/name)==digest,name
            checked+=1
        assert json.loads((folder/'exit_status.json').read_text())['exit_code']==0
        frozen=json.loads((folder/'frozen.json').read_text())
        assert frozen['config']['split']=='development'
        assert frozen['logical_gpu']==0 and frozen['config']['physical_gpu']==7
        assert runtime['weights_downloaded_bytes']==0
    frozen=json.loads((root/'score/frozen.json').read_text())
    cfg=frozen['config']
    assert cfg['source_count']==1 and cfg['draft_seed']==2026100821
    assert cfg['core']=={'k':1024,'b':7,'t_patch':2.0,'fallback_matches':10.0}
    for phase in ('prepare','score'):
        fr=json.loads((root/phase/'frozen.json').read_text())
        assert sha(root/'inputs/sd15_clip_mechanical.json')==fr['config_sha256']
        assert sha(root/'inputs/sd15_clip_mechanical.py')==fr['script_sha256']
    review=json.loads((root/'variants/visual_review.json').read_text())
    assert sha(root/'variants/visual_review.json')==frozen['visual_review_sha256']
    assert review==frozen['visual_review']
    assert review['reviewed_utc']<=frozen['started_utc']
    assert review['scores_available_at_review'] is False
    assert review['valid_fact_change'] and review['control_fact_unchanged']
    recipe=json.loads((root/'variants/recipe.json').read_text())
    assert sha(root/'variants/recipe.json')==review['recipe_sha256']
    assert sha(root/'variants/region_mask.png')==recipe['mask_sha256']
    assert sha(root/'inputs/prepare_mechanical_control.py')==recipe['constructor_sha256']
    assert sha(root/'prepare/source.png')==recipe['source_sha256']
    for name,digest in review['image_hashes'].items():
        assert sha(root/'variants'/name)==digest
        checked+=1
    # Recreate masks, source/control/edit, and equal JPEG/resize processing.
    with tempfile.TemporaryDirectory() as tmp:
        regenerated=Path(tmp)/'variants'
        cmd=[sys.executable,str(root/'inputs/prepare_mechanical_control.py'),
             '--source',str(root/'prepare/source.png'),'--config',str(root/'inputs/sd15_clip_mechanical.json'),
             '--bbox',*[str(x) for x in recipe['bbox_xyxy']],'--output',str(regenerated)]
        subprocess.run(cmd,check=True,capture_output=True,text=True)
        construction_files=list(review['image_hashes'])+['region_mask.png','source_jpeg70.jpg','control_jpeg70.jpg','edit_jpeg70.jpg']
        for name in construction_files:
            assert sha(regenerated/name)==sha(root/'variants'/name),name
    sys.path.insert(0,args.csi_code)
    from csi.schemes.seal import SealCore
    from csi.types import Key
    core=SealCore(k=1024,b=7,t_patch=2.0);key=Key(seed=42)
    registration=np.load(root/'prepare/registration.npz',allow_pickle=False)
    assert np.array_equal(core.noise_from_embedding(registration['draft_feature'],key),registration['registered_z'])
    arrays=np.load(root/'score/arrays.npz',allow_pickle=False)
    assert np.array_equal(arrays['registered_z'],registration['registered_z'])
    rows=json.loads((root/'score/scores.json').read_text())
    assert len(rows)==9
    assert {(r['condition'],r['processing']) for r in rows}=={
        (c,p) for c in ('source','control','edit') for p in ('original','jpeg70','resize05')}
    delta=0.0
    for row in rows:
        name=row['condition']+'_'+row['processing']
        ref=core.noise_from_embedding(arrays[name+'_feature'],key)
        assert np.array_equal(ref,arrays[name+'_reference'])
        l2=core.patch_l2(arrays[name+'_recon'],ref)
        d=float(np.max(np.abs(l2-arrays[name+'_l2'])));delta=max(delta,d);assert d<=1e-12
        count=int((l2<=2.0).sum());accepted=count>=10
        assert count==row['match_count'] and accepted==row['fallback_accepted']
        assert row['first_rejection_stage']==(None if accepted else 'match_count_threshold')
        assert core.match_count(arrays[name+'_recon'],arrays['registered_z'])==row['registration_reference_matches_oracle_only']
        for field,actual in [('patch_l2_min',l2.min()),('patch_l2_median',np.median(l2)),('patch_l2_max',l2.max())]:
            assert abs(row[field]-actual)<=1e-12
        assert row['image_sha256']==review['image_hashes'][name+'.png']
    result={'status':'passed','development_sources':1,'valid_mechanical_pairs':1,
        'detector_rows':9,'hash_bound_files_checked':checked,'recreated_construction_files':len(construction_files),
        'max_reference_noise_delta':0.0,'max_patch_l2_delta':delta,
        'review_before_scoring':True,'operating_point':'unchecked unchanged fallback',
        'scope':'exact CPU image construction and persisted-stage recomputation; no rerun of CLIP or inversion'}
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
