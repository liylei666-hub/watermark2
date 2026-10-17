"""Run established synthetic core checks through the new extraction boundary."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU only')
import importlib.util
import unittest
from pathlib import Path
from experiment import definitions
root=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('checks',root/'scripts/test_cover_baseline_adapter_r2.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.SOURCE_ROOT=root/'audit_sources/jain_0443396'
def route(relative,names):
    return definitions(dict(path=str(m.SOURCE_ROOT/relative),sha256=m.HASHES[relative]),names)
m.definitions=route
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(m.AdapterTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
