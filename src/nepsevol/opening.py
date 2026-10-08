"""What the opening price measures (M15): unbiasedness, band zones, event windows, Yang-Zhang.

WHY THIS MODULE EXISTS
----------------------
Every within-session estimator in this package -- the open-to-close proxy, Garman-Klass,
Rogers-Satchell, the VWAP estimators -- reads the OPENING price, and Parkinson reads it whenever
the open is the day's high or low. If the open carries a transient error, an estimator and its
benchmark can agree with each other because they share that error. The close-to-close return
does not read the open at all. This module holds the statistics M15 uses to ask how well the
open anticipates the close under each of NEPSE's opening rules
(``M15_OPENING_PRICE_ANALYSIS_PLAN.md``), so that the analysis script and the simulation tests
run one code path.

THE MODEL AND THE UNBIASEDNESS COEFFICIENT
------------------------------------------
Logs throughout. With previous close PC, open O, close C, write ``o = ln(O/PC)`` (overnight),
``c = ln(C/O)`` (intraday) and ``r = o + c = ln(C/PC)`` (close to close). If the observed open
and close are efficient prices plus transient errors ``eta`` and ``eps``, independent of
efficient returns and across days, the open's error cancels from ``r`` and

    b = E[o r] / E[o^2] = 1 + E[o c] / E[o^2],     E[o c] = -Var(eta),

so ``1 - b = Var(eta) / E[o^2]``: **b < 1 when the open overreacts**. A band that CENSORS the
open breaks the model in the other direction: the unrealised part of the overnight move is traded
through during the session, ``o`` and ``c`` share a sign, and **b > 1**. ``b`` is the
unbiasedness coefficient of the price-discovery literature (Biais, Hillion & Spatt, 1999;
Barclay & Hendershott, 2003), here estimated without intercept as a ratio of sums: daily mean
returns are negligible against daily variances, and the opening band bounds ``o``, so no single
observation dominates. A stale open (``O = PC``, ``o = 0``) adds nothing to either sum, so ``b``
is invariant to how many opens fail to match.

THE YANG-ZHANG IDENTITY
-----------------------
Within any window of n sessions, with sample moments (ddof = 1) and k = 0.34/(1.34 + (n+1)/(n-1)),

    YZ - Var(r) = (1 - k) [mean(RS) - Var(c)] - 2 Cov(o, c),

exactly, because Var(r) = Var(o) + Var(c) + 2 Cov(o, c) and YZ = Var(o) + k Var(c) +
(1 - k) mean(RS). Yang and Zhang (2000) assume the overnight and intraday returns independent;
the covariance term is what that assumption discards, and under a transient opening error it is
``+2 Var(eta)`` -- the open's error counted once in each half of the day.

References
    Barclay, M. J. & Hendershott, T. (2003). Price discovery and trading after hours. Review of
        Financial Studies 16(4), 1041-1073.
    Biais, B., Hillion, P. & Spatt, C. (1999). Price discovery and learning during the preopening
        period in the Paris Bourse. Journal of Political Economy 107(6), 1218-1248.
    Yang, D. & Zhang, Q. (2000). Drift-independent volatility estimation based on high, low,
        open, and close prices. Journal of Business 73(3), 477-492.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "BAND_REFORM", "WEEK_REFORM", "OLD_BAND", "NEW_BAND", "PIN_TOL", "ZONES",
    "band_in_force", "opening_coordinates", "zone_labels", "ratio_of_sums", "unbiasedness",
    "event_windows", "placebo_windows", "intensity_groups", "yang_zhang_components",
    "yz_k",
]

#: NEPSE widened the pre-open band from +/-2% to +/-5% effective this session, in a package that
#: also widened the daily limit (+/-10% to +/-15%) and the continuous-session order band (+/-2% to
#: +/-3% of the prevailing price), raised the circuit-breaker thresholds and allowed pre-session
#: order queuing (AUDIT-REGISTER M-013); see nepsevol.clean.limits.REGIMES.
BAND_REFORM = pd.Timestamp("2026-04-20")
#: The trading week moved to Monday-Friday effective this date (nepsevol.trading_calendar).
WEEK_REFORM = pd.Timestamp("2026-04-06")
OLD_BAND = 0.02
NEW_BAND = 0.05
#: An open is "pinned" when its SIMPLE return lies within this distance of the band. Simple
#: returns, not logs: a -5% move is -0.0513 in logs, beyond ln(1.05) = 0.0488 in absolute value.
PIN_TOL = 0.001
ZONES = ("stale", "interior", "old-band zone", "pinned")


def band_in_force(dates) -> np.ndarray:
    """The pre-open band applying on each date: 0.02 before :data:`BAND_REFORM`, 0.05 from it."""
    d = pd.to_datetime(pd.Series(dates)).to_numpy()
    return np.where(d >= BAND_REFORM.to_datetime64(), NEW_BAND, OLD_BAND)


def opening_coordinates(df: pd.DataFrame, prev_close: pd.Series) -> pd.DataFrame:
    """``o``, ``c``, ``r``, the simple opening return ``g`` and, with a vwap column, ``a`` and ``q``.

    ``a = ln(VWAP/O)`` and ``q = ln(C/VWAP) = c - a`` split the session at its volume-weighted
    centre: an opening error undone early in the session shows up in ``E[o a]``, one undone late
    in ``E[o q]``. ``prev_close`` must be NaN across a session gap (pass the package's adopted
    previous close), never a bare ``.shift(1)``.
    """
    O = df["open"].astype(float)
    out = pd.DataFrame(index=df.index)
    out["o"] = np.log(O / prev_close)
    out["c"] = np.log(df["close"] / O)
    out["r"] = out["o"] + out["c"]
    out["g"] = O / prev_close - 1.0
    if "vwap" in df.columns:
        out["a"] = np.log(df["vwap"] / O)
        out["q"] = out["c"] - out["a"]
    return out


def zone_labels(g, band) -> np.ndarray:
    """Classify each open by where its simple return ``g`` sits relative to the band in force.

    ``stale``          g == 0 (the open equals the previous close)
    ``pinned``         |g| >= band - PIN_TOL
    ``old-band zone``  OLD_BAND - PIN_TOL <= |g| < band - PIN_TOL (possible only under the wider
                       band: the opens the old band would have pinned)
    ``interior``       0 < |g| < OLD_BAND - PIN_TOL
    Rows with an undefined ``g`` get an empty label.
    """
    g = np.asarray(g, dtype=float)
    band = np.broadcast_to(np.asarray(band, dtype=float), g.shape)
    ag = np.abs(g)
    out = np.full(g.shape, "", dtype=object)
    ok = np.isfinite(g)
    out[ok & (g == 0)] = "stale"
    pinned = ok & (ag >= band - PIN_TOL)
    zone = ok & ~pinned & (ag >= OLD_BAND - PIN_TOL)
    interior = ok & (g != 0) & (ag < OLD_BAND - PIN_TOL)
    out[interior] = "interior"
    out[zone] = "old-band zone"
    out[pinned] = "pinned"
    return out


def ratio_of_sums(num, den, w=None, mask=None) -> float:
    """``sum(w num) / sum(w den)`` over rows where both are finite (and ``mask`` holds)."""
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    w = np.ones(len(num)) if w is None else np.asarray(w, dtype=float)
    ok = np.isfinite(num) & np.isfinite(den) & np.isfinite(w)
    if mask is not None:
        ok &= np.asarray(mask, dtype=bool)
    d = float((w[ok] * den[ok]).sum())
    return float((w[ok] * num[ok]).sum()) / d if d != 0 else np.nan


def unbiasedness(o, r, w=None, mask=None) -> float:
    """The unbiasedness coefficient ``b = sum(w o r) / sum(w o^2)`` -- see the module docstring."""
    o = np.asarray(o, dtype=float)
    r = np.asarray(r, dtype=float)
    return ratio_of_sums(o * r, o * o, w, mask)


def event_windows(calendar, post_start=BAND_REFORM, pre_end_before=WEEK_REFORM,
                  length: int = 40) -> dict:
    """The H7 windows on a sorted session calendar.

    ``post``: the first ``length`` sessions on or after ``post_start``; ``pre``: the last
    ``length`` sessions strictly before ``pre_end_before``; ``gap``: every session in between,
    which belongs to neither window.
    """
    cal = pd.DatetimeIndex(pd.to_datetime(pd.Series(calendar)).sort_values().unique())
    post = cal[cal >= pd.Timestamp(post_start)][:length]
    before = cal[cal < pd.Timestamp(pre_end_before)]
    pre = before[-length:]
    gap = cal[(cal >= pd.Timestamp(pre_end_before)) & (cal < pd.Timestamp(post_start))]
    if len(post) < length or len(pre) < length:
        raise ValueError("calendar too short for the requested windows")
    return {"pre": pre, "gap": gap, "post": post}


def placebo_windows(calendar, length: int = 40, gap: int = 9, step: int = 5) -> list:
    """Every placebo split of a sorted calendar: ``length``-session windows ``gap`` sessions apart.

    Positions ``s = length + gap, length + gap + step, ...`` while ``s + length`` fits; the post
    window is ``cal[s : s + length]`` and the pre window ``cal[s - gap - length : s - gap]``.
    Returns ``[(cal[s], pre, post), ...]``.
    """
    cal = pd.DatetimeIndex(pd.to_datetime(pd.Series(calendar)).sort_values().unique())
    out = []
    s = length + gap
    while s + length <= len(cal):
        out.append((cal[s], cal[s - gap - length:s - gap], cal[s:s + length]))
        s += step
    return out


def intensity_groups(share: pd.Series, n_groups: int = 3, prefix: str = "T") -> pd.Series:
    """Rank-based equal-count groups of a per-security treatment intensity (T1 = lowest).

    Ranked with ``method="first"`` before cutting, so ties at a boundary cannot leave groups of
    unequal size -- the same convention as the manuscript's security-level liquidity quintiles.
    """
    q = pd.qcut(share.rank(method="first"), n_groups,
                labels=[f"{prefix}{i}" for i in range(1, n_groups + 1)])
    return q.astype(str)


def yz_k(window: int) -> float:
    """Yang and Zhang's weight on the open-to-close variance for an ``window``-session window."""
    n = window
    return 0.34 / (1.34 + (n + 1) / (n - 1))


def yang_zhang_components(o: pd.Series, c: pd.Series, rs: pd.Series, window: int = 21) -> pd.DataFrame:
    """Rolling Yang-Zhang, the matched close-to-close variance and the two terms of their gap.

    For ONE security's rows in time order. Returns columns ``yz``, ``var_r``, ``rs_term`` =
    (1 - k)(mean RS - Var c) and ``cov_term`` = -2 Cov(o, c), with ``yz - var_r ==
    rs_term + cov_term`` up to floating point (the identity in the module docstring). A window
    containing any undefined ``o`` is undefined, as in :func:`nepsevol.estimators.range_.yang_zhang`.
    """
    n = window
    k = yz_k(n)
    var_o = o.rolling(n).var(ddof=1)
    var_c = c.rolling(n).var(ddof=1)
    mean_rs = rs.rolling(n).mean()
    out = pd.DataFrame(index=o.index)
    out["yz"] = var_o + k * var_c + (1.0 - k) * mean_rs
    out["var_r"] = (o + c).rolling(n).var(ddof=1)
    out["rs_term"] = (1.0 - k) * (mean_rs - var_c)
    out["cov_term"] = -2.0 * o.rolling(n).cov(c, ddof=1)
    return out
