"""Resume contracts: completed evidence is reused; every launched failure remains missing."""
import importlib.util,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
sys.path.insert(0,str(BASE/'cover_pilot'))
import contract as c
import runtime as r
IDS=list(range(1,13));METHODS=('imprint','jain','delivery')

def old_common():return load('comparison_original_common',BASE/'method_comparison/common.py')
module=load
def validate_job(path):return old_common().validate_job(path)
def origin(root,name):
    meta=c.read(Path(root)/'inheritance.json');source=meta['completed'].get(name)
    return c.inside(Path(root).parent.parent,source['path']) if source else Path(root)/name
def verify_source(root,record):
    p=c.inside(Path(root).parent.parent,record['path'])
    if c.sha(p/'execution.json')!=record['sha256']:raise ValueError('Source execution changed')
    return p
def delivery(root):
    root=Path(root);meta=c.read(root/'inheritance.json');rows=[];base=old_common()
    for sid in IDS:
        for method in METHODS:
            name=f'attack_outputs/{sid}/{method}';job=root/'attack_inputs'/str(sid)/(method+'.json');base.validate_job(job)
            if name in meta['failed']:
                p=verify_source(root,meta['failed'][name]);ex=c.read(p/'execution.json')
                if ex['completed'] or ex['exit_code']==0 or (root/name/'candidate.png').exists():raise ValueError('Failed task misclassified')
                rows.append(dict(task_id=sid,method=method,status='failed',source_execution=meta['failed'][name],candidate=None));continue
            out=root/name;p=origin(root,name)
            if name in meta['completed']:verify_source(root,meta['completed'][name])
            ex=c.read(p/'execution.json')
            if not ex['completed'] or ex['exit_code']!=0:raise ValueError('Candidate incomplete')
            frozen=c.read(out/'candidate_frozen.json');expected=dict(task_id=sid,method=method,job_sha256=c.sha(job),image=c.png_record(out/'candidate.png'))
            if frozen!=expected:raise ValueError('Frozen candidate changed')
            rows.append(dict(task_id=sid,method=method,status='completed',candidate=(out/'candidate.png').relative_to(root).as_posix(),sha256=frozen['image']['sha256']))
    return rows
def verify_delivery(root):
    sealed=c.read(Path(root)/'delivery_sealed.json')
    if sealed['rows']!=delivery(root):raise ValueError('Delivery seal changed')
    return sealed

def activate_gate():
    # Import the audited strict preimport gate without changing the original runtime module on disk.
    scope=load('stable_gate_revision',BASE/'method_comparison_r4/gate.py')
    r.check_device=scope.check_device
    return scope
