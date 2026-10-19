"""CPU recovery checks: verified bytes are reused; conflicting artifacts are retained."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import tempfile,unittest,sys
from pathlib import Path
import common
finalize=common.load('cpu_finalizer_test',Path(__file__).with_name('finalize.py'))

class Recovery(unittest.TestCase):
    def test_existing_artifact_is_reused_and_conflict_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'result.json';self.assertEqual(finalize.retain(p,b'original'),'created');before=p.stat().st_mtime_ns
            self.assertEqual(finalize.retain(p,b'original'),'verified_existing');self.assertEqual(p.stat().st_mtime_ns,before)
            with self.assertRaises(ValueError):finalize.retain(p,b'changed')
            self.assertEqual(p.read_bytes(),b'original')
    def test_analysis_and_private_decoder_import_cpu_only(self):
        analysis=common.load('cpu_analysis_test',Path(__file__).with_name('analyze.py'))
        sys.path.insert(0,str(common.BASE/'cross_generator'))
        decoder=common.load('cpu_decoder_test',common.BASE/'cross_generator/verify_message_scores.py')
        self.assertTrue(callable(analysis.analyze));self.assertTrue(callable(decoder.decode));self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main()
