"""Independent CPU audits of real-run artifacts; no model imports or GPU access."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import csv,json,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from stage02.core import dump,sha256,validate_manifest,HOST_GPUS,normalize
out=root/'outputs/stage02';checks={}
manifest=json.loads((root/'data/stage02/manifest.json').read_text());validate_manifest(manifest)
checks['group_hash_donor_near_duplicate_split_validation']=True
images={x['id']:x for x in manifest['images']}
from PIL import Image
for x in images.values():
    assert sha256(root/x['path'])==x['sha256']
    im=Image.open(root/x['path']);assert im.format=='PNG' and im.mode=='RGB'
checks['all_images_real_RGB_PNG_and_hashes']=True
for p in manifest['pairs']:
    if p['category']=='A' and p['params']['kind']=='jpeg':
        assert not np.array_equal(np.asarray(Image.open(root/images[p['left']]['path'])),np.asarray(Image.open(root/images[p['right']]['path'])))
checks['JPEG_encoding_changes_pixels']=True
metrics=json.loads((out/'metrics.json').read_text());thresholds=json.loads((out/'thresholds.json').read_text())['thresholds']
assert metrics['threshold_file_sha256']==sha256(out/'thresholds.json')
rows=list(csv.DictReader((out/'pair_scores.csv').open()))
for m,t in thresholds.items():
    cal=sorted(float(r[m]) for r in rows if r['category']=='A' and r['split']=='smoke_calibration')
    assert cal[int(.05*len(cal))]==t
    for cat,key,reject in [('A','test_frr',True),('D','test_D_false_accept',False),('C_proxy','test_C_proxy_false_accept',False)]:
        selected=[r for r in rows if r['category']==cat and r['split']=='smoke_test']
        count=sum((float(r[m])<t) if reject else (float(r[m])>=t) for r in selected)
        assert count==metrics['methods'][m][key]['count'] and len(selected)==metrics['methods'][m][key]['total']
checks['independent_threshold_metrics_recomputation']=True
bindings=json.loads((out/'gpu_binding.json').read_text())['workers']
for b in bindings:
    assert b['exit_code']==0 and b['torch_visible_count']==1
    assert HOST_GPUS[b['host_index']]==b['CUDA_VISIBLE_DEVICES']==b['driver']['uuid']
checks['each_actual_worker_single_authorized_UUID']=True
for p in ['worker_clip_sscd.json','worker_dinov2.json']:
    for m,r in json.loads((out/p).read_text()).items():
        assert r['status']=='complete' and r['repeat_max_abs']<=1e-5 and r['self_max_error']<=1e-5
        assert r['binding_evidence'] and r['batch_size']==1
        assert sha256(root/r['model']['path'])==r['model']['sha256']
        for d in json.loads((out/f'features_{m}.json').read_text()).values():
            a=np.load(root/d['path'],allow_pickle=False)
            assert a.shape==tuple(r['feature_shape']) and np.isfinite(a).all() and np.allclose(np.linalg.norm(a,axis=-1),1,atol=1e-5)
            assert a.nbytes==d['bytes'] and (root/d['path']).stat().st_size==d['file_bytes']
checks['real_weights_repeat_dimensions_norm_finiteness_bytes']=True
dino=json.loads((out/'features_dinov2.json').read_text());glob=json.loads((out/'features_dinov2_global.json').read_text())
for i,x in glob.items():
    a=np.load(root/x['path']);b=np.load(root/dino[i]['path'])
    assert a.nbytes==x['bytes'] and np.allclose(a,normalize(b.mean(axis=0)),atol=1e-6)
checks['DINO_global_derived_from_shared_patch_cache']=True
for r in rows:
    if r['category']=='SELF':
        assert all(abs(float(r[m])-1)<1e-5 for m in thresholds)
checks['all_original_self_pairs_near_one_separate_from_A']=True
before=json.loads((out/'gpu_before.json').read_text())['processes'];after=json.loads((out/'gpu_after.json').read_text())['processes']
def process_ids(text):
    return {int(line.split(',')[1].strip()) for line in text.splitlines()[1:] if line.strip()}
prior_pids=process_ids(before);final_pids=process_ids(after)
assert prior_pids.issubset(final_pids), 'a pre-existing process is absent in the final snapshot; investigate its lifecycle'
checks['preexisting_compute_PIDs_present_before_after']=True
dump(out/'runtime_checks.json',dict(status='passed',exit_code=0,checks=checks,scope='pre/post presence and own-worker records; not a continuous monitor of all server processes'))
print(json.dumps(checks,indent=2))
