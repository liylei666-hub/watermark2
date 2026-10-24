import sys,time,math
from pathlib import Path
from common31 import c,r,module,gate,candidates,guard,BASE,POINTS
def main(runtime,root,private_folder,output):
    root=Path(root);out=Path(output);cfg=gate(runtime,out)
    if cfg['role']!='evaluator':raise ValueError('Wrong evaluator role')
    seal=c.read(root/'candidates_sealed.json')
    if seal['rows']!=candidates(root):raise ValueError('Candidates changed')
    import numpy as np,torch
    from PIL import Image
    from skimage.metrics import structural_similarity
    from torchmetrics.image import MultiScaleStructuralSimilarityIndexMeasure,PeakSignalNoiseRatio
    private=module('native_eval_private',BASE/'reference_reliability/private_state.py');r.deterministic(0)
    provider=r.official_provider(cfg['design']['target']);arrays=[];guard(provider.scheduler_inverse,arrays);provider.scheduler_inverse.set_timesteps(50,device='cuda:0');rows=[]
    for task in cfg['design']['tasks']:
        sid=task['id'];record=c.read(root/'prepare'/str(sid)/'record.json');raw=private.load(Path(private_folder),sid,record['encryption_fingerprints']);wm=private.provider(raw,'cuda:0')
        with Image.open(root/'prepare'/str(sid)/'cover.png') as im:cover=im.convert('RGB').copy()
        for label,path in [('reference',root/'prepare'/str(sid)/'reference.png'),('cover',root/'prepare'/str(sid)/'cover.png')]+[(str(n),root/f'attack_{sid}'/f'update_{n}.png') for n in POINTS]:
            folder=out/(str(sid)+'_'+label);folder.mkdir()
            with Image.open(path) as im:image=im.convert('RGB')
            start=time.perf_counter()
            with torch.no_grad():z=provider.invert_images(image,num_inference_steps=50)['zT_torch']
            torch.cuda.synchronize();inverse_seconds=time.perf_counter()-start;ba=float(wm.get_accuracies(z)['bit_accuracies'][0])
            a=np.asarray(image,dtype=np.float64)/255;b=np.asarray(cover,dtype=np.float64)/255;mse=float(np.mean((a-b)**2));psnr=None if mse==0 else -10*math.log10(mse)
            gray1=np.asarray(image.convert('L'));gray2=np.asarray(cover.convert('L'));ssim=float(structural_similarity(gray1,gray2,data_range=255))
            ta=torch.from_numpy(a).permute(2,0,1).unsqueeze(0).float();tb=torch.from_numpy(b).permute(2,0,1).unsqueeze(0).float()
            official_psnr=float(PeakSignalNoiseRatio(data_range=1.0)(ta,tb))
            ms=float(MultiScaleStructuralSimilarityIndexMeasure(data_range=1.0)(ta,tb))
            row=dict(task_id=sid,label=label,image=c.png_record(path),inverse=r.tensor(folder/'target_inverse.npy',z),bit_accuracy=ba,gs_detected=ba>.70703125,mse_rgb01=mse,psnr_db=psnr,official_torchmetrics_psnr_db=None if mse==0 else official_psnr,psnr_infinite=mse==0,ssim_grayscale=ssim,ms_ssim_rgb=ms,lpips=None,inversion_seconds=inverse_seconds)
            c.write(folder/'metrics.json',row);rows.append(dict(**row,folder=folder.name));print('EVALUATED',sid,label,flush=True)
    if seal['rows']!=candidates(root):raise ValueError('Candidate changed')
    c.write(out/'summary.json',dict(completed=True,rows=rows,candidate_seal_sha256=c.sha(root/'candidates_sealed.json'),scheduler_calls=arrays,lpips_status='unknown_no_admitted_backbone'));print('COMPLETED_NATIVE_EVAL',flush=True)
if __name__=='__main__':main(*sys.argv[1:])
