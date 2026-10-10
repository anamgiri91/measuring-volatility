"""E8: the candidate second-generation system end to end, against the frozen open-free HAR and against the best
return-only forecast chosen on the fit span (the B1 question in development)."""
import sys, time, itertools
NAME = sys.argv[1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def kappa_for(d, X, mode):
    Xc, r2 = FB.clean_square(X), FB.clean_square(d["CC"])
    v = Xc.notna() & r2.notna()
    if mode == "panel":
        return FB.pooled_kappa(Xc.where(v), r2, d["date"], AN.POOL_SESSIONS, AN.MIN_POOL_DATES)
    return FB.series_kappa(Xc.where(v), r2, d["symbol"], AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)

def har_Z(d, X, factor):
    Xc = FB.clean_square(X)
    comp = FB.har_components(Xc.where(Xc.notna() & d["CC"].notna()), d["symbol"])
    if not factor:
        return comp[["d1", "m5", "m22", "lr"]]
    M5 = market_state(comp["m5"] / comp["lr"], d["date"]); M22 = market_state(comp["m22"] / comp["lr"], d["date"])
    return pd.DataFrame({"d1": comp["d1"], "m5": comp["m5"], "m22": comp["m22"], "lrM5": comp["lr"] * M5,
                         "lrM22": comp["lr"] * M22, "lr": comp["lr"]})

class SelfTuned:
    """Fit each candidate on the fit rows; keep the one with the lowest fit loss."""
    def __init__(self, cands: dict):
        self.cands = cands
        self.defined = None
        for m in cands.values():
            self.defined = m.defined if self.defined is None else (self.defined & m.defined)
        self.grid = "continuous"
    def fit(self, y, rows):
        best = None
        for k, m in self.cands.items():
            p, L = m.fit(y, rows)
            if best is None or L < best[2]:
                best = (k, p, L)
        self.choice = best
        return np.array([0.0]), best[2]
    def forecast(self, _):
        k, p, _L = self.choice
        return self.cands[k].forecast(p)

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    sym = d["symbol"]; zero = pd.Series(0.0, index=d.index)
    oM = loo_market(o, d["date"]).fillna(0.0) if mode == "panel" else zero
    XOF = AN.kernel(o, c, u, dd, zero)
    models = {"HAR-OF": LinearConvex(har_Z(d, XOF, False), kappa_for(d, XOF, mode))}
    if mode == "panel":
        models["FHAR-OF"] = LinearConvex(har_Z(d, XOF, True), kappa_for(d, XOF, mode))
    thetas = (0.0, 0.5, 1.0) if mode == "panel" else (0.0,)
    for factor in ((False, True) if mode == "panel" else (False,)):
        cands = {}
        for th, w in itertools.product(thetas, (0.2, 0.3, 0.4)):
            X = bar_kernel(o, c, u, dd, th * oM, w, exclude=0.0, overnight=(th > 0), zero_range_r2=True)
            cands[f"theta{th}|w{w}"] = LinearConvex(har_Z(d, X, factor), kappa_for(d, X, mode))
        models[("F" if factor else "") + "ANAM2"] = SelfTuned(cands)
    compR = FB.har_components(FB.clean_square(d["CC"]), sym)
    models["HAR-CC"] = LinearConvex(compR[["d1", "m5", "m22", "lr"]], 1.0)
    if mode == "panel":
        models["FHAR-CC"] = LinearConvex(har_Z(d, d["CC"], True), 1.0)
    vb = FB.rolling_rows(FB.clean_square(d["CC"]), sym, s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
    rows = []
    for win in (5, 21):
        mm = dict(models); mm["GJR"] = s47.Recursion(d, "GJR", win, vb)
        tgt = EV.forward_target(FB.clean_square(d["CC"]), sym, d["ses"], win); y = tgt["y"]
        defined = pd.Series(True, index=d.index)
        for m in mm.values():
            defined &= m.defined.reindex(d.index).fillna(False).astype(bool)
        for k, (fit_m, val_m) in enumerate(D["masks"]):
            v0, v1 = int(d.loc[val_m, "ses"].min()), int(d.loc[val_m, "ses"].max())
            fit_rows = fit_m & defined & y.notna() & ((tgt["end_session"] < v0) if d.loc[fit_m, "ses"].min() < v0 else True)
            val_rows = val_m & defined & y.notna() & (tgt["end_session"] <= v1)
            dates = d.loc[val_rows, "date"]
            F, fitL, info = {}, {}, {}
            for nm, m in mm.items():
                if getattr(m, "grid", None) == "continuous":
                    p, L = m.fit(y, fit_rows)
                else:
                    p, L, _ = EV.select_by_loss(m.grid, y, fit_rows, m.forecast)
                F[nm] = m.forecast(p); fitL[nm] = L
                if isinstance(m, SelfTuned):
                    info[nm] = m.choice[0]
            ret = [n for n in F if n in ("HAR-CC", "FHAR-CC", "GJR")]
            rstar = min(ret, key=lambda n: fitL[n])
            F["r*"] = F[rstar]; info["r*"] = rstar
            best2 = "FANAM2" if "FANAM2" in F else "ANAM2"
            F["1/2 " + best2 + " + 1/2 r*"] = 0.5 * F[best2] + 0.5 * F[rstar]
            L = {n: pd.Series(EV.qlike_canonical(y[val_rows], f[val_rows]), index=dates.index) for n, f in F.items()}
            for nm in L:
                a = EV.weighted_mean_se(L[nm] - L["HAR-OF"], dates, lags=2 * win)
                bb = EV.weighted_mean_se(L[nm] - L["r*"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, info=info.get(nm, ""),
                                 d_OF=a["mean"], t_OF=a["t"], d_rstar=bb["mean"], t_rstar=bb["t"], n_val=int(val_rows.sum())))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e8_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_OF": g.d_OF.mean(), "t_OF": g.t_OF.mean(),
                                                                     "d_r*": g.d_rstar.mean(), "t_r*": g.t_rstar.mean()}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).to_string(), flush=True)
    print(out[out.model.isin(["ANAM2", "FANAM2", "r*"])][["window", "fold", "model", "info"]].to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
