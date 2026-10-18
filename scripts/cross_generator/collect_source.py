"""CPU readback, whole-source sealing and explicit evidence export for stage24."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise RuntimeError('CPU collection requires empty CUDA visibility')
import datetime
import json
from pathlib import Path
import sys
import zipfile
import io_contract as c
import source_control as control
from verify_source import verify


def main(run_name):
    if not run_name.startswith('24_cross_generator_') or '/' in run_name or '\\' in run_name:
        raise ValueError('Expected stage24 run basename')
    root = control.r.ROOT / 'runs' / run_name
    cfg = control.r.verify_runtime(control.RUNTIME)
    plan = control.jobs(control.JOBS, cfg)
    entries = control.source_entries(root, plan)
    for split, folder in [('train','train_inputs'), ('validation','validation_inputs')]:
        bundle = c.read(root / folder / 'bundle.json')
        for row in bundle['rows']:
            for name in ('estimate','original_noise'):
                if row[name]['sha256'] != c.sha(entries[row['sample_id']][name]):
                    raise ValueError('Export differs from source generation record')
    verified = verify(root)
    # Hash every raw source output and fit artifact before future test generation.
    paths = []
    allowed_dirs = {'source_'+str(i) for i in range(6)} | {'train_inputs','validation_inputs','source_fit'}
    allowed_top = {'launch_intent.json','source_cpu_execution.json','source_status.json'}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Run symlink not allowed')
        if not path.is_file(): continue
        rel = path.relative_to(root)
        if (len(rel.parts)==1 and rel.name not in allowed_top) or (len(rel.parts)>1 and rel.parts[0] not in allowed_dirs):
            raise ValueError('Unexpected source publication path: '+str(rel))
        if path.suffix == '.bin': raise ValueError('Private binary file forbidden')
        paths.append(path)
    artifacts = {p.relative_to(root).as_posix():c.sha(p) for p in sorted(paths)}
    c.write(root / 'source_phase_sealed.json', dict(version=1, files=artifacts,
            design_sha256=plan['design_sha256'], source_runtime_sha256=c.sha(control.RUNTIME),
            frozen_publication_commit='6ccd379971a22f3a113f72ed335074af3320fe22'))
    paths.append(root / 'source_phase_sealed.json')
    report_folder = control.r.ROOT / 'reports/24_cross_generator'; report_folder.mkdir(exist_ok=True)
    verified.update(checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    run_dir=str(root), source_files_sealed=len(artifacts),
                    source_phase_seal_sha256=c.sha(root/'source_phase_sealed.json'),
                    collector_sha256=c.sha(__file__), private_material_published=False)
    c.write(report_folder/'source_verification.json', verified)
    archive = control.r.ROOT / (run_name+'_source_evidence.zip')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for path in paths:
            if c.sha(path) != (artifacts.get(path.relative_to(root).as_posix()) or verified['source_phase_seal_sha256']):
                raise ValueError('Source changed during packaging')
            z.write(path, path.relative_to(control.r.ROOT).as_posix())
        z.write(report_folder/'source_verification.json', 'reports/24_cross_generator/source_verification.json')
    print(json.dumps(dict(archive=str(archive),archive_sha256=c.sha(archive),files=len(paths)+1,
                         bytes=archive.stat().st_size,verification=verified), indent=2))


if __name__ == '__main__':
    main(sys.argv[1])
