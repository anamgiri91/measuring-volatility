"""Multiway cluster bootstrap for panel statistics.

REFEREE ITEM 14. The previous revision reported bootstrap intervals that resampled SECURITIES
only, and then used them to say that ratios were "statistically distinguishable from one". A
security-clustered interval absorbs serial dependence within a security. It does not absorb
COMMON MARKET-DATE SHOCKS -- and in a frontier cash market those dominate: a policy
announcement, an index-wide move or a settlement change hits every security on the same date at
once. Ignoring that dimension understates the interval, and on this panel it understates it by
roughly a factor of two.

The estimator here is the MULTIWAY (pigeonhole) BOOTSTRAP: draw each cluster dimension with
replacement independently, and weight each observation by the product of its dimensions'
multiplicities.

    Davezies, L., D'Haultfoeuille, X. & Guyonvarch, Y. (2021), "Empirical process results for
    exchangeable arrays", Annals of Statistics 49(2), 845-862.

Two entry points, because the project has two shapes of statistic and both must be exact:

* :func:`ratio_of_sums_ci` -- for ``mean(numerator) / mean(denominator)`` on a common row set.
  A resampled sum over a (security x date) cell matrix is exactly ``c' M e``, so a replicate is
  two matrix-vector products and no re-estimation. Used by ``scripts/26_robustness.py``.
* :func:`weighted_stat_ci` -- for anything else, including statistics involving a VARIANCE,
  which is not a ratio of sums because it centres on a sample mean that itself moves under
  resampling. The caller supplies a function of (values, weights). Used by
  ``scripts/12_benchmark_diagnosis.py``.

Both take an explicit ``seed`` and are bit-reproducible, like every other number in this package.

Reading the intervals. These are percentile intervals on a deviation from an IMPERFECT PROXY,
not from latent variance. An interval excluding 1.000 means the estimator differs detectably
from the matched proxy; it does not mean the estimator is biased, because the proxy is not the
truth. That distinction is the manuscript's own (Section 10) and the intervals must not be used
to smuggle it back.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["DIMS", "MEAN_BLOCK", "row_multiplicities", "ratio_of_sums_ci", "weighted_stat_ci",
           "cell_matrices", "stationary_date_multiplicities", "ratio_of_sums_ci_block"]

#: The two dependence dimensions of this panel. An observation is a security-day.
DIMS = ("security", "date")

#: Expected block length, in sessions, for the stationary bootstrap over calendar dates.
#: See :func:`stationary_date_multiplicities` for why 21 and not a tuned value.
MEAN_BLOCK = 21


def _codes(ids) -> np.ndarray:
    """Contiguous integer codes for an array of cluster labels."""
    return pd.factorize(pd.Series(ids), sort=True)[0]


def row_multiplicities(dim_codes: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    """One bootstrap draw: per-row weight = product of its clusters' multiplicities.

    A dimension omitted from ``dim_codes`` contributes a weight of 1 to every row, which is how
    a one-way cluster bootstrap is obtained from the same code path as the two-way one.
    """
    w = np.ones(len(dim_codes[0]) if dim_codes else 0)
    for codes in dim_codes:
        k = codes.max() + 1
        mult = np.bincount(rng.integers(0, k, size=k), minlength=k).astype(float)
        w = w * mult[codes]
    return w


def cell_matrices(num, den, sec, date):
    """Dense (security x date) numerator and denominator matrices.

    An observation is a security-day, so each cell holds at most one row and the matrices are
    exact rather than aggregated.
    """
    si, di = _codes(sec), _codes(date)
    shape = (si.max() + 1, di.max() + 1)
    N = np.zeros(shape)
    D = np.zeros(shape)
    np.add.at(N, (si, di), np.asarray(num, dtype=float))
    np.add.at(D, (si, di), np.asarray(den, dtype=float))
    return N, D


def ratio_of_sums_ci(num, den, sec, date, dims=DIMS, n_boot=1000, seed=20260901,
                     sqrt=True, alpha=0.05):
    """Percentile CI for ``sqrt(sum(num)/sum(den))`` under multiway clustering.

    ``sqrt=True`` returns the standard-deviation-scale ratio, which is the scale every ratio in
    this package's tables is reported on; pass ``sqrt=False`` for the variance scale. The
    numerator and denominator must already be row-matched -- zeros outside the common mask -- so
    that both sums describe the same observations (referee item 5).
    """
    N, D = cell_matrices(num, den, sec, date)
    n_sec, n_date = N.shape
    if n_sec < 2 or n_date < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    C = (np.ones((n_sec, n_boot)) if "security" not in dims
         else np.stack([np.bincount(rng.integers(0, n_sec, n_sec), minlength=n_sec)
                        for _ in range(n_boot)], axis=1).astype(float))
    E = (np.ones((n_date, n_boot)) if "date" not in dims
         else np.stack([np.bincount(rng.integers(0, n_date, n_date), minlength=n_date)
                        for _ in range(n_boot)], axis=1).astype(float))
    top = (C * (N @ E)).sum(axis=0)
    bot = (C * (D @ E)).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(bot > 0, top / bot, np.nan)
        if sqrt:
            r = np.sqrt(np.where(r >= 0, r, np.nan))
    if np.isfinite(r).sum() < 2:
        return (np.nan, np.nan)
    return (float(np.nanpercentile(r, 100 * alpha / 2)),
            float(np.nanpercentile(r, 100 * (1 - alpha / 2))))


def stationary_date_multiplicities(n_date: int, rng: np.random.Generator,
                                   mean_block: int = MEAN_BLOCK) -> np.ndarray:
    """Multiplicities for one stationary-bootstrap resample of the CALENDAR DATE dimension.

    PEER-REVIEW ITEM G / MANDATORY ITEM 5. Resampling individual dates with replacement --
    which is what :func:`ratio_of_sums_ci` does -- absorbs a shock common to one date, but it
    destroys temporal ordering and therefore cannot absorb dependence BETWEEN ADJACENT dates.
    Volatility clusters: a turbulent week is turbulent for every security on every day of it,
    so a market-wide shock is correlated across neighbouring sessions as well as across
    securities within a session. An i.i.d. date bootstrap treats those adjacent sessions as
    independent draws and understates the interval accordingly.

    The stationary bootstrap of Politis & Romano (1994) fixes exactly that. Blocks of
    CONSECUTIVE sessions are drawn with geometric length (mean ``mean_block``) and wrapped
    circularly until ``n_date`` dates have been drawn, so serial dependence inside a block is
    preserved rather than shuffled away. Random block length is what keeps the resampled series
    stationary; a fixed length does not.

        Politis, D. N. & Romano, J. P. (1994), "The stationary bootstrap",
        Journal of the American Statistical Association 89(428), 1303-1313.

    WHY 21 AND NOT A TUNED VALUE. 21 sessions is the manuscript's own volatility horizon -- the
    Yang-Zhang window and the 21-session series in Section 6.3 -- so it is the interval over
    which this paper already asserts that volatility is persistent. Choosing it by a data-driven
    rule would make the block length a function of the estimate it is used to bracket, and the
    sensitivity of the intervals to it is reported rather than assumed away.

    Returns a float vector of length ``n_date`` summing to ``n_date``, in the same form
    :func:`ratio_of_sums_ci` consumes, so a block resample is a drop-in for an i.i.d. one.
    """
    if n_date < 2:
        return np.ones(n_date, dtype=float)
    p = 1.0 / max(mean_block, 1)
    counts = np.zeros(n_date, dtype=float)
    drawn = 0
    while drawn < n_date:
        start = int(rng.integers(0, n_date))
        length = min(int(rng.geometric(p)), n_date - drawn)
        idx = (start + np.arange(length)) % n_date      # circular wrap: no end-of-sample bias
        np.add.at(counts, idx, 1.0)
        drawn += length
    return counts


def ratio_of_sums_ci_block(num, den, sec, date, n_boot=1000, seed=20260901,
                           mean_block=MEAN_BLOCK, resample_securities=True,
                           sqrt=True, alpha=0.05):
    """Percentile CI combining a STATIONARY block bootstrap over dates with security resampling.

    This is the inference the peer review asks for in mandatory item 5: block resampling over
    calendar dates, "preferably combined with security resampling". Securities are drawn i.i.d.
    with replacement (they have no natural ordering, so blocking them would be meaningless);
    dates are drawn in geometric-length blocks of consecutive sessions.

    BUCKET ASSIGNMENTS ARE FIXED ACROSS REPLICATES, not re-estimated. The liquidity buckets in
    Tables 4 and 6 are formed once on the full sample and carried into every replicate. This is
    a deliberate choice and it is the conservative direction for the claim being made:
    re-estimating quintile breakpoints inside each replicate would add the sampling variability
    of the breakpoints to the interval, but it would also let a bucket's MEMBERSHIP drift toward
    whichever securities happened to be drawn, which changes the estimand from "the ratio in the
    thinnest fifth of this market" to "the ratio in the thinnest fifth of a resampled market".
    The former is what the manuscript claims, so the buckets are held fixed and this choice is
    stated in Section 6.5 rather than left to the reader to infer.

    Dates must be sortable; blocks are formed on the SORTED date order, so the consecutive
    sessions of the panel are the consecutive columns of the cell matrix.
    """
    N, D = cell_matrices(num, den, sec, date)
    n_sec, n_date = N.shape
    if n_sec < 2 or n_date < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    C = (np.stack([np.bincount(rng.integers(0, n_sec, n_sec), minlength=n_sec)
                   for _ in range(n_boot)], axis=1).astype(float)
         if resample_securities else np.ones((n_sec, n_boot)))
    E = np.stack([stationary_date_multiplicities(n_date, rng, mean_block)
                  for _ in range(n_boot)], axis=1)
    top = (C * (N @ E)).sum(axis=0)
    bot = (C * (D @ E)).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(bot > 0, top / bot, np.nan)
        if sqrt:
            r = np.sqrt(np.where(r >= 0, r, np.nan))
    if np.isfinite(r).sum() < 2:
        return (np.nan, np.nan)
    return (float(np.nanpercentile(r, 100 * alpha / 2)),
            float(np.nanpercentile(r, 100 * (1 - alpha / 2))))


def weighted_stat_ci(stat, frame, sec, date, dims=DIMS, n_boot=1000, seed=20260901, alpha=0.05):
    """Percentile CI for an arbitrary weighted statistic under multiway clustering.

    ``stat(frame, w)`` must return a float given the data and a vector of non-negative row
    weights. Use this where the statistic is not a ratio of sums -- in particular where a sample
    VARIANCE appears, since its centring mean moves with the resample and it therefore cannot be
    written as a fixed ratio of sums.
    """
    codes = []
    if "security" in dims:
        codes.append(_codes(sec))
    if "date" in dims:
        codes.append(_codes(date))
    if not codes:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        w = row_multiplicities(codes, rng)
        try:
            draws[b] = stat(frame, w)
        except (ZeroDivisionError, FloatingPointError, ValueError):
            draws[b] = np.nan
    if np.isfinite(draws).sum() < 2:
        return (np.nan, np.nan)
    return (float(np.nanpercentile(draws, 100 * alpha / 2)),
            float(np.nanpercentile(draws, 100 * (1 - alpha / 2))))


def weighted_var(x: np.ndarray, w: np.ndarray) -> float:
    """Frequency-weighted sample variance, matching ``Series.var(ddof=1)`` when w == 1.

    Frequency weights, not reliability weights: a weight of 3 means the observation appears
    three times in the resample, so the effective sample size is ``sum(w)`` and the correction
    is ``sum(w) - 1``.
    """
    sw = w.sum()
    if sw <= 1:
        return np.nan
    mu = float((w * x).sum() / sw)
    return float((w * (x - mu) ** 2).sum() / (sw - 1))
