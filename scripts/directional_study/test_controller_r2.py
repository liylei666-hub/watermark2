"""Exercise the actual supervisor branches with a fake process and idle gate."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import control_r2 as c

class Tests(unittest.TestCase):
    def exercise(self, waits, marker=True):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'runtime.json';manifest.write_text('{}')
            gate=types.SimpleNamespace(snapshot=None,verify_idle=lambda sample,record,*args:record({'synthetic_idle':True}))
            spec=types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda m:None))
            captured={};remaining=list(waits)
            class Process:
                pid=987654
                def __init__(self,argv,**kw):
                    captured.update(argv=argv,env=kw['env'])
                    out=Path(argv[-1]);(out/'summary.json').write_text('{"completed":true}')
                    if marker:kw['stdout'].write('COMPLETED_DIRECTION_PREPARATION\n');kw['stdout'].flush()
                def wait(self,timeout=None):
                    value=remaining.pop(0)
                    if value=='timeout':raise c.subprocess.TimeoutExpired('synthetic',timeout)
                    return value
            cfg=dict(allowed_gpu_uuids={'0':'GPU-synthetic'},max_new_bytes=10*1024**3,watchdog_seconds=1200)
            with patch.object(c.r,'ROOT',root),patch.object(c,'RUNTIME',manifest),patch.object(c,'ATTACK_RUNTIME',manifest),\
                patch.object(c.r,'verify_runtime',lambda p:cfg),\
                patch.object(c.importlib.util,'spec_from_file_location',return_value=spec),\
                patch.object(c.importlib.util,'module_from_spec',return_value=gate),\
                patch.object(c.subprocess,'Popen',Process),patch.object(c.os,'killpg') as kill:
                try:c.run_child('child','prepare.py',[],root,cfg);error=None
                except RuntimeError as exc:error=str(exc)
                record=json.loads((root/'child/execution.json').read_text())
                return record,error,kill.call_count,captured

    def test_success_records_actual_wait_result(self):
        row,error,kills,call=self.exercise([0])
        self.assertTrue(row['completed']);self.assertIsNone(error);self.assertEqual(kills,0)
        self.assertEqual(call['env']['CUDA_VISIBLE_DEVICES'],'GPU-synthetic')
        self.assertEqual(row['model_processes_started'],1)

    def test_timeout_records_termination(self):
        row,error,kills,_=self.exercise(['timeout',-15])
        self.assertTrue(row['timed_out']);self.assertFalse(row['completed']);self.assertEqual(kills,1)
        self.assertIsNotNone(error)

    def test_stalled_termination_records_kill(self):
        row,error,kills,_=self.exercise(['timeout','timeout',-9])
        self.assertEqual(row['exit_code'],-9);self.assertEqual(kills,2);self.assertIsNotNone(error)

    def test_zero_exit_without_completion_marker_rejected(self):
        row,error,kills,_=self.exercise([0],marker=False)
        self.assertFalse(row['completed']);self.assertIsNotNone(error)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps(dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        gpu_used=False,models_loaded=False,new_model_experiments_run=0,scope='mock subprocess and killpg only; no real process launched or signaled')))
    raise SystemExit(0 if result.wasSuccessful() else 1)
