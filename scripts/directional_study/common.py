"""Pinned shared infrastructure; importing does not initialize CUDA."""
import sys
from pathlib import Path
ROOT=Path('/data0/liyanlei/watermark_research')
sys.path.insert(0,str(ROOT/'scripts/cover_pilot'))
import runtime as r
import interface as i

def design(path):
    path=Path(path)
    if i.sha(path)!=path.with_suffix('.sha256').read_text().strip():
        raise ValueError('Scientific design changed')
    return i.read(path)
