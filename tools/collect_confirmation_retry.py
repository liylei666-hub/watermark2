import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import sys
sys.path.insert(0,'/data0/liyanlei/watermark_research/tools')
import retry_confirmation100_assets as r
a=r.a
a.host()
assert (a.PUBLIC/'execution.json').exists()
files=[dict(path=p.relative_to(a.ROOT).as_posix(),bytes=p.stat().st_size,sha256=a.sha(p)) for p in a.DATA.rglob('*') if p.is_file()]
original=[dict(path=p.relative_to(a.ROOT).as_posix(),bytes=p.stat().st_size) for p in r.ORIGINAL_DATA.rglob('*') if p.is_file()]
processes=__import__('subprocess').check_output(['ps','-u','liyanlei','-o','pid,etime,args'],text=True).splitlines()
active=[s for s in processes if 'python' in s and ('tools/prepare_confirmation100_assets.py' in s or 'tools/retry_confirmation100_assets.py' in s)]
a.write(a.PUBLIC/'budget_after.json',dict(observed_at_utc=a.now(),budget=a.budget(),dataset_regular_files=len(files),files=files,first_attempt_regular_files=original,active_acquisition_processes=active,worker_sha256=a.sha(a.__file__),transport_wrapper_sha256=a.sha(r.__file__),first_execution_sha256=a.sha(r.FIRST/'execution.json'),first_result_seal_sha256=a.sha(r.FIRST/'result_seal.json')))
print((a.PUBLIC/'budget_after.json').read_text())
