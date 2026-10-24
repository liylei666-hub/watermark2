"""Evaluate all sealed final PNGs and controls, using evaluator-private GS identities."""
import sys,time
from pathlib import Path
from common import c,r,module,preimport,verify_seal,BASE,METHODS


def main(runtime,root,private_folder,output):
    root=Path(root);output=Path(output);cfg=preimport(runtime,output)
    if cfg['role']!='evaluator':raise ValueError('Wrong evaluator role')
    verify_seal(root)
    import torch
    from PIL import Image
    private=module('stage29_private_eval',BASE/'reference_reliability/private_state.py')
    r.deterministic(0);provider=r.official_provider(cfg['design']['target']);rows=[]
    for task in cfg['design']['tasks']:
        sid=task['task_id'];reference=c.read(root/'prepare_reference'/str(sid)/'record.json')
        raw=private.load(Path(private_folder),sid,reference['encryption_fingerprints']);wm=private.provider(raw,'cuda:0')
        for kind in ('reference','cover')+METHODS:
            source=root/'attack_inputs'/str(sid)/(kind+'.png') if kind in ('reference','cover') else root/f'attack_{sid}_{kind}'/'candidate.png'
            out=output/f'{sid}_{kind}';out.mkdir();image_record=c.png_record(source)
            with Image.open(source) as im:image=im.convert('RGB')
            start=time.perf_counter()
            with torch.no_grad():z=provider.invert_images(image,num_inference_steps=50)['zT_torch']
            torch.cuda.synchronize();elapsed=time.perf_counter()-start
            ba=float(wm.get_accuracies(z)['bit_accuracies'][0])
            row=dict(task_id=sid,kind=kind,image=image_record,inverse=r.tensor(out/'target_inverse.npy',z),
                bit_accuracy=ba,gs_detected=ba>cfg['design']['gs_threshold'],inversion_seconds=elapsed)
            c.write(out/'metrics.json',row);rows.append(row);print('EVALUATED',sid,kind,flush=True)
    verify_seal(root)
    c.write(output/'summary.json',dict(completed=True,rows=rows,seal_sha256=c.sha(root/'candidates_sealed.json'),
        target_feedback_to_attack=False,full_defense_acceptance=None))
    print('COMPLETED_QUALITY_EVALUATION',flush=True)


if __name__=='__main__':main(*sys.argv[1:])
