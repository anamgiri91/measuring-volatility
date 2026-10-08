"""POST HOC, EXPLORATORY follow-ups to the M16 holdout (scripts/40). Not in the frozen plan.

Written after the holdout verdicts were seen, because they raised the question: in NEPSE's
regime C -- the 90 sessions after the 20 April 2026 band reform -- close-to-close variance
forecasts better than Anam's estimator, and Anam's calibrated level drifts to 1.195. The estimator's
calibration pools the last 60 dates; at the reform the ratio of close-to-close to range-based variance
jumped, and a 60-date window needs most of a 90-session regime to catch up. This script asks whether
the calibration's SPEED or a RESET at a known rule change would have closed the gap. None of it
changes a frozen verdict; every result here is labelled post hoc wherever it is quoted.

Y1  Anam, Parkinson and close-to-close in regime C under calibration windows of 10, 20, 60 and 120
    pooled dates (the plan's estimator uses 60), and under a regime-reset calibration that pools only
    dates on or after the last known rule change (falling back to the trailing 60 dates until 10
    post-change dates exist). The open-quality coefficient b is reset the same way in the reset row.
Y2  The trajectory around the reform: by blocks of 10 sessions, b, the pooled ratio of mean r^2 to the
    mean kernel (the quantity the calibration tracks), and the 60-date calibration actually applied.

Outputs: output/tables/table106_anam_posthoc_calibration.csv, table106b_anam_posthoc_trajectory.csv
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util

import numpy as np
import pandas as pd

from nepsevol.estimators import anam as AN
from nepsevol.volforecast import LONGRUN_MIN, LONGRUN_SESSIONS, PHI_GRID, nw_t, trailing_sum

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"
RULE_CHANGES = [pd.Timestamp("2025-03-20"), pd.Timestamp("2025-09-23"), pd.Timestamp("2026-04-20")]

_spec = importlib.util.spec_from_file_location("s40", ROOT / "scripts" / "40_anam_holdout.py")
s40 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s40)


def pooled_ratio(num_rows, den_rows, date, L, reset=False, min_post=10):
    """Per-date ratio sum(num)/sum(den) over the last L dates, or (reset) over dates since the last
    rule change once ``min_post`` such dates exist."""
    num = num_rows.groupby(date).sum().sort_index()
    den = den_rows.groupby(date).sum().sort_index()
    trailing = num.rolling(L, min_periods=min(20, L)).sum() / den.rolling(L, min_periods=min(20, L)).sum()
    if not reset:
        return trailing
    out = trailing.copy()
    dates = num.index
    for i, t in enumerate(dates):
        past = [c for c in RULE_CHANGES if c <= t]
        if not past:
            continue
        since = (dates >= past[-1]) & (dates <= t)
        if since.sum() >= min_post:
            out.iloc[i] = num[since].sum() / den[since].sum()
    return out


def forecast_with_kappa(d, est_kappa: dict, train_mask, test_mask, win):
    """The plan's fair forecast test, but with each estimator's calibration supplied: est_kappa maps
    name -> (daily series X, per-row kappa)."""
    sym, r2 = d["symbol"], d["CC"]
    fut = r2.groupby(sym, sort=False).transform(lambda z: z[::-1].rolling(win, min_periods=win).mean()[::-1].shift(-1))
    parts = {}
    for name, (X, kappa) in est_kappa.items():
        Xv = X.where(X.notna() & r2.notna())
        cur = Xv.groupby(sym, sort=False).transform(lambda z: z.rolling(win, min_periods=win).mean())
        lr = trailing_sum(Xv, sym, LONGRUN_SESSIONS, LONGRUN_MIN) / Xv.notna().astype(float).groupby(sym, sort=False).transform(
            lambda z: z.rolling(LONGRUN_SESSIONS, min_periods=LONGRUN_MIN).sum())
        parts[name] = (kappa, cur, lr)
    ok_all = fut.notna() & (fut > 0)
    for kappa, cur, lr in parts.values():
        ok_all &= kappa.notna() & cur.notna() & lr.notna() & (kappa * cur > 0) & (lr > 0)
    losses, rows = {}, []
    for name, (kappa, cur, lr) in parts.items():
        def loss(phi, m):
            f = kappa * (phi * cur + (1 - phi) * lr)
            ok = m & ok_all & (f > 0)
            q = fut[ok] / f[ok]
            return q - np.log(q) - 1
        best = min(PHI_GRID, key=lambda p: loss(p, train_mask).mean())
        losses[name] = loss(best, test_mask)
        rows.append(dict(estimator=name, phi=float(best), n=len(losses[name]), QLIKE=float(losses[name].mean())))
    t = pd.DataFrame(rows).set_index("estimator")
    for name, ql in losses.items():
        j = losses["CC"].index.intersection(ql.index)
        diff = ql.loc[j] - losses["CC"].loc[j]
        per = pd.DataFrame({"x": diff, "date": d.loc[j, "date"]}).groupby("date")["x"].mean().sort_index()
        t.loc[name, "dQLIKE_vs_CC"] = float(diff.mean())
        t.loc[name, "t_vs_CC"] = nw_t(per.to_numpy(), lags=win)
    return t


def main() -> None:
    print("POST HOC: calibration speed and a rule-change reset (not in the frozen plan)")
    d = s40.nepse()
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    dev, C = d["regime"].isin(["A1", "B"]), d["regime"] == "C"
    date = d["date"]
    b60 = AN.open_quality_panel(o, r, date)
    b_reset = date.map(pooled_ratio((o * r), (o * o), date, 60, reset=True).clip(0, 1))
    A60 = AN.kernel(o, c, u, dd, b60)
    A_reset = AN.kernel(o, c, u, dd, b_reset)
    rows = []
    for win in (5, 21):
        specs = {"CC": (d["CC"], pd.Series(1.0, index=d.index))}
        for L in (10, 20, 60, 120):
            specs[f"P, calibration {L} dates"] = (d["P"], date.map(pooled_ratio(d["CC"], d["P"], date, L)))
            specs[f"Anam, calibration {L} dates"] = (A60, date.map(pooled_ratio(d["CC"], A60, date, L)))
        specs["P, reset at rule changes"] = (d["P"], date.map(pooled_ratio(d["CC"], d["P"], date, 60, reset=True)))
        specs["Anam, b and calibration reset at rule changes"] = (A_reset, date.map(pooled_ratio(d["CC"], A_reset, date, 60, reset=True)))
        t = forecast_with_kappa(d, specs, dev, C, win).reset_index()
        t.insert(0, "window", win)
        t.insert(0, "span", "C")
        rows.append(t)
        print(f"\nregime C, window {win} (post hoc)")
        print(t.sort_values("QLIKE")[["estimator", "QLIKE", "t_vs_CC"]].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    pd.concat(rows, ignore_index=True).to_csv(TAB / "table106_anam_posthoc_calibration.csv", index=False, float_format=FLOAT_FMT)

    # Y2: trajectory around the reform, blocks of 10 sessions
    dates = np.sort(date.unique())
    pos = {t: i for i, t in enumerate(dates)}
    reform = pos[np.datetime64("2026-04-20")]
    blk = date.map(lambda t: (pos[np.datetime64(t)] - reform) // 10)
    k60 = date.map(pooled_ratio(d["CC"], A60, date, 60))
    traj = pd.DataFrame({"block": blk, "b": b60, "kappa_applied": k60, "r2": d["CC"], "A": A60})
    g = traj[(traj.block >= -6) & (traj.block <= 8)].groupby("block")
    out = pd.DataFrame({"first_session_offset": g.block.first() * 10, "b": g.b.mean(), "kappa_applied": g.kappa_applied.mean(),
                        "ratio_mean_r2_to_mean_kernel": g.r2.mean() / g.A.mean()})
    out.to_csv(TAB / "table106b_anam_posthoc_trajectory.csv", index=False, float_format=FLOAT_FMT)
    print("\ntrajectory around the reform (post hoc; offsets in sessions from 2026-04-20)")
    print(out.to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
