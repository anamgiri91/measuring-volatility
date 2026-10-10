"""Anam II: the market-implied open, and a factor HAR forecast of it.

Anam's estimator reads the overnight move through one coefficient, b. In a panel the overnight move has two
parts:

* the market's move, the cross-sectional mean, most of which the session keeps;
* each stock's own remainder, of which it keeps less (in every frontier panel the paper examines).

One coefficient shrinks both by the same factor. Anam II reads the market's move from the other stocks' opens,
so it carries none of the stock's own opening error, and uses it where the stock's own open says nothing: where
the open printed exactly at the previous close.

For security i on date t, with o, c, u, d, r, h, l as in :func:`anam_estimator.bar_coordinates`:

1. ``m``: the equal-weighted mean of o over the panel's other securities that date (0 if there is none);
2. ``o*``: m where the open printed at the previous close (|o| < 1e-12), 0 elsewhere (and 0 for a series);
3. the kernel ``A = (1 - w)[o*^2 + R*^2 / D] + w r^2``, with ``R* = max(h, o*) - min(l, o*)``, ``w = 0.2`` and
   ``D = 4 ln 2``, except ``D = 1`` on a one-price bar (H = L). Where the open moved, it is the open-free
   kernel;
4. the calibration kappa of Anam's estimator, pooled over 60 dates (panel) or the series' own 250 sessions;
5. the forecast of the mean squared close-to-close return over the next h sessions:
   ``f = kappa * sum_k c_k Z_k``. The weights are convex, the last at least 0.05, and are fitted by
   minimising QLIKE. The components Z are:

   * the kernel's day, 5-row and 22-row means;
   * its long-run mean lr scaled by the cross-sectional medians of m5/lr and m22/lr (panels only);
   * the stock's own long-run mean of r^2 (divided by kappa);
   * lr (250 rows, at least 60).

The arithmetic is the research code's (``nepsevol.estimators.anam2`` in the parent repository), which plan M22
froze before testing; the parent repository's tests check that the two agree. Fitting the weights needs SciPy
(``pip install "anam-estimator[market]"``).

EVIDENCE. See the README's model card: plan M22 tested this forecast on markets it was not designed on.
"""
from __future__ import annotations

import json
import pathlib
import warnings

import numpy as np
import pandas as pd

from ._version import __version__
from .core import (LAMBDA0, LN2, MIN_POOL_DATES, MIN_SERIES_SESSIONS, POOL_SESSIONS, SERIES_SESSIONS,
                   bar_coordinates)
from .data import prepare, resolve_mode
from .estimator import annualization
from .evaluation import (clean_square, forward_target, purged, qlike_canonical, qlike_normalized,
                         rolling_mean_exact, session_ordinal)

__all__ = ["EPS", "FLOOR", "market_move", "effective_open", "market_kernel", "estimate_market", "fit_weights",
           "AnamIIModel"]

#: a log price difference below this is zero (an open at the previous close; a one-price bar)
EPS = 1e-12
#: the least weight on the long-run level
FLOOR = 0.05
LONGRUN_SESSIONS = 250
LONGRUN_MIN = 60


def market_move(o: pd.Series, date: pd.Series) -> pd.Series:
    """The leave-one-out equal-weighted mean of ``o`` over the other securities on the same date (0 where no
    other security has an observed ``o``)."""
    s = o.groupby(date).transform("sum")
    n = o.notna().groupby(date).transform("sum")
    own = o.notna().astype(float)
    m = (s - o.fillna(0.0)) / (n - own)
    return m.where((n - own) > 0).fillna(0.0)


def effective_open(o: pd.Series, date: pd.Series, mode: str) -> pd.Series:
    """o*: the market's move where the open printed at the previous close, 0 elsewhere (and 0 for a series)."""
    if mode != "panel":
        return pd.Series(0.0, index=o.index)
    return market_move(o, date).where(o.abs() < EPS, 0.0)


def market_kernel(o: pd.Series, c: pd.Series, u: pd.Series, d: pd.Series, ostar: pd.Series,
                  lam0: float = LAMBDA0) -> pd.Series:
    """Anam II's daily kernel ``(1 - w)[o*^2 + R*^2 / D] + w r^2``."""
    r = o + c
    h = o + u
    l = o + d
    R = np.maximum(h, ostar) - np.minimum(l, ostar)
    D = pd.Series(4.0 * LN2, index=o.index).where(~((u - d).abs() < EPS), 1.0)
    return (1.0 - lam0) * (ostar * ostar + R * R / D) + lam0 * r * r


def _kappa(X: pd.Series, r2: pd.Series, symbol: pd.Series, date: pd.Series, mode: str) -> pd.Series:
    valid = X.notna() & r2.notna()
    Xv, rv = X.where(valid), r2.where(valid)
    if mode == "panel":
        num, den = rv.groupby(date).sum(), Xv.groupby(date).sum()
        m = min(MIN_POOL_DATES, POOL_SESSIONS)
        return date.map(num.rolling(POOL_SESSIONS, min_periods=m).sum() / den.rolling(POOL_SESSIONS, min_periods=m).sum())
    m = min(MIN_SERIES_SESSIONS, SERIES_SESSIONS)
    roll = lambda s: s.groupby(symbol, sort=False).transform(lambda z: z.rolling(SERIES_SESSIONS, min_periods=m).sum())
    return roll(rv) / roll(Xv)


def estimate_market(prepared: pd.DataFrame, *, window: int = 21, mode: str = "panel",
                    lam0: float = LAMBDA0) -> pd.DataFrame:
    """Anam II's estimate on a frame from :func:`anam_estimator.prepare`: ``ostar, kernel, kappa, variance, r2``
    aligned with ``prepared`` (NaN on bars without a previous close or with an invalid bar)."""
    if mode not in ("panel", "series"):
        raise ValueError(f"mode must be 'panel' or 'series', got {mode!r}")
    window = int(window)
    co = bar_coordinates(prepared["open"], prepared["high"], prepared["low"], prepared["close"],
                         prepared["prev_close"])
    use = co[["o", "c", "u", "d"]].notna().all(axis=1)
    p, co = prepared[use], co[use]
    ostar = effective_open(co["o"], p["date"], mode)
    A = market_kernel(co["o"], co["c"], co["u"], co["d"], ostar, lam0=lam0)
    r2 = co["r"] ** 2
    kappa = _kappa(clean_square(A), clean_square(r2), p["symbol"], p["date"], mode)
    mean_A = A.groupby(p["symbol"], sort=False).transform(lambda z: z.rolling(window, min_periods=window).mean())
    out = pd.DataFrame({"ostar": ostar, "kernel": A, "kappa": kappa, "variance": kappa * mean_A, "r2": r2},
                       index=p.index)
    return out.reindex(prepared.index)


def fit_weights(Zr: np.ndarray, yr: np.ndarray, floor: float = FLOOR) -> tuple[np.ndarray, float]:
    """Convex weights (the last at least ``floor``) minimising mean(y/f + ln f), f = Zr @ c: SLSQP with the
    exact gradient from two starts. Needs SciPy."""
    try:
        from scipy.optimize import minimize
    except ImportError as e:  # pragma: no cover - exercised only without SciPy
        raise ImportError('AnamIIModel needs SciPy to fit its weights: pip install "anam-estimator[market]" '
                          "(or pip install scipy)") from e
    k = Zr.shape[1]

    def obj(c):
        f = np.maximum(Zr @ c, 1e-300)
        return float(np.mean(yr / f + np.log(f)))

    def grad(c):
        f = np.maximum(Zr @ c, 1e-300)
        return Zr.T @ (1.0 / f - yr / (f * f)) / len(yr)

    cons = [{"type": "eq", "fun": lambda c: c.sum() - 1.0, "jac": lambda c: np.ones_like(c)}]
    bounds = [(0.0, 1.0)] * (k - 1) + [(floor, 1.0)]
    best = None
    for s in (np.full(k, 1.0 / k), np.r_[np.full(k - 1, 0.5 / (k - 1)), 0.5]):
        res = minimize(obj, s, jac=grad, method="SLSQP", bounds=bounds, constraints=cons,
                       options={"maxiter": 500, "ftol": 1e-12})
        if best is None or res.fun < best.fun:
            best = res
    c = np.clip(best.x, 0.0, None)
    c = c / c.sum()
    return c, obj(c)


class AnamIIModel:
    """Anam II as a volatility model: the market-implied kernel and a factor HAR with the stock's own level.

    Parameters
    ----------
    horizon : int
        Sessions ahead that :meth:`forecast` covers by default (default 5).
    window : int
        Sessions in each variance estimate of :meth:`variance_path` (default 21).
    mode : {"auto", "panel", "series"}
        ``"panel"`` reads the market's move from the cross-section and pools the calibration; ``"series"``
        (one security) has no market move and drops the factor terms; ``"auto"`` pools when there is more than
        one security.
    annualize : None, float or "observed"
        Report annualised volatility too.
    calendar : sequence of dates, optional
        The market's sessions (default: every date in the data).

    Examples
    --------
    >>> model = AnamIIModel(horizon=5).fit(prices)     # doctest: +SKIP
    >>> model.forecast()                               # doctest: +SKIP
    """

    def __init__(self, horizon: int = 5, window: int = 21, mode: str = "auto", annualize=None,
                 lam0: float = LAMBDA0, calendar=None):
        self.horizon, self.window = int(horizon), int(window)
        if self.window < 1 or self.horizon < 1:
            raise ValueError("window and horizon must be at least 1")
        if mode not in ("auto", "panel", "series"):
            raise ValueError(f"mode must be 'auto', 'panel' or 'series', got {mode!r}")
        self.mode, self.annualize, self.lam0 = mode, annualize, float(lam0)
        self.calendar = None if calendar is None else pd.DatetimeIndex(pd.to_datetime(list(calendar)))
        self.weights_: dict[int, list[float]] = {}
        self.components_: list[str] | None = None
        self.train_end_ = None
        self._fitted = None
        self._comps: dict[int, pd.DataFrame] = {}

    # ── data ───────────────────────────────────────────────────────────────────────────────

    def _load(self, data, **kw):
        p = prepare(data, **kw)
        mode = resolve_mode(self.mode, p)
        path = estimate_market(p, window=self.window, mode=mode, lam0=self.lam0)
        return p, mode, path

    def _components(self, p: pd.DataFrame, mode: str, path: pd.DataFrame, h: int) -> pd.DataFrame:
        use = path["r2"].notna()
        r2_all = clean_square(path["r2"])
        q = p[use]
        sym, date = q["symbol"], q["date"]
        A, r2 = clean_square(path.loc[use, "kernel"]), r2_all[use]
        kappa = path.loc[use, "kappa"]
        Xv = A.where(A.notna() & r2.notna())
        lr = rolling_mean_exact(Xv, sym, LONGRUN_SESSIONS, LONGRUN_MIN)
        m5, m22 = rolling_mean_exact(Xv, sym, 5), rolling_mean_exact(Xv, sym, 22)
        Z = {"d1": Xv, "m5": m5, "m22": m22}
        if mode == "panel":
            state = lambda x: date.map(x.replace([np.inf, -np.inf], np.nan).groupby(date).median())
            Z["lrM5"] = lr * state(m5 / lr)
            Z["lrM22"] = lr * state(m22 / lr)
        Z["lrCC"] = rolling_mean_exact(r2, sym, LONGRUN_SESSIONS, LONGRUN_MIN) / kappa
        Z["lr"] = lr
        out = pd.DataFrame(Z, index=q.index)
        ready = out.notna().all(axis=1) & kappa.notna() & (kappa > 0) & (lr > 0)
        out["kappa"] = kappa
        out["ready"] = ready
        out = out.reindex(p.index)
        out["ready"] = out["ready"].fillna(False).astype(bool)
        ses = session_ordinal(p["date"], self.calendar)
        tgt = forward_target(r2_all, p["symbol"], ses, h)
        out["fut"] = tgt["y"]
        out["end_session"] = tgt["end_session"]
        return out

    def _cols(self, c: pd.DataFrame) -> list[str]:
        return [k for k in ("d1", "m5", "m22", "lrM5", "lrM22", "lrCC", "lr") if k in c.columns]

    def _comps_fitted(self, h: int) -> pd.DataFrame:
        if h not in self._comps:
            self._comps[h] = self._components(*self._fitted, h)
        return self._comps[h]

    def _forecast(self, c: pd.DataFrame, w) -> pd.Series:
        return c["kappa"] * (c[self._cols(c)].to_numpy() @ np.asarray(w, float))

    # ── fitting ────────────────────────────────────────────────────────────────────────────

    def fit(self, data: pd.DataFrame, *, train_end=None, symbol: str | None = None, date: str | None = None,
            prev_close: str | None = None, max_gap_days: float | None = None, on_invalid: str = "nan"):
        """Fit the weights to daily bars. With ``train_end``, only origins whose whole outcome window ends
        before it are used, so :meth:`score` measures the loss after it out of sample."""
        self._fitted = self._load(data, symbol=symbol, date=date, prev_close=prev_close,
                                  max_gap_days=max_gap_days, on_invalid=on_invalid)
        self.train_end_ = None if train_end is None else pd.Timestamp(train_end)
        self.weights_, self._comps = {}, {}
        self.weights(self.horizon)
        return self

    def weights(self, horizon: int | None = None) -> np.ndarray:
        """The fitted weights for ``horizon`` sessions (fitted on first use for a new horizon), in the order of
        ``components_``."""
        h = int(horizon or self.horizon)
        if h in self.weights_:
            return np.asarray(self.weights_[h])
        if self._fitted is None:
            raise RuntimeError(f"weights for a {h}-session horizon are not fitted: call fit() first")
        c = self._comps_fitted(h)
        rows = c["ready"] & c["fut"].notna()
        if self.train_end_ is not None:
            cal = (self.calendar if self.calendar is not None else pd.DatetimeIndex(self._fitted[0]["date"])).unique()
            rows &= purged(c["end_session"], int((cal < self.train_end_).sum())).to_numpy()
        if not rows.any():
            raise ValueError("not enough history to fit: each security needs at least 60 bars with a previous close "
                             "(the long-run levels, and a single series' calibration, need 60 observed rows), plus "
                             f"{h} consecutive sessions to score a {h}-session forecast")
        cols = self._cols(c)
        Zr = c.loc[rows, cols].to_numpy() * c.loc[rows, "kappa"].to_numpy()[:, None]
        w, _ = fit_weights(Zr, c.loc[rows, "fut"].to_numpy())
        self.weights_[h] = [float(x) for x in w]
        self.components_ = cols
        return w

    # ── using the model ────────────────────────────────────────────────────────────────────

    def forecast(self, data: pd.DataFrame | None = None, *, horizon: int | None = None, **prepare_kw) -> pd.DataFrame:
        """Forecast the mean daily variance over the next ``horizon`` sessions for every security, at its last
        session with enough history (``as_of``); with ``data``, the fitted weights are applied to it."""
        h = int(horizon or self.horizon)
        w = self.weights(h)
        if data is None:
            if self._fitted is None:
                raise RuntimeError("pass data, or call fit() first")
            p, mode, path = self._fitted
            c = self._comps_fitted(h)
        else:
            p, mode, path = self._load(data, **prepare_kw)
            c = self._components(p, mode, path, h)
        if len(self._cols(c)) != len(w):
            raise ValueError("the data's mode differs from the fitted model's (panel against series)")
        ready = c.index[c["ready"]]
        last = p.loc[ready].groupby("symbol", sort=False).tail(1).index
        f = self._forecast(c.loc[last], w)
        out = pd.DataFrame({"symbol": p.loc[last, "symbol"], "as_of": p.loc[last, "date"], "horizon": h,
                            "variance": f, "volatility": np.sqrt(f), "kappa": c.loc[last, "kappa"],
                            "market_open": path.loc[last, "ostar"]})
        missing = sorted(set(p["symbol"]) - set(out["symbol"]))
        if missing:
            warnings.warn(f"no forecast for {len(missing)} securities with too little history: "
                          f"{missing[:5]}{' ...' if len(missing) > 5 else ''}", stacklevel=2)
        n = annualization(self.annualize, p["date"])
        if n is not None:
            out["volatility_annualized"] = np.sqrt(f * n)
        return out.reset_index(drop=True)

    predict = forecast

    def variance_path(self, data: pd.DataFrame | None = None, **prepare_kw) -> pd.DataFrame:
        """Anam II's estimate on every bar: the effective open o*, kappa, the ``window``-session variance and
        volatility, and close-to-close variance over the same sessions."""
        if data is None:
            if self._fitted is None:
                raise RuntimeError("pass data, or call fit() first")
            p, mode, path = self._fitted
        else:
            p, mode, path = self._load(data, **prepare_kw)
        used = path["r2"].notna()
        cc = path.loc[used, "r2"].groupby(p.loc[used, "symbol"], sort=False).transform(
            lambda z: z.rolling(self.window, min_periods=self.window).mean()).reindex(p.index)
        out = pd.DataFrame({"symbol": p["symbol"], "date": p["date"], "market_open": path["ostar"],
                            "kappa": path["kappa"], "variance": path["variance"],
                            "volatility": np.sqrt(path["variance"]), "cc_variance": cc})
        n = annualization(self.annualize, p["date"])
        if n is not None:
            out["volatility_annualized"] = np.sqrt(path["variance"] * n)
        return out

    def backtest(self, *, start=None, end=None, horizon: int | None = None) -> pd.DataFrame:
        """Every forecast the fitted model would have made on the fitted data, beside what followed (as
        :meth:`anam_estimator.AnamModel.backtest`)."""
        if self._fitted is None:
            raise RuntimeError("call fit() first")
        h = int(horizon or self.horizon)
        c = self._comps_fitted(h)
        p = self._fitted[0]
        start = self.train_end_ if start is None else pd.Timestamp(start)
        rows = c["ready"] & c["fut"].notna()
        if start is not None:
            rows &= p["date"] >= start
        if end is not None:
            rows &= p["date"] < pd.Timestamp(end)
        i = c.index[rows]
        f = self._forecast(c.loc[i], self.weights(h))
        y = c.loc[i, "fut"]
        return pd.DataFrame({"symbol": p.loc[i, "symbol"], "date": p.loc[i, "date"], "forecast": f,
                             "realised": y, "qlike": qlike_normalized(y, f),
                             "qlike_canonical": qlike_canonical(y, f)}).reset_index(drop=True)

    def score(self, *, start=None, end=None, horizon: int | None = None, loss: str = "normalized") -> float:
        """Mean loss of :meth:`backtest`: normalised QLIKE (positive targets) or canonical (every origin)."""
        if loss not in ("normalized", "canonical"):
            raise ValueError("loss must be 'normalized' or 'canonical'")
        bt = self.backtest(start=start, end=end, horizon=horizon)
        self.n_scored_ = int(len(bt))
        v = bt["qlike" if loss == "normalized" else "qlike_canonical"].dropna()
        return float(v.mean()) if len(v) else float("nan")

    # ── persistence ────────────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {"model": "AnamIIModel", "package_version": __version__, "horizon": self.horizon,
                "window": self.window, "mode": self.mode, "annualize": self.annualize, "lam0": self.lam0,
                "calendar": None if self.calendar is None else [str(x.date()) for x in self.calendar],
                "components": self.components_, "weights": {str(k): v for k, v in self.weights_.items()},
                "train_end": None if self.train_end_ is None else self.train_end_.isoformat()}

    @classmethod
    def from_dict(cls, d: dict) -> "AnamIIModel":
        m = cls(horizon=d["horizon"], window=d["window"], mode=d["mode"], annualize=d.get("annualize"),
                lam0=d.get("lam0", LAMBDA0), calendar=d.get("calendar"))
        m.weights_ = {int(k): [float(x) for x in v] for k, v in d.get("weights", {}).items()}
        m.components_ = d.get("components")
        m.train_end_ = None if d.get("train_end") is None else pd.Timestamp(d["train_end"])
        return m

    def save(self, path) -> None:
        pathlib.Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    @classmethod
    def load(cls, path) -> "AnamIIModel":
        return cls.from_dict(json.loads(pathlib.Path(path).read_text()))

    def __repr__(self) -> str:
        return f"AnamIIModel(horizon={self.horizon}, window={self.window}, mode={self.mode!r})"
