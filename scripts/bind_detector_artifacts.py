"""Supplementary artifact bindings; this is not independent model re-execution."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
from runtime_provenance import file_sha,array_binding

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    records=[]
    runs=[('smoke',root/'reports/sd15_clip_smoke',root/'reports/sd15_clip_smoke'),
          ('prompt_edit',root/'reports/sd15_clip_smoke/followup',root/'reports/sd15_clip_smoke/followup'),
          ('mechanical',root/'reports/mechanical_development/score',root/'reports/mechanical_development/variants')]
    for label,run,images in runs:
        frozen=json.loads((run/'frozen.json').read_text())
        arrays=np.load(run/'arrays.npz',allow_pickle=False)
        rows=json.loads((run/'scores.json').read_text())
        for row in rows:
            if label=='mechanical':prefix=row['condition']+'_'+row['processing']
            else:prefix=row['source']+'_'+row['variant']
            p=images/(prefix+'.png')
            records.append({'run':label,'image':str(p.relative_to(root)),
                'image_sha256':file_sha(p),'decoded_rgb':array_binding(np.array(Image.open(p).convert('RGB'))),
                'frozen_sha256':file_sha(run/'frozen.json'),'executed_script_sha256':frozen['script_sha256'],
                'score_row':row,'stored_stages':{suffix:array_binding(arrays[prefix+'_'+suffix])
                    for suffix in ('feature','reference','recon','l2')}})
    out=Path(args.output);assert not out.exists()
    out.write_text(json.dumps({'status':'artifact_hash_bindings_recorded','rows':len(records),
        'scope':'post-hoc artifact inventory; stage associations come from executed loop and persisted records, no encoder/inversion rerun',
        'records':records},indent=2)+'\n',encoding='utf8')
    print('Bound',len(records),'image/stage records')
if __name__=='__main__':main()
