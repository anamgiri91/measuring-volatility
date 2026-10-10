"""E11: how to estimate the market's overnight move, and what to credit on a bar with no trade.
All under factor-HAR dynamics, w = 0.3, one-price fix on. Variants of the anchor/overnight term:
  M1  : leave-one-out (LOO) equal-weighted mean of o over all other stocks (E10's best);
  MU  : M1 anchor, overnight term o_M^2 - s^2/(n-1) (floored at 0): removes the sampling noise of the mean;
  MA  : LOO mean over ACTIVE stocks only (bar with a range or a non-zero overnight move), so stale prints do
        not dilute the market move;
  MD  : LOO median of o (robust to one stock's error or an unadjusted corporate action);
  MB  : M1, and on a bar with no trade at all the whole latent bar is the market's LOO mean bar
        (o, c, u, d each the LOO mean), i.e. a stale stock is credited the market's day."""
import sys, time
NAME = sys.argv[1] if len(sys.argv) > 1 else None
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
from e10_marketopen import kappa_for, har_Z
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def loo_mean_masked(x, mask, date):
    xm = x.where(mask)
    s = xm.groupby(date).transform("sum"); n = xm.notna().groupby(date).transform("sum")
    own = xm.notna().astype(float)
    return ((s - xm.fillna(0.0)) / (n - own)).where((n - own) > 0)

def loo_var_of_mean(x, date):
    """s^2/(n-1) of the LOO sample: the sampling variance of the leave-one-out mean."""
    s1 = x.groupby(date).transform("sum"); s2 = (x * x).groupby(date).transform("sum"); n = x.notna().groupby(date).transform("sum")
    xi = x.fillna(0.0); own = x.notna().astype(float)
    m = n - own
    mean = (s1 - xi) / m
    var = ((s2 - xi * xi) - m * mean * mean) / (m - 1)
    return (var / m).where(m > 2)

def loo_median(x, date):
    df = pd.DataFrame({"x": x, "date": date}).dropna()
    df["rk"] = df.groupby("date")["x"].rank(method="first").astype(int)
    df["n"] = df.groupby("date")["x"].transform("size")
    out = pd.Series(np.nan, index=x.index)
    for dt, g in df.groupby("date"):
        v = np.sort(g["x"].to_numpy()); n = len(v)
        if n < 3:
            continue
        k = g["rk"].to_numpy()  # 1-based rank of the removed element
        m = n - 1
        if m % 2 == 1:  # odd count left: the middle element of the remainder
            pos = (m + 1) // 2  # 1-based position in the remainder
            val = np.where(k <= pos, v[pos], v[pos - 1])
        else:
            p1, p2 = m // 2, m // 2 + 1
            a = np.where(k <= p1, v[p1], v[p1 - 1]); b = np.where(k <= p2 - 1, v[p2], v[p2 - 1])
            # element at remainder position p: v[p] (0-based) if k <= p, else v[p-1]
            a = np.where(k <= p1, v[p1], v[p1 - 1])
            b = np.where(k <= p2, v[p2], v[p2 - 1])
            val = 0.5 * (a + b)
        out.loc[g.index] = val
    return out

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    sym, date = d["symbol"], d["date"]; zero = pd.Series(0.0, index=d.index)
    notrade = (o.abs() < EPS) & (u.abs() < EPS) & (dd.abs() < EPS) & (c.abs() < EPS)
    active = ~notrade & o.notna()
    oM = loo_market(o, date).fillna(0.0)
    vM = loo_var_of_mean(o, date).fillna(0.0)
    oA = loo_mean_masked(o, active, date).fillna(0.0)
    oD = loo_median(o, date).fillna(0.0)
    w = 0.3
    kern = {"PC": bar_kernel(o, c, u, dd, zero, w, exclude=0.0, overnight=False, zero_range_r2=True),
            "M1": bar_kernel(o, c, u, dd, oM, w, exclude=0.0, overnight=True, zero_range_r2=True)}
    on_u = (oM * oM - vM).clip(lower=0.0)
    kern["MU"] = kern["M1"] - (1 - w) * (oM * oM - on_u)
    kern["MA"] = bar_kernel(o, c, u, dd, oA, w, exclude=0.0, overnight=True, zero_range_r2=True)
    kern["MD"] = bar_kernel(o, c, u, dd, oD, w, exclude=0.0, overnight=True, zero_range_r2=True)
    cM, uM, dM = loo_market(c, date).fillna(0.0), loo_market(u, date).fillna(0.0), loo_market(dd, date).fillna(0.0)
    kB = bar_kernel(oM, cM, uM, dM, oM, w, exclude=0.0, overnight=True, zero_range_r2=True)
    kern["MB"] = kern["M1"].where(~notrade, kB)
    print(name, "built", f"{time.time() - t0:.0f}s", "no-trade share", round(float(notrade.mean()), 3),
          "corr(oM,oA)", round(float(np.corrcoef(oM, oA)[0, 1]), 3), "corr(oM,oD)", round(float(np.corrcoef(oM, oD)[0, 1]), 3),
          "mean vM/oM2", round(float(vM.sum() / (oM * oM).sum()), 3), flush=True)
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
            L = {}
            for nm, m in models.items():
                p, fl = m.fit(y, fit_rows)
                L[nm] = pd.Series(EV.qlike_canonical(y[val_rows], m.forecast(p)[val_rows]), index=dates.index)
            for nm in L:
                a = EV.weighted_mean_se(L[nm] - L["FHAR-OF"], dates, lags=2 * win)
                b2 = EV.weighted_mean_se(L[nm] - L["F:M1"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, d_FOF=a["mean"], t_FOF=a["t"],
                                 d_M1=b2["mean"], t_M1=b2["t"]))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e11_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_FOF": g.d_FOF.mean(), "t_FOF": g.t_FOF.mean(),
                                                                     "d_M1": g.d_M1.mean(), "t_M1": g.t_M1.mean(),
                                                                     "winsM1": int((g.d_M1 < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).sort_values(("d_M1", 5)).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
