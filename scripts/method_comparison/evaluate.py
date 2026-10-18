"""Evaluate all predetermined candidate PNGs only after the entire delivery is sealed."""
import sys,time
from pathlib import Path
from common import c,r,METHODS,IDS,private_module,verify_delivery

def main(runtime,root,batch,private_folder,output):
    root=Path(root);output=Path(output);batch=int(batch);cfg=r.check_device(Path(runtime),output)
    if cfg['role']!='evaluator' or batch not in range(3):raise ValueError('Wrong evaluator role')
    verify_delivery(root)
    import torch
    from PIL import Image
    private=private_module();r.deterministic(0);provider=r.official_provider(cfg['design']['target'])
    from utils.utils import check_if_detection_successful
    rows=[]
    for sid in IDS[4*batch:4*(batch+1)]:
        rec=c.read(root/('reference_'+str((sid-1)//4))/str(sid)/'record.json')
        wm=private.provider(private.load(Path(private_folder),sid,rec['encryption_fingerprints']),'cuda:0')
        for kind in ('reference','cover')+METHODS:
            source=root/'attack_inputs'/str(sid)/(kind+'.png') if kind in ('reference','cover') else root/'attack_outputs'/str(sid)/kind/'candidate.png'
            folder=output/(str(sid)+'_'+kind);folder.mkdir();image_record=c.png_record(source)
            with Image.open(source) as im:image=im.convert('RGB')
            start=time.perf_counter()
            with torch.no_grad():z=provider.invert_images(image,num_inference_steps=50)['zT_torch']
            torch.cuda.synchronize();seconds=time.perf_counter()-start
            ba=float(wm.get_accuracies(z)['bit_accuracies'][0]);record=r.tensor(folder/'target_inverse.npy',z)
            row=dict(task_id=sid,kind=kind,image=image_record,inverse=record,bit_accuracy=ba,
                     gs_detected=bool(check_if_detection_successful('GS',.70703125,ba)),inversion_seconds=seconds,full_defense_accepted=None,formal_content_label=None)
            c.write(folder/'metrics.json',row);rows.append(row)
    verify_delivery(root)
    c.write(output/'summary.json',dict(completed=True,rows=rows,delivery_seal_sha256=c.sha(root/'delivery_sealed.json'),feedback_to_attack=False))
    print('COMPLETED_COVER_EVALUATION',flush=True)

if __name__=='__main__':main(*sys.argv[1:])
