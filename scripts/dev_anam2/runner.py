"""Fit on the fit rows (purged), score on the validation rows common to every candidate."""
import numpy as np, pandas as pd
from harness import EV, FB

def run(D, models, win, base, tag, ledger):
    d = D["d"]
    tgt = EV.forward_target(FB.clean_square(d["CC"]), d["symbol"], d["ses"], win)
    y = tgt["y"]
    defined = pd.Series(True, index=d.index)
    for m in models.values():
        defined &= m.defined.reindex(d.index).fillna(False).astype(bool)
    out = []
    for k, (fit_m, val_m) in enumerate(D["masks"]):
        v0, v1 = int(d.loc[val_m, "ses"].min()), int(d.loc[val_m, "ses"].max())
        if d.loc[fit_m, "ses"].min() < v0:      # fit before validation: purge outcomes reaching it
            fit_rows = fit_m & defined & y.notna() & (tgt["end_session"] < v0)
        else:                                    # fit after validation (NEPSE fold B -> A1)
            fit_rows = fit_m & defined & y.notna()
        val_rows = val_m & defined & y.notna() & (tgt["end_session"] <= v1)
        dates = d.loc[val_rows, "date"]
        L, P = {}, {}
        for name, m in models.items():
            p, fl, _ = EV.select_by_loss(m.grid, y, fit_rows, m.forecast) if m.grid != (None,) else (None, np.nan, 0)
            f = m.forecast(p)
            L[name] = pd.Series(EV.qlike_canonical(y[val_rows], f[val_rows]), index=dates.index)
            P[name] = p
        for name in models:
            r = EV.weighted_mean_se(L[name] - L[base], dates, lags=2 * win)
            row = dict(tag=tag, sample=D["name"], fold=k, window=win, model=name, params=str(P[name]),
                       n_val=int(val_rows.sum()), val_loss=float(L[name].mean()),
                       d_vs_base=r["mean"], t_vs_base=r["t"], base=base)
            out.append(row); ledger.append(row)
    return pd.DataFrame(out)
