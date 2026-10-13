import os
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
import ast, datetime, hashlib, json, subprocess, sys
from pathlib import Path
root=Path('/data0/liyanlei/watermark_research')
out=Path(sys.argv[1]); g=root/'third_party/geodistort-wm'; b=root/'third_party/semantic-forgery'
def git(p,*args):
    return subprocess.check_output(['git','-C',str(p),*args],text=True).strip()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
files=git(g,'ls-files').splitlines()
inventory=[{'path':f,'bytes':(g/f).stat().st_size,'sha256':sha(g/f)} for f in files]
comparisons=[]
for f in ['utils/wm/gs_provider.py','utils/wm/keys.py','utils/wm/messages.py','utils/wm/nonces.py','utils/wm/wm_provider.py','utils/pipe/SD_provider.py','utils/pipe/SDXL_provider.py','utils/pipe/pipe_provider.py','utils/pipe/schedulers/scheduling_ddim.py','utils/pipe/schedulers/scheduling_ddim_inverse.py']:
    comparisons.append({'path':f,'identical':sha(g/f)==sha(b/f),'geometry_sha256':sha(g/f),'baseline_sha256':sha(b/f)})
missing=[]; defs=[]
for f in files:
    if not f.endswith('.py') or f in ['utils/wm/keys.py','utils/wm/messages.py','utils/wm/nonces.py']: continue
    tree=ast.parse((g/f).read_text(),filename=f)
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(s in n.name.lower() for s in ['cos','spd','airm','geom','roc']): defs.append({'file':f,'line':n.lineno,'name':n.name})
        if isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('utils'):
            mp=g.joinpath(*n.module.split('.'))
            if not mp.with_suffix('.py').exists() and not (mp/'__init__.py').exists(): missing.append({'file':f,'line':n.lineno,'module':n.module})
            elif n.module=='utils.pipe':
                for a in n.names:
                    if a.name=='pipe_utils' and not (mp/'pipe_utils.py').exists(): missing.append({'file':f,'line':n.lineno,'module':'utils.pipe.pipe_utils'})
result={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'repo_path':str(g),'remote':git(g,'remote','get-url','origin'),'commit':git(g,'rev-parse','HEAD'),'branch':git(g,'symbolic-ref','--short','HEAD'),'status':git(g,'status','--porcelain'),'baseline_commit':git(b,'rev-parse','HEAD'),'baseline_status':git(b,'status','--porcelain'),'license_files':[f for f in files if any(x in Path(f).name.lower() for x in ['license','licence','copying'])],'tracked_files':inventory,'missing_local_imports':missing,'metric_named_definitions':defs,'file_comparisons':comparisons,'paper_sha256':sha(out/'paper_v1.html'),'bundle_sha256':sha(out/'geodistort_full.bundle')}
with (out/'source_evidence.json').open('x') as f: json.dump(result,f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='tracked_files'},indent=2))
