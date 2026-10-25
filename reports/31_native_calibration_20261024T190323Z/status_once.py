"""Read-only observer; not part of the frozen experiment runtime."""
import datetime,json,subprocess
from pathlib import Path
root=Path('/data0/liyanlei/watermark_research/runs/31_native_calibration_20261024T190323Z')
def read(path):return json.loads(path.read_text())
rows={}
for folder in sorted(root.iterdir()):
    if not folder.is_dir() or folder.name not in ('prepare','evaluate','attack_1','attack_2','attack_3','attack_4'):continue
    row={};p=folder/'process.json'
    if p.exists():
        identity=read(p);row.update(pid=identity['pid'],gpu_uuid=identity['gpu_uuid'])
        stat=Path('/proc')/str(identity['pid'])/'stat'
        row['same_process_alive']=stat.exists() and stat.read_text().rsplit(')',1)[1].split()[19]==identity['proc_start_ticks']
    log=folder/'stdout.log'
    if log.exists():
        lines=log.read_text(errors='replace').splitlines();updates=[x for x in lines if x.startswith('NATIVE_UPDATE ')]
        row['actual_updates']=int(updates[-1].split()[1]) if updates else 0
        row['checkpoint_pngs']=[n for n in (20,50,100,150,151) if (folder/f'update_{n}.png').exists()]
        if folder.name=='evaluate':row['evaluated_images']=sum(x.startswith('EVALUATED ') for x in lines)
    p=folder/'execution.json'
    if p.exists():
        ex=read(p)['outcome'];row['execution']={n:ex[n] for n in ('completed','exit_code','stop_reason','process_wall_seconds')}
    rows[folder.name]=row
print(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),state=read(root/'scheduler_status.json'),jobs=rows,candidates_sealed=(root/'candidates_sealed.json').exists(),results_sealed=(root/'results_sealed.json').exists(),gpu_csv=subprocess.check_output(['nvidia-smi','-i','0,1','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).splitlines())),flush=True)
