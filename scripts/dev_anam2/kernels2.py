"""Candidate second-generation kernels (development only)."""
import numpy as np, pandas as pd
LN2 = float(np.log(2.0))
EPS = 1e-12

def loo_market(x: pd.Series, date: pd.Series) -> pd.Series:
    """Leave-one-out equal-weighted cross-sectional mean of x on each date."""
    s = x.groupby(date).transform("sum"); n = x.notna().groupby(date).transform("sum")
    return ((s - x.fillna(0.0)) / (n - x.notna().astype(float))).where(n > 1)

def two_component_b(o, r, date, sessions=60, min_dates=20, clip=(0.0, 1.0)):
    """Trailing pooled no-intercept projection of r on (o_M, o_I): b_M, b_I by date."""
    oM = loo_market(o, date); oI = o - oM
    ok = o.notna() & r.notna() & oM.notna()
    f = pd.DataFrame({"mm": (oM * oM).where(ok), "ii": (oI * oI).where(ok), "mi": (oM * oI).where(ok),
                      "my": (oM * r).where(ok), "iy": (oI * r).where(ok), "date": date})
    g = f.groupby("date")[["mm", "ii", "mi", "my", "iy"]].sum().sort_index()
    roll = g.rolling(sessions, min_periods=min_dates).sum()
    det = roll.mm * roll.ii - roll.mi ** 2
    bM = (roll.ii * roll.my - roll.mi * roll.iy) / det
    bI = (roll.mm * roll.iy - roll.mi * roll.my) / det
    bM = bM.clip(*clip); bI = bI.clip(*clip)
    return date.map(bM), date.map(bI), oM, oI

def bar_kernel(o, c, u, d, ostar, w, exclude=1.0, extend=True, overnight=True, zero_range_r2=False):
    """Kernel on the 'effective bar'.
    ostar : effective overnight log move (anchor = PC exp(ostar)); 0 gives the open-free anchor.
    exclude : 1 replaces an extreme set by the opening print by max/min(ostar, r); 0 keeps it.
    zero_range_r2 : on a one-price bar (H = L) the squared range term is the squared move itself,
                    not divided by Parkinson's 4 ln 2 (a range of one observation is not a Brownian range).
    """
    r = o + c; h = o + u; l = o + d
    o_is_h = u.abs() < EPS; o_is_l = d.abs() < EPS
    hx = np.maximum(ostar, r); lx = np.minimum(ostar, r)
    hs = h.where(~o_is_h, hx + (1 - exclude) * (h - hx))
    ls = l.where(~o_is_l, lx + (1 - exclude) * (l - lx))
    if extend:
        hs = np.maximum(hs, ostar); ls = np.minimum(ls, ostar)
    R = hs - ls
    div = pd.Series(4 * LN2, index=o.index)
    if zero_range_r2:
        div = div.where(~((u - d).abs() < EPS), 1.0)
    on = ostar * ostar if overnight else 0.0
    return (1 - w) * (on + R * R / div) + w * r * r
