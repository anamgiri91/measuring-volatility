"""DEVELOPMENT evidence for Anam's estimator (nepsevol.estimators.anam) -- NEPSE regimes A1 and B only.

This script reproduces the experiments that shaped the estimator, so the selection process can be
audited. It reads ONLY the development sample (regimes A1, 2024-03-04 to 2025-03-19, and B,
2025-03-20 to 2025-09-21) and simulated panels. It never reads regimes A2 or C, NIFTY 50 or the
S&P 500: those are the holdout of M16_ANAM_ESTIMATOR_PLAN.md, frozen after this script's results.

Design choices are made on cross-regime forecasts -- weights or tuning from one regime, scored on
the other -- because the two regimes differ in their closing rule (last trade in A1, a 15-minute
VWAP in B), which is the kind of change an estimator must survive.

Outputs (output/tables/):
    table98_anam_dev_forecast.csv       fair forecast test: Anam's estimator vs the classical set
    table98b_anam_dev_calibration.csv   per-security vs pooled calibration
    table98c_anam_dev_lambda.csv        sensitivity to the blend constant LAMBDA0
    table98d_anam_dev_rejected.csv      alternatives tried and rejected
    table99_anam_dev_simulation.csv     known-truth accuracy in simulated markets
    table100_anam_dev_level.csv         raw level relative to close-to-close, by regime
    table100b_anam_dev_noise.csv        instrumented noise (the M14 machinery, reference r^2)
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util
import time

import numpy as np
import pandas as pd

from nepsevol.calibration import calibrate, lagged_means
from nepsevol.estimators import anam as AN
from nepsevol.estimators.microsim import simulate_panel
from nepsevol.volforecast import fair_forecast_test

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"
LN2 = float(np.log(2.0))
DEV = ["A1", "B"]
FOLDS = [("A1", "B"), ("B", "A1")]
WINDOWS = [5, 21]

_spec = importlib.util.spec_from_file_location("s34", ROOT / "scripts" / "34_instrumented_calibration.py")
s34 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s34)


# --------------------------------------------------------------------------------------------
# Data and estimators
# --------------------------------------------------------------------------------------------

def dev_panel() -> pd.DataFrame:
    d = s34.build_nepse()
    d = d[d["regime"].isin(DEV)].copy()
    d = d.dropna(subset=["o", "c", "u", "d"]).sort_values(["symbol", "date"]).reset_index(drop=True)
    d["r"] = d["o"] + d["c"]
    d["CC"] = d["r"] ** 2
    return d


def yz_daily(o, c, RS, n=21):
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    return o * o + k * c * c + (1 - k) * RS


def estimator_set(d: pd.DataFrame) -> dict:
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]
    b = AN.open_quality_panel(o, d["r"], d["date"])
    zero = pd.Series(0.0, index=d.index)
    return {
        "CC": d["CC"], "P": d["P"], "GK": d["GK"], "RS": d["RS"],
        "o2+P": o * o + d["P"], "o2+GK": o * o + d["GK"], "YZ (daily form)": yz_daily(o, c, d["RS"]),
        "Anam, open-free special case (b=0)": AN.kernel(o, c, u, dd, zero),
        "Anam": AN.kernel(o, c, u, dd, b),
    }


def regime_mask(d, reg):
    return d["regime"] == reg


def run_forecasts(d: pd.DataFrame, est: dict, scheme=("pool", AN.POOL_SESSIONS), tag="") -> pd.DataFrame:
    rows = []
    for win in WINDOWS:
        for tr, te in FOLDS:
            t0 = time.time()
            t, _ = fair_forecast_test(d, est, regime_mask(d, tr), regime_mask(d, te), win=win, scheme=scheme)
            t = t.reset_index()
            t.insert(0, "test", te)
            t.insert(0, "train", tr)
            t.insert(0, "window", win)
            t.insert(0, "calibration", f"{scheme[0]}{scheme[1]}")
            rows.append(t)
            print(f"  {tag} window {win}, {tr} -> {te}: {time.time() - t0:.0f}s; best "
                  f"{t.sort_values('QLIKE').estimator.iloc[0]!r}")
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------------------------
# Rejected alternatives
# --------------------------------------------------------------------------------------------

def openfree_composite(d_train: pd.DataFrame, d_all: pd.DataFrame) -> pd.Series:
    """The instrumented minimum-noise quadratic in (h, l, r) -- weights from the training regime."""
    def blocks(z):
        h, l, r = z["o"] + z["u"], z["o"] + z["d"], z["o"] + z["c"]
        return {"h2": h * h, "l2": l * l, "r2": r * r, "hl": h * l, "hr": h * r, "lr": l * r}
    tr = d_train.copy()
    lm = lagged_means(tr, ["CC", "P"], windows=(1, 5, 22), skip=2)
    lm.columns = [f"x_{c}" for c in lm.columns]
    tr = pd.concat([tr, lm], axis=1)
    instr = list(lm.columns)
    bt = blocks(tr)
    names = list(bt)
    X = pd.DataFrame({"CC": tr["CC"], **bt})
    frame = pd.concat([tr[["symbol", "date", "w"] + instr], X], axis=1).dropna().reset_index(drop=True)
    cols = ["CC"] + names
    res = calibrate(frame[cols].to_numpy(), frame[instr].to_numpy(), frame["symbol"], cols, "CC",
                    weights=frame["w"].to_numpy(), date=frame["date"], composite_over=names, compute_J=False)
    w = pd.Series(res.weights, index=res.measures).loc[names]
    ba = blocks(d_all)
    return sum(w[k] * ba[k] for k in names)


def rejected(d: pd.DataFrame) -> pd.DataFrame:
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]
    b = AN.open_quality_panel(o, d["r"], d["date"])
    base = AN.kernel(o, c, u, dd, b)
    R = u - dd
    P = R ** 2 / (4 * LN2)
    ct = d["r"] - b * o
    w = AN.LAMBDA0 * (1 - b)
    gk_switch = base + (1 - w) * (2 * LN2 - 1) * b ** 2 * (P - ct * ct)
    n = d["n_trades"].clip(lower=2).astype(float)
    rows = []
    for win in WINDOWS:
        for tr, te in FOLDS:
            comp = openfree_composite(d[regime_mask(d, tr)], d)
            est = {"CC": d["CC"], "P": d["P"], "Anam": base,
                   "open-free instrumented composite (trained on the other regime)": comp,
                   "Anam + Garman-Klass control switched on by b^2": gk_switch,
                   "Parkinson with a trade-count correction": P / (1 - 0.73 / np.sqrt(n)) ** 2}
            t, _ = fair_forecast_test(d, est, regime_mask(d, tr), regime_mask(d, te), win=win,
                                      scheme=("pool", AN.POOL_SESSIONS))
            t = t.reset_index()
            t.insert(0, "test", te); t.insert(0, "train", tr); t.insert(0, "window", win)
            rows.append(t)
            print(f"  rejected: window {win}, {tr} -> {te} done")
    return pd.concat(rows, ignore_index=True)


def lambda_sensitivity(d: pd.DataFrame) -> pd.DataFrame:
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]
    b = AN.open_quality_panel(o, d["r"], d["date"])
    est = {"P": d["P"], "CC": d["CC"]}
    for lam in (0.0, 0.1, 0.2, 0.3, 0.4, 0.6):
        est[f"Anam, LAMBDA0={lam}"] = AN.kernel(o, c, u, dd, b, lam0=lam)
    return run_forecasts(d, est, tag="lambda")


# --------------------------------------------------------------------------------------------
# Simulation with known truth
# --------------------------------------------------------------------------------------------

WORLDS = {
    "clean continuous market": dict(auction_noise_frac=0.0, band=None, limit=None, stale_open_thin=0.0,
                                    stale_open_thick=0.0, trades_median=3000, trades_disp=0.2,
                                    spread_bp_at_median=1.0),
    "simulator defaults": dict(),
    "moderate opening error (0.7 overnight sd)": dict(auction_noise_frac=0.7, band=None),
    "heavy opening error (2.2 overnight sd), +/-2% band": dict(auction_noise_frac=2.2),
    "heavy opening error (2.2 overnight sd), no band": dict(auction_noise_frac=2.2, band=None),
    "stale opens (60%)": dict(stale_open_thin=0.6, stale_open_thick=0.6),
    "very thin trading (20 trades median)": dict(trades_median=20),
}


def simulation(win=21, seed=7) -> pd.DataFrame:
    rows = []
    for world, p in WORLDS.items():
        s = simulate_panel(n_sec=80, n_days=400, seed=seed, **p).sort_values(["symbol", "day"]).reset_index(drop=True)
        s = s[s["prev_close"].notna()].reset_index(drop=True)
        co = AN.bar_coordinates(s.open, s.high, s.low, s.close, s.prev_close)
        o, c, u, dd, r = co.o, co.c, co.u, co.d, co.r
        b = AN.open_quality_panel(o, r, s["day"])
        R = u - dd
        P = R ** 2 / (4 * LN2)
        GK = 0.5 * R ** 2 - (2 * LN2 - 1) * c ** 2
        RS = u * (u - c) + dd * (dd - c)
        est = {"CC": r * r, "P": P, "GK": GK, "o2+P": o * o + P, "o2+GK": o * o + GK,
               "YZ (daily form)": yz_daily(o, c, RS, win),
               "Anam, open-free special case (b=0)": AN.kernel(o, c, u, dd, pd.Series(0.0, index=s.index)),
               "Anam": AN.kernel(o, c, u, dd, b)}
        truth = (s.iv + s.on).groupby(s.symbol, sort=False).transform(lambda z: z.rolling(win, min_periods=win).mean())
        curs, raws = {}, {}
        for k, X in est.items():
            cur = X.groupby(s.symbol, sort=False).transform(lambda z: z.rolling(win, min_periods=win).mean())
            raws[k] = cur
            curs[k] = cur * AN.calibration_panel(X, r * r, s["day"])
        ok = truth.notna()
        for v in curs.values():
            ok &= v.notna() & (v > 0)
        for k in est:
            q = truth[ok] / curs[k][ok]
            rows.append(dict(world=world, estimator=k, n=int(ok.sum()),
                             b_market=float(np.sum(o * r) / np.sum(o * o)),
                             raw_level_vs_truth=float(raws[k][ok].mean() / truth[ok].mean()),
                             calibrated_QLIKE_vs_truth=float((q - np.log(q) - 1).mean())))
        print(f"  simulated: {world}")
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Level and instrumented noise on the development sample
# --------------------------------------------------------------------------------------------

def level_by_regime(d: pd.DataFrame, est: dict) -> pd.DataFrame:
    rows = []
    for reg in DEV:
        m = d["regime"] == reg
        for k, X in est.items():
            ok = m & X.notna() & d["CC"].notna()
            rows.append(dict(regime=reg, estimator=k, raw_mean_over_mean_r2=float(X[ok].mean() / d.loc[ok, "CC"].mean())))
        out = AN.anam_estimator(d[m].rename(columns={"prev_close_adj": "pc"}), window=21, mode="panel", prev_close="pc")
        ok = out["var"].notna()
        r2w = d.loc[m, "CC"].groupby(d.loc[m, "symbol"], sort=False).transform(lambda z: z.rolling(21, min_periods=21).mean())
        rows.append(dict(regime=reg, estimator="Anam (calibrated, 21-session window)",
                         raw_mean_over_mean_r2=float(out.loc[ok, "var"].mean() / r2w[ok].mean())))
    return pd.DataFrame(rows)


def instrumented_noise(d: pd.DataFrame, est: dict) -> pd.DataFrame:
    x = d.copy()
    lm = lagged_means(x, ["CC", "P"], windows=(1, 5, 22), skip=2)
    lm.columns = [f"z_{c}" for c in lm.columns]
    x = pd.concat([x, lm], axis=1)
    instr = list(lm.columns)
    names = list(est)
    X = pd.DataFrame(est)
    frame = pd.concat([x[["symbol", "date", "w"] + instr], X], axis=1).dropna().reset_index(drop=True)
    res = calibrate(frame[names].to_numpy(), frame[instr].to_numpy(), frame["symbol"], names, "CC",
                    weights=frame["w"].to_numpy(), date=frame["date"], composite_over=None, compute_J=False)
    t = res.table()[["measure", "mean_ratio_var", "iv_slope", "additive_share", "noise_upper"]]
    t["efficiency_vs_CC_lower_bound"] = float(t.loc[t.measure == "CC", "noise_upper"].iloc[0]) / t["noise_upper"]
    t["n_obs"] = res.n_obs
    return t


def main() -> None:
    print("DEVELOPMENT evidence for Anam's estimator (NEPSE regimes A1 and B only)")
    d = dev_panel()
    print(f"  development sample: {len(d):,} stock-days, {d.symbol.nunique()} securities")
    est = estimator_set(d)

    t98 = run_forecasts(d, est, tag="main")
    t98.to_csv(TAB / "table98_anam_dev_forecast.csv", index=False, float_format=FLOAT_FMT)

    sub = {k: est[k] for k in ("CC", "P", "Anam")}
    t98b = pd.concat([run_forecasts(d, sub, scheme=("series", 250), tag="calib-sec"),
                      run_forecasts(d, sub, scheme=("pool", AN.POOL_SESSIONS), tag="calib-pool")], ignore_index=True)
    t98b.to_csv(TAB / "table98b_anam_dev_calibration.csv", index=False, float_format=FLOAT_FMT)

    lambda_sensitivity(d).to_csv(TAB / "table98c_anam_dev_lambda.csv", index=False, float_format=FLOAT_FMT)
    rejected(d).to_csv(TAB / "table98d_anam_dev_rejected.csv", index=False, float_format=FLOAT_FMT)
    simulation().to_csv(TAB / "table99_anam_dev_simulation.csv", index=False, float_format=FLOAT_FMT)
    level_by_regime(d, est).to_csv(TAB / "table100_anam_dev_level.csv", index=False, float_format=FLOAT_FMT)
    instrumented_noise(d, est).to_csv(TAB / "table100b_anam_dev_noise.csv", index=False, float_format=FLOAT_FMT)

    pd.set_option("display.width", 220)
    show = t98[["calibration", "window", "train", "test", "estimator", "QLIKE", "t_vs_P", "t_vs_CC"]]
    for (w, tr), g in show.groupby(["window", "train"], sort=False):
        print(f"\nwindow {w}, trained on {tr}:")
        print(g.sort_values("QLIKE").to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
