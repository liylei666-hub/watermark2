"""Publish an immutable, fully validated data receipt with an exclusive atomic link."""
import hashlib,json,os
from pathlib import Path
def publish_ready(staging,final,body):
 staging,final,body=map(Path,(staging,final,body))
 if staging.parent.resolve()!=final.parent.resolve():raise ValueError('Same-filesystem receipt directory required')
 receipt=json.loads(staging.read_text(encoding='utf8'))
 h=hashlib.sha256()
 with body.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 if body.stat().st_size!=receipt['bytes'] or h.hexdigest()!=receipt['sha256']:raise ValueError('Body/receipt integrity mismatch')
 if receipt.get('tls_verification_disabled') is not False:raise ValueError('Normal TLS verification required')
 os.link(staging,final)
 return receipt
