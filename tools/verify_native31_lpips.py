"""Public seal/aggregation verifier; does not import a model or recalculate LPIPS."""
import hashlib,json,math,statistics
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def verify(project):
 project=Path(project);out=project/'reports/31_native_calibration_lpips_20261025';run=project/'runs/31_native_calibration_20261024T190323Z'
 ex=read(out/'execution.json');seal=read(out/'result_seal.json');summary=read(out/'summary.json');qa=read(out/'qa.json');plan=read(out/'plan.json')
 assert ex['completed'] and ex['exit_code']==0 and ex['stop_reason'] is None
 assert sha(out/'execution.json')==seal['execution_sha256'] and sha(out/'summary.json')==seal['summary_sha256']
 for name,h in ex['files'].items():assert sha(out/name)==h
 assert sha(out/'qa.json')==summary['qa_sha256']
 assert sha(project/'tools/native31_lpips_cpu.py')==plan['worker_sha256'] and sha(project/'tools/run_native31_lpips_cpu.py')==plan['supervisor_sha256']
 assert plan['gpu_allowed'] is False and plan['implicit_downloads_allowed'] is False
 assert read(out/'process.json')['environment']['CUDA_VISIBLE_DEVICES']==''
 assert summary['completed'] and summary['posthoc_quality_supplement'] and summary['not_preregistered_primary_metric']
 assert summary['gpu_used'] is False and summary['cuda_initialized'] is False and summary['network_attempts']==0
 assert qa['same_image_lpips']==0 and qa['lpips_version']=='0.1' and qa['pnet_rand'] is False and qa['pretrained'] is True
 assert qa['model_training'] is False and qa['all_modules_eval'] and qa['all_parameters_cpu'] and qa['network_attempts']==0
 assert qa['input_spy']==dict(shape=[1,3,512,512],dtype='torch.float32',device='cpu',black_min=-1.,black_max=-1.,white_min=1.,white_max=1.)
 assert qa['helper_git_blob']=='43c6755a9b132e8ac33fbb63ab38b85506a2cf85' and qa['resize_or_imagenet_crop'] is False
 assert plan['weights']==qa['weights']
 for name,h in summary['original_file_hashes_unchanged'].items():assert sha(run/name)==h
 rows=summary['rows'];assert rows==[json.loads(s) for s in (out/'rows.jsonl').read_text().splitlines()]
 expected={(i,label) for i in range(1,5) for label in ['reference','cover','20','50','100','150','151']}
 assert len(rows)==28 and {(r['task_id'],r['label']) for r in rows}==expected
 for row,source in zip(rows,plan['inputs']):
  assert all(row[k]==v for k,v in source.items()) and math.isfinite(row['lpips']) and row['lpips']>=0
  for kind in ('image','cover'):
   relative=row[kind+'_path'].removeprefix('/data0/liyanlei/watermark_research/')
   assert sha(project/relative)==row[kind+'_sha256']
  if row['label']=='cover':assert row['lpips']==0
 groups={}
 for n in (20,50,100,150,151):
  values=[r['lpips'] for r in rows if r['label']==str(n)];assert len(values)==4
  g=summary['checkpoints'][str(n)];assert g['n']==4 and values==g['values'] and abs(statistics.mean(values)-g['mean_lpips'])<1e-12;groups[str(n)]=g
 assert summary['primary_actual_update']==151 and summary['secondary_actual_update']==150
 return dict(status='passed',scope='Public file/input pairing and aggregation checks; no duplicate LPIPS inference',sealed_worker_artifacts=len(ex['files']),evaluated_pairs=28,candidate_pairs=20,unchanged_original_score_and_seal_files=4,checkpoints=groups,qa_sha256=sha(out/'qa.json'),metric_summary_sha256=sha(out/'summary.json'),cpu_process_wall_seconds=ex['process_wall_seconds'],gpu_used=False,network_attempts=0)
if __name__=='__main__':print(json.dumps(verify(Path(__file__).resolve().parents[1]),indent=2))
