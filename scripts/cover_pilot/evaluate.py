"""Ordinary GS evaluation of the complete presealed delivery; no attack feedback."""
import sys
import time
from pathlib import Path
import contract as c
import bundle as b
import runtime as r


def main(runtime,protocol,root,output):
    r.check_device(runtime,output)
    if c.sha(protocol)!=protocol.with_suffix('.sha256').read_text().strip():raise ValueError('Protocol changed')
    cfg=c.read(protocol);plan=root/'attack_plan.json'
    # Fail before loading a target if any candidate or input is missing or changed.
    b.evaluation_queue(root,plan)
    import torch
    from PIL import Image
    r.deterministic(0);provider=r.official_provider(cfg['target'])
    from utils.wm.gs_provider import GsProvider
    from utils.utils import check_if_detection_successful
    wm=GsProvider(latent_shape=(1,4,64,64),device='cuda:0',**cfg['gs_parameters'])
    def evaluator(path,task,kind):
        folder=output/str(task)/kind;folder.mkdir(parents=True)
        with Image.open(path) as im:image=im.convert('RGB')
        torch.cuda.synchronize();start=time.perf_counter()
        with torch.no_grad():z=provider.invert_images(image,num_inference_steps=50)['zT_torch']
        torch.cuda.synchronize();elapsed=time.perf_counter()-start
        record=r.tensor(folder/'target_inverse.npy',z)
        ba=float(wm.get_accuracies(z)['bit_accuracies'][0])
        result=dict(bit_accuracy=ba,gs_detected=check_if_detection_successful('GS',cfg['gs_threshold'],ba),
            inversion_seconds=elapsed,target_inverse=record,content_pass=None,full_defense_accepted=None)
        c.write(folder/'metrics.json',result);return result
    results=b.evaluate_fixed_queue(root,plan,evaluator)
    c.write(output/'summary.json',dict(completed=True,rows=results,protocol_sha256=c.sha(protocol),
        delivery_seal_sha256=c.sha(root/'delivery_sealed.json'),target_feedback_to_attack=False,
        threshold=cfg['gs_threshold'],decision='bit_accuracy > threshold',full_defense_acceptance=None))
    print('COMPLETED_COVER_EVALUATION',flush=True)


if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]))
