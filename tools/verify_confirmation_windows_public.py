"""Offline audit of two Windows HTTPS attempts and preserved server failures."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU-only verification')
import hashlib,json
from pathlib import Path
from verify_confirmation_assets_retry_public import verify as verify_server
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def verify(root):
 root=Path(root);server=verify_server(root);rows=[]
 for name in ['confirmation100_assets_windows_v1','confirmation100_assets_windows_retry1']:
  out=root/'reports'/name;launch=read(out/'launch.json');terminal=read(out/'terminal.json');seal=read(out/'result_seal.json');receipt=read(out/'verification.json')
  for n,record in seal['files'].items():assert (out/n).stat().st_size==record['bytes'] and sha(out/n)==record['sha256']
  fields=(out/'metadata.curl.txt').read_text(encoding='utf-8-sig').splitlines()
  assert terminal['curl_exit_code']==60 and fields[:3]==['000','0','0']
  assert b'SEC_E_WRONG_PRINCIPAL' in (out/'metadata.stderr.log').read_bytes()
  assert launch['url']==read(root/'protocols/confirmation100_assets_v1.json')['metadata_url']
  assert launch['connect_timeout_seconds']==20 and launch['total_timeout_seconds']==600 and launch['automatic_retries']==0 and not launch['tls_verification_disabled']
  assert receipt['protocol_sha256']==server['protocol_sha256'] and receipt['coverage_sha256']==server['coverage_sha256']
  assert not receipt['zip_downloaded'] and not receipt['scp_started'] and receipt['models_started']==0 and not receipt['gpu_used']
  rows.append(dict(report=name,curl_exit_code=60,http_code='000',body_bytes=0,seconds=float(fields[3]),error='SEC_E_WRONG_PRINCIPAL'))
 recovery=read(root/'reports/confirmation100_assets_windows_retry1/verification.json')
 assert recovery['first_windows_seal_sha256']==sha(root/'reports/confirmation100_assets_windows_v1/result_seal.json')
 assert recovery['first_windows_execution_files_unchanged'] and recovery['active_download_processes']==0
 return dict(status='passed',server_metadata_attempts=2,windows_metadata_attempts=2,total_metadata_attempts=4,successful_downloads=0,covers=0,captions=0,source_protocol_unchanged=True,prior_coverage_unchanged=True,windows_attempts=rows,zip_integrity_and_scp_hash_checks='not_applicable_no_zip_received',models_started=0,gpu_used=False,no_security_bypass=True)
if __name__=='__main__':print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
