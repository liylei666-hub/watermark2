import copy
import tempfile
import unittest
from pathlib import Path
import common as c


class Contract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg={'inputs':{}}
        for key,relative in c.expected_inputs().items():
            p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(key.encode())
            self.cfg['inputs'][key]=dict(path=c.REMOTE+'/'+relative,sha256=c.sha(p))

    def test_complete_group(self): self.assertEqual(len(c.validate(self.cfg,self.root)),12)

    def test_missing_candidate(self):
        del self.cfg['inputs']['2/jain']
        with self.assertRaises(ValueError):c.validate(self.cfg,self.root)

    def test_target_noise_substitution(self):
        self.cfg['inputs']['1/reference']['path']=c.REMOTE+'/'+c.RUN+'/evaluator_private/reference/1/original_noise.npy'
        with self.assertRaises(ValueError):c.validate(self.cfg,self.root)

    def test_image_tamper(self):
        (self.root/c.expected_inputs()['3/imprint']).write_bytes(b'changed')
        with self.assertRaises(ValueError):c.validate(self.cfg,self.root)

    def test_extra_score(self):
        self.cfg['inputs']['score']=copy.deepcopy(self.cfg['inputs']['1/reference'])
        with self.assertRaises(ValueError):c.validate(self.cfg,self.root)


if __name__=='__main__':unittest.main(verbosity=2)
