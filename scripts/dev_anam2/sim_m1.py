"""Simulation: when does the market-implied open help? A panel with a market factor, stochastic volatility,
an opening auction error, heterogeneous betas and stale stocks. Truth known; forecasts scored by QLIKE on the
forward mean of observed squared close-to-close returns, as in the paper."""
import sys
sys.argv = sys.argv[:1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state

def simulate(N=120, T=1500, steps=20, s_on=0.3, noise=1.0, beta_spread=0.0, stale_p=0.0, stale_share=0.0, seed=0):
    rng = np.random.default_rng(seed)
    # volatility states
    hM = np.zeros(T); hI = np.zeros((T, N))
    for t in range(1, T):
        hM[t] = 0.985 * hM[t - 1] + 0.12 * rng.standard_normal()
        hI[t] = 0.98 * hI[t - 1] + 0.12 * rng.standard_normal(N)
    sM2 = 0.8e-4 * np.exp(hM)                            # market daily variance
    lvl = np.exp(rng.normal(np.log(2.0e-4), 0.5, N))      # idiosyncratic level, heterogeneous
    sI2 = lvl[None, :] * np.exp(hI)
    beta = 1.0 + beta_spread * (rng.uniform(-1, 1, N))
    # efficient moves
    ZM = rng.standard_normal(T); ZI = rng.standard_normal((T, N))
    on_eff = beta[None, :] * np.sqrt(s_on * sM2)[:, None] * ZM[:, None] + np.sqrt(s_on * sI2) * ZI
    dW_M = rng.standard_normal((T, steps)) * np.sqrt((1 - s_on) * sM2 / steps)[:, None]
    dW_I = rng.standard_normal((T, N, steps)) * np.sqrt((1 - s_on) * sI2 / steps)[:, :, None]
    path = np.cumsum(beta[None, :, None] * dW_M[:, None, :] + dW_I, axis=2)          # intraday, from the efficient open
    var_on = beta[None, :] ** 2 * s_on * sM2[:, None] + s_on * sI2
    eta = noise * np.sqrt(var_on) * rng.standard_normal((T, N))
    true_var = beta[None, :] ** 2 * sM2[:, None] + sI2
    # efficient log prices at closes
    eff_close = np.cumsum(on_eff + path[:, :, -1], axis=0)
    eff_open = eff_close - path[:, :, -1]
    illiquid = rng.uniform(size=N) < stale_share
    stale = (rng.uniform(size=(T, N)) < stale_p) & illiquid[None, :]
    stale[0] = False
    rows = []
    obs_close = np.zeros(N)  # observed log close (previous)
    prev = np.zeros(N)
    O = np.empty((T, N)); H = np.empty((T, N)); L = np.empty((T, N)); C = np.empty((T, N)); PC = np.empty((T, N))
    pc = eff_close[0] - on_eff[0] - path[0, :, -1]  # start
    for t in range(T):
        PC[t] = pc
        op = eff_open[t] + eta[t]
        hi = np.maximum(op, eff_open[t] + path[t].max(axis=1)); lo = np.minimum(op, eff_open[t] + path[t].min(axis=1))
        hi = np.maximum(hi, eff_open[t]); lo = np.minimum(lo, eff_open[t])
        cl = eff_close[t]
        st = stale[t]
        O[t] = np.where(st, pc, op); H[t] = np.where(st, pc, hi); L[t] = np.where(st, pc, lo); C[t] = np.where(st, pc, cl)
        pc = C[t]
    sym = np.tile(np.arange(N), T); date = np.repeat(np.arange(T), N)
    d = pd.DataFrame({"symbol": sym, "date": pd.to_datetime("2000-01-01") + pd.to_timedelta(date, "D"), "ses": date,
                      "o": (O - PC).ravel(), "c": (C - O).ravel(), "u": (H - O).ravel(), "d": (L - O).ravel(),
                      "true": true_var.ravel()})
    d["r"] = d["o"] + d["c"]; d["CC"] = d["r"] ** 2
    d = d.sort_values(["symbol", "ses"]).reset_index(drop=True)
    return d

def har_Z(d, X, factor):
    Xc = FB.clean_square(X)
    comp = FB.har_components(Xc.where(Xc.notna() & d["CC"].notna()), d["symbol"])
    if not factor:
        return comp[["d1", "m5", "m22", "lr"]]
    M5 = market_state(comp["m5"] / comp["lr"], d["date"]); M22 = market_state(comp["m22"] / comp["lr"], d["date"])
    return pd.DataFrame({"d1": comp["d1"], "m5": comp["m5"], "m22": comp["m22"], "lrM5": comp["lr"] * M5,
                         "lrM22": comp["lr"] * M22, "lr": comp["lr"]})

def run(cfg, seed=0, win=5):
    d = simulate(seed=seed, **cfg)
    o, c, u, dd, date = d["o"], d["c"], d["u"], d["d"], d["date"]
    zero = pd.Series(0.0, index=d.index)
    oM = loo_market(o, date).fillna(0.0)
    stale = (o.abs() < EPS) & (u.abs() < EPS) & (dd.abs() < EPS) & (c.abs() < EPS)
    K = {"OF": AN.kernel(o, c, u, dd, zero),
         "PC": bar_kernel(o, c, u, dd, zero, 0.2, exclude=0.0, overnight=False, zero_range_r2=True),
         "MS": bar_kernel(o, c, u, dd, oM.where(stale, 0.0), 0.2, exclude=0.0, overnight=True, zero_range_r2=True),
         "M1": bar_kernel(o, c, u, dd, oM, 0.2, exclude=0.0, overnight=True, zero_range_r2=True)}
    r2 = FB.clean_square(d["CC"])
    out = {}
    tgt = EV.forward_target(r2, d["symbol"], d["ses"], win); y = tgt["y"]
    fit = d["ses"] < 750; val = d["ses"] >= 800
    for k, X in K.items():
        kap = FB.pooled_kappa(FB.clean_square(X), r2, date, 60, 20)
        m = LinearConvex(har_Z(d, X, True), kap)
        ok = m.defined & y.notna()
        p, _ = m.fit(y, fit & ok & (tgt["end_session"] < 800))
        f = m.forecast(p)
        out[k] = pd.Series(EV.qlike_canonical(y[val & ok], f[val & ok]), index=d.index[val & ok])
        # measurement quality: correlation of log calibrated kernel 22-day mean with log true variance
        m22 = FB.rolling_rows(FB.clean_square(X), d["symbol"], 22)
        tr22 = FB.rolling_rows(d["true"], d["symbol"], 22)
        good = (m22 > 0) & tr22.notna() & val
        out[k + "_corr"] = float(np.corrcoef(np.log(m22[good]), np.log(tr22[good]))[0, 1])
    j = out["PC"].index
    for k in ("OF", "MS", "M1"):
        jj = j.intersection(out[k].index)
        out[k + "-PC"] = float((out[k].loc[jj] - out["PC"].loc[jj]).mean())
    return {k: v for k, v in out.items() if not isinstance(v, pd.Series)}

if __name__ == "__main__":
    cfgs = {"homog, liquid": dict(beta_spread=0.0, stale_p=0.0),
            "hetero beta, liquid": dict(beta_spread=0.7, stale_p=0.0),
            "homog, stale": dict(beta_spread=0.0, stale_p=0.4, stale_share=0.5),
            "hetero beta, stale": dict(beta_spread=0.7, stale_p=0.4, stale_share=0.5),
            "homog, no noise": dict(beta_spread=0.0, stale_p=0.0, noise=0.0)}
    res = []
    for name, cfg in cfgs.items():
        for seed in range(3):
            r = run(cfg, seed=seed); r["cfg"] = name; r["seed"] = seed; res.append(r)
            print(name, seed, {k: round(v, 4) for k, v in r.items() if k not in ("cfg", "seed")}, flush=True)
    res = pd.DataFrame(res)
    print(res.groupby("cfg").mean(numeric_only=True).round(4).to_string())
