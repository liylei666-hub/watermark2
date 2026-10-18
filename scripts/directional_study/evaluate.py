"""Evaluate all sealed images with the fixed ordinary GS provider, per identity."""
import sys
import time
from pathlib import Path
import interface as i
from common import r,design

def main(runtime,protocol,root,output):
    r.check_device(runtime,output);cfg=design(protocol)
    i.verified_queue(root)
    import torch
    from PIL import Image
    r.deterministic(0);provider=r.official_provider(cfg['target'])
    from utils.wm.gs_provider import GsProvider
    from utils.utils import check_if_detection_successful
    watermarks={task['task_id']:GsProvider(latent_shape=(1,4,64,64),device='cuda:0',
        offset=task['gs_offset'],**cfg['gs_parameters']) for task in cfg['tasks']}
    def one(path,task,kind):
        folder=output/str(task)/kind;folder.mkdir(parents=True)
        with Image.open(path) as im:image=im.copy()
        torch.cuda.synchronize();start=time.perf_counter()
        with torch.no_grad():z=provider.invert_images(image,num_inference_steps=50)['zT_torch']
        torch.cuda.synchronize();seconds=time.perf_counter()-start
        record=r.tensor(folder/'target_inverse.npy',z)
        score=float(watermarks[task].get_accuracies(z)['bit_accuracies'][0])
        result=dict(bit_accuracy=score,gs_detected=check_if_detection_successful('GS',cfg['gs_threshold'],score),
            inversion_seconds=seconds,target_inverse=record,content_pass=None,full_defense_accepted=None)
        i.write(folder/'metrics.json',result);return result
    rows=i.evaluate(root,one)
    i.write(output/'summary.json',dict(completed=True,rows=rows,protocol_sha256=i.sha(protocol),
        delivery_seal_sha256=i.sha(root/'delivery_sealed.json'),target_feedback_to_attack=False,
        full_defense_acceptance=None))
    print('COMPLETED_DIRECTION_EVALUATION',flush=True)

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
