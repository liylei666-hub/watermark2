"""Pinned stage23 infrastructure; no model imports on import."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cover_pilot'))
import runtime as r
from contract import read, write, sha

def design(path):
    path = Path(path)
    if sha(path) != path.with_suffix('.sha256').read_text().strip():
        raise ValueError('Scientific design changed')
    return read(path)
