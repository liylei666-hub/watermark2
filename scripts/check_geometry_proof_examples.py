"""Closed-form mathematical checks, independent of models and official scores."""
import os

if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
    raise SystemExit('Set CUDA_VISIBLE_DEVICES="" for this CPU-only check.')

import json
import math


def results():
    # z=sqrt(N)e1 and u=e2 give exact finite-dimensional illustrations.
    # Gaussian convergence is proved in the accompanying note, not simulated.
    a = 0.01
    angular = []
    for n in (64, 256, 4096, 16384, 1048576):
        theta = math.atan2(1.0, (1.0 + a) * math.sqrt(n))
        cosine = (1.0 + a) * math.sqrt(n) / math.sqrt((1.0 + a) ** 2 * n + 1.0)
        assert math.isclose(math.cos(theta), cosine, abs_tol=1e-14)
        angular.append({"dimension": n, "normalized_mse": a * a + 1.0 / n,
                        "orthogonal_energy": 1.0, "angle_radians": theta})
    assert all(x["angle_radians"] > y["angle_radians"] for x, y in zip(angular, angular[1:]))
    assert all(x["normalized_mse"] > a * a for x in angular)

    # Diagonal SPD matrices: AIRM is Euclidean norm of log eigenvalue ratios.
    def diagonal_airm(p, q):
        assert len(p) == len(q) and all(v > 0 for v in p + q)
        return math.sqrt(math.fsum(math.log(y / x) ** 2 for x, y in zip(p, q)))

    p, q, g = [1.0, 1.0], [4.0, 4.0], [2.0, 3.0]
    distance = diagonal_airm(p, q)
    transformed = diagonal_airm([x * s * s for x, s in zip(p, g)],
                                [y * s * s for y, s in zip(q, g)])
    assert math.isclose(distance, math.sqrt(2.0) * math.log(4.0), abs_tol=1e-14)
    assert math.isclose(distance, transformed, abs_tol=1e-14) and distance > 0
    conditioning = []
    for epsilon in (0.01, 0.0001, 0.000001):
        d = diagonal_airm([epsilon, 1.0], [2 * epsilon, 1.0])
        assert math.isclose(d, math.log(2.0), abs_tol=1e-14)
        conditioning.append({"epsilon": epsilon, "frobenius_difference": epsilon, "airm": d})

    # f_N(X)=1+tanh(X1), X standard Gaussian. Mean=median=1 by symmetry.
    # P(f_N>1/2)=Phi(atanh(1/2)), independent of ambient dimension.
    probability = 0.5 * (1.0 + math.erf(math.atanh(0.5) / math.sqrt(2.0)))
    assert 0.70 < probability < 0.72
    return {
        "kind": "synthetic_closed_form_mathematical_checks",
        "gpu_used": False, "models_loaded": False, "new_model_experiments_run": 0,
        "official_geometry_implementation_executed": False,
        "angular_example": {"a": a, "representative_norm": "sqrt(N)", "rows": angular},
        "airm_example": {"dimension": 2, "one_sided_scale": 2,
                         "distance": distance, "simultaneous_congruence_distance": transformed,
                         "conditioning_rows": conditioning},
        "gaussian_example": {"function": "1+tanh(X1)", "lipschitz_constant": 1,
                             "mean_and_median": 1, "threshold": 0.5,
                             "probability_above_threshold": probability,
                             "depends_on_ambient_dimension": False},
        "scope": "Checks illustrative formulas; does not implement a watermark verifier or attack."
    }


if __name__ == "__main__":
    print(json.dumps(results(), ensure_ascii=False, indent=2, allow_nan=False))
