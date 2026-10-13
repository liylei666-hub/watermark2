"""CPU-only management checks. Execute only argv construction AST nodes."""
import os
assert os.environ.get("CUDA_VISIBLE_DEVICES")==""
import ast,json,sys,types
from pathlib import Path
import torch
from recording import Recorder,write_json,sha
experiment=Path(sys.argv[1]); code=Path(__file__).resolve().parent
protocol=json.loads((experiment/"pilot_protocol.json").read_text())
source=ast.parse((code/"run_recorded.py").read_text())
nodes=[]
for n in source.body:
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name) and t.value.id=="sys" and t.attr=="argv" for t in n.targets): nodes.append(n)
    if isinstance(n,ast.For) and "sys.argv.extend" in ast.unparse(n): nodes.append(n)
assert len(nodes)==2
ids=[]; outputs=[]
testroot=experiment/"evaluator_only/parameter_tests";testroot.mkdir()
for seed in protocol["planned_seeds"]:
    run=experiment/("seed_"+str(seed))
    cfg=json.loads((run/"evaluator_only/config.json").read_text())
    assert cfg["arguments"]["seed"]==seed
    ns=dict(sys=types.SimpleNamespace(argv=[]),cfg=cfg,up=Path(cfg["upstream_path"]),run=run)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),"<argv-only>","exec"),ns)
    args=ns["sys"].argv
    assert args[args.index("--seed")+1]==str(seed)
    expected=str(run/"evaluator_only/official_output")
    assert args[args.index("--out_dir")+1]==expected
    assert "--resample" not in args
    outputs.append(expected);ids.extend([cfg["reference_id"],cfg["candidate_id"]])
    directory=testroot/str(seed);directory.mkdir()
    recorder=Recorder(directory,sha(run/"evaluator_only/config.json"),"target",
        reference_id=cfg["reference_id"],candidate_id=cfg["candidate_id"])
    z=torch.arange(4,dtype=torch.float32).reshape(1,1,2,2); before=z.clone()
    recorder.tensor("test",z,"CPU parameter mock",1)
    r=recorder.records["test"]
    assert r["reference_id"]==cfg["reference_id"] and r["candidate_id"]==cfg["candidate_id"]
    assert torch.equal(z,before)
assert len(set(ids))==16 and len(set(outputs))==8
write_json(experiment/"evaluator_only/parameter_tests.json",dict(passed=True,
    tested_seeds=protocol["planned_seeds"],unique_ids=16,unique_output_directories=8,
    argv_seed_output_binding=True,unchanged_inputs=True,models_loaded=False))
print("PARAMETER_TESTS_PASSED")

