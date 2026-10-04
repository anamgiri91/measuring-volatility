"""Instrumented calibration of daily-bar volatility estimators: NEPSE and NIFTY 50.

Implements M14_CALIBRATION_ANALYSIS_PLAN.md, frozen before this script was run. Every
specification below is the plan's; nothing here is chosen after seeing a result. The decision
rules are applied mechanically in ``decisions()`` and written to the ledger, table86.

What it estimates, per daily estimator k and relative to the matched proxy OC = ln(C/O)^2:
    beta_k   the CALIBRATION SLOPE -- how much the estimator's conditional mean moves when the
             proxy's does -- identified from volatility persistence with instruments dated t-1;
    delta_k  the ADDITIVE SHARE, mean(X_k)/mean(OC) - beta_k: what the manuscript's ratio holds
             that the slope does not;
and the slope-constrained minimum-variance composite with identified bounds on its efficiency.
See nepsevol.calibration for the theory and scripts/35 for the Monte Carlo validation.

Outputs (output/tables/ and output/figures/):
    table78_calibration_full.csv          H1  full equity sample, every named estimator
    table79_calibration_by_liquidity.csv  H2  by security-level liquidity quintile
    table80_composite_blocks.csv              the empirical best quadratic (block composite)
                                              beside Garman-Klass's Brownian weights
    table81_composite_oos.csv             H3  out-of-sample noise differences
    table82_regimes.csv                   H4/H5 slopes by market-design regime, and differences
    table83_endpoint_moments.csv          H4/H5 overnight-intraday cross moments by regime
    table84_nifty_vix.csv                 H6  NIFTY slopes under lagged vs India VIX instruments
    table85_calibration_sensitivity.csv       transformation, weighting and instrument variants
    table86_m14_decisions.csv                 the frozen decision rules, applied
    fig22_calibration_masking.{pdf,png}       mean ratio against calibration slope, by liquidity
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats as sstats

from nepsevol.calibration import (BLOCKS_OHLCV, GK_VWAP_WEIGHTS, LN2, bar_logs, calibrate,
                                  lagged_means, named_measures, predictable_scale,
                                  quadratic_blocks)
from nepsevol.estimators.range_ import add_rs
from nepsevol.inference import stationary_date_multiplicities
from nepsevol.sample import load_sample
from nepsevol.utils import plotstyle as ps

TAB = ROOT / "output" / "tables"
# Ten significant digits: far beyond any reported precision, and short enough that the last
# floating-point bits -- which differ with BLAS threading -- never reach the frozen CSV.
FLOAT_FMT = "%.10g"
FIG = ROOT / "output" / "figures"
EXT = ROOT / "data" / "external"
TAB.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

N_BOOT = 499
SEED = 20261004
MEAN_BLOCK = 21
MEASURES = ["OC", "P", "GK", "RS", "AddRS", "AP", "GKV"]
# The named composite combines a LINEARLY INDEPENDENT set. Garman-Klass is identically
# 2 ln2 * P - (2 ln2 - 1) * OC, so a set containing all three has a singular covariance and
# unidentified weights; dropping GK leaves the span -- and so the composite -- unchanged, and GK
# still receives its excess-noise and efficiency bound against that composite.
COMPOSITE_NAMED = ["OC", "P", "RS", "AddRS", "AP", "GKV"]
NIFTY_MEASURES = ["OC", "P", "GK", "RS", "AddRS"]
INSTR = ["OC_L1m1", "OC_L1m5", "OC_L1m22", "P_L1m1", "P_L1m5", "P_L1m22"]

# M14: market-design regimes (dates inclusive). 2025-09-18 is excluded from B: the early-close
# session on resumption after the September 2025 halt prints no off-grid closes.
REGIMES = [
    ("A1", "2024-03-04", "2025-03-19", "last-trade close, +/-2% band, +/-10% limit"),
    ("B", "2025-03-20", "2025-09-21", "15-minute VWAP close, +/-2% band, +/-10% limit"),
    ("A2", "2025-09-23", "2026-04-19", "last-trade close, +/-2% band, +/-10% limit"),
    ("C", "2026-04-20", "2026-08-26", "last-trade close, +/-5% band, +/-15% limit"),
]
EXCLUDED_SESSIONS = [pd.Timestamp("2025-09-18")]

# Block representation of each named estimator (for out-of-sample noise comparisons).
THETA = {
    "OC": {"c2": 1.0},
    "P": {"u2": 1 / (4 * LN2), "d2": 1 / (4 * LN2), "ud": -2 / (4 * LN2)},
    "GK": {"u2": 0.5, "d2": 0.5, "ud": -1.0, "c2": -(2 * LN2 - 1)},
    "RS": {"u2": 1.0, "uc": -1.0, "d2": 1.0, "dc": -1.0},
    "AP": {"c2": 2.0, "ac": -6.0, "a2": 6.0},
    "GKV": dict(GK_VWAP_WEIGHTS),
}


def theta_vec(name: str) -> np.ndarray:
    return np.array([THETA[name].get(b, 0.0) for b in BLOCKS_OHLCV])


# --------------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------------

def build_nepse() -> pd.DataFrame:
    df = load_sample(ROOT, "equity").sort_values(["symbol", "date"]).reset_index(drop=True)
    logs = bar_logs(df, prev_close=df["prev_close_adj"])
    blocks = quadratic_blocks(logs, with_vwap=True)
    named = named_measures(blocks)
    named["AddRS"] = add_rs(df)
    # the stored panel carries its own u, d, c; recompute them here from one code path
    df = df.drop(columns=[c for c in df.columns if c in set(logs) | set(blocks) | set(named)])
    out = pd.concat([df, logs, blocks, named], axis=1)
    # consistency with the package's stored estimators (same formulas, independent code path)
    assert np.allclose(out["P"], out["var_pk"], rtol=1e-9, atol=1e-15), "Parkinson mismatch"
    assert np.allclose(out["RS"], out["var_rs"], rtol=1e-9, atol=1e-15), "Rogers-Satchell mismatch"
    nxt = out.groupby("symbol")["o"].shift(-1)
    out["o_next"] = nxt
    out = pd.concat([out, lagged_means(out, ["OC", "P"], windows=(1, 5, 22), skip=1),
                     lagged_means(out, ["OC", "P"], windows=(1, 5, 22), skip=2)], axis=1)
    out["w"] = predictable_scale(out, "P", window=22)
    out["regime"] = None
    for name, a, b, _ in REGIMES:
        m = (out["date"] >= a) & (out["date"] <= b) & ~out["date"].isin(EXCLUDED_SESSIONS)
        out.loc[m, "regime"] = name
    med = out.groupby("symbol")["n_trades"].median()
    q = pd.qcut(med.rank(method="first"), 5, labels=[f"Q{i}" for i in range(1, 6)])
    out["liq_q"] = out["symbol"].map(q).astype(str)
    out["liq_median_trades"] = out["symbol"].map(med)
    return out


def usable(d: pd.DataFrame, cols, instr=INSTR) -> pd.DataFrame:
    return d.dropna(subset=list(cols) + list(instr) + ["w"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------------
# Joint bootstrap: one draw of (security, date) multiplicities shared by every specification,
# so that DIFFERENCES between specifications carry a valid joint interval.
# --------------------------------------------------------------------------------------------

def joint_bootstrap(frame: pd.DataFrame, specs: dict, n_boot: int = N_BOOT, seed: int = SEED,
                    resample_securities: bool = True) -> dict:
    """``specs``: name -> callable(frame, row_weights) -> dict of arrays. Returns name -> list."""
    sec = pd.factorize(frame["symbol"], sort=True)[0]
    dates = pd.factorize(frame["date"], sort=True)[0]
    n_sec, n_date = sec.max() + 1, dates.max() + 1
    rng = np.random.default_rng(seed)
    out = {k: [] for k in specs}
    for _ in range(n_boot):
        ms = (np.bincount(rng.integers(0, n_sec, n_sec), minlength=n_sec).astype(float)
              if resample_securities else np.ones(n_sec))
        md = stationary_date_multiplicities(n_date, rng, MEAN_BLOCK)
        mult = ms[sec] * md[dates]
        for k, f in specs.items():
            try:
                out[k].append(f(frame, mult))
            except (np.linalg.LinAlgError, ZeroDivisionError, ValueError):
                out[k].append(None)
    return out


def ci(draws, lo=2.5, hi=97.5, min_valid=100):
    """Element-wise percentile interval over bootstrap draws.

    Replicates that failed outright (None) are dropped. Within a replicate, an element may be
    NaN BY DESIGN -- a measure outside the composite has no composite weight -- or because the
    replicate drew no session from a short regime; each element's interval is therefore taken
    over that element's own finite draws, and is reported only if at least ``min_valid`` exist.
    Dropping a whole replicate whenever ANY element is NaN would discard every replicate as soon
    as one element is NaN by design, which is the failure this replaces.
    """
    rows = [np.asarray(d, dtype=float) for d in draws if d is not None]
    if not rows:
        return np.nan, np.nan
    a = np.vstack(rows)
    ok = np.isfinite(a).sum(0) >= min_valid
    import warnings
    a = np.where(np.isfinite(a), a, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)     # all-NaN columns are expected
        lo_v = np.where(ok, np.nanpercentile(a, lo, axis=0), np.nan)
        hi_v = np.where(ok, np.nanpercentile(a, hi, axis=0), np.nan)
    return lo_v, hi_v


def calib(frame, mult=None, measures=MEASURES, ref="OC", instr=INSTR, group=None,
          composite_over="default", **kw):
    if composite_over == "default":
        composite_over = COMPOSITE_NAMED if list(measures) == MEASURES else None
    w = frame["w"].to_numpy() * (1.0 if mult is None else mult)
    grp = frame["symbol"] if group is None else group
    return calibrate(frame[measures].to_numpy(), frame[list(instr)].to_numpy(), grp, measures, ref,
                     weights=w, date=frame["date"], composite_over=composite_over, **kw)


def j_pvalue(J, df):
    return np.where(np.isfinite(J), sstats.chi2.sf(J, df), np.nan)


# --------------------------------------------------------------------------------------------
# H1, H2: full sample and liquidity quintiles
# --------------------------------------------------------------------------------------------

def run_full_and_liquidity(d: pd.DataFrame):
    u = usable(d, MEASURES)
    groups = ["All"] + [f"Q{i}" for i in range(1, 6)]
    subsets = {g: (u if g == "All" else u[u["liq_q"] == g].reset_index(drop=True)) for g in groups}
    points = {g: calib(s) for g, s in subsets.items()}

    def make(g):
        def f(frame, mult):
            m = mult if g == "All" else mult[frame["liq_q"].to_numpy() == g]
            s = subsets[g]
            r = calib(s, m, compute_J=False)
            return np.concatenate([r.beta, r.delta, r.ratio, r.weights, r.bounds["eff_lb"]])
        return f
    t0 = time.time()
    boot = joint_bootstrap(u, {g: make(g) for g in groups})
    print(f"  bootstrap (full + quintiles): {time.time() - t0:.0f}s")
    K = len(MEASURES)
    rows = []
    for g in groups:
        r = points[g]
        lo, hi = ci(boot[g])
        s = subsets[g]
        for k, m in enumerate(MEASURES):
            rows.append({
                "group": g, "measure": m, "n_stock_days": r.n_obs, "n_securities": r.n_groups,
                "median_trades": float(s["n_trades"].median()),
                "mean_ratio_var": r.ratio[k], "mean_ratio_lo": lo[2 * K + k], "mean_ratio_hi": hi[2 * K + k],
                "iv_slope": r.beta[k], "iv_slope_lo": lo[k], "iv_slope_hi": hi[k],
                "additive_share": r.delta[k], "additive_share_lo": lo[K + k], "additive_share_hi": hi[K + k],
                "ols_slope": r.ols_slope[k], "corr_with_ref": r.corr_with_ref[k],
                "composite_weight": r.weights[k], "composite_eff_lb": r.bounds["eff_lb"][k],
                "composite_eff_lb_lo": lo[4 * K + k], "composite_eff_lb_hi": hi[4 * K + k],
                "J": r.J[k], "J_df": r.J_df, "J_pvalue": float(j_pvalue(r.J[k], r.J_df)),
                "first_stage_F": r.first_stage_F, "rank1_share": r.rank_one_share,
            })
    tab = pd.DataFrame(rows)
    # H2 difference Q1 - Q5 for every measure, from the joint draws
    diffs = []
    b1 = [x for x in boot["Q1"]]
    b5 = [x for x in boot["Q5"]]
    dd = [None if (a is None or b is None) else (a[:K] - b[:K]) for a, b in zip(b1, b5)]
    lo, hi = ci(dd)
    for k, m in enumerate(MEASURES):
        diffs.append({"measure": m, "slope_Q1_minus_Q5": points["Q1"].beta[k] - points["Q5"].beta[k],
                      "lo": lo[k], "hi": hi[k]})
    return tab, pd.DataFrame(diffs), u


# --------------------------------------------------------------------------------------------
# Block composite (the empirical best quadratic) and H3 out of sample
# --------------------------------------------------------------------------------------------

def run_blocks_and_oos(d: pd.DataFrame):
    blocks = list(BLOCKS_OHLCV)
    u = usable(d, blocks + ["OC", "P"])
    full = calib(u, measures=blocks, ref="c2")
    # Garman-Klass's Brownian-optimal weights in the same block space, expressed on the same
    # normalisation (slope one relative to c2 in THIS sample), for comparison
    gk = theta_vec("GK")
    gk_rescaled = gk / float(gk @ full.beta)
    gkv = theta_vec("GKV")
    gkv_rescaled = gkv / float(gkv @ full.beta)
    tab = pd.DataFrame({"block": blocks, "iv_slope_rel_c2": full.beta,
                        "empirical_weight": full.weights,
                        "gk_brownian_weight_rescaled": gk_rescaled,
                        "gkv_brownian_weight_rescaled": gkv_rescaled,
                        "J": full.J, "J_pvalue": j_pvalue(full.J, full.J_df)})

    # H3: weights from the first half of dates, noise differences on the second half
    dates = np.sort(u["date"].unique())
    cut = dates[len(dates) // 2]
    first = u[u["date"] < cut].reset_index(drop=True)
    second = u[u["date"] >= cut].reset_index(drop=True)
    comp_names = ["OC", "P", "GK", "RS", "GKV", "AP"]
    thetas = {k: theta_vec(k) for k in comp_names}

    def oos(mult1=None, mult2=None):
        r1 = calib(first, mult1, measures=blocks, ref="c2", compute_J=False)
        r2 = calib(second, mult2, measures=blocks, ref="c2", compute_J=False)
        w1 = r1.weights
        S = _sigma_from(second, mult2, blocks)
        b2 = r2.beta
        comp = float(w1 @ S @ w1) / float(w1 @ b2) ** 2
        out = []
        for k in comp_names:
            th = thetas[k]
            out.append(comp - float(th @ S @ th) / float(th @ b2) ** 2)
        scale = float(thetas["OC"] @ S @ thetas["OC"]) / float(thetas["OC"] @ b2) ** 2
        return np.array(out), comp, scale, w1
    point, comp_var, oc_var, w1 = oos()
    first_idx = (u["date"] < cut).to_numpy()

    def f(frame, mult):
        m1, m2 = mult[first_idx], mult[~first_idx]
        dlt, _, _, _ = oos(m1, m2)
        return dlt
    boot = joint_bootstrap(u, {"oos": f})
    lo, hi = ci(boot["oos"])
    oos_tab = pd.DataFrame({"estimator": comp_names, "noise_diff_composite_minus_k": point,
                            "lo": lo, "hi": hi,
                            "relative_to_OC_scaled_var": point / oc_var,
                            "in_decision_set": [k in ("OC", "P", "GK", "RS", "GKV") for k in comp_names]})
    oos_tab.attrs["split_date"] = str(pd.Timestamp(cut).date())
    return tab, oos_tab, full


def _sigma_from(frame, mult, cols):
    """FOD-transformed weighted covariance of ``cols`` -- the Sigma that calibrate() uses."""
    from nepsevol.calibration import forward_orthogonal_deviations, _group_codes
    w = frame["w"].to_numpy() * (1.0 if mult is None else mult)
    order = np.lexsort((frame["date"].to_numpy(), _group_codes(frame["symbol"])))
    X = frame[cols].to_numpy()[order]
    codes = _group_codes(frame["symbol"].to_numpy()[order])
    Xs, keep = forward_orthogonal_deviations(X, codes)
    Xs, ww = Xs[keep], w[order][keep]
    mu = (Xs * ww[:, None]).sum(0) / ww.sum()
    Xc = Xs - mu
    return (Xc * ww[:, None]).T @ Xc / ww.sum()


# --------------------------------------------------------------------------------------------
# H4, H5: market-design regimes
# --------------------------------------------------------------------------------------------

def run_regimes(d: pd.DataFrame):
    u = usable(d[d["regime"].notna()], MEASURES)
    names = [r[0] for r in REGIMES]
    subsets = {g: u[u["regime"] == g].reset_index(drop=True) for g in names}
    points = {g: calib(s) for g, s in subsets.items()}

    def make(g):
        def f(frame, mult):
            m = mult[frame["regime"].to_numpy() == g]
            r = calib(subsets[g], m, compute_J=False)
            return np.concatenate([r.beta, r.delta, r.ratio])
        return f
    boot = joint_bootstrap(u, {g: make(g) for g in names})
    K = len(MEASURES)
    rows = []
    for g, a, b, desc in REGIMES:
        r = points[g]
        lo, hi = ci(boot[g])
        for k, m in enumerate(MEASURES):
            rows.append({"regime": g, "from": a, "to": b, "rules": desc, "measure": m,
                         "n_stock_days": r.n_obs, "iv_slope": r.beta[k], "iv_slope_lo": lo[k],
                         "iv_slope_hi": hi[k], "additive_share": r.delta[k],
                         "additive_share_lo": lo[K + k], "additive_share_hi": hi[K + k],
                         "mean_ratio_var": r.ratio[k], "J": r.J[k],
                         "J_pvalue": float(j_pvalue(r.J[k], r.J_df)),
                         "first_stage_F": r.first_stage_F})
    tab = pd.DataFrame(rows)
    diffs = []
    for lab, g1, g0 in [("B - A1", "B", "A1"), ("B - A2", "B", "A2"), ("C - A2", "C", "A2"),
                        ("A2 - A1", "A2", "A1")]:
        dd = [None if (x is None or y is None) else (x[:K] - y[:K]) for x, y in zip(boot[g1], boot[g0])]
        lo, hi = ci(dd)
        for k, m in enumerate(MEASURES):
            diffs.append({"contrast": lab, "measure": m,
                          "slope_difference": points[g1].beta[k] - points[g0].beta[k],
                          "lo": lo[k], "hi": hi[k]})
    return tab, pd.DataFrame(diffs)


def run_endpoint_moments(d: pd.DataFrame):
    """E[o_t c_t]/E[P] and E[c_t o_t+1]/E[P] by regime, and the band-pinned share of opens."""
    x = d[d["regime"].notna()].copy()
    x["next_regime"] = x.groupby("symbol")["regime"].shift(-1)
    x["oc_prod"] = x["o"] * x["c"]
    x["co_next"] = np.where(x["next_regime"] == x["regime"], x["c"] * x["o_next"], np.nan)
    band = np.where(x["date"] >= pd.Timestamp("2026-04-20"), 0.05, 0.02)
    # at the band: within 0.1 percentage point of ln(1 + band), as in the descriptive check of M14
    x["pinned"] = np.where(x["o"].notna(), (x["o"].abs() >= np.log(1 + band) - 0.001), np.nan)
    names = [r[0] for r in REGIMES]

    def stat(frame, mult):
        out = []
        for g in names:
            m = (frame["regime"] == g).to_numpy()
            ww = mult[m]
            f = frame[m]
            a = f["oc_prod"].to_numpy(); b = f["co_next"].to_numpy(); p = f["P"].to_numpy()
            ok1 = np.isfinite(a) & np.isfinite(p)
            ok2 = np.isfinite(b) & np.isfinite(p)
            r1 = (ww[ok1] * a[ok1]).sum() / (ww[ok1] * p[ok1]).sum()
            r2 = (ww[ok2] * b[ok2]).sum() / (ww[ok2] * p[ok2]).sum()
            pin = f["pinned"].to_numpy(); okp = np.isfinite(pin)
            r3 = (ww[okp] * pin[okp]).sum() / ww[okp].sum()
            out += [r1, r2, r3]
        return np.array(out)
    point = stat(x, np.ones(len(x)))
    boot = joint_bootstrap(x, {"m": stat})
    lo, hi = ci(boot["m"])
    rows = []
    for i, g in enumerate(names):
        for j, lab in enumerate(["E[o_t c_t]/E[P]", "E[c_t o_t+1]/E[P]", "share of opens at the band"]):
            idx = 3 * i + j
            rows.append({"regime": g, "moment": lab, "value": point[idx], "lo": lo[idx], "hi": hi[idx]})
    tab = pd.DataFrame(rows)
    diffs = []
    arr = np.array([b for b in boot["m"] if b is not None])
    for lab, g1, g0 in [("B - A1", "B", "A1"), ("B - A2", "B", "A2"), ("C - A2", "C", "A2")]:
        i1, i0 = names.index(g1), names.index(g0)
        for j, mlab in enumerate(["E[o_t c_t]/E[P]", "E[c_t o_t+1]/E[P]", "share of opens at the band"]):
            dv = arr[:, 3 * i1 + j] - arr[:, 3 * i0 + j]
            # a replicate can draw no session from a short regime (C has ~85); such replicates are
            # undefined for that regime and are dropped, as ci() does for every other statistic
            dv = dv[np.isfinite(dv)]
            diffs.append({"contrast": lab, "moment": mlab,
                          "difference": point[3 * i1 + j] - point[3 * i0 + j],
                          "lo": np.percentile(dv, 2.5), "hi": np.percentile(dv, 97.5),
                          "n_valid_replicates": int(len(dv))})
    return tab, pd.DataFrame(diffs)


# --------------------------------------------------------------------------------------------
# H6: NIFTY 50 with India VIX as an external instrument
# --------------------------------------------------------------------------------------------

def build_nifty() -> pd.DataFrame:
    nif = pd.read_csv(EXT / "nifty50.csv", parse_dates=["Date"])
    nif.columns = [c.lower() for c in nif.columns]
    nif = nif[(nif[["open", "high", "low", "close"]] > 0).all(axis=1)].sort_values("date").reset_index(drop=True)
    nif["symbol"] = "NIFTY50"
    logs = bar_logs(nif, prev_close=nif["close"].shift(1))
    blocks = quadratic_blocks(logs, with_vwap=False)
    named = named_measures(blocks)
    named["AddRS"] = add_rs(nif)
    out = pd.concat([nif, logs, blocks, named], axis=1)
    out = out.loc[:, ~out.columns.duplicated()]
    out = pd.concat([out, lagged_means(out, ["OC", "P"], windows=(1, 5, 22), skip=1)], axis=1)
    vix = pd.read_csv(EXT / "india_vix.csv", parse_dates=["Date"]).rename(columns={"Date": "date"})
    vix["vix_var"] = (vix["India_VIX"] / 100.0) ** 2 / 252.0     # daily variance units
    out = out.merge(vix[["date", "vix_var"]], on="date", how="left")
    # VIX observed at the close of t-1 and its trailing five-session mean, both F_{t-1}
    out["VIX_L1m1"] = out["vix_var"].shift(1)
    out["VIX_L1m5"] = out["vix_var"].shift(1).rolling(5, min_periods=5).mean()
    out["w"] = predictable_scale(out, "P", window=22)
    return out


def run_nifty(nif: pd.DataFrame):
    sets = {"(i) lagged OC, P": INSTR, "(ii) India VIX only": ["VIX_L1m1", "VIX_L1m5"],
            "(iii) both": INSTR + ["VIX_L1m1", "VIX_L1m5"]}
    allinst = INSTR + ["VIX_L1m1", "VIX_L1m5"]
    results = []
    for sample, frame in [("full (incl. 2012-10-05)", nif),
                          ("excl. 2012-10-05", nif[nif["date"] != pd.Timestamp("2012-10-05")])]:
        u = frame.dropna(subset=NIFTY_MEASURES + allinst + ["w"]).reset_index(drop=True)
        points = {s: calib(u, measures=NIFTY_MEASURES, instr=ins) for s, ins in sets.items()}

        def make(ins):
            return lambda fr, mult: calib(u, mult, measures=NIFTY_MEASURES, instr=ins, compute_J=False).beta
        boot = joint_bootstrap(u, {s: make(ins) for s, ins in sets.items()}, resample_securities=False)
        for s in sets:
            lo, hi = ci(boot[s])
            r = points[s]
            for k, m in enumerate(NIFTY_MEASURES):
                results.append({"sample": sample, "instruments": s, "measure": m,
                                "n_sessions": r.n_obs, "from": str(u["date"].min().date()),
                                "to": str(u["date"].max().date()),
                                "iv_slope": r.beta[k], "lo": lo[k], "hi": hi[k],
                                "additive_share": r.delta[k], "mean_ratio_var": r.ratio[k],
                                "J": r.J[k], "J_pvalue": float(j_pvalue(r.J[k], r.J_df)),
                                "first_stage_F": r.first_stage_F})
        dd = [None if (a is None or b is None) else a - b
              for a, b in zip(boot["(i) lagged OC, P"], boot["(ii) India VIX only"])]
        lo, hi = ci(dd)
        for k, m in enumerate(NIFTY_MEASURES):
            results.append({"sample": sample, "instruments": "difference (i) - (ii)", "measure": m,
                            "n_sessions": points["(i) lagged OC, P"].n_obs,
                            "iv_slope": points["(i) lagged OC, P"].beta[k] - points["(ii) India VIX only"].beta[k],
                            "lo": lo[k], "hi": hi[k]})
    return pd.DataFrame(results)


# --------------------------------------------------------------------------------------------
# Sensitivity (reported, not decisive)
# --------------------------------------------------------------------------------------------

def run_sensitivity(d: pd.DataFrame):
    instr2 = [c.replace("_L1m", "_L2m") for c in INSTR]
    u = usable(d, MEASURES, INSTR + instr2)
    specs = {
        "primary: FOD, level instruments, weighted": dict(),
        "whole-sample within transformation": dict(transform="within"),
        "unweighted": dict(unweighted=True),
        "past-demeaned instruments": dict(instruments="past"),
        "instruments lagged two sessions": dict(instr=instr2),
    }
    rows = []
    for lab, kw in specs.items():
        kw = dict(kw)
        instr = kw.pop("instr", INSTR)
        if kw.pop("unweighted", False):
            uu = u.assign(w=1.0)
        else:
            uu = u
        r = calib(uu, instr=instr, compute_J=False, **kw)
        for k, m in enumerate(MEASURES):
            rows.append({"specification": lab, "measure": m, "iv_slope": r.beta[k],
                         "additive_share": r.delta[k], "mean_ratio_var": r.ratio[k],
                         "first_stage_F": r.first_stage_F, "n_stock_days": r.n_obs})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Decision ledger: the frozen rules, applied mechanically
# --------------------------------------------------------------------------------------------

def decisions(full, qdiff, oos, regd, endd, nifty):
    rows = []
    a = full[full["group"] == "All"].set_index("measure")
    for k in ["P", "GK", "RS"]:
        r = a.loc[k]
        if r.iv_slope_hi < 1 and r.additive_share_lo > 0:
            v = "masking"
        elif r.iv_slope_lo > 1:
            v = "amplification"
        elif r.iv_slope_lo <= 1 <= r.iv_slope_hi:
            v = "no detectable attenuation"
        else:
            v = "attenuation without a detectable additive share"
        rows.append({"hypothesis": "H1", "statistic": f"slope and additive share, {k}",
                     "estimate": f"slope {r.iv_slope:.3f} [{r.iv_slope_lo:.3f}, {r.iv_slope_hi:.3f}]; "
                                 f"additive {r.additive_share:.3f} [{r.additive_share_lo:.3f}, {r.additive_share_hi:.3f}]",
                     "verdict": v})
    q = qdiff.set_index("measure").loc["P"]
    v = "gradient" if q.hi < 0 else ("reversed" if q.lo > 0 else "not detected")
    rows.append({"hypothesis": "H2", "statistic": "slope P, Q1 - Q5",
                 "estimate": f"{q.slope_Q1_minus_Q5:.3f} [{q.lo:.3f}, {q.hi:.3f}]", "verdict": v})
    for _, r in oos[oos["in_decision_set"]].iterrows():
        v = "improvement" if r.hi < 0 else "not established"
        rows.append({"hypothesis": "H3", "statistic": f"out-of-sample noise difference, composite - {r.estimator}",
                     "estimate": f"{r.noise_diff_composite_minus_k:.3e} [{r.lo:.3e}, {r.hi:.3e}]", "verdict": v})
    p = regd[regd["measure"] == "P"].set_index("contrast")
    hits = sum(p.loc[c, "lo"] > 0 for c in ["B - A1", "B - A2"])
    v = {2: "confirmed", 1: "partial", 0: "not detected"}[int(hits)]
    rows.append({"hypothesis": "H4", "statistic": "slope P: B - A1 and B - A2 (predicted > 0)",
                 "estimate": "; ".join(f"{c} {p.loc[c, 'slope_difference']:.3f} [{p.loc[c, 'lo']:.3f}, {p.loc[c, 'hi']:.3f}]"
                                       for c in ["B - A1", "B - A2"]), "verdict": v})
    e = endd.set_index(["contrast", "moment"])
    for c in ["B - A1", "B - A2"]:
        r = e.loc[(c, "E[c_t o_t+1]/E[P]")]
        rows.append({"hypothesis": "H4 (reported)", "statistic": f"E[c_t o_t+1]/E[P], {c} (predicted > 0)",
                     "estimate": f"{r.difference:.4f} [{r.lo:.4f}, {r.hi:.4f}]",
                     "verdict": "as predicted" if r.lo > 0 else ("opposite" if r.hi < 0 else "not detected")})
    r = p.loc["C - A2"]
    rows.append({"hypothesis": "H5", "statistic": "slope P: C - A2 (predicted > 0)",
                 "estimate": f"{r.slope_difference:.3f} [{r.lo:.3f}, {r.hi:.3f}]",
                 "verdict": "confirmed" if r.lo > 0 else ("opposite" if r.hi < 0 else "not detected")})
    r = e.loc[("C - A2", "E[o_t c_t]/E[P]")]
    rows.append({"hypothesis": "H5 (reported)", "statistic": "E[o_t c_t]/E[P], C - A2 (predicted < 0)",
                 "estimate": f"{r.difference:.4f} [{r.lo:.4f}, {r.hi:.4f}]",
                 "verdict": "as predicted" if r.hi < 0 else ("opposite" if r.lo > 0 else "not detected")})
    for sample in nifty["sample"].unique():
        dd = nifty[(nifty["sample"] == sample) & (nifty["instruments"] == "difference (i) - (ii)")]
        ok = ((dd["lo"] <= 0) & (dd["hi"] >= 0)).all()
        rows.append({"hypothesis": "H6", "statistic": f"NIFTY slopes, lagged minus VIX instruments ({sample})",
                     "estimate": "; ".join(f"{m} {s:+.3f} [{l:+.3f}, {h:+.3f}]" for m, s, l, h in
                                           zip(dd.measure, dd.iv_slope, dd.lo, dd.hi)),
                     "verdict": "corroborated" if ok else "failed overidentification"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------------------------

def figure(full: pd.DataFrame) -> None:
    ps.apply()
    names = {"P": "Parkinson", "GK": "Garman-Klass", "RS": "Rogers-Satchell"}
    groups = ["Q1", "Q2", "Q3", "Q4", "Q5", "All"]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 3.1), sharey=True)
    x = np.arange(len(groups))
    handles = []
    for ax, (k, lab) in zip(axes, names.items()):
        col, _, mk = ps.STYLE[lab]
        t = full[full["measure"] == k].set_index("group").loc[groups]
        ax.axhline(1.0, color=ps.INK_MUTED, lw=0.8, zorder=1)
        h1 = ax.errorbar(x - 0.13, t["mean_ratio_var"],
                         yerr=[t["mean_ratio_var"] - t["mean_ratio_lo"], t["mean_ratio_hi"] - t["mean_ratio_var"]],
                         fmt="o", mfc=ps.SURFACE, mec=ps.INK_SOFT, ecolor=ps.INK_MUTED, ms=5, lw=0.9,
                         capsize=0, zorder=3)
        h2 = ax.errorbar(x + 0.13, t["iv_slope"],
                         yerr=[t["iv_slope"] - t["iv_slope_lo"], t["iv_slope_hi"] - t["iv_slope"]],
                         fmt=mk, color=col, ecolor=col, ms=5, lw=1.1, capsize=0, zorder=4)
        handles.append(h2)
        ax.set_xticks(x, ["Q1\nthin", "Q2", "Q3", "Q4", "Q5\nactive", "All"])
        ps.finish(ax, title=lab)
    axes[0].set_ylabel("Relative to the proxy\n(variance scale)")
    fig.tight_layout(rect=[0, 0.09, 1, 0.80])
    fig.text(0.0, 0.995, "Ratios and calibration slopes are different quantities", ha="left", va="top",
             fontsize=10.5, fontweight="bold", color=ps.INK)
    fig.text(0.0, 0.925, "Mean ratio to the open-to-close proxy against the instrumented calibration slope,\n"
             "by security-level liquidity quintile; 95% stationary block-bootstrap intervals",
             ha="left", va="top", fontsize=8, color=ps.INK_SOFT)
    fig.legend([h1] + handles, ["mean ratio to proxy (all panels)", "calibration slope, Parkinson",
                                "calibration slope, Garman-Klass", "calibration slope, Rogers-Satchell"],
               loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.0), handletextpad=0.3,
               columnspacing=1.2, fontsize=7.5)
    for e in ("pdf", "png"):
        fig.savefig(FIG / f"fig22_calibration_masking.{e}")
    plt.close(fig)


# --------------------------------------------------------------------------------------------

def main() -> None:
    t0 = time.time()
    print("Instrumented calibration (M14 plan, frozen)")
    d = build_nepse()
    print(f"  NEPSE equity panel: {len(d):,} stock-days, {d.symbol.nunique()} securities")

    full, qdiff, _ = run_full_and_liquidity(d)
    full[full.group == "All"].to_csv(TAB / "table78_calibration_full.csv", index=False, float_format=FLOAT_FMT)
    full[full.group != "All"].to_csv(TAB / "table79_calibration_by_liquidity.csv", index=False, float_format=FLOAT_FMT)
    qdiff.to_csv(TAB / "table79b_slope_gradient.csv", index=False, float_format=FLOAT_FMT)
    print(full[full.group == "All"][["measure", "mean_ratio_var", "iv_slope", "iv_slope_lo", "iv_slope_hi",
                                      "additive_share", "ols_slope", "corr_with_ref", "J_pvalue"]]
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"  [{time.time() - t0:.0f}s]")

    blk, oos, _ = run_blocks_and_oos(d)
    blk.to_csv(TAB / "table80_composite_blocks.csv", index=False, float_format=FLOAT_FMT)
    oos.to_csv(TAB / "table81_composite_oos.csv", index=False, float_format=FLOAT_FMT)
    print(blk.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"  out-of-sample split at {oos.attrs['split_date']}")
    print(oos.to_string(index=False, float_format=lambda v: f"{v:.4g}"))
    print(f"  [{time.time() - t0:.0f}s]")

    reg, regd = run_regimes(d)
    reg.to_csv(TAB / "table82_regimes.csv", index=False, float_format=FLOAT_FMT)
    regd.to_csv(TAB / "table82b_regime_differences.csv", index=False, float_format=FLOAT_FMT)
    print(regd[regd.measure.isin(["P", "GK", "RS", "OC"])].to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"  [{time.time() - t0:.0f}s]")

    endm, endd = run_endpoint_moments(d)
    endm.to_csv(TAB / "table83_endpoint_moments.csv", index=False, float_format=FLOAT_FMT)
    endd.to_csv(TAB / "table83b_endpoint_differences.csv", index=False, float_format=FLOAT_FMT)
    print(endm.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"  [{time.time() - t0:.0f}s]")

    nif = build_nifty()
    nt = run_nifty(nif)
    nt.to_csv(TAB / "table84_nifty_vix.csv", index=False, float_format=FLOAT_FMT)
    print(nt.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"  [{time.time() - t0:.0f}s]")

    sens = run_sensitivity(d)
    sens.to_csv(TAB / "table85_calibration_sensitivity.csv", index=False, float_format=FLOAT_FMT)
    print(sens[sens.measure.isin(["P", "GK", "RS"])].to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    dec = decisions(full, qdiff, oos, regd, endd, nt)
    dec.to_csv(TAB / "table86_m14_decisions.csv", index=False, float_format=FLOAT_FMT)
    print("\nM14 decisions (frozen rules, applied mechanically)")
    print(dec.to_string(index=False))

    figure(full)
    print(f"\ndone in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
