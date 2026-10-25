import hashlib,json,tempfile,unittest
from pathlib import Path
from confirmation_ready import publish_ready
class AtomicReady(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]);self.root=Path(self.tmp.name);self.body=self.root/'body';self.body.write_bytes(b'complete data');self.stage=self.root/'receipt.uploading';self.final=self.root/'receipt.ready.json';self.record=dict(bytes=13,sha256=hashlib.sha256(b'complete data').hexdigest(),tls_verification_disabled=False)
 def tearDown(self):self.tmp.cleanup()
 def test_incomplete_receipt_never_visible(self):
  self.stage.write_bytes(b'')
  with self.assertRaises(json.JSONDecodeError):publish_ready(self.stage,self.final,self.body)
  self.assertFalse(self.final.exists())
 def test_complete_receipt_is_published_and_staging_retained(self):
  self.stage.write_text(json.dumps(self.record));publish_ready(self.stage,self.final,self.body);self.assertEqual(json.loads(self.final.read_text()),self.record);self.assertEqual(self.final.read_bytes(),self.stage.read_bytes())
 def test_mismatched_body_never_published(self):
  self.record['sha256']='0'*64;self.stage.write_text(json.dumps(self.record))
  with self.assertRaises(ValueError):publish_ready(self.stage,self.final,self.body)
  self.assertFalse(self.final.exists())
 def test_existing_receipt_never_overwritten(self):
  self.stage.write_text(json.dumps(self.record));self.final.write_text('preserved')
  with self.assertRaises(FileExistsError):publish_ready(self.stage,self.final,self.body)
  self.assertEqual(self.final.read_text(),'preserved')
if __name__=='__main__':unittest.main()
