"""Execute the historical PSNR function on CPU; independently recompute saved PNGs."""
import os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
import ast,csv,hashlib,json,math,statistics
from pathlib import Path
import numpy as np
from PIL import Image
base=Path(__file__).resolve().parents[1]
import argparse
parser=argparse.ArgumentParser();parser.add_argument("--archive-root",type=Path,required=True);args=parser.parse_args()
old=base/'audit_sources/psnr_versions/43eec7e2b82ffbc947a88785a1b7a9963abb5a09.py'
tree=ast.parse(old.read_text(encoding='utf8'));node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='psnr_PIL')
scope=dict(Image=Image,np=np,math=math);exec(compile(ast.Module(body=[node],type_ignores=[]),str(old),'exec'),scope)
def corrected(a,b):
    delta=np.asarray(a,dtype=np.float64)-np.asarray(b,dtype=np.float64)
    mse=float(np.mean(delta**2));return math.inf if mse==0 else 10*math.log10(255**2/mse)
synthetic=[]
for distance in [1,15,16,20,64,255]:
    a=Image.fromarray(np.zeros((17,19,3),dtype=np.uint8));b=Image.fromarray(np.full((17,19,3),distance,dtype=np.uint8))
    before=scope['psnr_PIL'](a,b);after=corrected(a,b)
    synthetic.append(dict(byte_difference=distance,old_psnr='inf' if math.isinf(before) else before,corrected_psnr=after,
        old_uint8_mse=float(np.mean((np.asarray(a)-np.asarray(b))**2)),correct_float64_mse=distance**2))
assert synthetic[2]['old_psnr']=='inf' and math.isclose(synthetic[-1]['corrected_psnr'],0.)
assert math.isclose(synthetic[0]['old_psnr'],synthetic[0]['corrected_psnr'])
root=args.archive_root.resolve()/'runs/27_method_resume_20261019T173017Z';rows=[]
for sid in range(1,13):
    cover_path=root/f'attack_inputs/{sid}/cover.png';candidate_path=root/f'attack_outputs/{sid}/imprint/candidate.png';reference_path=root/f'attack_inputs/{sid}/reference.png'
    with Image.open(cover_path) as im:cover=im.copy()
    with Image.open(candidate_path) as im:candidate=im.copy()
    with Image.open(reference_path) as im:reference=im.copy()
    mse=float(np.mean((np.asarray(candidate,dtype=np.float64)/255-np.asarray(cover,dtype=np.float64)/255)**2))
    rows.append(dict(task_id=sid,method='native_imprint_10_updates',candidate_path=str(candidate_path),
        candidate_sha256=hashlib.sha256(candidate_path.read_bytes()).hexdigest(),cover_path=str(cover_path),
        cover_sha256=hashlib.sha256(cover_path.read_bytes()).hexdigest(),correct_psnr_to_cover=corrected(candidate,cover),
        old_buggy_psnr_to_cover=scope['psnr_PIL'](candidate,cover),wrong_pair_reference_psnr=corrected(candidate,reference),mse_rgb01=mse))
mean_db=statistics.mean(r['correct_psnr_to_cover'] for r in rows)
aggregate=-10*math.log10(statistics.mean(r['mse_rgb01'] for r in rows))
result=dict(launch_state=dict(stage30_model_processes_started=0,stage30_run_directory_exists=False,stage30_runtime_frozen=False,scientific_hold=True),
    historical_old_source_blob='c44801ba1e1027d0b2244ba5bc32198985f2cb61',
    fixed_source_blob='5c8b98877d8f1d587beda80366a24d44c1457fb8',
    synthetic_actual_old_function=synthetic,
    native27=dict(tasks=12,updates_each=10,rows=rows,mean_per_image_db=mean_db,psnr_from_aggregate_mse=aggregate,
        mean_buggy_db=statistics.mean(r['old_buggy_psnr_to_cover'] for r in rows),paper_native150_reproduced=False),
    implementation_note='Old function executed by AST extraction; corrected values independent float64 reference formula, not a TorchMetrics execution.',
    model_weights_loaded=False,new_model_experiments=0)
# Read-only replay; evidence is never overwritten.
print(json.dumps({k:v for k,v in result.items() if k!='native27'},indent=2));print('NATIVE27',mean_db,aggregate,result['native27']['mean_buggy_db'])
