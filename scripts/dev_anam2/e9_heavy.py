"""E9: HEAVY / range-GARCH. A variance-targeted GJR-GARCH whose shock adds the calibrated daily kernel:
    s_{t+1} = (1 - p) v_t + a r_t^2 + g r_t^2 1{r_t < 0} + dl kA_t + b s_t,   p = a + g/2 + dl + b,
run in calendar time (a session without a bar replaces each shock by its expectation, p s_t). The h-session
forecast is the GARCH mean of the next h conditional variances. Parameters common to all securities,
chosen on the fit span by canonical QLIKE over a grid. Compared on common rows with HAR-OF, FHAR-OF, GJR and
the HAR on the market-implied kernel."""
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

GRID = [(a, g, dl, round(p - a - g / 2 - dl, 10), p)
        for a in (0.0, 0.03, 0.06) for g in (0.0, 0.06, 0.12) for dl in (0.05, 0.1, 0.2, 0.3, 0.45)
        for p in (0.85, 0.9, 0.93, 0.95, 0.97, 0.98, 0.99) if p - a - g / 2 - dl >= -1e-12]

class Heavy:
    def __init__(self, d, KA, vbar):
        codes, _ = pd.factorize(d["symbol"]); ses = d["ses"].to_numpy()
        self.codes, self.ses = codes, ses
        T, N = int(ses.max()) + 1, int(codes.max()) + 1
        r = d["r"].where(~(d["r"].abs() < FB.ZERO_SQUARE ** 0.5), 0.0)
        self.R = FB.to_matrix(r, codes, ses, T, N)
        self.K = FB.to_matrix(FB.clean_square(KA), codes, ses, T, N)
        self.V = FB.to_matrix(vbar, codes, ses, T, N, ffill=True)
        self.vrow = vbar.to_numpy(); self.index = d.index
        self.defined = vbar.notna() & (vbar > 0)
    def s1(self, a, g, dl, b, p):
        R, K, V = self.R, self.K, self.V
        T, N = R.shape
        out = np.full((T, N), np.nan); prev = np.full(N, np.nan)
        for t in range(T):
            vb, rt, kt = V[t], R[t], K[t]
            started = np.isfinite(prev) & np.isfinite(vb)
            r2 = rt * rt
            sh_r = np.where(np.isfinite(rt), a * r2 + g * r2 * (rt < 0), (a + g / 2) * prev)
            sh_k = np.where(np.isfinite(kt) & np.isfinite(rt), dl * kt, dl * prev)
            upd = (1 - p) * vb + sh_r + sh_k + b * prev
            cur = np.where(started, upd, np.where(np.isfinite(vb) & ~np.isfinite(prev), vb, prev))
            out[t] = cur; prev = cur
        return FB.from_matrix(out, self.codes, self.ses)
    def forecast(self, par, win):
        a, g, dl, b, p = par
        return pd.Series(FB.h_step_mean(self.s1(a, g, dl, b, p), self.vrow, p, win), index=self.index)

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]
    sym = d["symbol"]; zero = pd.Series(0.0, index=d.index)
    vb = FB.rolling_rows(FB.clean_square(d["CC"]), sym, s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
    kern = {"OF": AN.kernel(o, c, u, dd, zero)}
    if mode == "panel":
        oM = loo_market(o, d["date"]).fillna(0.0)
        kern["MI"] = bar_kernel(o, c, u, dd, oM, 0.3, exclude=0.0, overnight=True, zero_range_r2=True)
    kap = {k: kappa_for(d, X, mode) for k, X in kern.items()}
    lin = {"HAR-OF": LinearConvex(har_Z(d, kern["OF"], False), kap["OF"])}
    if mode == "panel":
        lin["FHAR-OF"] = LinearConvex(har_Z(d, kern["OF"], True), kap["OF"])
        lin["HAR-MI"] = LinearConvex(har_Z(d, kern["MI"], False), kap["MI"])
        lin["FHAR-MI"] = LinearConvex(har_Z(d, kern["MI"], True), kap["MI"])
    heavy = {f"HEAVY-{k}": Heavy(d, kap[k] * FB.clean_square(X), vb) for k, X in kern.items()}
    print(name, "grid", len(GRID), "built", f"{time.time() - t0:.0f}s", flush=True)
    rows = []
    for win in (5, 21):
        gjr = s47.Recursion(d, "GJR", win, vb)
        tgt = EV.forward_target(FB.clean_square(d["CC"]), sym, d["ses"], win); y = tgt["y"]
        defined = y.notna() & gjr.defined.reindex(d.index).fillna(False).astype(bool)
        for m in list(lin.values()) + list(heavy.values()):
            defined &= m.defined.reindex(d.index).fillna(False).astype(bool)
        folds = []
        for k, (fit_m, val_m) in enumerate(D["masks"]):
            v0, v1 = int(d.loc[val_m, "ses"].min()), int(d.loc[val_m, "ses"].max())
            fit_rows = fit_m & defined & ((tgt["end_session"] < v0) if d.loc[fit_m, "ses"].min() < v0 else True)
            val_rows = val_m & defined & (tgt["end_session"] <= v1)
            folds.append((fit_rows, val_rows))
        # grid losses for every HEAVY model, all folds at once
        best = {}
        for hn, hm in heavy.items():
            Ls = np.full((len(GRID), len(folds)), np.inf)
            for gi, par in enumerate(GRID):
                f = hm.forecast(par, win)
                for k, (fr, _) in enumerate(folds):
                    Ls[gi, k] = float(np.mean(EV.qlike_canonical(y[fr], f[fr])))
            for k in range(len(folds)):
                best[(hn, k)] = (GRID[int(np.argmin(Ls[:, k]))], float(Ls[:, k].min()))
        for k, (fr, vr) in enumerate(folds):
            dates = d.loc[vr, "date"]
            F, fitL, info = {}, {}, {}
            for nm, m in lin.items():
                p, L = m.fit(y, fr); F[nm] = m.forecast(p); fitL[nm] = L
            p, L, _ = EV.select_by_loss(gjr.grid, y, fr, gjr.forecast); F["GJR"] = gjr.forecast(p); fitL["GJR"] = L
            info["GJR"] = str(p)
            for hn, hm in heavy.items():
                par, L = best[(hn, k)]; F[hn] = hm.forecast(par, win); fitL[hn] = L; info[hn] = str(par)
            F["1/2 HAR-OF + 1/2 GJR"] = 0.5 * F["HAR-OF"] + 0.5 * F["GJR"]
            if mode == "panel":
                F["1/2 FHAR-MI + 1/2 GJR"] = 0.5 * F["FHAR-MI"] + 0.5 * F["GJR"]
                F["1/2 FHAR-MI + 1/2 HEAVY-MI"] = 0.5 * F["FHAR-MI"] + 0.5 * F["HEAVY-MI"]
            L = {n: pd.Series(EV.qlike_canonical(y[vr], f[vr]), index=dates.index) for n, f in F.items()}
            for nm in L:
                a = EV.weighted_mean_se(L[nm] - L["HAR-OF"], dates, lags=2 * win)
                bb = EV.weighted_mean_se(L[nm] - L["GJR"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, info=info.get(nm, ""), fit_loss=fitL.get(nm, np.nan),
                                 d_OF=a["mean"], t_OF=a["t"], d_GJR=bb["mean"], t_GJR=bb["t"], n_val=int(vr.sum())))
        print(name, "h", win, f"{time.time() - t0:.0f}s", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e9_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_OF": g.d_OF.mean(), "t_OF": g.t_OF.mean(),
                                                                     "d_GJR": g.d_GJR.mean(), "t_GJR": g.t_GJR.mean(),
                                                                     "wins_OF": int((g.d_OF < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).to_string(), flush=True)
    print(out[out.model.str.startswith("HEAVY")][["window", "fold", "model", "info"]].to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
