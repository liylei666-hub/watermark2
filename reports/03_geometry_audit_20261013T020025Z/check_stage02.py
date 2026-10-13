import os
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import csv, hashlib, json, shlex, sys, datetime
from pathlib import Path
from PIL import Image
root=Path('/data0/liyanlei/watermark_research')
out=Path(sys.argv[1])
s=json.loads((root/'reports/02_status.json').read_text())
report=(root/'reports/02_smoke_report.md').read_text()
run=Path(s['run_dir']); assert root in run.parents
cfg=json.loads((run/'config.json').read_text())
cmd=(run/'command.sh').read_text()
tokens=shlex.split(cmd.splitlines()[-1]); start=tokens.index(cfg['command'][0])
with Path(s['metrics_path']).open() as f:
    reader=csv.DictReader(f); headers=reader.fieldnames; rows=list(reader)
images=[]
recorded=json.loads((run/'image_checks.json').read_text())
for key in ['reference_image_path','forged_image_path']:
    p=Path(s[key]); assert run in p.parents
    with Image.open(p) as im: im.verify()
    with Image.open(p) as im: size=list(im.size); mode=im.mode
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    before=next(i for i in recorded if i['path']==str(p))
    images.append(dict(role=key,path=str(p),size=size,mode=mode,sha256=sha,
        status='已核对一致' if sha==before['sha256'] and size==[512,512] and sha in report else '存在差异'))
by_step={int(r['step']):r for r in rows}
csv_ok=all(float(by_step[n]['bit_accuracy'])==s[k] and by_step[n]['detection_successful'].lower()==str(s[b]).lower() for n,k,b in [(-1,'reference_bit_accuracy','reference_detected'),(1,'forged_bit_accuracy','forged_detected')])
stdout=(run/'stdout.log').read_text(); ex=json.loads((run/'execution.json').read_text()); rc=int((run/'exit_code.txt').read_text().strip())
checks={
 'command_and_config':'已核对一致' if tokens[start:]==cfg['command'] and '--resample' not in tokens else '存在差异',
 'exit_and_completion_log':'已核对一致' if rc==0 and ex['exit_code']==0 and all('phase '+str(i)+':' in stdout for i in range(1,5)) and '(Harmful image) detection_success: True' in stdout else '存在差异',
 'csv_values_and_report':'已核对一致' if csv_ok and len(rows)==2 and '0.953125' in report and '1.0' in report else '存在差异',
 'threshold_record':'已核对一致' if cfg['threshold']==s['threshold']==0.70703125 and cfg['threshold_comparator']==s['threshold_comparator']=='>' else '存在差异',
 'historical_gpu':'已核对一致' if cfg['gpu_uuid']==s['gpu_uuid'] and s['gpu_physical_index']==3 else '存在差异',
 'images':'已核对一致' if all(i['status']=='已核对一致' for i in images) else '存在差异'}
files=[]
for p in [root/'AGENTS.md',root/'reports/02_smoke_report.md',root/'reports/02_status.json']+sorted(run.rglob('*')):
 if p.is_file(): files.append(dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
result=dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,
 stage02_evidence_consistent=all(v=='已核对一致' for v in checks.values()),run_dir=str(run),
 csv_header=headers,csv_rows=rows,images=images,command=cmd,config=cfg,
 exit_code=rc,stdout=stdout,execution=ex,files=files,
 saved_tensor_files=[i['path'] for i in files if Path(i['path']).suffix in ['.pt','.pth','.npy','.npz','.safetensors']],
 gpu_used=False,models_loaded=False,new_experiments_run=0)
with (out/'stage02_evidence.json').open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({k:result[k] for k in ['checked_at_utc','checks','stage02_evidence_consistent','images','saved_tensor_files']},ensure_ascii=False,indent=2))
