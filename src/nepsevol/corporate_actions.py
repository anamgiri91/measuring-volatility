"""Corporate-action detection and ONE previous-close definition for the whole package.

PEER-REVIEW ITEM D / MANDATORY ITEM 4. The 2026-09-02 revision left three previous-close
definitions coexisting in three places, and the reviewer was right that this makes the
opening-return, overnight-return and total-risk results insufficiently secure:

    scripts/03_descriptive.py       the SUPPLIED ``prev_close`` column          (screening)
    nepsevol.clean.limits           ``.shift(1)``, the previous OBSERVED ROW    (auction flags)
    nepsevol.estimators.range_      the previous GENUINE SESSION's close        (YZ, close-to-close)

The previous revision declined to use the supplied column on the grounds that its "provenance
is unaudited". That was an honest position but not a finding. This module performs the audit
the reviewer asked for, and the audit resolves the question rather than merely documenting it.

WHAT THE 315 DISAGREEMENTS ARE
------------------------------
On the ordinary-equity panel the supplied ``prev_close`` disagrees with the previous observed
row's close on 315 stock-days, spread over 190 securities and 131 distinct dates. Writing each
disagreement as an implied adjustment factor

    f = close_{t-1} / prev_close_t

the distribution is not noise. It piles up on the Nepali bonus-share ladder:

    f within 2% of 1.05   79 rows        f within 2% of 1.20   10 rows
    f within 2% of 1.10   48 rows        f within 2% of 1.25    4 rows
    f within 2% of 1.15   34 rows        f within 2% of 1.30    2 rows

310 of the 315 sit on CONSECUTIVE sessions, so they are not gap artifacts. This is NEPSE's
ex-date reference-price adjustment: on the first trading day after book closure the exchange
publishes a previous close already adjusted for the bonus or rights entitlement, so that the
day's published return is the price change and not the mechanical entitlement drop.

That matters for a volatility paper specifically. An unadjusted overnight return on an ex-date
manufactures a price movement that never happened -- a 1:1 bonus registers as a -69% log
return -- and both the close-to-close benchmark and the overnight component of Yang-Zhang are
built from exactly that quantity.

THE ADOPTED DEFINITION
----------------------
One definition is now used everywhere, and it is the one that is correct for measuring price
variation rather than the one that was easiest to compute:

    the close of the previous GENUINE TRADING SESSION, adjusted for a corporate action
    where the exchange's own published previous close evidences one.

Operationally, for a row whose previous session exists:

    prev = prev_close_t   when the supplied column disagrees with close_{t-1} and the
                          disagreement is classified as a corporate action
    prev = close_{t-1}    otherwise

and NaN where there is no previous genuine session, exactly as before. The change is confined
to at most 315 rows of 143,718 (0.219%), and :func:`classify_disagreements` labels every one
of them so the reader can see which rule fired and why.

WHAT IS NOT CLAIMED. This is a detection rule keyed on the exchange's own published reference
price, not a corporate-action feed. It cannot name the entitlement, and a small residual class
-- adjustments below the rounding floor, and the handful where the published previous close
sits ABOVE the prior close -- is labelled ``unexplained`` rather than swept into the corporate-
action bucket. Those rows are reported and their sensitivity is shown; they are not hidden.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["CLASSES", "ROUNDING_TOL", "classify_disagreements", "adjusted_previous_close",
           "corporate_action_flags"]

#: Relative tolerance below which a disagreement is not treated as an entitlement. It is a classification
#: choice, not a rounding bound: two-decimal rounding of a price in the hundreds moves it by about 0.001%,
#: and none of the 315 disagreements is that small (an earlier comment said sub-0.5% disagreements "are
#: not separable from tick rounding"; audit item A11). Entitlement adjustments (bonus and rights issues)
#: move the reference price by several percent, so 0.5% separates them from small reference-price
#: differences of unknown origin, which keep the class name ``reference_rounding`` for stability. At 0.1%
#: or 0.25% the corporate-action count changes from 216 to 221 or 219 (scripts/49_audit_sensitivities.py).
ROUNDING_TOL = 0.005

#: The classes :func:`classify_disagreements` can assign. Ordered from most to least explained.
CLASSES = (
    "corporate_action",       # published previous close is BELOW the prior close: entitlement
    "reference_rounding",     # |f - 1| <= ROUNDING_TOL: tick/rounding, not an event
    "upward_adjustment",      # published previous close is ABOVE the prior close: unexplained
    "session_gap",            # the prior observed row is not the previous genuine session
)


def _implied_factor(prev_close: pd.Series, prior_close: pd.Series) -> pd.Series:
    """f = close_{t-1} / prev_close_t. A bonus/rights adjustment drives f above one."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return prior_close / prev_close.where(prev_close > 0)


def classify_disagreements(df: pd.DataFrame, session_col: str = "session_ord",
                           symbol_col: str = "symbol") -> pd.DataFrame:
    """One row per stock-day where the supplied ``prev_close`` disagrees with the prior close.

    Returns the disagreeing rows with three added columns: ``prior_close`` (the previous
    observed row's close), ``implied_factor`` (``f`` above) and ``ca_class`` (one of
    :data:`CLASSES`). Rows that agree are not returned -- the frame is the audit, and an audit
    of 143,718 rows in which 143,403 say "no disagreement" is not readable.

    The classification is deliberately conservative. Only ``f > 1 + ROUNDING_TOL`` earns the
    ``corporate_action`` label, because only a DOWNWARD revision of the published previous
    close is what an entitlement adjustment does. A published previous close ABOVE the prior
    close cannot be explained that way and is labelled ``upward_adjustment``, not silently
    absorbed.
    """
    if "prev_close" not in df.columns:
        return df.head(0).assign(prior_close=[], implied_factor=[], ca_class=[])

    d = df.sort_values([symbol_col, "date"]).copy()
    prior = d.groupby(symbol_col)["close"].shift(1)
    disagrees = (d["prev_close"].notna() & prior.notna()
                 & ~np.isclose(d["prev_close"], prior, rtol=1e-9))

    out = d.loc[disagrees].copy()
    out["prior_close"] = prior[disagrees]
    out["implied_factor"] = _implied_factor(out["prev_close"], out["prior_close"])

    gap = (d.groupby(symbol_col)[session_col].diff()[disagrees]
           if session_col in d.columns else pd.Series(1.0, index=out.index))
    f = out["implied_factor"]
    out["ca_class"] = np.select(
        [gap.ne(1).fillna(True).to_numpy(),
         (f - 1.0).abs().le(ROUNDING_TOL).to_numpy(),
         f.gt(1.0 + ROUNDING_TOL).to_numpy()],
        ["session_gap", "reference_rounding", "corporate_action"],
        default="upward_adjustment",
    )
    return out


def corporate_action_flags(df: pd.DataFrame, session_col: str = "session_ord",
                           symbol_col: str = "symbol") -> pd.Series:
    """Boolean, indexed like ``df``: is this row an ex-date by the published-reference test?

    True only for rows classified ``corporate_action``. Used both to build the adopted previous
    close and to drop ex-dates in the sensitivity specification, so the two can never disagree
    about which rows are the ex-dates.
    """
    flags = pd.Series(False, index=df.index)
    dis = classify_disagreements(df, session_col=session_col, symbol_col=symbol_col)
    if len(dis):
        flags.loc[dis.index[dis["ca_class"] == "corporate_action"]] = True
    return flags


def adjusted_previous_close(df: pd.DataFrame, session_col: str = "session_ord",
                            symbol_col: str = "symbol",
                            use_corporate_actions: bool = True) -> pd.Series:
    """THE previous close, adopted package-wide. See the module docstring.

    Close of the previous genuine trading session, replaced by the exchange's published
    ``prev_close`` on rows where that published value evidences a corporate action. NaN wherever
    there is no previous genuine session -- across a listing gap, and on a security's first row.

    ``use_corporate_actions=False`` returns the unadjusted previous-session close, which is the
    definition the previous revision used. It exists so the sensitivity specification is a
    parameter of one function rather than a second implementation that could drift from this
    one.

    ``session_col`` behaves as in :func:`nepsevol.estimators.range_.previous_session_close`:
    when the column is present the previous close is accepted only where the session ordinal
    advanced by exactly one; when absent this degrades to ``.shift(1)``, which is correct for a
    gapless series such as an index.
    """
    d = df.sort_values([symbol_col, "date"]) if symbol_col in df.columns else df.sort_values("date")

    prev = d.groupby(symbol_col)["close"].shift(1) if symbol_col in d.columns else d["close"].shift(1)
    if session_col in d.columns:
        step = (d.groupby(symbol_col)[session_col].diff() if symbol_col in d.columns
                else d[session_col].diff())
        prev = prev.where(step == 1)

    if use_corporate_actions and "prev_close" in d.columns:
        ex = corporate_action_flags(d, session_col=session_col, symbol_col=symbol_col)
        # Only on rows that HAVE a previous genuine session: an ex-date across a listing gap
        # still has no overnight return to measure, and must stay NaN.
        take = ex & prev.notna()
        prev = prev.where(~take, d["prev_close"])

    return prev.reindex(df.index)
