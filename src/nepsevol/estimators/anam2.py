"""Anam II: the market-implied open, and a factor HAR forecast of it.

WHY A SECOND GENERATION
-----------------------
Anam's estimator (``nepsevol.estimators.anam``) reads the overnight move through one coefficient b, the share of
the move the session keeps. The corrected evaluation (plan M20) found that reading the open through b never beat
ignoring it (the open-free form). The development record (``ANAM2_DEVELOPMENT.md``) shows why. Split each
overnight return into the market's move, the cross-sectional mean, and the stock's own remainder:

* the session keeps the market part almost entirely (b_M between 0.64 and 1.00 in the five frontier panels);
* it reverses most of the stock-specific part (b_I between 0.20 and 0.70);
* the market part is only 6-21% of the overnight second moment, so b is close to b_I.

One coefficient therefore shrinks the reliable component by the unreliable one's factor. The market's move can be
measured without the stock's own opening error, from the other stocks' opens.

THE ESTIMATOR
-------------
For security i on date t, with previous close PC and bar (O, H, L, C), write o = ln(O/PC), c = ln(C/O),
u = ln(H/O), d = ln(L/O), r = o + c, h = o + u, l = o + d.

1. **The market's overnight move** ``m_{-i,t}``: the equal-weighted mean of o over the panel's other securities
   on the date (leave-one-out, so it carries none of security i's own opening error); 0 where no other security
   has a bar.
2. **The effective open** ``o*``: ``m_{-i,t}`` where security i's open printed exactly at the previous close
   (O = PC, a stale open, which says nothing about the overnight move); 0 everywhere else. A single series has
   no cross-section and o* = 0 throughout.
3. **The daily kernel**
   ``A = (1 - w) [ o*^2 + R*^2 / D ] + w r^2``,  ``R* = max(h, o*) - min(l, o*)``,  ``w = LAMBDA0 = 0.2``,
   with ``D = 4 ln 2`` (Parkinson) except ``D = 1`` on a one-price bar (H = L). The one-price divisor:
   the "range" of a bar with one price, measured from the anchor, is a single increment. Its expected square
   is the variance itself, not 4 ln 2 times it; the 4 ln 2 of a continuously observed range is the limit of
   n observations as n grows (theory supplement, Proposition 8).

   Where the open moved (o != 0) this is Anam's open-free kernel, ``0.8 TR^2 / D + 0.2 r^2``.
4. **The calibration** ``kappa``: ``sum r^2 / sum A``, pooled over the cross-section and the last
   ``POOL_SESSIONS`` dates (at least ``MIN_POOL_DATES``); a single series uses its own last ``SERIES_SESSIONS``
   sessions (at least ``MIN_SERIES_SESSIONS``). As in Anam I.
5. **The forecast** of the mean squared close-to-close return over the next h sessions:
   ``f = kappa * sum_k c_k Z_k``, with convex weights (``c_k >= 0``, ``sum c_k = 1``, the last at least
   ``FLOOR``) fitted by minimising QLIKE on the training origins. The components Z, all built from the
   kernel's own rows (a row counts where the kernel and r^2 are both observed):
   * ``d1`` (the day), ``m5`` and ``m22`` (means of the last 5 and 22 rows);
   * ``lr * M5`` and ``lr * M22``, where ``M5`` and ``M22`` are the cross-sectional medians of ``m5 / lr`` and
     ``m22 / lr`` on the date: the stock's long-run level scaled by the market's current state (panels only);
   * ``lrCC / kappa``, the stock's own long-run mean of r^2 (so ``kappa * Z`` is that mean itself);
   * ``lr``, the long-run mean of the kernel (``LONGRUN_SESSIONS`` rows, at least ``LONGRUN_MIN``).

WHAT IS AND IS NOT CLAIMED
--------------------------
The factor terms follow the common-component HAR models of Bollerslev, Hood, Huss and Pedersen (2018) and are
not claimed as new. Reading the market's overnight move from the cross-section, in place of a stale opening
print, is the measurement idea this module adds. Every constant was fixed on training spans
(``ANAM2_DEVELOPMENT.md``) before plan M22 was frozen; that plan tests it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nepsevol import forecast_baselines as FB
from nepsevol.estimators import anam as AN

__all__ = ["EPS", "LAMBDA0", "FLOOR", "market_move", "effective_open", "kernel", "calibration", "components",
           "fit_weights", "Forecaster"]

LN2 = float(np.log(2.0))
#: a log price difference below this is zero (an open printed at the previous close; a bar with one price)
EPS = 1e-12
#: the weight of r^2 in the kernel (Anam I's lambda_0; the open-free form's blend)
LAMBDA0 = 0.2
#: the least weight on the long-run level, so every forecast is positive
FLOOR = 0.05


def market_move(o: pd.Series, date: pd.Series) -> pd.Series:
    """The leave-one-out equal-weighted mean of ``o`` over the other securities on the same date (0 where there
    is no other security with an observed ``o``)."""
    s = o.groupby(date).transform("sum")
    n = o.notna().groupby(date).transform("sum")
    own = o.notna().astype(float)
    m = (s - o.fillna(0.0)) / (n - own)
    return m.where((n - own) > 0).fillna(0.0)


def effective_open(o: pd.Series, date: pd.Series, mode: str) -> pd.Series:
    """o*: the market's move where the open printed at the previous close, 0 elsewhere (and 0 for a series)."""
    if mode != "panel":
        return pd.Series(0.0, index=o.index)
    stale = o.abs() < EPS
    return market_move(o, date).where(stale, 0.0)


def kernel(o: pd.Series, c: pd.Series, u: pd.Series, d: pd.Series, ostar: pd.Series,
           w: float = LAMBDA0) -> pd.Series:
    """``(1 - w) [o*^2 + R*^2 / D] + w r^2`` with ``R* = max(h, o*) - min(l, o*)`` and ``D = 4 ln 2``, or 1 on a
    one-price bar."""
    r = o + c
    h = o + u
    l = o + d
    R = np.maximum(h, ostar) - np.minimum(l, ostar)
    D = pd.Series(4.0 * LN2, index=o.index).where(~((u - d).abs() < EPS), 1.0)
    return (1.0 - w) * (ostar * ostar + R * R / D) + w * r * r


def calibration(A: pd.Series, r2: pd.Series, date: pd.Series, symbol: pd.Series, mode: str) -> pd.Series:
    """kappa: the pooled trailing ratio sum r^2 / sum A (panel), or the security's own (series)."""
    Ac, rc = FB.clean_square(A), FB.clean_square(r2)
    v = Ac.notna() & rc.notna()
    if mode == "panel":
        return FB.pooled_kappa(Ac.where(v), rc, date, AN.POOL_SESSIONS, AN.MIN_POOL_DATES)
    return FB.series_kappa(Ac.where(v), rc, symbol, AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)


def _market_state(ratio: pd.Series, date: pd.Series) -> pd.Series:
    g = ratio.replace([np.inf, -np.inf], np.nan).groupby(date)
    return date.map(g.median())


def components(A: pd.Series, r2: pd.Series, symbol: pd.Series, date: pd.Series, kappa: pd.Series,
               mode: str) -> pd.DataFrame:
    """The forecast's components, in the order of the weights (``lr`` last)."""
    Ac, rc = FB.clean_square(A), FB.clean_square(r2)
    comp = FB.har_components(Ac.where(Ac.notna() & r2.notna()), symbol)
    lrCC = FB.rolling_rows(rc, symbol, FB.LONGRUN_SESSIONS, FB.LONGRUN_MIN)
    Z = {"d1": comp["d1"], "m5": comp["m5"], "m22": comp["m22"]}
    if mode == "panel":
        Z["lrM5"] = comp["lr"] * _market_state(comp["m5"] / comp["lr"], date)
        Z["lrM22"] = comp["lr"] * _market_state(comp["m22"] / comp["lr"], date)
    Z["lrCC"] = lrCC / kappa
    Z["lr"] = comp["lr"]
    return pd.DataFrame(Z, index=A.index)


def fit_weights(Zr: np.ndarray, yr: np.ndarray, floor: float = FLOOR) -> tuple[np.ndarray, float]:
    """argmin over convex weights c (last >= floor) of mean(y / f + ln f), f = Zr @ c; SLSQP with the exact
    gradient from two starts (equal weights; half on the last component)."""
    from scipy.optimize import minimize

    k = Zr.shape[1]

    def obj(c):
        f = np.maximum(Zr @ c, 1e-300)
        return float(np.mean(yr / f + np.log(f)))

    def grad(c):
        f = np.maximum(Zr @ c, 1e-300)
        return Zr.T @ (1.0 / f - yr / (f * f)) / len(yr)

    cons = [{"type": "eq", "fun": lambda c: c.sum() - 1.0, "jac": lambda c: np.ones_like(c)}]
    bounds = [(0.0, 1.0)] * (k - 1) + [(floor, 1.0)]
    best = None
    for s in (np.full(k, 1.0 / k), np.r_[np.full(k - 1, 0.5 / (k - 1)), 0.5]):
        res = minimize(obj, s, jac=grad, method="SLSQP", bounds=bounds, constraints=cons,
                       options={"maxiter": 500, "ftol": 1e-12})
        if best is None or res.fun < best.fun:
            best = res
    c = np.clip(best.x, 0.0, None)
    c = c / c.sum()
    return c, obj(c)


class Forecaster:
    """``f = kappa * Z @ c`` for a kernel ``A``; ``fit`` chooses c on the given rows."""

    def __init__(self, A: pd.Series, r2: pd.Series, symbol: pd.Series, date: pd.Series, mode: str,
                 kappa: pd.Series | None = None):
        self.kappa = calibration(A, r2, date, symbol, mode) if kappa is None else kappa
        self.Z = components(A, r2, symbol, date, self.kappa, mode)
        self.defined = (self.Z.notna().all(axis=1) & self.kappa.notna() & (self.kappa > 0) & (self.Z["lr"] > 0))
        self.grid = "continuous"

    def forecast(self, c) -> pd.Series:
        return pd.Series(self.kappa.to_numpy() * (self.Z.to_numpy() @ np.asarray(c, float)), index=self.Z.index)

    def fit(self, y: pd.Series, rows: pd.Series) -> tuple[np.ndarray, float]:
        Zr = self.Z[rows].to_numpy() * self.kappa[rows].to_numpy()[:, None]
        return fit_weights(Zr, y[rows].to_numpy())
