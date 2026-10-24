"""CPU-only design and evaluator reduction for the proposed crossed diagnostic."""
import math
import statistics

CLASSES = ('simple', 'complex')


def cells():
    return [(b, r, c) for b in range(1, 5) for r in CLASSES for c in CLASSES]


def attack_inputs(plan, cell):
    """Allowlist excludes generation metadata, target identity and evaluator state."""
    block, reference, cover = cell
    data = plan['blocks'][block - 1]
    return dict(block=block, reference_id=data['references'][reference]['id'],
                cover_id=data['covers'][cover]['id'], method='pixel50',
                inversion_steps=50, seed=data['attack_seed'], proxy=plan['proxy'],
                policy=plan['policy'])


def validate(plan):
    assert plan['status'] == 'proposal_frozen_for_scientific_review_not_launch_runtime'
    assert plan['inversion']['timesteps'] == list(range(1, 982, 20))
    assert plan['method'] == 'unchanged_stage29_pixel50'
    assert len(plan['blocks']) == 4
    identities, seeds = [], []
    for expected, block in enumerate(plan['blocks'], 1):
        assert block['block'] == expected
        for role in ('references', 'covers'):
            assert set(block[role]) == set(CLASSES)
            for image in block[role].values():
                seeds.append(image['seed'])
                assert image['prompt']
        identities.extend(x['id'] for x in block['references'].values())
    assert len(set(identities)) == 8 and len(set(seeds)) == 16
    assert sorted(map(tuple, plan['attack_order'])) == sorted(cells())
    for cell in cells():
        job = attack_inputs(plan, cell)
        assert not set(job) & {'target', 'key', 'message', 'nonce', 'score', 'original_noise'}
    return dict(blocks=4, independent_reference_identities=8, cover_images=8,
                attacks=16, reference_evaluations=8, clean_cover_identity_pairs=16,
                candidate_evaluations=16, target_inversions=40, inference_units=4)


def reduce(rows, references, *, delivery_qualified, generated_classes_valid):
    """Evaluator-only; one row per crossed cell and its identity-matched clean cover."""
    expected = set(cells())
    by = {(row['block'], row['reference_class'], row['cover_class']): row for row in rows}
    if len(rows) != 16 or set(by) != expected:
        return dict(decision='inconclusive_missing_or_duplicate_cells')
    if set(references) != {(b, r) for b in range(1, 5) for r in CLASSES}:
        return dict(decision='inconclusive_reference_evidence')
    for row in rows:
        for key in ('attack_ba', 'clean_ba'):
            value = row[key]
            if not math.isfinite(value) or not 0 <= value <= 1 or value * 256 != int(value * 256):
                raise ValueError('Invalid message accuracy')
        if row['clean_reference_id'] != row['reference_id']:
            raise ValueError('Clean cover evaluated under wrong identity')
        if row['reference_id'] != 2 * row['block'] - (row['reference_class'] == 'simple'):
            raise ValueError('Reference identity differs from frozen block mapping')
    if not all(math.isfinite(v) and v > .70703125 for v in references.values()):
        return dict(decision='inconclusive_invalid_reference')
    if delivery_qualified is not True or generated_classes_valid is not True:
        return dict(decision='inconclusive_quality_time_or_generated_class')
    blocks = []
    for b in range(1, 5):
        gain = {(r, c): by[b, r, c]['attack_ba'] - by[b, r, c]['clean_ba']
                for r in CLASSES for c in CLASSES}
        cover = statistics.mean(gain[r, 'simple'] - gain[r, 'complex'] for r in CLASSES)
        reference = statistics.mean(gain['simple', c] - gain['complex', c] for c in CLASSES)
        interaction = ((gain['simple', 'simple'] - gain['simple', 'complex']) -
                       (gain['complex', 'simple'] - gain['complex', 'complex']))
        blocks.append(dict(block=b, cover_gap=cover, reference_gap=reference,
                           interaction_difference_of_differences=interaction))
    mean = statistics.mean(b['cover_gap'] for b in blocks)
    gate = mean >= .05 and all(b['cover_gap'] > 0 for b in blocks)
    return dict(decision='retain_cover_susceptibility_for_independent_confirmation' if gate else
                'close_fixed_cover_susceptibility_hypothesis', blocks=blocks,
                mean_cover_gap=mean, inference_units=4, significance_claim=False,
                novel_method=False, general_cover_causal_claim=False)
