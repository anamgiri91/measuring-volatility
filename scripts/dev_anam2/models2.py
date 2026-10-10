"""Development forecast models with continuous parameters, fitted by minimising canonical QLIKE."""
import numpy as np, pandas as pd
from scipy.optimize import minimize
from harness import FB, EV

def fit_simplex(Zr, yr, floor_last=0.05, starts=None):
    """argmin_c mean(y/f + ln f), f = Zr @ c, c >= 0, sum c = 1, c[-1] >= floor_last (SLSQP, exact gradient)."""
    k = Zr.shape[1]
    def obj(c):
        f = np.maximum(Zr @ c, 1e-300)
        return np.mean(yr / f + np.log(f))
    def grad(c):
        f = np.maximum(Zr @ c, 1e-300)
        g = (1.0 / f - yr / (f * f))
        return Zr.T @ g / len(yr)
    cons = [{"type": "eq", "fun": lambda c: c.sum() - 1.0, "jac": lambda c: np.ones_like(c)}]
    bounds = [(0.0, 1.0)] * (k - 1) + [(floor_last, 1.0)]
    starts = starts or [np.full(k, 1.0 / k), np.r_[np.full(k - 1, 0.5 / (k - 1)), 0.5]]
    best = None
    for s in starts:
        r = minimize(obj, s, jac=grad, method="SLSQP", bounds=bounds, constraints=cons,
                     options={"maxiter": 500, "ftol": 1e-12})
        if best is None or r.fun < best.fun:
            best = r
    c = np.clip(best.x, 0, None); c = c / c.sum()
    return c, float(obj(c))

class LinearConvex:
    """f = kappa * sum_k c_k Z_k with c on the simplex, the last component (a long-run level) weighted at
    least floor_last so that every forecast is positive; fitted by canonical QLIKE."""
    def __init__(self, Z: pd.DataFrame, kappa, floor_last=0.05):
        self.Z = Z; self.kappa = kappa if isinstance(kappa, pd.Series) else pd.Series(float(kappa), index=Z.index)
        self.defined = Z.notna().all(axis=1) & self.kappa.notna() & (self.kappa > 0) & (Z.iloc[:, -1] > 0)
        self.grid = "continuous"; self.floor_last = floor_last
    def forecast(self, c):
        return pd.Series(self.kappa.to_numpy() * (self.Z.to_numpy() @ np.asarray(c, float)), index=self.Z.index)
    def fit(self, y, rows):
        Zr = self.Z[rows].to_numpy() * self.kappa[rows].to_numpy()[:, None]; yr = y[rows].to_numpy()
        return fit_simplex(Zr, yr, self.floor_last)

def market_state(ratio: pd.Series, date: pd.Series, how="median"):
    g = ratio.replace([np.inf, -np.inf], np.nan).groupby(date)
    m = g.median() if how == "median" else g.mean()
    return date.map(m)
