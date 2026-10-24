"""One bounded proxy-only integration gate on deterministic synthetic RGB arrays."""
import sys
from pathlib import Path
from common import c,r,preimport
from attack import load_model,optimize


def main(runtime,output):
    output=Path(output);cfg=preimport(runtime,output)
    if cfg['role']!='attacker':raise ValueError('Wrong qualification role')
    import numpy as np
    r.deterministic(29000)
    y,x=np.mgrid[:512,:512]
    cover=np.stack(((x//8%2)*160+40,(y//8%2)*150+50,(x+y)%220+15),axis=-1).astype(np.uint8)
    reference=np.stack(((x*3+y)%230+10,(y*3)%200+25,(511-x)%220+20),axis=-1).astype(np.uint8)
    model=load_model(cfg['proxy']);rows=[]
    for steps in (50,10):
        folder=output/str(steps);folder.mkdir()
        policy=dict(cfg['policy'],core_budget_seconds=120)
        result=optimize(model,reference,cover,steps,policy,folder,maximum_updates=1)
        if not result['quality']['feasible'] or result['updates']!=1:raise RuntimeError('Qualification incomplete')
        if result['update_seconds'][0] > (65 if steps==50 else 20):raise RuntimeError('Initial timing reserve inadequate')
        if result['finalization_reserve_exceeded']:raise RuntimeError('PNG finalization reserve inadequate')
        rows.append(dict(inversion_steps=steps,timing=result))
    c.write(output/'summary.json',dict(completed=True,rows=rows,target_calls=0,
        source='deterministic procedural RGB patterns; not target-generated or benchmark tasks'))
    print('COMPLETED_QUALITY_QUALIFICATION',flush=True)


if __name__=='__main__':main(*sys.argv[1:])
