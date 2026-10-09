"""Agreement measures for the gold-set check (Clarifications 19, 25 and 30).

Krippendorff's alpha, ordinal, for two coders who both answered every unit, levels 1-4:
  1. Coincidence counts: each passage answered (a, b) adds 1 to o[a][b] and 1 to o[b][a].
  2. n_c = how often level c was used, over both coders; n = 2 x passages.
  3. Ordinal distance between levels c and k: (n_c + ... + n_k - (n_c + n_k) / 2) squared. Levels that
     many answers fall between count as further apart.
  4. alpha = 1 - (n - 1) x sum(o_ck x distance) / sum(n_c x n_k x distance).
alpha = 1 is perfect agreement; 0 is what chance alone would give. The 90% interval comes from
resampling passages with replacement (seed and count from Clarification 19).
"""

import numpy as np

LEVELS = (1, 2, 3, 4)


def _distance(n_by_level):
    """Ordinal squared distance between every pair of levels, from how often each level was used."""
    k = len(LEVELS)
    d = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            lo, hi = min(i, j), max(i, j)
            d[i, j] = (n_by_level[lo:hi + 1].sum() - (n_by_level[i] + n_by_level[j]) / 2) ** 2
    return d


def ordinal_alpha(a, b):
    """Krippendorff's ordinal alpha for two coders' levels (lists of 1-4, same passages in the same order)."""
    a, b = np.asarray(a, int), np.asarray(b, int)
    o = np.zeros((4, 4))
    for x, y in zip(a - 1, b - 1):
        o[x, y] += 1
        o[y, x] += 1
    n_by_level = o.sum(axis=1)
    n = n_by_level.sum()
    d = _distance(n_by_level)
    expected = (np.outer(n_by_level, n_by_level) * d).sum()
    if expected == 0:                     # every answer the same level: alpha is undefined
        return float("nan")
    return float(1 - (n - 1) * (o * d).sum() / expected)


def bootstrap_interval(a, b, seed=20260923, resamples=2000, level=0.90):
    """Percentile interval for alpha from resampling passages with replacement."""
    a, b = np.asarray(a, int), np.asarray(b, int)
    rng = np.random.default_rng(seed)
    stats = [ordinal_alpha(a[idx], b[idx]) for idx in (rng.integers(0, len(a), len(a)) for _ in range(resamples))]
    tail = (1 - level) / 2 * 100
    return tuple(float(x) for x in np.nanpercentile(stats, [tail, 100 - tail]))


def exact_agreement(a, b):
    return float(np.mean(np.asarray(a) == np.asarray(b)))


def confusion(a, b):
    """4x4 counts: rows = first coder's level, columns = second coder's level."""
    m = np.zeros((4, 4), int)
    for x, y in zip(a, b):
        m[int(x) - 1, int(y) - 1] += 1
    return m


def summarize(a, b, seed=20260923, resamples=2000):
    """All the measures for one comparison, as a plain dict."""
    if len(a) < 2:
        return {"n": len(a), "alpha": float("nan"), "interval": (float("nan"), float("nan")),
                "exact": exact_agreement(a, b) if a else float("nan"), "confusion": confusion(a, b)}
    return {"n": len(a), "alpha": ordinal_alpha(a, b), "interval": bootstrap_interval(a, b, seed, resamples),
            "exact": exact_agreement(a, b), "confusion": confusion(a, b)}
