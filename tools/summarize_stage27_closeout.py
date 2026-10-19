"""Targeted CPU readback of completed stage27, retaining published source identity."""
import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys

if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('Set CUDA_VISIBLE_DEVICES empty for CPU-only readback')
ROOT = Path(__file__).resolve().parents[1]
COMMIT = '678487991fab34650cc5b16e5e96a008fb38bcf4'
RELATIVE = 'reports/27_method_resume_20261019T173017Z/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def compare(a, b, tolerance, differences, path=''):
    if isinstance(a, float) and isinstance(b, float):
        differences.append(abs(a-b))
        if not math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance):
            raise ValueError('Numeric mismatch: ' + path)
    elif type(a) is not type(b):
        raise ValueError('Type mismatch: ' + path)
    elif isinstance(a, dict):
        if a.keys() != b.keys():
            raise ValueError('Field mismatch: ' + path)
        for key in a:
            compare(a[key], b[key], tolerance, differences, path+'/'+key)
    elif isinstance(a, list):
        if len(a) != len(b):
            raise ValueError('Length mismatch: ' + path)
        for i, (x, y) in enumerate(zip(a, b)):
            compare(x, y, tolerance, differences, path+'/'+str(i))
    elif a != b:
        raise ValueError('Value mismatch: ' + path)


def main(original):
    original = Path(original).resolve()
    report = ROOT/'reports/27_recovery_audit_20261019'
    source = original/RELATIVE
    r = read(report/'final_public_recheck.json')
    published = read(source/'verification_public.json')
    # Reuse the published numeric readback tolerance; decision gates remain exact.
    tolerance = read(source/'public_private_comparison.json')['absolute_and_relative_tolerance']
    if tolerance != 1e-12:
        raise ValueError('Published readback tolerance changed')
    differences = []
    compare(r, published, tolerance, differences)
    if not r['verified'] or r['images_checked'] != 59 or r['primary_pairs_complete'] != 12:
        raise ValueError('Incomplete analysis')
    paths = [RELATIVE+name for name in ('task_results.csv','status.json','verification_public.json',
        'results_figure.png','results_figure.pdf','public_private_comparison.json','local_readback.json')]
    paths += ['scripts/method_comparison_r4/analyze.py','protocols/27_method_design.json','protocols/27_method_runtime_r4.json']
    source_hashes = {}
    for relative in paths:
        blob = subprocess.run(['git','-c','safe.directory='+original.as_posix(),'-C',str(original),
                               'show',COMMIT+':'+relative], capture_output=True, check=True).stdout
        digest = sha(original/relative)
        if hashlib.sha256(blob).hexdigest() != digest:
            raise ValueError('Published source changed: '+relative)
        source_hashes[relative] = digest
    with (source/'task_results.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    failed = [row for row in rows if row['status']=='failed']
    if len(rows)!=36 or len(failed)!=1 or failed[0]['task_id']!='2' or failed[0]['method']!='jain' or failed[0]['bit_accuracy']!='':
        raise ValueError('Failure accounting differs')
    independent = {}
    for method in ('imprint','jain','delivery'):
        group = [row for row in rows if row['method']==method and row['status']=='completed']
        count = sum(float(row['bit_accuracy'])>.70703125 for row in group)
        mean = statistics.mean(float(row['bit_accuracy']) for row in group)
        if count!=r['summary'][method]['gs_pass_count'] or not math.isclose(mean,r['summary'][method]['conditional_mean_bit_accuracy'],abs_tol=tolerance):
            raise ValueError('CSV summary differs')
        independent[method] = dict(delivered=len(group),gs_passes=count,attempt_denominator=12,conditional_mean_bit_accuracy=mean)
    pairs = []
    for sid in range(1,13):
        by = {row['method']:row for row in rows if row['task_id']==str(sid)}
        a,b = by['imprint'],by['delivery']
        pairs.append(dict(mse_ratio=float(b['cover_mse_rgb01'])/float(a['cover_mse_rgb01']),
            time_ratio=float(b['core_seconds'])/float(a['core_seconds']),
            accuracy_difference=float(b['bit_accuracy'])-float(a['bit_accuracy'])))
    for key, target in [('mse_ratio','median_paired_pixel_mse_ratio'),('time_ratio','median_paired_core_time_ratio')]:
        if not math.isclose(statistics.median(p[key] for p in pairs),r[target],abs_tol=tolerance):
            raise ValueError('CSV paired summary differs')
    if sum(p['accuracy_difference']<0 for p in pairs)!=10 or sum(p['mse_ratio']<1 for p in pairs)!=12:
        raise ValueError('Paired direction counts differ')
    copies = {'task_results.csv':'final_task_results.csv','results_figure.png':'method_comparison_results.png',
              'results_figure.pdf':'method_comparison_results.pdf'}
    for src,dst in copies.items():
        with (report/dst).open('xb') as stream:
            stream.write((source/src).read_bytes())
    result = dict(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        live_check_at_utc='2026-10-19T21:30:45Z', run='27_method_resume_20261019T173017Z',
        attacks=dict(completed=35,running=0,pending=0,failed=1,unknown=0),
        controller_or_worker_processes_observed=[], scheduler_completed_at_utc='2026-10-19T21:16:52.277621+00:00',
        postprocessing_state='verified_and_packaged', original_publication_commit=COMMIT,
        source_files_match_commit=source_hashes, public_analyzer_rerun_matches_within_published_tolerance=True,
        numeric_readback_tolerance=tolerance, maximum_numeric_difference=max(differences),
        local_independent_message_decodes=0, server_reported_independent_message_decodes=59,
        local_public_images_checked=59, cpu_only=True, gpu_processes_started=0,
        original_evidence_modified=False,private_material_exported=False,csv_summary_recomputed=independent,
        decision=r['decision'],decision_gates=r['decision_gates'],gs_pass_gain=r['gs_pass_gain'],
        median_paired_pixel_mse_ratio=r['median_paired_pixel_mse_ratio'],
        median_paired_core_time_ratio=r['median_paired_core_time_ratio'],
        mean_paired_accuracy_difference=r['mean_bit_accuracy_difference'],
        artifact_sha256={name:sha(report/name) for name in ['final_public_recheck.json']+list(copies.values())},
        readback_script_sha256=sha(Path(__file__)),next_progress_check_required=False,
        remaining_scientific_unknowns=['Full geometry/SemBind acceptance','Formal independent content labels',
                                      'Population inference','Novelty and superiority of a new method'])
    with (report/'final_closeout.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(source_files_checked=len(paths),csv_summary=independent,
                         maximum_numeric_difference=max(differences),decision=r['decision']),indent=2))


if __name__=='__main__':
    main(sys.argv[1])
