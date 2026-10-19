"""Resumable CPU verification, tables, image sheets and evidence package."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import csv,datetime,fcntl,hashlib,io,json,sys,time,zipfile
from pathlib import Path
from common import c,r,load

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def retain(path,data):
    """Reuse exact bytes, reject conflicting evidence; never rewrite an existing artifact."""
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('Existing artifact differs: '+str(path))
        return 'verified_existing'
    with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    return 'created'
def save(path,value):return retain(path,(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
def status(report,value):
    tmp=report/'postprocess_status.tmp';tmp.write_text(json.dumps(dict(checked_at_utc=now(),gpu_used=False,models_loaded=False,**value),indent=2));tmp.replace(report/'postprocess_status.json')
def event(report,**value):
    with (report/'postprocess_events.jsonl').open('a') as f:f.write(json.dumps(dict(at_utc=now(),**value))+'\n');f.flush();os.fsync(f.fileno())
def live_controller(report):
    launch=c.read(report/'controller_launch.json');path=Path('/proc')/str(launch['pid'])
    if not path.exists():return False
    argv=(path/'cmdline').read_bytes().replace(b'\x00',b' ').decode()
    return 'scripts/method_comparison_r4/control.py --run' in argv
def make_contacts(run,result,report):
    from PIL import Image,ImageDraw
    known={(x['task_id'],x['method']):x for x in result['rows']}
    for group in range(4):
        canvas=Image.new('RGB',(5*256,3*288),'white');draw=ImageDraw.Draw(canvas)
        for row,sid in enumerate(range(group*3+1,group*3+4)):
            for col,kind in enumerate(('reference','cover','imprint','jain','delivery')):
                xy=(col*256,row*288+25)
                if kind in ('reference','cover'):path=run/'attack_inputs'/str(sid)/(kind+'.png')
                elif known[(sid,kind)]['status']=='failed':path=None
                else:path=run/'attack_outputs'/str(sid)/kind/'candidate.png'
                if path is None:
                    draw.rectangle([xy,(xy[0]+255,xy[1]+255)],fill='#dddddd');draw.text((xy[0]+20,xy[1]+115),'FAILED: NO CANDIDATE',fill='black')
                else:
                    with Image.open(path) as im:canvas.paste(im.resize((256,256)),xy)
                draw.text((col*256+5,row*288+5),f'Task {sid} | {kind}',fill='black')
        buf=io.BytesIO();canvas.save(buf,format='PNG');retain(report/f'contact_{group}.png',buf.getvalue())

def main():
    cfg=c.read(r.ROOT/'protocols/27_method_runtime_r4.json');run=r.ROOT/cfg['run_dir'];report=r.ROOT/'reports'/run.name
    report.mkdir(exist_ok=True)
    with (report/'.cpu_finalize.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        event(report,event='cpu_postprocess_started',pid=os.getpid(),script_sha256=c.sha(__file__))
        try:
            while True:
                terminal=c.read(run/'status.json') if (run/'status.json').exists() else None
                if terminal and terminal.get('completed'):break
                if not live_controller(report):raise RuntimeError('Controller is not active and comparison has not completed; no GPU task will be relaunched by CPU postprocessing')
                status(report,dict(completed=False,state='waiting_for_comparison'));time.sleep(30)
            analysis=load('comparison_result_analysis',Path(__file__).with_name('analyze.py'))
            result=analysis.analyze(run,private_check=True)
            save(report/'verification_private.json',result);event(report,event='analysis_verified',scores=result['independent_gs_scores_checked'])
            fields=list(result['rows'][0]);fields+=['failure_reason']
            output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader();writer.writerows(result['rows']);retain(report/'task_results.csv',output.getvalue().encode())
            make_contacts(run,result,report);event(report,event='contacts_verified',images=59)
            evidence=[report/'verification_private.json',report/'task_results.csv']+list(report.glob('contact_*.png'))
            files=sorted([p for p in run.rglob('*') if p.is_file()]+evidence)
            records=[dict(path=p.relative_to(r.ROOT).as_posix(),sha256=c.sha(p),bytes=p.stat().st_size) for p in files]
            manifest=report/'artifact_manifest.json';save(manifest,dict(files=records,private_material_included=False,original_source_run=cfg['source_run'],original_source_files=cfg['source_files']))
            files.append(manifest);archive=r.ROOT/(run.name+'_evidence.zip')
            if archive.exists():
                with zipfile.ZipFile(archive) as z:
                    if set(z.namelist())!={p.relative_to(r.ROOT).as_posix() for p in files}:raise ValueError('Existing archive inventory differs')
                    for p in files:
                        if hashlib.sha256(z.read(p.relative_to(r.ROOT).as_posix())).hexdigest()!=c.sha(p):raise ValueError('Existing archive bytes differ')
            else:
                temporary=archive.with_name(archive.name+'.partial_'+str(os.getpid()))
                with zipfile.ZipFile(temporary,'x',zipfile.ZIP_DEFLATED) as z:
                    for p in files:z.write(p,p.relative_to(r.ROOT).as_posix())
                temporary.rename(archive)
            status(report,dict(completed=True,state='verified_and_packaged',archive=archive.name,archive_sha256=c.sha(archive),archive_bytes=archive.stat().st_size,independently_decoded_scores=59,private_material_included=False,decision=result['decision'],local_collection_and_visual_review_pending=True))
            event(report,event='cpu_postprocess_completed',archive_sha256=c.sha(archive));print('COMPLETED_CPU_POSTPROCESS',flush=True)
        except BaseException as exc:
            stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
            error=dict(completed=False,error_type=type(exc).__name__,reason=str(exc),at_utc=now(),models_loaded=False,gpu_used=False)
            save(report/('postprocess_error_'+stamp+'.json'),error);status(report,dict(completed=False,state='error',reason=str(exc)));raise

if __name__=='__main__':main()
