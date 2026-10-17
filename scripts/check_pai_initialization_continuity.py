"""Deterministic scalar arithmetic for a published initializer; no model experiment.

Source: QingyuLiu/PAI commit 9ebc58d1a106e7155347f0d1f186e67313a4b0cf,
encode.py:81-89. All keys and uniforms below are synthetic scalar examples.
This does not implement an attack, a diffusion trajectory or a verifier.
"""

import json
import math


def initializer(key, uniform):
    cdf = 0.5 * (1 + math.erf(key / math.sqrt(2)))
    return math.sqrt(-2 * math.log(uniform)) * math.cos(2 * math.pi * cdf)


def main():
    key, uniform = 0.4, 0.37
    reference = initializer(key, uniform)
    assert initializer(key, uniform) == reference
    rows = []
    for delta in (1e-1, 1e-2, 1e-3, 1e-4, 1e-6):
        candidate = initializer(key + delta, uniform)
        distance_squared = (reference - candidate) ** 2
        diagonal_terms = reference ** 2 + candidate ** 2
        cross_term = -2 * reference * candidate
        # |dF/dK| <= sqrt(-2 log U) * sqrt(2 pi).
        lipschitz_squared_bound = (-2 * math.log(uniform)) * 2 * math.pi * delta ** 2
        assert distance_squared <= lipschitz_squared_bound + 1e-14
        assert math.isclose(distance_squared, diagonal_terms + cross_term, abs_tol=1e-14)
        rows.append({
            "key_delta": delta,
            "initializer_squared_difference": distance_squared,
            "diagonal_terms_without_cross_term": diagonal_terms,
            "cross_term": cross_term,
            "squared_lipschitz_bound": lipschitz_squared_bound,
        })
    assert all(b["initializer_squared_difference"] < a["initializer_squared_difference"]
               for a, b in zip(rows, rows[1:]))
    assert rows[-1]["initializer_squared_difference"] < 1e-10
    assert rows[-1]["diagonal_terms_without_cross_term"] > 1
    return {
        "status": "passed",
        "scope": "synthetic deterministic scalar initializer arithmetic",
        "synthetic_inputs": {"key": key, "uniform": uniform},
        "rows": rows,
        "model_experiments": 0,
        "target_keys_read": False,
        "attack_success": None,
        "interpretation": "Continuity and cross-term cancellation in the initializer only; no conclusion about full verifier bypass or key recovery.",
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
