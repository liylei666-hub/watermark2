"""Independent diagnostic, not the missing author's implementation."""
import os
import json
from pathlib import Path
import numpy as np
from recording import sha, write_json

def independent_global_cosine_diagnostic(z, zhat):
    z, zhat = np.asarray(z), np.asarray(zhat)
    if z.shape != zhat.shape or z.ndim != 4 or z.shape[0] != 1:
        raise ValueError("Expected identical [1,C,H,W] shapes")
    if z.dtype.kind not in "fiu" or zhat.dtype.kind not in "fiu":
        raise ValueError("Expected real numeric tensors")
    if not np.isfinite(z).all() or not np.isfinite(zhat).all():
        raise ValueError("Non-finite input")
    a,b=z.astype(np.float64).reshape(-1),zhat.astype(np.float64).reshape(-1)
    na,nb=np.linalg.norm(a),np.linalg.norm(b)
    if not np.isfinite(na) or not np.isfinite(nb) or na==0 or nb==0:
        raise ValueError("Invalid norm")
    result=float(np.dot(a,b)/(na*nb))
    if not np.isfinite(result): raise ValueError("Non-finite cosine")
    return result

def main(run):
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    d=Path(run)/"evaluator_only"
    frozen=json.loads((d/"candidate_frozen.json").read_text())
    assert sha(frozen["path"])==frozen["sha256"]
    manifest=json.loads((d/"tensor_manifest.json").read_text())
    arrays={}
    for name,record in manifest["tensors"].items():
        assert sha(record["path"])==record["sha256"]
        assert sha(record["image_path"])==record["image_sha256"]
        a=np.load(record["path"],allow_pickle=False)
        assert str(a.dtype)==record["dtype"]=="float32" and list(a.shape)==record["shape"]
        arrays[name]=a
    ref=independent_global_cosine_diagnostic(arrays["target_original_wm_zT"],arrays["target_inverted_reference_zT"])
    forged=independent_global_cosine_diagnostic(arrays["target_original_wm_zT"],arrays["target_inverted_forged_zT"])
    write_json(d/"diagnostic.json",dict(implementation="independent_global_cosine_diagnostic",
        paper="arXiv:2606.29807v1 Definition 4.5 / Remark 4.7",dtype="float64",device="cpu",
        gcos_reference=ref,gcos_forged=forged,gcos_gap_reference_minus_forged=ref-forged,
        candidate_frozen_sha256=frozen["sha256"],geometry_threshold=None,geometry_accepted=None))
if __name__=="__main__":
    import sys
    main(sys.argv[1])

