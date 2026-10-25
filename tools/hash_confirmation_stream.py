"""Hash the complete relayed annotation ZIP without storing a duplicate package."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only data integrity check')
import datetime,hashlib,json,sys
from pathlib import Path
import prepare_confirmation100_assets as a
a.host();destination=a.ROOT/'datasets/confirmation100_relay_v1'
destination.mkdir(exist_ok=True)
receipt=destination/'full_zip_stream_verification.json'
if receipt.exists():raise SystemExit('Existing hash receipt: inspect rather than repeat transfer')
h=hashlib.sha256();n=0
for b in iter(lambda:sys.stdin.buffer.read(1024*1024),b''):
 n+=len(b)
 if n>252907541:raise SystemExit('Stream exceeds fixed package size')
 h.update(b)
assert n==252907541 and h.hexdigest()=='113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268'
record=dict(verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),bytes=n,sha256=h.hexdigest(),complete_zip_stream_hashed=True,full_zip_copy_stored_on_server=False,chunk_bytes=1024*1024,transport='Existing verified SSH identity/host, stdin stream',models_started=0,gpu_used=False)
with receipt.open('x') as f:json.dump(record,f,indent=2);f.write('\n')
print(json.dumps(record))
