"""E5: leverage, multi-measure HAR, fitted combination with GJR, liquidity-specific weights."""
import sys, time
NAME = sys.argv[1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, fit_simplex
from runner2 import run
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def kappa_for(d, X, mode):
    Xc, r2 = FB.clean_square(X), FB.clean_square(d["CC"])
    v = Xc.notna() & r2.notna()
    if mode == "panel":
        return FB.pooled_kappa(Xc.where(v), r2, d["date"], AN.POOL_SESSIONS, AN.MIN_POOL_DATES)
    return FB.series_kappa(Xc.where(v), r2, d["symbol"], AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)

class Fitted2:
    """f = a f1 + (1 - a) f2, a on a grid, fitted on the fit rows (the components refitted first)."""
    def __init__(self, m1, m2):
        self.m1, self.m2 = m1, m2
        self.defined = m1.defined & m2.defined; self.grid = "continuous"
    def fit(self, y, rows):
        from runner2 import fit_model
        p1, _ = fit_model(self.m1, y, rows); p2, _ = fit_model(self.m2, y, rows)
        f1, f2 = self.m1.forecast(p1), self.m2.forecast(p2)
        best = None
        for a in np.round(np.arange(0, 1.0001, 0.05), 2):
            f = a * f1[rows] + (1 - a) * f2[rows]
            L = float(np.mean(EV.qlike_canonical(y[rows], f)))
            if best is None or L < best[1]:
                best = (a, L)
        self.p = (p1, p2)
        return np.array([best[0]]), best[1]
    def forecast(self, a):
        a = float(np.asarray(a).ravel()[0])
        return a * self.m1.forecast(self.p[0]) + (1 - a) * self.m2.forecast(self.p[1])

class ByGroup:
    """A LinearConvex fitted separately in each group (liquidity tercile fixed on the fit rows' history)."""
    def __init__(self, Z, kappa, group):
        self.base = LinearConvex(Z, kappa); self.group = group
        self.defined = self.base.defined & group.notna(); self.grid = "continuous"
    def fit(self, y, rows):
        self.c = {}
        for gname in self.group.dropna().unique():
            rr = rows & (self.group == gname)
            if rr.sum() > 500:
                self.c[gname], _ = self.base.fit(y, rr)
        allc, L = self.base.fit(y, rows); self.c["_all"] = allc
        return np.array([0.0]), L
    def forecast(self, _):
        f = self.base.forecast(self.c["_all"]).copy()
        for gname, c in self.c.items():
            if gname == "_all":
                continue
            m = self.group == gname
            f[m] = self.base.forecast(c)[m]
        return f

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    zero = pd.Series(0.0, index=d.index)
    b = (AN.open_quality_panel(o, r, d["date"]) if mode == "panel" else AN.open_quality_series(o, r, d["symbol"]))
    if mode == "panel":
        bM, bI, oM, oI = two_component_b(o, r, d["date"])
        ost = (bM * oM + bI * oI).where(oM.notna(), b * o)
    else:
        ost = b * o
    X2 = bar_kernel(o, c, u, dd, ost, 0.2, exclude=1.0)
    XO = AN.kernel(o, c, u, dd, zero)
    sym = d["symbol"]
    def comps(X):
        Xc = FB.clean_square(X)
        return FB.har_components(Xc.where(Xc.notna() & d["CC"].notna()), sym)
    cO, c2, cR = comps(XO), comps(X2), comps(d["CC"])
    kO, k2 = kappa_for(d, XO, mode), kappa_for(d, X2, mode)
    down = (r < 0).astype(float).where(r.notna())
    X2d = FB.clean_square(X2) * down
    lev = pd.DataFrame({"d1": c2["d1"], "d1dn": X2d, "m5": c2["m5"],
                        "m5dn": FB.rolling_rows(X2d.where(X2.notna()), sym, 5), "m22": c2["m22"], "lr": c2["lr"]})
    multi = pd.DataFrame({"d1": c2["d1"], "d1r": cR["d1"], "m5": c2["m5"], "m5r": cR["m5"], "m22": c2["m22"],
                          "m22r": cR["m22"], "lr": c2["lr"]})
    models = {"HAR-OF": LinearConvex(cO[["d1", "m5", "m22", "lr"]], kO),
              "HAR-2CXw2": LinearConvex(c2[["d1", "m5", "m22", "lr"]], k2),
              "LHAR-2CXw2": LinearConvex(lev, k2),
              "MHAR-2CXw2": LinearConvex(multi, k2)}
    if D["liq"] is not None:
        liq = D["liq"].reindex(d.index)
        lm = liq.groupby(sym).transform(lambda z: z.rolling(250, min_periods=20).median().shift(1))
        q = lm.groupby(d["date"]).transform(lambda z: pd.qcut(z.rank(method="first"), 3, labels=False) if z.notna().sum() >= 30 else z * np.nan)
        models["GHAR-2CXw2"] = ByGroup(c2[["d1", "m5", "m22", "lr"]], k2, q)
    vb = FB.rolling_rows(FB.clean_square(d["CC"]), sym, s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
    ledger, res = [], []
    for win in (5, 21):
        mm = dict(models)
        mm["GJR"] = s47.Recursion(d, "GJR", win, vb)
        mm["FIT a*HAR-2CXw2 + (1-a)*GJR"] = Fitted2(LinearConvex(c2[["d1", "m5", "m22", "lr"]], k2), s47.Recursion(d, "GJR", win, vb))
        res.append(run(D, mm, win, "HAR-OF", "E5", ledger))
    out = pd.concat(res)
    out.to_csv(OUT / f"e5_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"val": g.val_loss.mean(), "d": g.d_vs_base.mean(), "t": g.t_vs_base.mean()}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).to_string(), flush=True)
    print(out[out.model.str.contains("FIT|LHAR|MHAR")][["fold", "window", "model", "params"]].to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
