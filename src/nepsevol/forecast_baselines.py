"""Forecast models for the corrected evaluation of plan M20: return-only baselines, range variants, ablations.

The 9 October 2026 audit (item A12) observed that "no classical range estimator has significantly lower
loss" is a weak claim when every comparator is a daily kernel inside the same calibration-and-shrinkage
forecast. M20 therefore adds forecasts that use only returns, and variants that switch off one ingredient
of Anam's estimator at a time. Everything here is causal: a forecast made at the close of session t uses
bars through t and nothing later.

RETURN-ONLY BASELINES (calendar time)
-------------------------------------
Run on a (session x security) matrix of close-to-close returns, so a session on which a security did not
trade advances the recursion with its expected value rather than being skipped:

* EWMA (RiskMetrics): ``s_{t+1} = lam s_t + (1 - lam) r_t^2``.
* GARCH(1,1) and GJR-GARCH(1,1) with VARIANCE TARGETING on a moving level:
  ``s_{t+1} = (1 - p) v_t + alpha r_t^2 + gamma r_t^2 1{r_t < 0} + beta s_t``, ``p = alpha + beta + gamma/2``,
  where ``v_t`` is the security's trailing mean of r^2 (250 observed sessions, at least 60) -- the same
  long-run level the kernel forecasts shrink toward, so no parameter is estimated on future data. The
  parameters are common to all securities and chosen on the training span, which is stable where many
  securities have short or irregular histories. The h-session forecast is the mean of the next h
  conditional variances, ``v + (s_{t+1} - v)(1 - p^h) / (h (1 - p))``.
* HAR in convex form: ``f = c1 X_t + c2 mean_5(X) + c3 mean_22(X) + c4 longrun(X)`` with ``c >= 0``,
  ``sum c = 1`` and ``c4 >= 0.1``, so the forecast is positive; applied to r^2 it is a return-only model,
  applied to a kernel (times its calibration) it isolates the forecasting dynamics from the measurement.

RANGE VARIANTS
--------------
* ``tr_parkinson``: Wilder's true range in Parkinson's form, ``TR^2 / (4 ln 2)``, without the r^2 blend of
  the open-free form (which is ``0.8 tr_parkinson + 0.2 r^2``).
* ``posterior_kernel``: Anam's full kernel with the overnight term replaced by its linear posterior second
  moment ``b^2 o^2 + b (1 - b) m2``, ``m2`` the security's trailing mean of o^2. Under uncorrelated opening
  error and efficient overnight move ``E[(b o)^2] = b E[o*^2]``: the frozen kernel's overnight term
  understates the efficient overnight second moment by the factor b (audit item A04; theory supplement,
  Proposition 7). The posterior moment is unbiased for it under that condition. EXPLORATORY: derived after
  the audit, never tested out of sample.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from nepsevol.estimators import anam as AN

__all__ = ["LONGRUN_SESSIONS", "LONGRUN_MIN", "rolling_rows", "pooled_kappa", "series_kappa", "constant_kappa",
           "to_matrix", "from_matrix", "ewma_path", "garch_path", "h_step_mean", "har_components", "simplex_grid",
           "tr_parkinson", "posterior_kernel", "EWMA_GRID", "GARCH_GRID", "GJR_GRID"]

LONGRUN_SESSIONS = 250
LONGRUN_MIN = 60
LN2 = float(np.log(2.0))

#: decay factors tried for EWMA
EWMA_GRID = (0.80, 0.85, 0.90, 0.94, 0.96, 0.97, 0.98, 0.99)
_PERSIST = (0.80, 0.85, 0.90, 0.93, 0.95, 0.97, 0.98, 0.99)
#: (alpha, beta, gamma) tried for GARCH(1,1): alpha on a grid, persistence p = alpha + beta on a grid
GARCH_GRID = tuple((a, round(p - a, 10), 0.0) for a in (0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20)
                   for p in _PERSIST if p - a >= 0)
#: (alpha, beta, gamma) tried for GJR-GARCH(1,1): p = alpha + beta + gamma / 2
GJR_GRID = tuple((a, round(p - a - g / 2, 10), g) for a in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
                 for g in (0.04, 0.08, 0.12, 0.16, 0.20) for p in _PERSIST if p - a - g / 2 >= 0)


def rolling_rows(x: pd.Series, by: pd.Series, n: int, minp: int | None = None) -> pd.Series:
    """Mean of each security's last ``n`` observed rows through the current one (NaN rows are skipped
    by the count of ``minp``)."""
    mp = n if minp is None else minp
    return x.groupby(by, sort=False).transform(lambda z: z.rolling(n, min_periods=mp).mean())


def pooled_kappa(X: pd.Series, r2: pd.Series, date: pd.Series, L: int = 60, minp: int = 20) -> pd.Series:
    """The frozen pooled calibration: sum r^2 / sum X over all securities and the last L dates through t,
    on rows where both are observed (``nepsevol.volforecast``)."""
    valid = X.notna() & r2.notna()
    num = r2.where(valid).groupby(date).sum()
    den = X.where(valid).groupby(date).sum()
    k = num.rolling(L, min_periods=minp).sum() / den.rolling(L, min_periods=minp).sum()
    return date.map(k)


def series_kappa(X: pd.Series, r2: pd.Series, by: pd.Series, L: int = 250, minp: int = 60) -> pd.Series:
    """Each security's own calibration: sum r^2 / sum X over its last L observed rows."""
    valid = X.notna() & r2.notna()
    roll = lambda s: s.groupby(by, sort=False).transform(lambda z: z.rolling(L, min_periods=minp).sum())
    return roll(r2.where(valid)) / roll(X.where(valid))


def constant_kappa(X: pd.Series, r2: pd.Series, rows: pd.Series) -> float:
    """One calibration for the whole test span: sum r^2 / sum X over the (training) ``rows``."""
    ok = rows & X.notna() & r2.notna()
    return float(r2[ok].sum() / X[ok].sum())


def to_matrix(values: pd.Series, sec_code: np.ndarray, session: np.ndarray, n_sessions: int, n_sec: int,
              ffill: bool = False) -> np.ndarray:
    """A (session x security) matrix of a row-aligned series, NaN where a security has no row; with
    ``ffill`` each column carries its last value forward over sessions without a row."""
    M = np.full((n_sessions, n_sec), np.nan)
    M[session, sec_code] = np.asarray(values, dtype=float)
    if ffill:
        M = pd.DataFrame(M).ffill().to_numpy()
    return M


def from_matrix(M: np.ndarray, sec_code: np.ndarray, session: np.ndarray) -> np.ndarray:
    return M[session, sec_code]


def ewma_path(r: np.ndarray, vbar: np.ndarray, lam: float) -> np.ndarray:
    """``s[t]`` = the EWMA forecast of r^2 for session t+1 made at the close of t, started at the
    long-run level ``vbar`` on the first session where it is defined. A session without a return leaves
    the forecast unchanged."""
    T, N = r.shape
    out = np.full((T, N), np.nan)
    prev = np.full(N, np.nan)
    for t in range(T):
        vb, rt = vbar[t], r[t]
        started = np.isfinite(prev)
        upd = np.where(np.isfinite(rt), lam * prev + (1.0 - lam) * rt * rt, prev)
        cur = np.where(started, upd, np.where(np.isfinite(vb), vb, np.nan))
        out[t] = cur
        prev = cur
    return out


def garch_path(r: np.ndarray, vbar: np.ndarray, alpha: float, beta: float, gamma: float = 0.0) -> np.ndarray:
    """``s[t]`` = the variance-targeted GJR-GARCH(1,1) forecast of r^2 for session t+1 made at the close of
    t (GARCH when ``gamma`` = 0). Started at ``vbar``; a session without a return replaces the shock by its
    expectation, so the forecast decays toward the moving level ``vbar``."""
    p = alpha + beta + gamma / 2.0
    if not (alpha >= 0 and beta >= 0 and gamma >= 0 and p < 1):
        raise ValueError("need alpha, beta, gamma >= 0 and alpha + beta + gamma/2 < 1")
    T, N = r.shape
    out = np.full((T, N), np.nan)
    prev = np.full(N, np.nan)
    for t in range(T):
        vb, rt = vbar[t], r[t]
        started = np.isfinite(prev) & np.isfinite(vb)
        r2 = rt * rt
        shock = np.where(np.isfinite(rt), alpha * r2 + gamma * r2 * (rt < 0), (alpha + gamma / 2.0) * prev)
        upd = (1.0 - p) * vb + shock + beta * prev
        cur = np.where(started, upd, np.where(np.isfinite(vb) & ~np.isfinite(prev), vb, prev))
        out[t] = cur
        prev = cur
    return out


def h_step_mean(s1: np.ndarray, vbar: np.ndarray, p: float, h: int) -> np.ndarray:
    """Mean of the next h conditional variances of a variance-targeted GARCH with persistence p."""
    w = 1.0 if p == 0 else (1.0 - p ** h) / (h * (1.0 - p))
    return vbar + (s1 - vbar) * w


def har_components(X: pd.Series, by: pd.Series) -> pd.DataFrame:
    """The four HAR components of a daily series: the day, the last 5 and 22 observed rows, and the
    long-run mean (250 rows, at least 60)."""
    return pd.DataFrame({"d1": X, "m5": rolling_rows(X, by, 5), "m22": rolling_rows(X, by, 22),
                         "lr": rolling_rows(X, by, LONGRUN_SESSIONS, LONGRUN_MIN)}, index=X.index)


def simplex_grid(step: float = 0.1, min_last: float = 0.1) -> list[tuple[float, float, float, float]]:
    """Convex weights (c1, c2, c3, c4) on a grid of ``step`` with the last weight at least ``min_last``."""
    k = int(round(1 / step))
    out = []
    for a, b, c in itertools.product(range(k + 1), repeat=3):
        d = k - a - b - c
        if d >= round(min_last / step):
            out.append(tuple(round(v * step, 10) for v in (a, b, c, d)))
    return out


def tr_parkinson(o: pd.Series, u: pd.Series, d: pd.Series) -> pd.Series:
    """Wilder's true range in Parkinson's form: R*(b = 0)^2 / (4 ln 2)."""
    TR = AN.extended_range(o, u, d, pd.Series(0.0, index=o.index))
    return TR ** 2 / (4 * LN2)


def posterior_kernel(o: pd.Series, c: pd.Series, u: pd.Series, d: pd.Series, b: pd.Series, m2: pd.Series,
                     lam0: float = AN.LAMBDA0) -> pd.Series:
    """Anam's kernel with the overnight term ``(b o)^2`` replaced by ``b^2 o^2 + b (1 - b) m2``."""
    r = o + c
    Rs = AN.extended_range(o, u, d, b)
    w = lam0 * (1.0 - b)
    return (1.0 - w) * (b * b * o * o + b * (1.0 - b) * m2 + Rs ** 2 / (4.0 * LN2)) + w * r * r
