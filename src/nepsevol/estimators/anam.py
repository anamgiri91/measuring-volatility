"""Anam's estimator: daily-bar volatility for markets whose opening price cannot be trusted.

THE PROBLEM IT ADDRESSES
------------------------
Every classical daily-bar estimator treats the opening price as an efficient price. Garman-Klass and
Rogers-Satchell anchor the session at the open; Yang-Zhang adds the squared overnight return to an
open-anchored intraday estimate and assumes the two are independent. In the Nepal Stock Exchange the
pooled projection of the close-to-close return on the overnight return has slope b = 0.13-0.36 (M15): by
that statistic, which weights days by the size of their opening move, the session reverses 64-87% of the
overnight move, and under the model of the theory supplement the open carries a large transient error. In
the development sample this makes overnight^2 + Parkinson overstate close-to-close variance by 39%
(regime A1) and 65% (regime B), and the daily form of Yang-Zhang by 48% and 75% (table100); and it
makes every open-anchored estimator a worse forecaster than Parkinson, which reads only the high and
the low (table98). Parkinson in turn ignores overnight variance,
carries an additive floor (bid-ask bounce, tick size, an open that sets an extreme) and collapses
when few trades print a range. Close-to-close variance does not read the open, so an opening error
cannot bias it; it still carries the errors of the close, and it uses one price a day.

THE ESTIMATOR
-------------
For a security with previous close PC and today's bar (O, H, L, C), with o = ln(O/PC),
r = ln(C/PC), h = ln(H/PC), l = ln(L/PC) and range R = ln(H/L):

1. **Open quality** ``b``: the market's unbiasedness coefficient of the open for the close,
   ``b = sum(o r) / sum(o^2)`` over a trailing window, clipped to [0, 1] -- the share of the
   overnight move that the session keeps (M15's central statistic). In a panel it is pooled over all
   securities and the last ``POOL_SESSIONS`` dates; for a single series it is the series' own
   trailing ``SERIES_SESSIONS`` sessions.
2. **Anchor**: ``PC exp(b o)``. Under the theory supplement's Assumption 1, ``b o`` is the best
   through-origin linear predictor of the efficient overnight LOG move given the printed one: a shrinkage
   predictor, not the permanent move itself, and ``PC exp(b o)`` is the anchor price it implies, not a
   predictor of the efficient opening price (audit item A04, 9 October 2026).
3. **Extended range**: the day's range extended to reach the anchor,
   ``R* = R + max(0, b o - h) + max(0, l - b o) = max(h, b o) - min(l, b o)``. With b = 1 the open lies
   inside [L, H], so R* = R (Parkinson's range); with b = 0 the anchor is the previous close and R* is
   Wilder's (1978) true range; R <= R* <= TR in between. The extension moves the anchor, never the
   extremes: an opening print that sets the high or the low stays in R*, and so in the kernel. (An
   earlier version said "an overshooting open cannot inflate it", true only of the extension term with
   the high and low held fixed; audit item A05. Proposition 7 of the theory supplement measures how much
   of the opening error's variance each form absorbs.)
4. **Daily kernel**:
   ``A = (1 - w) [ (b o)^2 + R*^2 / (4 ln 2) ] + w r^2``,  ``w = LAMBDA0 (1 - b)``.
   The shrunk overnight move enters squared; the extended range enters with Parkinson's constant;
   the close-to-close return is blended in in proportion to 1 - b. A >= 0 always. The overnight term
   has expectation b^2 E[o^2], the lower end of the identified set for the efficient overnight second
   moment: under an opening error uncorrelated with the news it carries only the fraction b of that
   moment (theory supplement, Proposition 7(a)). The construction is a heuristic, not an unbiased
   estimator of any component; the calibration below sets its overall level.
5. **Market calibration** ``kappa``: the trailing ratio ``sum(r^2) / sum(A)``, pooled over the
   cross-section in a panel (``POOL_SESSIONS`` dates) or over the series' own history. The window
   estimate is ``sigma^2 = kappa_t * mean(A over the window)`` (the calibration of the window's last
   session applied to the whole window): the LEVEL comes from close-to-close variance, which no
   opening error can bias (closing errors still enter it), and the DYNAMICS from the range.

Special cases: b = 1 gives kappa * (o^2 + Parkinson) -- the overnight-plus-Parkinson estimator of a
market with a clean open. b = 0 gives kappa * (0.8 true-range Parkinson + 0.2 r^2) -- a market whose
open is worthless.

WHY POOLED CALIBRATION
----------------------
The distortions of the range in a frontier market -- the opening overreaction, the closing rule, the
share of overnight variance -- are market-wide and change with market design. Hundreds of securities
trade under the same rules on the same dates, so the cross-section measures the current ratio of
close-to-close to range-based variance quickly and precisely; a security's own history is slow and
noisy. On the development sample, pooled calibration beat per-security calibration in every
forecast comparison (``scripts/39_anam_development.py``).

WHAT IS AND IS NOT CLAIMED
--------------------------
The components have antecedents: Parkinson (1980), Garman & Klass (1980), Yang & Zhang (2000), the
true range of Wilder (1978), and the scaling and weighting of overnight and intraday variance in
Hansen & Lunde (2005). Their combination -- an overnight weight set by the open's measured
unbiasedness, a range extended to the effective open, a close-to-close blend that grows as the open
degrades, and calibration across a market's cross-section -- was not found in a targeted search.
In a perfectly clean, continuous market the estimator reduces to overnight^2 + Parkinson and is less
efficient than open-anchored Garman-Klass; that is the price of not trusting the open, and it is
reported, not hidden.

The constants (LAMBDA0, POOL_SESSIONS, SERIES_SESSIONS) were chosen on the development sample and
frozen in ``M16_ANAM_ESTIMATOR_PLAN.md`` before the estimator was computed on the holdout. The holdout
was not unseen: M15's findings, which informed the design, use the whole NEPSE sample, as the plan
discloses (an earlier version of this docstring said "before any holdout data were read"; audit item
A12, and M-020 for the same wording in the manuscript).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "LN2", "LAMBDA0", "POOL_SESSIONS", "SERIES_SESSIONS", "MIN_POOL_DATES", "MIN_SERIES_SESSIONS",
    "bar_coordinates", "open_quality_panel", "open_quality_series", "extended_range", "kernel",
    "calibration_panel", "calibration_series", "anam_estimator",
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


def anam_estimator(df: pd.DataFrame, window: int = 21, mode: str = "panel", by: str = "symbol",
                   date: str = "date", prev_close: str = "prev_close", lam0: float = LAMBDA0,
                   open_free: bool = False) -> pd.DataFrame:
    """Anam's estimator for every row of a daily-bar frame.

    ``df`` needs open/high/low/close, ``prev_close`` (NaN across gaps) and, in panel mode, ``by`` and
    ``date``. Rows must be sorted by (``by``, ``date``). ``mode="panel"`` pools b and kappa across the
    cross-section; ``mode="series"`` uses each series' own history (the only option for one index).
    Returns columns b, kernel, kappa and ``var`` -- the calibrated variance of the window of
    ``window`` observed sessions ending at the row (daily units; multiply by the market's session
    count to annualise).

    ``open_free=True`` gives the open-free form, b = 0 throughout: 0.8 x true-range Parkinson plus
    0.2 r^2, calibrated the same way. It is the special case the frozen M16 plan reported as a
    variant; M18 tested it as a hypothesis fixed in advance, and of the two forms it is the one the
    frontier-market evidence favours (manuscript Section 6.8; ``ANAM_RECHECK_POSTHOC.md``). The default,
    ``False``, is the estimator frozen in M16. The installable package ``anam-estimator/`` copies this
    arithmetic verbatim (``tests/test_anam_package.py``).
    """
    if mode not in ("panel", "series"):
        raise ValueError(f"mode must be 'panel' or 'series', got {mode!r}")
    co = bar_coordinates(df["open"], df["high"], df["low"], df["close"], df[prev_close])
    grp = df[by] if by in df else pd.Series(0, index=df.index)
    if open_free:
        b = pd.Series(0.0, index=df.index)
    elif mode == "panel":
        b = open_quality_panel(co["o"], co["r"], df[date])
    else:
        b = open_quality_series(co["o"], co["r"], grp)
    A = kernel(co["o"], co["c"], co["u"], co["d"], b, lam0=lam0)
    r2 = co["r"] ** 2
    if mode == "panel":
        kappa = calibration_panel(A, r2, df[date])
    else:
        kappa = calibration_series(A, r2, grp)
    mean_A = A.groupby(grp, sort=False).transform(lambda z: z.rolling(window, min_periods=window).mean())
    return pd.DataFrame({"b": b, "kernel": A, "kappa": kappa, "var": kappa * mean_A}, index=df.index)
