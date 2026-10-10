"""E10: how the market-implied open should enter, under factor-HAR dynamics.
Variants (panels): PC (open-free with the one-price fix), M1 (anchor at the leave-one-out market overnight move),
BM (anchor at b_M o_M, b_M the trailing pooled projection of r on o_M: the market open read as far as it is
kept), M1N (market overnight term + the stock's own H-L range, no extension), MS (market anchor only on bars
with no trade at all, O = H = L = C = PC; open-free elsewhere), M1 without the one-price fix; w in 0.2/0.3/0.4."""
import sys, time, itertools
NAME = sys.argv[1] if len(sys.argv) > 1 else None
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

def b_market(oM, r, date, sessions=60, min_dates=20):
    ok = oM.notna() & r.notna()
    g = pd.DataFrame({"xy": (oM * r).where(ok), "xx": (oM * oM).where(ok), "date": date}).groupby("date")[["xy", "xx"]].sum().sort_index()
    roll = g.rolling(sessions, min_periods=min_dates).sum()
    return date.map((roll.xy / roll.xx).clip(0.0, 1.0))

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    assert mode == "panel"
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    sym = d["symbol"]; zero = pd.Series(0.0, index=d.index)
    oM = loo_market(o, d["date"]).fillna(0.0)
    bM = b_market(oM, r, d["date"])
    notrade = (o.abs() < EPS) & (u.abs() < EPS) & (dd.abs() < EPS) & (c.abs() < EPS)
    kern = {}
    for w in (0.2, 0.3, 0.4):
        kern[f"PC|w{w}"] = bar_kernel(o, c, u, dd, zero, w, exclude=0.0, overnight=False, zero_range_r2=True)
        kern[f"M1|w{w}"] = bar_kernel(o, c, u, dd, oM, w, exclude=0.0, overnight=True, zero_range_r2=True)
        kern[f"BM|w{w}"] = bar_kernel(o, c, u, dd, (bM * oM).fillna(0.0), w, exclude=0.0, overnight=True, zero_range_r2=True)
        kern[f"M1N|w{w}"] = bar_kernel(o, c, u, dd, oM, w, exclude=0.0, extend=False, overnight=True, zero_range_r2=True)
        kern[f"MS|w{w}"] = bar_kernel(o, c, u, dd, oM.where(notrade, 0.0), w, exclude=0.0, overnight=True, zero_range_r2=True)
    kern["M1|w0.3|zr0"] = bar_kernel(o, c, u, dd, oM, 0.3, exclude=0.0, overnight=True, zero_range_r2=False)
    XOF = AN.kernel(o, c, u, dd, zero)
    models = {"HAR-OF": LinearConvex(har_Z(d, XOF, False), kappa_for(d, XOF, mode)),
              "FHAR-OF": LinearConvex(har_Z(d, XOF, True), kappa_for(d, XOF, mode))}
    for k, X in kern.items():
        models["F:" + k] = LinearConvex(har_Z(d, X, True), kappa_for(d, X, mode))
    print(name, "built", f"{time.time() - t0:.0f}s", "share no-trade", round(float(notrade.mean()), 3),
          "median bM", round(float(bM.median()), 3), flush=True)
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
            L, fitL = {}, {}
            for nm, m in models.items():
                p, fl = m.fit(y, fit_rows); fitL[nm] = fl
                L[nm] = pd.Series(EV.qlike_canonical(y[val_rows], m.forecast(p)[val_rows]), index=dates.index)
            for fam in ("PC", "M1", "BM", "M1N", "MS"):
                cand = [n for n in models if n.startswith(f"F:{fam}|") and "zr0" not in n]
                L[f"TUNED:{fam}"] = L[min(cand, key=lambda n: fitL[n])]
            for nm in L:
                a = EV.weighted_mean_se(L[nm] - L["HAR-OF"], dates, lags=2 * win)
                b2 = EV.weighted_mean_se(L[nm] - L["FHAR-OF"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, fit_loss=fitL.get(nm, np.nan),
                                 d_OF=a["mean"], t_OF=a["t"], d_FOF=b2["mean"], t_FOF=b2["t"]))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e10_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_OF": g.d_OF.mean(), "t_OF": g.t_OF.mean(),
                                                                     "d_FOF": g.d_FOF.mean(), "t_FOF": g.t_FOF.mean(),
                                                                     "winsF": int((g.d_FOF < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).sort_values(("d_FOF", 5)).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
