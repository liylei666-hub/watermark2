"""CPU-only reanalysis and provenance verification of stages 08 and partial 09."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import verify_archive as a
import analyze_target_roundtrip as t
import analyze_vae_roundtrip as v

def main():
    out={}
    for stage,module,run,report in [
        ('08',t,'08_target_roundtrip_20261016T014337Z','08_target_roundtrip'),
        ('09',v,'09_vae_roundtrip_20261016T015236Z','09_vae_roundtrip')]:
        rows,summary=module.analyze(ROOT/'runs'/run)
        assert rows==a.load(ROOT/'reports'/report/'per_sample.json')
        assert summary==a.load(ROOT/'reports'/report/'summary.json')
        files=a.load(ROOT/'provenance'/f'{stage}_remote_manifest.json')['files']
        for f in files:
            path=ROOT/f['path'];assert path.stat().st_size==f['bytes'] and a.sha(path)==f['sha256'],f['path']
        out[stage]=dict(completed_model_runs=summary['completed_model_processes'],
            real_target_tensors_checked=summary['completed_model_processes']*3,
            candidate_count=summary['candidate_count'],remote_transfer_files_checked=len(files),
            max_abs_cosine_readback_error=summary['max_abs_cosine_readback_error'],analysis_code_sha256=summary['analysis_code_sha256'])
    return out

if __name__=='__main__':print(json.dumps(main(),indent=2))
