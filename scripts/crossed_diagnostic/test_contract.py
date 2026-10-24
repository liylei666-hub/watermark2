import copy
import hashlib
import json
from pathlib import Path
import unittest
import contract as c

PLAN = json.loads((Path(__file__).resolve().parents[2] / 'protocols/30_crossed_proposal.json').read_text(encoding='utf8'))


def fixture():
    rows = []
    for b, r, cover in c.cells():
        ref = 2 * b - (r == 'simple')
        rows.append(dict(block=b, reference_class=r, cover_class=cover,
                         reference_id=ref, clean_reference_id=ref, clean_ba=.5,
                         attack_ba=.8125 if cover == 'simple' else .6875))
    return rows


def run(rows, **kwargs):
    return c.reduce(rows, {(b, r): 1. for b in range(1, 5) for r in c.CLASSES},
                    delivery_qualified=kwargs.get('delivery', True),
                    generated_classes_valid=kwargs.get('content', True))


class Contract(unittest.TestCase):
    def test_balance_denominators_and_order(self):
        counts = c.validate(PLAN)
        self.assertEqual(counts['target_inversions'], 40)
        self.assertEqual(counts['inference_units'], 4)
        bad = copy.deepcopy(PLAN); bad['attack_order'][-1] = bad['attack_order'][0]
        with self.assertRaises(AssertionError): c.validate(bad)

    def test_core_policy_unchanged(self):
        prior = json.loads((Path(__file__).resolve().parents[2] / 'protocols/29_quality_design.json').read_text(encoding='utf8'))
        self.assertEqual(PLAN['policy'], prior['policy'])
        self.assertEqual(PLAN['proxy'], prior['proxy'])
        self.assertEqual(PLAN['target'], prior['target'])
        root = Path(__file__).resolve().parents[2]
        for key, path in [('core_sha256', PLAN['core_source']), ('quantizer_sha256', PLAN['core_quantizer'])]:
            self.assertEqual(PLAN[key], hashlib.sha256((root / path).read_bytes()).hexdigest())
        proposal = root / 'protocols/30_crossed_proposal.json'
        self.assertEqual(proposal.with_suffix('.sha256').read_text().strip(), hashlib.sha256(proposal.read_bytes()).hexdigest())

    def test_predicted_direction_and_block_unit(self):
        result = run(fixture())
        self.assertTrue(result['decision'].startswith('retain_'))
        self.assertEqual(result['mean_cover_gap'], .125)
        self.assertEqual(len(result['blocks']), 4)
        self.assertTrue(all(b['reference_gap'] == b['interaction_difference_of_differences'] == 0 for b in result['blocks']))

    def test_matching_clean_baseline_can_remove_apparent_cover_gap(self):
        rows = fixture()
        for row in rows:
            if row['cover_class'] == 'simple': row['clean_ba'] += .125
        self.assertEqual(run(rows)['mean_cover_gap'], 0.)

    def test_reference_effect_separate_from_cover(self):
        rows = fixture()
        for row in rows:
            if row['reference_class'] == 'simple': row['attack_ba'] += .0625
        result = run(rows)
        self.assertEqual(result['mean_cover_gap'], .125)
        self.assertTrue(all(b['reference_gap'] == .0625 for b in result['blocks']))

    def test_interaction_and_reference_mapping(self):
        rows = fixture()
        for row in rows:
            if row['reference_class'] == row['cover_class'] == 'simple': row['attack_ba'] += .0625
        self.assertTrue(all(b['interaction_difference_of_differences'] == .0625 for b in run(rows)['blocks']))
        rows[0]['reference_id'] = rows[0]['clean_reference_id'] = 100
        with self.assertRaises(ValueError): run(rows)

    def test_one_nonpositive_block_closes_despite_large_mean(self):
        rows = fixture()
        for row in rows:
            if row['block'] == 4: row['attack_ba'] = .75
        self.assertTrue(run(rows)['decision'].startswith('close_'))

    def test_missing_duplicate_and_wrong_identity_fail_closed(self):
        self.assertTrue(run(fixture()[:-1])['decision'].startswith('inconclusive'))
        self.assertTrue(run(fixture()[:-1] + [fixture()[0]])['decision'].startswith('inconclusive'))
        rows = fixture(); rows[0]['clean_reference_id'] = 99
        with self.assertRaises(ValueError): run(rows)

    def test_invalid_qualification_or_class_is_inconclusive(self):
        for flag in (False, None):
            self.assertTrue(run(fixture(), content=flag)['decision'].startswith('inconclusive'))
            self.assertTrue(run(fixture(), delivery=flag)['decision'].startswith('inconclusive'))

    def test_threshold_equality_reference_rejected(self):
        refs = {(b, r): 1. for b in range(1, 5) for r in c.CLASSES}
        refs[1, 'simple'] = .70703125
        self.assertEqual(c.reduce(fixture(), refs, delivery_qualified=True,
                                 generated_classes_valid=True)['decision'], 'inconclusive_invalid_reference')


if __name__ == '__main__': unittest.main()
