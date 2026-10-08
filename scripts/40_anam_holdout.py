"""M16 HOLDOUT: Anam's estimator on NEPSE regimes A2 and C, NIFTY 50 and the S&P 500.

Implements M16_ANAM_ESTIMATOR_PLAN.md, frozen and pushed in commit dc41f1e together with the
estimator (nepsevol.estimators.anam) and the evaluation module (nepsevol.volforecast) before this
script existed or any holdout observation was read. Every specification is the plan's; the decision
rules are applied mechanically in ``decisions()``.

Two implementation details the plan leaves implicit are fixed here and stated in the results:
* level ratios "by regime" use only 21-session windows lying wholly inside the regime (or inside the
  index's test half), so no window mixes two rule regimes;
* H3's "the Yang-Zhang window form's ratio changes by more" is read as "by more than 0.10".

Outputs (output/tables/):
    table101_anam_holdout_forecast.csv   T1: fair forecast test, every market and horizon
    table102_anam_holdout_level.csv      T2/T3: raw and calibrated level against close-to-close
    table103_anam_holdout_noise.csv      T4: instrumented noise on the NEPSE holdout (reported)
    table104_anam_holdout_implied.csv    T5: correlation with implied variance (reported)
    table105_anam_holdout_decisions.csv  H1-H5 and the per-rival verdicts, applied mechanically
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util

import numpy as np
import pandas as pd

from nepsevol import opening as op
from nepsevol.calibration import calibrate, lagged_means
from nepsevol.estimators import anam as AN
from nepsevol.volforecast import fair_forecast_test

TAB = ROOT / "output" / "tables"
EXT = ROOT / "data" / "external"
FLOAT_FMT = "%.10g"
LN2 = float(np.log(2.0))
WINDOWS = [5, 21]
RIVALS = ["CC", "P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"]
VARIANT = "Anam, open-free special case (b=0)"

_spec = importlib.util.spec_from_file_location("s34", ROOT / "scripts" / "34_instrumented_calibration.py")
s34 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s34)


# --------------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------------

def nepse() -> pd.DataFrame:
    d = s34.build_nepse()
    d = d[d["regime"].notna()].dropna(subset=["o", "c", "u", "d"]).sort_values(["symbol", "date"]).reset_index(drop=True)
    d["r"] = d["o"] + d["c"]
    d["CC"] = d["r"] ** 2
    d["pc"] = d["prev_close_adj"]
    return d


def index_series(raw: pd.DataFrame, name: str) -> pd.DataFrame:
    """One index, M14's convention: positivity screen only; previous close = prior session's close."""
    x = raw.rename(columns=str.lower).copy()
    x = x[(x[["open", "high", "low", "close"]] > 0).all(axis=1)].sort_values("date").reset_index(drop=True)
    x["symbol"] = name
    x["pc"] = x["close"].shift(1)
    co = AN.bar_coordinates(x["open"], x["high"], x["low"], x["close"], x["pc"])
    for k in ("o", "c", "u", "d", "r"):
        x[k] = co[k]
    R = x["u"] - x["d"]
    x["P"] = R ** 2 / (4 * LN2)
    x["GK"] = 0.5 * R ** 2 - (2 * LN2 - 1) * x["c"] ** 2
    x["RS"] = x["u"] * (x["u"] - x["c"]) + x["d"] * (x["d"] - x["c"])
    x["CC"] = x["r"] ** 2
    x = x.dropna(subset=["o", "c", "u", "d"]).reset_index(drop=True)
    half = x["date"].iloc[len(x) // 2]
    x["span"] = np.where(x["date"] < half, "train", "test")
    return x


def nifty() -> pd.DataFrame:
    raw = pd.read_csv(EXT / "nifty50.csv", parse_dates=["Date"])
    return index_series(raw, "NIFTY50")


def sp500() -> pd.DataFrame:
    from arch.data import sp500 as sp
    raw = sp.load().reset_index()
    raw = raw.rename(columns={"index": "Date"})[["Date", "Open", "High", "Low", "Close"]]
    return index_series(raw, "SP500")


# --------------------------------------------------------------------------------------------
# Estimators
# --------------------------------------------------------------------------------------------

def yz_daily(o, c, RS, n=21):
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    return o * o + k * c * c + (1 - k) * RS


def estimator_set(d: pd.DataFrame, mode: str) -> tuple[dict, pd.Series]:
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]
    if mode == "panel":
        b = AN.open_quality_panel(o, d["r"], d["date"])
    else:
        b = AN.open_quality_series(o, d["r"], d["symbol"])
    est = {"CC": d["CC"], "P": d["P"], "GK": d["GK"], "RS": d["RS"],
           "o2+P": o * o + d["P"], "o2+GK": o * o + d["GK"], "YZ (daily form)": yz_daily(o, c, d["RS"]),
           VARIANT: AN.kernel(o, c, u, dd, pd.Series(0.0, index=d.index)),
           "Anam": AN.kernel(o, c, u, dd, b)}
    return est, b


# --------------------------------------------------------------------------------------------
# T1 forecasts
# --------------------------------------------------------------------------------------------

def t1(d, est, train_mask, test_mask, scheme, market, span) -> pd.DataFrame:
    rows = []
    for win in WINDOWS:
        t, _ = fair_forecast_test(d, est, train_mask, test_mask, win=win, scheme=scheme, refs=("Anam", "P", "CC"))
        t = t.reset_index()
        t.insert(0, "test_span", span)
        t.insert(0, "window", win)
        t.insert(0, "market", market)
        rows.append(t)
        best = t.sort_values("QLIKE")["estimator"].iloc[0]
        print(f"  T1 {market} [{span}] window {win}: best {best!r}; Anam rank "
              f"{int(t['QLIKE'].rank().loc[t['estimator'] == 'Anam'].iloc[0])} of {len(t)}")
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------------------------
# T2/T3 level
# --------------------------------------------------------------------------------------------

def window_mean(X, sym, n=21):
    return X.groupby(sym, sort=False).transform(lambda z: z.rolling(n, min_periods=n).mean())


def inside(mask: pd.Series, sym: pd.Series, n=21) -> pd.Series:
    """Rows whose n-session window (ending at the row) lies wholly inside ``mask``."""
    m = mask.astype(float).groupby(sym, sort=False).transform(lambda z: z.rolling(n, min_periods=n).min())
    return m == 1


def yz_window(d: pd.DataFrame) -> pd.Series:
    parts = []
    for _, g in d.groupby("symbol", sort=False):
        parts.append(op.yang_zhang_components(g["o"], g["c"], g["RS"], window=21)["yz"])
    return pd.concat(parts).reindex(d.index)


def t2_level(d, est, spans: dict, market, mode) -> pd.DataFrame:
    sym = d["symbol"]
    r2w = window_mean(d["CC"], sym)
    cal = AN.anam_estimator(d.assign(prev_close=d["pc"]), window=21, mode=mode, prev_close="pc")["var"]
    series = {k: window_mean(v, sym) for k, v in est.items()}
    series["YZ (window form)"] = yz_window(d)
    series["Anam (calibrated)"] = cal
    rows = []
    for span, mask in spans.items():
        ok = inside(mask, sym) & r2w.notna()
        for v in series.values():
            ok &= v.notna()
        for k, v in series.items():
            rows.append(dict(market=market, span=span, estimator=k, n=int(ok.sum()),
                             ratio_to_close_to_close=float(v[ok].mean() / r2w[ok].mean())))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# T4 instrumented noise (NEPSE holdout), T5 implied variance
# --------------------------------------------------------------------------------------------

def t4_noise(d, est, mask) -> pd.DataFrame:
    lm = lagged_means(d, ["CC", "P"], windows=(1, 5, 22), skip=2)
    lm.columns = [f"z_{c}" for c in lm.columns]
    x = pd.concat([d, lm], axis=1)[mask]
    instr = list(lm.columns)
    names = list(est)
    X = pd.DataFrame({k: v[mask] for k, v in est.items()})
    frame = pd.concat([x[["symbol", "date", "w"] + instr], X], axis=1).dropna().reset_index(drop=True)
    res = calibrate(frame[names].to_numpy(), frame[instr].to_numpy(), frame["symbol"], names, "CC",
                    weights=frame["w"].to_numpy(), date=frame["date"], composite_over=None, compute_J=False)
    t = res.table()[["measure", "mean_ratio_var", "iv_slope", "additive_share", "noise_upper"]]
    t["efficiency_vs_CC_lower_bound"] = float(t.loc[t.measure == "CC", "noise_upper"].iloc[0]) / t["noise_upper"]
    t["n_obs"] = res.n_obs
    t["first_stage_F"] = res.first_stage_F
    return t


def t5_implied(d, est, implied: pd.Series, mask, market) -> pd.DataFrame:
    sym = d["symbol"]
    rows = []
    for k, X in est.items():
        kap = AN.calibration_series(X, d["CC"], sym)
        v = kap * window_mean(X, sym)
        ok = mask & v.notna() & implied.notna()
        rows.append(dict(market=market, estimator=k, n=int(ok.sum()),
                         corr_with_implied_variance=float(np.corrcoef(v[ok], implied[ok])[0, 1]),
                         spearman=float(pd.Series(v[ok]).rank().corr(pd.Series(implied[ok]).rank()))))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Decisions
# --------------------------------------------------------------------------------------------

def verdict(dq, t):
    if not np.isfinite(t):
        return "no difference"
    if dq < 0 and t < -1.96:
        return "beats"
    if dq > 0 and t > 1.96:
        return "loses to"
    return "no difference"


def decisions(fc: pd.DataFrame, lev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    # per-rival verdicts: Anam's loss minus the rival's = -(rival minus Anam)
    for (market, span, win), g in fc.groupby(["market", "test_span", "window"], sort=False):
        g = g.set_index("estimator")
        for rv in RIVALS:
            dq, t = -g.loc[rv, "dQLIKE_vs_Anam"], -g.loc[rv, "t_vs_Anam"]
            rows.append(dict(rule="rival", market=market, span=span, window=win, rival=rv,
                             dQLIKE_Anam_minus_rival=dq, t=t, verdict=f"Anam {verdict(dq, t)} {rv}"))
    v = pd.DataFrame(rows)

    def get(market, span, win, rv):
        r = v[(v.market == market) & (v.span == span) & (v.window == win) & (v.rival == rv)]
        return r["verdict"].iloc[0]

    out = []
    h1 = all(get("NEPSE", "A2+C", 5, rv) == f"Anam beats {rv}" for rv in ("CC", "P"))
    out.append(dict(rule="H1", market="NEPSE", verdict="holds" if h1 else "does not hold",
                    detail=f"5 sessions on A2+C: {get('NEPSE', 'A2+C', 5, 'CC')}; {get('NEPSE', 'A2+C', 5, 'P')}"))
    L = lev[lev.market == "NEPSE"].set_index(["span", "estimator"])["ratio_to_close_to_close"]
    an = [L[("A2", "Anam (calibrated)")], L[("C", "Anam (calibrated)")]]
    rivals_out = all(not (0.9 <= L[(s, e)] <= 1.1) for s in ("A2", "C") for e in ("o2+P", "YZ (daily form)"))
    h2 = all(0.9 <= a <= 1.1 for a in an) and rivals_out
    out.append(dict(rule="H2", market="NEPSE", verdict="holds" if h2 else "does not hold",
                    detail=f"Anam {an[0]:.3f} (A2), {an[1]:.3f} (C); o2+P {L[('A2', 'o2+P')]:.3f}, {L[('C', 'o2+P')]:.3f}; "
                           f"YZ daily {L[('A2', 'YZ (daily form)')]:.3f}, {L[('C', 'YZ (daily form)')]:.3f}"))
    dA = L[("C", "Anam (calibrated)")] - L[("A2", "Anam (calibrated)")]
    dY = L[("C", "YZ (window form)")] - L[("A2", "YZ (window form)")]
    h3 = abs(dA) < 0.10 and abs(dY) > 0.10
    out.append(dict(rule="H3", market="NEPSE", verdict="holds" if h3 else "does not hold",
                    detail=f"change A2 -> C: Anam {dA:+.3f}; Yang-Zhang window form {dY:+.3f}"))
    for rule, market in (("H4", "NIFTY50"), ("H5", "SP500")):
        vv = get(market, "test half", 5, "CC")
        out.append(dict(rule=rule, market=market, verdict="holds" if vv == "Anam beats CC" else "does not hold",
                        detail=f"5 sessions on the test half: {vv}"))
    for market, span in (("NEPSE", "A2+C"), ("NIFTY50", "test half"), ("SP500", "test half")):
        losses = v[(v.market == market) & (v.span == span) & v.verdict.str.startswith("Anam loses")]
        out.append(dict(rule="best in market", market=market,
                        verdict="yes" if losses.empty else "no",
                        detail="no rival beats Anam at 5 or 21 sessions" if losses.empty else
                        "; ".join(f"{r.verdict} at {r.window}" for r in losses.itertuples())))
    return pd.concat([pd.DataFrame(out), v], ignore_index=True)


def main() -> None:
    print("M16 HOLDOUT (frozen plan, commit dc41f1e)")
    # NEPSE --------------------------------------------------------------------------------
    d = nepse()
    est, b = estimator_set(d, "panel")
    dev, a2, c_ = d["regime"].isin(["A1", "B"]), d["regime"] == "A2", d["regime"] == "C"
    print(f"  NEPSE: {len(d):,} stock-days; holdout A2 {int(a2.sum()):,}, C {int(c_.sum()):,}; "
          f"b on holdout dates: A2 median {b[a2].median():.3f}, C median {b[c_].median():.3f}")
    fc = [t1(d, est, dev, a2 | c_, ("pool", AN.POOL_SESSIONS), "NEPSE", "A2+C"),
          t1(d, est, dev, a2, ("pool", AN.POOL_SESSIONS), "NEPSE", "A2"),
          t1(d, est, dev, c_, ("pool", AN.POOL_SESSIONS), "NEPSE", "C")]
    lev = [t2_level(d, est, {"A2": a2, "C": c_}, "NEPSE", "panel")]
    noise = t4_noise(d, est, a2 | c_)
    noise.insert(0, "market", "NEPSE")
    # Indices --------------------------------------------------------------------------------
    implied = []
    vix_in = pd.read_csv(EXT / "india_vix.csv", parse_dates=["Date"]).rename(columns={"Date": "date"})
    from arch.data import vix as vixmod
    vix_us = vixmod.load().reset_index()
    vix_us = vix_us.rename(columns={vix_us.columns[0]: "date"})
    for market, x, iv_frame, col in (("NIFTY50", nifty(), vix_in, "India_VIX"), ("SP500", sp500(), vix_us, "vix")):
        e, bx = estimator_set(x, "series")
        tr, te = x["span"] == "train", x["span"] == "test"
        stale = float((x["o"] == 0).mean())
        bad = int(((x["high"] < x[["open", "close"]].max(axis=1)) | (x["low"] > x[["open", "close"]].min(axis=1))).sum())
        print(f"  {market}: {len(x):,} sessions {x['date'].min().date()} to {x['date'].max().date()}; test half from "
              f"{x.loc[te, 'date'].min().date()}; stale opens {stale:.3f}; OHLC-inconsistent rows {bad}; "
              f"b (test half median) {bx[te].median():.3f}")
        fc.append(t1(x, e, tr, te, ("series", AN.SERIES_SESSIONS), market, "test half"))
        lev.append(t2_level(x, e, {"test half": te}, market, "series"))
        ivs = x[["date"]].merge(iv_frame[["date", col]], on="date", how="left")[col]
        ivs.index = x.index
        implied.append(t5_implied(x, e, (ivs / 100.0) ** 2 / 252.0, te, market))
    fc = pd.concat(fc, ignore_index=True)
    lev = pd.concat(lev, ignore_index=True)
    implied = pd.concat(implied, ignore_index=True)
    dec = decisions(fc, lev)
    fc.to_csv(TAB / "table101_anam_holdout_forecast.csv", index=False, float_format=FLOAT_FMT)
    lev.to_csv(TAB / "table102_anam_holdout_level.csv", index=False, float_format=FLOAT_FMT)
    noise.to_csv(TAB / "table103_anam_holdout_noise.csv", index=False, float_format=FLOAT_FMT)
    implied.to_csv(TAB / "table104_anam_holdout_implied.csv", index=False, float_format=FLOAT_FMT)
    dec.to_csv(TAB / "table105_anam_holdout_decisions.csv", index=False, float_format=FLOAT_FMT)

    pd.set_option("display.width", 230)
    pd.set_option("display.max_colwidth", 120)
    print("\nDECISIONS")
    print(dec[dec.rule != "rival"][["rule", "market", "verdict", "detail"]].to_string(index=False))
    for (market, span, win), g in fc.groupby(["market", "test_span", "window"], sort=False):
        print(f"\n{market} [{span}] window {win}")
        print(g.sort_values("QLIKE")[["estimator", "QLIKE", "t_vs_Anam", "t_vs_P", "t_vs_CC"]].to_string(
            index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nLEVEL (ratio to close-to-close)")
    print(lev.pivot_table(index="estimator", columns=["market", "span"], values="ratio_to_close_to_close").round(3).to_string())


if __name__ == "__main__":
    main()
