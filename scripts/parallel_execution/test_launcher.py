"""Real CPU subprocess integration; synthetic models and explicit test-only gates."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import launcher as L
import scheduler as s

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

ENTRY = '''import json, os, sys, time
from pathlib import Path
p=json.loads(Path(sys.argv[1]).read_text()); out=Path(sys.argv[2])
with (out/'invoked').open('x') as f: f.write('once')
if p.get('barrier'):
    (out/'ready').write_text('ready'); deadline=time.monotonic()+8
    while len(list(out.parent.glob('attack*_first/ready')))<p['barrier']:
        assert time.monotonic()<deadline, 'CPU subprocess concurrency barrier expired'
        time.sleep(.01)
if p.get('sleep'): time.sleep(p['sleep'])
if p.get('crash'): raise RuntimeError('synthetic child failure')
if p['phase']=='attack': (out/'candidate.png').write_bytes(p['name'].encode())
else: assert (out.parent/'candidates_sealed.json').is_file()
(out/'summary.json').write_text(json.dumps(dict(completed=True, uuid=os.environ['CUDA_VISIBLE_DEVICES'])))
print('FIXTURE_COMPLETED', flush=True)
'''
GATE = '''import os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'scripts/parallel_execution'))
import launcher as L
import scheduler as s
import worker
L.check_host=lambda project: None
L.sample=lambda index: dict(index=index,uuid='GPU-test-'+str(index),model='CPU fixture',memory_used_mib=0,utilization_percent=0,compute_apps=[])
original=s.verify_idle
s.verify_idle=lambda device,sample,record: original(device,sample,record,sleep=lambda seconds:None)
worker.main()
'''


class FixtureRunner(L.ProcessRunner):
    def command(self, job, device, output):
        command = super().command(job, device, output)
        command[1] = str(self.project / 'fixture_gate.py')
        return command


class Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        source = self.root / 'scripts/parallel_execution'
        source.mkdir(parents=True)
        for name in ('launcher.py', 'worker.py', 'scheduler.py'):
            shutil.copyfile(L.HERE / name, source / name)
        self.source_patch = patch.object(L, 'HERE', source)
        self.source_patch.start()
        (self.root / 'entry.py').write_text(ENTRY)
        (self.root / 'fixture_gate.py').write_text(GATE)
        revision = 'a' * 40
        model = self.root / 'models' / revision
        model.mkdir(parents=True)
        (model / 'fixture.bin').write_bytes(b'CPU synthetic model identity only')
        (self.root / 'model_manifest.json').write_text(json.dumps({'fixture.bin': L.sha(model / 'fixture.bin')}))
        self.plan = dict(schema=1, run_name='parallel_cpu_fixture', python_version=sys.version.split()[0],
            versions={'pip': importlib.metadata.version('pip')}, methods=['first', 'second'],
            devices=[dict(index=i, uuid='GPU-test-'+str(i), model='CPU fixture') for i in (0, 1, 2, 7)],
            models=[dict(snapshot='models/'+revision, revision=revision, manifest='model_manifest.json')],
            files={}, resource_wait_seconds=0, attack_groups=[], evaluation_groups=[])
        for i in range(4):
            self.plan['attack_groups'].append(dict(name='task'+str(i), jobs=[self.job('attack'+str(i)+'_'+m, 'attack', m) for m in self.plan['methods']]))
        self.plan['evaluation_groups'] = [dict(name='evaluation', jobs=[self.job('evaluate', 'evaluation', None)])]
        self.freeze()

    def job(self, name, phase, method):
        (self.root / (name+'.json')).write_text(json.dumps(dict(name=name, phase=phase)))
        return dict(name=name, method=method, entry='entry.py', parameters=name+'.json',
                    argv=['{parameters}', '{output}'], watchdog_seconds=20,
                    output_limit_bytes=1024**2, completion_marker='FIXTURE_COMPLETED')

    def freeze(self):
        self.path = self.root / 'plan.json'
        self.plan['files'] = {p.relative_to(self.root).as_posix(): L.sha(p) for p in self.root.rglob('*')
            if p.is_file() and p != self.path and not p.is_relative_to(self.root / 'runs')
            and not p.is_relative_to(self.root / 'models')}
        self.path.write_text(json.dumps(self.plan, indent=2))
        self.digest = L.sha(self.path)

    def tearDown(self):
        self.source_patch.stop()
        self.temp.cleanup()

    def scheduler(self, resume=False, gate=None):
        plan, devices, groups, jobs, phases = L.load_plan(self.root, self.path, self.digest)
        runner = FixtureRunner(self.root, self.path, self.digest, jobs, phases)
        return s.Scheduler(self.root, plan['run_name'], devices, groups['attack'], groups['evaluation'],
            runner, gate or (lambda device: True), resource_wait_seconds=0, resume=resume)

    def test_real_subprocess_logs_gpu_affinity_barrier_and_result_seals(self):
        for i in range(4):
            path = self.root/f'attack{i}_first.json'
            params = L.read(path); params['barrier'] = 4
            path.write_text(json.dumps(params))
        self.freeze()
        result = self.scheduler().run()
        self.assertTrue(result['completed'], result)
        root = self.root / 'runs' / self.plan['run_name']
        self.assertEqual(len(result['completed_jobs']), 9)
        self.assertEqual(len(L.read(root/'results_sealed.json')['executions']), 9)
        for i in range(4):
            records = [L.read(root/f'attack{i}_{m}'/'execution.json') for m in self.plan['methods']]
            self.assertEqual(records[0]['gpu_uuid'], records[1]['gpu_uuid'])
        for name in result['completed_jobs']:
            output = root/name
            self.assertTrue(L.read(output/'child_preimport.json')['idle'])
            self.assertTrue(L.read(output/'process.json')['pid'] > 0)
            self.assertEqual((output/'invoked').read_text(), 'once')
            record = L.read(output/'execution.json')
            self.assertEqual(record['outcome']['artifacts']['stdout.log'], L.sha(output/'stdout.log'))
        with self.assertRaises(ValueError):
            self.scheduler(resume=True).run()

    def test_dry_run_cli_enumerates_without_gpu_or_output(self):
        command = [sys.executable, str(L.HERE/'launcher.py'), '--project', str(self.root), '--plan', str(self.path),
                   '--plan-sha256', self.digest, '--dry-run']
        result = subprocess.run(command, capture_output=True, text=True, env=os.environ, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['maximum_concurrent_processes'], 4)
        self.assertEqual(report['model_processes_started'], 0)
        self.assertFalse((self.root/'runs').exists())

    def test_gpu6_and_five_devices_rejected(self):
        for indices in ((0, 1, 2, 6), (0, 1, 2, 3, 7)):
            self.plan['devices'] = [dict(index=i, uuid='GPU-test-'+str(i), model='CPU fixture') for i in indices]
            self.freeze()
            with self.assertRaises(ValueError): self.scheduler()
        self.assertFalse((self.root/'runs').exists())

    def test_model_or_parameter_mutation_refused_before_claim(self):
        (self.root/'attack0_first.json').write_text('{}')
        with self.assertRaises(ValueError): self.scheduler()
        self.assertFalse((self.root/'runs').exists())

    def test_changed_local_model_refused_before_claim(self):
        (self.root/'models'/('a'*40)/'fixture.bin').write_bytes(b'changed model')
        with self.assertRaisesRegex(ValueError, 'model file changed'): self.scheduler()
        self.assertFalse((self.root/'runs').exists())

    def test_child_rejects_wrong_uuid_before_entry_import(self):
        scheduler = self.scheduler()
        output = scheduler.root/'attack0_first'; output.mkdir(parents=True)
        runner = scheduler.runner
        command = runner.command(scheduler.attacks[0].jobs[0], scheduler.devices[0], output)
        result = subprocess.run(command, capture_output=True, text=True, timeout=20,
            env=dict(os.environ, CUDA_VISIBLE_DEVICES='GPU-test-7'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Child GPU/offline environment differs', result.stderr)
        self.assertFalse((output/'invoked').exists())

    def test_output_allowance_enforced(self):
        self.plan['devices'] = self.plan['devices'][:1]
        self.plan['attack_groups'][0]['jobs'][0]['output_limit_bytes'] = 1
        self.freeze()
        result = self.scheduler().run()
        root = self.root/'runs'/self.plan['run_name']
        outcome = L.read(root/'attack0_first/execution.json')['outcome']
        self.assertFalse(result['completed'])
        self.assertEqual(outcome['stop_reason'], 'output_allowance_exceeded')
        self.assertFalse((root/'evaluate').exists())

    def test_incomplete_method_group_refused(self):
        self.plan['attack_groups'][0]['jobs'].pop()
        self.freeze()
        with self.assertRaises(ValueError): self.scheduler()

    def test_production_launcher_refuses_local_host(self):
        with self.assertRaises(ValueError):
            L.execute(self.root, self.path, self.digest)
        self.assertFalse((self.root/'runs').exists())

    def test_watchdog_records_failure_blocks_evaluation_and_no_retry(self):
        self.plan['devices'] = self.plan['devices'][:1]
        spec = self.plan['attack_groups'][0]['jobs'][0]
        spec['watchdog_seconds'] = .3
        path = self.root/spec['parameters']; params = L.read(path); params['sleep'] = 3
        path.write_text(json.dumps(params)); self.freeze()
        result = self.scheduler().run()
        self.assertEqual(result['failed_jobs'], ['attack0_first'])
        root = self.root/'runs'/self.plan['run_name']
        self.assertEqual(L.read(root/'attack0_first/execution.json')['outcome']['stop_reason'], 'watchdog_expired')
        before = (root/'attack0_first/execution.json').read_bytes()
        with self.assertRaises(ValueError): self.scheduler(resume=True).run()
        self.assertEqual(before, (root/'attack0_first/execution.json').read_bytes())
        self.assertFalse((root/'evaluate').exists())

    def test_boundary_recovery_preserves_completed_method_device_and_no_duplicates(self):
        first = 'attack0_first'
        def interrupted_gate(device):
            if (self.root/'runs'/self.plan['run_name']/first/'execution_seal.json').exists():
                raise RuntimeError('synthetic interruption at a clean task boundary')
            return device.index == 1
        # One group ensures the simulated interruption occurs after exactly one method.
        self.plan['attack_groups'] = self.plan['attack_groups'][:1]
        self.freeze()
        result = self.scheduler(gate=interrupted_gate).run()
        self.assertEqual(result['completed_jobs'], [first])
        root = self.root/'runs'/self.plan['run_name']
        original = (root/first/'execution.json').read_bytes()
        recovered = self.scheduler(resume=True).run()
        self.assertTrue(recovered['completed'], recovered)
        self.assertEqual(original, (root/first/'execution.json').read_bytes())
        self.assertEqual(L.read(root/'attack0_second/execution.json')['gpu_index'], 1)
        self.assertTrue((root/'recovery_status_1.json').exists())
        self.assertFalse(L.read(root/'status.json')['completed'])

    def test_ambiguous_live_child_claim_blocks_recovery_without_killing_it(self):
        scheduler = self.scheduler(gate=lambda device: False)
        scheduler.run()
        root = scheduler.root
        output = root/'attack0_first'; output.mkdir()
        s.write_once(output/'claim.json', dict(job='attack0_first'))
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
        try:
            s.write_once(output/'process.json', dict(pid=child.pid))
            with self.assertRaisesRegex(ValueError, 'Ambiguous'):
                self.scheduler(resume=True).run()
            self.assertIsNone(child.poll())
        finally:
            child.kill(); child.wait()

    def test_recovery_rejects_tampered_completed_artifact(self):
        self.plan['attack_groups'] = self.plan['attack_groups'][:1]; self.freeze()
        def boundary(device):
            if (self.root/'runs'/self.plan['run_name']/'attack0_first/execution.json').exists():
                raise RuntimeError('boundary stop')
            return True
        self.scheduler(gate=boundary).run()
        output = self.root/'runs'/self.plan['run_name']/'attack0_first'
        (output/'stdout.log').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            self.scheduler(resume=True).run()


if __name__ == '__main__':
    unittest.main()
