"""CPU postprocessor for the already running comparison; never launches a model."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import datetime,hashlib,json,subprocess,sys,time,zipfile
from pathlib import Path

ROOT=Path('/data0/liyanlei/watermark_research')

def write(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)

def main():
    cfg=json.loads((ROOT/'protocols/27_method_runtime_r2.json').read_text());run=ROOT/cfg['run_dir'];reports=ROOT/'reports/27_method_comparison'
    launch=json.loads((reports/'controller_launch.json').read_text());pid=launch['pid']
    while not (run/'status.json').exists():
        try:os.kill(pid,0)
        except ProcessLookupError:
            write(reports/'postprocess_status.json',dict(completed=False,reason='Controller exited without terminal status',models_loaded=False,gpu_used=False));return
        time.sleep(30)
    status=json.loads((run/'status.json').read_text())
    if not status.get('completed'):
        write(reports/'postprocess_status.json',dict(completed=False,reason='Experiment stopped; raw evidence preserved',experiment_status=status,models_loaded=False,gpu_used=False));return
    command=[sys.executable,str(ROOT/'scripts/method_comparison/analyze.py'),str(run),str(reports/'verification_private.json'),'--private-check']
    result=subprocess.run(command,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1'),cwd=ROOT,capture_output=True,text=True)
    with (reports/'verification_stdout.txt').open('x') as f:f.write(result.stdout)
    with (reports/'verification_stderr.txt').open('x') as f:f.write(result.stderr)
    if result.returncode:
        write(reports/'postprocess_status.json',dict(completed=False,reason='CPU result verification failed',exit_code=result.returncode,models_loaded=False,gpu_used=False));return
    from PIL import Image,ImageDraw
    for group in range(4):
        canvas=Image.new('RGB',(5*256,3*288),'white');draw=ImageDraw.Draw(canvas)
        for row,sid in enumerate(range(group*3+1,group*3+4)):
            for col,kind in enumerate(('reference','cover','imprint','jain','delivery')):
                path=run/'attack_inputs'/str(sid)/(kind+'.png') if kind in ('reference','cover') else run/'attack_outputs'/str(sid)/kind/'candidate.png'
                with Image.open(path) as im:canvas.paste(im.resize((256,256)),(col*256,row*288+25))
                draw.text((col*256+5,row*288+5),f'Task {sid} | {kind}',fill='black')
        with (reports/f'contact_{group}.png').open('xb') as f:canvas.save(f,format='PNG')
    files=sorted([p for p in run.rglob('*') if p.is_file()]+[p for p in reports.rglob('*') if p.is_file() and p.name not in ('postprocessor_stdout.log','postprocessor_stderr.log')])
    records=[dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in files]
    manifest=reports/'artifact_manifest.json';write(manifest,dict(files=records,private_material_included=False))
    archive=ROOT/(run.name+'_evidence.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in files+[manifest]:z.write(p,p.relative_to(ROOT).as_posix())
    write(reports/'postprocess_status.json',dict(completed=True,checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        archive=archive.name,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),archive_bytes=archive.stat().st_size,
        independently_decoded_scores=60,private_material_included=False,models_loaded=False,gpu_used=False))
    print('COMPLETED_CPU_POSTPROCESS',flush=True)

if __name__=='__main__':main()
