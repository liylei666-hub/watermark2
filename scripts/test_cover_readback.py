"""Synthetic CPU checks for result binding and complete-task accounting."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only test')
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
import analyze_cover_pilot as a
c=a.c;b=a.b


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        prepared=dict(version=1,tasks=[])
        for task in [1,2,3]:
            row=dict(task_id=task)
            for kind,value in [('reference',80),('cover',10)]:
                folder=self.root/'evaluator_private'/kind/str(task);folder.mkdir(parents=True)
                path=folder/(kind+'.png');Image.new('RGB',(512,512),(value,)*3).save(path)
                row[kind]=c.png_record(path);row[kind]['path']=path.relative_to(self.root).as_posix()
            prepared['tasks'].append(row)
        plan=b.export_jobs(self.root,prepared)
        folders=['evaluator_private/reference','evaluator_private/cover','evaluator_results']
        for row in plan['jobs']:
            out=self.root/row['output_path'];out.mkdir(parents=True);folders.append(row['output_path'])
            Image.new('RGB',(512,512),(255,)*3 if row['method']=='jain' else (0,)*3).save(out/'candidate.png')
            frozen=c.freeze_candidate(out,self.root/row['job_path'])
            timing=dict(reference_encoding_and_optimization_seconds=12.) if row['method']=='jain' else dict(reference_and_cover_preparation_seconds=2.,optimization_seconds=10.)
            c.write(out/'summary.json',dict(task_id=row['task_id'],method=row['method'],candidate=frozen,timing=timing))
            if row['method']=='jain':np.save(out/'final_float.npy',np.ones((1,3,512,512),dtype=np.float32),allow_pickle=False)
        c.seal_delivery(self.root,self.root/'attack_plan.json');rows=[]
        for row in b.evaluation_queue(self.root,self.root/'attack_plan.json'):
            folder=self.root/'evaluator_results'/str(row['task_id'])/row['kind'];folder.mkdir(parents=True)
            np.save(folder/'target_inverse.npy',np.zeros((1,4,64,64),dtype=np.float32),allow_pickle=False)
            # Synthetic scores exercise accounting only; not detector outcomes.
            ba=.75 if row['kind']=='imprint' else .5
            rows.append(dict(input=row,result=dict(bit_accuracy=ba,gs_detected=ba>181/256,target_inverse=dict(sha256=c.sha(folder/'target_inverse.npy')))))
        c.write(self.root/'evaluator_results/summary.json',dict(rows=rows,delivery_seal_sha256=c.sha(self.root/'delivery_sealed.json'),threshold=181/256,decision='bit_accuracy > threshold'))
        for folder in folders:
            c.write(self.root/folder/'execution.json',dict(exit_code=0,completed=True,timed_out=False,elapsed_seconds=15.,gpu_index=0,gpu_uuid='synthetic-test-fixture'))
        c.write(self.root/'status.json',dict(status='completed',completed=True))

    def change(self,path,mutate):
        p=self.root/path;value=c.read(p);mutate(value);p.write_text(__import__('json').dumps(value),encoding='utf-8')

    def test_all_planned_pairs_counted_despite_reference_rejection(self):
        result=a.analyze(self.root)
        self.assertEqual(len(result['rows']),6)
        self.assertEqual(result['descriptive_counts']['imprint']['ordinary_gs_pass'],3)
        self.assertEqual(result['descriptive_counts']['jain']['ordinary_gs_pass'],0)
        self.assertEqual(result['model_process_seconds'],135.)
        self.assertTrue(all(row['content_pass'] is None and row['joint_success'] is None for row in result['rows']))
        first=result['rows'][0]
        self.assertAlmostEqual(first['png_to_cover_mse_0_1'],(10/255)**2,places=15)
        self.assertEqual(first['png_to_cover_linf_8bit'],10)

    def test_changed_evaluation_input_rejected(self):
        self.change('evaluator_results/summary.json',lambda d:d['rows'][0]['input'].update(task_id=3))
        with self.assertRaises(ValueError):a.analyze(self.root)

    def test_changed_latent_rejected(self):
        p=self.root/'evaluator_results/1/imprint/target_inverse.npy';p.write_bytes(p.read_bytes()+b'changed')
        with self.assertRaises(ValueError):a.analyze(self.root)

    def test_false_success_boolean_rejected(self):
        self.change('evaluator_results/summary.json',lambda d:d['rows'][0]['result'].update(gs_detected=True))
        with self.assertRaises(ValueError):a.analyze(self.root)

    def test_wrong_float_serialization_rejected(self):
        np.save(self.root/'attack_outputs/1/jain/final_float.npy',np.zeros((1,3,512,512),dtype=np.float32),allow_pickle=False)
        with self.assertRaises(ValueError):a.analyze(self.root)

    def test_missing_child_rejected(self):
        (self.root/'evaluator_private/cover/execution.json').unlink()
        with self.assertRaises(ValueError):a.analyze(self.root)

    def test_failed_child_rejected(self):
        self.change('attack_outputs/3/jain/execution.json',lambda d:d.update(exit_code=1,completed=False))
        with self.assertRaises(ValueError):a.analyze(self.root)

    def test_incomplete_group_rejected(self):
        self.change('status.json',lambda d:d.update(status='running',completed=False))
        with self.assertRaises(ValueError):a.analyze(self.root)


if __name__=='__main__':unittest.main(verbosity=2)
