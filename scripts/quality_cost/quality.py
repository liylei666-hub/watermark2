"""Deterministic RGB byte feasibility; no model or evaluator dependencies."""
import math
import numpy as np


def certify(candidate, cover, mse_limit, linf_levels):
    if candidate.dtype != np.uint8 or cover.dtype != np.uint8 or candidate.shape != cover.shape:
        raise ValueError('Expected matching RGB byte arrays')
    delta = candidate.astype(np.int64)-cover.astype(np.int64)
    squared = int(np.sum(delta*delta, dtype=np.int64))
    allowance = math.floor(mse_limit*65025*candidate.size)
    maximum = int(np.abs(delta).max())
    return dict(squared_byte_error=squared, squared_byte_allowance=allowance,
                mse_rgb01=squared/(65025*candidate.size), linf_levels=maximum,
                feasible=squared <= allowance and maximum <= linf_levels)


def quantize_feasible(value, cover, mse_limit, linf_levels):
    """Round toward cover, then allocate remaining byte increments by fractional part.

    This is a fixed feasible quantizer, not a claim of exact Euclidean projection.
    No target score or reference image enters it.
    """
    if not np.isfinite(value).all() or cover.dtype != np.uint8 or value.shape != cover.shape:
        raise ValueError('Invalid image')
    if not 0 < mse_limit <= 1 or not 0 < linf_levels <= 255:
        raise ValueError('Invalid quality contract')
    base = cover.astype(np.float64)
    delta = np.clip(np.clip(value, 0, 1)*255-base, -linf_levels, linf_levels)
    delta = np.clip(delta, -base, 255-base)
    allowance = math.floor(mse_limit*65025*cover.size)
    energy = float(np.sum(delta*delta))
    if energy > allowance:
        delta *= math.sqrt(allowance/energy)
    elif energy < .95*allowance:
        nearest=np.rint(base+delta).clip(0,255).astype(np.uint8)
        certificate=certify(nearest,cover,mse_limit,linf_levels)
        if certificate['feasible']:
            return nearest,certificate
    magnitude = np.abs(delta).ravel()
    integers = np.floor(magnitude).astype(np.int64)
    fractions = magnitude-integers
    remaining = allowance-int(np.sum(integers*integers, dtype=np.int64))
    eligible = np.flatnonzero((fractions > 1e-12) & (integers < linf_levels))
    order = eligible[np.argsort(-fractions[eligible], kind='stable')]
    costs = 2*integers[order]+1
    cumulative = np.cumsum(costs, dtype=np.int64)
    count = int(np.searchsorted(cumulative, remaining, side='right'))
    integers[order[:count]] += 1
    if count:
        remaining -= int(cumulative[count-1])
    # Remaining slack is smaller than the next cost; consume only admissible units.
    for index in order[count:]:
        cost = 2*int(integers[index])+1
        if cost <= remaining:
            integers[index] += 1
            remaining -= cost
        if remaining == 0:
            break
    signed = (np.sign(delta).ravel()*integers).reshape(cover.shape)
    result = (base+signed).astype(np.uint8)
    certificate = certify(result, cover, mse_limit, linf_levels)
    if not certificate['feasible']:
        raise ValueError('Quantizer violated quality contract')
    return result, certificate


def project_tensor(value, cover, mse_limit, linf_levels):
    """Common continuous box/L-infinity/L2 feasibility map for both arms."""
    import torch
    with torch.no_grad():
        delta = (value.clamp(0, 1)-cover).clamp(-linf_levels/255, linf_levels/255)
        mse = delta.square().mean()
        scale = torch.minimum(torch.ones_like(mse), torch.sqrt(mse_limit/mse.clamp_min(1e-30)))
        value.copy_(cover+scale*delta)


def enough_time(elapsed, durations, steps, budget, reserve):
    predicted = max(durations)*1.10+1 if durations else (65 if steps == 50 else 20)
    return elapsed+predicted+reserve <= budget
