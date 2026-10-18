"""Synthetic, standard-library checks for the GS majority-decoder argument.

No image, model, historical latent, watermark identity, or secret is read.
The binary decoder is an abstract specification, not an official verifier.
"""
import os
if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise SystemExit('CPU-only visibility required')
import json
from fractions import Fraction
from itertools import product

def vote(bits):
    return int(sum(bits) > len(bits) // 2)

def distance_to_change(bits):
    n, v = len(bits), sum(bits)
    return v - n // 2 if vote(bits) else n // 2 + 1 - v

def hamming(a, b):
    return sum(x != y for x, y in zip(a, b))

def main():
    pairs = 0
    for n in range(1, 7):
        values = list(product((0, 1), repeat=n))
        for reference in values:
            minimum = min(hamming(reference, candidate) for candidate in values
                          if vote(reference) != vote(candidate))
            assert minimum == distance_to_change(reference)
            for candidate in values:
                assert int(vote(reference) != vote(candidate)) <= int(
                    hamming(reference, candidate) >= minimum)
                pairs += 1
    xor_cases = 0
    for n in range(1, 5):
        values = list(product((0, 1), repeat=n))
        for a, b, mask in product(values, repeat=3):
            assert hamming(a, b) == hamming(
                [x ^ k for x, k in zip(a, mask)],
                [x ^ k for x, k in zip(b, mask)])
            xor_cases += 1
    # All-one plaintext, a public mathematical toy: no cipher keys are used.
    reference = [Fraction(1)] * 64
    near = [Fraction(-1, 1000)] * 33 + [Fraction(1)] * 31
    far = [Fraction(2)] * 64
    mse = lambda z: sum((x-y)**2 for x,y in zip(z, reference))/64
    decoded = lambda z: vote([int(x >= 0) for x in z])
    assert mse(near) < mse(far) and decoded(near) == 0 and decoded(far) == 1
    # Identical total sign errors, different message errors (including tie-to-zero).
    concentrated = [[0] * 64, [1] * 64]
    spread = [[0] * 32 + [1] * 32] * 2
    assert sum(sum(1-b for b in c) for c in concentrated) == 64
    assert sum(sum(1-b for b in c) for c in spread) == 64
    assert [vote(c) for c in concentrated] == [0, 1]
    assert [vote(c) for c in spread] == [0, 0]
    assert distance_to_change([1] * 33 + [0] * 31) == 1
    assert distance_to_change([1] * 32 + [0] * 32) == 1
    assert distance_to_change([1] * 64) == 32
    assert distance_to_change([0] * 64) == 33
    # Real-arithmetic margin bound at several exact rational thresholds.
    margin_cases = 0
    values = [Fraction(-2), Fraction(-1, 10), Fraction(0), Fraction(1, 10), Fraction(2)]
    for r, z, alpha in product(values, values, [Fraction(1,100), Fraction(1,2), Fraction(1)]):
        mismatch = int((r >= 0) != (z >= 0))
        bound = int(abs(r) < alpha) + (z-r)**2 / alpha**2
        assert mismatch <= bound
        margin_cases += 1
    return dict(status='passed', scope='Synthetic decoder algebra; not a model or attack experiment',
        majority_pairs_checked=pairs, xor_cases_checked=xor_cases, rational_margin_cases=margin_cases,
        mse_counterexample=dict(lower_mse=float(mse(near)), higher_mse=float(mse(far)),
            lower_mse_decoded_bit=decoded(near), higher_mse_decoded_bit=decoded(far)),
        same_sign_error_count=64, concentrated_message_errors=1, spread_message_errors=2,
        repetition64_minimum_flip_examples=dict(all_ones=32, all_zeros=33, votes33=1, votes32=1),
        gpu_used=False, models_loaded=False, new_model_experiments_run=0,
        original_runs_read=False, original_runs_modified=False)

if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
