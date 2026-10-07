"""Offline document/config checks and byte-level preservation of tracked legacy assets."""
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OLD = '1eeea4c95e555bfabc242b90aad35ca813557443'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True, encoding='utf-8').strip()


def check():
    references = json.loads((ROOT / 'research/references.json').read_text(encoding='utf-8'))
    config = json.loads((ROOT / 'configs/pilot.json').read_text(encoding='utf-8'))
    ids = [r['id'] for r in references]
    assert len(ids) == len(set(ids)) == 7
    assert set(config['required_references']) == set(ids)
    matrix = (ROOT / 'research/literature.md').read_text(encoding='utf-8')
    for ref in references:
        assert ref['id'] in matrix
        assert all(ref.get(k) for k in ['title', 'authors', 'venue', 'status', 'scope', 'checked'])
        parsed = urlparse(ref['url'])
        assert parsed.scheme == 'https' and parsed.netloc
    assert config['status'] == 'planned_not_executed' and not config['new_experiment_results']
    assert sum(config['planned_source_groups'].values()) == 48
    assert len(config['allowed_transforms']) == 4
    assert config['primary_calibration_benign_acceptance'] == .95
    assert all(v == 0 for v in config['execution_budget'].values())
    assert config['full_verifier_required']
    links = 0
    docs = [ROOT / 'README.md', ROOT / 'AGENTS.md', *sorted((ROOT / 'research').glob('*.md'))]
    for path in docs:
        content = path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if urlparse(target).scheme or target.startswith('#'):
                continue
            assert (path.parent / target.split('#')[0]).exists(), f'broken link: {path.name}: {target}'
            links += 1
    archived = 0
    for entry in git('ls-tree', '-r', OLD).splitlines():
        metadata, path = entry.split('\t', 1)
        if path.startswith('.'):
            continue
        legacy = ROOT / 'legacy' / path
        assert legacy.is_file(), f'missing archive: {path}'
        blob = git('hash-object', '--path=' + path, str(legacy))
        assert blob == metadata.split()[2], f'changed archive: {path}'
        archived += 1
    assert not (ROOT / '.github/workflows').exists(), 'review new workflows before publishing'
    return dict(status='passed', references=len(ids), local_links=links, legacy_blobs_identical=archived,
                config_status=config['status'], scope='offline links, metadata, config and archive; not scientific novelty or external URL availability')


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
