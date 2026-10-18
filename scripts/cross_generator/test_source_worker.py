"""CPU source-plan validation; no upstream/provider execution."""
import ast
import copy
from pathlib import Path
import tempfile
import unittest
import io_contract as c
from source_worker import jobs


class SourcePlanTests(unittest.TestCase):
    def test_plan_matches_frozen_scientific_design(self):
        root = Path(__file__).resolve().parents[2]
        design = c.read(root / 'protocols/24_cross_generator_design.json')
        source = design['tasks'][:24]
        plan = dict(version=1, model={}, batches=[source[i:i+4] for i in range(0,24,4)],
                    design_sha256=c.sha(root / 'protocols/24_cross_generator_design.json'))
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'jobs.json'; c.write(path, plan)
            self.assertEqual(jobs(path, {'source_jobs_sha256':c.sha(path)})['batches'], plan['batches'])
            with self.assertRaises(ValueError): jobs(path, {'source_jobs_sha256':'0'*64})
            for field, value in [('generator_role','target'), ('role','target_test'), ('noise_distribution','GS')]:
                changed = copy.deepcopy(plan); changed['batches'][0][0][field] = value
                path.unlink(); c.write(path, changed)
                with self.assertRaises(ValueError): jobs(path, {'source_jobs_sha256':c.sha(path)})

    def test_gpu_import_follows_device_check(self):
        tree = ast.parse(Path(__file__).with_name('source_worker.py').read_bytes())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        imports = [n for n in ast.walk(main) if isinstance(n, ast.Import) and any(a.name == 'torch' for a in n.names)]
        checks = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'check_device']
        self.assertEqual(len(imports), 1); self.assertEqual(len(checks), 1)
        self.assertLess(checks[0].lineno, imports[0].lineno)
        self.assertFalse(any(isinstance(n, ast.Import) and any(a.name == 'torch' for a in n.names) for n in tree.body))


if __name__ == '__main__':
    unittest.main()
