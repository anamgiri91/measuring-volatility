"""Pipeline assertions. These STOP the build; they do not warn.

Audit policy SS8: if an invariant fails, the pipeline must halt. A warning printed into a
long run log is not a guard -- the whole reason several defects in this project survived
into committed results is that nothing refused to continue.

Every check here corresponds to a defect that actually occurred:

* OHLC envelope violations       1,154 rows reached the committed analysis sample
* ``high < low``                 2 rows
* negative GK / RS               970 and 134 rows, all on invalid bars
* duplicated security-days       640 keys, 18 with conflicting prices
* non-equity in an equity sample the retracted D-0012 finding
* month/day-swapped ISO dates    produced a plausible but wrong 0.033
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["SampleValidationError", "validate_analysis_sample"]

_GK_FLOOR = 1.5 - 2 * np.log(2)          # ~0.113706; GK >= this * ln(C/O)^2 on a valid bar


class SampleValidationError(AssertionError):
    """Raised when an analysis sample violates an invariant the science depends on."""


def _fail(msg: str, n: int, example: pd.DataFrame | None = None) -> None:
    detail = ""
    if example is not None and len(example):
        cols = [c for c in ("symbol", "date", "open", "high", "low", "close") if c in example.columns]
        detail = "\n  first offending rows:\n" + example[cols].head(3).to_string(index=False)
    raise SampleValidationError(f"{msg}: {n:,} row(s){detail}")


def validate_analysis_sample(
    df: pd.DataFrame,
    universe: str = "equity",
    expect_sec_type: bool = True,
    keys: tuple[str, ...] = ("symbol", "date"),
) -> None:
    """Assert every invariant an analysis sample must satisfy. Raises on the first failure."""
    if df.empty:
        raise SampleValidationError("analysis sample is empty")

    # --- prices are usable numbers ---------------------------------------------------
    for c in ("open", "high", "low", "close"):
        bad = df[~(df[c] > 0)]
        if len(bad):
            _fail(f"{c} must be strictly positive", len(bad), bad)

    # --- OHLC envelope ---------------------------------------------------------------
    hi_bad = df[df["high"] < df[["open", "close"]].max(axis=1)]
    if len(hi_bad):
        _fail("high < max(open, close)", len(hi_bad), hi_bad)
    lo_bad = df[df["low"] > df[["open", "close"]].min(axis=1)]
    if len(lo_bad):
        _fail("low > min(open, close)", len(lo_bad), lo_bad)
    hl_bad = df[df["high"] < df["low"]]
    if len(hl_bad):
        _fail("high < low", len(hl_bad), hl_bad)

    log_hl = np.log(df["high"] / df["low"])
    neg = df[log_hl < 0]
    if len(neg):
        _fail("log(high/low) < 0", len(neg), neg)

    # --- estimator admissibility -----------------------------------------------------
    k2 = np.log(df["close"] / df["open"]) ** 2
    gk = 0.5 * log_hl**2 - (2 * np.log(2) - 1) * k2
    gk_bad = df[gk < -1e-12]
    if len(gk_bad):
        _fail("Garman-Klass negative on a valid bar (impossible; indicates bad OHLC)",
              len(gk_bad), gk_bad)
    u, d, c = np.log(df.high / df.open), np.log(df.low / df.open), np.log(df.close / df.open)
    rs = u * (u - c) + d * (d - c)
    rs_bad = df[rs < -1e-12]
    if len(rs_bad):
        _fail("Rogers-Satchell negative on a valid bar", len(rs_bad), rs_bad)

    # --- non-negative quantities -----------------------------------------------------
    for c in ("volume", "turnover", "n_trades"):
        if c in df.columns:
            bad = df[df[c].notna() & (df[c] < 0)]
            if len(bad):
                _fail(f"{c} must be non-negative", len(bad), bad)

    # --- sample definition -----------------------------------------------------------
    have = [k for k in keys if k in df.columns]
    if have:
        dup = df[df.duplicated(have, keep=False)]
        if len(dup):
            _fail(f"duplicated {tuple(have)} (an observation is a security-day)", len(dup), dup)

    if universe == "equity" and expect_sec_type:
        if "sec_type" not in df.columns:
            raise SampleValidationError(
                "equity sample has no sec_type column, so the instrument filter cannot be verified"
            )
        bad = df[df["sec_type"] != "equity"]
        if len(bad):
            _fail("non-equity instrument in the equity sample", len(bad), bad)

    # --- dates -----------------------------------------------------------------------
    if "date" in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            raise SampleValidationError("date column is not datetime64")
        if df["date"].isna().any():
            _fail("unparsed dates", int(df["date"].isna().sum()))
        span = (df["date"].min(), df["date"].max())
        if span[0] < pd.Timestamp("1990-01-01") or span[1] > pd.Timestamp.today() + pd.Timedelta(days=1):
            raise SampleValidationError(f"implausible date range {span[0].date()} -> {span[1].date()}")
