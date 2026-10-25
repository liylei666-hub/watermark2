import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import hashlib,json,tempfile,unittest
from pathlib import Path
import relay_confirmation100_assets as r
class RelayGates(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]);self.base=Path(self.temp.name)
  self.saved={n:getattr(r.a,n) for n in ('ROOT','DATA','PUBLIC','budget')};self.incoming=r.INCOMING
  r.a.ROOT=self.base;r.a.DATA=self.base/'data';r.a.PUBLIC=self.base/'report';r.a.budget=lambda *a:None;r.INCOMING=r.a.DATA/'incoming'
  r.INCOMING.mkdir(parents=True);(r.a.PUBLIC/'requests').mkdir(parents=True);(r.a.PUBLIC/'transfers').mkdir();r.sequence=1
 def tearDown(self):
  for n,v in self.saved.items():setattr(r.a,n,v)
  r.INCOMING=self.incoming;self.temp.cleanup()
 def receipt(self,**kwargs):
  data=b'fixture';p=r.INCOMING/'001.bin';p.write_bytes(data)
  rec=dict(index=1,canonical_url='https://images.cocodataset.org/val2017/000000000139.jpg',actual_source_url='https://storage.googleapis.com/images.cocodataset.org/val2017/000000000139.jpg',tls_verification_disabled=False,http_status=200,bytes=len(data),sha256=hashlib.sha256(data).hexdigest());rec.update(kwargs)
  (r.INCOMING/'001.ready.json').write_text(json.dumps(rec));return rec
 def run_fetch(self):return r.fetch('https://images.cocodataset.org/val2017/000000000139.jpg',r.a.DATA/'139.jpg',100)
 def test_exact_bytes_finalized_and_receipt_bound(self):
  rec=self.receipt();result=self.run_fetch();self.assertEqual(result['sha256'],rec['sha256']);self.assertEqual((r.a.DATA/'139.jpg').read_bytes(),b'fixture');self.assertFalse((r.INCOMING/'001.bin').exists())
 def test_hash_mismatch_preserves_incoming(self):
  self.receipt(sha256='0'*64)
  with self.assertRaises(AssertionError):self.run_fetch()
  self.assertTrue((r.INCOMING/'001.bin').exists());self.assertFalse((r.a.DATA/'139.jpg').exists())
 def test_other_image_or_unknown_host_rejected(self):
  self.receipt(actual_source_url='https://storage.googleapis.com/images.cocodataset.org/val2017/000000000140.jpg')
  with self.assertRaises(AssertionError):self.run_fetch()
 def test_disabled_tls_rejected(self):
  self.receipt(tls_verification_disabled=True)
  with self.assertRaises(AssertionError):self.run_fetch()
 def test_frozen_150_candidate_ceiling(self):
  r.sequence=151
  with self.assertRaises(ValueError):self.run_fetch()
if __name__=='__main__':unittest.main()
