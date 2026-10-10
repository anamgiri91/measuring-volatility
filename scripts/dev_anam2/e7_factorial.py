"""E7: factorial ablation of the effective bar (open x exclusion x blend), one-price fix always on, HAR dynamics;
plus a SELF-TUNED kernel chosen on each fold's fit span by QLIKE (the deployable procedure)."""
import sys, time, itertools
NAME = sys.argv[1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, fit_simplex
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def kappa_for(d, X, mode):
    Xc, r2 = FB.clean_square(X), FB.clean_square(d["CC"])
    v = Xc.notna() & r2.notna()
    if mode == "panel":
        return FB.pooled_kappa(Xc.where(v), r2, d["date"], AN.POOL_SESSIONS, AN.MIN_POOL_DATES)
    return FB.series_kappa(Xc.where(v), r2, d["symbol"], AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    sym = d["symbol"]; zero = pd.Series(0.0, index=d.index)
    b = (AN.open_quality_panel(o, r, d["date"]) if mode == "panel" else AN.open_quality_series(o, r, d["symbol"]))
    if mode == "panel":
        bM, bI, oM, oI = two_component_b(o, r, d["date"])
        opens = {"PC": zero, "M1": oM.fillna(0.0), "MT": (oM + bI * oI).where(oM.notna(), b * o),
                 "2C": (bM * oM + bI * oI).where(oM.notna(), b * o)}
    else:
        opens = {"PC": zero, "B": b * o}
    models = {}
    for (ok_, ost), ex, w in itertools.product(opens.items(), (0.0, 1.0), (0.2, 0.3, 0.4)):
        X = bar_kernel(o, c, u, dd, ost, w, exclude=ex, overnight=(ok_ != "PC"), zero_range_r2=True)
        Xc = FB.clean_square(X)
        comp = FB.har_components(Xc.where(Xc.notna() & d["CC"].notna()), sym)
        models[f"{ok_}|x{int(ex)}|w{w}"] = LinearConvex(comp[["d1", "m5", "m22", "lr"]], kappa_for(d, X, mode))
    XO = AN.kernel(o, c, u, dd, zero); Xc = FB.clean_square(XO)
    compO = FB.har_components(Xc.where(Xc.notna() & d["CC"].notna()), sym)
    models["OF (frozen)"] = LinearConvex(compO[["d1", "m5", "m22", "lr"]], kappa_for(d, XO, mode))
    defined = pd.Series(True, index=d.index)
    for m in models.values():
        defined &= m.defined.reindex(d.index).fillna(False).astype(bool)
    rows = []
    for win in (5, 21):
        tgt = EV.forward_target(FB.clean_square(d["CC"]), sym, d["ses"], win); y = tgt["y"]
        for k, (fit_m, val_m) in enumerate(D["masks"]):
            v0, v1 = int(d.loc[val_m, "ses"].min()), int(d.loc[val_m, "ses"].max())
            fit_rows = fit_m & defined & y.notna() & ((tgt["end_session"] < v0) if d.loc[fit_m, "ses"].min() < v0 else True)
            val_rows = val_m & defined & y.notna() & (tgt["end_session"] <= v1)
            dates = d.loc[val_rows, "date"]
            fitL, L = {}, {}
            for nm, m in models.items():
                p, fl = m.fit(y, fit_rows); fitL[nm] = fl
                L[nm] = pd.Series(EV.qlike_canonical(y[val_rows], m.forecast(p)[val_rows]), index=dates.index)
            cand = [n for n in models if n != "OF (frozen)"]
            tuned = min(cand, key=lambda n: fitL[n])
            L["SELF-TUNED"] = L[tuned]
            for nm in L:
                rr = EV.weighted_mean_se(L[nm] - L["OF (frozen)"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, chosen=tuned if nm == "SELF-TUNED" else "",
                                 fit_loss=fitL.get(nm, np.nan), d=rr["mean"], t=rr["t"]))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e7_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d": g.d.mean(), "t": g.t.mean(), "wins": int((g.d < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).sort_values(("d", 5)).to_string(), flush=True)
    print(out[out.model == "SELF-TUNED"][["window", "fold", "chosen", "d", "t"]].to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
