"""Anam's estimator as a function: one call from a price table to a volatility estimate."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .core import (LAMBDA0, bar_coordinates, calibration_panel, calibration_series, kernel,
                   open_quality_panel, open_quality_series)
from .data import observed_sessions_per_year, prepare, resolve_mode

__all__ = ["FORMS", "estimate", "anam_estimator", "resolve_form", "annualization"]

FORMS = ("full", "open-free")


def resolve_form(form: str) -> str:
    f = str(form).strip().lower().replace("_", "-")
    if f not in FORMS:
        raise ValueError(f"form must be 'full' (b measured from the data) or 'open-free' (b = 0), got {form!r}")
    return f


def annualization(annualize, dates) -> float | None:
    """None (daily units), a number of sessions per year, or ``"observed"`` for the market's own count."""
    if annualize is None:
        return None
    if isinstance(annualize, str):
        if annualize.strip().lower() != "observed":
            raise ValueError("annualize must be None, a number of sessions per year, or 'observed'")
        return observed_sessions_per_year(dates)
    n = float(annualize)
    if not n > 0:
        raise ValueError("annualize must be positive")
    return n


def estimate(prepared: pd.DataFrame, *, form: str = "full", window: int = 21, mode: str = "panel",
             lam0: float = LAMBDA0) -> pd.DataFrame:
    """The estimator on a frame from :func:`prepare` -- the arithmetic of the research code's
    ``anam_estimator`` exactly. Returns ``b, kernel, kappa, variance, r2`` aligned with
    ``prepared``."""
    form = resolve_form(form)
    if mode not in ("panel", "series"):
        raise ValueError(f"mode must be 'panel' or 'series', got {mode!r}")
    window = int(window)
    if window < 1:
        raise ValueError("window must be at least 1")
    co = bar_coordinates(prepared["open"], prepared["high"], prepared["low"], prepared["close"],
                         prepared["prev_close"])
    # The research code runs on bars that have all four coordinates (a previous close, a valid
    # bar); windows then span only those bars. The rest are left out here too and come back as NaN.
    use = co[["o", "c", "u", "d"]].notna().all(axis=1)
    p, co = prepared[use], co[use]
    grp = p["symbol"]
    if form == "open-free":
        b = pd.Series(0.0, index=p.index)
    elif mode == "panel":
        b = open_quality_panel(co["o"], co["r"], p["date"])
    else:
        b = open_quality_series(co["o"], co["r"], grp)
    A = kernel(co["o"], co["c"], co["u"], co["d"], b, lam0=lam0)
    r2 = co["r"] ** 2
    if mode == "panel":
        kappa = calibration_panel(A, r2, p["date"])
    else:
        kappa = calibration_series(A, r2, grp)
    mean_A = A.groupby(grp, sort=False).transform(lambda z: z.rolling(window, min_periods=window).mean())
    out = pd.DataFrame({"b": b, "kernel": A, "kappa": kappa, "variance": kappa * mean_A, "r2": r2},
                       index=p.index)
    return out.reindex(prepared.index)


def anam_estimator(data: pd.DataFrame, *, form: str = "full", window: int = 21, mode: str = "auto",
                   annualize=None, symbol: str | None = None, date: str | None = None,
                   prev_close: str | None = None, max_gap_days: float | None = None,
                   on_invalid: str = "nan", lam0: float = LAMBDA0) -> pd.DataFrame:
    """Anam's estimator for every bar of ``data``.

    Parameters
    ----------
    data
        Daily bars: a date column (or a date index), ``open``, ``high``, ``low``, ``close`` and, for several
        securities, a ``symbol`` column (see :func:`anam_estimator.prepare` for the accepted layouts).
    form
        ``"full"`` (default): the open's weight b is measured from the data. ``"open-free"``: b = 0, so the
        estimator reads only the previous close, the high, the low and the close. In the paper the
        open-free form had the lower loss of the two wherever b was well below one (every frontier market
        tested), and the full form where the open is close to unbiased (two indices).
    window
        Sessions in each variance estimate (default 21).
    mode
        ``"panel"`` pools b and the calibration across all securities (the last 60 dates);
        ``"series"`` uses each security's own last 250 sessions; ``"auto"`` (default) chooses ``"panel"``
        when there is more than one security.
    annualize
        ``None`` (daily units), a number of sessions per year, or ``"observed"`` to use the market's own
        session count from the dates.

    Returns
    -------
    DataFrame sorted by (symbol, date) with ``symbol, date, b, kappa, variance, volatility,
    cc_variance`` and, when annualising, ``volatility_annualized``. ``variance`` is the calibrated mean
    daily variance of the ``window`` sessions ending on that row; ``cc_variance`` is the plain
    close-to-close variance (mean squared return) of the same sessions, which the paper recommends
    reporting beside it.
    """
    p = prepare(data, symbol=symbol, date=date, prev_close=prev_close, max_gap_days=max_gap_days,
                on_invalid=on_invalid)
    m = resolve_mode(mode, p)
    est = estimate(p, form=form, window=window, mode=m, lam0=lam0)
    window = int(window)
    used = est["r2"].notna()
    cc = est.loc[used, "r2"].groupby(p.loc[used, "symbol"], sort=False).transform(
        lambda z: z.rolling(window, min_periods=window).mean()).reindex(p.index)
    out = pd.DataFrame({"symbol": p["symbol"], "date": p["date"], "b": est["b"], "kappa": est["kappa"],
                        "variance": est["variance"], "volatility": np.sqrt(est["variance"]),
                        "cc_variance": cc})
    n = annualization(annualize, p["date"])
    if n is not None:
        out["volatility_annualized"] = np.sqrt(est["variance"] * n)
    out.attrs.update(mode=m, form=resolve_form(form), window=window, sessions_per_year=n)
    return out
