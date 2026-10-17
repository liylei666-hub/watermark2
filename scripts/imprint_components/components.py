"""Scalar decomposition of a composed finite-step directional discrepancy."""
import math


def decompose(analytic, chain_secant, whole_secant):
    if not all(math.isfinite(x) for x in [analytic, chain_secant, whole_secant]):
        raise ValueError('Nonfinite directional value')
    return dict(analytic=analytic, chain_secant=chain_secant, whole_secant=whole_secant,
        map_linearization_residual=analytic-chain_secant,
        inverse_linearization_residual=chain_secant-whole_secant,
        total_residual=analytic-whole_secant)
