"""M22: Anam II on the test spans of M20 (seen) and on the Pakistan Stock Exchange (unseen).

Implements ``M22_ANAM2_PLAN.md``. The plan, this script, ``nepsevol.estimators.anam2`` and the Pakistan reader in
``nepsevol.frontier`` were frozen and pushed together before this script was run on any test row and before any
estimator was computed on the Pakistan data. The plan's decision rules are applied mechanically.

For each sample and horizon (h = 5, 21):

1. M20's forecasts are rebuilt by M20's own code (``scripts/47_corrected_evaluation.py``) and their parameters
   chosen by M20's rule on M20's training rows. On the seven M20 samples, the open-free HAR's test loss on M20's
   rows must reproduce table 127; the script stops otherwise.
2. The forecasts of M22 (Anam II, its ablations and its alternatives) are fitted by QLIKE on the same training
   rows, restricted to the rows where they are defined.
3. Every forecast is scored on the common test rows: M20's rows where every M22 forecast is also defined.

Inputs: as script 47, plus ``data/external/frontier/psx/`` (pinned in ``nepsevol.frontier``). Samples whose inputs
are missing are skipped and the tables are written with a ``_partial`` suffix.

``--dry-run DIR`` exercises the whole script on training rows only, so that it could be checked before the plan was
frozen: each sample except Pakistan is cut to its training span, whose first half plays the training span and
whose second half the test span; the check against table 127 is skipped; the tables go to DIR.

Outputs (output/tables/):
    table138_m22_comparison.csv    every forecast: parameters, training and test loss, differences and t statistics
    table139_m22_claims.csv        hypotheses H1-H3 with Holm's adjustment and the practical margin, and P1-P2
    table140_m22_mcs.csv           the 90% model confidence set among the main forecasts
    table141_m22_panels.csv        the panels: rule counts (Pakistan) and descriptive statistics of the open
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import argparse
import importlib.util
import math
import sys
import time

import numpy as np
import pandas as pd

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"

_spec = importlib.util.spec_from_file_location("s47", ROOT / "scripts" / "47_corrected_evaluation.py")
s47 = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, sys.argv[:1]
_spec.loader.exec_module(s47)
sys.argv = _argv
EV, FB, AN, F = s47.EV, s47.FB, s47.AN, s47.F

from nepsevol.estimators import anam2 as A2  # noqa: E402

PANELS = ["NEPSE", "DSE 2023-2026", "DSE 2009-2021", "Vietnam 2007-2020", "Morocco 2012-2026", "Pakistan 2016-2026"]
SERIES = ["NIFTY50", "SP500"]
SAMPLES = ["NEPSE", "NIFTY50", "SP500", "DSE 2023-2026", "Vietnam 2007-2020", "DSE 2009-2021", "Morocco 2012-2026",
           "Pakistan 2016-2026"]
UNSEEN = {"Pakistan 2016-2026"}
WINDOWS = s47.WINDOWS
SEED = 20261011
N_BOOT = 1999

ANAM2 = "Anam II"
REF = "HAR-open-free"                       # M20's forecast, M20's grid and rule
COMBO2 = "1/2 Anam II + 1/2 GJR"
RSTAR = "r* (best return-only)"
#: M22's forecasts besides Anam II (panels / series)
M22_PANEL = ["HAR open-free (continuous)", "FHARL open-free", "HAR MSO (continuous)", "FHARL M1", "FHARL MS"]
M22_SERIES = ["HAR open-free (continuous)"]
MCS_SET = [ANAM2, REF, "FHARL open-free", RSTAR, "GJR", COMBO2, "CC"]


class ConvexHAR:
    """kappa (c1 d1 + c2 m5 + c3 m22 + c4 lr), convex weights fitted by QLIKE (Anam II's fit, M20's components)."""

    def __init__(self, A, r2, symbol, date, mode):
        self.kappa = A2.calibration(A, r2, date, symbol, mode)
        Ac = FB.clean_square(A)
        self.Z = FB.har_components(Ac.where(Ac.notna() & r2.notna()), symbol)[["d1", "m5", "m22", "lr"]]
        self.defined = self.Z.notna().all(axis=1) & self.kappa.notna() & (self.kappa > 0) & (self.Z["lr"] > 0)

    def forecast(self, c):
        return pd.Series(self.kappa.to_numpy() * (self.Z.to_numpy() @ np.asarray(c, float)), index=self.Z.index)

    def fit(self, y, rows):
        Zr = self.Z[rows].to_numpy() * self.kappa[rows].to_numpy()[:, None]
        return A2.fit_weights(Zr, y[rows].to_numpy())


def m22_models(S) -> dict:
    d, mode = S["d"], S["mode"]
    o, c, u, dd, r2, sym, date = d["o"], d["c"], d["u"], d["d"], d["CC"], d["symbol"], d["date"]
    zero = pd.Series(0.0, index=d.index)
    X_of = AN.kernel(o, c, u, dd, zero)
    X_a2 = A2.kernel(o, c, u, dd, A2.effective_open(o, date, mode))
    M = {ANAM2: A2.Forecaster(X_a2, r2, sym, date, mode),
         "HAR open-free (continuous)": ConvexHAR(X_of, r2, sym, date, mode)}
    if mode == "panel":
        m = A2.market_move(o, date)
        stale_bar = (o.abs() < A2.EPS) & (u.abs() < A2.EPS) & (dd.abs() < A2.EPS) & (c.abs() < A2.EPS)
        M["FHARL open-free"] = A2.Forecaster(X_of, r2, sym, date, mode)
        M["HAR MSO (continuous)"] = ConvexHAR(X_a2, r2, sym, date, mode)
        M["FHARL M1"] = A2.Forecaster(A2.kernel(o, c, u, dd, m), r2, sym, date, mode)
        M["FHARL MS"] = A2.Forecaster(A2.kernel(o, c, u, dd, m.where(stale_bar, 0.0)), r2, sym, date, mode)
    return M


def p_two_sided(t: float) -> float:
    return math.erfc(abs(t) / math.sqrt(2.0)) if np.isfinite(t) else np.nan


def holm(rows: list[dict]) -> list[dict]:
    """Holm's step-down adjustment of the two-sided p values in ``rows`` (one family)."""
    order = sorted([r for r in rows if np.isfinite(r["p"])], key=lambda r: r["p"])
    m, running = len(order), 0.0
    for i, r in enumerate(order):
        running = max(running, min(1.0, (m - i) * r["p"]))
        r["p_holm"] = running
    for r in rows:
        r.setdefault("p_holm", np.nan)
        sig = np.isfinite(r["p_holm"]) and r["p_holm"] < 0.05
        r["verdict"] = ("better" if r["d"] < 0 else "worse") if sig else "no detectable difference"
    return rows


def descriptives(S, log: dict | None) -> dict:
    """The open on the sample's training rows: b, its market and stock-specific parts, stale shares."""
    d = S["d"]
    tr = S["train"].reindex(d.index).fillna(False).astype(bool)
    x = d[tr & d[["o", "c", "u", "d"]].notna().all(axis=1)]
    out = dict(sample=S["name"], train_bars=len(x), securities=int(d["symbol"].nunique()),
               sessions=int(d["date"].nunique()), first_session=str(d["date"].min().date()),
               last_session=str(d["date"].max().date()))
    test0 = d.loc[S["spans"][S["primary"]], "date"].min()
    out["first_test_session"] = str(test0.date())
    out["b_pooled"] = float((x["o"] * x["r"]).sum() / (x["o"] ** 2).sum())
    out["stale_open_share"] = float((x["o"].abs() < A2.EPS).mean())
    out["one_price_share"] = float(((x["u"] - x["d"]).abs() < A2.EPS).mean())
    if S["mode"] == "panel":
        oM = x.groupby("date")["o"].transform("mean")
        oI = x["o"] - oM
        out["b_market"] = float((oM * x["r"]).sum() / (oM ** 2).sum())
        out["b_stock"] = float((oI * x["r"]).sum() / (oI ** 2).sum())
        out["market_share_o2"] = float((oM ** 2).sum() / (x["o"] ** 2).sum())
    if log:
        out.update({f"rule: {k}": v for k, v in log.items()})
    return out


def dry_sample(S) -> dict:
    """The sample cut to its training rows, split at the median training date (``--dry-run``)."""
    d = S["d"]
    tr = S["train"].reindex(d.index).fillna(False).astype(bool)
    d = d[tr].copy()
    dates = np.sort(d["date"].unique())
    half = dates[len(dates) // 2]
    S = dict(S, d=d, train=d["date"] < half, spans={"pseudo test": d["date"] >= half}, primary="pseudo test")
    return S


def run_sample(S, idx, n_boot, m20_tab, dry=False):
    d = S["d"]
    name = S["name"]
    out = dict(comparison=[], mcs=[])
    M22 = m22_models(S)
    for win in WINDOWS:
        t0 = time.time()
        M, K, b = s47.build_models(S, win)
        tgt = EV.forward_target(FB.clean_square(d["CC"]), d["symbol"], d["ses"], win)
        y = tgt["y"]
        first_test = {sp: int(d.loc[m, "ses"].min()) for sp, m in S["spans"].items()}
        cutoff = min(first_test.values())
        def_m20 = pd.Series(True, index=d.index)
        for m in M.values():
            def_m20 &= m.defined.reindex(d.index).fillna(False).astype(bool)
        def_all = def_m20.copy()
        for m in M22.values():
            def_all &= m.defined.reindex(d.index).fillna(False).astype(bool)
        train_m20 = S["train"] & def_m20 & y.notna() & (tgt["end_session"] < cutoff)
        train_all = S["train"] & def_all & y.notna() & (tgt["end_session"] < cutoff)
        # M20's forecasts, M20's rule on M20's training rows
        params, train_loss = {}, {}
        for nm in s47.RETURN_ONLY + [REF]:
            p, L, _ = s47.select(M[nm], y, train_m20)
            params[nm], train_loss[nm] = p, L
        fc = {nm: M[nm].forecast(params[nm]) for nm in s47.RETURN_ONLY + [REF]}
        rstar = min(s47.RETURN_ONLY, key=lambda k: train_loss[k])
        fc[RSTAR] = fc[rstar]
        params[RSTAR], train_loss[RSTAR] = f"{rstar} {params[rstar]}", train_loss[rstar]
        # M22's forecasts, fitted by QLIKE on the common training rows
        for nm, m in M22.items():
            c, L = m.fit(y, train_all)
            fc[nm] = m.forecast(c)
            params[nm], train_loss[nm] = str(np.round(c, 6).tolist()), L
        fc[COMBO2] = 0.5 * fc[ANAM2] + 0.5 * fc["GJR"]
        params[COMBO2] = "fixed 1/2, 1/2"
        train_loss[COMBO2] = float(np.mean(EV.qlike_canonical(y[train_all], fc[COMBO2][train_all])))
        for span, span_mask in S["spans"].items():
            span_end = int(d.loc[span_mask, "ses"].max())
            inside = tgt["end_session"] <= span_end
            rows_m20 = span_mask & def_m20 & y.notna() & inside
            rows = span_mask & def_all & y.notna() & inside
            if name not in UNSEEN and not dry:  # M20's forecast must reproduce M20's published test loss
                pub = m20_tab[(m20_tab.market == name) & (m20_tab.span == span) & (m20_tab.window == win) &
                              (m20_tab.model == REF)]
                mine = float(np.mean(EV.qlike_canonical(y[rows_m20], fc[REF][rows_m20])))
                assert len(pub) == 1 and int(pub["n"].iloc[0]) == int(rows_m20.sum()), (name, span, win, "rows")
                assert abs(mine - float(pub["QLIKE_canonical"].iloc[0])) < 1e-9, (name, span, win, mine)
                assert str(params[REF]) == str(pub["parameters"].iloc[0]), (name, span, win, params[REF])
            dates = d.loc[rows, "date"]
            L = {nm: pd.Series(EV.qlike_canonical(y[rows], f[rows]), index=dates.index) for nm, f in fc.items()}
            for nm in L:
                row = dict(market=name, span=span, window=win, model=nm, seen=name not in UNSEEN,
                           parameters=str(params.get(nm, "")), train_loss=train_loss.get(nm, np.nan),
                           n_train=int(train_all.sum()), n=int(rows.sum()), n_m20_rows=int(rows_m20.sum()),
                           n_dates=int(dates.nunique()), zero_targets=int((y[rows] == 0).sum()),
                           QLIKE_canonical=float(L[nm].mean()),
                           QLIKE_normalized=float(np.nanmean(EV.qlike_normalized(y[rows], fc[nm][rows]))))
                for ref in (REF, ANAM2, RSTAR, "FHARL open-free" if S["mode"] == "panel" else "HAR open-free (continuous)"):
                    rr = EV.weighted_mean_se(L[nm] - L[ref], dates, lags=2 * win)
                    row[f"d_vs_{ref}"], row[f"t_vs_{ref}"] = rr["mean"], rr["t"]
                out["comparison"].append(row)
            sel = [m for m in MCS_SET if m in L]
            Sm = EV.date_sums(pd.DataFrame({m: L[m] for m in sel}), dates)
            W = Sm.pop("_W")
            mcs = EV.model_confidence_set(Sm, W, alpha=(0.10, 0.25), n_boot=n_boot, mean_block=max(2 * win, 10),
                                          seed=SEED + 100 * idx + win)
            mcs.insert(0, "window", win)
            mcs.insert(0, "span", span)
            mcs.insert(0, "market", name)
            out["mcs"].append(mcs)
        print(f"  {name} h={win}: {time.time() - t0:.0f}s; r* = {rstar}", flush=True)
    return out


def claims(cmp: pd.DataFrame, primary: dict) -> pd.DataFrame:
    rows = []
    hyp = {"H1": (ANAM2, REF, "Anam II against M20's open-free HAR"),
           "H2": (ANAM2, "FHARL open-free", "the market-implied open against the open-free kernel, same dynamics"),
           "H3": (ANAM2, RSTAR, "Anam II against the best return-only forecast")}
    for h, (a, b, what) in hyp.items():
        for win in WINDOWS:
            fam = []
            for mk in PANELS:
                if mk not in primary:
                    continue
                r = cmp[(cmp.market == mk) & (cmp.span == primary[mk]) & (cmp.window == win) & (cmp.model == a)]
                if not len(r):
                    continue
                dv, tv = float(r[f"d_vs_{b}"].iloc[0]), float(r[f"t_vs_{b}"].iloc[0])
                ref = cmp[(cmp.market == mk) & (cmp.span == primary[mk]) & (cmp.window == win) & (cmp.model == b)]
                margin = 0.01 * float(ref["QLIKE_normalized"].iloc[0])
                half90 = 1.645 * abs(dv / tv) if np.isfinite(tv) and tv != 0 else np.nan
                fam.append(dict(hypothesis=h, what=what, market=mk, span=primary[mk], window=win, seen=mk not in UNSEEN,
                                d=dv, t=tv, p=p_two_sided(tv), margin=margin,
                                practically_equivalent=bool(abs(dv) + half90 < margin) if np.isfinite(half90) else False))
            rows += holm(fam)
    out = pd.DataFrame(rows)
    # P1: the overall reading of H1 (plan, "Decision rules")
    summ = []
    if len(out):
        h1 = out[out.hypothesis == "H1"]
        n_better5 = int(((h1.window == 5) & (h1.verdict == "better")).sum())
        n_worse = int((h1.verdict == "worse").sum())
        n5 = int((h1.window == 5).sum())
        if n_worse == 0 and n_better5 >= 3:
            v = "supported: Anam II improves on M20's open-free HAR"
        elif n_worse == 0 and n_better5 >= 1:
            v = "partly supported: better in some panels, worse in none"
        elif n_worse == 0:
            v = "not supported: no panel shows a difference"
        else:
            v = "not supported: worse in at least one panel"
        summ.append(dict(hypothesis="P1", what="overall reading of H1", market="all panels", span="primary",
                         window=np.nan, seen=np.nan, d=np.nan, t=np.nan, p=np.nan, p_holm=np.nan,
                         verdict=f"{v} (better at h=5 in {n_better5} of {n5}; worse in {n_worse} panel-horizons)"))
        # P2: the predicted pattern of H2 (plan): better where stale opens are common, no difference elsewhere
        h2 = out[(out.hypothesis == "H2") & (out.window == 5)].set_index("market")
        pred = {"DSE 2023-2026": "better", "Morocco 2012-2026": "better", "Vietnam 2007-2020": "better",
                "NEPSE": "no detectable difference", "DSE 2009-2021": "no detectable difference"}
        def as_predicted(mk, v):
            if v == "better":
                return h2.loc[mk, "verdict"] == "better"
            # "no detectable difference" also holds when a significant difference lies inside the practical margin
            return h2.loc[mk, "verdict"] == v or bool(h2.loc[mk, "practically_equivalent"])
        hits = [mk for mk, v in pred.items() if mk in h2.index and as_predicted(mk, v)]
        summ.append(dict(hypothesis="P2", what="predicted pattern of H2 at h=5", market="five seen panels",
                         span="primary", window=5, seen=True, d=np.nan, t=np.nan, p=np.nan, p_holm=np.nan,
                         verdict=f"{len(hits)} of {len([m for m in pred if m in h2.index])} as predicted: {', '.join(hits)}"))
    return pd.concat([out, pd.DataFrame(summ)], ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", nargs="*", default=SAMPLES)
    ap.add_argument("--boot", type=int, default=N_BOOT)
    ap.add_argument("--dry-run", default=None, help="directory for a run on training rows only (see the docstring)")
    a = ap.parse_args()
    dry = a.dry_run is not None
    out_dir = TAB if not dry else __import__("pathlib").Path(a.dry_run)
    if dry:
        out_dir.mkdir(parents=True, exist_ok=True)
        print("DRY RUN on training rows only; Pakistan is not read")
    print("M22: Anam II on the M20 test spans (seen) and on Pakistan (unseen)")
    m20_tab = pd.read_csv(TAB / "table127_m20_comparison.csv")
    B = dict(comparison=[], mcs=[])
    panels, primary, done = [], {}, []
    for idx, name in enumerate(SAMPLES):
        if name not in a.samples:
            continue
        if name not in ("NEPSE", "NIFTY50", "SP500") and not s47.INPUTS.exists():
            continue
        if name == "Pakistan 2016-2026" and dry:
            continue
        if name == "Pakistan 2016-2026" and not (s47.INPUTS / "psx").exists():
            print("  Pakistan 2016-2026: skipped (data/external/frontier/psx/ not present)")
            continue
        t0 = time.time()
        S = s47.load(name)
        S["name"] = name
        if dry:
            S = dry_sample(S)
        log = None
        if name in UNSEEN:
            _, log = F.market_panel(name, s47.INPUTS)
        panels.append(descriptives(S, log))
        primary[name] = S["primary"]
        out = run_sample(S, idx, a.boot, m20_tab, dry=dry)
        for k in B:
            B[k] += out[k]
        done.append(name)
        print(f"  {name}: done in {time.time() - t0:.0f}s", flush=True)
    cmp = pd.DataFrame(B["comparison"])
    mcs = pd.concat(B["mcs"], ignore_index=True)
    cl = claims(cmp, primary)
    suffix = "" if set(done) == set(SAMPLES) else "_partial"
    for df, fname in ((cmp, "table138_m22_comparison"), (cl, "table139_m22_claims"), (mcs, "table140_m22_mcs"),
                      (pd.DataFrame(panels), "table141_m22_panels")):
        df.to_csv(out_dir / f"{fname}{suffix}.csv", index=False, float_format=FLOAT_FMT)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_colwidth", 120)
    print("\nCLAIMS")
    print(cl.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nTHE MAIN FORECASTS ON EACH PRIMARY SPAN (d against M20's open-free HAR, t)")
    main_ = cmp[cmp.apply(lambda r: r["span"] == primary.get(r["market"]), axis=1)]
    print(main_.pivot_table(index=["market", "window"], columns="model", values=f"t_vs_{REF}").round(2).to_string())
    print("\nTHE 90% MODEL CONFIDENCE SET")
    for (mk, sp, w), g in mcs.groupby(["market", "span", "window"], sort=False):
        print(f"  {mk} [{sp}] h={w}: {g[g['in_mcs_90']].sort_values('loss')['model'].tolist()}")
    if suffix:
        print(f"\nPARTIAL RUN: computed {done}")


if __name__ == "__main__":
    main()
