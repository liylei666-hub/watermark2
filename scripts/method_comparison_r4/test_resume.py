"""CPU regression checks for duplicate prevention, resource waiting and wrapper imports."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import common
control=common.load('resume_control_test',Path(__file__).with_name('control.py'))
gate=common.load('resume_gate_test',Path(__file__).with_name('gate.py'))

class Resume(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.project=Path(self.temp.name);self.root=self.project/'runs/new';self.root.mkdir(parents=True);self.meta=dict(completed={},failed={})
    def tearDown(self):self.temp.cleanup()
    def test_started_unknown_is_not_pending(self):
        p=self.root/'task';p.mkdir();common.c.write(p/'process.json',dict(pid=123))
        self.assertEqual(control.state(self.root,'task',self.meta),'unknown_launched')
        with patch.object(control,'choose',side_effect=AssertionError('must not acquire GPU')):
            with self.assertRaisesRegex(RuntimeError,'cannot be retried'):control.run_child(self.root,{},self.meta,'task','attack.py',[])
    def test_failure_is_not_pending(self):
        p=self.root/'task';p.mkdir();common.c.write(p/'execution.json',dict(completed=False,exit_code=1,timed_out=False))
        self.assertEqual(control.state(self.root,'task',self.meta),'failed')
    def test_inherited_failure_never_relaunches(self):
        p=self.project/'runs/old/task';p.mkdir(parents=True);common.c.write(p/'execution.json',dict(completed=False,exit_code=1))
        self.meta['failed']['task']=dict(path='runs/old/task',sha256=common.c.sha(p/'execution.json'))
        with patch.object(control,'choose',side_effect=AssertionError('must not acquire GPU')):control.run_child(self.root,{},self.meta,'task','attack.py',[])
    def test_completed_not_relaunched(self):
        p=self.root/'task';p.mkdir();common.c.write(p/'execution.json',dict(completed=True,exit_code=0,timed_out=False))
        with patch.object(control,'choose',side_effect=AssertionError('must not acquire GPU')):control.run_child(self.root,{},self.meta,'task','attack.py',[])
    def test_busy_waits_without_task_reservation(self):
        cfg=dict(allowed_gpu_uuids={'0':'GPU-test'},resource_recheck_seconds=300);calls=[]
        def sample(*args):
            calls.append(1)
            if len(calls)==1:raise RuntimeError('GPU compute process present')
        def sleep(seconds):
            self.assertEqual(common.c.read(self.root/'scheduler_status.json')['status'],'waiting_resource');self.assertFalse((self.root/'task').exists());self.assertEqual(seconds,300)
        with patch.object(control,'gate_functions',return_value=dict(verify_idle=sample,snapshot=None)),patch.object(control.time,'sleep',side_effect=sleep):
            self.assertEqual(control.choose(self.root,cfg,'task',self.meta)[:2],(0,'GPU-test'))
    def test_wrapper_imports_without_cuda_import(self):
        import sys
        attack=common.load('resume_attack_test',Path(__file__).with_name('attack.py'))
        evaluate=common.load('resume_evaluate_test',Path(__file__).with_name('evaluate.py'))
        self.assertNotIn('torch',sys.modules);self.assertTrue(callable(attack.original.main));self.assertTrue(callable(evaluate.main));self.assertEqual(common.r.check_device.__name__,'check_device')

class Gate(unittest.TestCase):
    def row(self,u=0,apps=None,index='0',memory=4):return dict(row=[index,'GPU-test','NVIDIA GeForce RTX 3090','24576',str(memory),str(u)],compute_apps=apps or [])
    def call(self,rows):
        events=[];it=iter(rows);result=gate.gate_functions()['verify_idle'](lambda _:next(it),events.append,0,'GPU-test','NVIDIA GeForce RTX 3090',max_samples=len(rows),sleep=lambda _:None);return result,events
    def test_transient_requires_three_idle(self):self.assertEqual(self.call([self.row(1)]+[self.row()]*3)[1][-1]['samples'],4)
    def test_interruption_resets(self):self.assertEqual(self.call([self.row(),self.row(),self.row(1)]+[self.row()]*3)[1][-1]['samples'],6)
    def test_process_fails(self):
        with self.assertRaises(RuntimeError):self.call([self.row(apps=[['GPU-test','123','foreign','100']])]*3)
    def test_busy_fails(self):
        with self.assertRaises(RuntimeError):self.call([self.row(1)]*15)
    def test_identity_fails(self):
        with self.assertRaises(RuntimeError):self.call([self.row(index='1')]*3)
    def test_memory_fails(self):
        with self.assertRaises(RuntimeError):self.call([self.row(memory=1000)]*3)

if __name__=='__main__':unittest.main()
