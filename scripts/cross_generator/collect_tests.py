"""Verify and export stage24 public evidence; evaluator keys stay outside the run."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':raise SystemExit('CPU visibility required')
import datetime,json,sys,zipfile
from pathlib import Path
import io_contract as c
from verify_tests import verify
from verify_message_scores import main as verify_scores
from source_worker import r


def main():
    source=r.ROOT/'runs/24_cross_generator_20261018T044821Z';folder=source/'tests'
    result=verify(source);scores=verify_scores(source)
    report=r.ROOT/'reports/24_cross_generator'
    result.update(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        independent_message_score_check=scores,verifier_sha256=c.sha(Path(__file__).with_name('verify_tests.py')),
        message_verifier_sha256=c.sha(Path(__file__).with_name('verify_message_scores.py')))
    c.write(report/'test_verification.json',result)
    paths=[]
    allowed_dirs={'proxy_generate_0','proxy_generate_1','target_generate_0','target_generate_1','target_inverse_0','target_inverse_1',
                  'target_images','proxy_test_inputs','target_test_inputs','proxy_test_predictions','target_test_predictions'}
    allowed_files={'launch_intent.json','prediction_cpu_execution.json','test_predictions_sealed.json','evaluation.json','status.json'}
    for path in folder.rglob('*'):
        if path.is_symlink():raise ValueError('Symlink in evidence')
        if not path.is_file():continue
        rel=path.relative_to(folder)
        if (len(rel.parts)==1 and rel.name not in allowed_files) or (len(rel.parts)>1 and rel.parts[0] not in allowed_dirs):raise ValueError('Unexpected artifact')
        if path.suffix=='.bin' or any(word in path.name for word in ['secret','material','nonce','message','key']):raise ValueError('Private material forbidden')
        paths.append(path)
    records={p.relative_to(folder).as_posix():c.sha(p) for p in sorted(paths)}
    c.write(folder/'test_artifacts_sealed.json',dict(files=records,source_fit_unchanged=True,
            prelaunch_publication_commit='f2d1646e6d1906dda93def2008eba861a7588fb5'))
    paths.extend([folder/'test_artifacts_sealed.json',report/'test_verification.json'])
    archive=r.ROOT/(source.name+'_test_evidence.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for path in paths:z.write(path,path.relative_to(r.ROOT).as_posix())
    print(json.dumps(dict(archive=str(archive),archive_sha256=c.sha(archive),files=len(paths),bytes=archive.stat().st_size,
                         test_files_sealed=len(records),summaries=result['summaries'],
                         official_scores_cross_checked=scores['official_scores_cross_checked']),indent=2))


if __name__=='__main__':main()
