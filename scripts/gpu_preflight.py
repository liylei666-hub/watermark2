"""CPU-only, evidence-first GPU idle gate for future launchers; starts no model."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU preflight requires CUDA_VISIBLE_DEVICES=""')
import argparse, csv, datetime, json, subprocess, time
from pathlib import Path

def snapshot(index):
    def run(args):
        return subprocess.check_output(['nvidia-smi']+args,text=True,timeout=10).strip()
    row=next(csv.reader([run(['-i',str(index),'--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'])],skipinitialspace=True))
    all_apps=list(csv.reader(run(['--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader,nounits']).splitlines(),skipinitialspace=True))
    return dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),row=row,
                compute_apps=[a for a in all_apps if a and a[0]==row[1]])

def verify_idle(sample,record,index,uuid,model,max_samples=15,sleep=time.sleep):
    """Require three consecutive idle samples. Foreign process or identity fails immediately."""
    assert index in [0,1,2] and max_samples>=3
    stable=0
    for attempt in range(max_samples):
        try:g=sample(index)
        except Exception as exc:
            record(dict(event='query_error',error=str(exc)));raise
        record(dict(event='sample',attempt=attempt,**g))
        row=g['row']
        if row[:3]!=[str(index),uuid,model]:raise RuntimeError('GPU identity mismatch')
        if g['compute_apps']:raise RuntimeError('GPU compute process present')
        idle=int(row[4])<=50 and int(row[5])==0
        stable=stable+1 if idle else 0
        if stable==3:
            record(dict(event='idle_verified',samples=attempt+1));return g
        if attempt+1<max_samples:sleep(2)
    raise RuntimeError('GPU did not meet stable idle conditions within bounded sampling')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,choices=[0,1,2],required=True)
    ap.add_argument('--uuid',required=True);ap.add_argument('--model',required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    with args.output.open('x',encoding='utf-8') as f:
        def record(event):f.write(json.dumps(event)+'\n');f.flush();os.fsync(f.fileno())
        try:verify_idle(snapshot,record,args.index,args.uuid,args.model)
        except Exception as exc:record(dict(event='failed',error=str(exc)));raise
