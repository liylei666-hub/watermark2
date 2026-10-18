"""CPU tests of information allowlists and all-candidate-before-evaluation order."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility must be empty')
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
import delivery as d
import interface as i


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.cover=np.full((512,512,3),128,dtype=np.uint8)
        self.ref=np.full((512,512,3),90,dtype=np.uint8)
        Image.fromarray(self.cover).save(self.root/'c.png')
        Image.fromarray(self.ref).save(self.root/'r.png')
        for task in range(1,5):i.export_job(self.root,task,self.root/'r.png',self.root/'c.png')
        i.freeze_inputs(self.root)

    def tearDown(self): self.tmp.cleanup()

    def outputs(self):
        for task in range(1,5):
            values,support,summary=d.build(self.cover,np.ones(self.cover.shape),-np.ones(self.cover.shape),800+task)
            out=self.root/'attack_outputs'/str(task);out.mkdir(parents=True)
            d.export(out/'probes',self.cover,values,support,summary)

    def test_target_metadata_rejected(self):
        p=self.root/'attack_inputs/1/job.json';base=i.read(p)
        for name in ['gs_offset','target','key','target_score','reference_noise']:
            bad=dict(base);bad[name]='not_allowed'
            p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):i.validate_job(p)

    def test_input_path_replacement_rejected(self):
        p=self.root/'attack_inputs/1/job.json';job=i.read(p);job['reference']['path']='../../r.png'
        p.write_text(json.dumps(job))
        with self.assertRaises(ValueError):i.validate_job(p)

    def test_missing_candidates_prevent_all_callbacks(self):
        calls=[]
        with self.assertRaises(FileNotFoundError):i.evaluate(self.root,lambda *x:calls.append(x))
        self.assertEqual(calls,[])

    def test_complete_seal_then_fixed_order(self):
        self.outputs();sealed=i.seal(self.root);calls=[]
        rows=i.evaluate(self.root,lambda path,task,kind:calls.append((task,kind)))
        self.assertEqual(len(rows),28)
        self.assertEqual(calls,[(t,k) for t in range(1,5) for k in ['reference','cover',*d.CONDITIONS]])
        with self.assertRaises(FileExistsError):i.seal(self.root)

    def test_changed_png_blocks_callbacks(self):
        self.outputs();i.seal(self.root)
        p=self.root/'attack_outputs/4/probes/random.png'
        Image.fromarray(self.ref).save(p);calls=[]
        with self.assertRaises(ValueError):i.evaluate(self.root,lambda *x:calls.append(x))
        self.assertEqual(calls,[])

    def test_reference_replacement_after_input_freeze_rejected(self):
        self.outputs();p=self.root/'attack_inputs/1/reference.png'
        Image.fromarray(self.cover).save(p)
        jp=p.parent/'job.json';job=i.read(jp);job['reference']=i.image_record(p);jp.write_text(json.dumps(job))
        with self.assertRaises(ValueError):i.seal(self.root)

    def test_summary_tampering_rejected(self):
        self.outputs();p=self.root/'attack_outputs/2/probes/candidate_set.json'
        record=i.read(p);record['distortion']['linf_integer']=2;p.write_text(json.dumps(record))
        with self.assertRaises(ValueError):i.seal(self.root)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        gpu_used=False,models_loaded=False,new_model_experiments_run=0,
        scope='synthetic PNGs and callbacks; data contracts, not OS permission isolation')))
    raise SystemExit(0 if result.wasSuccessful() else 1)
