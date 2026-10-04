"""Instrumented calibration of daily volatility measures, without a high-frequency benchmark.

WHY THIS MODULE EXISTS
----------------------
Every comparison elsewhere in this package is a RATIO of means, ``mean(X_k) / mean(X_0)``,
between a daily estimator ``X_k`` and a matched proxy ``X_0`` (the squared open-to-close return),
supplemented by a correlation. Section 10 of the manuscript concedes the weakness: the proxy is
not latent variance, and Patton (2011) shows an imperfect proxy can distort comparisons. Neither
statistic can separate the two distortions a thin market produces:

* a MULTIPLICATIVE distortion -- with few trades the observed high and low are extremes of a
  short sample, so a range estimator responds LESS than one-for-one to latent variance; and
* an ADDITIVE distortion -- bid-ask bounce and transient auction mispricing add a component
  that does not scale with latent variance.

The two push the ratio in opposite directions and can cancel, so a ratio of 1.00 is compatible
with an estimator that moves only 70% as much as true variance. Correlation with a same-day proxy
cannot separate them either, because the estimator and the proxy are computed from the SAME
daily bar and share its sampling error.

THE MEASUREMENT MODEL
---------------------
For security ``i`` and session ``t``, with ``IV_it`` the latent integrated variance of the session,

    X_{k,it} = alpha_{k,i} + beta_k * IV_it + U_{k,it},     E[U_it | IV_it, F_{i,t-1}] = 0,   (M1)

where ``F_{i,t-1}`` is the information available at the close of session ``t-1``. ``alpha`` is the
additive distortion (allowed to differ by security), ``beta`` the multiplicative one. A reference
measure is normalised to ``beta_0 = 1``. Same-day errors ``U_{k,it}`` may be arbitrarily correlated
across ``k`` -- they are, since every ``X_k`` reads one bar -- and arbitrarily heteroskedastic.

IDENTIFICATION THROUGH VOLATILITY PERSISTENCE
---------------------------------------------
Let ``V_it = E[IV_it | F_{i,t-1}]``. Under (M1), ``E[X_{k,it} | F_{i,t-1}] = alpha_{k,i} + beta_k V_it``,
so for ANY F_{t-1}-measurable instrument vector ``Z_{i,t-1}``

    Cov(X_it, Z_{i,t-1}') = beta * Cov(V_it, Z_{i,t-1}'),                                   (P1)

a K x L matrix of RANK ONE whose column space is spanned by ``beta``. The measurement error and
the unpredictable part of variance are martingale differences, so lagged measures are valid
instruments however strongly the same-day errors are correlated. No assumption is made about
how ``V`` evolves -- in particular it need not be a random walk, which the data-based ranking of
Patton (2011, J. Econometrics 161) requires -- and no high-frequency benchmark is used. This is
the classic errors-in-variables remedy of Christensen & Prabhala (1998), applied to estimators
that share one daily bar rather than to implied volatility.

In practice ``beta_k`` is the 2SLS coefficient of ``X_k`` on the reference, instrumented by lagged
measures, within security:

    beta_k = Cov_w(X_k, Vhat) / Cov_w(X_0, Vhat),     Vhat = first-stage fit of X_0 on Z.

THE MEAN RATIO, DECOMPOSED
--------------------------
Exactly, on the variance scale,

    mean(X_k) / mean(X_0) = beta_k + delta_k,
    delta_k = [mean(X_k) - beta_k mean(X_0)] / mean(X_0),                                     (P2)

so the ratio the manuscript reports is the calibration slope PLUS an additive share. A ratio of
one is consistent with ``beta_k < 1`` offset by ``delta_k > 0``.

THE OPTIMAL COMPOSITE
---------------------
Among weights with ``w' beta = 1`` (the composite responds one-for-one to latent variance),
``Var(w'X) = Var(IV) + w' Omega_U w``, so minimising the variance of the composite minimises its
noise. The minimiser

    w* = Sigma_X^{-1} beta / (beta' Sigma_X^{-1} beta)                                       (P3)

needs only the observable covariance ``Sigma_X`` and ``beta`` -- not ``Var(IV)``, not the split of
``IV`` into predictable and transitory parts, and not ``Omega_U`` -- because
``Sigma_X = Var(IV) beta beta' + Omega_U`` and, by Sherman-Morrison, ``Sigma_X^{-1} beta`` is
proportional to ``Omega_U^{-1} beta``. Garman & Klass (1980) derived the best quadratic OHLC
estimator under Brownian motion; (P3) is its empirical counterpart, with weights read from the
data's own volatility persistence instead of from a model of the price path.

Without the constraint ``w'beta = 1`` a minimum-variance combination REWARDS attenuation: an
estimator that ignores volatility altogether has the smallest variance of all. This is why an
efficiency comparison of mean-rescaled estimators is not a noise comparison.

WHAT IS AND IS NOT IDENTIFIED ABOUT NOISE
-----------------------------------------
Write ``n_k = Omega_U[k,k] / beta_k^2`` for estimator k's noise variance on the latent scale.

* ``n_k - n_j = Sigma_X[k,k]/beta_k^2 - Sigma_X[j,j]/beta_j^2`` is identified, so the RANKING of
  estimators by noise is identified.
* ``D_k = Sigma_X[k,k]/beta_k^2 - 1/(beta' Sigma_X^{-1} beta) >= 0`` is k's excess noise over the
  optimal composite, identified.
* The LEVEL of ``n_k`` is not identified, because a purely transitory component of latent variance
  is indistinguishable from measurement error in time-series data. It is bounded:
  ``D_k <= n_k <= UB_k = Sigma_X[k,k]/beta_k^2 - Var(Vhat)``, since
  ``Var(IV) >= Var(V) >= Var(Vhat)``. Hence the composite's efficiency relative to k,
  ``n_k / n_C``, is at least ``UB_k / (UB_k - D_k)``. The bound is conservative by construction.

TESTABLE RESTRICTION
--------------------
(P1) says the lagged cross-covariance matrix has rank one. :func:`rank_one_share` reports the
share of its squared Frobenius norm carried by the first singular value (one under the model),
and :func:`calibrate` reports, per measure, a date-clustered Hansen J statistic for the
overidentifying restrictions. With a hundred thousand stock-days a J test will reject any
specification that is not exactly true, so the share is reported beside it as a magnitude.

WITHIN-SECURITY TRANSFORMATION
------------------------------
``alpha`` may differ by security (spreads and auction behaviour do), so every moment is computed
within security. Demeaning over a security's whole sample makes the demeaned error correlate with
the demeaned instrument at order 1/T; with a median of ~490 sessions per security that is a
fraction of a percent, and the Monte Carlo in ``scripts/35_calibration_simulation.py`` measures it
rather than assumes it.

WEIGHTS
-------
Daily variance measures are heavy-tailed and heteroskedastic, so unweighted moments are dominated
by a handful of turbulent security-days. Callers may pass weights ``omega_it`` that are
F_{t-1}-measurable -- :func:`predictable_scale` builds ``1 / S_{i,t-1}^2`` from a trailing mean of
the reference -- which leaves every moment condition valid, because a predictable weight
multiplies a martingale difference into a martingale difference.

References
    Christensen, B. J. & Prabhala, N. R. (1998). The relation between implied and realized
        volatility. Journal of Financial Economics 50(2), 125-150.
    Garman, M. B. & Klass, M. J. (1980). On the estimation of security price volatilities from
        historical data. Journal of Business 53(1), 67-78.
    Hansen, P. R. & Lunde, A. (2014). Estimating the persistence and the autocorrelation function
        of a time series that is measured with error. Econometric Theory 30(1), 60-93.
    Patton, A. J. (2011). Data-based ranking of realised volatility estimators. Journal of
        Econometrics 161(2), 284-303.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = [
    "LN2", "bar_logs", "quadratic_blocks", "named_measures", "noise_kernel",
    "lagged_means", "predictable_scale", "CalibrationResult", "calibrate",
    "rank_one_share", "optimal_weights", "efficiency_bounds", "decompose_ratio",
    "forward_orthogonal_deviations", "past_demean",
    "bootstrap_calibration", "GK_VWAP_WEIGHTS", "BLOCKS_OHLC", "BLOCKS_OHLCV",
]

LN2 = float(np.log(2.0))

#: Quadratic monomials of the within-session coordinates (u, d, c) -- the space Garman & Klass
#: (1980) searched for their best estimator under Brownian motion.
BLOCKS_OHLC = ("u2", "d2", "c2", "ud", "uc", "dc")
#: The same space extended by the session VWAP coordinate a = ln(VWAP/O).
BLOCKS_OHLCV = BLOCKS_OHLC + ("a2", "ac", "au", "ad")

#: Weights on BLOCKS_OHLCV of the best unbiased quadratic estimator under Brownian motion with
#: volume uniform in time and continuous observation, computed by ``scripts/35`` from 400,000
#: exactly-sampled paths (bridge-sampled extrema, bridge-corrected time integral). Its efficiency
#: relative to the squared open-to-close return is 7.60, against 7.47 for the best quadratic in
#: (u, d, c) alone -- the theoretical value of the VWAP to an OHLC bar is small. It is carried here
#: as a FIXED estimator so that the empirical composite can be compared with the model-optimal one.
GK_VWAP_WEIGHTS = {
    "u2": 1.3223, "d2": 1.3326, "c2": -0.3538, "ud": 0.6521, "uc": -0.6965, "dc": -0.7015,
    "a2": 0.6462, "ac": 1.2544, "au": -1.9027, "ad": -1.9135,
}


# --------------------------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------------------------

def bar_logs(df: pd.DataFrame, prev_close: pd.Series | None = None,
             next_open_col: str | None = None) -> pd.DataFrame:
    """Log coordinates of one daily bar relative to its open.

    ``u = ln(H/O)``, ``d = ln(L/O)``, ``c = ln(C/O)``, ``a = ln(VWAP/O)`` (if a ``vwap`` column is
    present) and, when ``prev_close`` is supplied, the overnight return ``o = ln(O/C_prev)``.
    ``prev_close`` must already be NaN across a session gap -- pass the package's adopted
    previous close (:func:`nepsevol.corporate_actions.adjusted_previous_close`), never a bare
    ``.shift(1)``. The intraday coordinates read one bar only and are unaffected.
    """
    O = df["open"].astype(float)
    out = pd.DataFrame(index=df.index)
    out["u"] = np.log(df["high"] / O)
    out["d"] = np.log(df["low"] / O)
    out["c"] = np.log(df["close"] / O)
    if "vwap" in df.columns:
        out["a"] = np.log(df["vwap"] / O)
    if prev_close is not None:
        out["o"] = np.log(O / prev_close)
    return out


def quadratic_blocks(logs: pd.DataFrame, with_vwap: bool = True) -> pd.DataFrame:
    """The quadratic monomials of (u, d, c[, a]) -- the building blocks of every estimator here.

    Every within-session estimator in the package (open-to-close, Parkinson, Garman-Klass,
    Rogers-Satchell, the VWAP estimators) is a fixed linear combination of these columns, so a
    calibration of the blocks calibrates every estimator built from them.
    """
    u, d, c = logs["u"], logs["d"], logs["c"]
    out = pd.DataFrame({"u2": u * u, "d2": d * d, "c2": c * c,
                        "ud": u * d, "uc": u * c, "dc": d * c}, index=logs.index)
    if with_vwap:
        if "a" not in logs:
            raise ValueError("with_vwap=True needs an 'a' column (a vwap column in the bar)")
        a = logs["a"]
        out["a2"], out["ac"], out["au"], out["ad"] = a * a, a * c, a * u, a * d
    return out


def named_measures(blocks: pd.DataFrame) -> pd.DataFrame:
    """The named daily-variance estimators, written as fixed combinations of the blocks.

    OC   squared open-to-close return, the manuscript's matched proxy (the reference)
    P    Parkinson (1980): (u - d)^2 / (4 ln 2)
    GK   Garman-Klass, simplified: 0.5 (u - d)^2 - (2 ln 2 - 1) c^2
    RS   Rogers-Satchell (1991): u(u - c) + d(d - c)
    AP   average-price estimator, NEW: the best unbiased quadratic in (c, a) under Brownian motion
         with uniform volume, 2c^2 - 6ac + 6a^2 (E[a^2] = s^2/3, E[ac] = s^2/2). It reads the open,
         the close and the session VWAP, and never the extremes.
    GKV  Garman-Klass-VWAP, NEW: the best unbiased quadratic in (u, d, c, a) under the same
         model, weights :data:`GK_VWAP_WEIGHTS`.

    Each of these is unbiased for the session variance under continuously observed driftless
    Brownian motion (and, for AP and GKV, volume uniform in time). Departures from that model are
    what the calibration measures.
    """
    b = blocks
    hl2 = b["u2"] + b["d2"] - 2.0 * b["ud"]
    out = pd.DataFrame(index=b.index)
    out["OC"] = b["c2"]
    out["P"] = hl2 / (4.0 * LN2)
    out["GK"] = 0.5 * hl2 - (2.0 * LN2 - 1.0) * b["c2"]
    out["RS"] = b["u2"] - b["uc"] + b["d2"] - b["dc"]
    if "a2" in b:
        out["AP"] = 2.0 * b["c2"] - 6.0 * b["ac"] + 6.0 * b["a2"]
        out["GKV"] = sum(w * b[k] for k, w in GK_VWAP_WEIGHTS.items())
    return out


def noise_kernel(c: pd.Series, o: pd.Series, o_next: pd.Series) -> pd.Series:
    """Endpoint-noise-robust reference for intraday variance: ``K_t = c_t^2 + o_t c_t + c_t o_{t+1}``.

    If the observed open and close are the efficient price plus transient errors ``e_O``, ``e_C``
    (independent of efficient returns and across days, possibly correlated with each other within
    a day), then ``E[c^2] = IV + V_O + V_C - 2 rho``, ``E[o_t c_t] = rho - V_O`` and
    ``E[c_t o_{t+1}] = rho - V_C``, so ``E[K_t | F_{t-1}] = E[IV_t | F_{t-1}]``: the kernel is
    CONDITIONALLY unbiased, which is what an instrumented calibration needs from its reference.
    It is the daily, alternating-overnight/intraday analogue of the first-order noise correction
    of Zhou (1996) for high-frequency returns.

    Its maintained assumption fails where an opening price band CENSORS the open: the unrealised
    part of the overnight move then continues intraday, ``o`` and ``c`` covary positively for a
    reason that is not noise, and ``K`` is biased upward. It is therefore a robustness reference
    here, not the primary one. ``o_next`` must be NaN where the next session is not consecutive.
    """
    return c * c + o * c + c * o_next


# --------------------------------------------------------------------------------------------
# Instruments and weights
# --------------------------------------------------------------------------------------------

def lagged_means(df: pd.DataFrame, cols, windows=(1, 5, 22), by: str = "symbol",
                 skip: int = 1, min_obs: int | None = None) -> pd.DataFrame:
    """Trailing means of ``cols`` over each security's previous ``w`` OBSERVED sessions.

    ``skip=1`` uses sessions ``t-1, ..., t-w`` -- information available at the close of ``t-1``,
    which is what makes the result a valid instrument for session ``t``. ``skip=2`` lags one more
    session, which is required whenever a measure involves the previous close (see the module
    docstring of ``scripts/34``): yesterday's closing error is then partly known at ``t-1``.
    ``df`` must be sorted by ``[by, date]``. A window is NaN until it is full (``min_obs``
    defaults to the window length), so no instrument is built from a partial history.
    """
    out = {}
    g = df.groupby(by, sort=False)
    for col in cols:
        shifted = g[col].shift(skip)
        gs = shifted.groupby(df[by], sort=False)
        for w in windows:
            mp = w if min_obs is None else min(min_obs, w)
            out[f"{col}_L{skip}m{w}"] = gs.transform(lambda s, w=w, mp=mp: s.rolling(w, min_periods=mp).mean())
    return pd.DataFrame(out, index=df.index)


def predictable_scale(df: pd.DataFrame, col: str, window: int = 22, by: str = "symbol",
                      floor_quantile: float = 0.01) -> pd.Series:
    """Precision weight ``1 / S_{t-1}^2`` from a trailing mean of ``col`` through session ``t-1``.

    F_{t-1}-measurable by construction, so weighting by it leaves every moment condition valid.
    ``S`` is floored at the ``floor_quantile`` of its own distribution so a security-day with an
    implausibly quiet history cannot take an unbounded weight.
    """
    s = df.groupby(by, sort=False)[col].shift(1)
    S = s.groupby(df[by], sort=False).transform(lambda x: x.rolling(window, min_periods=window).mean())
    floor = np.nanquantile(S, floor_quantile)
    S = S.clip(lower=floor)
    return 1.0 / S.pow(2)


# --------------------------------------------------------------------------------------------
# Core estimation
# --------------------------------------------------------------------------------------------

def _group_codes(g) -> np.ndarray:
    return pd.factorize(pd.Series(g), sort=True)[0]


def _within(M: np.ndarray, codes: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted within-group demeaning of every column of ``M``."""
    n_g = codes.max() + 1
    sw = np.bincount(codes, weights=w, minlength=n_g)
    out = np.empty_like(M)
    for j in range(M.shape[1]):
        mu = np.bincount(codes, weights=w * M[:, j], minlength=n_g)
        with np.errstate(invalid="ignore", divide="ignore"):
            mu = np.where(sw > 0, mu / sw, 0.0)
        out[:, j] = M[:, j] - mu[codes]
    return out


def _group_means(M: np.ndarray, codes: np.ndarray, w: np.ndarray) -> np.ndarray:
    n_g = codes.max() + 1
    sw = np.bincount(codes, weights=w, minlength=n_g)
    out = np.empty((n_g, M.shape[1]))
    for j in range(M.shape[1]):
        mu = np.bincount(codes, weights=w * M[:, j], minlength=n_g)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[:, j] = np.where(sw > 0, mu / sw, np.nan)
    return out


def optimal_weights(Sigma: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """``w* = Sigma^{-1} beta / (beta' Sigma^{-1} beta)`` -- (P3) in the module docstring."""
    Si_b = np.linalg.solve(Sigma, beta)
    return Si_b / float(beta @ Si_b)


def efficiency_bounds(Sigma: np.ndarray, beta: np.ndarray, var_vhat: float) -> dict:
    """Identified noise quantities on the latent scale -- see the module docstring.

    Returns per-measure arrays:
        scaled_var   Sigma[k,k] / beta_k^2  (= Var(IV) + n_k)
        excess       D_k = scaled_var_k - 1/(beta' Sigma^{-1} beta), excess noise over the composite
        upper        UB_k = scaled_var_k - Var(Vhat), an upper bound on n_k
        eff_lb       lower bound on the composite's efficiency relative to k, UB_k / (UB_k - D_k)
    and the scalar ``composite_var`` = 1/(beta' Sigma^{-1} beta) = Var(IV) + n_C.
    """
    sv = np.diag(Sigma) / beta ** 2
    comp = 1.0 / float(beta @ np.linalg.solve(Sigma, beta))
    D = sv - comp
    UB = sv - var_vhat
    with np.errstate(invalid="ignore", divide="ignore"):
        eff_lb = np.where(UB - D > 0, UB / (UB - D), np.inf)
    return {"scaled_var": sv, "excess": D, "upper": UB, "eff_lb": eff_lb, "composite_var": comp}


def decompose_ratio(mean_k: float, mean_0: float, beta_k: float) -> tuple[float, float, float]:
    """(P2): mean ratio = slope + additive share, on the variance scale. Returns (ratio, beta, delta)."""
    ratio = mean_k / mean_0
    return ratio, beta_k, ratio - beta_k


def rank_one_share(XZ_cov: np.ndarray) -> float:
    """Share of the squared Frobenius norm carried by the leading singular value.

    ``XZ_cov`` should be the cross-covariance between STANDARDISED measures and STANDARDISED
    instruments, so no single column dominates by its units. Equals one under (P1).
    """
    s = np.linalg.svd(XZ_cov, compute_uv=False)
    return float(s[0] ** 2 / np.sum(s ** 2)) if np.sum(s ** 2) > 0 else np.nan


@dataclass
class CalibrationResult:
    """Point estimates from :func:`calibrate`. Every array is indexed like ``measures``."""
    measures: list
    reference: str
    beta: np.ndarray
    ols_slope: np.ndarray
    mean: np.ndarray
    ratio: np.ndarray
    delta: np.ndarray
    corr_with_ref: np.ndarray
    weights: np.ndarray
    bounds: dict
    var_vhat: float
    first_stage_F: float
    first_stage_R2: float
    rank_one_share: float
    J: np.ndarray = field(default_factory=lambda: np.array([]))
    J_df: int = 0
    n_obs: int = 0
    n_groups: int = 0

    def table(self) -> pd.DataFrame:
        b = self.bounds
        return pd.DataFrame({
            "measure": self.measures,
            "mean_ratio_var": self.ratio,
            "iv_slope": self.beta,
            "additive_share": self.delta,
            "ols_slope": self.ols_slope,
            "corr_with_ref": self.corr_with_ref,
            "composite_weight": self.weights,
            "scaled_var": b["scaled_var"],
            "excess_noise": b["excess"],
            "noise_upper": b["upper"],
            "composite_eff_lb": b["eff_lb"],
            "J": self.J if len(self.J) else np.nan,
        })


def forward_orthogonal_deviations(M: np.ndarray, codes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Forward orthogonal deviations within group (Arellano & Bover, 1995).

    Rows must be in time order within each group. Row ``j`` of a group with ``m`` LATER rows
    becomes ``sqrt(m/(m+1)) * (x_j - mean(x_{j+1}, ..., x_{j+m}))``; the last row of each group has
    no future and is dropped (the returned mask is False there). Unlike demeaning over the whole
    sample, this removes a group's fixed effect using FUTURE rows only, so the transformed error of
    session t is a combination of errors dated t and later and stays orthogonal to every
    instrument dated t-1 or earlier. Whole-sample demeaning would instead put every future
    instrument -- which contains the session-t measure itself -- into the demeaned instrument, and
    bias the slope at order 1/T times the noise-to-signal ratio, which for a daily squared return
    is large (the Monte Carlo of scripts/35 shows it). The sqrt factor keeps homoskedastic,
    serially uncorrelated errors homoskedastic and uncorrelated after the transformation.
    """
    n = len(codes)
    out = np.full_like(M, np.nan, dtype=float)
    keep = np.zeros(n, dtype=bool)
    # group boundaries (codes must be contiguous blocks in time order)
    starts = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ends = np.r_[starts[1:], n]
    for a, b in zip(starts, ends):
        k = b - a
        if k < 2:
            continue
        blk = M[a:b]
        csum = np.cumsum(blk[::-1], axis=0)[::-1]          # csum[j] = sum_{s>=j} x_s
        m = np.arange(k - 1, -1, -1, dtype=float)           # number of later rows
        fut = np.zeros_like(blk)
        fut[:-1] = csum[1:] / m[:-1, None]
        fac = np.sqrt(m / (m + 1.0))[:, None]
        out[a:b - 1] = (fac * (blk - fut))[:-1]
        keep[a:b - 1] = True
    return out, keep


def past_demean(M: np.ndarray, codes: np.ndarray) -> np.ndarray:
    """Subtract each row's expanding within-group mean of ``M`` THROUGH that row.

    Applied to instruments that are already lagged, the result is still F_{t-1}-measurable, so it
    remains a valid instrument; it removes a security's average volatility LEVEL, which carries
    no information about the forward-orthogonal-deviation of the measure and would only add noise
    to the first stage.
    """
    out = np.empty_like(M, dtype=float)
    starts = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ends = np.r_[starts[1:], len(codes)]
    for a, b in zip(starts, ends):
        blk = M[a:b]
        mean = np.cumsum(blk, axis=0) / np.arange(1, b - a + 1)[:, None]
        out[a:b] = blk - mean
    return out


def calibrate(X: np.ndarray, Z: np.ndarray, group, measures, reference: str,
              weights: np.ndarray | None = None, date=None, composite_over=None,
              transform: str = "fod", cluster: str = "two-way",
              compute_J: bool = True, instruments: str = "levels") -> CalibrationResult:
    """Instrumented calibration of K measures against a reference, with security fixed effects.

    Parameters
    ----------
    X : (n, K) measures for session t, one column per name in ``measures``.
    Z : (n, L) instruments, every one F_{t-1}-measurable (lagged).
    group : length-n security labels (the fixed effects).
    reference : the measure normalised to beta = 1 (must be in ``measures``).
    weights : optional F_{t-1}-measurable weights (see :func:`predictable_scale`).
    date : length-n date labels. Required for ``transform="fod"`` (rows are put in time order
        within security) and for the J statistic.
    composite_over : names of the measures to combine in (P3); default all.
    transform : ``"fod"`` (default) removes the fixed effect by forward orthogonal deviations and
        demeans the instruments on their own past, which keeps every moment condition exactly
        valid; ``"within"`` demeans over each security's whole sample, which is biased at order
        1/T and is retained only so that the bias can be measured.
    cluster : ``"two-way"`` (security and date, Cameron-Gelbach-Miller) or ``"date"`` for the
        covariance of the moment conditions in the J statistic.
    compute_J : skip the J statistic (the bootstrap does not need it).
    instruments : under ``"fod"``, use the lagged instruments in ``"levels"`` with a constant
        (default; the standard Arellano-Bover choice for predetermined instruments) or
        ``"past"``-demeaned on each security's own expanding mean. Both are valid. The Monte
        Carlo of scripts/35 found the level form unbiased in the linear model and closer to the
        oracle when the measurement relation is nonlinear, so it is the default.

    Rows with any non-finite entry are dropped; ``n_obs`` reports how many were used. Rows with
    ZERO weight are kept through the transformation -- their measures still enter the forward
    means of earlier rows -- and contribute nothing to the moments. That is what makes a
    bootstrap replicate a re-weighting of fixed moment contributions rather than a different
    transformation of a thinned panel.
    """
    X = np.asarray(X, dtype=float)
    Z = np.asarray(Z, dtype=float)
    measures = list(measures)
    w = np.ones(len(X)) if weights is None else np.asarray(weights, dtype=float)
    ok = np.isfinite(X).all(1) & np.isfinite(Z).all(1) & np.isfinite(w) & (w >= 0)
    g_all = np.asarray(group)
    d_all = None if date is None else np.asarray(date)
    X, Z, w, g = X[ok], Z[ok], w[ok], g_all[ok]
    dts = None if d_all is None else d_all[ok]
    if transform == "fod":
        if dts is None:
            raise ValueError("transform='fod' needs dates to order each security's sessions")
        order = np.lexsort((pd.to_datetime(pd.Series(dts)).to_numpy(), _group_codes(g)))
        X, Z, w, g, dts = X[order], Z[order], w[order], g[order], dts[order]
    codes = _group_codes(g)
    r = measures.index(reference)

    if transform == "fod":
        Xs, keep = forward_orthogonal_deviations(X, codes)
        if instruments == "past":
            Zs = past_demean(Z, codes)
        elif instruments == "levels":
            Zs = Z.copy()
        else:
            raise ValueError(f"instruments must be 'levels' or 'past', got {instruments!r}")
        Xs, Zs, w, codes_k = Xs[keep], Zs[keep], w[keep], codes[keep]
        Xlev = X[keep]
        dts_k = None if dts is None else dts[keep]
        Zs = np.column_stack([np.ones(len(Zs)), Zs])      # constant: E[e*] = 0 is a valid moment
    elif transform == "within":
        Xs = _within(X, codes, w)
        Zs = _within(Z, codes, w)
        Xlev, codes_k, dts_k = X, codes, dts
    else:
        raise ValueError(f"transform must be 'fod' or 'within', got {transform!r}")
    sw = w.sum()
    n, L = Zs.shape

    # first stage: reference on instruments
    ZtWZ = (Zs * w[:, None]).T @ Zs
    pi = np.linalg.solve(ZtWZ, (Zs * w[:, None]).T @ Xs[:, r])
    vhat = Zs @ pi
    resid1 = Xs[:, r] - vhat
    vhat_c = vhat - (w * vhat).sum() / sw
    ss_fit = float((w * vhat_c ** 2).sum())
    ss_res = float((w * resid1 ** 2).sum())
    L_eff = L - 1 if transform == "fod" else L            # the constant is not an excluded instrument
    n_g = codes_k.max() + 1
    dof = max(n - n_g - L, 1)
    F = (ss_fit / L_eff) / (ss_res / dof) if ss_res > 0 else np.inf
    R2 = ss_fit / (ss_fit + ss_res) if (ss_fit + ss_res) > 0 else np.nan

    # second stage: each measure's slope on the fitted reference, relative to the reference's
    cov_kv = (Xs * (w * vhat)[:, None]).sum(0)
    beta = cov_kv / cov_kv[r]

    # covariance of the transformed measures (fixed effects removed)
    mu_s = (Xs * w[:, None]).sum(0) / sw
    Xc = Xs - mu_s
    Sigma = (Xc * w[:, None]).T @ Xc / sw
    var_vhat = float((w * vhat_c ** 2).sum() / sw)

    # naive comparisons, for contrast
    ols = Sigma[:, r] / Sigma[r, r]
    corr = Sigma[:, r] / np.sqrt(np.diag(Sigma) * Sigma[r, r])

    # mean-ratio decomposition, on levels
    mean = (Xlev * w[:, None]).sum(0) / sw
    ratio = mean / mean[r]
    delta = ratio - beta

    sel = list(range(len(measures))) if composite_over is None else [measures.index(m) for m in composite_over]
    wts = np.full(len(measures), np.nan)
    wts[sel] = optimal_weights(Sigma[np.ix_(sel, sel)], beta[sel])
    bounds_sel = efficiency_bounds(Sigma[np.ix_(sel, sel)], beta[sel], var_vhat)
    bounds = {k: np.full(len(measures), np.nan) for k in ("scaled_var", "excess", "upper", "eff_lb")}
    for k in bounds:
        bounds[k][sel] = bounds_sel[k]
    bounds["composite_var"] = bounds_sel["composite_var"]

    # rank-one share of the standardised cross-covariance between measures and instruments
    Zx = Zs[:, 1:] if transform == "fod" else Zs
    Zc = Zx - (Zx * w[:, None]).sum(0) / sw
    sx = np.sqrt(np.diag(Sigma))
    sz = np.sqrt((Zc ** 2 * w[:, None]).sum(0) / sw)
    XZ = (Xc * w[:, None]).T @ Zc / sw
    share = rank_one_share(XZ / np.outer(sx, sz))

    # Hansen J per measure: two-step efficient GMM on g(b) = sum z w (x_k - b x_ref), with the
    # moment covariance clustered by date (common market shocks) and, for "two-way", by security
    # as well (Cameron, Gelbach & Miller, 2011): S = S_date + S_security - S_row.
    J = np.full(len(measures), np.nan)
    if compute_J and dts_k is not None and L_eff > 1:
        dcodes = _group_codes(dts_k)
        n_d = dcodes.max() + 1
        b_vec = (Zs * (w * Xs[:, r])[:, None]).sum(0)
        for k in range(len(measures)):
            if k == r:
                continue
            e = Xs[:, k] - beta[k] * Xs[:, r]
            h = Zs * (w * e)[:, None]
            gd = np.zeros((n_d, L))
            gs = np.zeros((n_g, L))
            for j in range(L):
                gd[:, j] = np.bincount(dcodes, weights=h[:, j], minlength=n_d)
                gs[:, j] = np.bincount(codes_k, weights=h[:, j], minlength=n_g)
            S = gd.T @ gd
            if cluster == "two-way":
                S = S + gs.T @ gs - h.T @ h
            Sinv = np.linalg.pinv(S)
            a_vec = (Zs * (w * Xs[:, k])[:, None]).sum(0)
            b_gmm = float(b_vec @ Sinv @ a_vec) / float(b_vec @ Sinv @ b_vec)
            m_ = a_vec - b_gmm * b_vec
            J[k] = float(m_ @ Sinv @ m_)
    return CalibrationResult(
        measures=measures, reference=reference, beta=beta, ols_slope=ols, mean=mean, ratio=ratio,
        delta=delta, corr_with_ref=corr, weights=wts, bounds=bounds, var_vhat=var_vhat,
        first_stage_F=float(F), first_stage_R2=float(R2), rank_one_share=share, J=J,
        J_df=max(L_eff - 1, 0), n_obs=int((w > 0).sum()), n_groups=int(n_g))


# --------------------------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------------------------

def bootstrap_calibration(X, Z, group, date, measures, reference, weights=None,
                          composite_over=None, n_boot: int = 499, seed: int = 20261004,
                          mean_block: int = 21, resample_groups: bool = True,
                          transform: str = "fod",
                          stats=("beta", "delta", "ratio", "weights", "excess", "eff_lb")) -> dict:
    """Stationary block bootstrap over dates x i.i.d. resampling of securities.

    Each replicate re-estimates EVERYTHING -- first stage, slopes, composite weights and bounds
    -- under row weights equal to (security multiplicity) x (date multiplicity) x (predictable
    weight). Dates are drawn in blocks of consecutive sessions with geometric length (Politis &
    Romano, 1994) so that volatility clustering across adjacent sessions is preserved; securities
    have no natural order and are drawn i.i.d. The fixed-effect transformation is applied to the
    full panel once per replicate with zero-weight rows retained, so a replicate re-weights the
    same moment contributions rather than transforming a thinned panel.

    Returns ``{stat: (n_valid, K) array}``.
    """
    from .inference import stationary_date_multiplicities

    X = np.asarray(X, dtype=float)
    Z = np.asarray(Z, dtype=float)
    w0 = np.ones(len(X)) if weights is None else np.asarray(weights, dtype=float)
    ok = np.isfinite(X).all(1) & np.isfinite(Z).all(1) & np.isfinite(w0) & (w0 > 0)
    X, Z, w0 = X[ok], Z[ok], w0[ok]
    g = np.asarray(group)[ok]
    d = np.asarray(date)[ok]
    dts = pd.to_datetime(pd.Series(d))
    sec_codes = _group_codes(g)
    date_codes = pd.factorize(dts, sort=True)[0]
    n_sec, n_date = sec_codes.max() + 1, date_codes.max() + 1
    rng = np.random.default_rng(seed)
    out = {s_: [] for s_ in stats}
    for _ in range(n_boot):
        ms = (np.bincount(rng.integers(0, n_sec, n_sec), minlength=n_sec).astype(float)
              if resample_groups else np.ones(n_sec))
        md = stationary_date_multiplicities(n_date, rng, mean_block)
        wb = w0 * ms[sec_codes] * md[date_codes]
        try:
            res = calibrate(X, Z, g, measures, reference, weights=wb, date=d,
                            composite_over=composite_over, transform=transform, compute_J=False)
        except np.linalg.LinAlgError:
            continue
        for s_ in stats:
            if s_ in ("excess", "eff_lb"):
                out[s_].append(res.bounds[s_])
            else:
                out[s_].append(getattr(res, s_))
    return {s_: np.asarray(v) for s_, v in out.items()}
