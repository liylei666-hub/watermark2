"""Synthetic CPU orchestration checks; no model callback exists in this test."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import json,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
import delivery as d
import interface as i
from workflow import execute

class Tests(unittest.TestCase):
    def test_full_order_and_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);calls=[]
            def child(name,script,args):
                calls.append((name,script));out=root/name;out.mkdir(parents=True)
                if script=='prepare.py':
                    role=args[1]
                    for task in range(1,5):
                        f=out/str(task);f.mkdir()
                        Image.fromarray(np.full((512,512,3),90 if role=='reference' else 128,dtype=np.uint8)).save(f/(role+'.png'))
                elif script=='attack.py':
                    self.assertTrue((root/'input_jobs_sealed.json').exists())
                    job=i.validate_job(args[0]);self.assertEqual(set(job),{'version','task_id','seed','proxy','reference','cover'})
                    with Image.open(args[0].parent/'cover.png') as im:cover=np.array(im)
                    images,mask,stat=d.build(cover,np.ones(cover.shape),-np.ones(cover.shape),job['seed'])
                    d.export(out/'probes',cover,images,mask,stat)
                else:
                    self.assertEqual(len(i.verified_queue(root)),28)
                return out
            execute(root,child,Path('synthetic_protocol'))
            self.assertEqual([x[1] for x in calls],['prepare.py']*2+['attack.py']*4+['evaluate.py'])

    def test_failure_stops_without_later_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            def fail(*args):calls.append(args);raise RuntimeError('synthetic failure')
            with self.assertRaisesRegex(RuntimeError,'synthetic failure'):execute(Path(tmp),fail,Path('unused'))
            self.assertEqual(len(calls),1)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        gpu_used=False,models_loaded=False,new_model_experiments_run=0,scope='synthetic workflow only')))
    raise SystemExit(0 if result.wasSuccessful() else 1)
