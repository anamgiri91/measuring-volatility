"""M15: what the opening price measures, and what NEPSE's April 2026 band reform did to it.

Implements M15_OPENING_PRICE_ANALYSIS_PLAN.md, frozen and pushed (commit 6b71646) before this
script was written; the simulation checks of the statistics it uses were committed next
(f2699aa, tests/test_opening_price.py). Every specification here is the plan's. The decision
rules are applied mechanically in ``decisions()`` and written to the ledger, table96.

The central statistic is the unbiasedness coefficient of the open for the close,
``b = E[o r] / E[o^2]`` with ``o = ln(O/PC)`` and ``r = ln(C/PC)`` (nepsevol.opening): b < 1 when
the open overreacts and the session undoes part of it, b > 1 when the open underreacts and the
session completes it. Every interval comes from ONE joint bootstrap -- stationary blocks of dates
(mean 21) x i.i.d. securities, 499 replicates, seed 20261007 -- shared by every statistic, so
differences, DiDs and changes carry valid joint intervals.

Outputs (output/tables/ and output/figures/):
    table89_m15_unbiasedness.csv          b and the other opening moments by regime, by zone x
                                          regime (H9) and by liquidity quintile x regime
    table90_m15_event_window.csv          H7: the pre, inter-reform and post windows and the jump
    table90b_m15_placebo_breaks.csv       H7: the jump at every placebo date
    table91_m15_monthly.csv               b and E[o c]/E[P] by calendar month
    table92_m15_dose_response.csv         H8: b by intensity group x regime, DiD and placebo
    table93_m15_estimator_evaluation.csv  H10: ratios to the proxy and to the noise-robust kernel
    table94_m15_yang_zhang.csv            H11: Yang-Zhang over Var(r) and the decomposition
    table95_m15_nifty.csv                 H12: the external contrast
    table96_m15_decisions.csv             the frozen rules, applied
    fig23_opening_price.{pdf,png}
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nepsevol import opening as op
from nepsevol.estimators import range_ as R
from nepsevol.utils import plotstyle as ps

TAB = ROOT / "output" / "tables"
FIG = ROOT / "output" / "figures"
FLOAT_FMT = "%.10g"
SEED = 20261007
EXCLUDED = pd.Timestamp("2025-09-18")
REGIMES = ["A1", "B", "A2", "C"]
MEASURES = ["OC", "P", "GK", "RS", "AddRS"]
RULE_DATES = [("2025-03-20", "15-minute VWAP close"), ("2025-09-23", "last-trade close again"),
              ("2026-04-06", "Monday-Friday week"), ("2026-04-20", "band +/-2% to +/-5%")]

_spec = importlib.util.spec_from_file_location("s34", ROOT / "scripts" / "34_instrumented_calibration.py")
s34 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s34)


# --------------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------------

def build() -> pd.DataFrame:
    d = s34.build_nepse()                      # sorted by symbol, date; o from prev_close_adj
    co = op.opening_coordinates(d, d["prev_close_adj"])
    assert np.allclose(co["o"], d["o"], equal_nan=True) and np.allclose(co["a"], d["a"], equal_nan=True)
    d["r"], d["g"], d["q"] = co["r"], co["g"], co["q"]
    d["band"] = op.band_in_force(d["date"])
    d["zone"] = op.zone_labels(d["g"], d["band"])
    # the noise-robust kernel exactly as table88 builds it (scripts/36::e2_noise_share): the next
    # row's regime is looked up within the regime-labelled rows, and o_next is used only when it
    # is the same regime
    x = d[d["regime"].notna()]
    nr = x.groupby("symbol")["regime"].shift(-1)
    same = pd.Series(False, index=d.index)
    same.loc[x.index] = (nr == x["regime"]).to_numpy()
    d["K"] = np.where(d["regime"].notna(),
                      d["c"] ** 2 + d["o"] * d["c"] + np.where(same, d["c"] * d["o_next"], np.nan),
                      np.nan)
    return add_yang_zhang(d)


def add_yang_zhang(d: pd.DataFrame) -> pd.DataFrame:
    """Rolling 21-session Yang-Zhang (package code path), Var(r) and the two terms of the gap."""
    code = d["regime"].map({g: i for i, g in enumerate(REGIMES)}).astype(float)
    parts = []
    for _, g in d.groupby("symbol", sort=False):
        comp = op.yang_zhang_components(g["o"], g["c"], g["RS"])
        comp["yz_pkg"] = (R.yang_zhang(g, 21, prev_close=g["prev_close_adj"]) if len(g) > 22
                          else pd.Series(np.nan, index=g.index))
        rc = code.loc[g.index]
        inside = (rc.rolling(21).min() == rc.rolling(21).max()) & rc.rolling(21).count().eq(21)
        comp["yz_regime"] = np.where(inside, rc, np.nan)
        parts.append(comp)
    y = pd.concat(parts).reindex(d.index)
    ok = y["yz"].notna() & y["yz_pkg"].notna()
    assert np.allclose(y.loc[ok, "yz"], y.loc[ok, "yz_pkg"], rtol=1e-9, atol=1e-15), "YZ code paths differ"
    ok2 = y[["yz", "var_r", "rs_term", "cov_term"]].notna().all(axis=1)
    gap = (y["yz"] - y["var_r"])[ok2]
    assert np.allclose(gap, (y["rs_term"] + y["cov_term"])[ok2], rtol=1e-7, atol=1e-13), "YZ identity"
    for c_ in ["yz", "var_r", "rs_term", "cov_term", "yz_regime"]:
        d[c_] = y[c_]
    d["yz_gap"] = d["yz"] - d["var_r"]
    return d


# --------------------------------------------------------------------------------------------
# One registry of ratio-of-sums statistics, evaluated under shared bootstrap multiplicities
# --------------------------------------------------------------------------------------------

class Registry:
    """Ratios sum(m * num) / sum(m * den) over fixed row sets, plus derived linear contrasts."""

    def __init__(self, n_rows: int):
        self.n = n_rows
        self.names, self._idx, self._num, self._den = [], [], [], []
        self.derived = []                       # (name, {base_name: coefficient})

    def ratio(self, name, num, den, mask=None):
        num = np.asarray(num, dtype=float)
        den = np.asarray(den, dtype=float)
        ok = np.isfinite(num) & np.isfinite(den)
        if mask is not None:
            ok &= np.asarray(mask, dtype=bool)
        idx = np.flatnonzero(ok)
        assert name not in self.names, name
        self.names.append(name)
        self._idx.append(idx)
        self._num.append(num[idx])
        self._den.append(den[idx])
        return name

    def b(self, name, d, mask=None):
        o, r = d["o"].to_numpy(), d["r"].to_numpy()
        return self.ratio(name, o * r, o * o, mask)

    def contrast(self, name, weights: dict):
        self.derived.append((name, weights))
        return name

    def all_names(self):
        return self.names + [n for n, _ in self.derived]

    def evaluate(self, mult=None) -> np.ndarray:
        base = []
        for idx, num, den in zip(self._idx, self._num, self._den):
            m = np.ones(len(idx)) if mult is None else mult[idx]
            dd = float((m * den).sum())
            base.append(float((m * num).sum()) / dd if dd != 0 else np.nan)
        pos = {n: i for i, n in enumerate(self.names)}
        der = [sum(w * base[pos[k]] for k, w in ws.items()) for _, ws in self.derived]
        return np.array(base + der)


def diff(reg, name, a, b_):
    return reg.contrast(name, {a: 1.0, b_: -1.0})


def did(reg, name, hi_post, hi_pre, lo_post, lo_pre):
    return reg.contrast(name, {hi_post: 1.0, hi_pre: -1.0, lo_post: -1.0, lo_pre: 1.0})


# --------------------------------------------------------------------------------------------
# Register every statistic of the plan
# --------------------------------------------------------------------------------------------

def register(d: pd.DataFrame) -> tuple[Registry, dict]:
    reg = Registry(len(d))
    meta = {}
    o, c = d["o"].to_numpy(), d["c"].to_numpy()
    P = d["P"].to_numpy()
    defined = np.isfinite(o) & np.isfinite(c)
    regime = d["regime"].to_numpy()
    zone = d["zone"].to_numpy()
    date = d["date"].to_numpy()
    one = np.ones(len(d))

    # ---- by regime: b, moments, timing split, shares ----------------------------------------
    for g in REGIMES:
        m = defined & (regime == g)
        reg.b(f"b|{g}", d, m)
        reg.ratio(f"oc_P|{g}", o * c, P, m)
        reg.ratio(f"oa_o2|{g}", o * d["a"].to_numpy(), o * o, m)
        reg.ratio(f"oq_o2|{g}", o * d["q"].to_numpy(), o * o, m)
        reg.ratio(f"stale|{g}", (zone == "stale").astype(float), one, m)
        reg.ratio(f"pinned|{g}", (zone == "pinned").astype(float), one, m)
        for z in ["interior", "old-band zone", "pinned"]:
            mz = m & (zone == z)
            if mz.sum() >= 200:
                reg.b(f"b|{g}|{z}", d, mz)
    for a_, b_ in [("C", "A2"), ("B", "A1"), ("A2", "A1")]:
        diff(reg, f"db|{a_}-{b_}", f"b|{a_}", f"b|{b_}")

    # ---- H9 -----------------------------------------------------------------------------------
    meta["H9"] = {"a": "b|A2|pinned", "b": "b|C|old-band zone",
                  "c": diff(reg, "db_interior|C-A2", "b|C|interior", "b|A2|interior")}
    first5 = pd.DatetimeIndex(np.sort(d.loc[d["date"] >= op.BAND_REFORM, "date"].unique()))[:5]
    late_c = defined & (regime == "C") & ~d["date"].isin(first5).to_numpy()
    reg.b("b|C|old-band zone|excl first 5", d, late_c & (zone == "old-band zone"))
    reg.b("b|C|interior|excl first 5", d, late_c & (zone == "interior"))

    # ---- liquidity quintile x regime -------------------------------------------------------------
    liq = d["liq_q"].to_numpy()
    for q in [f"Q{i}" for i in range(1, 6)]:
        for g in REGIMES:
            reg.b(f"b|{q}|{g}", d, defined & (liq == q) & (regime == g))

    # ---- H7: event windows ---------------------------------------------------------------------
    cal = pd.DatetimeIndex(np.sort(d["date"].unique()))
    cal = cal[cal != EXCLUDED]
    ew = op.event_windows(cal, length=40)
    post_late = cal[cal >= op.BAND_REFORM][5:45]
    meta["windows"] = {"pre": ew["pre"], "gap": ew["gap"], "post": ew["post"], "post_late": post_late}
    Kv, OCv = d["K"].to_numpy(), d["OC"].to_numpy()
    for lab, dates in meta["windows"].items():
        m = defined & d["date"].isin(dates).to_numpy()
        reg.b(f"b|win:{lab}", d, m)
        reg.ratio(f"oc_P|win:{lab}", o * c, P, m)
        reg.ratio(f"K_OC|win:{lab}", Kv, OCv, m & np.isfinite(Kv))
    meta["H7"] = diff(reg, "db|win:post-pre", "b|win:post", "b|win:pre")
    diff(reg, "db|win:post_late-pre", "b|win:post_late", "b|win:pre")
    diff(reg, "db|win:gap-pre", "b|win:gap", "b|win:pre")

    # ---- monthly -------------------------------------------------------------------------------
    month = d["date"].dt.to_period("M").astype(str).to_numpy()
    meta["months"] = sorted(set(month[defined & (d["date"] != EXCLUDED).to_numpy()]))
    for mo in meta["months"]:
        m = defined & (month == mo) & (d["date"] != EXCLUDED).to_numpy()
        reg.b(f"b|month:{mo}", d, m)
        reg.ratio(f"oc_P|month:{mo}", o * c, P, m)

    # ---- H8: dose-response ---------------------------------------------------------------------
    pre_rows = d[d["regime"].isin(["A1", "B"]) & d["o"].notna()]
    pin = (pre_rows["g"].abs() >= op.OLD_BAND - op.PIN_TOL).groupby(pre_rows["symbol"])
    share = pin.mean()[pin.size() >= 60]
    groups = {"terciles": op.intensity_groups(share, 3),
              "halves": op.intensity_groups(share, 2, prefix="half")}
    a2_rows = d[(d["regime"] == "A2") & d["o"].notna()]
    pin2 = (a2_rows["g"].abs() >= op.OLD_BAND - op.PIN_TOL).groupby(a2_rows["symbol"])
    share2 = pin2.mean()[pin2.size() >= 60]
    groups["terciles, intensity measured in A2"] = op.intensity_groups(share2, 3)
    meta["intensity"] = {"share": share, "share_A2": share2, "groups": groups}
    a2_cal = cal[(cal >= pd.Timestamp("2025-09-23")) & (cal <= pd.Timestamp("2026-04-19"))]
    a2_cal = a2_cal[~a2_cal.isin(ew["gap"])]
    half = a2_cal[len(a2_cal) // 2]
    meta["placebo_split"] = half
    h1 = d["date"].isin(a2_cal[a2_cal < half]).to_numpy()
    h2 = d["date"].isin(a2_cal[a2_cal >= half]).to_numpy()
    sym = d["symbol"]
    meta["H8"] = {}
    for gname, grp in groups.items():
        lab = sym.map(grp).fillna("").to_numpy()
        hi, lo = (("T3", "T1") if gname.startswith("terciles") else ("half2", "half1"))
        for t in sorted(set(grp)):
            for g in ["A2", "C"]:
                reg.b(f"b|{gname}|{t}|{g}", d, defined & (lab == t) & (regime == g))
            reg.b(f"b|{gname}|{t}|C excl first 5", d, late_c & (lab == t))
            reg.b(f"b|{gname}|{t}|A2 first half", d, defined & (lab == t) & h1)
            reg.b(f"b|{gname}|{t}|A2 second half", d, defined & (lab == t) & h2)
        k = f"b|{gname}|"
        meta["H8"][gname] = {
            "did": did(reg, f"DiD|{gname}", k + f"{hi}|C", k + f"{hi}|A2", k + f"{lo}|C", k + f"{lo}|A2"),
            "placebo": did(reg, f"placebo DiD|{gname}", k + f"{hi}|A2 second half",
                           k + f"{hi}|A2 first half", k + f"{lo}|A2 second half", k + f"{lo}|A2 first half"),
            "did_late": did(reg, f"DiD excl first 5|{gname}", k + f"{hi}|C excl first 5", k + f"{hi}|A2",
                            k + f"{lo}|C excl first 5", k + f"{lo}|A2"),
            "hi": hi, "lo": lo,
        }

    # ---- H10: estimator evaluation against OC and against K, on rows where K is defined -------
    kdef = np.isfinite(Kv) & (pd.Series(regime).notna().to_numpy())
    for g in REGIMES:
        m = kdef & (regime == g)
        reg.ratio(f"nu|{g}", OCv - Kv, OCv, m)
        for x in MEASURES:
            X = d[x].to_numpy()
            reg.ratio(f"{x}/OC|{g}", X, OCv, m & np.isfinite(X))
            reg.ratio(f"{x}/K|{g}", X, Kv, m & np.isfinite(X))
    for x in MEASURES:
        diff(reg, f"d {x}/OC|C-A2", f"{x}/OC|C", f"{x}/OC|A2")
        diff(reg, f"d {x}/K|C-A2", f"{x}/K|C", f"{x}/K|A2")
    diff(reg, "d nu|C-A2", "nu|C", "nu|A2")

    # ---- H11: Yang-Zhang -----------------------------------------------------------------------
    yz, vr = d["yz"].to_numpy(), d["var_r"].to_numpy()
    gapv, covt, rst = d["yz_gap"].to_numpy(), d["cov_term"].to_numpy(), d["rs_term"].to_numpy()
    yzr = d["yz_regime"].to_numpy()
    for i, g in enumerate(REGIMES + ["all windows"]):
        m = (yzr == i) if g != "all windows" else np.ones(len(d), dtype=bool)
        m = m & np.isfinite(yz) & np.isfinite(vr)
        reg.ratio(f"YZ/VarR|{g}", yz, vr, m)
        reg.ratio(f"cov share|{g}", covt, gapv, m)
        reg.ratio(f"rs share|{g}", rst, gapv, m)
        reg.ratio(f"cov/VarR|{g}", covt, vr, m)
    meta["H11"] = diff(reg, "d YZ/VarR|C-A2", "YZ/VarR|C", "YZ/VarR|A2")
    return reg, meta


# --------------------------------------------------------------------------------------------
# NIFTY (H12)
# --------------------------------------------------------------------------------------------

def nifty() -> pd.DataFrame:
    n = s34.build_nifty()
    n["r"] = n["o"] + n["c"]
    n["o_next"] = n["o"].shift(-1)
    n["K"] = n["c"] ** 2 + n["o"] * n["c"] + n["c"] * n["o_next"]
    comp = op.yang_zhang_components(n["o"], n["c"], n["RS"])
    for c_ in comp:
        n[c_] = comp[c_]
    n["yz_gap"] = n["yz"] - n["var_r"]
    crash = pd.Timestamp("2012-10-05")
    pos = n.index[n["date"] == crash]
    n["window_has_crash"] = False
    if len(pos):
        p = n.index.get_loc(pos[0])
        n.iloc[p:p + 21, n.columns.get_loc("window_has_crash")] = True
    return n


def run_nifty(n: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sample, frame in [("full (incl. 2012-10-05)", n),
                          ("excl. 2012-10-05", n[n["date"] != pd.Timestamp("2012-10-05")])]:
        f = frame.reset_index(drop=True)
        reg = Registry(len(f))
        o, c, P = f["o"].to_numpy(), f["c"].to_numpy(), f["P"].to_numpy()
        ok = np.isfinite(o) & np.isfinite(c)
        reg.b("b", f, ok)
        reg.ratio("E[o c]/E[P]", o * c, P, ok)
        reg.ratio("E[c o_next]/E[P]", c * f["o_next"].to_numpy(), P, ok)
        Kv, OC = f["K"].to_numpy(), f["OC"].to_numpy()
        reg.ratio("transient share 1 - E[K]/E[OC]", OC - Kv, OC, ok & np.isfinite(Kv))
        reg.ratio("E[P]/E[K]", P, Kv, ok & np.isfinite(Kv))
        reg.ratio("E[P]/E[OC]", P, OC, ok)
        wm = np.isfinite(f["yz"].to_numpy()) & np.isfinite(f["var_r"].to_numpy())
        if sample.startswith("excl"):
            wm &= ~f["window_has_crash"].to_numpy()
        reg.ratio("YZ/Var21(r)", f["yz"].to_numpy(), f["var_r"].to_numpy(), wm)
        reg.ratio("covariance share of the YZ gap", f["cov_term"].to_numpy(), f["yz_gap"].to_numpy(), wm)
        # POST-RESULT ADDITION (disclosed in M15_OPENING_PRICE_RESULTS.md): on NIFTY the gap is
        # ~0, so its covariance SHARE is a ratio of two near-zero sums and uninformative; the same
        # decomposition is reported scaled by Var21(r), which is well defined.
        reg.ratio("-2 Cov(o,c) / Var21(r)", f["cov_term"].to_numpy(), f["var_r"].to_numpy(), wm)
        reg.ratio("RS term / Var21(r)", f["rs_term"].to_numpy(), f["var_r"].to_numpy(), wm)
        point = reg.evaluate()
        boot = s34.joint_bootstrap(f, {"m": lambda fr, mult: reg.evaluate(mult)}, seed=SEED,
                                   resample_securities=False)
        lo, hi = s34.ci(boot["m"])
        for i, name in enumerate(reg.all_names()):
            rows.append({"sample": sample, "statistic": name, "value": point[i], "lo": lo[i],
                         "hi": hi[i], "n_sessions": int(ok.sum()),
                         "from": str(f["date"].min().date()), "to": str(f["date"].max().date())})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Placebo breaks (H7): point estimates at every placebo date
# --------------------------------------------------------------------------------------------

def placebo_breaks(d: pd.DataFrame) -> pd.DataFrame:
    cal = pd.DatetimeIndex(np.sort(d["date"].unique()))
    cal = cal[(cal != EXCLUDED) & (cal < op.WEEK_REFORM)]
    o, r = d["o"].to_numpy(), d["r"].to_numpy()
    ok = np.isfinite(o) & np.isfinite(r)
    # per-date sums, so each window is a sum over dates
    dd = d.loc[ok, "date"]
    s_or = pd.Series(o[ok] * r[ok]).groupby(dd.to_numpy()).sum()
    s_oo = pd.Series(o[ok] * o[ok]).groupby(dd.to_numpy()).sum()
    rows = []
    for d0, pre, post in op.placebo_windows(cal, length=40, gap=9, step=5):
        bp = s_or.reindex(pre).sum() / s_oo.reindex(pre).sum()
        bq = s_or.reindex(post).sum() / s_oo.reindex(post).sum()
        rows.append({"placebo_date": str(d0.date()), "pre_from": str(pre[0].date()),
                     "pre_to": str(pre[-1].date()), "post_from": str(post[0].date()),
                     "post_to": str(post[-1].date()), "b_pre": bp, "b_post": bq,
                     "jump": bq - bp})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------------------------

def tables(d, reg, meta, point, lo, hi, plac):
    v = {n: (point[i], lo[i], hi[i]) for i, n in enumerate(reg.all_names())}
    out = {}

    def row(name, **kw):
        p, l, h = v[name]
        return {**kw, "value": p, "lo": l, "hi": h}

    # table89: by regime, zones, liquidity
    t = []
    for g in REGIMES:
        n_rows = int(((d["regime"] == g) & d["o"].notna() & d["c"].notna()).sum())
        for stat, lab in [("b", "unbiasedness coefficient b = E[o r]/E[o^2]"),
                          ("oc_P", "E[o c]/E[P]"),
                          ("oa_o2", "E[o a]/E[o^2] (undone before the VWAP centre)"),
                          ("oq_o2", "E[o q]/E[o^2] (undone after the VWAP centre)"),
                          ("stale", "share of opens equal to the previous close"),
                          ("pinned", "share of opens pinned at the band in force")]:
            t.append(row(f"{stat}|{g}", block="regime", regime=g, group="all", statistic=lab,
                         n_stock_days=n_rows))
        for z in ["interior", "old-band zone", "pinned"]:
            name = f"b|{g}|{z}"
            if name in v:
                n_z = int(((d["regime"] == g) & (d["zone"] == z) & d["o"].notna() & d["c"].notna()).sum())
                t.append(row(name, block="zone", regime=g, group=z, statistic="b",
                             n_stock_days=n_z))
    for name in ["b|C|old-band zone|excl first 5", "b|C|interior|excl first 5"]:
        t.append(row(name, block="zone, sensitivity", regime="C",
                     group=name.split("|")[2] + ", excl. first 5 sessions", statistic="b",
                     n_stock_days=np.nan))
    for q in [f"Q{i}" for i in range(1, 6)]:
        for g in REGIMES:
            t.append(row(f"b|{q}|{g}", block="liquidity quintile", regime=g, group=q,
                         statistic="b", n_stock_days=np.nan))
    for name, lab in [("db|C-A2", "C - A2"), ("db|B-A1", "B - A1"), ("db|A2-A1", "A2 - A1"),
                      ("db_interior|C-A2", "interior opens, C - A2")]:
        t.append(row(name, block="difference", regime=lab, group="all" if "interior" not in name
                     else "interior", statistic="difference in b", n_stock_days=np.nan))
    out["table89_m15_unbiasedness.csv"] = pd.DataFrame(t)

    # table90: event windows
    t = []
    w = meta["windows"]
    for lab in ["pre", "gap", "post", "post_late"]:
        dates = w[lab]
        for stat, sl in [("b", "b"), ("oc_P", "E[o c]/E[P]"), ("K_OC", "E[K]/E[OC]")]:
            t.append(row(f"{stat}|win:{lab}", window=lab, statistic=sl,
                         sessions=len(dates), date_from=str(dates[0].date()),
                         date_to=str(dates[-1].date())))
    for name, lab in [("db|win:post-pre", "jump: post - pre"),
                      ("db|win:post_late-pre", "jump, post window starting at the 6th session"),
                      ("db|win:gap-pre", "inter-reform bin - pre")]:
        t.append(row(name, window=lab, statistic="difference in b", sessions=np.nan,
                     date_from="", date_to=""))
    tab90 = pd.DataFrame(t)
    jump = v["db|win:post-pre"][0]
    tab90.attrs["placebo_rank"] = int((plac["jump"] <= jump).sum())
    out["table90_m15_event_window.csv"] = tab90
    out["table90b_m15_placebo_breaks.csv"] = plac

    # table91: monthly
    t = []
    for mo in meta["months"]:
        n_rows = int(((d["date"].dt.to_period("M").astype(str) == mo) & d["o"].notna()
                      & d["c"].notna() & (d["date"] != EXCLUDED)).sum())
        pb, lb, hb = v[f"b|month:{mo}"]
        pm, lm, hm = v[f"oc_P|month:{mo}"]
        t.append({"month": mo, "n_stock_days": n_rows, "b": pb, "b_lo": lb, "b_hi": hb,
                  "oc_over_P": pm, "oc_over_P_lo": lm, "oc_over_P_hi": hm})
    out["table91_m15_monthly.csv"] = pd.DataFrame(t)

    # table92: dose-response
    t = []
    for gname, grp in meta["intensity"]["groups"].items():
        share = meta["intensity"]["share_A2" if "A2" in gname else "share"]
        for g_ in sorted(set(grp)):
            members = grp.index[grp == g_]
            for per in ["A2", "C", "C excl first 5", "A2 first half", "A2 second half"]:
                t.append(row(f"b|{gname}|{g_}|{per}", grouping=gname, group=g_, period=per,
                             statistic="b", n_securities=len(members),
                             intensity_min=float(share.loc[members].min()),
                             intensity_max=float(share.loc[members].max())))
        h = meta["H8"][gname]
        for key, lab in [("did", "DiD: (high, C - A2) - (low, C - A2)"),
                         ("did_late", "DiD, C excluding its first 5 sessions"),
                         ("placebo", "placebo DiD: A2 second half - first half")]:
            t.append(row(h[key], grouping=gname, group=f"{h['hi']} vs {h['lo']}", period=lab,
                         statistic="difference-in-differences in b", n_securities=np.nan,
                         intensity_min=np.nan, intensity_max=np.nan))
    tab92 = pd.DataFrame(t)
    tab92.attrs["placebo_split"] = str(meta["placebo_split"].date())
    out["table92_m15_dose_response.csv"] = tab92

    # table93: estimator evaluation
    t = []
    for g in REGIMES:
        t.append(row(f"nu|{g}", regime=g, measure="OC",
                     statistic="transient share of the proxy, 1 - E[K]/E[OC]"))
        for x in MEASURES:
            t.append(row(f"{x}/OC|{g}", regime=g, measure=x, statistic="E[X]/E[OC]"))
            t.append(row(f"{x}/K|{g}", regime=g, measure=x, statistic="E[X]/E[K]"))
    for x in MEASURES:
        t.append(row(f"d {x}/OC|C-A2", regime="C - A2", measure=x, statistic="change in E[X]/E[OC]"))
        t.append(row(f"d {x}/K|C-A2", regime="C - A2", measure=x, statistic="change in E[X]/E[K]"))
    t.append(row("d nu|C-A2", regime="C - A2", measure="OC", statistic="change in the transient share"))
    out["table93_m15_estimator_evaluation.csv"] = pd.DataFrame(t)

    # table94: Yang-Zhang
    t = []
    for i, g in enumerate(REGIMES + ["all windows"]):
        m = ((d["yz_regime"] == i) if g != "all windows" else True) & d["yz"].notna() & d["var_r"].notna()
        n_w = int(m.sum())
        for stat, lab in [("YZ/VarR", "sum YZ / sum Var21(r) (variance scale)"),
                          ("cov share", "share of sum(YZ - Var21(r)) carried by -2 Cov(o, c)"),
                          ("rs share", "share carried by (1 - k)[mean RS - Var(c)]"),
                          ("cov/VarR", "sum(-2 Cov(o, c)) / sum Var21(r)")]:
            t.append(row(f"{stat}|{g}", windows=g, statistic=lab, n_windows=n_w))
    t.append(row("d YZ/VarR|C-A2", windows="C - A2", statistic="change in sum YZ / sum Var21(r)",
                 n_windows=np.nan))
    out["table94_m15_yang_zhang.csv"] = pd.DataFrame(t)
    return out, v


# --------------------------------------------------------------------------------------------
# Decision ledger
# --------------------------------------------------------------------------------------------

def decisions(v, meta, plac, nif):
    rows = []

    def fmt(name, nd=3):
        p, l, h = v[name]
        return f"{p:.{nd}f} [{l:.{nd}f}, {h:.{nd}f}]"

    # H7
    p, l, h = v[meta["H7"]]
    below_all = bool(p < plac["jump"].min())
    rank = int((plac["jump"] <= p).sum())
    verdict = ("sharp break" if (h < 0 and below_all) else
               ("break, not unique" if h < 0 else "not detected"))
    rows.append({"hypothesis": "H7", "statistic": "jump in b, 40 sessions from 2026-04-20 minus the 40 ending 2026-04-05 (predicted < 0)",
                 "estimate": f"{fmt(meta['H7'])}; placebo jumps {len(plac)}, min {plac['jump'].min():.3f}, "
                             f"max {plac['jump'].max():.3f}; placebos at or below the actual jump: {rank}",
                 "verdict": verdict})
    # H8
    h8 = meta["H8"]["terciles"]
    p, l, h = v[h8["did"]]
    pp, pl, ph = v[h8["placebo"]]
    placebo_zero = pl <= 0 <= ph
    if h < 0 and placebo_zero:
        verdict = "confirmed"
    elif h < 0 and ph < 0:
        verdict = "confounded"
    elif l > 0:
        verdict = "reversed"
    else:
        verdict = "not detected"
    rows.append({"hypothesis": "H8", "statistic": "DiD in b, top minus bottom tercile of pre-reform pinned share, C minus A2 (predicted < 0)",
                 "estimate": f"DiD {fmt(h8['did'])}; placebo DiD {fmt(h8['placebo'])}",
                 "verdict": verdict})
    # H9
    pa, la, ha = v[meta["H9"]["a"]]
    pb, lb, hb = v[meta["H9"]["b"]]
    a_ok, b_ok = la > 1, hb < 1
    joint = {(True, True): "trade-off", (True, False): "censoring only",
             (False, True): "overshoot only", (False, False): "neither"}[(a_ok, b_ok)]
    rows.append({"hypothesis": "H9(a)", "statistic": "b, pinned opens in A2 (predicted > 1)",
                 "estimate": fmt(meta["H9"]["a"]),
                 "verdict": "delayed price discovery at the band" if a_ok else "not detected"})
    rows.append({"hypothesis": "H9(b)", "statistic": "b, opens in the old-band zone in C (predicted < 1)",
                 "estimate": fmt(meta["H9"]["b"]),
                 "verdict": "overshoot where the band used to bind" if b_ok else "not detected"})
    rows.append({"hypothesis": "H9", "statistic": "joint verdict", "estimate": "", "verdict": joint})
    pc, lc, hc = v[meta["H9"]["c"]]
    rows.append({"hypothesis": "H9(c) (reported)", "statistic": "b, interior opens, C minus A2",
                 "estimate": fmt(meta["H9"]["c"]),
                 "verdict": ("concentrated where the band bound" if lc <= 0 <= hc else
                             ("broader change in auction behaviour" if hc < 0 else
                              "interior opens moved toward underreaction"))})
    # H10
    p1, l1, h1_ = v["d P/OC|C-A2"]
    p2, l2, h2_ = v["d P/K|C-A2"]
    rows.append({"hypothesis": "H10 (consequence)",
                 "statistic": "change A2 to C in E[P]/E[OC] and in E[P]/E[K] (point estimates known before freezing)",
                 "estimate": f"E[P]/E[OC] {fmt('d P/OC|C-A2')}; E[P]/E[K] {fmt('d P/K|C-A2')}",
                 "verdict": "inversion" if (h1_ < 0 and l2 > 0) else "no inversion established"})
    # H11
    p, l, h = v[meta["H11"]]
    rows.append({"hypothesis": "H11", "statistic": "sum YZ / sum Var21(r), C minus A2 (predicted > 0)",
                 "estimate": fmt(meta["H11"]),
                 "verdict": "confirmed" if l > 0 else ("opposite" if h < 0 else "not detected")})
    # H12
    for sample in nif["sample"].unique():
        s = nif[nif["sample"] == sample].set_index("statistic")
        rows.append({"hypothesis": "H12 (reported)", "statistic": f"NIFTY 50, {sample}",
                     "estimate": "; ".join(f"{k} {s.loc[k, 'value']:.3f} [{s.loc[k, 'lo']:.3f}, {s.loc[k, 'hi']:.3f}]"
                                           for k in ["b", "E[o c]/E[P]", "transient share 1 - E[K]/E[OC]",
                                                     "YZ/Var21(r)"]),
                     "verdict": "reported, no decision"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------------------------

RULE_KEY = ("Rule changes: 1 = 15-minute VWAP close (20 Mar 2025); 2 = last-trade close again "
            "(23 Sep 2025);\n3 = Monday-Friday week (6 Apr 2026); 4, solid = pre-open band "
            "±2% → ±5% and daily limit ±10% → ±15% (20 Apr 2026)")


def _monthly_panel(ax, x, mid, lo, hi, ref, title, sub, ylabel):
    blue = ps.SERIES["blue"]
    ax.axhline(ref, color=ps.INK_MUTED, lw=0.8, zorder=1)
    ax.fill_between(x, lo, hi, color=blue, alpha=0.16, lw=0, zorder=2)
    ax.plot(x, mid, color=blue, marker="o", ms=3.2, lw=1.4, zorder=3)
    for k, (dt, _) in enumerate(RULE_DATES):
        t = pd.Timestamp(dt)
        ax.axvline(t, color=ps.INK_SOFT if k == 3 else ps.INK_MUTED, lw=1.0 if k == 3 else 0.7,
                   ls="-" if k == 3 else "--", zorder=1)
        # numbered tags just inside the top edge; 3 and 4 are two weeks apart, so they face apart
        ax.text(t, 0.97, f" {k + 1} " if k < 2 else (f"{k + 1} " if k == 2 else f" {k + 1}"),
                transform=ax.get_xaxis_transform(), va="top",
                ha="right" if k == 2 else "left", fontsize=7, color=ps.INK_SOFT)
    ps.finish(ax, title=title, sub=sub, ylabel=ylabel)


def figure(tab91: pd.DataFrame, tab92: pd.DataFrame, plac: pd.DataFrame, jump: float) -> None:
    ps.apply()
    fig = plt.figure(figsize=(7.2, 8.3))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.05, 1.0, 1.0], hspace=0.95, wspace=0.32)
    x = pd.PeriodIndex(tab91["month"], freq="M").to_timestamp() + pd.Timedelta(days=14)
    blue = ps.SERIES["blue"]
    _monthly_panel(fig.add_subplot(gs[0, :]), x, tab91["b"], tab91["b_lo"], tab91["b_hi"], 1.0,
                   "A. How much of the opening move survives to the close, by month",
                   "b = E[o r]/E[o²]: 1 = the open anticipates the close, 0 = the session "
                   "undoes it all; 95% block-bootstrap band", "b")
    _monthly_panel(fig.add_subplot(gs[1, :]), x, tab91["oc_over_P"], tab91["oc_over_P_lo"],
                   tab91["oc_over_P_hi"], 0.0,
                   "B. The overnight-intraday reversal, by month",
                   "E[o c]/E[P]: the opening error's footprint, scaled by mean Parkinson variance; "
                   "95% block-bootstrap band", "E[o c] / E[P]")

    ax2 = fig.add_subplot(gs[2, 0])
    t = tab92[(tab92["grouping"] == "terciles") & tab92["period"].isin(["A2", "C"])]
    orange = ps.SERIES["orange"]
    # identity colours in the house order: blue = before the reform, orange = after it
    for j, (per, col, mk) in enumerate([("A2", blue, "o"), ("C", orange, "s")]):
        s = t[t["period"] == per].set_index("group").loc[["T1", "T2", "T3"]]
        xx = np.arange(3) + (j - 0.5) * 0.22
        ax2.errorbar(xx, s["value"], yerr=[s["value"] - s["lo"], s["hi"] - s["value"]], fmt=mk,
                     color=col, ecolor=col, ms=5, lw=1.0, capsize=0,
                     label="A2 (±2% band)" if per == "A2" else "C (±5% band)")
    ax2.set_xticks(range(3), ["T1\nband bound\nleast", "T2", "T3\nband bound\nmost"])
    ax2.set_ylim(0, 0.72)
    ax2.legend(loc="upper center", ncol=2, fontsize=7, handletextpad=0.3, columnspacing=1.0)
    ps.finish(ax2, title="C. By pre-reform exposure to the band", ylabel="b")

    ax3 = fig.add_subplot(gs[2, 1])
    ax3.hist(plac["jump"], bins=24, color=ps.INK_MUTED, alpha=0.75, lw=0)
    ax3.axvline(jump, color=orange, lw=1.6)
    ax3.text(jump, ax3.get_ylim()[1] * 0.95, " 20 Apr\n 2026", color=ps.INK_SOFT, fontsize=7,
             va="top", ha="left")
    ps.finish(ax3, title="D. The reform's jump against placebo dates",
              xlabel="jump in b, 40 sessions after minus 40 before")
    ax3.set_ylabel("placebo dates")
    # the key to the numbered rule-date lines of panels A and B, as a footnote (bbox_inches="tight"
    # in the house style extends the canvas to include it)
    fig.text(0.0, 0.0, RULE_KEY, ha="left", va="top", fontsize=7, color=ps.INK_SOFT)
    for e in ("pdf", "png"):
        fig.savefig(FIG / f"fig23_opening_price.{e}")
    plt.close(fig)


# --------------------------------------------------------------------------------------------

def main() -> None:
    t0 = time.time()
    print("M15: what the opening price measures (frozen plan)")
    d = build()
    print(f"  NEPSE equity panel: {len(d):,} stock-days; built in {time.time() - t0:.0f}s")
    reg, meta = register(d)
    point = reg.evaluate()
    boot = s34.joint_bootstrap(d, {"m": lambda fr, mult: reg.evaluate(mult)}, seed=SEED)
    lo, hi = s34.ci(boot["m"])
    print(f"  {len(reg.all_names())} statistics, joint bootstrap done [{time.time() - t0:.0f}s]")
    plac = placebo_breaks(d)
    out, v = tables(d, reg, meta, point, lo, hi, plac)
    nif = run_nifty(nifty())
    out["table95_m15_nifty.csv"] = nif
    dec = decisions(v, meta, plac, nif)
    out["table96_m15_decisions.csv"] = dec
    for name, frame in out.items():
        frame.to_csv(TAB / name, index=False, float_format=FLOAT_FMT)
    print(f"  placebo rank of the actual jump: {out['table90_m15_event_window.csv'].attrs['placebo_rank']} "
          f"of {len(plac)} placebos at or below it; A2 placebo split at {out['table92_m15_dose_response.csv'].attrs['placebo_split']}")
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 140)
    print(out["table89_m15_unbiasedness.csv"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(out["table90_m15_event_window.csv"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(out["table92_m15_dose_response.csv"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(out["table93_m15_estimator_evaluation.csv"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(out["table94_m15_yang_zhang.csv"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(nif.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\nM15 decisions (frozen rules, applied mechanically)")
    print(dec.to_string(index=False))
    figure(out["table91_m15_monthly.csv"], out["table92_m15_dose_response.csv"], plac,
           v[meta["H7"]][0])
    print(f"\ndone in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
