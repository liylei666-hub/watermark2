"""CPU tests of the preparation-to-attack-to-evaluator interface."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only tests')
import copy
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import contract as c
import bundle as b


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.prepared=dict(version=1,tasks=[])
        for task in [1,2,3]:
            row=dict(task_id=task)
            for kind,color in [('reference',(task,40,100)),('cover',(170,task,80))]:
                p=self.root/'evaluator_private'/str(task)/(kind+'.png');p.parent.mkdir(parents=True,exist_ok=True)
                Image.new('RGB',(512,512),color).save(p)
                row[kind]=c.png_record(p);row[kind]['path']=p.relative_to(self.root).as_posix()
            c.write(p.parent/'private_state.json',dict(target_key='private synthetic fixture',target_score=0.99))
            self.prepared['tasks'].append(row)

    def prepare_candidates(self):
        plan=b.export_jobs(self.root,self.prepared)
        for row in plan['jobs']:
            out=self.root/row['output_path'];out.mkdir(parents=True)
            Image.new('RGB',(512,512),(row['task_id'],80,70)).save(out/'candidate.png')
            c.freeze_candidate(out,self.root/row['job_path'])
        return self.root/'attack_plan.json'

    def test_public_export_contains_only_jobs_and_two_images(self):
        plan=b.export_jobs(self.root,self.prepared)
        self.assertEqual(len(plan['jobs']),6)
        for task in [1,2,3]:
            folder=self.root/'attack_inputs'/str(task)
            self.assertEqual({p.name for p in folder.iterdir()},{'reference.png','cover.png','imprint.json','jain.json'})
            for method in c.METHODS:c.validate_job(folder/(method+'.json'))

    def test_all_candidates_required_before_first_evaluator_call(self):
        path=self.prepare_candidates();calls=[]
        with self.assertRaises(FileNotFoundError):b.evaluate_fixed_queue(self.root,path,lambda *args:calls.append(args))
        self.assertEqual(calls,[])

    def test_exact_queue_and_reference_failure_do_not_filter_candidates(self):
        path=self.prepare_candidates();c.seal_delivery(self.root,path);calls=[]
        def evaluator(p,task,kind):
            calls.append((task,kind));return dict(bit_accuracy=0.,detected=False)
        rows=b.evaluate_fixed_queue(self.root,path,evaluator)
        self.assertEqual(calls,[(t,k) for t in [1,2,3] for k in ['reference','cover','imprint','jain']])
        self.assertEqual(len(rows),12)

    def test_changed_input_rejected_before_export(self):
        Image.new('RGB',(512,512),(1,2,3)).save(self.root/self.prepared['tasks'][-1]['cover']['path'])
        with self.assertRaises(ValueError):b.export_jobs(self.root,self.prepared)
        self.assertFalse((self.root/'attack_inputs').exists())

    def test_export_cannot_overwrite(self):
        b.export_jobs(self.root,self.prepared)
        with self.assertRaises(FileExistsError):b.export_jobs(self.root,self.prepared)

    def test_changed_candidate_blocks_every_evaluation(self):
        path=self.prepare_candidates();c.seal_delivery(self.root,path);calls=[]
        out=self.root/'attack_outputs/3/jain/candidate.png'
        Image.new('RGB',(512,512),(0,0,0)).save(out)
        with self.assertRaises(ValueError):b.evaluate_fixed_queue(self.root,path,lambda *args:calls.append(args))
        self.assertEqual(calls,[])

    def test_target_fields_in_preparation_rejected(self):
        for field in ['target_key','target_score','target_original_latent','target_rng']:
            data=copy.deepcopy(self.prepared);data['tasks'][0][field]='fixture'
            with self.assertRaises(ValueError):b.export_jobs(self.root,data)
        self.assertFalse((self.root/'attack_inputs').exists())


if __name__=='__main__':unittest.main(verbosity=2)
