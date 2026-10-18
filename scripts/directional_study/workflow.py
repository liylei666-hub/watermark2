"""Fixed seven-process workflow, injectable for CPU order verification."""
import interface as i

def execute(root,run_child,protocol):
    reference=run_child('evaluator_private/reference','prepare.py',[protocol,'reference'])
    cover=run_child('evaluator_private/cover','prepare.py',[protocol,'cover'])
    for task in range(1,5):
        i.export_job(root,task,reference/str(task)/'reference.png',cover/str(task)/'cover.png')
    i.freeze_inputs(root)
    for task in range(1,5):
        run_child('attack_outputs/'+str(task),'attack.py',[root/'attack_inputs'/str(task)/'job.json'])
    i.seal(root)
    run_child('evaluator_results','evaluate.py',[protocol,root])
