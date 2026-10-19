"""Evaluate sealed available candidates and controls; failed tasks stay explicitly missing."""
import sys,time
from pathlib import Path
from common import BASE,c,r,load,IDS,METHODS,activate_gate,verify_delivery
activate_gate()
def main(runtime,root,batch,private_folder,output):
    root=Path(root);output=Path(output);batch=int(batch);cfg=r.check_device(Path(runtime),output)
    sealed=verify_delivery(root)
    import torch
    from PIL import Image
    private=load('evaluation_private',BASE/'reference_reliability/private_state.py');r.deterministic(0);provider=r.official_provider(cfg['design']['target'])
    from utils.utils import check_if_detection_successful
    rows=[]
    for sid in IDS[batch*4:(batch+1)*4]:
        rec=c.read(root/('reference_'+str((sid-1)//4))/str(sid)/'record.json');wm=private.provider(private.load(Path(private_folder),sid,rec['encryption_fingerprints']),'cuda:0')
        for kind in ('reference','cover')+METHODS:
            item=next((x for x in sealed['rows'] if x['task_id']==sid and x['method']==kind),None)
            if item is not None and item['status']=='failed':continue
            source=root/'attack_inputs'/str(sid)/(kind+'.png') if item is None else root/item['candidate']
            folder=output/(str(sid)+'_'+kind);folder.mkdir();imrec=c.png_record(source)
            with Image.open(source) as im:image=im.convert('RGB')
            start=time.perf_counter()
            with torch.no_grad():z=provider.invert_images(image,num_inference_steps=50)['zT_torch']
            torch.cuda.synchronize();seconds=time.perf_counter()-start;ba=float(wm.get_accuracies(z)['bit_accuracies'][0])
            row=dict(task_id=sid,kind=kind,image=imrec,inverse=r.tensor(folder/'target_inverse.npy',z),bit_accuracy=ba,gs_detected=bool(check_if_detection_successful('GS',.70703125,ba)),inversion_seconds=seconds,full_defense_accepted=None,formal_content_label=None)
            c.write(folder/'metrics.json',row);rows.append(row)
    verify_delivery(root);c.write(output/'summary.json',dict(completed=True,rows=rows,delivery_seal_sha256=c.sha(root/'delivery_sealed.json'),feedback_to_attack=False));print('COMPLETED_COVER_EVALUATION',flush=True)
if __name__=='__main__':main(*sys.argv[1:])
