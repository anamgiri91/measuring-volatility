"""E14: the level across stocks. A pooled calibration cannot fit every stock (theory, Proposition 4), and the
market-implied overnight term adds the same o_M^2 to a low- and a high-volatility stock. Calibration variants
under factor-HAR dynamics, for kernels PC (open-free, one-price fix), MS (market move on stale bars only) and
M1 (market move on every bar), all with w = 0.2:
  pool   : the frozen pooled calibration (60 dates);
  shrunk : the stock's own ratio sum r^2 / sum X over its last 250 rows, shrunk toward the pooled one with the
           weight of n0 = 60 rows: (S_r + n0 k_pool Xbar) / (S_X + n0 Xbar), Xbar the stock's mean of X;
  +lrCC  : pooled calibration and the factor HAR gets the stock's own long-run mean of r^2 as one more
           component (the forecast can anchor each stock's level on its own returns)."""
import sys, time
NAME = sys.argv[1] if len(sys.argv) > 1 else None
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
from e10_marketopen import kappa_for, har_Z
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def shrunk_kappa(d, X, kpool, n=250, minp=60, n0=60):
    Xc, r2 = FB.clean_square(X), FB.clean_square(d["CC"])
    v = Xc.notna() & r2.notna()
    sym = d["symbol"]
    roll = lambda s: s.groupby(sym, sort=False).transform(lambda z: z.rolling(n, min_periods=1).sum())
    Sr, SX = roll(r2.where(v)), roll(Xc.where(v))
    cnt = roll(v.astype(float))
    Xbar = SX / cnt
    return ((Sr + n0 * kpool * Xbar) / (SX + n0 * Xbar)).where(cnt >= 1)

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    sym, date = d["symbol"], d["date"]; zero = pd.Series(0.0, index=d.index)
    oM = loo_market(o, date).fillna(0.0)
    stale = (o.abs() < EPS) & (u.abs() < EPS) & (dd.abs() < EPS) & (c.abs() < EPS)
    kern = {"PC": bar_kernel(o, c, u, dd, zero, 0.2, exclude=0.0, overnight=False, zero_range_r2=True),
            "MS": bar_kernel(o, c, u, dd, oM.where(stale, 0.0), 0.2, exclude=0.0, overnight=True, zero_range_r2=True),
            "M1": bar_kernel(o, c, u, dd, oM, 0.2, exclude=0.0, overnight=True, zero_range_r2=True)}
    XOF = AN.kernel(o, c, u, dd, zero)
    lrCC = FB.rolling_rows(FB.clean_square(d["CC"]), sym, s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
    models = {"FHAR-OF": LinearConvex(har_Z(d, XOF, True), kappa_for(d, XOF, mode))}
    for k, X in kern.items():
        kp = kappa_for(d, X, mode); Z = har_Z(d, X, True)
        models[f"{k}|pool"] = LinearConvex(Z, kp)
        models[f"{k}|shrunk"] = LinearConvex(Z, shrunk_kappa(d, X, kp))
        Z2 = Z.copy(); lr = Z2.pop("lr"); Z2["lrCC"] = lrCC / kp; Z2["lr"] = lr
        models[f"{k}|+lrCC"] = LinearConvex(Z2, kp)
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
            L, W = {}, {}
            for nm, m in models.items():
                p, fl = m.fit(y, fit_rows); W[nm] = np.round(p, 3).tolist()
                L[nm] = pd.Series(EV.qlike_canonical(y[val_rows], m.forecast(p)[val_rows]), index=dates.index)
            for nm in L:
                a = EV.weighted_mean_se(L[nm] - L["FHAR-OF"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, weights=str(W[nm]), d_FOF=a["mean"], t_FOF=a["t"]))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e14_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_FOF": g.d_FOF.mean(), "t_FOF": g.t_FOF.mean(),
                                                                     "wins": int((g.d_FOF < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).sort_values(("d_FOF", 5)).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
