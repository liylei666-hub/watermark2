"""Fixed reference reliability scores and descriptive, image-level endpoints."""
import math
import numpy as np

def finite_vector(value):
    x = np.asarray(value, dtype=np.float64).ravel(order='C')
    if x.size == 0 or not np.isfinite(x).all():
        raise ValueError('Empty or nonfinite array')
    return x

def score_vectors(arrays):
    if set(arrays) != {25, 50, 100}:
        raise ValueError('Expected three fixed step counts')
    vectors = {k: finite_vector(v) for k, v in arrays.items()}
    if len({v.size for v in vectors.values()}) != 1:
        raise ValueError('Mismatched coordinates')
    normalized = {}
    for k, v in vectors.items():
        rms = float(np.sqrt(np.mean(v * v)))
        if not np.isfinite(rms) or rms <= 0:
            raise ValueError('Invalid RMS')
        normalized[k] = v / rms
    sign = np.where(vectors[50] >= 0, 1., -1.)
    return dict(baseline=np.abs(normalized[50]),
                consistency=np.min(np.stack([sign * normalized[k] for k in (25, 50, 100)]), axis=0))

def ranking(score):
    score = finite_vector(score)
    return np.lexsort((np.arange(score.size), -score))

def auc(score, correct):
    """Mann-Whitney AUROC; tied scores get half credit, absent classes -> None."""
    score = finite_vector(score)
    correct = np.asarray(correct)
    if correct.dtype != bool or correct.shape != score.shape:
        raise ValueError('Expected matching correctness vector')
    positive = int(correct.sum()); negative = score.size - positive
    if not positive or not negative:
        return None
    order = np.argsort(score, kind='stable'); sorted_score = score[order]
    starts = np.r_[0, np.flatnonzero(sorted_score[1:] != sorted_score[:-1]) + 1]
    ends = np.r_[starts[1:], score.size]
    rank_sum = sum(float(correct[order[a:b]].sum()) * (a + 1 + b) / 2 for a, b in zip(starts, ends))
    return float((rank_sum - positive * (positive + 1) / 2) / (positive * negative))

def endpoints(scores, prediction, label):
    prediction = np.asarray(prediction).ravel(); label = np.asarray(label).ravel()
    if prediction.shape != label.shape or not np.isin(prediction, [0, 1]).all() or not np.isin(label, [0, 1]).all():
        raise ValueError('Invalid bin labels')
    correct = prediction == label
    risks = {}
    for name in ('baseline', 'consistency'):
        order = ranking(scores[name])
        if order.size != correct.size:
            raise ValueError('Score/label size mismatch')
        risks[name] = {str(c): float(np.mean(~correct[order[:math.ceil(c * correct.size)]]))
                       for c in (.25, .5, .75, 1.)}
    return dict(coordinates=int(correct.size), correct_count=int(correct.sum()), risks=risks,
                baseline_minus_consistency={str(c): risks['baseline'][str(c)] - risks['consistency'][str(c)] for c in (.25, .5, .75, 1.)},
                correctness_auc={name: auc(scores[name], correct) for name in ('baseline', 'consistency')})

def cdf_bins(value):
    """Pinned GS l=1 CDF rule, including its upper-bin clamp; scipy only."""
    from scipy.stats import norm
    v = finite_vector(value)
    bins = np.minimum((norm.cdf(v) * 2).astype(np.int64), 1)
    if not np.array_equal(bins, (v >= 0).astype(np.int64)):
        raise ValueError('CDF/sign quantizer disagreement: stop interpretation')
    return bins
