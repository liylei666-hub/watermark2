"""Linux CPU supervisor simulation: fixed tasks, stop rules, evaluation ordering."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only tests')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import contract as c
import bundle as b
import control as ctl


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'runs').mkdir();self.protocol=self.root/'protocol.json';c.write(self.protocol,dict(version=1))
        self.protocol.with_suffix('.sha256').write_text(c.sha(self.protocol))
        self.runtime=self.root/'runtime.json';c.write(self.runtime,dict(version=1))
        self.calls=[];self.fail_at=None
        for name,value in [('PROTOCOL',self.protocol),('RUNTIME',self.runtime)]:
            p=patch.object(ctl,name,value);p.start();self.addCleanup(p.stop)
        p=patch.object(ctl.r,'ROOT',self.root);p.start();self.addCleanup(p.stop)
        p=patch.object(ctl.r,'verify_runtime',return_value={});p.start();self.addCleanup(p.stop)

    def fake_child(self,name,script,args,root,cfg):
        self.calls.append((name,script));out=root/name;out.mkdir(parents=True)
        if name==self.fail_at:raise RuntimeError('Synthetic child failure')
        if script=='prepare.py':
            role=args[1]
            for task in [1,2,3]:
                folder=out/str(task);folder.mkdir()
                Image.new('RGB',(512,512),(task,20 if role=='reference' else 150,80)).save(folder/(role+'.png'))
        elif script=='attack.py':
            self.assertFalse((root/'delivery_sealed.json').exists())
            Image.new('RGB',(512,512),(80,100,50)).save(out/'candidate.png');c.freeze_candidate(out,args[0])
        elif script=='evaluate.py':
            self.assertEqual(len([x for x in self.calls if x[1]=='attack.py']),6)
            self.assertEqual(len(b.evaluation_queue(root,root/'attack_plan.json')),12)
        return out

    def test_all_attacks_precede_single_evaluation(self):
        with patch.object(ctl,'run_child',side_effect=self.fake_child):ctl.main()
        self.assertEqual([s for _,s in self.calls],['prepare.py']*2+['attack.py']*6+['evaluate.py'])
        folder=next((self.root/'runs').glob('17_cover_pilot_*'))
        self.assertTrue(c.read(folder/'status.json')['completed'])

    def test_failure_stops_without_evaluation_or_retry(self):
        self.fail_at='attack_outputs/1/jain'
        with patch.object(ctl,'run_child',side_effect=self.fake_child):
            with self.assertRaises(RuntimeError):ctl.main()
            with self.assertRaises(RuntimeError):ctl.main()
        self.assertEqual([s for _,s in self.calls],['prepare.py']*2+['attack.py']*2)
        folder=next((self.root/'runs').glob('17_cover_pilot_*'))
        self.assertFalse(c.read(folder/'status.json')['completed'])
        self.assertFalse((folder/'delivery_sealed.json').exists())

    def test_existing_attempt_prevents_duplicate_launch(self):
        folder=self.root/'runs/17_cover_pilot_fixture';folder.mkdir();c.write(folder/'launch_intent.json',{})
        with patch.object(ctl,'run_child') as child:
            with self.assertRaises(RuntimeError):ctl.main()
            child.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
