"""The forecast comparison of plans M16-M18, FROZEN: kept unchanged so that tables 101, 108 and 113 stay
reproducible. Superseded by ``anam_estimator.evaluation`` and ``scripts/47_corrected_evaluation.py``
(plan M20), which correct four defects an independent audit found here on 9 October 2026:

* the training mask applies to the forecast ORIGIN only, so training targets run into the test span
  (audit item A01);
* a target of ``win`` sessions is the next ``win`` retained ROWS, stitched across sessions a security
  did not trade (A02);
* zero targets are dropped, and a phi above one can turn a forecast negative and be scored on fewer
  origins (A08);
* the reported mean difference weights stock-days, its t statistic dates (A09).

WHY THIS TEST, AND WHY IN THIS FORM
-----------------------------------
Latent variance is unobserved, so estimators are compared by how well each forecasts a common,
observable target: the mean squared close-to-close return over the next ``win`` sessions. Under QLIKE
loss the ranking with this target matches the ranking by the target's CONDITIONAL MEAN, the conditional
second moment of observed returns (Patton 2011, J. Econometrics 160). That is not latent integrated
variance: squared observed returns also carry the squared drift and closing-price errors
(``ESTIMAND_NOTE.md``; an earlier version said the ranking "matches the ranking with the true variance",
audit item A03). Three choices keep the comparison about MEASUREMENT rather than about forecasting
models:

* every estimator is put on the close-to-close scale by the SAME calibration scheme (``kappa``:
  a trailing ratio sum(r^2)/sum(X), pooled across the cross-section or from a series' own history),
  so an estimator is not rewarded or punished for its raw level;
* every estimator gets its OWN optimal shrinkage toward its long-run level,
  ``f = kappa [phi * mean_win(X) + (1 - phi) * mean_longrun(X)]``, with ``phi`` chosen on a training
  period. Without this, an estimator carrying a near-constant additive component (a band-capped
  squared overnight return, say) wins merely because a constant behaves like mean reversion;
* every estimator is scored on the SAME set of forecast origins -- those at which every estimator,
  its calibration and its long-run level are all defined -- so no estimator is judged on an easier
  sample.

Loss differences are tested with Newey-West statistics on the per-date mean difference (lags equal
to the window, since overlapping windows make consecutive dates dependent).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["nw_t", "trailing_sum", "fair_forecast_test"]

PHI_GRID = np.linspace(0.0, 2.0, 41)
LONGRUN_SESSIONS = 250
LONGRUN_MIN = 60


def nw_t(x, lags: int = 21) -> float:
    """t statistic of the mean of ``x`` with a Bartlett-kernel (Newey-West) long-run variance."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 10:
        return np.nan
    e = x - x.mean()
    s = e @ e / n
    for k in range(1, min(lags, n - 1) + 1):
        s += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return float(x.mean() / np.sqrt(s / n)) if s > 0 else np.nan


def trailing_sum(s: pd.Series, by: pd.Series, n: int, minp: int) -> pd.Series:
    return s.groupby(by, sort=False).transform(lambda z: z.rolling(n, min_periods=minp).sum())


def fair_forecast_test(d: pd.DataFrame, est: dict, train_mask: pd.Series, test_mask: pd.Series,
                       win: int = 5, scheme: tuple = ("pool", 60), by: str = "symbol", date: str = "date",
                       r2_col: str = "CC", refs=("P", "CC"), grid=PHI_GRID) -> tuple[pd.DataFrame, dict]:
    """Two-pass comparison on a common sample (module docstring).

    ``d`` sorted by (``by``, ``date``) with the squared close-to-close return in ``r2_col``.
    ``est`` maps names to daily estimator series aligned with ``d``. ``scheme`` is ("pool", L) --
    cross-sectional ratio over the last L dates -- or ("series", L) -- each series' own last L
    sessions (the only choice for a single index). Returns the result table and the per-origin
    test losses by estimator.
    """
    sym = d[by]
    r2 = d[r2_col]
    fut = r2.groupby(sym, sort=False).transform(
        lambda z: z[::-1].rolling(win, min_periods=win).mean()[::-1].shift(-1))
    trm = train_mask.reindex(d.index).fillna(False).astype(bool)
    tem = test_mask.reindex(d.index).fillna(False).astype(bool)
    kind, L = scheme
    parts = {}
    for name, X in est.items():
        X = X.reindex(d.index)
        valid = X.notna() & r2.notna()
        Xv, rv = X.where(valid), r2.where(valid)
        cur = Xv.groupby(sym, sort=False).transform(lambda z: z.rolling(win, min_periods=win).mean())
        sX = trailing_sum(Xv, sym, LONGRUN_SESSIONS, LONGRUN_MIN)
        nX = Xv.notna().astype(float).groupby(sym, sort=False).transform(
            lambda z: z.rolling(LONGRUN_SESSIONS, min_periods=LONGRUN_MIN).sum())
        lr = sX / nX
        if kind == "pool":
            num = rv.groupby(d[date]).sum()
            den = Xv.groupby(d[date]).sum()
            kap = num.rolling(L, min_periods=min(20, L)).sum() / den.rolling(L, min_periods=min(20, L)).sum()
            kappa = d[date].map(kap)
        elif kind == "series":
            kappa = trailing_sum(rv, sym, L, min(60, L)) / trailing_sum(Xv, sym, L, min(60, L))
        else:
            raise ValueError(f"scheme must be ('pool', L) or ('series', L), got {scheme!r}")
        parts[name] = (kappa, cur, lr)
    ok_all = fut.notna() & (fut > 0)
    for kappa, cur, lr in parts.values():
        ok_all &= kappa.notna() & cur.notna() & lr.notna() & (kappa * cur > 0) & (lr > 0)
    rows, losses = [], {}
    for name, (kappa, cur, lr) in parts.items():
        def loss(phi, m):
            f = kappa * (phi * cur + (1 - phi) * lr)
            ok = m & ok_all & (f > 0)
            q = fut[ok] / f[ok]
            return q - np.log(q) - 1
        best = min(grid, key=lambda p: loss(p, trm).mean())
        ql = loss(best, tem)
        losses[name] = ql
        rows.append(dict(estimator=name, phi=float(best), n=int(len(ql)), QLIKE=float(ql.mean())))
    t = pd.DataFrame(rows).set_index("estimator")
    for ref in [r for r in refs if r in losses]:
        for name, ql in losses.items():
            j = losses[ref].index.intersection(ql.index)
            diff = ql.loc[j] - losses[ref].loc[j]
            per_date = pd.DataFrame({"diff": diff, "date": d.loc[j, date]}).groupby("date")["diff"].mean().sort_index()
            t.loc[name, f"dQLIKE_vs_{ref}"] = float(diff.mean())
            t.loc[name, f"t_vs_{ref}"] = nw_t(per_date.to_numpy(), lags=win)
    return t, losses
