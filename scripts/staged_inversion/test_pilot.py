"""CPU decision and single-card orchestration regressions for the frozen pilot."""
import copy,json,os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import common as m
import control
import analyze
import freeze

DESIGN=json.loads((Path(__file__).resolve().parents[2]/'protocols/28_staged_design.json').read_text())


def rows():
    result=[]
    for sid in range(1,5):
        for kind in ('reference','cover')+m.METHODS:
            ba={'reference':1.,'cover':.5,'native50':.70,'short10':.71,'staged10_50':.75}[kind]
            result.append(dict(task_id=sid,kind=kind,bit_accuracy=ba,gs_detected=ba>.70703125,
                cover_mse_rgb01=.001 if kind in m.METHODS else None,
                core_seconds=400 if kind in m.METHODS else None))
    return result


class Decisions(unittest.TestCase):
    def test_attack_runtime_pins_exclude_target_config_and_private_state(self):
        sources={'/project/scripts/attack.py':'a','/project/models/proxy/config.json':'b',
                 '/project/models/target/config.json':'c','/project/protocols/design.json':'d',
                 '/project/private_eval/1.bin':'e'}
        self.assertEqual(set(freeze.attack_source_pins(sources,'/project/models/proxy')),
                         {'/project/scripts/attack.py','/project/models/proxy/config.json'})
    def test_stage_boundary_and_work_accounting(self):
        self.assertEqual(m.schedule('staged10_50'),[dict(inversion_steps=10,updates=30),dict(inversion_steps=50,updates=4)])
        for method in m.METHODS:
            self.assertEqual(sum(p['updates']*p['inversion_steps'] for p in m.schedule(method)),500)
        self.assertEqual(DESIGN['target'],json.loads((Path(__file__).resolve().parents[2]/'protocols/27_method_design.json').read_text())['target'])
    def test_all_gates_required(self):
        self.assertEqual(m.decide(rows(),DESIGN['decision_rule'])['decision'],'advance_to_independent_confirmation')
        data=rows()
        for row in data:
            if row['kind']=='staged10_50':row['cover_mse_rgb01']=.0012
        self.assertEqual(m.decide(data,DESIGN['decision_rule'])['decision'],'close_fixed_staged_candidate')
    def test_short_control_removes_staged_explanation(self):
        data=rows()
        for row in data:
            if row['kind']=='short10':row['bit_accuracy']=.75
        self.assertEqual(m.decide(data,DESIGN['decision_rule'])['decision'],'close_fixed_staged_candidate')
    def test_reference_or_measured_budget_mismatch_is_inconclusive(self):
        for mode in ('reference','cost'):
            data=rows()
            for row in data:
                if mode=='reference' and row['kind']=='reference':row['gs_detected']=False
                if mode=='cost' and row['kind']=='short10':row['core_seconds']=460
            self.assertTrue(m.decide(data,DESIGN['decision_rule'])['decision'].startswith('inconclusive'))
    def test_missing_or_duplicate_evidence_is_inconclusive(self):
        self.assertTrue(m.decide(rows()[:-1],DESIGN['decision_rule'])['decision'].startswith('inconclusive'))
        self.assertTrue(m.decide(rows()+[rows()[0]],DESIGN['decision_rule'])['decision'].startswith('inconclusive'))


class Orchestration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='stage28_test_',dir=Path(__file__).resolve().parents[2]);self.root=Path(self.temp.name)
        for folder in ('runs','private_eval','protocols'): (self.root/folder).mkdir()
        self.runtime=self.root/'protocols/controller.json';self.runtime.write_text('{}')
        self.cfg=dict(device=dict(index=0,uuid='GPU-test-0',model='CPU fixture'),run_dir='runs/test',private_folder='private_eval/test',
            runtime_paths={role:'protocols/controller.json' for role in ('controller','attacker','evaluator')},
            runtime_sha256={role:m.c.sha(self.runtime) for role in ('attacker','evaluator')},
            max_new_bytes=10*1024**3,source_commit='fixture',watchdog_seconds=20,design=DESIGN,proxy=DESIGN['proxy'])
        self.calls=[]
    def tearDown(self):self.temp.cleanup()
    def run_fixture(self,fail=None):
        calls=self.calls;cfg=self.cfg
        class Runner(control.PilotRunner):
            def __call__(self,job,device,output,environment):
                from PIL import Image
                calls.append(job.name)
                self.assertions(job,device,environment)
                if job.name==fail:return dict(completed=False,exit_code=1)
                if job.name.startswith('prepare_'):
                    role=job.name[len('prepare_'):]
                    for sid in range(1,5):
                        out=output/str(sid);out.mkdir()
                        Image.new('RGB',(512,512),(sid,0,1)).save(out/(role+'.png'))
                elif job.name.startswith('attack_'):
                    path=Path(self.commands[job.name][1][0]);data=m.validate_job(path,cfg)
                    self.assertions_private(data)
                    Image.new('RGB',(512,512),(2,1,0)).save(output/'candidate.png')
                    m.c.write(output/'candidate_frozen.json',dict(task_id=data['task_id'],method=data['method'],
                        job_sha256=m.c.sha(path),image=m.c.png_record(output/'candidate.png')))
                else:
                    m.verify_seal(output.parent)
                    if len(calls)!=15:raise AssertionError('Premature evaluation')
                return dict(completed=True,exit_code=0)
            def assertions(self,job,device,environment):
                if device.index!=0 or environment['CUDA_VISIBLE_DEVICES']!=device.uuid:raise AssertionError('Device mismatch')
            def assertions_private(self,data):
                if any(k in data for k in ('key','message','nonce','target','original_noise','private_folder')):raise AssertionError('Private attacker input')
        with patch.object(control,'ROOT',self.root),patch.object(control.launch,'check_host',lambda _:None),\
             patch.object(control.r,'verify_runtime',lambda _:self.cfg),patch.object(control.sched,'verify_idle',lambda *args:True),\
             patch.object(control,'PilotRunner',Runner),patch.object(analyze,'analyze',lambda *args:dict(decision={'decision':'fixture'})):
            # A synthetic finalizer writes its result so final seal verification also runs.
            def finish(*args):
                result=dict(decision={'decision':'fixture'});m.c.write(args[0]/'analysis.json',result);return result
            with patch.object(analyze,'analyze',finish):control.run(self.runtime)
    def test_complete_order_sealing_and_attacker_boundary(self):
        self.run_fixture()
        self.assertEqual(len(self.calls),15)
        self.assertEqual(self.calls[:2],['prepare_reference','prepare_cover'])
        self.assertEqual(self.calls[-1],'evaluate')
        self.assertEqual(len(set(self.calls)),15)
        self.assertEqual(m.c.read(self.root/'runs/test/scheduler_status.json')['state'],'completed')
        self.assertTrue((self.root/'runs/test/results_sealed.json').exists())
    def test_failed_child_stops_without_retry_or_evaluation(self):
        with self.assertRaises(RuntimeError):self.run_fixture(fail='attack_1_short10')
        self.assertEqual(self.calls[-1],'attack_1_short10')
        self.assertNotIn('evaluate',self.calls)
        before=self.calls.copy()
        with self.assertRaises(ValueError):self.run_fixture()
        self.assertEqual(self.calls,before)
    def test_existing_project_owner_prevents_claims(self):
        with m.sched.project_lock(self.root/'runs/.imprint_delivery.lock'):
            with self.assertRaises(OSError):self.run_fixture()
        self.assertFalse((self.root/'runs/test').exists())


if __name__=='__main__':unittest.main()
