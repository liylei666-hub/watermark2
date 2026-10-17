"""Export image-only attack jobs and build the fixed post-delivery evaluation queue."""
from pathlib import Path
import shutil
import contract as c


def export_jobs(root, prepared):
    """Caller owns evaluator metadata. Only the two PNGs cross this interface."""
    root=Path(root)
    c.keys(prepared,['version','tasks'])
    if prepared['version']!=1 or len(prepared['tasks'])!=3:
        raise ValueError('Expected three prepared pairs')
    ids=[r['task_id'] for r in prepared['tasks']]
    if ids!=[1,2,3]:raise ValueError('Expected task order 1,2,3')
    # Validate every source before writing any public job.
    for row in prepared['tasks']:
        c.keys(row,['task_id','reference','cover'])
        for kind in ['reference','cover']:
            rec=row[kind];c.keys(rec,['path','sha256','bytes'])
            source=c.inside(root,rec['path']);actual=c.png_record(source)
            if actual['sha256']!=rec['sha256'] or actual['bytes']!=rec['bytes']:
                raise ValueError('Prepared input changed')
    plan=dict(version=1,jobs=[])
    for row in prepared['tasks']:
        folder=root/'attack_inputs'/str(row['task_id']);folder.mkdir(parents=True)
        for kind in ['reference','cover']:
            with c.inside(root,row[kind]['path']).open('rb') as src, (folder/(kind+'.png')).open('xb') as dst:
                shutil.copyfileobj(src,dst)
        for method in c.METHODS:
            job=dict(version=1,task_id=row['task_id'],method=method,seed=500+row['task_id'],
                reference=c.png_record(folder/'reference.png'),cover=c.png_record(folder/'cover.png'),
                proxy=dict(model_id=c.PROXY_ID,revision=c.PROXY_REVISION,snapshot=c.PROXY_SNAPSHOT,dtype='float32',resolution=512),
                parameters=c.METHODS[method])
            path=folder/(method+'.json');c.write(path,job);c.validate_job(path)
            plan['jobs'].append(dict(task_id=row['task_id'],method=method,
                job_path=path.relative_to(root).as_posix(),job_sha256=c.sha(path),
                output_path='attack_outputs/'+str(row['task_id'])+'/'+method))
    c.write(root/'attack_plan.json',plan)
    return plan


def evaluation_queue(root,plan_path):
    """Validate all six deliveries before making any evaluator work available.

    Reference and unwatermarked cover are fixed controls; neither controls inclusion.
    """
    root=Path(root);delivery=c.verify_delivery(root,plan_path)
    plan=c.read(plan_path);queue=[]
    for task in [1,2,3]:
        entries=[x for x in plan['jobs'] if x['task_id']==task]
        jobs=[c.validate_job(c.inside(root,x['job_path'])) for x in entries]
        for kind in ['reference','cover']:
            # Comparison must share the same pair, not merely the same task label.
            if jobs[0][kind]!=jobs[1][kind]:raise ValueError('Methods do not share inputs')
            path=c.inside(root,entries[0]['job_path']).parent/jobs[0][kind]['path']
            queue.append(dict(task_id=task,kind=kind,path=path.relative_to(root).as_posix(),sha256=c.sha(path)))
        for method in c.METHODS:
            candidate=next(x for x in delivery['candidates'] if (x['task_id'],x['method'])==(task,method))
            queue.append(dict(task_id=task,kind=method,path=candidate['candidate_path'],sha256=candidate['candidate_sha256']))
    return queue


def evaluate_fixed_queue(root,plan_path,evaluator):
    """Injectable evaluator for CPU order tests. No callbacks until seal validates."""
    queue=evaluation_queue(root,plan_path)
    results=[]
    for row in queue:
        path=c.inside(root,row['path'])
        if c.sha(path)!=row['sha256']:raise ValueError('Image changed before evaluation')
        result=evaluator(path,row['task_id'],row['kind'])
        if c.sha(path)!=row['sha256']:raise ValueError('Image changed during evaluation')
        results.append(dict(input=row,result=result))
    c.verify_delivery(root,plan_path)
    return results
