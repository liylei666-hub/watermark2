import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cpu_pilot',ROOT/'scripts/cpu_pilot.py')
pilot=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class PilotTests(unittest.TestCase):
    def test_threshold_ties_and_small_sample(self):
        self.assertEqual(pilot.fit([.8]*36,.05),.8)
        self.assertEqual(pilot.fit(list(range(36)),.05),1)
        for values in ([],[float('nan')],[float('inf')]):
            with self.assertRaises(ValueError):pilot.fit(values,.05)

    def test_manifest_has_complete_disjoint_source_groups(self):
        rows=json.loads((ROOT/'reports/cpu_pilot/manifest.json').read_text(encoding='utf-8'))
        source_splits={}
        for row in rows:
            source_splits.setdefault(row['source_id'],set()).add(row['split'])
        self.assertEqual(len(source_splits),18)
        self.assertTrue(all(len(v)==1 for v in source_splits.values()))
        expected={'reference','jpeg70','jpeg90','resize0.5','resize0.75','count','text','relation','process_control'}
        for sid in source_splits:
            self.assertEqual({r['variant'] for r in rows if r['source_id']==sid},expected)
        self.assertEqual(len({r['id'] for r in rows}),len(rows))

    def test_frozen_inputs_and_labels(self):
        frozen=pilot.load(ROOT/'reports/cpu_pilot/frozen_inputs.json')
        self.assertEqual(pilot.digest(ROOT/'configs/cpu_pilot.json'),frozen['config_sha256'])
        self.assertEqual(pilot.digest(ROOT/'reports/cpu_pilot/manifest.json'),frozen['manifest_sha256'])
        for row in pilot.load(ROOT/'reports/cpu_pilot/manifest.json'):
            self.assertEqual(row['facts']['count'],3 if row['variant']=='count' else 2)
            self.assertEqual(row['facts']['text'],'80' if row['variant']=='text' else '30')


if __name__=='__main__':unittest.main()
