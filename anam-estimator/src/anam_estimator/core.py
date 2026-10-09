"""The arithmetic of Anam's estimator.

This module is a verbatim copy of the arithmetic in ``src/nepsevol/estimators/anam.py`` of the research
package (the estimator frozen in plan M16 of the paper), so that the installable package and the
code that produced the paper's tables give the same numbers. A test in the research repository
(``tests/test_anam_package.py``) checks that they agree to machine precision.

For a bar (O, H, L, C) with previous close PC, write o = ln(O/PC), r = ln(C/PC), h = ln(H/PC),
l = ln(L/PC) and R = ln(H/L).

1. Open quality ``b = sum(o r) / sum(o^2)`` over a trailing window, clipped to [0, 1]: the share of the
   overnight move that the session keeps, on average. In a panel it is pooled over the cross-section
   and the last ``POOL_SESSIONS`` dates; for one series it uses the series' own last
   ``SERIES_SESSIONS`` sessions.
2. Extended range ``R* = R + max(0, b o - h) + max(0, l - b o)``: the day's range extended to reach the
   effective open ``PC exp(b o)``. With b = 0 it is Wilder's (1978) true range.
3. Daily kernel ``A = (1 - w)[(b o)^2 + R*^2 / (4 ln 2)] + w r^2`` with ``w = LAMBDA0 (1 - b)``.
4. Calibration ``kappa = sum(r^2) / sum(A)`` over the same trailing set, so that ``kappa * mean(A)`` over a
   window is on the close-to-close scale.

With b = 1 the kernel is overnight^2 + Parkinson; with b = 0 (the open-free form) it is
0.8 x true-range Parkinson + 0.2 r^2, which reads only the previous close, the high, the low and the close.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "LN2", "LAMBDA0", "POOL_SESSIONS", "SERIES_SESSIONS", "MIN_POOL_DATES", "MIN_SERIES_SESSIONS",
    "bar_coordinates", "open_quality_panel", "open_quality_series", "extended_range", "kernel",
    "calibration_panel", "calibration_series",
]

LN2 = float(np.log(2.0))
#: weight on r^2 when the open is worthless (b = 0); the blend weight is LAMBDA0 * (1 - b)
LAMBDA0 = 0.2
#: panel mode: trailing dates pooled across the cross-section for b and kappa
POOL_SESSIONS = 60
MIN_POOL_DATES = 20
#: single-series mode: the series' own trailing sessions for b and kappa
SERIES_SESSIONS = 250
MIN_SERIES_SESSIONS = 60


def bar_coordinates(open_, high, low, close, prev_close) -> pd.DataFrame:
    """Log coordinates of a daily bar relative to the previous close and the open.

    ``prev_close`` must already be NaN across a session gap and adjusted for corporate actions.
    Returns o = ln(O/PC), c = ln(C/O), u = ln(H/O), d = ln(L/O), r = o + c, h = o + u, l = o + d.
    """
    O = pd.Series(open_, dtype=float)
    out = pd.DataFrame(index=O.index)
    out["o"] = np.log(O / pd.Series(prev_close, index=O.index, dtype=float))
    out["c"] = np.log(pd.Series(close, index=O.index, dtype=float) / O)
    out["u"] = np.log(pd.Series(high, index=O.index, dtype=float) / O)
    out["d"] = np.log(pd.Series(low, index=O.index, dtype=float) / O)
    out["r"] = out["o"] + out["c"]
    out["h"] = out["o"] + out["u"]
    out["l"] = out["o"] + out["d"]
    return out


def _clip_b(num: pd.Series, den: pd.Series) -> pd.Series:
    """b = num/den clipped to [0, 1]; where the open never moved (den == 0) the open carries no
    information and b = 0."""
    with np.errstate(invalid="ignore", divide="ignore"):
        b = num / den
    b = b.where(den > 0, 0.0)
    return b.clip(0.0, 1.0)


def open_quality_panel(o: pd.Series, r: pd.Series, date: pd.Series, sessions: int = POOL_SESSIONS,
                       min_dates: int = MIN_POOL_DATES) -> pd.Series:
    """Pooled trailing unbiasedness coefficient of the open, by date, mapped back to rows.

    For date t it uses every security's (o, r) on the last ``sessions`` dates up to and including t.
    """
    ok = o.notna() & r.notna()
    num = (o * r).where(ok).groupby(date).sum()
    den = (o * o).where(ok).groupby(date).sum()
    cnt = ok.groupby(date).sum()
    num_r = num.rolling(sessions, min_periods=1).sum()
    den_r = den.rolling(sessions, min_periods=1).sum()
    n_dates = (cnt > 0).astype(float).rolling(sessions, min_periods=1).sum()
    b = _clip_b(num_r, den_r).where(n_dates >= min_dates)
    return date.map(b)


def open_quality_series(o: pd.Series, r: pd.Series, by: pd.Series | None = None,
                        sessions: int = SERIES_SESSIONS, min_sessions: int = MIN_SERIES_SESSIONS) -> pd.Series:
    """Trailing unbiasedness coefficient from a series' own history (rows in time order per ``by``)."""
    by = pd.Series(0, index=o.index) if by is None else by
    ok = o.notna() & r.notna()
    num = (o * r).where(ok, 0.0).groupby(by, sort=False).transform(lambda z: z.rolling(sessions, min_periods=1).sum())
    den = (o * o).where(ok, 0.0).groupby(by, sort=False).transform(lambda z: z.rolling(sessions, min_periods=1).sum())
    n = ok.astype(float).groupby(by, sort=False).transform(lambda z: z.rolling(sessions, min_periods=1).sum())
    return _clip_b(num, den).where(n >= min_sessions)


def extended_range(o: pd.Series, u: pd.Series, d: pd.Series, b: pd.Series) -> pd.Series:
    """R* = ln(H/L) extended to the effective open PC exp(b o)."""
    h, l = o + u, o + d
    ot = b * o
    return (u - d) + np.maximum(0.0, ot - h) + np.maximum(0.0, l - ot)


def kernel(o: pd.Series, c: pd.Series, u: pd.Series, d: pd.Series, b: pd.Series,
           lam0: float = LAMBDA0) -> pd.Series:
    """Daily kernel A = (1 - w)[(b o)^2 + R*^2/(4 ln 2)] + w r^2, w = lam0 (1 - b). Never negative."""
    r = o + c
    Rs = extended_range(o, u, d, b)
    w = lam0 * (1.0 - b)
    return (1.0 - w) * ((b * o) ** 2 + Rs ** 2 / (4.0 * LN2)) + w * r * r


def calibration_panel(A: pd.Series, r2: pd.Series, date: pd.Series, sessions: int = POOL_SESSIONS,
                      min_dates: int = MIN_POOL_DATES) -> pd.Series:
    """kappa_t = sum(r^2)/sum(A) over all securities and the last ``sessions`` dates through t."""
    ok = A.notna() & r2.notna()
    num = r2.where(ok).groupby(date).sum().rolling(sessions, min_periods=1).sum()
    den = A.where(ok).groupby(date).sum().rolling(sessions, min_periods=1).sum()
    n_dates = (ok.groupby(date).sum() > 0).astype(float).rolling(sessions, min_periods=1).sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        k = (num / den).where((den > 0) & (n_dates >= min_dates))
    return date.map(k)


def calibration_series(A: pd.Series, r2: pd.Series, by: pd.Series | None = None,
                       sessions: int = SERIES_SESSIONS, min_sessions: int = MIN_SERIES_SESSIONS) -> pd.Series:
    """kappa_t from the series' own trailing ``sessions`` observations through t."""
    by = pd.Series(0, index=A.index) if by is None else by
    ok = A.notna() & r2.notna()
    roll = lambda s: s.groupby(by, sort=False).transform(lambda z: z.rolling(sessions, min_periods=1).sum())
    num, den, n = roll(r2.where(ok, 0.0)), roll(A.where(ok, 0.0)), roll(ok.astype(float))
    with np.errstate(invalid="ignore", divide="ignore"):
        return (num / den).where((den > 0) & (n >= min_sessions))
