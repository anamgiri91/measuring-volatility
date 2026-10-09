"""M20: the corrected forecast evaluation, after the 9 October 2026 audit.

Implements M20_CORRECTED_EVALUATION_PLAN.md. The plan was frozen and pushed in commit 984dfbc, together with:

* the shared evaluation module (``anam_estimator.evaluation``);
* the baselines (``nepsevol.forecast_baselines``);
* their tests.

That was before this script existed or any corrected loss was computed. Every specification is the plan's;
the decision rules are applied mechanically.

Part A  The correction, one step at a time, for the nine frozen estimators. Step S0 must reproduce the
        frozen tables 101, 108 and 113.
Part B  Seventeen forecasts: return-only baselines, range variants and a combination.
        Rule B1 asks whether the range adds information. B2 is the model confidence set, B3 Holm's
        adjustment, B4 the practical margin.
Part C  Ablations.
Part D  Coverage, by reason and by liquidity.
Part E  Inference sensitivity.

Inputs: as scripts 40, 42 and 43. Four of the seven samples need the frontier files under
data/external/frontier/; the run reports which samples it computed.

Outputs (output/tables/):
    table125_m20_correction_steps.csv    Part A, every step
    table126_m20_verdict_changes.csv     Rule A: the frozen per-rival verdicts against the corrected ones
    table127_m20_comparison.csv          Part B: parameters, training and test losses, differences
    table128_m20_mcs.csv                 Rule B2
    table129_m20_claims.csv              Rules B1, B3, B4
    table130_m20_ablations.csv           Part C
    table131_m20_coverage.csv            Part D
    table132_m20_inference.csv           Part E
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

sys.path.insert(0, str(ROOT / "anam-estimator" / "src"))

from anam_estimator import evaluation as EV  # noqa: E402
from nepsevol import forecast_baselines as FB  # noqa: E402
from nepsevol import frontier as F  # noqa: E402
from nepsevol.estimators import anam as AN  # noqa: E402
from nepsevol.volforecast import LONGRUN_MIN, LONGRUN_SESSIONS  # noqa: E402
from nepsevol.volforecast import PHI_GRID as FROZEN_GRID  # noqa: E402
from nepsevol.volforecast import fair_forecast_test, nw_t, trailing_sum  # noqa: E402

TAB = ROOT / "output" / "tables"
INPUTS = ROOT / "data" / "external" / "frontier"
FLOAT_FMT = "%.10g"
WINDOWS = (5, 21)
PHI = tuple(float(x) for x in np.round(np.arange(0.0, 0.951, 0.05), 2))
SEED = 20261010
N_BOOT = 1999

_spec = importlib.util.spec_from_file_location("s40", ROOT / "scripts" / "40_anam_holdout.py")
s40 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s40)

OF = s40.VARIANT                                    # "Anam, open-free special case (b=0)"
FROZEN9 = ["CC", "P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)", OF, "Anam"]
SAMPLES = ["NEPSE", "NIFTY50", "SP500", "DSE 2023-2026", "Vietnam 2007-2020", "DSE 2009-2021", "Morocco 2012-2026"]
FROZEN_TABLE = {"NEPSE": "table101_anam_holdout_forecast.csv", "NIFTY50": "table101_anam_holdout_forecast.csv",
                "SP500": "table101_anam_holdout_forecast.csv", "DSE 2023-2026": "table108_anam_frontier_forecast.csv",
                "Vietnam 2007-2020": "table108_anam_frontier_forecast.csv",
                "DSE 2009-2021": "table108_anam_frontier_forecast.csv",
                "Morocco 2012-2026": "table113_anam_morocco_forecast.csv"}
RETURN_ONLY = ["CC", "EWMA", "GARCH", "GJR", "HAR-CC"]
RANGE = ["P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)", "Anam", OF, "TR-P", "HAR-open-free",
         "Anam posterior (exploratory)"]
COMBO = "1/2 CC + 1/2 open-free"
MODELS = RETURN_ONLY + RANGE + [COMBO]


# --------------------------------------------------------------------------------------------
# Samples
# --------------------------------------------------------------------------------------------

def nepse_calendar() -> pd.DatetimeIndex:
    cal = pd.read_csv(ROOT / "data" / "processed" / "nepse_trading_calendar.csv", parse_dates=["date"])
    return pd.DatetimeIndex(cal.loc[cal["is_session"], "date"])


def load(name: str) -> dict:
    """One sample, built exactly as by scripts 40, 42 and 43, with its session ordinals."""
    if name == "NEPSE":
        d = s40.nepse()
        ses = EV.session_ordinal(d["date"], nepse_calendar())
        train = d["regime"].isin(["A1", "B"])
        spans = {"A2+C": d["regime"].isin(["A2", "C"]), "A2": d["regime"] == "A2", "C": d["regime"] == "C"}
        mode, liq, primary = "panel", d["n_trades"], "A2+C"
    elif name in ("NIFTY50", "SP500"):
        d = s40.nifty() if name == "NIFTY50" else s40.sp500()
        ses = EV.session_ordinal(d["date"])
        train, spans = d["span"] == "train", {"test half": d["span"] == "test"}
        mode, liq, primary = "series", None, "test half"
    else:
        d, _ = F.market_panel(name, INPUTS)
        ses = d["session"].astype(int)
        # the panel's sessions are its own calendar: one ordinal per date, increasing with the date
        chk = d.groupby("date")["session"].nunique()
        assert (chk == 1).all() and d.groupby("session")["date"].nunique().max() == 1
        train, spans = d["span"] == "train", {"test half": d["span"] == "test"}
        mode, liq, primary = "panel", d["volume"], "test half"
    d = d.copy()
    d["ses"] = np.asarray(ses, dtype=int)
    return dict(name=name, d=d, train=train, spans=spans, mode=mode, liq=liq, primary=primary)


# --------------------------------------------------------------------------------------------
# Part A: the frozen arithmetic with one correction at a time
# --------------------------------------------------------------------------------------------

def frozen_parts(d, X, win, scheme):
    """kappa, cur and lr exactly as nepsevol.volforecast.fair_forecast_test computes them."""
    sym, r2 = d["symbol"], d["CC"]
    X = X.reindex(d.index)
    valid = X.notna() & r2.notna()
    Xv, rv = X.where(valid), r2.where(valid)
    cur = Xv.groupby(sym, sort=False).transform(lambda z: z.rolling(win, min_periods=win).mean())
    sX = trailing_sum(Xv, sym, LONGRUN_SESSIONS, LONGRUN_MIN)
    nX = Xv.notna().astype(float).groupby(sym, sort=False).transform(
        lambda z: z.rolling(LONGRUN_SESSIONS, min_periods=LONGRUN_MIN).sum())
    lr = sX / nX
    kind, L = scheme
    if kind == "pool":
        num, den = rv.groupby(d["date"]).sum(), Xv.groupby(d["date"]).sum()
        kap = num.rolling(L, min_periods=min(20, L)).sum() / den.rolling(L, min_periods=min(20, L)).sum()
        kappa = d["date"].map(kap)
    else:
        kappa = trailing_sum(rv, sym, L, min(60, L)) / trailing_sum(Xv, sym, L, min(60, L))
    return kappa, cur, lr


def norm_q(y, f):
    q = y / f
    return q - np.log(q) - 1


def staged(d, est, train, test, span_end, win, scheme, step, cut, parts=None, tgt=None, parts_c=None, tgt_c=None):
    """The frozen evaluation with corrections S1..S4 switched on cumulatively (plan, Part A).

    ``cut`` = (date, session) of the sample's first test session: training outcomes must end before it,
    for every test span of the sample, so that one fitted phi serves them all. From S3 on, the components
    and the target come from ``parts_c`` and ``tgt_c``, built with squared residues of equal prices set to
    zero and exact rolling means (``Kernel``), so that "lr > 0" means a positive long-run level. Returns the
    per-estimator table (phi, n, losses, differences, t) and the per-estimator test losses."""
    sym, r2, date = d["symbol"], d["CC"], d["date"]
    if parts is None:
        parts = {k: frozen_parts(d, X, win, scheme) for k, X in est.items()}
    if step >= 3:
        parts = parts_c
        tgt = tgt_c
    trm = train.reindex(d.index).fillna(False).astype(bool)
    tem = test.reindex(d.index).fillna(False).astype(bool)
    test_start, cutoff = cut
    if step >= 2:
        if tgt is None:
            tgt = EV.forward_target(r2, sym, d["ses"], win)
        fut = tgt["y"]
        trm = trm & (tgt["end_session"] < cutoff)
        tem = tem & (tgt["end_session"] <= span_end)
    else:
        fut = r2.groupby(sym, sort=False).transform(
            lambda z: z[::-1].rolling(win, min_periods=win).mean()[::-1].shift(-1))
        if step >= 1:
            end_row = date.groupby(sym, sort=False).shift(-win)
            trm = trm & (end_row < test_start)
    if step <= 2:
        ok_all = fut.notna() & (fut > 0)
        for kappa, cur, lr in parts.values():
            ok_all &= kappa.notna() & cur.notna() & lr.notna() & (kappa * cur > 0) & (lr > 0)
    else:
        ok_all = fut.notna()
        for kappa, cur, lr in parts.values():
            ok_all &= kappa.notna() & cur.notna() & lr.notna() & (kappa > 0) & (lr > 0)
    rows, losses = [], {}
    for name, (kappa, cur, lr) in parts.items():
        fc = lambda p: kappa * (p * cur + (1 - p) * lr)
        if step <= 2:
            def loss(p, m):
                f = fc(p)
                ok = m & ok_all & (f > 0)
                return norm_q(fut[ok], f[ok])
            best = min(FROZEN_GRID, key=lambda p: loss(p, trm).mean())
            ql = loss(best, tem)
            canon = EV.qlike_canonical(fut[ql.index], fc(best)[ql.index])
            losses[name] = pd.Series(ql.to_numpy(), index=ql.index)
            rows.append(dict(estimator=name, phi=float(best), n=int(len(ql)), QLIKE=float(ql.mean()),
                             QLIKE_canonical=float(np.mean(canon)), n_train=int((trm & ok_all).sum())))
        else:
            best, _, rej = EV.select_by_loss(PHI, fut, trm & ok_all, fc)
            m = tem & ok_all
            f = fc(best)[m]
            canon = pd.Series(EV.qlike_canonical(fut[m], f), index=f.index)
            nq = EV.qlike_normalized(fut[m], f)
            losses[name] = canon
            rows.append(dict(estimator=name, phi=float(best), n=int(m.sum()), QLIKE=float(np.nanmean(nq)),
                             QLIKE_canonical=float(canon.mean()), n_train=int((trm & ok_all).sum()),
                             rejected_candidates=int(rej), zero_targets=int((fut[m] == 0).sum())))
    t = pd.DataFrame(rows).set_index("estimator")
    for ref in ("CC", "P", "Anam", OF):
        for name, ql in losses.items():
            j = losses[ref].index.intersection(ql.index)
            diff = ql.loc[j] - losses[ref].loc[j]
            if step <= 3:
                per_date = pd.DataFrame({"diff": diff, "date": date[j]}).groupby("date")["diff"].mean().sort_index()
                tt = nw_t(per_date.to_numpy(), lags=win)
            else:
                tt = EV.weighted_mean_se(diff, date[j], lags=2 * win)["t"]
            t.loc[name, f"dQLIKE_vs_{ref}"] = float(diff.mean())
            t.loc[name, f"t_vs_{ref}"] = tt
    return t, losses


def verdict(dq, t):
    if not np.isfinite(t):
        return "no significant difference"
    if dq < 0 and t < -1.96:
        return "beats"
    if dq > 0 and t > 1.96:
        return "loses to"
    return "no significant difference"


def part_a(S, frozen_tab):
    d, mode = S["d"], S["mode"]
    scheme = ("pool", AN.POOL_SESSIONS) if mode == "panel" else ("series", AN.SERIES_SESSIONS)
    est, _ = s40.estimator_set(d, mode)
    rows, verdicts = [], []
    first = S["spans"][S["primary"]]
    cut = (d.loc[first, "date"].min(), int(d.loc[first, "ses"].min()))
    for win in WINDOWS:
        parts = {k: frozen_parts(d, X, win, scheme) for k, X in est.items()}
        tgt = EV.forward_target(d["CC"], d["symbol"], d["ses"], win)
        parts_c = {}
        for k, X in est.items():
            kk = Kernel(d, X, win, mode)
            parts_c[k] = (kk.kappa, kk.cur, kk.lr)
        tgt_c = EV.forward_target(FB.clean_square(d["CC"]), d["symbol"], d["ses"], win)
        for span, test in S["spans"].items():
            span_end = int(d.loc[test, "ses"].max())
            # S0 must be the frozen test, first through the frozen function itself
            ref, _ = fair_forecast_test(d, est, S["train"], test, win=win, scheme=scheme, refs=("Anam", "P", "CC"))
            fz = frozen_tab[(frozen_tab.market == S["name"]) & (frozen_tab.test_span == span) &
                            (frozen_tab.window == win)].set_index("estimator")
            for e in FROZEN9:
                assert abs(ref.loc[e, "QLIKE"] - fz.loc[e, "QLIKE"]) < 1e-9, (S["name"], span, win, e)
                assert abs(ref.loc[e, "phi"] - fz.loc[e, "phi"]) < 1e-12 and int(ref.loc[e, "n"]) == int(fz.loc[e, "n"])
            steps = {}
            for step in range(5):
                t, _ = staged(d, est, S["train"], test, span_end, win, scheme, step, cut, parts=parts, tgt=tgt,
                              parts_c=parts_c, tgt_c=tgt_c)
                if step == 0:
                    for e in FROZEN9:
                        assert abs(t.loc[e, "QLIKE"] - ref.loc[e, "QLIKE"]) < 1e-12, ("S0", S["name"], span, win, e)
                        assert abs(t.loc[e, "t_vs_CC"] - ref.loc[e, "t_vs_CC"]) < 1e-9 or not np.isfinite(ref.loc[e, "t_vs_CC"])
                steps[step] = t
                tt = t.reset_index()
                tt.insert(0, "step", f"S{step}")
                tt.insert(0, "window", win)
                tt.insert(0, "span", span)
                tt.insert(0, "market", S["name"])
                rows.append(tt)
            for a in ("Anam", OF):
                for b in FROZEN9:
                    if b == a:
                        continue
                    v = {}
                    for step in (0, 4):
                        t = steps[step]
                        dq, tv = t.loc[a, f"dQLIKE_vs_{b}"] if f"dQLIKE_vs_{b}" in t else -t.loc[b, f"dQLIKE_vs_{a}"], \
                            t.loc[a, f"t_vs_{b}"] if f"t_vs_{b}" in t else -t.loc[b, f"t_vs_{a}"]
                        v[step] = (dq, tv, verdict(dq, tv))
                    verdicts.append(dict(market=S["name"], span=span, window=win, estimator=a, rival=b,
                                         dQLIKE_frozen=v[0][0], t_frozen=v[0][1], verdict_frozen=v[0][2],
                                         dQLIKE_corrected=v[4][0], t_corrected=v[4][1], verdict_corrected=v[4][2],
                                         changed=v[0][2] != v[4][2]))
    return pd.concat(rows, ignore_index=True), pd.DataFrame(verdicts)


# --------------------------------------------------------------------------------------------
# Part B: the seventeen forecasts
# --------------------------------------------------------------------------------------------

class Kernel:
    """A calibrated, shrunk kernel forecast: kappa (phi cur + (1 - phi) lr)."""

    def __init__(self, d, X, win, mode, kappa=None):
        sym, r2 = d["symbol"], FB.clean_square(d["CC"])
        X = FB.clean_square(X.reindex(d.index))
        valid = X.notna() & r2.notna()
        Xv = X.where(valid)
        self.cur = FB.rolling_rows(Xv, sym, win)
        self.lr = FB.rolling_rows(Xv, sym, LONGRUN_SESSIONS, LONGRUN_MIN)
        if kappa is None:
            kappa = (FB.pooled_kappa(Xv, r2, d["date"], AN.POOL_SESSIONS, AN.MIN_POOL_DATES) if mode == "panel"
                     else FB.series_kappa(Xv, r2, sym, AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS))
        self.kappa = kappa if isinstance(kappa, pd.Series) else pd.Series(float(kappa), index=d.index)
        self.defined = (self.kappa.notna() & self.cur.notna() & self.lr.notna() & (self.kappa > 0) & (self.lr > 0))
        self.grid = PHI

    def forecast(self, phi):
        return self.kappa * (phi * self.cur + (1 - phi) * self.lr)


class HAR:
    """kappa (c1 X + c2 mean5 + c3 mean22 + c4 lr), convex weights with c4 >= 0.1."""

    def __init__(self, d, X, kappa):
        X = FB.clean_square(X)
        comp = FB.har_components(X.where(X.notna() & d["CC"].notna()), d["symbol"])
        self.c = comp
        self.kappa = kappa if isinstance(kappa, pd.Series) else pd.Series(float(kappa), index=d.index)
        self.defined = comp.notna().all(axis=1) & (comp["lr"] > 0) & self.kappa.notna() & (self.kappa > 0)
        self.grid = FB.simplex_grid()

    def forecast(self, w):
        c = self.c
        return self.kappa * (w[0] * c["d1"] + w[1] * c["m5"] + w[2] * c["m22"] + w[3] * c["lr"])


class Recursion:
    """EWMA or variance-targeted (GJR-)GARCH, run in calendar time and read at each row."""

    def __init__(self, d, kind, win, vbar):
        self.kind, self.win = kind, win
        codes, _ = pd.factorize(d["symbol"])
        self.codes, self.ses = codes, d["ses"].to_numpy()
        T, N = int(self.ses.max()) + 1, int(codes.max()) + 1
        r = d["r"].where(~(d["r"].abs() < FB.ZERO_SQUARE ** 0.5), 0.0)
        self.R = FB.to_matrix(r, codes, self.ses, T, N)
        self.V = FB.to_matrix(vbar, codes, self.ses, T, N, ffill=True)
        self.vrow = vbar.to_numpy()
        self.index = d.index
        self.defined = vbar.notna() & (vbar > 0)
        self.grid = (FB.EWMA_GRID if kind == "EWMA" else FB.GARCH_GRID if kind == "GARCH" else FB.GJR_GRID)
        self._cache = {}

    def forecast(self, par):
        if par not in self._cache:
            if self.kind == "EWMA":
                s1 = FB.from_matrix(FB.ewma_path(self.R, self.V, par), self.codes, self.ses)
                f = s1
            else:
                a, b, g = par
                s1 = FB.from_matrix(FB.garch_path(self.R, self.V, a, b, g), self.codes, self.ses)
                f = FB.h_step_mean(s1, self.vrow, a + b + g / 2, self.win)
            self._cache = {par: pd.Series(f, index=self.index)}
        return self._cache[par]


class Fixed:
    """A forecast with nothing left to choose."""

    def __init__(self, f, defined):
        self.f, self.defined, self.grid = f, defined, (None,)

    def forecast(self, _):
        return self.f


def kernels_for(d, mode, b):
    est, _ = s40.estimator_set(d, mode)
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]
    k = dict(est)
    k["TR-P"] = FB.tr_parkinson(o, u, dd)
    m2 = FB.rolling_rows(FB.clean_square((o * o).where(o.notna())), d["symbol"], LONGRUN_SESSIONS, LONGRUN_MIN)
    k["Anam posterior (exploratory)"] = FB.posterior_kernel(o, c, u, dd, b, m2)
    return k


def build_models(S, win):
    d, mode = S["d"], S["mode"]
    b = (AN.open_quality_panel(d["o"], d["r"], d["date"]) if mode == "panel"
         else AN.open_quality_series(d["o"], d["r"], d["symbol"]))
    K = kernels_for(d, mode, b)
    M = {}
    for name in ["CC", "P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)", "Anam", OF, "TR-P",
                 "Anam posterior (exploratory)"]:
        M[name] = Kernel(d, K[name], win, mode)
    vbar = M["CC"].lr
    for kind in ("EWMA", "GARCH", "GJR"):
        M[kind] = Recursion(d, kind, win, vbar)
    M["HAR-CC"] = HAR(d, K["CC"], 1.0)
    M["HAR-open-free"] = HAR(d, K[OF], M[OF].kappa)
    return M, K, b


def select(model, y, rows):
    if model.grid == (None,):
        return None, float(np.mean(EV.qlike_canonical(y[rows], model.forecast(None)[rows]))), 0
    return EV.select_by_loss(model.grid, y, rows, model.forecast)


def part_b(S, idx, n_boot):
    d = S["d"]
    out = dict(comparison=[], mcs=[], claims=[], ablations=[], coverage=[], inference=[])
    for win in WINDOWS:
        t0 = time.time()
        M, K, b = build_models(S, win)
        tgt = EV.forward_target(FB.clean_square(d["CC"]), d["symbol"], d["ses"], win)
        y = tgt["y"]
        first_test = {sp: int(d.loc[m, "ses"].min()) for sp, m in S["spans"].items()}
        cutoff = min(first_test.values())
        defined_all = pd.Series(True, index=d.index)
        for m in M.values():
            defined_all &= m.defined.reindex(d.index).fillna(False).astype(bool)
        train_rows = S["train"] & defined_all & y.notna() & (tgt["end_session"] < cutoff)
        params, train_loss = {}, {}
        for name, m in M.items():
            p, L, _ = select(m, y, train_rows)
            params[name], train_loss[name] = p, L
        # the combination of the two selected forecasts, fixed weights
        f_combo = 0.5 * M["CC"].forecast(params["CC"]) + 0.5 * M[OF].forecast(params[OF])
        M[COMBO] = Fixed(f_combo, M["CC"].defined & M[OF].defined)
        params[COMBO] = None
        train_loss[COMBO] = float(np.mean(EV.qlike_canonical(y[train_rows], f_combo[train_rows])))
        fc = {name: M[name].forecast(params[name]) for name in MODELS}
        # Part C models, tuned on the same training rows
        abl = ablation_models(S, M, K, win, params)
        abl_params = {}
        for name, m in abl.items():
            p, L, _ = select(m, y, train_rows & m.defined)
            abl_params[name] = p
        abl_fc = {name: m.forecast(abl_params[name]) for name, m in abl.items()}
        r_star = min(RETURN_ONLY, key=lambda k: train_loss[k])
        g_star = min(RANGE, key=lambda k: train_loss[k])
        for span, span_mask in S["spans"].items():
            span_end = int(d.loc[span_mask, "ses"].max())
            inside = tgt["end_session"] <= span_end
            test_rows = span_mask & defined_all & y.notna() & inside
            n_test = int(test_rows.sum())
            if n_test == 0:
                continue
            dates = d.loc[test_rows, "date"]
            L = {name: pd.Series(EV.qlike_canonical(y[test_rows], fc[name][test_rows]), index=dates.index)
                 for name in MODELS}
            NQ = {name: np.nanmean(EV.qlike_normalized(y[test_rows], fc[name][test_rows])) for name in MODELS}
            cc_norm = NQ["CC"]
            for name in MODELS:
                row = dict(market=S["name"], span=span, window=win, model=name,
                           cls="return-only" if name in RETURN_ONLY else "range-based" if name in RANGE else "combination",
                           parameters=str(params[name]), train_loss=train_loss[name], n_train=int(train_rows.sum()),
                           n=n_test, n_dates=int(dates.nunique()), zero_targets=int((y[test_rows] == 0).sum()),
                           QLIKE_canonical=float(L[name].mean()), QLIKE=float(NQ[name]))
                for ref in ("CC", "Anam", OF):
                    r = EV.weighted_mean_se(L[name] - L[ref], dates, lags=2 * win)
                    row[f"d_vs_{ref}"], row[f"t_vs_{ref}"] = r["mean"], r["t"]
                out["comparison"].append(row)
            # Rule B2
            Sm = EV.date_sums(pd.DataFrame(L), dates)
            W = Sm.pop("_W")
            mcs = EV.model_confidence_set(Sm, W, alpha=(0.10, 0.25), n_boot=n_boot,
                                          mean_block=max(2 * win, 10), seed=SEED + 100 * idx + win)
            mcs.insert(0, "window", win)
            mcs.insert(0, "span", span)
            mcs.insert(0, "market", S["name"])
            out["mcs"].append(mcs)
            # Rule B1
            r = EV.weighted_mean_se(L[g_star] - L[r_star], dates, lags=2 * win)
            v = ("range adds information" if r["mean"] < 0 and r["t"] < -1.96 else
                 "returns suffice" if r["mean"] > 0 and r["t"] > 1.96 else "no significant difference")
            out["claims"].append(dict(rule="B1", market=S["name"], span=span, window=win,
                                      primary=span == S["primary"], detail=f"g* = {g_star}; r* = {r_star}",
                                      estimate=r["mean"], t=r["t"], verdict=v))
            # Rule B4
            for form in ("Anam", OF):
                r = EV.weighted_mean_se(L[form] - L["CC"], dates, lags=2 * win)
                margin = 0.01 * cc_norm
                lo, hi = r["mean"] - 1.645 * r["se"], r["mean"] + 1.645 * r["se"]
                out["claims"].append(dict(rule="B4", market=S["name"], span=span, window=win,
                                          primary=span == S["primary"], detail=f"{form} - CC; margin +/-{margin:.5f}",
                                          estimate=r["mean"], t=r["t"], lo90=lo, hi90=hi, margin=margin,
                                          verdict="practically equivalent" if (lo > -margin and hi < margin)
                                          else "not shown equivalent"))
            # Part C
            for label, a, bb in CONTRASTS:
                if a not in abl_fc and a not in fc:
                    continue
                fa = abl_fc.get(a, fc.get(a))
                fb = abl_fc.get(bb, fc.get(bb))
                ok = test_rows & fa.notna() & fb.notna() & (fa > 0) & (fb > 0)
                la = pd.Series(EV.qlike_canonical(y[ok], fa[ok]), index=d.index[ok])
                lb = pd.Series(EV.qlike_canonical(y[ok], fb[ok]), index=d.index[ok])
                r = EV.weighted_mean_se(la - lb, d.loc[ok, "date"], lags=2 * win)
                out["ablations"].append(dict(market=S["name"], span=span, window=win, contrast=label, model=a,
                                             reference=bb, parameters=str(abl_params.get(a, params.get(a))),
                                             n=int(ok.sum()), difference=r["mean"], t=r["t"],
                                             verdict=verdict(r["mean"], r["t"])))
            # Part E
            for a, bb in (("Anam", "CC"), (OF, "CC"), (OF, "Anam"), (g_star, r_star)):
                out["inference"] += inference_rows(S, span, win, a, bb, L, dates, d, test_rows, first_test[span])
            # Part D
            out["coverage"] += coverage_rows(S, span, win, span_mask, tgt, inside, defined_all, M, y)
        print(f"    {S['name']} h={win}: r* {r_star}, g* {g_star}; {time.time() - t0:.0f}s")
    return out


CONTRASTS = [
    ("calibration", "P raw", "P"), ("calibration", "open-free raw", OF),
    ("previous-close anchor", "TR-P", "P"), ("r^2 blend", OF, "TR-P"),
    ("estimated b against b = 0", "Anam", OF), ("estimated b against b = 1", "Anam", "o2+P"),
    ("cross-sectional pooling", "open-free, own calibration", OF),
    ("adaptive scale", "open-free, constant calibration", OF),
    ("dynamics: HAR against phi", "HAR-open-free", OF), ("dynamics: HAR against phi", "HAR-CC", "CC"),
    ("measurement with common dynamics", "open-free, CC's phi", "CC"),
    ("measurement with common dynamics", "Anam, CC's phi", "CC"),
    ("residual uncertainty", "Anam posterior (exploratory)", "Anam"),
]


def ablation_models(S, M, K, win, params):
    d, mode = S["d"], S["mode"]
    A = {}
    A["P raw"] = Kernel(d, K["P"], win, mode, kappa=1.0)
    A["open-free raw"] = Kernel(d, K[OF], win, mode, kappa=1.0)
    if mode == "panel":
        Xc, rc = FB.clean_square(K[OF]), FB.clean_square(d["CC"])
        own = FB.series_kappa(Xc.where(Xc.notna() & rc.notna()), rc, d["symbol"], AN.SERIES_SESSIONS,
                              AN.MIN_SERIES_SESSIONS)
        A["open-free, own calibration"] = Kernel(d, K[OF], win, mode, kappa=own)
    first = d.loc[pd.concat(list(S["spans"].values()), axis=1).any(axis=1), "date"].min()
    k0 = FB.constant_kappa(FB.clean_square(K[OF]), FB.clean_square(d["CC"]), S["train"] & (d["date"] < first))
    A["open-free, constant calibration"] = Kernel(d, K[OF], win, mode, kappa=k0)
    for name, base in (("open-free, CC's phi", OF), ("Anam, CC's phi", "Anam")):
        m = M[base]
        A[name] = Fixed(m.forecast(params["CC"]), m.defined)
    return A


def inference_rows(S, span, win, a, b, L, dates, d, test_rows, first_ses):
    diff = L[a] - L[b]
    rows = []
    base = dict(market=S["name"], span=span, window=win, model=a, reference=b)
    g = pd.DataFrame({"u": diff - diff.mean(), "date": dates}).groupby("date")["u"].sum().sort_index()
    andrews = EV.andrews_bandwidth(g.to_numpy(), floor=win)
    for label, lags in (("stock-day, L = h", win), ("stock-day, L = 2h (primary)", 2 * win),
                        ("stock-day, L = 4h", 4 * win), (f"stock-day, Andrews L = {andrews}", andrews)):
        r = EV.weighted_mean_se(diff, dates, lags=lags)
        rows.append(dict(base, estimand=label, mean=r["mean"], se=r["se"], t=r["t"], n=r["n"], n_dates=r["n_dates"]))
    n_t = dates.map(dates.value_counts())
    r = EV.weighted_mean_se(diff, dates, weights=1.0 / n_t, lags=2 * win)
    rows.append(dict(base, estimand="equal-date mean, L = 2h", mean=r["mean"], se=r["se"], t=r["t"], n=r["n"],
                     n_dates=r["n_dates"]))
    sec = d.loc[diff.index, "symbol"]
    n_i = sec.map(sec.value_counts())
    r = EV.weighted_mean_se(diff, dates, weights=1.0 / n_i, lags=2 * win)
    rows.append(dict(base, estimand="equal-security mean, L = 2h", mean=r["mean"], se=r["se"], t=r["t"], n=r["n"],
                     n_dates=r["n_dates"]))
    keep = ((d.loc[diff.index, "ses"] - first_ses) % win) == 0
    sub = diff[keep]
    T = int(dates[keep].nunique())
    lags = max(1, int(4 * (max(T, 1) / 100) ** (2 / 9)))
    r = EV.weighted_mean_se(sub, dates[keep], lags=lags)
    rows.append(dict(base, estimand=f"non-overlapping origins, stock-day, L = {lags}", mean=r["mean"], se=r["se"],
                     t=r["t"], n=r["n"], n_dates=r["n_dates"]))
    return rows


def liquidity_groups(S):
    d = S["d"]
    if S["liq"] is None:
        return pd.Series("index", index=d.index)
    med = S["liq"][S["train"]].groupby(d.loc[S["train"], "symbol"]).median()
    q = pd.qcut(med.rank(method="first"), 3, labels=["low", "middle", "high"])
    g = d["symbol"].map(q).astype(object)
    return g.where(g.notna(), "no training bars")


def coverage_rows(S, span, win, span_mask, tgt, inside, defined_all, M, y):
    d = S["d"]
    grp = liquidity_groups(S)
    reason = pd.Series(tgt["reason"], index=d.index).astype(object)
    reason = reason.where(~((reason == "complete") & ~inside), "outcome beyond the span")
    zero_level = pd.Series(False, index=d.index)
    for m in M.values():
        if isinstance(m, Kernel):
            zero_level |= (m.lr == 0) | (m.kappa == 0)
    status = np.where(reason != "complete", reason,
                      np.where(defined_all, "eligible",
                               np.where(zero_level, "excluded: zero long-run level or calibration",
                                        "excluded: a forecast not yet defined")))
    x = pd.DataFrame({"status": status, "group": grp, "zero": (y == 0) & defined_all & (reason == "complete")})[span_mask]
    rows = []
    for g, gx in list(x.groupby("group")) + [("all", x)]:
        cnt = gx["status"].value_counts()
        row = dict(market=S["name"], span=span, window=win, liquidity=g, origins=int(len(gx)),
                   securities=int(d.loc[gx.index, "symbol"].nunique()))
        for k in ("eligible", "missing session", "missing return", "beyond data", "outcome beyond the span",
                  "excluded: a forecast not yet defined", "excluded: zero long-run level or calibration"):
            row[k] = int(cnt.get(k, 0))
        row["eligible share"] = row["eligible"] / max(row["origins"], 1)
        row["zero targets among eligible"] = int(gx["zero"].sum())
        rows.append(row)
    return rows


# --------------------------------------------------------------------------------------------
# Rule B3 and the run
# --------------------------------------------------------------------------------------------

def holm(cmp: pd.DataFrame, primary: dict) -> list:
    out = []
    for form in ("Anam", OF):
        fam = []
        for mk, sp in primary.items():
            r = cmp[(cmp.market == mk) & (cmp.span == sp) & (cmp.window == 5) & (cmp.model == form)]
            if len(r):
                t = float(r["t_vs_CC"].iloc[0])
                fam.append((mk, t, 0.5 * math.erfc(-t / math.sqrt(2))))     # one-sided p = Phi(t)
        order = sorted(fam, key=lambda z: z[2])
        m, running = len(order), 0.0
        for i, (mk, t, p) in enumerate(order):
            running = max(running, min(1.0, (m - i) * p))
            out.append(dict(rule="B3", market=mk, span=primary[mk], window=5, primary=True,
                            detail=f"{form} beats CC (one-sided), Holm over {m} samples", estimate=np.nan, t=t,
                            p_one_sided=p, p_holm=running,
                            verdict="beats after Holm" if running < 0.025 else "not after Holm"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", nargs="*", default=SAMPLES)
    ap.add_argument("--boot", type=int, default=N_BOOT)
    a = ap.parse_args()
    print("M20 CORRECTED EVALUATION (frozen plan, commit 984dfbc)")
    if not INPUTS.exists():
        print("  data/external/frontier/ is missing: the four frontier samples are skipped (partial run)")
    A_rows, V_rows, B = [], [], dict(comparison=[], mcs=[], claims=[], ablations=[], coverage=[], inference=[])
    primary = {}
    done = []
    for idx, name in enumerate(SAMPLES):
        if name not in a.samples:
            continue
        if name not in ("NEPSE", "NIFTY50", "SP500") and not INPUTS.exists():
            continue
        t0 = time.time()
        S = load(name)
        primary[name] = S["primary"]
        frozen_tab = pd.read_csv(TAB / FROZEN_TABLE[name])
        steps, verd = part_a(S, frozen_tab)
        A_rows.append(steps)
        V_rows.append(verd)
        print(f"  {name}: Part A done ({time.time() - t0:.0f}s); S0 reproduces {FROZEN_TABLE[name]}")
        out = part_b(S, idx, a.boot)
        for k in B:
            B[k] += out[k]
        done.append(name)
        print(f"  {name}: done in {time.time() - t0:.0f}s")
    steps = pd.concat(A_rows, ignore_index=True)
    verd = pd.concat(V_rows, ignore_index=True)
    cmp = pd.DataFrame(B["comparison"])
    mcs = pd.concat(B["mcs"], ignore_index=True)
    claims = pd.DataFrame(B["claims"] + holm(cmp, primary))
    abl = pd.DataFrame(B["ablations"])
    cov = pd.DataFrame(B["coverage"])
    inf = pd.DataFrame(B["inference"])
    if set(done) != set(SAMPLES):
        print(f"  PARTIAL RUN: computed {done}; the tables are written with a _partial suffix")
    suffix = "" if set(done) == set(SAMPLES) else "_partial"
    for df, fname in ((steps, "table125_m20_correction_steps"), (verd, "table126_m20_verdict_changes"),
                      (cmp, "table127_m20_comparison"), (mcs, "table128_m20_mcs"), (claims, "table129_m20_claims"),
                      (abl, "table130_m20_ablations"), (cov, "table131_m20_coverage"),
                      (inf, "table132_m20_inference")):
        df.to_csv(TAB / f"{fname}{suffix}.csv", index=False, float_format=FLOAT_FMT)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_colwidth", 80)
    print("\nRULE A: verdicts that change between the frozen and the corrected evaluation")
    ch = verd[verd["changed"]]
    print(ch[["market", "span", "window", "estimator", "rival", "verdict_frozen", "t_frozen", "verdict_corrected",
              "t_corrected"]].to_string(index=False, float_format=lambda v: f"{v:.2f}") if len(ch) else "  none")
    print("\nPART A, S4 against S0 for the two forms against close-to-close")
    s = steps[steps.estimator.isin(["Anam", OF]) & steps.step.isin(["S0", "S1", "S2", "S3", "S4"])]
    print(s.pivot_table(index=["market", "span", "window", "estimator"], columns="step",
                        values="t_vs_CC").round(2).to_string())
    print("\nRULES B1, B3, B4")
    print(claims.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nRULE B2: the 90% model confidence set, by sample")
    for (mk, sp, w), g in mcs.groupby(["market", "span", "window"], sort=False):
        ins = g[g["in_mcs_90"]].sort_values("loss")["model"].tolist()
        print(f"  {mk} [{sp}] h={w}: {ins}")
    print("\nPART C")
    print(abl.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
