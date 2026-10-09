"""Anam's estimator as a forecasting model: fit it to history, then forecast the coming sessions' volatility.

The forecast is the one the paper evaluated (Section 6.8, Table 34). For a horizon of h sessions, at the
last session t,

    forecast = kappa_t * (phi * mean of A over the last h sessions + (1 - phi) * mean of A over the last 250)

where A is the estimator's daily kernel and kappa_t its calibration to close-to-close variance. The
shrinkage phi toward the long-run level is the one model parameter: ``fit`` chooses it from a grid by
minimising the QLIKE loss of past forecasts of the mean squared close-to-close return over the next h
sessions. The arithmetic is that of the paper's forecast test (``nepsevol.volforecast``), so a model
fitted on a paper's training span reproduces the paper's test losses.
"""
from __future__ import annotations

import json
import pathlib
import warnings

import numpy as np
import pandas as pd

from ._version import __version__
from .core import LAMBDA0, MIN_POOL_DATES, MIN_SERIES_SESSIONS, POOL_SESSIONS, SERIES_SESSIONS
from .data import prepare, resolve_mode
from .estimator import annualization, estimate, resolve_form

__all__ = ["AnamModel", "qlike", "PHI_GRID", "LONGRUN_SESSIONS", "LONGRUN_MIN"]

#: the long-run level the forecast shrinks toward: the kernel's mean over the last 250 sessions (at least 60)
LONGRUN_SESSIONS = 250
LONGRUN_MIN = 60
#: shrinkage weights tried by ``fit`` (phi > 1 extrapolates recent changes)
PHI_GRID = tuple(float(x) for x in np.linspace(0.0, 2.0, 41))


def qlike(realised, forecast):
    """QLIKE loss of a variance forecast: q - ln q - 1 with q = realised / forecast (zero when exact)."""
    q = np.asarray(realised, dtype=float) / np.asarray(forecast, dtype=float)
    return q - np.log(q) - 1.0


def _trailing_sum(s: pd.Series, by: pd.Series, n: int, minp: int) -> pd.Series:
    return s.groupby(by, sort=False).transform(lambda z: z.rolling(n, min_periods=minp).sum())


class AnamModel:
    """Anam's estimator as a volatility model.

    Parameters
    ----------
    form : {"full", "open-free"}
        ``"full"`` measures the open's weight b from the data; ``"open-free"`` sets b = 0 and reads only
        the previous close, the high, the low and the close.
    window : int
        Sessions in each variance estimate of :meth:`variance_path` (default 21).
    horizon : int
        Sessions ahead that :meth:`forecast` covers by default (default 5).
    mode : {"auto", "panel", "series"}
        Pool b and the calibration across securities (``"panel"``) or use each series' own history
        (``"series"``); ``"auto"`` pools when there is more than one security.
    annualize : None, float or "observed"
        Report annualised volatility too, using this many sessions per year, or the market's own
        observed count.

    Examples
    --------
    >>> model = AnamModel(form="open-free").fit(prices)        # doctest: +SKIP
    >>> model.forecast()                                       # doctest: +SKIP
    """

    def __init__(self, form: str = "full", window: int = 21, horizon: int = 5, mode: str = "auto",
                 annualize=None, lam0: float = LAMBDA0, phi_grid=PHI_GRID):
        self.form = resolve_form(form)
        self.window, self.horizon = int(window), int(horizon)
        if self.window < 1 or self.horizon < 1:
            raise ValueError("window and horizon must be at least 1")
        if mode not in ("auto", "panel", "series"):
            raise ValueError(f"mode must be 'auto', 'panel' or 'series', got {mode!r}")
        self.mode = mode
        self.annualize = annualize
        self.lam0 = float(lam0)
        self.phi_grid = tuple(float(x) for x in phi_grid)
        if not self.phi_grid:
            raise ValueError("phi_grid is empty")
        self.phis_: dict[int, float] = {}
        self.train_end_ = None
        self._fitted = None
        self._comps: dict[int, pd.DataFrame] = {}

    # ── fitting ────────────────────────────────────────────────────────────────────────────

    def fit(self, data: pd.DataFrame, *, train_end=None, symbol: str | None = None, date: str | None = None,
            prev_close: str | None = None, max_gap_days: float | None = None, on_invalid: str = "nan"):
        """Fit the model to daily bars.

        ``train_end`` (optional): choose phi only from forecast origins dated before it, so that
        :meth:`score` can measure the loss after it out of sample. The other arguments are passed to
        :func:`anam_estimator.prepare`.
        """
        self._fitted = self._load(data, symbol=symbol, date=date, prev_close=prev_close,
                                  max_gap_days=max_gap_days, on_invalid=on_invalid)
        self.train_end_ = None if train_end is None else pd.Timestamp(train_end)
        self.phis_, self._comps = {}, {}
        self.phi_ = self.phi(self.horizon)
        return self

    def _load(self, data, **kw):
        p = prepare(data, **kw)
        mode = resolve_mode(self.mode, p)
        path = estimate(p, form=self.form, window=self.window, mode=mode, lam0=self.lam0)
        return p, mode, path

    def _components(self, p: pd.DataFrame, mode: str, path: pd.DataFrame, h: int) -> pd.DataFrame:
        # The bars with a full set of coordinates are the frame the paper's forecast test ran on; within
        # it the kernel is still undefined until b has enough history, exactly as there.
        use = path["r2"].notna()
        q, X, r2 = p[use], path.loc[use, "kernel"], path.loc[use, "r2"]
        sym, date = q["symbol"], q["date"]
        valid = X.notna() & r2.notna()
        Xv, rv = X.where(valid), r2.where(valid)
        cur = Xv.groupby(sym, sort=False).transform(lambda z: z.rolling(h, min_periods=h).mean())
        n = Xv.notna().astype(float).groupby(sym, sort=False).transform(
            lambda z: z.rolling(LONGRUN_SESSIONS, min_periods=LONGRUN_MIN).sum())
        lr = _trailing_sum(Xv, sym, LONGRUN_SESSIONS, LONGRUN_MIN) / n
        if mode == "panel":
            L, m = POOL_SESSIONS, min(MIN_POOL_DATES, POOL_SESSIONS)
            num, den = rv.groupby(date).sum(), Xv.groupby(date).sum()
            kappa = date.map(num.rolling(L, min_periods=m).sum() / den.rolling(L, min_periods=m).sum())
        else:
            L, m = SERIES_SESSIONS, min(MIN_SERIES_SESSIONS, SERIES_SESSIONS)
            kappa = _trailing_sum(rv, sym, L, m) / _trailing_sum(Xv, sym, L, m)
        fut = r2.groupby(sym, sort=False).transform(
            lambda z: z[::-1].rolling(h, min_periods=h).mean()[::-1].shift(-1))
        ready = kappa.notna() & cur.notna() & lr.notna() & (kappa * cur > 0) & (lr > 0)
        out = pd.DataFrame({"kappa": kappa, "cur": cur, "lr": lr, "fut": fut, "ready": ready}, index=q.index)
        out = out.reindex(p.index)
        out["ready"] = out["ready"].fillna(False).astype(bool)
        return out

    def _comps_fitted(self, h: int) -> pd.DataFrame:
        if h not in self._comps:
            self._comps[h] = self._components(*self._fitted, h)
        return self._comps[h]

    @staticmethod
    def _losses(c: pd.DataFrame, phi: float, rows: pd.Series) -> pd.Series:
        f = c["kappa"] * (phi * c["cur"] + (1 - phi) * c["lr"])
        ok = rows & c["ready"] & c["fut"].notna() & (c["fut"] > 0) & (f > 0)
        return pd.Series(qlike(c.loc[ok, "fut"], f[ok]), index=c.index[ok])

    def phi(self, horizon: int | None = None) -> float:
        """The fitted shrinkage weight for ``horizon`` sessions (fitted on first use for a new horizon)."""
        h = int(horizon or self.horizon)
        if h in self.phis_:
            return self.phis_[h]
        if self._fitted is None:
            raise RuntimeError(f"phi for a {h}-session horizon is not fitted: call fit() first")
        c = self._comps_fitted(h)
        dates = self._fitted[0]["date"]
        train = pd.Series(True, index=c.index) if self.train_end_ is None else dates < self.train_end_
        n = len(self._losses(c, self.phi_grid[0], train))
        if n == 0:
            raise ValueError("not enough history to fit: each series needs about 120 valid sessions in "
                             "series mode (b and the calibration need 60, the long-run level 60 more), "
                             f"plus {h} to score a {h}-session forecast")
        self.phis_[h] = float(min(self.phi_grid, key=lambda ph: self._losses(c, ph, train).mean()))
        return self.phis_[h]

    # ── using the model ────────────────────────────────────────────────────────────────────

    def forecast(self, data: pd.DataFrame | None = None, *, horizon: int | None = None, **prepare_kw) -> pd.DataFrame:
        """Forecast the mean daily variance over the next ``horizon`` sessions for every security.

        Without ``data`` the forecast is made at the end of the fitted data; with ``data`` (for example,
        the same series with newer sessions) the fitted phi is applied to it, without refitting. Each
        security's forecast is made at its last session with enough history; ``as_of`` says which.
        """
        h = int(horizon or self.horizon)
        ph = self.phi(h)
        if data is None:
            if self._fitted is None:
                raise RuntimeError("pass data, or call fit() first")
            p, mode, path = self._fitted
            c = self._comps_fitted(h)
        else:
            p, mode, path = self._load(data, **prepare_kw)
            c = self._components(p, mode, path, h)
        ready = c.index[c["ready"]]
        last = p.loc[ready].groupby("symbol", sort=False).tail(1).index
        f = c.loc[last, "kappa"] * (ph * c.loc[last, "cur"] + (1 - ph) * c.loc[last, "lr"])
        out = pd.DataFrame({"symbol": p.loc[last, "symbol"], "as_of": p.loc[last, "date"], "horizon": h,
                            "variance": f, "volatility": np.sqrt(f), "b": path.loc[last, "b"],
                            "kappa": c.loc[last, "kappa"], "phi": ph})
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
        """The estimator on every bar: b, the calibration kappa, the ``window``-session variance and
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
        out = pd.DataFrame({"symbol": p["symbol"], "date": p["date"], "b": path["b"], "kappa": path["kappa"],
                            "variance": path["variance"], "volatility": np.sqrt(path["variance"]),
                            "cc_variance": cc})
        n = annualization(self.annualize, p["date"])
        if n is not None:
            out["volatility_annualized"] = np.sqrt(path["variance"] * n)
        return out

    def backtest(self, *, start=None, end=None, horizon: int | None = None) -> pd.DataFrame:
        """Every forecast the fitted model would have made on the fitted data, beside what followed.

        One row per forecast origin dated from ``start`` (default: ``train_end`` if one was given, else
        the beginning) and before ``end``: ``symbol``, ``date`` (the origin), ``forecast`` (mean daily
        variance over the next ``horizon`` sessions), ``realised`` (the mean squared close-to-close
        return over those sessions) and its ``qlike`` loss. Origins before ``train_end`` are in sample:
        phi was chosen on them.
        """
        if self._fitted is None:
            raise RuntimeError("call fit() first")
        h = int(horizon or self.horizon)
        c = self._comps_fitted(h)
        p = self._fitted[0]
        start = self.train_end_ if start is None else pd.Timestamp(start)
        rows = pd.Series(True, index=c.index)
        if start is not None:
            rows &= p["date"] >= start
        if end is not None:
            rows &= p["date"] < pd.Timestamp(end)
        ph = self.phi(h)
        loss = self._losses(c, ph, rows)
        i = loss.index
        f = c.loc[i, "kappa"] * (ph * c.loc[i, "cur"] + (1 - ph) * c.loc[i, "lr"])
        return pd.DataFrame({"symbol": p.loc[i, "symbol"], "date": p.loc[i, "date"], "forecast": f,
                             "realised": c.loc[i, "fut"], "qlike": loss}).reset_index(drop=True)

    def score(self, *, start=None, end=None, horizon: int | None = None) -> float:
        """Mean QLIKE loss of :meth:`backtest` (same arguments); the number of origins scored is left
        in ``n_scored_``."""
        bt = self.backtest(start=start, end=end, horizon=horizon)
        self.n_scored_ = int(len(bt))
        return float(bt["qlike"].mean()) if len(bt) else float("nan")

    def summary(self) -> dict:
        """What was fitted, on what."""
        d = {"form": self.form, "window": self.window, "horizon": self.horizon, "phi": dict(self.phis_)}
        if self._fitted is not None:
            p, mode, path = self._fitted
            d.update(mode=mode, securities=int(p["symbol"].nunique()), bars=int(len(p)),
                     bars_used=int(path["kernel"].notna().sum()), first_date=str(p["date"].min().date()),
                     last_date=str(p["date"].max().date()),
                     latest_b=float(path.groupby(p["symbol"])["b"].last().median()),
                     train_end=None if self.train_end_ is None else str(self.train_end_.date()))
        return d

    # ── persistence ────────────────────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        return {"form": self.form, "window": self.window, "horizon": self.horizon, "mode": self.mode,
                "annualize": self.annualize, "lam0": self.lam0, "phi_grid": list(self.phi_grid)}

    def to_dict(self) -> dict:
        """The model's settings and fitted weights (not the data) as plain JSON types."""
        return {"model": "AnamModel", "package_version": __version__, **self.get_params(),
                "phis": {str(k): v for k, v in self.phis_.items()},
                "train_end": None if self.train_end_ is None else self.train_end_.isoformat()}

    @classmethod
    def from_dict(cls, d: dict) -> "AnamModel":
        m = cls(form=d["form"], window=d["window"], horizon=d["horizon"], mode=d["mode"],
                annualize=d.get("annualize"), lam0=d.get("lam0", LAMBDA0), phi_grid=d.get("phi_grid", PHI_GRID))
        m.phis_ = {int(k): float(v) for k, v in d.get("phis", {}).items()}
        m.train_end_ = None if d.get("train_end") is None else pd.Timestamp(d["train_end"])
        if m.horizon in m.phis_:
            m.phi_ = m.phis_[m.horizon]
        return m

    def save(self, path) -> None:
        """Write the fitted settings to a JSON file; :meth:`load` reads it back."""
        pathlib.Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    @classmethod
    def load(cls, path) -> "AnamModel":
        return cls.from_dict(json.loads(pathlib.Path(path).read_text()))

    def __repr__(self) -> str:
        ph = f", phi={self.phis_[self.horizon]:.2f}" if self.horizon in self.phis_ else ""
        return (f"AnamModel(form={self.form!r}, window={self.window}, horizon={self.horizon}, "
                f"mode={self.mode!r}{ph})")
