"""Sum per-process wall times from original stage07+ execution records, including failures."""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU ledger requires CUDA_VISIBLE_DEVICES=""')
import hashlib
import json
import math
from pathlib import Path


def collect(root):
    records = []
    for stage in ['07', '08', '09', '10', '11', '12']:
        for folder in sorted((root / 'runs').glob(stage + '_*')):
            for file in sorted(folder.rglob('execution.json')):
                data = json.loads(file.read_text(encoding='utf-8'))
                value = data.get('elapsed_seconds', data.get('wall_time_seconds'))
                if value is None or not math.isfinite(value) or value < 0:
                    raise ValueError('Missing or invalid per-process duration: ' + str(file))
                records.append(dict(path=file.relative_to(root).as_posix(),
                    sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                    gpu_process_wall_seconds=value, exit_code=data['exit_code']))
    return dict(scope='Per-process stage07-12 execution records; earlier historical stages excluded',
        model_processes_with_execution=len(records),
        gpu_process_seconds=math.fsum(r['gpu_process_wall_seconds'] for r in records),
        nonzero_exit_processes=sum(r['exit_code'] != 0 for r in records),
        note='Wall time of GPU model processes, including failures; not measured GPU kernel time or successful sample count',
        records=records, verifier_gpu_used=False, verifier_models_loaded=False)


if __name__ == '__main__':
    print(json.dumps(collect(Path(__file__).resolve().parents[1]), indent=2))
