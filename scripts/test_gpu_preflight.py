import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import unittest
from gpu_preflight import verify_idle

class Tests(unittest.TestCase):
    def gate(self,values):
        events=[];iterator=iter(values)
        def sample(index):return next(iterator)
        result=verify_idle(sample,events.append,0,'uuid','model',max_samples=len(values),sleep=lambda _:None)
        return events,result
    def snap(self,util=0,apps=None,uuid='uuid'):
        return dict(row=['0',uuid,'model','24576','1',str(util)],compute_apps=apps or [])
    def test_transient_utilization_preserved_then_three_idle_samples(self):
        events,_=self.gate([self.snap(65),self.snap(),self.snap(),self.snap()])
        self.assertEqual(events[0]['row'][5],'65');self.assertEqual(events[-1]['samples'],4)
    def test_nonconsecutive_idle_is_insufficient(self):
        with self.assertRaisesRegex(RuntimeError,'stable idle'):
            self.gate([self.snap(),self.snap(10),self.snap()])
    def test_foreign_process_logged_and_rejected_immediately(self):
        events=[];calls=[]
        def sample(index):calls.append(index);return self.snap(apps=[['uuid','42','python','100']])
        with self.assertRaisesRegex(RuntimeError,'process present'):
            verify_idle(sample,events.append,0,'uuid','model',sleep=lambda _:None)
        self.assertEqual(len(calls),1);self.assertEqual(events[0]['compute_apps'][0][1],'42')
    def test_identity_logged_and_rejected(self):
        events=[]
        with self.assertRaisesRegex(RuntimeError,'identity mismatch'):
            verify_idle(lambda _:self.snap(uuid='other'),events.append,0,'uuid','model',sleep=lambda _:None)
        self.assertEqual(events[0]['row'][1],'other')
    def test_query_failure_logged(self):
        events=[]
        def sample(_):raise RuntimeError('query failed')
        with self.assertRaisesRegex(RuntimeError,'query failed'):
            verify_idle(sample,events.append,0,'uuid','model',sleep=lambda _:None)
        self.assertEqual(events[0]['event'],'query_error')

if __name__=='__main__':unittest.main()
