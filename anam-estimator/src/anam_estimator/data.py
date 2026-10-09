"""Turning a price table into the bars the estimator reads.

Accepted inputs, all returned in one long layout sorted by (symbol, date):

* a long table with a date column, open/high/low/close and, for several securities, a symbol column
  (any capitalisation: ``Date``, ``Open``, ``Ticker`` ... are recognised);
* a single series indexed by date, as returned by most data libraries;
* a wide table with two-level columns (price field x ticker), as returned for several tickers at once.

Prices should be adjusted for splits and stock dividends. If you have the exchange's adjusted previous
close, pass it as ``prev_close``; otherwise the previous row's close of the same symbol is used.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

__all__ = ["prepare", "resolve_mode", "observed_sessions_per_year"]

PRICES = ("open", "high", "low", "close")
SYMBOL_NAMES = ("symbol", "ticker", "code", "trading_code", "security", "stock")
DATE_NAMES = ("date", "datetime", "timestamp", "time", "day")
ON_INVALID = ("nan", "repair", "raise")


def _norm(name) -> str:
    return str(name).strip().lower().replace(" ", "_")


def _from_two_level_columns(df: pd.DataFrame) -> pd.DataFrame:
    """(field, ticker) or (ticker, field) columns -> long table with a symbol column."""
    levels = [[_norm(v) for v in df.columns.get_level_values(i)] for i in (0, 1)]
    field = 0 if set(PRICES) <= set(levels[0]) else 1 if set(PRICES) <= set(levels[1]) else None
    if field is None:
        raise ValueError("two-level columns must hold open, high, low and close for each ticker")
    tick = 1 - field
    if isinstance(df.index, pd.DatetimeIndex) and df.index.name is None:
        df = df.rename_axis("date")
    parts = []
    for t in pd.unique(df.columns.get_level_values(tick)):
        sub = df.xs(t, axis=1, level=tick)
        sub.columns = [_norm(c) for c in sub.columns]
        sub = sub.reset_index()
        sub.insert(0, "symbol", str(t))
        parts.append(sub)
    return pd.concat(parts, ignore_index=True)


def prepare(data: pd.DataFrame, *, symbol: str | None = None, date: str | None = None,
            prev_close: str | None = None, max_gap_days: float | None = None,
            on_invalid: str = "nan") -> pd.DataFrame:
    """Return a clean copy of ``data`` in the layout the estimator reads.

    Columns of the result: ``symbol, date, open, high, low, close, prev_close, valid``, sorted by
    (symbol, date) with a fresh index. ``prev_close`` is the previous row's close of the same symbol
    unless a column is named; with ``max_gap_days`` it is set to NaN where the previous row is more
    than that many calendar days earlier.

    A bar is invalid if a price is missing or not positive, or if the high is below the open, the
    close or the low, or the low above the open or the close. ``on_invalid`` decides what happens:
    ``"nan"`` (default) keeps the row but excludes it from every estimate, with a warning;
    ``"repair"`` widens the high and low to contain the open and close (missing or non-positive
    prices are still excluded); ``"raise"`` stops with the offending rows.
    """
    if on_invalid not in ON_INVALID:
        raise ValueError(f"on_invalid must be one of {ON_INVALID}, got {on_invalid!r}")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if isinstance(data.columns, pd.MultiIndex):
        df = _from_two_level_columns(data)
    else:
        df = data.copy()
        names = [_norm(c) for c in df.columns]
        has_date = (_norm(date) in names) if date else any(n in names for n in DATE_NAMES)
        if isinstance(df.index, pd.DatetimeIndex) and not has_date:
            df = df.rename_axis(df.index.name or "date").reset_index()
    df.columns = [_norm(c) for c in df.columns]

    date_col = _norm(date) if date else next((c for c in DATE_NAMES if c in df.columns), None)
    if date_col is None or date_col not in df.columns:
        raise ValueError("no date column found: name it 'date' or pass date='<column>'")
    sym_col = _norm(symbol) if symbol else next((c for c in SYMBOL_NAMES if c in df.columns), None)
    if symbol and sym_col not in df.columns:
        raise ValueError(f"symbol column {symbol!r} not found")
    missing = [c for c in PRICES if c not in df.columns]
    if missing:
        raise ValueError(f"missing price columns: {missing}")
    pc_col = _norm(prev_close) if prev_close else None
    if pc_col is not None and pc_col not in df.columns:
        raise ValueError(f"prev_close column {prev_close!r} not found")

    out = pd.DataFrame({
        "symbol": df[sym_col].astype(str) if sym_col else "series",
        "date": pd.to_datetime(df[date_col]),
    })
    for c in PRICES:
        out[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    if pc_col is not None:
        out["prev_close"] = pd.to_numeric(df[pc_col], errors="coerce").astype(float)
    if out["date"].isna().any():
        raise ValueError(f"{int(out['date'].isna().sum())} rows have no readable date")
    dup = out.duplicated(["symbol", "date"])
    if dup.any():
        first = out.loc[dup, ["symbol", "date"]].head(3).to_dict("records")
        raise ValueError(f"{int(dup.sum())} duplicated (symbol, date) rows, e.g. {first}")
    out = out.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)

    if pc_col is None:
        out["prev_close"] = out.groupby("symbol", sort=False)["close"].shift(1)
    if max_gap_days is not None:
        gap = out.groupby("symbol", sort=False)["date"].diff().dt.days
        out.loc[gap > max_gap_days, "prev_close"] = np.nan

    o, h, l, c = (out[k] for k in PRICES)
    positive = pd.concat([o, h, l, c], axis=1).gt(0).all(axis=1)
    if on_invalid == "repair":
        out.loc[positive, "high"] = pd.concat([h, o, c], axis=1).max(axis=1)[positive]
        out.loc[positive, "low"] = pd.concat([l, o, c], axis=1).min(axis=1)[positive]
        o, h, l, c = (out[k] for k in PRICES)
    envelope = (h >= o) & (h >= c) & (h >= l) & (l <= o) & (l <= c)
    valid = positive & envelope
    if (~valid).any():
        bad = out.loc[~valid, ["symbol", "date"] + list(PRICES)]
        if on_invalid == "raise":
            raise ValueError(f"{len(bad)} invalid bars (missing, non-positive or outside the high-low "
                             f"envelope), e.g.\n{bad.head(5).to_string(index=False)}")
        warnings.warn(f"{len(bad)} of {len(out)} bars are invalid (missing, non-positive or outside the "
                      "high-low envelope) and are excluded from the estimates; pass on_invalid='repair' to "
                      "widen the high and low instead, or 'raise' to stop", stacklevel=2)
        out.loc[~valid, list(PRICES)] = np.nan
    pcv = out["prev_close"]
    out.loc[pcv.notna() & ~(pcv > 0), "prev_close"] = np.nan
    out["valid"] = valid
    return out


def resolve_mode(mode: str, prepared: pd.DataFrame) -> str:
    """``"auto"`` pools across securities when there is more than one, and otherwise uses the series' own
    history."""
    if mode not in ("auto", "panel", "series"):
        raise ValueError(f"mode must be 'auto', 'panel' or 'series', got {mode!r}")
    if mode != "auto":
        return mode
    return "panel" if prepared["symbol"].nunique() > 1 else "series"


def observed_sessions_per_year(dates) -> float:
    """The market's own annual session count, observed from its dates: session-to-session intervals
    per calendar year. Use it to annualise instead of an imported convention such as 252."""
    d = pd.Series(pd.to_datetime(pd.Series(dates).dropna().unique())).sort_values()
    if len(d) < 2:
        raise ValueError("need at least two distinct dates")
    years = (d.iloc[-1] - d.iloc[0]).days / 365.25
    if years <= 0:
        raise ValueError("the dates span no time")
    return float((len(d) - 1) / years)
