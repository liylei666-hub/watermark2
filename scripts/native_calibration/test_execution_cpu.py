import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import ast,copy,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
import torch
from common31 import c,r,ROOT,HERE,BASE,POINTS,update_code,validate_job,candidates
import control31
import analyze31
class Execution(unittest.TestCase):
    def test_original_update_ast_151_matches_reference_and_step(self):
        torch.manual_seed(311);initial=torch.randn(17,dtype=torch.float64);target=torch.randn(17,dtype=torch.float64)
        a=torch.nn.Parameter(initial.clone());oa=torch.optim.Adam([a],lr=.01)
        scope=dict(optim=oa,z0=a,torch=torch,zT_retrieved=target,diffpipe=lambda x,*a,**kw:x.sin())
        code=update_code(ROOT/'third_party/semantic-forgery/run_imprint_forgery.py');seen=[]
        for n in range(1,152):
            exec(code,scope)
            if n in POINTS:seen.append((n,a.detach().clone()))
        b=torch.nn.Parameter(initial.clone());ob=torch.optim.Adam([b],lr=.01)
        for n in range(1,152):ob.zero_grad();loss=torch.nn.functional.mse_loss(b.sin(),target.detach());loss.backward();ob.step()
        self.assertTrue(torch.equal(a,b));self.assertEqual(int(oa.state[a]['step']),151);self.assertEqual([n for n,v in seen],[20,50,100,150,151]);self.assertFalse(torch.equal(seen[-2][1],seen[-1][1]))
    def test_checkpoint_binding_requires_twenty_images_and_successful_jobs(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='native31_cpu_') as t:
            root=Path(t)
            for sid in range(1,5):
                out=root/f'attack_{sid}';out.mkdir();inp=root/'attack_inputs'/str(sid);inp.mkdir(parents=True);c.write(inp/'job.json',dict(id=sid));images={}
                for n in POINTS:Image.new('RGB',(512,512),(sid,n,0)).save(out/f'update_{n}.png');images[str(n)]=c.png_record(out/f'update_{n}.png')
                c.write(out/'candidates_frozen.json',dict(task_id=sid,job_sha256=c.sha(inp/'job.json'),images=images));c.write(out/'execution.json',dict(outcome=dict(completed=True)))
            self.assertEqual(len(candidates(root)),20)
            (root/'attack_4/update_151.png').write_bytes(b'changed')
            with self.assertRaises(Exception):candidates(root)
    def test_plan_preserves_approved_inputs_and_role_boundary(self):
        p=c.read(ROOT/'protocols/31_native_calibration_execution.json')
        self.assertEqual(p['native']['actual_adam_updates'],151);self.assertEqual(p['native']['checkpoint_actual_updates'],list(POINTS));self.assertEqual(p['evaluation']['target_inverse_images'],28)
        self.assertEqual([x['id'] for x in p['tasks']],[1,2,3,4]);self.assertIsNone(p['native']['mask']);self.assertEqual(p['native']['reference_encoding_range'],[0,1]);self.assertEqual(p['native']['cover_encoding_range'],[-1,1])
        attacker={name:h for name,h in p.items() if name in ('proxy','native')}
        self.assertNotIn('target',attacker);self.assertNotIn('key',attacker)

    def test_mock_workflow_seals_all_checkpoints_before_evaluation(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='native31_flow_') as t:
            root=Path(t);(root/'protocols').mkdir();(root/'runs').mkdir();(root/'private_eval').mkdir();runtime=root/'protocols/controller.json';runtime.write_text('{}')
            design=c.read(ROOT/'protocols/31_native_calibration_execution.json');cfg=dict(design=design,proxy=design['proxy'],native=design['native'],source_commit='cpu_fixture',run_dir='runs/test',private_folder='private_eval/test',
                devices=[dict(index=i,uuid='GPU-fixture-'+str(i),model='fixture') for i in (0,1)],per_device_runtime={role:{str(i):'protocols/controller.json' for i in (0,1)} for role in ('attacker','evaluator')},role_hashes={role:{str(i):c.sha(runtime) for i in (0,1)} for role in ('attacker','evaluator')})
            calls=[]
            class Fake(control31.Runner):
                def __call__(self,job,device,out,env):
                    calls.append(job.name)
                    if job.name=='prepare':
                        for sid in range(1,5):
                            folder=out/str(sid);folder.mkdir()
                            for kind in ('cover','reference'):Image.new('RGB',(512,512),(sid,0,0)).save(folder/(kind+'.png'))
                    elif job.name.startswith('attack_'):
                        self_outer.assertEqual(self.phases[job.name],'native_attack')
                        sid=int(job.name.split('_')[1]);inp=out.parent/'attack_inputs'/str(sid)/'job.json';validate_job(inp,cfg);images={}
                        for n in POINTS:Image.new('RGB',(512,512),(sid,n,0)).save(out/f'update_{n}.png');images[str(n)]=c.png_record(out/f'update_{n}.png')
                        c.write(out/'candidates_frozen.json',dict(task_id=sid,job_sha256=c.sha(inp),images=images))
                    else:
                        self_outer.assertEqual(len(candidates(out.parent)),20);self_outer.assertTrue((out.parent/'candidates_sealed.json').exists());self_outer.assertEqual(set(calls),{'prepare','attack_1','attack_2','attack_3','attack_4','evaluate'})
                    return dict(completed=True,exit_code=0)
            self_outer=self
            def analysis(run,private):c.write(run/'analysis.json',dict(completed=True));return dict(completed=True)
            with patch.object(control31,'ROOT',root),patch.object(control31.launch,'check_host',lambda _:None),patch.object(control31.r,'verify_runtime',lambda _:cfg),patch.object(control31.sched,'verify_idle',lambda *args:True),patch.object(control31,'Runner',Fake),patch.object(analyze31,'analyze',analysis):
                control31.run(runtime)
                self.assertEqual(c.read(root/'runs/test/scheduler_status.json')['state'],'completed')
                count=len(calls)
                with self.assertRaises(ValueError):control31.run(runtime)
                self.assertEqual(len(calls),count)
if __name__=='__main__':unittest.main()
