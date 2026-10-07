"""Fetch only the pinned small public source files listed in the audit manifests."""
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/reproduction_audit'


def main():
    repos = json.loads((REPORT / 'public_code_inventory.json').read_text())['repositories']
    repos.append(json.loads((REPORT / 'csi_code_inventory.json').read_text()))
    total = sum(f['bytes'] for r in repos for f in r['files'])
    assert total <= 1_000_000, 'Source download budget exceeded'
    downloaded = 0
    for repo in repos:
        for f in repo['files']:
            assert f['bytes'] <= 200_000
            rel = PurePosixPath(f['path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            expected = f"https://raw.githubusercontent.com/{repo['repo']}/{repo['commit']}/{f['path']}"
            assert f['url'] == expected
            target = ROOT / 'runs/reproduction_audit' / repo['repo'].split('/')[1] / f['path']
            if target.exists():
                data = target.read_bytes()
            else:
                with urlopen(expected, timeout=30) as response:
                    data = response.read(f['bytes'] + 1)
                assert len(data) == f['bytes']
                assert hashlib.sha256(data).hexdigest() == f['sha256']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                downloaded += len(data)
            assert hashlib.sha256(data).hexdigest() == f['sha256'], target
    print(json.dumps({'verified_source_bytes': total, 'downloaded_bytes': downloaded}))


if __name__ == '__main__':
    main()
