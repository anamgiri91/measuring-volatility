"""A machine-learning volatility forecaster built on Anam's estimator.

EXPERIMENTAL. It has been checked on simulated data only; its evaluation on real markets, under a plan
frozen before testing (M19), has not been run. Nothing here claims it forecasts better than
:class:`anam_estimator.AnamModel` or close-to-close variance.

Gradient-boosted trees (scikit-learn's ``HistGradientBoostingRegressor``) forecast the mean squared
close-to-close return over the next ``horizon`` sessions from features of the daily bars:

* Anam's daily kernel in both forms, close-to-close, Parkinson and overnight variance, each averaged
  over the last 1, 5, 21 and 63 sessions (and the kernel and close-to-close over 250), on a log scale;
* the open's quality b and the two calibrations kappa;
* the share of the last 21 bars with no range and with an open equal to the previous close;
* three log ratios (recent against long-run kernel, close-to-close against range, overnight against
  range) and the market's average kernel and close-to-close variance on the date.

Every feature uses only sessions up to the forecast origin. The trees are fitted with the gamma
deviance, which is exactly twice the QLIKE loss by which the paper scores forecasts, so the model is
trained on the paper's own criterion. The number of boosting rounds is chosen on the last
``validation_share`` of the training dates, with the training targets purged so that none reaches into
the validation dates (or past ``train_end``); the model is then refitted on the whole training span.

Needs scikit-learn::

    pip install "anam-estimator[ml] @ git+https://github.com/anamgiri91/measuring-volatility.git#subdirectory=anam-estimator"
"""
from __future__ import annotations

import pathlib
import warnings

import numpy as np
import pandas as pd

from ._version import __version__
from .core import LAMBDA0, LN2, bar_coordinates
from .data import prepare, resolve_mode
from .estimator import annualization, estimate
from .model import LONGRUN_MIN, LONGRUN_SESSIONS, qlike

__all__ = ["AnamMLModel", "build_features", "future_mean", "FEATURES", "WINDOWS"]

WINDOWS = (1, 5, 21, 63)
EPS = 1e-12
BASE = ("A_of", "A_full", "r2", "P", "o2")
READY = "log_A_of_21"
FEATURES = (
    [f"log_{n}_{w}" for n in BASE for w in WINDOWS]
    + [f"log_A_of_{LONGRUN_SESSIONS}", f"log_r2_{LONGRUN_SESSIONS}", "b", "log_kappa_full", "log_kappa_of",
       "zero_range_21", "stale_open_21", "log_ratio_short_long", "log_ratio_cc_to_range_63",
       "log_ratio_overnight_21", "market_log_A_of_5", "market_log_r2_21"]
)


def _hgb():
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
    except ImportError as e:  # pragma: no cover - exercised only without scikit-learn
        raise ImportError("AnamMLModel needs scikit-learn: pip install 'anam-estimator[ml]' "
                          "(or pip install scikit-learn)") from e
    return HistGradientBoostingRegressor


def _rolling_mean(x: pd.Series, by: pd.Series, n: int, minp: int) -> pd.Series:
    return x.groupby(by, sort=False).transform(lambda z: z.rolling(n, min_periods=minp).mean())


def build_features(prepared: pd.DataFrame, mode: str, lam0: float = LAMBDA0) -> tuple[pd.DataFrame, pd.Series]:
    """The model's features on every bar of a frame from :func:`anam_estimator.prepare` (NaN where a
    feature is not yet defined), and the squared close-to-close return of each bar."""
    full = estimate(prepared, form="full", window=21, mode=mode, lam0=lam0)
    free = estimate(prepared, form="open-free", window=21, mode=mode, lam0=lam0)
    co = bar_coordinates(prepared["open"], prepared["high"], prepared["low"], prepared["close"],
                         prepared["prev_close"])
    use = co[["o", "c", "u", "d"]].notna().all(axis=1)
    q, c = prepared[use], co[use]
    sym, date = q["symbol"], q["date"]
    R = c["u"] - c["d"]
    base = {"A_of": free.loc[use, "kernel"], "A_full": full.loc[use, "kernel"], "r2": c["r"] ** 2,
            "P": R ** 2 / (4.0 * LN2), "o2": c["o"] ** 2}
    F = {}
    for name, x in base.items():
        for w in WINDOWS:
            F[f"log_{name}_{w}"] = np.log(_rolling_mean(x, sym, w, w) + EPS)
    for name in ("A_of", "r2"):
        F[f"log_{name}_{LONGRUN_SESSIONS}"] = np.log(
            _rolling_mean(base[name], sym, LONGRUN_SESSIONS, LONGRUN_MIN) + EPS)
    F["b"] = full.loc[use, "b"]
    with np.errstate(divide="ignore", invalid="ignore"):
        F["log_kappa_full"] = np.log(full.loc[use, "kappa"])
        F["log_kappa_of"] = np.log(free.loc[use, "kappa"])
    F["zero_range_21"] = _rolling_mean((R == 0).astype(float), sym, 21, 21)
    F["stale_open_21"] = _rolling_mean((c["o"] == 0).astype(float), sym, 21, 21)
    F = pd.DataFrame(F, index=q.index)
    F["log_ratio_short_long"] = F["log_A_of_21"] - F[f"log_A_of_{LONGRUN_SESSIONS}"]
    F["log_ratio_cc_to_range_63"] = F["log_r2_63"] - F["log_A_of_63"]
    F["log_ratio_overnight_21"] = F["log_o2_21"] - F["log_A_of_21"]
    for col in ("log_A_of_5", "log_r2_21"):
        F[f"market_{col}"] = F[col].groupby(date).transform("mean")
    return F[FEATURES].reindex(prepared.index), base["r2"].reindex(prepared.index)


def future_mean(r2: pd.Series, prepared: pd.DataFrame, h: int) -> tuple[pd.Series, pd.Series]:
    """The forecast target -- the mean squared close-to-close return over the next ``h`` usable sessions
    of the same security -- and the date of the last of those sessions (for purging)."""
    use = r2.notna()
    s, sym = r2[use], prepared.loc[use, "symbol"]
    fut = s.groupby(sym, sort=False).transform(lambda z: z[::-1].rolling(h, min_periods=h).mean()[::-1].shift(-1))
    end = prepared.loc[use, "date"].groupby(sym, sort=False).shift(-h)
    return fut.reindex(prepared.index), end.reindex(prepared.index)


class AnamMLModel:
    """Gradient-boosted volatility forecaster on Anam's estimator and other daily-bar features.

    Parameters
    ----------
    horizon : int
        Sessions ahead: the model forecasts the mean daily variance over the next ``horizon`` sessions.
    mode : {"auto", "panel", "series"}
        How b and the calibrations are computed (as in :class:`AnamModel`). One model is trained on all
        securities together.
    learning_rate, max_leaf_nodes, min_samples_leaf, l2_regularization, max_iter
        Passed to ``HistGradientBoostingRegressor``. ``min_samples_leaf=None`` uses one thousandth of the
        training rows, and at least 20.
    validation_share : float
        Share of the training dates, at the end, used to choose the number of boosting rounds.
    annualize : None, float or "observed"
        Also report annualised volatility.
    """

    def __init__(self, horizon: int = 5, mode: str = "auto", learning_rate: float = 0.05,
                 max_leaf_nodes: int = 15, min_samples_leaf: int | None = None, l2_regularization: float = 1.0,
                 max_iter: int = 1000, validation_share: float = 0.2, annualize=None, random_state: int = 0):
        self.horizon = int(horizon)
        if self.horizon < 1:
            raise ValueError("horizon must be at least 1")
        if mode not in ("auto", "panel", "series"):
            raise ValueError(f"mode must be 'auto', 'panel' or 'series', got {mode!r}")
        if not 0 < validation_share < 1:
            raise ValueError("validation_share must lie in (0, 1)")
        self.mode = mode
        self.learning_rate, self.max_leaf_nodes = float(learning_rate), int(max_leaf_nodes)
        self.min_samples_leaf, self.l2_regularization = min_samples_leaf, float(l2_regularization)
        self.max_iter, self.validation_share = int(max_iter), float(validation_share)
        self.annualize, self.random_state = annualize, random_state
        self.model_ = None
        self.train_end_ = None
        self._fitted = None

    # ── fitting ────────────────────────────────────────────────────────────────────────────

    def _frame(self, data, **prepare_kw):
        p = prepare(data, **prepare_kw)
        mode = resolve_mode(self.mode, p)
        F, r2 = build_features(p, mode)
        y, end = future_mean(r2, p, self.horizon)
        return p, mode, F, y, end

    def _regressor(self, n_iter: int, n_rows: int):
        leaf = self.min_samples_leaf or max(20, n_rows // 1000)
        return _hgb()(loss="gamma", learning_rate=self.learning_rate, max_iter=n_iter,
                      max_leaf_nodes=self.max_leaf_nodes, min_samples_leaf=leaf,
                      l2_regularization=self.l2_regularization, early_stopping=False,
                      random_state=self.random_state)

    def fit(self, data: pd.DataFrame, *, train_end=None, **prepare_kw):
        """Fit to daily bars; ``train_end`` (optional) keeps every training target before that date, so
        that :meth:`score` after it is out of sample. Other arguments go to :func:`anam_estimator.prepare`."""
        p, mode, F, y, end = self._frame(data, **prepare_kw)
        rows = F[READY].notna() & y.notna() & (y > 0)
        self.train_end_ = None if train_end is None else pd.Timestamp(train_end)
        if self.train_end_ is not None:
            rows &= end < self.train_end_
        dates = np.sort(p.loc[rows, "date"].unique())
        if rows.sum() < 200 or len(dates) < 20:
            raise ValueError("not enough history to fit: each series needs about 100 valid sessions, and the "
                             "training sample at least 200 forecast origins on 20 dates")
        cut = pd.Timestamp(dates[int(len(dates) * (1.0 - self.validation_share))])
        fit_rows = rows & (end < cut)
        val_rows = rows & (p["date"] >= cut)
        first = self._regressor(self.max_iter, int(fit_rows.sum())).fit(F[fit_rows], y[fit_rows])
        yv = y[val_rows].to_numpy()
        curve = np.array([qlike(yv, pred).mean() for pred in first.staged_predict(F[val_rows])])
        self.n_iter_ = int(np.argmin(curve)) + 1
        self.validation_curve_ = curve
        self.validation_cut_ = cut
        self.model_ = self._regressor(self.n_iter_, int(rows.sum())).fit(F[rows], y[rows])
        self.n_train_ = int(rows.sum())
        self.mode_ = mode
        self._fitted = (p, mode, F, y)
        return self

    # ── using the model ────────────────────────────────────────────────────────────────────

    def _check(self):
        if self.model_ is None:
            raise RuntimeError("call fit() or load() first")

    def predict_features(self, F: pd.DataFrame) -> np.ndarray:
        """Forecasts for rows of :func:`build_features` output (mean daily variance over the horizon)."""
        self._check()
        return self.model_.predict(F[FEATURES])

    def forecast(self, data: pd.DataFrame | None = None, **prepare_kw) -> pd.DataFrame:
        """Forecast the mean daily variance over the next ``horizon`` sessions for every security, at its
        last session with enough history (``as_of``). With ``data`` the fitted model is applied to it."""
        self._check()
        if data is None:
            if self._fitted is None:
                raise RuntimeError("pass data: a loaded model keeps no data")
            p, mode, F, _ = self._fitted
        else:
            p, mode, F, _, _ = self._frame(data, **prepare_kw)
        ready = F.index[F[READY].notna()]
        last = p.loc[ready].groupby("symbol", sort=False).tail(1).index
        f = self.predict_features(F.loc[last])
        out = pd.DataFrame({"symbol": p.loc[last, "symbol"].to_numpy(), "as_of": p.loc[last, "date"].to_numpy(),
                            "horizon": self.horizon, "variance": f, "volatility": np.sqrt(f)})
        missing = sorted(set(p["symbol"]) - set(out["symbol"]))
        if missing:
            warnings.warn(f"no forecast for {len(missing)} securities with too little history: "
                          f"{missing[:5]}{' ...' if len(missing) > 5 else ''}", stacklevel=2)
        n = annualization(self.annualize, p["date"])
        if n is not None:
            out["volatility_annualized"] = np.sqrt(f * n)
        return out

    predict = forecast

    def backtest(self, *, start=None, end=None) -> pd.DataFrame:
        """Every forecast the fitted model would have made on the fitted data, beside what followed, for
        origins from ``start`` (default ``train_end``) and before ``end``. Origins before ``train_end`` are
        in sample."""
        self._check()
        if self._fitted is None:
            raise RuntimeError("backtest needs the fitted data")
        p, _, F, y = self._fitted
        start = self.train_end_ if start is None else pd.Timestamp(start)
        rows = F[READY].notna() & y.notna() & (y > 0)
        if start is not None:
            rows &= p["date"] >= start
        if end is not None:
            rows &= p["date"] < pd.Timestamp(end)
        f = self.predict_features(F[rows])
        yr = y[rows].to_numpy()
        return pd.DataFrame({"symbol": p.loc[rows, "symbol"].to_numpy(), "date": p.loc[rows, "date"].to_numpy(),
                             "forecast": f, "realised": yr, "qlike": qlike(yr, f)})

    def score(self, *, start=None, end=None) -> float:
        """Mean QLIKE loss of :meth:`backtest`; the number of origins is left in ``n_scored_``."""
        bt = self.backtest(start=start, end=end)
        self.n_scored_ = int(len(bt))
        return float(bt["qlike"].mean()) if len(bt) else float("nan")

    def feature_importance(self, *, n_repeats: int = 3, max_rows: int = 50_000, start=None) -> pd.Series:
        """Permutation importance of each feature: the rise in mean QLIKE loss when it is shuffled, on the
        backtest rows (out of sample after ``train_end``), at most ``max_rows`` of them."""
        self._check()
        p, _, F, y = self._fitted
        bt_rows = F[READY].notna() & y.notna() & (y > 0)
        start = self.train_end_ if start is None else pd.Timestamp(start)
        if start is not None:
            bt_rows &= p["date"] >= start
        X, yy = F.loc[bt_rows, FEATURES], y[bt_rows].to_numpy()
        rng = np.random.default_rng(self.random_state)
        if len(X) > max_rows:
            keep = np.sort(rng.choice(len(X), max_rows, replace=False))
            X, yy = X.iloc[keep], yy[keep]
        base = qlike(yy, self.model_.predict(X)).mean()
        out = {}
        for col in FEATURES:
            rises = []
            for _ in range(n_repeats):
                Xp = X.copy()
                Xp[col] = rng.permutation(Xp[col].to_numpy())
                rises.append(qlike(yy, self.model_.predict(Xp)).mean() - base)
            out[col] = float(np.mean(rises))
        return pd.Series(out).sort_values(ascending=False)

    # ── persistence ────────────────────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        return {"horizon": self.horizon, "mode": self.mode, "learning_rate": self.learning_rate,
                "max_leaf_nodes": self.max_leaf_nodes, "min_samples_leaf": self.min_samples_leaf,
                "l2_regularization": self.l2_regularization, "max_iter": self.max_iter,
                "validation_share": self.validation_share, "annualize": self.annualize,
                "random_state": self.random_state}

    def save(self, path) -> None:
        """Save the fitted trees and settings (not the data) with joblib. Load only files you trust:
        joblib files are pickles and can run code when loaded."""
        self._check()
        import joblib
        import sklearn
        joblib.dump({"model": "AnamMLModel", "package_version": __version__, "sklearn_version": sklearn.__version__,
                     "params": self.get_params(), "n_iter": self.n_iter_, "features": list(FEATURES),
                     "regressor": self.model_}, pathlib.Path(path))

    @classmethod
    def load(cls, path) -> "AnamMLModel":
        """Load a model written by :meth:`save` (a pickle: only from a source you trust)."""
        import joblib
        d = joblib.load(pathlib.Path(path))
        if d.get("model") != "AnamMLModel" or list(d.get("features", [])) != list(FEATURES):
            raise ValueError("not an AnamMLModel file for this version of the features")
        m = cls(**d["params"])
        m.model_, m.n_iter_ = d["regressor"], d["n_iter"]
        return m

    def __repr__(self) -> str:
        it = f", n_iter={self.n_iter_}" if self.model_ is not None else ""
        return f"AnamMLModel(horizon={self.horizon}, mode={self.mode!r}{it})"
