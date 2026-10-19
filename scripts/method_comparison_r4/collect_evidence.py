"""CPU-only idempotent collection of the server's hash-verified stage27 evidence ZIP."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import hashlib,json,sys,zipfile
from pathlib import Path,PurePosixPath

def sha(data):return hashlib.sha256(data).hexdigest()
def main(archive,expected_sha256,project):
    archive=Path(archive);project=Path(project).resolve()
    if sha(archive.read_bytes())!=expected_sha256:raise ValueError('Transferred archive hash mismatch')
    cfg=json.loads((project/'protocols/27_method_runtime_r4.json').read_text(encoding='utf-8'));run=cfg['run_dir'];report='reports/'+Path(run).name
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive paths')
        for name in names:
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or not (name.startswith(run+'/') or name.startswith(report+'/')):raise ValueError('Unexpected archive member')
        manifest_name=report+'/artifact_manifest.json';manifest=json.loads(z.read(manifest_name))
        records={rec['path']:rec for rec in manifest['files']}
        if set(names)!=set(records)|{manifest_name} or len(records)!=len(manifest['files']):raise ValueError('Archive differs from manifest inventory')
        if manifest['private_material_included'] or manifest['original_source_run']!=cfg['source_run'] or manifest['original_source_files']!=cfg['source_files']:raise ValueError('Source provenance differs')
        if sum(i.file_size for i in z.infolist())>cfg['max_new_bytes']:raise ValueError('Archive exceeds storage allowance')
        for rel,h in cfg['source_files'].items():
            if sha((project/cfg['source_run']/rel).read_bytes())!=h:raise ValueError('Original local source evidence changed')
        for name in names:
            data=z.read(name);record=records.get(name)
            if record and (len(data)!=record['bytes'] or sha(data)!=record['sha256']):raise ValueError('Member hash or size mismatch')
            dst=project/name
            if not dst.resolve().is_relative_to(project):raise ValueError('Resolved target escapes repository')
            if dst.exists() and dst.read_bytes()!=data:raise ValueError('Existing evidence conflicts: '+name)
        # Every source and destination has been checked before writing missing files.
        for name in names:
            dst=project/name
            if not dst.exists():
                dst.parent.mkdir(parents=True,exist_ok=True)
                with dst.open('xb') as f:f.write(z.read(name))
    result=dict(verified=True,archive_sha256=expected_sha256,archive_bytes=archive.stat().st_size,transferred_files=len(names),original_source_files_verified=len(cfg['source_files']),existing_artifacts_reused_only_on_exact_match=True,private_material_included=False,gpu_used=False,models_loaded=False)
    output=project/report/'local_readback.json';data=(json.dumps(result,indent=2)+'\n').encode()
    if output.exists():
        if output.read_bytes()!=data:raise ValueError('Existing readback evidence differs')
    else:
        with output.open('xb') as f:f.write(data)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main(*sys.argv[1:])
