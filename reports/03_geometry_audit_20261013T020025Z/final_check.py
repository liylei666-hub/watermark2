import os
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import datetime, hashlib, json, subprocess, sys
from pathlib import Path
out=Path(sys.argv[1]); root=out.parent.parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads((out/'stage02_evidence.json').read_text())
changes=[i['path'] for i in e['files'] if not Path(i['path']).is_file() or sha(Path(i['path']))!=i['sha256']]
repo_states={}
for name in ['semantic-forgery','geodistort-wm']:
    p=root/'third_party'/name
    repo_states[name]={'commit':subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip(),'status':subprocess.check_output(['git','-C',str(p),'status','--porcelain'],text=True).strip()}
bit_checks=[]
for row in e['csv_rows']:
    a=row['message_bits_str_initial']; b=row['message_bits_str_recovered']
    n=sum(x==y for x,y in zip(a,b))
    bit_checks.append({'step':int(row['step']),'initial_bits':len(a),'recovered_bits':len(b),'matching_bits':n,'csv_ratio_consistent':n/len(a)==float(row['bit_accuracy'])})
s=json.loads((out/'03_status.json').read_text())
assert s['gpu_used'] is False and s['models_loaded'] is False and s['new_experiments_run']==0
assert not changes and all(not r['status'] for r in repo_states.values()) and all(i['csv_ratio_consistent'] for i in bit_checks)
r={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'existing_files_checked':len(e['files']),'changed_existing_files':changes,'repo_states':repo_states,'csv_bit_string_arithmetic':bit_checks,'artifacts':[{'path':str(out/f),'sha256':sha(out/f),'bytes':(out/f).stat().st_size} for f in ['03_audit.md','03_status.json','information_boundary.md']],'scope':'文件完整性与CSV算术核查；未重新运行检测器'}
with (out/'preservation_check.json').open('x',encoding='utf-8') as f: json.dump(r,f,ensure_ascii=False,indent=2)
print(json.dumps(r,ensure_ascii=False,indent=2))
