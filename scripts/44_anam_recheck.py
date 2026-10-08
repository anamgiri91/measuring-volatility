"""POST HOC recheck of the claims made for Anam's estimator (plans M16-M18). Not pre-registered.

Written after every M16-M18 verdict was known, when the manuscript and README were audited for
claims stronger than the evidence. Nothing here changes a frozen verdict. Each part asks how much a
headline depends on a choice the plans fixed, or on an assumption about the data:

R1  Level. Every estimator is given the calibration Anam's estimator has (the pooled 60-date ratio
    to r^2 in a panel, the series' own 250 sessions for an index) and its level measured as in T2,
    first with the calibration window ending at the window's last session, as frozen, and then with
    a calibration that ends before the 21-session window starts.
R2  Inference. The frozen Newey-West t (lags = horizon, Bartlett) against longer lags (2h and 4h),
    non-overlapping forecast origins, an MSE loss (same forecasts), and each half of the test span,
    for Anam and its open-free form against close-to-close, Parkinson and each other, and for every
    classical range estimator against Anam.
R3  Multiplicity. Holm adjustment of the one-sided p-values of every "beats" rule of the three plans,
    within each plan and across all three. A frozen "beats" is t < -1.96, i.e. one-sided p < 0.025.
R4  Data. Zero-range and stale-open shares; the raw (unclipped) b of the two indices; the trailing
    pooled b of NEPSE's holdout regimes on the same statistic as the new markets; the Dhaka date
    repair (repaired against unambiguous dates, with the unrepaired 2023-2026 panel as control);
    Morocco's band schedule (large moves by band regime, before the band screen); Vietnam's
    exchanges, inferred from each ticker's largest moves; and how often Dhaka's close is its last
    trade.

Inputs: as scripts 40, 42 and 43 (the frontier files under data/external/frontier/ are required).
Outputs (output/tables/):
    table117_anam_recheck_level.csv          R1
    table118_anam_recheck_inference.csv      R2
    table119_anam_recheck_multiplicity.csv   R3
    table120_anam_recheck_data.csv           R4
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util
import math
import sys
import time

import numpy as np
import pandas as pd

from nepsevol import frontier as F
from nepsevol.estimators import anam as AN
from nepsevol.volforecast import LONGRUN_MIN, LONGRUN_SESSIONS, PHI_GRID, nw_t, trailing_sum

TAB = ROOT / "output" / "tables"
INPUTS = ROOT / "data" / "external" / "frontier"
FLOAT_FMT = "%.10g"

_spec = importlib.util.spec_from_file_location("s40", ROOT / "scripts" / "40_anam_holdout.py")
s40 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s40)

VARIANT = s40.VARIANT
RANGE_RIVALS = ["P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"]
PAIRS = [("Anam", "CC"), ("Anam", "P"), (VARIANT, "CC"), (VARIANT, "Anam")] + [(x, "Anam") for x in RANGE_RIVALS]
FROZEN = {"NEPSE": "table101_anam_holdout_forecast.csv", "NIFTY50": "table101_anam_holdout_forecast.csv",
          "SP500": "table101_anam_holdout_forecast.csv", "DSE 2023-2026": "table108_anam_frontier_forecast.csv",
          "Vietnam 2007-2020": "table108_anam_frontier_forecast.csv", "DSE 2009-2021": "table108_anam_frontier_forecast.csv",
          "Morocco 2012-2026": "table113_anam_morocco_forecast.csv"}


# --------------------------------------------------------------------------------------------
# Samples, exactly as the frozen scripts build them
# --------------------------------------------------------------------------------------------

def samples():
    d = s40.nepse()
    dev, a2, c_ = d["regime"].isin(["A1", "B"]), d["regime"] == "A2", d["regime"] == "C"
    yield "NEPSE", d, "panel", dev, {"A2+C": a2 | c_, "A2": a2, "C": c_}
    for name, x in (("NIFTY50", s40.nifty()), ("SP500", s40.sp500())):
        yield name, x, "series", x["span"] == "train", {"test half": x["span"] == "test"}
    for name in list(F.SPANS) + list(F.SPANS_M18):
        p, _ = F.market_panel(name, INPUTS)
        yield name, p, "panel", p["span"] == "train", {"test half": p["span"] == "test"}


# --------------------------------------------------------------------------------------------
# R2: fair_forecast_test's forecasts, row by row
# --------------------------------------------------------------------------------------------

def forecast_rows(d, est, train_mask, test_mask, win, scheme, by="symbol", date="date", r2_col="CC"):
    """The forecasts of ``nepsevol.volforecast.fair_forecast_test`` (same calibration, phi grid and
    common sample), returned row by row so that other losses and other inference can be applied."""
    sym, r2 = d[by], d[r2_col]
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
        else:
            kappa = trailing_sum(rv, sym, L, min(60, L)) / trailing_sum(Xv, sym, L, min(60, L))
        parts[name] = (kappa, cur, lr)
    ok_all = fut.notna() & (fut > 0)
    for kappa, cur, lr in parts.values():
        ok_all &= kappa.notna() & cur.notna() & lr.notna() & (kappa * cur > 0) & (lr > 0)
    out = {}
    for name, (kappa, cur, lr) in parts.items():
        def loss(phi, m):
            f = kappa * (phi * cur + (1 - phi) * lr)
            ok = m & ok_all & (f > 0)
            q = fut[ok] / f[ok]
            return q - np.log(q) - 1
        best = min(PHI_GRID, key=lambda p: loss(p, trm).mean())
        f = kappa * (best * cur + (1 - best) * lr)
        ok = tem & ok_all & (f > 0)
        out[name] = pd.DataFrame({"f": f[ok], "fut": fut[ok], "date": d.loc[ok, date]})
    return out


def qlike(x):
    q = x["fut"] / x["f"]
    return q - np.log(q) - 1


def mse(x):
    return (x["fut"] - x["f"]) ** 2


def nw_auto(x):
    """Bartlett lags by the usual rule of thumb, floor(4 (n/100)^(2/9))."""
    n = int(np.isfinite(np.asarray(x, dtype=float)).sum())
    return nw_t(x, lags=max(1, int(4 * (n / 100) ** (2 / 9))))


def inference_rows(out, win, market, span):
    rows = []
    for a, b in PAIRS:
        A, B = out[a], out[b]
        j = A.index.intersection(B.index)
        dq = qlike(A.loc[j]) - qlike(B.loc[j])
        dm = mse(A.loc[j]) - mse(B.loc[j])
        dates = A.loc[j, "date"]
        pq = pd.DataFrame({"x": dq, "date": dates}).groupby("date")["x"].mean().sort_index()
        pm = pd.DataFrame({"x": dm, "date": dates}).groupby("date")["x"].mean().sort_index()
        mid = pq.index[len(pq) // 2]
        rows.append(dict(
            market=market, test_span=span, window=win, estimator=a, reference=b, n=int(len(j)), n_dates=int(len(pq)),
            dQLIKE=float(dq.mean()),
            t_frozen_NW_h=nw_t(pq.to_numpy(), lags=win),
            t_NW_2h=nw_t(pq.to_numpy(), lags=2 * win),
            t_NW_4h=nw_t(pq.to_numpy(), lags=4 * win),
            t_nonoverlapping=nw_auto(pq.to_numpy()[::win]),
            n_nonoverlapping=int(len(pq.to_numpy()[::win])),
            dMSE_rel=float(dm.mean() / mse(B.loc[j]).mean()),
            t_MSE_NW_h=nw_t(pm.to_numpy(), lags=win),
            t_first_half=nw_t(pq[pq.index < mid].to_numpy(), lags=win),
            t_second_half=nw_t(pq[pq.index >= mid].to_numpy(), lags=win)))
    return rows


# --------------------------------------------------------------------------------------------
# R1: level with the same calibration for every estimator
# --------------------------------------------------------------------------------------------

def level_rows(d, est, spans, market, mode):
    sym, r2 = d["symbol"], d["CC"]
    r2w = s40.window_mean(r2, sym)
    raw, cal, cal_lag = {}, {}, {}
    for k, X in est.items():
        wm = s40.window_mean(X, sym)
        if mode == "panel":
            kap = AN.calibration_panel(X, r2, d["date"])
            kd = kap.groupby(d["date"]).first().sort_index()
            kap_lag = d["date"].map(kd.shift(21))
        else:
            kap = AN.calibration_series(X, r2, sym)
            kap_lag = kap.groupby(sym, sort=False).shift(21)
        raw[k], cal[k], cal_lag[k] = wm, kap * wm, kap_lag * wm
    frozen = AN.anam_estimator(d.assign(prev_close=d["pc"]), window=21, mode=mode, prev_close="pc")["var"]
    rows = []
    for span, mask in spans.items():
        ok = s40.inside(mask, sym) & r2w.notna() & frozen.notna()
        for k in est:
            ok &= raw[k].notna() & cal[k].notna() & cal_lag[k].notna()
        den = r2w[ok].mean()
        for k in est:
            rows.append(dict(market=market, span=span, estimator=k, n=int(ok.sum()),
                             raw_ratio=float(raw[k][ok].mean() / den),
                             calibrated_ratio=float(cal[k][ok].mean() / den),
                             calibrated_before_window_ratio=float(cal_lag[k][ok].mean() / den)))
        rows.append(dict(market=market, span=span, estimator="Anam (calibrated, frozen T2)", n=int(ok.sum()),
                         raw_ratio=np.nan, calibrated_ratio=float(frozen[ok].mean() / den),
                         calibrated_before_window_ratio=np.nan))
    return rows


# --------------------------------------------------------------------------------------------
# R4: data checks
# --------------------------------------------------------------------------------------------

def data_rows(d, b, spans, market, mode):
    rows = []
    def add(span, check, value, note=""):
        rows.append(dict(market=market, span=span, check=check, value=float(value), note=note))
    for span, m in spans.items():
        x = d[m]
        add(span, "zero-range share (high = low)", ((x["u"] - x["d"]) == 0).mean())
        add(span, "stale-open share (o = 0)", (x["o"] == 0).mean())
        add(span, "single-price share (open = high = low = close)",
            ((x["u"] == 0) & (x["d"] == 0) & (x["c"] == 0)).mean())
        add(span, "pooled b, whole span, unclipped", (x["o"] * x["r"]).sum() / (x["o"] ** 2).sum())
        add(span, "median trailing b used by the estimator (clipped)", b[m].median(),
            "60 pooled dates" if mode == "panel" else "250 own sessions")
        if mode == "series":
            o, r = d["o"], d["r"]
            num = (o * r).rolling(AN.SERIES_SESSIONS, min_periods=AN.MIN_SERIES_SESSIONS).sum()
            den = (o * o).rolling(AN.SERIES_SESSIONS, min_periods=AN.MIN_SERIES_SESSIONS).sum()
            braw = num / den
            add(span, "median trailing b before clipping", braw[m].median(), "250 own sessions")
            add(span, "share of sessions with trailing b clipped at 1", (braw[m] >= 1).mean())
    return rows


def dhaka_repair_rows(d, market):
    """Dates whose day is 12 or less were repaired (day and month exchanged) in 2009-2021; in the
    2023-2026 panel nothing was repaired, so the same split is a control."""
    rep = d["date"].dt.day <= 12
    rows = []
    for label, m in (("day <= 12 (repaired in 2009-2021)", rep), ("day > 12 (stamped correctly)", ~rep)):
        x = d[m]
        for check, value in (("mean r^2", x["CC"].mean()), ("mean Parkinson", x["P"].mean()),
                             ("median |o|", x["o"].abs().median()), ("share |r| > 0.05", (x["r"].abs() > 0.05).mean()),
                             ("pooled b, unclipped", (x["o"] * x["r"]).sum() / (x["o"] ** 2).sum()),
                             ("dates", x["date"].nunique()),
                             ("dates on a Friday or Saturday", x.loc[x["date"].dt.dayofweek.isin([4, 5]), "date"].nunique())):
            rows.append(dict(market=market, span=label, check=f"date repair: {check}", value=float(value), note=""))
    return rows


def morocco_band_rows():
    """Large moves by band regime BEFORE the band screen: build the panel with no band at all."""
    _, start, end = F.SPANS_M18["Morocco 2012-2026"]
    x = F.read_casablanca(INPUTS / "casablanca" / "stock")
    p, _ = F.build_panel(x, band=1.0, unit=0.01, start=start, end=end)
    edges = [pd.Timestamp(s) if s else None for s, _ in F.MA_BANDS]
    labels = ["10% to 2020-03-16", "4% 2020-03-17 to 2021-10-11", "6% 2021-10-12 to 2023-10-08", "10% from 2023-10-09"]
    rows = []
    for i, lab in enumerate(labels):
        m = pd.Series(True, index=p.index)
        if edges[i] is not None:
            m &= p["date"] >= edges[i]
        if i + 1 < len(edges):
            m &= p["date"] < edges[i + 1]
        r = p.loc[m, "r"].abs()
        for thr in (0.04, 0.06, 0.10):
            rows.append(dict(market="Morocco 2012-2026", span=lab, check=f"band schedule: share |r| > {thr:.2f} + 0.01 (no band screen)",
                             value=float((r > thr + 0.01).mean()), note=f"n = {len(r)}"))
        rows.append(dict(market="Morocco 2012-2026", span=lab, check="band schedule: 99.9th percentile of |r| (no band screen)",
                         value=float(r.quantile(0.999)), note=f"n = {len(r)}"))
    return rows


def vietnam_exchange_rows(d, b):
    """Each ticker's exchange inferred from its 99.5th percentile |r| on the test span (HOSE +-7%,
    HNX +-10%, UPCoM +-15% after 2013); pooled b and share of stock-days by inferred exchange."""
    te = d[d["span"] == "test"]
    q = te.groupby("symbol")["r"].apply(lambda z: z.abs().quantile(0.995) if len(z) >= 250 else np.nan)
    cls = pd.cut(q, [0, 0.072, 0.102, 1.0], labels=["7% limit (HOSE-like)", "10% limit (HNX-like)", "15% limit (UPCoM-like)"])
    te = te.assign(cls=te["symbol"].map(cls))
    rows = []
    for k, g in te.groupby("cls", observed=True):
        rows.append(dict(market="Vietnam 2007-2020", span=f"test half, {k}", check="exchange mix: share of test stock-days",
                         value=float(len(g) / len(te)), note=f"{g['symbol'].nunique()} tickers"))
        rows.append(dict(market="Vietnam 2007-2020", span=f"test half, {k}", check="exchange mix: pooled b, unclipped",
                         value=float((g["o"] * g["r"]).sum() / (g["o"] ** 2).sum()), note=""))
        rows.append(dict(market="Vietnam 2007-2020", span=f"test half, {k}", check="exchange mix: stale-open share (o = 0)",
                         value=float((g["o"] == 0).mean()), note=""))
    return rows


def dhaka_close_rows():
    m = pd.read_csv(INPUTS / "dse_mirror" / "prices.csv", usecols=["symbol", "ltp", "close", "high", "low", "trade"])
    m = m[(m["trade"] > 0) & m["close"].gt(0) & m["ltp"].gt(0)]
    return [dict(market="DSE 2023-2026", span="mirror, 2024-09-30 to 2026-10-08", check="close equals last-trade price (share)",
                 value=float((m["close"] == m["ltp"]).mean()), note=f"n = {len(m)} stock-days with trades"),
            dict(market="DSE 2023-2026", span="mirror, 2024-09-30 to 2026-10-08", check="close inside [low, high] (share)",
                 value=float(((m["close"] >= m["low"]) & (m["close"] <= m["high"])).mean()), note="")]


# --------------------------------------------------------------------------------------------
# R3: multiplicity
# --------------------------------------------------------------------------------------------

RULES = [  # plan, rule, market, span, estimator, reference
    ("M16", "H1 (vs close-to-close)", "NEPSE", "A2+C", "Anam", "CC"),
    ("M16", "H1 (vs Parkinson)", "NEPSE", "A2+C", "Anam", "P"),
    ("M16", "H4", "NIFTY50", "test half", "Anam", "CC"),
    ("M16", "H5", "SP500", "test half", "Anam", "CC"),
    ("M17", "F1", "DSE 2023-2026", "test half", "Anam", "CC"),
    ("M17", "F2", "DSE 2023-2026", "test half", "Anam", "P"),
    ("M17", "F1", "Vietnam 2007-2020", "test half", "Anam", "CC"),
    ("M17", "F2", "Vietnam 2007-2020", "test half", "Anam", "P"),
    ("M17", "F1", "DSE 2009-2021", "test half", "Anam", "CC"),
    ("M17", "F2", "DSE 2009-2021", "test half", "Anam", "P"),
    ("M18", "F1", "Morocco 2012-2026", "test half", "Anam", "CC"),
    ("M18", "F2", "Morocco 2012-2026", "test half", "Anam", "P"),
    ("M18", "V1", "Morocco 2012-2026", "test half", VARIANT, "CC"),
    ("M18", "V2", "Morocco 2012-2026", "test half", VARIANT, "Anam"),
]
VARIANTS = ["t_frozen_NW_h", "t_NW_2h", "t_NW_4h", "t_nonoverlapping", "t_MSE_NW_h", "t_first_half", "t_second_half"]


def holm(p: pd.Series, alpha: float = 0.025) -> pd.Series:
    """Holm step-down adjusted p-values (compare with ``alpha``)."""
    order = p.sort_values().index
    m, run, adj = len(p), 0.0, {}
    for i, k in enumerate(order):
        run = max(run, min(1.0, (m - i) * p[k]))
        adj[k] = run
    return pd.Series(adj).reindex(p.index)


def multiplicity(inf: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for plan, rule, market, span, est, ref in RULES:
        g = inf[(inf.market == market) & (inf.test_span == span) & (inf.window == 5)
                & (inf.estimator == est) & (inf.reference == ref)].iloc[0]
        row = dict(plan=plan, rule=rule, market=market, estimator=est, reference=ref, t=g.t_frozen_NW_h,
                   p_one_sided=0.5 * math.erfc(-g.t_frozen_NW_h / math.sqrt(2)))
        for v in VARIANTS[1:]:
            row[f"beats under {v}"] = bool(g[v] < -1.96)
        rows.append(row)
    out = pd.DataFrame(rows)
    out["frozen verdict: beats"] = out["t"] < -1.96
    out["Holm p within plan"] = pd.concat([holm(g["p_one_sided"]) for _, g in out.groupby("plan", sort=False)])
    out["Holm p across plans"] = holm(out["p_one_sided"])
    out["beats after Holm within plan"] = out["Holm p within plan"] < 0.025
    out["beats after Holm across plans"] = out["Holm p across plans"] < 0.025
    return out


# --------------------------------------------------------------------------------------------

def main() -> None:
    if not INPUTS.exists():
        sys.exit("data/external/frontier/ is missing: see data/external/README.md (scripts 42 and 43 need it too)")
    print("POST HOC RECHECK of the M16-M18 claims (not pre-registered)")
    lev, inf, dat = [], [], []
    for market, d, mode, train, spans in samples():
        t0 = time.time()
        est, b = s40.estimator_set(d, mode)
        scheme = ("pool", AN.POOL_SESSIONS) if mode == "panel" else ("series", AN.SERIES_SESSIONS)
        frozen = pd.read_csv(TAB / FROZEN[market])
        for span, test in spans.items():
            for win in s40.WINDOWS:
                out = forecast_rows(d, est, train, test, win, scheme)
                rows = inference_rows(out, win, market, span)
                fz = frozen[(frozen.market == market) & (frozen.test_span == span) & (frozen.window == win)].set_index("estimator")
                for r in rows:  # the frozen t must be reproduced before any variant is believed
                    ref_t = fz.loc[r["estimator"], f"t_vs_{r['reference']}"] if f"t_vs_{r['reference']}" in fz.columns else np.nan
                    if not np.isfinite(ref_t):
                        ref_t = -fz.loc[r["reference"], f"t_vs_{r['estimator']}"]
                    assert abs(r["t_frozen_NW_h"] - ref_t) < 1e-6, (market, span, win, r["estimator"], r["reference"])
                inf += rows
        lev += level_rows(d, est, spans, market, mode)
        dat += data_rows(d, b, spans, market, mode)
        if market.startswith("DSE"):
            dat += dhaka_repair_rows(d, market)
        if market.startswith("Vietnam"):
            dat += vietnam_exchange_rows(d, b)
        print(f"  {market}: done in {time.time() - t0:.0f}s")
    dat += morocco_band_rows() + dhaka_close_rows()
    lev, inf, dat = pd.DataFrame(lev), pd.DataFrame(inf), pd.DataFrame(dat)
    mult = multiplicity(inf)
    lev.to_csv(TAB / "table117_anam_recheck_level.csv", index=False, float_format=FLOAT_FMT)
    inf.to_csv(TAB / "table118_anam_recheck_inference.csv", index=False, float_format=FLOAT_FMT)
    mult.to_csv(TAB / "table119_anam_recheck_multiplicity.csv", index=False, float_format=FLOAT_FMT)
    dat.to_csv(TAB / "table120_anam_recheck_data.csv", index=False, float_format=FLOAT_FMT)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_colwidth", 70)
    print("\nR1 LEVEL (ratio to the 21-session mean of r^2)")
    print(lev.pivot_table(index="estimator", columns=["market", "span"], values="calibrated_ratio").round(3).to_string())
    print(lev.pivot_table(index="estimator", columns=["market", "span"], values="calibrated_before_window_ratio").round(3).to_string())
    print("\nR2 INFERENCE")
    print(inf.round(2).to_string(index=False))
    print("\nR3 MULTIPLICITY")
    print(mult.round(4).to_string(index=False))
    print("\nR4 DATA")
    print(dat.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
