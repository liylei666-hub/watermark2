"""Target evaluation of all fixed PNGs after complete paired candidate sealing."""
import sys,time
from pathlib import Path
from common import c,r,bundle,IDS,METHODS


def main(runtime,images,digest,batch,output):
    runtime=Path(runtime);images=Path(images);output=Path(output);batch=int(batch)
    cfg=r.check_device(runtime,output)
    if cfg['role']!='target_evaluator' or batch not in (0,1):raise ValueError('Wrong evaluation role')
    bundle(images,digest,'evaluation_images')
    import torch
    from PIL import Image
    from gs_batch import private_module
    private=private_module();r.deterministic(0);start=time.perf_counter();provider=r.official_provider(cfg['target'])
    from utils.utils import check_if_detection_successful
    torch.cuda.synchronize();loading=time.perf_counter()-start
    if provider.get_dtype()!=torch.float32 or type(provider.scheduler_inverse).__name__!='DDIMInverseScheduler':raise ValueError('Provider changed')
    rows=[]
    for sid in IDS[4*batch:4*batch+4]:
        expected=cfg['identities'][sid];raw=private.load(Path(cfg['private_folder']),sid,expected)
        wm=private.provider(raw,'cuda:0')
        for method in ('reference',)+METHODS:
            folder=output/(sid+'_'+method);folder.mkdir();path=images/(sid+'_'+method+'.png');image=c.png_record(path)
            with Image.open(path) as im:im.load();im=im.copy()
            start=time.perf_counter()
            with torch.no_grad():z=provider.invert_images(im,num_inference_steps=50)['zT_torch']
            torch.cuda.synchronize();seconds=time.perf_counter()-start
            score=float(wm.get_accuracies(z)['bit_accuracies'][0])
            inverse=c.save_array(folder/'inverse.npy',z.detach().cpu().numpy(),'float32')
            row=dict(sample_id=sid,method=method,image=image,inverse=inverse,bit_accuracy=score,
                gs_detected=bool(check_if_detection_successful('GS',.70703125,score)),inversion_seconds=seconds,full_defense_accepted=None)
            c.write(folder/'metrics.json',row);rows.append(row)
    bundle(images,digest,'evaluation_images')
    c.write(output/'summary.json',dict(completed=True,rows=rows,model=cfg['target'],image_seal_sha256=digest,
        model_loading_seconds=loading,dtype=str(provider.get_dtype()),inverse_scheduler=type(provider.scheduler_inverse).__name__,
        vae_scaling_factor=provider.pipe.vae.config.scaling_factor,feedback_to_generator=False))
    print('COMPLETED_DELIVERY_EVALUATION',flush=True)

if __name__=='__main__':main(*sys.argv[1:])
