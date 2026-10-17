"""CPU regressions for candidate binding and attack/evaluator field boundaries."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only tests')
import copy
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import contract as c


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.plan=dict(version=1,jobs=[])
        for task in [1,2,3]:
            folder=self.root/'inputs'/str(task);folder.mkdir(parents=True)
            for name,color in [('reference',(20*task,50,90)),('cover',(180,30*task,10))]:
                Image.new('RGB',(512,512),color).save(folder/(name+'.png'))
            for method in c.METHODS:
                job=dict(version=1,task_id=task,method=method,seed=500+task,
                    reference=c.png_record(folder/'reference.png'),cover=c.png_record(folder/'cover.png'),
                    proxy=dict(model_id=c.PROXY_ID,revision=c.PROXY_REVISION,snapshot=c.PROXY_SNAPSHOT,dtype='float32',resolution=512),
                    parameters=c.METHODS[method])
                jp=folder/(method+'.json');c.write(jp,job)
                out=self.root/'outputs'/str(task)/method;out.mkdir(parents=True)
                Image.new('RGB',(512,512),(100,task,20)).save(out/'candidate.png')
                c.freeze_candidate(out,jp)
                self.plan['jobs'].append(dict(task_id=task,method=method,job_path=jp.relative_to(self.root).as_posix(),
                    job_sha256=c.sha(jp),output_path=out.relative_to(self.root).as_posix()))
        self.plan_path=self.root/'plan.json';c.write(self.plan_path,self.plan)

    def job(self):return self.root/self.plan['jobs'][0]['job_path']
    def overwrite_fixture(self,path,value):path.write_text(json.dumps(value),encoding='utf-8')

    def test_complete_delivery_is_verified(self):
        value=c.seal_delivery(self.root,self.plan_path)
        self.assertEqual(c.verify_delivery(self.root,self.plan_path),value)
        self.assertEqual(len(value['candidates']),6)

    def test_evaluator_only_fields_rejected(self):
        path=self.job();original=c.read(path)
        for key in ['target_key','target_message','target_original_latent','target_rng','target_inversion','target_score']:
            modified=copy.deepcopy(original);modified[key]='forbidden fixture'
            self.overwrite_fixture(path,modified)
            with self.assertRaises(ValueError):c.validate_job(path)
        self.overwrite_fixture(path,original)

    def test_nested_target_configuration_rejected(self):
        path=self.job();job=c.read(path);job['proxy']['target_score']=0.9;self.overwrite_fixture(path,job)
        with self.assertRaises(ValueError):c.validate_job(path)

    def test_parameter_and_seed_changes_rejected(self):
        path=self.job();original=c.read(path)
        for change in ['parameters','seed']:
            job=copy.deepcopy(original)
            if change=='parameters':job['parameters']['updates']=11
            else:job['seed']=301
            self.overwrite_fixture(path,job)
            with self.assertRaises(ValueError):c.validate_job(path)

    def test_path_escape_rejected(self):
        for path in ['../private/key.json','/tmp/private','C:/private','..\\private']:
            with self.assertRaises(ValueError):c.inside(self.root,path)

    def test_candidate_mutation_after_seal_rejected(self):
        c.seal_delivery(self.root,self.plan_path)
        path=self.root/self.plan['jobs'][0]['output_path']/'candidate.png'
        Image.new('RGB',(512,512),(0,0,0)).save(path)
        with self.assertRaises(ValueError):c.verify_delivery(self.root,self.plan_path)

    def test_swapped_task_binding_rejected(self):
        a=self.root/self.plan['jobs'][0]['output_path']/'candidate_frozen.json'
        b=self.root/self.plan['jobs'][2]['output_path']/'candidate_frozen.json'
        a.write_bytes(b.read_bytes())
        with self.assertRaises(ValueError):c.seal_delivery(self.root,self.plan_path)

    def test_missing_candidate_prevents_evaluation(self):
        path=self.root/self.plan['jobs'][-1]['output_path']/'candidate_frozen.json';path.unlink()
        with self.assertRaises(FileNotFoundError):c.seal_delivery(self.root,self.plan_path)

    def test_duplicate_task_rejected(self):
        self.plan['jobs'][-1]=self.plan['jobs'][0];self.overwrite_fixture(self.plan_path,self.plan)
        with self.assertRaises(ValueError):c.seal_delivery(self.root,self.plan_path)

    def test_job_mutation_invalidates_plan(self):
        path=self.job();path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(ValueError):c.seal_delivery(self.root,self.plan_path)

    def test_records_are_exclusive(self):
        c.seal_delivery(self.root,self.plan_path)
        with self.assertRaises(FileExistsError):c.seal_delivery(self.root,self.plan_path)

    def test_duplicate_json_key_rejected(self):
        path=self.root/'duplicate.json';path.write_text('{"version":1,"version":2}',encoding='utf-8')
        with self.assertRaises(ValueError):c.read(path)


if __name__=='__main__':unittest.main(verbosity=2)
