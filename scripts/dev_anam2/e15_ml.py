"""E15: a different approach -- gradient-boosted trees on bar features, trained on a Patton-robust loss.
HistGradientBoostingRegressor with the Poisson deviance (Patton's robust family, b = -1; it accepts zero targets)
and with the gamma deviance (= 2 x QLIKE; zero targets left out of training). Fixed hyperparameters (no tuning):
300 rounds, learning rate 0.05, 31 leaves, 200 rows per leaf. Features (all causal), on a log scale:
calibrated means of the open-free (PC) and market-implied (M1) kernels and of r^2 over 1, 5, 22, 250 rows, the
factor-HAR market states, the share of stale bars and of zero returns over 22 rows, today's and the 5-row mean
of o_M^2. Compared with the factor HAR on M1 and on the frozen open-free kernel."""
import sys, time
NAME = sys.argv[1] if len(sys.argv) > 1 else None
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
from e10_marketopen import kappa_for, har_Z
from sklearn.ensemble import HistGradientBoostingRegressor
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"
TINY = 1e-12

def lg(x):
    return np.log(np.maximum(x.astype(float), TINY))

def features(d, mode):
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]; sym, date = d["symbol"], d["date"]
    zero = pd.Series(0.0, index=d.index)
    F = {}
    kern = {"PC": bar_kernel(o, c, u, dd, zero, 0.2, exclude=0.0, overnight=False, zero_range_r2=True)}
    if mode == "panel":
        oM = loo_market(o, date).fillna(0.0)
        kern["M1"] = bar_kernel(o, c, u, dd, oM, 0.2, exclude=0.0, overnight=True, zero_range_r2=True)
        kern["MSO"] = bar_kernel(o, c, u, dd, oM.where(o.abs() < EPS, 0.0), 0.2, exclude=0.0, overnight=True, zero_range_r2=True)
        F["log_oM2"] = lg(oM * oM); F["log_oM2_5"] = lg(FB.rolling_rows(oM * oM, sym, 5))
    for k, X in kern.items():
        kp = kappa_for(d, X, mode)
        comp = FB.har_components(FB.clean_square(X).where(d["CC"].notna()), sym)
        for col in ("d1", "m5", "m22", "lr"):
            F[f"log_{k}_{col}"] = lg(kp * comp[col])
        if mode == "panel":
            F[f"log_{k}_M5"] = lg(market_state(comp["m5"] / comp["lr"], date))
            F[f"log_{k}_M22"] = lg(market_state(comp["m22"] / comp["lr"], date))
    cc = FB.har_components(FB.clean_square(d["CC"]), sym)
    for col in ("d1", "m5", "m22", "lr"):
        F[f"log_CC_{col}"] = lg(cc[col])
    stale = ((o.abs() < EPS) & (u.abs() < EPS) & (dd.abs() < EPS) & (c.abs() < EPS)).astype(float)
    F["stale_22"] = FB.rolling_rows(stale, sym, 22)
    F["zero_r_22"] = FB.rolling_rows((FB.clean_square(d["CC"]) == 0).astype(float).where(d["CC"].notna()), sym, 22)
    return pd.DataFrame(F, index=d.index)

class Boost:
    def __init__(self, X, loss):
        self.X, self.loss = X, loss
        self.defined = X[[c for c in X.columns if c.endswith("_lr")]].notna().all(axis=1)
        self.grid = "continuous"
    def fit(self, y, rows):
        rr = rows & (y > 0) if self.loss == "gamma" else rows
        self.m = HistGradientBoostingRegressor(loss=self.loss, learning_rate=0.05, max_iter=300, max_leaf_nodes=31,
                                               min_samples_leaf=200, early_stopping=False, random_state=0)
        self.m.fit(self.X[rr].to_numpy(), y[rr].to_numpy())
        f = self.forecast(None)
        return np.array([0.0]), float(np.mean(EV.qlike_canonical(y[rows], f[rows])))
    def forecast(self, _):
        return pd.Series(np.maximum(self.m.predict(self.X.to_numpy()), 1e-10), index=self.X.index)

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd = d["o"], d["c"], d["u"], d["d"]; sym = d["symbol"]; zero = pd.Series(0.0, index=d.index)
    X = features(d, mode)
    XOF = AN.kernel(o, c, u, dd, zero)
    models = {"HAR-OF": LinearConvex(har_Z(d, XOF, False), kappa_for(d, XOF, mode))}
    if mode == "panel":
        models["FHAR-OF"] = LinearConvex(har_Z(d, XOF, True), kappa_for(d, XOF, mode))
        oM = loo_market(o, d["date"]).fillna(0.0)
        XM = bar_kernel(o, c, u, dd, oM, 0.2, exclude=0.0, overnight=True, zero_range_r2=True)
        models["FHAR-M1"] = LinearConvex(har_Z(d, XM, True), kappa_for(d, XM, mode))
        XS = bar_kernel(o, c, u, dd, oM.where(o.abs() < EPS, 0.0), 0.2, exclude=0.0, overnight=True, zero_range_r2=True)
        kS = kappa_for(d, XS, mode); ZS = har_Z(d, XS, True)
        lrCC = FB.rolling_rows(FB.clean_square(d["CC"]), sym, s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
        lr = ZS.pop("lr"); ZS["lrCC"] = lrCC / kS; ZS["lr"] = lr
        models["FHARL-MSO"] = LinearConvex(ZS, kS)
    models["GBT-poisson"] = Boost(X, "poisson"); models["GBT-gamma"] = Boost(X, "gamma")
    print(name, "features", X.shape, f"{time.time() - t0:.0f}s", flush=True)
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
                a = EV.weighted_mean_se(L[nm] - L["HAR-OF"], dates, lags=2 * win)
                rows.append(dict(sample=name, window=win, fold=k, model=nm, d_OF=a["mean"], t_OF=a["t"]))
        print(name, "h", win, f"{time.time() - t0:.0f}s", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"e15_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d_OF": g.d_OF.mean(), "t_OF": g.t_OF.mean(),
                                                                     "wins": int((g.d_OF < 0).sum())}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).sort_values(("d_OF", 5)).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
