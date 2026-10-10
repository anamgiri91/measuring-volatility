"""E16: the candidate second-generation systems side by side on every development sample (w = 0.2 throughout).
Kernels: OF (frozen open-free), MS (market-implied open on stale bars only, one-price fix), M1 (market-implied open
on every bar, one-price fix). Dynamics: HAR, FHAR (factor states), FHARL (factor states + the stock's own
long-run mean of r^2). Return-only: GJR, and r* = the best of HAR-CC, FHAR-CC, GJR by fit-span loss.
Combinations: 1/2 with GJR."""
import sys, time
NAME = sys.argv[1] if len(sys.argv) > 1 else None
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
from e10_marketopen import kappa_for, har_Z
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def with_lrcc(Z, lrCC, kap):
    Z2 = Z.copy(); lr = Z2.pop("lr"); Z2["lrCC"] = lrCC / kap; Z2["lr"] = lr
    return Z2

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]
    sym, date = d["symbol"], d["date"]; zero = pd.Series(0.0, index=d.index)
    K = {"OF": AN.kernel(o, c, u, dd, zero)}
    if mode == "panel":
        oM = loo_market(o, date).fillna(0.0)
        stale = (o.abs() < EPS) & (u.abs() < EPS) & (dd.abs() < EPS) & (c.abs() < EPS)
        K["MS"] = bar_kernel(o, c, u, dd, oM.where(stale, 0.0), 0.2, exclude=0.0, overnight=True, zero_range_r2=True)
        K["M1"] = bar_kernel(o, c, u, dd, oM, 0.2, exclude=0.0, overnight=True, zero_range_r2=True)
        so = o.abs() < EPS  # stale open: the open printed at the previous close
        K["MSO"] = bar_kernel(o, c, u, dd, oM.where(so, 0.0), 0.2, exclude=0.0, overnight=True, zero_range_r2=True)
        print(name, "stale bars", round(float(stale.mean()), 3), "stale opens", round(float(so.mean()), 3), flush=True)
    else:
        K["PC"] = bar_kernel(o, c, u, dd, zero, 0.2, exclude=0.0, overnight=False, zero_range_r2=True)
    lrCC = FB.rolling_rows(FB.clean_square(d["CC"]), sym, s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
    models = {}
    for k, X in K.items():
        kap = kappa_for(d, X, mode)
        models[f"HAR-{k}"] = LinearConvex(har_Z(d, X, False), kap)
        if mode == "panel":
            Zf = har_Z(d, X, True)
            models[f"FHAR-{k}"] = LinearConvex(Zf, kap)
            models[f"FHARL-{k}"] = LinearConvex(with_lrcc(Zf, lrCC, kap), kap)
        else:
            models[f"HARL-{k}"] = LinearConvex(with_lrcc(har_Z(d, X, False), lrCC, kap), kap)
    compR = FB.har_components(FB.clean_square(d["CC"]), sym)
    models["HAR-CC"] = LinearConvex(compR[["d1", "m5", "m22", "lr"]], 1.0)
    if mode == "panel":
        models["FHAR-CC"] = LinearConvex(har_Z(d, d["CC"], True), 1.0)
    vb = FB.rolling_rows(FB.clean_square(d["CC"]), sym, s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
    best = ["FHARL-M1", "FHARL-MS", "FHARL-MSO"] if mode == "panel" else ["HARL-OF"]
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
                    p, L = m.fit(y, fit_rows); info[nm] = str(np.round(p, 3).tolist())
                else:
                    p, L, _ = EV.select_by_loss(m.grid, y, fit_rows, m.forecast); info[nm] = str(p)
                F[nm] = m.forecast(p); fitL[nm] = L
            ret = [n for n in F if n in ("HAR-CC", "FHAR-CC", "GJR")]
            rstar = min(ret, key=lambda n: fitL[n]); F["r*"] = F[rstar]; info["r*"] = rstar
            for b in best:
                F[f"1/2 {b} + 1/2 GJR"] = 0.5 * F[b] + 0.5 * F["GJR"]
            L = {n: pd.Series(EV.qlike_canonical(y[val_rows], f[val_rows]), index=dates.index) for n, f in F.items()}
            for nm in L:
                a = EV.weighted_mean_se(L[nm] - L["HAR-OF"], dates, lags=2 * win)
                bb = EV.weighted_mean_se(L[nm] - L["r*"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, info=info.get(nm, ""), fit_loss=fitL.get(nm, np.nan),
                                 val_loss=float(L[nm].mean()), d_OF=a["mean"], t_OF=a["t"], d_rstar=bb["mean"], t_rstar=bb["t"],
                                 n_val=int(val_rows.sum())))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e16_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_OF": g.d_OF.mean(), "t_OF": g.t_OF.mean(),
                                                                     "d_r*": g.d_rstar.mean(), "t_r*": g.t_rstar.mean(),
                                                                     "winsOF": int((g.d_OF < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).sort_values(("d_OF", 5)).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
