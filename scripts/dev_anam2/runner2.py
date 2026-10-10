"""Runner that supports both grid models (s47 classes) and continuous models (LinearConvex)."""
import numpy as np, pandas as pd
from harness import EV, FB

def fit_model(m, y, rows):
    if getattr(m, "grid", None) == "continuous":
        p, L = m.fit(y, rows); return p, L
    if m.grid == (None,):
        return None, np.nan
    p, L, _ = EV.select_by_loss(m.grid, y, rows, m.forecast)
    return p, L

def run(D, models, win, base, tag, ledger, combos=()):
    d = D["d"]
    tgt = EV.forward_target(FB.clean_square(d["CC"]), d["symbol"], d["ses"], win)
    y = tgt["y"]
    defined = pd.Series(True, index=d.index)
    for m in models.values():
        defined &= m.defined.reindex(d.index).fillna(False).astype(bool)
    out = []
    for k, (fit_m, val_m) in enumerate(D["masks"]):
        v0, v1 = int(d.loc[val_m, "ses"].min()), int(d.loc[val_m, "ses"].max())
        if d.loc[fit_m, "ses"].min() < v0:
            fit_rows = fit_m & defined & y.notna() & (tgt["end_session"] < v0)
        else:
            fit_rows = fit_m & defined & y.notna()
        val_rows = val_m & defined & y.notna() & (tgt["end_session"] <= v1)
        dates = d.loc[val_rows, "date"]
        F, P = {}, {}
        for name, m in models.items():
            p, _ = fit_model(m, y, fit_rows)
            F[name] = m.forecast(p); P[name] = p
        for name, (a, b, wa) in dict(combos).items():
            F[name] = wa * F[a] + (1 - wa) * F[b]; P[name] = f"{wa} {a} + {1 - wa:g} {b}"
        L = {n: pd.Series(EV.qlike_canonical(y[val_rows], f[val_rows]), index=dates.index) for n, f in F.items()}
        for name in L:
            r = EV.weighted_mean_se(L[name] - L[base], dates, lags=2 * win)
            p = P[name]
            row = dict(tag=tag, sample=D["name"], fold=k, window=win, model=name,
                       params=str(np.round(p, 3).tolist() if isinstance(p, np.ndarray) else p),
                       n_val=int(val_rows.sum()), val_loss=float(L[name].mean()),
                       d_vs_base=r["mean"], t_vs_base=r["t"], base=base)
            out.append(row); ledger.append(row)
    return pd.DataFrame(out)
