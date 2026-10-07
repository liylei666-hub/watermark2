"""Run the existing frozen extractor with only its artifact namespace changed."""
import argparse, json
from pathlib import Path
from stage02.worker import worker

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--task',required=True);a=p.parse_args()
    raise SystemExit(worker(Path(__file__).resolve().parents[1],json.loads(Path(a.config).read_text()),a.task,stage='stage03'))
