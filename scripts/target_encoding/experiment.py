"""Official target image encoding of all presealed images; evaluator-only."""
import sys
import time
from pathlib import Path
from common import REMOTE, RUN, sha, write, validate

ROOT = Path(REMOTE)
sys.path.insert(0,str(ROOT/'scripts/cover_pilot'))
import runtime as r
import bundle as b


def main(protocol, output):
    cfg = r.check_device(protocol,output)
    inputs = validate(cfg,ROOT)
    source = ROOT/RUN
    queue = b.evaluation_queue(source,source/'attack_plan.json')
    for row in queue:
        key = f"{row['task_id']}/{row['kind']}"
        if source/row['path'] != inputs[key] or row['sha256'] != cfg['inputs'][key]['sha256']:
            raise ValueError('Sealed evaluation inventory differs')
    import torch
    from PIL import Image
    r.deterministic(0)
    provider = r.official_provider(cfg['target'])
    rows = []
    with torch.no_grad():
        for task in [1,2,3]:
            folder = output/str(task)
            folder.mkdir()
            for role in ['reference','cover','imprint','jain']:
                p = inputs[f'{task}/{role}']
                with Image.open(p) as image:
                    if image.size != (512,512) or image.mode != 'RGB':
                        raise ValueError('Unexpected image geometry')
                    torch.cuda.synchronize()
                    start = time.perf_counter()
                    z = provider.imgs_to_latents(image.copy())
                    torch.cuda.synchronize()
                if z.dtype != torch.float32 or tuple(z.shape) != (1,4,64,64):
                    raise ValueError('Unexpected encoding format')
                rec = r.tensor(folder/(role+'_z.npy'),z)
                rows.append(dict(task_id=task,role=role,input_sha256=sha(p),
                    target_encoding=rec,encoding_seconds=time.perf_counter()-start))
    validate(cfg,ROOT)
    b.evaluation_queue(source,source/'attack_plan.json')
    write(output/'summary.json',dict(completed=True,rows=rows,
        protocol_sha256=sha(protocol),target_model_loaded=True,
        target_encoding_calls=12,target_inversion_calls=0,generation_calls=0,
        optimization_updates=0,new_candidate_images=0,attack_feedback=False,
        scaling_factor=provider.pipe.vae.config.scaling_factor,full_defense_acceptance=None))
    print('COMPLETED_TARGET_ENCODING',flush=True)


if __name__=='__main__': main(Path(sys.argv[1]),Path(sys.argv[2]))
