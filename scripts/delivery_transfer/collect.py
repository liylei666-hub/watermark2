"""Export completed public evidence after independent evaluator-private decoding."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise SystemExit('CPU visibility required')
import json,zipfile
from common import c,r
from verify import verify

def main():
    result=verify(r.ROOT,True);cfg=c.read(r.ROOT/'protocols/25_delivery_runtime.json');folder=r.ROOT/cfg['run_dir']
    report=r.ROOT/'reports/25_delivery_transfer/verification.json';c.write(report,result)
    paths=[]
    allowed_dirs={'attack_inputs','evaluation_images','generate_0','generate_1','evaluate_0','evaluate_1'}
    allowed_files={'launch_intent.json','conversion.json','candidates_sealed.json','results.json','status.json'}
    for p in folder.rglob('*'):
        if p.is_symlink():raise ValueError('Symlink in export')
        if not p.is_file():continue
        rel=p.relative_to(folder)
        if (len(rel.parts)==1 and p.name not in allowed_files) or (len(rel.parts)>1 and rel.parts[0] not in allowed_dirs):raise ValueError('Unexpected export file')
        if p.suffix not in {'.json','.jsonl','.npy','.npz','.png','.log'}:raise ValueError('Unexpected export type')
        paths.append(p)
    c.write(folder/'artifacts_sealed.json',dict(files={p.relative_to(folder).as_posix():c.sha(p) for p in sorted(paths)},
        prelaunch_publication_commit='440fb0e906fb845e287ff239403b36c0e61a79bc'))
    paths.extend([folder/'artifacts_sealed.json',report]);archive=r.ROOT/(folder.name+'_evidence.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for path in paths:z.write(path,path.relative_to(r.ROOT).as_posix())
    print(json.dumps(dict(archive=str(archive),sha256=c.sha(archive),bytes=archive.stat().st_size,files=len(paths),summary=result['result']['summary']),indent=2))

if __name__=='__main__':main()
