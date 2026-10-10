"""E12: dynamics refinements of the factor HAR on the market-implied kernel (M1, w = 0.3; open-free for a series).
  F     : factor HAR, market states = cross-sectional medians of m5/lr and m22/lr (E8-E11);
  F+d   : adds lr * median(d1/lr) (a one-day market state);
  Fmean : market states by cross-sectional mean (not median);
  F125  : long-run level over 125 sessions (min 40) instead of 250;
  Fk20 / Fk120 : the pooled calibration over 20 / 120 dates instead of 60;
  F-noD : factor HAR without the stock's own d1 (the day enters only through the market state);
  HAR   : plain HAR on M1 (no market state)."""
import sys, time
NAME = sys.argv[1] if len(sys.argv) > 1 else None
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def kappa_L(d, X, mode, L=60):
    Xc, r2 = FB.clean_square(X), FB.clean_square(d["CC"])
    v = Xc.notna() & r2.notna()
    if mode == "panel":
        return FB.pooled_kappa(Xc.where(v), r2, d["date"], L, max(10, L // 3))
    return FB.series_kappa(Xc.where(v), r2, d["symbol"], AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)

def comps(d, X, lr_n=250, lr_min=60):
    Xc = FB.clean_square(X)
    Xv = Xc.where(Xc.notna() & d["CC"].notna())
    return pd.DataFrame({"d1": Xv, "m5": FB.rolling_rows(Xv, d["symbol"], 5), "m22": FB.rolling_rows(Xv, d["symbol"], 22),
                         "lr": FB.rolling_rows(Xv, d["symbol"], lr_n, lr_min)}, index=X.index)

def fZ(d, comp, how="median", daily=False, own_d1=True):
    M5 = market_state(comp["m5"] / comp["lr"], d["date"], how); M22 = market_state(comp["m22"] / comp["lr"], d["date"], how)
    cols = {}
    if own_d1:
        cols["d1"] = comp["d1"]
    cols.update({"m5": comp["m5"], "m22": comp["m22"], "lrM5": comp["lr"] * M5, "lrM22": comp["lr"] * M22})
    if daily:
        cols["lrM1"] = comp["lr"] * market_state(comp["d1"] / comp["lr"], d["date"], how)
    cols["lr"] = comp["lr"]
    return pd.DataFrame(cols)

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]
    sym = d["symbol"]; zero = pd.Series(0.0, index=d.index)
    XOF = AN.kernel(o, c, u, dd, zero)
    if mode == "panel":
        oM = loo_market(o, d["date"]).fillna(0.0)
        X = bar_kernel(o, c, u, dd, oM, 0.3, exclude=0.0, overnight=True, zero_range_r2=True)
    else:
        X = bar_kernel(o, c, u, dd, zero, 0.2, exclude=0.0, overnight=False, zero_range_r2=True)
    k60 = kappa_L(d, X, mode, 60)
    cX = comps(d, X)
    models = {"HAR-OF": LinearConvex(FB.har_components(FB.clean_square(XOF).where(d["CC"].notna()), sym)[["d1", "m5", "m22", "lr"]],
                                     kappa_L(d, XOF, mode, 60)),
              "HAR": LinearConvex(cX[["d1", "m5", "m22", "lr"]], k60)}
    if mode == "panel":
        models["F"] = LinearConvex(fZ(d, cX), k60)
        models["F+d"] = LinearConvex(fZ(d, cX, daily=True), k60)
        models["Fmean"] = LinearConvex(fZ(d, cX, how="mean"), k60)
        models["F125"] = LinearConvex(fZ(d, comps(d, X, 125, 40)), k60)
        models["Fk20"] = LinearConvex(fZ(d, cX), kappa_L(d, X, mode, 20))
        models["Fk120"] = LinearConvex(fZ(d, cX), kappa_L(d, X, mode, 120))
        models["F-noD"] = LinearConvex(fZ(d, cX, own_d1=False), k60)
    else:
        models["HAR125"] = LinearConvex(comps(d, X, 125, 40)[["d1", "m5", "m22", "lr"]], k60)
    defined = pd.Series(True, index=d.index)
    for m in models.values():
        defined &= m.defined.reindex(d.index).fillna(False).astype(bool)
    base = "F" if mode == "panel" else "HAR"
    rows = []
    for win in (5, 21):
        tgt = EV.forward_target(FB.clean_square(d["CC"]), sym, d["ses"], win); y = tgt["y"]
        for k, (fit_m, val_m) in enumerate(D["masks"]):
            v0, v1 = int(d.loc[val_m, "ses"].min()), int(d.loc[val_m, "ses"].max())
            fit_rows = fit_m & defined & y.notna() & ((tgt["end_session"] < v0) if d.loc[fit_m, "ses"].min() < v0 else True)
            val_rows = val_m & defined & y.notna() & (tgt["end_session"] <= v1)
            dates = d.loc[val_rows, "date"]
            L, info = {}, {}
            for nm, m in models.items():
                p, fl = m.fit(y, fit_rows); info[nm] = np.round(p, 3).tolist()
                L[nm] = pd.Series(EV.qlike_canonical(y[val_rows], m.forecast(p)[val_rows]), index=dates.index)
            for nm in L:
                a = EV.weighted_mean_se(L[nm] - L["HAR-OF"], dates, lags=2 * win)
                b2 = EV.weighted_mean_se(L[nm] - L[base], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, weights=str(info[nm]), d_OF=a["mean"], t_OF=a["t"],
                                 d_base=b2["mean"], t_base=b2["t"]))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e12_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_OF": g.d_OF.mean(), "t_OF": g.t_OF.mean(),
                                                                     "d_base": g.d_base.mean(), "t_base": g.t_base.mean(),
                                                                     "wins": int((g.d_base < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).sort_values(("d_base", 5)).to_string(), flush=True)
    print(out[out.model.isin([base])][["window", "fold", "weights"]].to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
