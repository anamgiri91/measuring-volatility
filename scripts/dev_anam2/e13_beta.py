"""E13: stock-specific exposure to the market's overnight move. M1 credits every stock the full LOO market
overnight move; a low-beta stock is over-credited on a big market night. Variants (factor HAR, w = 0.2/0.3):
  PC  : open-free with the one-price fix;  M1 : full market move;
  MBi : beta_i o_M, beta_i the stock's trailing projection of r on o_M (250 rows, min 60), shrunk toward the
        pooled b_M with the weight of 60 typical days, clipped to [0, 2];
  MBr : (beta_i / b_M) o_M, the same beta relative to the pooled one, so the average stock keeps the full move."""
import sys, time
NAME = sys.argv[1] if len(sys.argv) > 1 else None
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
from e10_marketopen import kappa_for, har_Z, b_market
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def stock_beta(oM, r, sym, date, bM, n=250, minp=60, prior_days=60):
    ok = oM.notna() & r.notna()
    xy = (oM * r).where(ok); xx = (oM * oM).where(ok)
    roll = lambda s: s.groupby(sym, sort=False).transform(lambda z: z.rolling(n, min_periods=minp).sum())
    Sxy, Sxx = roll(xy), roll(xx)
    typ = date.map((oM * oM).groupby(date).mean().rolling(250, min_periods=20).median())  # a typical day's o_M^2
    lam = prior_days * typ
    return ((Sxy + lam * bM) / (Sxx + lam)).clip(0.0, 2.0)

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    sym, date = d["symbol"], d["date"]; zero = pd.Series(0.0, index=d.index)
    oM = loo_market(o, date).fillna(0.0)
    bM = b_market(oM, r, date)
    beta = stock_beta(oM, r, sym, date, bM)
    rel = (beta / bM).clip(0.0, 2.0)
    print(name, "beta quantiles", beta.quantile([0.1, 0.5, 0.9]).round(2).tolist(), "rel", rel.quantile([0.1, 0.5, 0.9]).round(2).tolist(), flush=True)
    kern = {}
    for w in (0.2, 0.3):
        kern[f"PC|w{w}"] = bar_kernel(o, c, u, dd, zero, w, exclude=0.0, overnight=False, zero_range_r2=True)
        kern[f"M1|w{w}"] = bar_kernel(o, c, u, dd, oM, w, exclude=0.0, overnight=True, zero_range_r2=True)
        kern[f"MBi|w{w}"] = bar_kernel(o, c, u, dd, (beta * oM).fillna(oM * bM).fillna(0.0), w, exclude=0.0, overnight=True, zero_range_r2=True)
        kern[f"MBr|w{w}"] = bar_kernel(o, c, u, dd, (rel * oM).fillna(oM).fillna(0.0), w, exclude=0.0, overnight=True, zero_range_r2=True)
    XOF = AN.kernel(o, c, u, dd, zero)
    models = {"FHAR-OF": LinearConvex(har_Z(d, XOF, True), kappa_for(d, XOF, mode))}
    for k, X in kern.items():
        models["F:" + k] = LinearConvex(har_Z(d, X, True), kappa_for(d, X, mode))
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
            for nm in L:
                a = EV.weighted_mean_se(L[nm] - L["FHAR-OF"], dates, lags=2 * win)
                b2 = EV.weighted_mean_se(L[nm] - L["F:M1|w0.2"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, fit_loss=fitL[nm], d_FOF=a["mean"], t_FOF=a["t"],
                                 d_M1=b2["mean"], t_M1=b2["t"]))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e13_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_FOF": g.d_FOF.mean(), "t_FOF": g.t_FOF.mean(),
                                                                     "d_M1": g.d_M1.mean(), "t_M1": g.t_M1.mean(),
                                                                     "winsM1": int((g.d_M1 < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).sort_values(("d_FOF", 5)).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
