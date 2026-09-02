"""Detection of NEPSE's price-limit and pre-open band censoring.

NEPSE censors observed prices in two places, and both truncate what a volatility estimator
can see. Neither is a nuisance to be cleaned away: they are the mechanism.

    Pre-open auction band   orders may be placed only within +/- band of the previous close.
                            The OPENING price is censored. Observed +/-2% through 2026-03,
                            widened to +/-5% from 2026-04.

    Daily price limit       the whole session is bounded relative to the previous close, so the
                            HIGH and LOW are censored. Observed +/-10% through 2026-03, widened
                            to +/-15% from 2026-04.

Both were verified from the data rather than assumed: pre-2026-04 the 99th percentile of the
absolute close-to-close move sits at exactly 10.0% with 1.81% of highs pinned at +10% and only
0.07% of moves exceeding 10.5%.

Why this matters for measurement. A binding limit means the reported extreme is the limit, not
the latent extreme. Range-based variance is then censored downward for a reason that has nothing
to do with sampling frequency, and any bias correction calibrated on discretisation alone will
mis-attribute it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["REGIMES", "regime_for", "flag_limits", "censoring_summary",
           "range_ceiling", "flag_infeasible_range"]

# (effective_from, pre_open_band, daily_price_limit) — fractions of the previous close.
# The 2026-04 revision changed BOTH simultaneously, alongside a new intraday circuit breaker and
# round-the-clock order entry. Treatments in that window are therefore CONFOUNDED and must not be
# used as a clean natural experiment.
REGIMES = [
    (pd.Timestamp("1900-01-01"), 0.02, 0.10),
    (pd.Timestamp("2026-04-01"), 0.05, 0.15),
]


def regime_for(dates: pd.Series) -> pd.DataFrame:
    """Band and limit applicable on each date."""
    dates = pd.to_datetime(pd.Series(dates).values)
    band = pd.Series(np.nan, index=range(len(dates)))
    limit = pd.Series(np.nan, index=range(len(dates)))
    for start, b, l in REGIMES:
        m = (dates >= start)
        band[m], limit[m] = b, l
    return pd.DataFrame({"band": band.values, "limit": limit.values}, index=range(len(dates)))


def flag_limits(df: pd.DataFrame, tol: float = 0.05, symbol_col: str = "symbol") -> pd.DataFrame:
    """Flag stock-days where the pre-open band or the daily price limit was binding.

    `tol` is the relative tolerance for calling a value "at" the boundary (0.05 => within 5% of
    the limit itself, e.g. 9.5-10.5% for a 10% limit), which absorbs tick rounding.

    Adds:
        band, limit            the rules in force that day
        open_pinned            opening return within tolerance of +/- band
        open_at_prev_close     open exactly equals previous close (auction found no match)
        high_limited           high within tolerance of the upper daily limit
        low_limited            low within tolerance of the lower daily limit
        range_censored         either extreme was limited -> observed range is truncated
    """
    d = df.copy()
    if symbol_col in d.columns:
        d = d.sort_values([symbol_col, "date"])
        prev_c = d.groupby(symbol_col)["close"].shift(1)
    else:
        d = d.sort_values("date")
        prev_c = d["close"].shift(1)

    reg = regime_for(d["date"])
    d["band"] = reg["band"].values
    d["limit"] = reg["limit"].values

    with np.errstate(divide="ignore", invalid="ignore"):
        r_open = d["open"] / prev_c - 1.0
        r_high = d["high"] / prev_c - 1.0
        r_low = d["low"] / prev_c - 1.0

    lo_b, hi_b = d["band"] * (1 - tol), d["band"] * (1 + tol)
    lo_l, hi_l = d["limit"] * (1 - tol), d["limit"] * (1 + tol)

    d["open_pinned"] = r_open.abs().between(lo_b, hi_b)
    d["open_at_prev_close"] = (r_open == 0) & prev_c.notna()
    d["high_limited"] = r_high.between(lo_l, hi_l)
    d["low_limited"] = (-r_low).between(lo_l, hi_l)
    d["range_censored"] = d["high_limited"] | d["low_limited"]
    return d


def censoring_summary(df: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """Share of stock-days censored by each mechanism, optionally grouped."""
    cols = ["open_pinned", "open_at_prev_close", "high_limited", "low_limited", "range_censored"]
    if by is None:
        out = df[cols].mean().mul(100).to_frame("percent_of_stock_days")
        out.loc["n_observations"] = len(df)
        return out
    g = df.groupby(by)[cols].mean().mul(100)
    g["n"] = df.groupby(by).size()
    return g


def range_ceiling(dates) -> np.ndarray:
    """Maximum log(H/L) a legal session can produce under the prevailing daily price limit.

    The high may exceed the previous close by at most +L and the low may fall below it by at
    most -L, so log(H/L) <= log((1+L)/(1-L)):

        +/-10% regime  ->  0.2007
        +/-15% regime  ->  0.3023

    A rules-derived bound, not a percentile. It screens the RANGE, which the close-to-close
    filter cannot: a corrupted high or low leaves the close untouched, passes every
    return-based screen, and contaminates exactly the inputs a range estimator consumes.
    """
    limit = regime_for(dates)["limit"].values
    return np.log((1 + limit) / (1 - limit))


def flag_infeasible_range(df: pd.DataFrame, tol: float = 1e-4) -> np.ndarray:
    """Boolean mask: sessions whose observed range exceeds what the price limit permits.

    On the NEPSE sample this flags 3 rows in 184,394 (0.0016%), all of them non-equity. One --
    SJLICP on 2024-05-12, a low of 100 (par) against an open of 383 on three trades -- by itself
    supplied 82% of the summed Rogers-Satchell variance of the thinnest liquidity quintile.
    """
    lr = np.log(df["high"].values / df["low"].values)
    return lr > range_ceiling(df["date"]) * (1 + tol)
