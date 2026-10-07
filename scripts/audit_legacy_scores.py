"""Recompute saved stage03 counts; never generate images or new research results."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit():
    score_path = ROOT / 'legacy/outputs/stage03/pair_scores.csv'
    rows = list(csv.DictReader(score_path.open(encoding='utf-8', newline='')))
    metrics = json.loads((ROOT / 'legacy/outputs/stage03/metrics.json').read_text(encoding='utf-8'))
    thresholds = json.loads((ROOT / 'legacy/outputs/stage03/thresholds.json').read_text(encoding='utf-8'))
    assert dict(Counter(r['split'] + '/' + r['category'] for r in rows)) == metrics['counts']
    assert len({r['pair_id'] for r in rows}) == len(rows), 'duplicate pair IDs'
    cal_families = {r['family'] for r in rows if r['split'] == 'calibration'}
    test_families = {r['family'] for r in rows if r['split'] == 'test'}
    assert not cal_families & test_families, 'family leakage'
    checked = 0
    main = {}
    for method, detail in metrics['methods'].items():
        assert all(math.isfinite(float(r[method])) for r in rows)
        for target, point in detail['working_points'].items():
            calibration = sorted(float(r[method]) for r in rows if r['split'] == 'calibration' and r['category'] == 'A')
            threshold = calibration[math.floor(float(target) * len(calibration))]
            assert threshold == point['threshold'] == thresholds['thresholds'][target][method]
            groups = [('calibration', 'A', point['calibration_A'])]
            groups += [('test', category, saved) for category, saved in point['test'].items()]
            for split, category, saved in groups:
                selected = [r for r in rows if r['split'] == split and r['category'] == category]
                def count(items):
                    return sum(float(r[method]) < threshold if category == 'A' else float(r[method]) >= threshold for r in items)
                assert (count(selected), len(selected)) == (saved['count'], saved['total'])
                assert math.isclose(count(selected) / len(selected), saved['rate'], abs_tol=1e-12)
                checked += 1
                for transform, saved_t in saved['by_transform'].items():
                    subset = [r for r in selected if r['transform'] == transform]
                    assert (count(subset), len(subset)) == (saved_t['count'], saved_t['total'])
                    checked += 1
            if target == '0.05':
                main[method] = {c: {'count': v['count'], 'total': v['total']} for c, v in point['test'].items()}
    return dict(status='passed', scope='recalculation_of_existing_scores_only', rows=len(rows),
                checked_count_cells=checked, calibration_families=len(cal_families), test_families=len(test_families),
                score_sha256=hashlib.sha256(score_path.read_bytes()).hexdigest(), main_working_point=main,
                not_checked=['source image pixels', 'feature extraction', 'GPU execution', 'new attacks', 'full verifier'])


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
