"""Freeze role-specific pilot manifests on the authorized server; CPU only, no launch."""
import datetime,hashlib,json,sys
from pathlib import Path
from common import ROOT,BASE,c,r,launch


def attack_source_pins(sources,proxy_snapshot):
    return {name:digest for name,digest in sources.items()
            if Path(name).suffix=='.py' or Path(name).is_relative_to(Path(proxy_snapshot))}


def main(commit):
    if len(commit)!=40 or any(x not in '0123456789abcdef' for x in commit):raise ValueError('Expected source commit')
    launch.check_host(ROOT)
    design_path=ROOT/'protocols/29_quality_design.json';design=c.read(design_path)
    previous=c.read(ROOT/'protocols/27_method_runtime_r4.json')
    for role in ('target','proxy'):
        if design[role]!=previous['design'][role] or not Path(design[role]['snapshot']).is_dir():
            raise ValueError('Existing model snapshot differs')
    sources=dict(previous['code_hashes'])
    for folder in (BASE/'quality_cost',BASE/'parallel_execution'):
        for path in folder.glob('*.py'):sources[str(path)]=c.sha(path)
    sources[str(design_path)]=c.sha(design_path)
    sources[str(BASE/'cover_pilot/attack.py')]=c.sha(BASE/'cover_pilot/attack.py')
    sources[str(BASE/'cross_generator/verify_message_scores.py')]=c.sha(BASE/'cross_generator/verify_message_scores.py')
    for role in ('target','proxy'):
        snapshot=Path(design[role]['snapshot'])
        for path in snapshot.rglob('*.json'):sources[str(path)]=c.sha(path)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');run='29_quality_cost_'+stamp
    paths={role:'protocols/29_quality_'+role+'_runtime.json' for role in ('controller','attacker','evaluator')}
    if any((ROOT/path).exists() or (ROOT/path).with_suffix('.sha256').exists() for path in paths.values()):
        raise ValueError('Already frozen; do not overwrite or retry')
    config=dict(stage='29',source_commit=commit,versions=previous['versions'],code_hashes=sources,
        device=dict(index=0,uuid=previous['allowed_gpu_uuids']['0'],model='NVIDIA GeForce RTX 3090'))
    evaluator=dict(config,role='evaluator',design=design)
    attack_sources=attack_source_pins(sources,design['proxy']['snapshot'])
    attacker=dict(config,role='attacker',proxy=design['proxy'],policy=design['policy'],code_hashes=attack_sources)
    controller=dict(config,role='controller',design=design,run_dir='runs/'+run,private_folder='private_eval/'+run,
        runtime_paths=paths,max_new_bytes=10737418240,watchdog_seconds=1200)
    for role,value in [('attacker',attacker),('evaluator',evaluator)]:
        path=ROOT/paths[role];c.write(path,value)
        with path.with_suffix('.sha256').open('x') as stream:stream.write(c.sha(path)+'\n')
        r.verify_runtime(path)
    controller['runtime_sha256']={role:c.sha(ROOT/paths[role]) for role in ('attacker','evaluator')}
    path=ROOT/paths['controller'];c.write(path,controller)
    with path.with_suffix('.sha256').open('x') as stream:stream.write(c.sha(path)+'\n')
    r.verify_runtime(path)
    print(json.dumps(dict(run_dir=controller['run_dir'],runtime_paths=paths,
        hashes={role:c.sha(ROOT/path) for role,path in paths.items()},source_commit=commit),indent=2))


if __name__=='__main__':main(sys.argv[1])
