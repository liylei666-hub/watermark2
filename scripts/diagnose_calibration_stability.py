"""Post-hoc stored-stage stability decomposition, using no new GPU inference."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from runtime_provenance import array_binding

def cosine(a,b):
    return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--csi-code',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();root=Path(args.run)
    sys.path.insert(0,args.csi_code)
    from csi.schemes.seal import SealCore
    from csi.types import Key
    core=SealCore(k=1024,b=7,t_patch=2.0);key=Key(seed=42)
    cfg=json.loads((root/'inputs/sd15_clip_calibration.json').read_text());rows=[]
    for source in cfg['sources']:
        sid=source['id'];phase=source['split'];a=np.load(root/phase/(sid+'_arrays.npz'),allow_pickle=False)
        draft=a['draft_feature'];registered=a['registered_z'];original=a['original_feature'];original_recon=a['original_recon']
        registered_ids=core.bucket_ids(draft,key);original_ids=core.bucket_ids(original,key)
        for variant in cfg['benign_variants']:
            query=a[variant+'_feature'];recon=a[variant+'_recon'];reference=a[variant+'_reference']
            qids=core.bucket_ids(query,key);same=qids==registered_ids
            oracle_l2=core.patch_l2(recon,registered);oracle_close=oracle_l2<=2.0
            native_l2=core.patch_l2(recon,reference);native_close=native_l2<=2.0
            # Exact agreement means identical keyed patch; check this decomposition.
            assert np.array_equal(native_close[same],oracle_close[same])
            native_count=int(native_close.sum())
            shared_close=int((same&oracle_close).sum())
            unshared_close=int((~same&native_close).sum())
            assert native_count==shared_close+unshared_close
            rows.append({'source':sid,'split':phase,'variant':variant,
                'native_matches':native_count,'oracle_registered_matches':int(oracle_close.sum()),
                'query_vs_draft_cosine':cosine(query,draft),'query_vs_original_cosine':cosine(query,original),
                'query_vs_draft_same_buckets':int(same.sum()),
                'query_vs_original_same_buckets':int((qids==original_ids).sum()),
                'registered_reconstruction_close_and_shared_bucket':shared_close,
                'close_under_different_bucket':unshared_close,
                'reconstruction_vs_registered_rmse':float(np.sqrt(np.mean((recon-registered)**2))),
                'reconstruction_vs_original_rmse':float(np.sqrt(np.mean((recon-original_recon)**2))),
                'oracle_patch_l2_min':float(oracle_l2.min()),'oracle_patch_l2_median':float(np.median(oracle_l2)),
                'oracle_l2_binding':array_binding(oracle_l2)})
    result={'kind':'posthoc_diagnostic','fixed_patch_tolerance':2.0,'rows':rows,
        'scope':'saved-array decomposition with oracle registered latent; no new encoding/inversion, no threshold selection or independent causal proof'}
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps([r for r in rows if r['source']=='c04'],indent=2))
if __name__=='__main__':main()
