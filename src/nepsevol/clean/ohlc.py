"""OHLC envelope repair and duplicate-key resolution.

Two DIFFERENT data problems, kept logically separate and applied in a fixed order:

1. :func:`resolve_duplicate_keys` -- enforce the security-day sample definition.
2. :func:`repair_ohlc` -- enforce the OHLC envelope.

ORDER MATTERS AND IS FIXED. Duplicate detection runs on ORIGINAL, unrepaired values.
Repairing first could make two genuinely conflicting records identical -- both get their
extrema pushed out to the same ``max(H,O,C)`` / ``min(L,O,C)`` -- and a conflict would be
silently reclassified as an exact duplicate. The canonical order lives in
:data:`CLEANING_ORDER`.

PAP-v4 SS3.1 -- deterministic OHLC envelope repair
--------------------------------------------------
    H_adj := max(H_orig, O, C)
    L_adj := min(L_orig, O, C)

Open and Close are taken as correct and High/Low as the corrupted fields: O and C are
single transaction prices carried straight from the tape, whereas H and L are session
extrema and are the fields an exchange feed most often reports inconsistently. O and C are
never modified.

Properties, verifiable from this docstring alone:

* deterministic -- no tuning constant, no threshold, no iteration
* idempotent -- applying twice equals applying once, provenance columns included
* order-independent -- the two assignments do not interact
* guarantees ``H_adj >= max(O,C) >= min(O,C) >= L_adj``, hence ``H_adj >= L_adj``
* a conforming row is left bit-identical
* **weakly widening**: ``H_adj - L_adj >= H_orig - L_orig`` whenever the input was
  malformed, and exactly equal when it was not. This is a mathematical consequence of the
  rule. What a widened range implies for any particular estimate is an empirical question
  about a particular dataset and is recorded in the audit register, not here.

Provenance convention: ORIGINAL values are preserved as ``open_original`` ...
``close_original`` for all four fields. That is the single convention for new code. The
frozen confirmatory script ``scripts/11_ho2_confirmatory.py`` performs its own inline
repair using ``high_raw``/``low_raw``; it is deliberately NOT migrated, because the
historical registered result must stay byte-reconstructable.

Duplicate keys
--------------
An observation is a security-day. Duplicated keys are classified, never resolved by row
order:

``EXACT_DUPLICATE``     every scientifically relevant field agrees (missing values
                        included -- see :data:`EQUALITY_COLS` and the NaN semantics below)
``CONFLICTING_OHLC``    prices disagree
``CONFLICTING_VOLUME``  volume or turnover disagrees
``CONFLICTING_TRADES``  trade count disagrees

Only ``EXACT_DUPLICATE`` is collapsed; every conflicting class is excluded and reported.

MISSING-VALUE SEMANTICS, stated because the obvious implementation is wrong.
``DataFrame.nunique()`` ignores NaN by default, so ``n_trades = [NaN, 10]`` would report
one distinct value and a genuine conflict would be labelled an exact duplicate. Equality
here therefore treats NaN as its own value: ``NaN vs NaN`` agrees, ``NaN vs value``
conflicts, ``value vs different value`` conflicts.

PRECEDENCE, so that overlapping conflicts never depend on evaluation order: a key
matching several conflict classes takes the most severe, ordered
``CONFLICTING_OHLC > CONFLICTING_VOLUME > CONFLICTING_TRADES > EXACT_DUPLICATE``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "repair_ohlc", "ohlc_violations", "repair_audit_table",
    "resolve_duplicate_keys", "classify_duplicates",
    "PRICE_COLS", "ORIGINAL_COLS", "EQUALITY_COLS", "DUPLICATE_CLASSES",
    "CLASS_PRECEDENCE", "CLEANING_ORDER",
]

PRICE_COLS = ["open", "high", "low", "close"]
ORIGINAL_COLS = [f"{c}_original" for c in PRICE_COLS]

#: Fields that determine scientific equality of two records for the same security-day.
#: Provenance-only columns (``*_original``, ``ohlc_repaired``, source filenames) are
#: deliberately excluded: they may legitimately differ without the observations differing.
EQUALITY_COLS = {
    "ohlc": PRICE_COLS,
    "volume": ["volume", "turnover"],
    "trades": ["n_trades"],
}

DUPLICATE_CLASSES = (
    "EXACT_DUPLICATE", "CONFLICTING_OHLC", "CONFLICTING_VOLUME", "CONFLICTING_TRADES",
)

#: Most severe first. A key matching several classes takes the first it matches.
CLASS_PRECEDENCE = ("CONFLICTING_OHLC", "CONFLICTING_VOLUME", "CONFLICTING_TRADES")

#: The canonical cleaning order, in one place.
CLEANING_ORDER = (
    "1. instrument classification (nepsevol.universe)",
    "2. duplicate-key resolution ON ORIGINAL VALUES (resolve_duplicate_keys)",
    "3. OHLC envelope repair (repair_ohlc)",
    "4. structural validation, halting (nepsevol.validate)",
    "5. sample restriction / universe selection (nepsevol.sample)",
)


# --------------------------------------------------------------------------- repair

def ohlc_violations(df: pd.DataFrame) -> pd.Series:
    """Rows whose reported extrema do not contain open and close, on ORIGINAL values."""
    hi = df["high_original"] if "high_original" in df.columns else df["high"]
    lo = df["low_original"] if "low_original" in df.columns else df["low"]
    return (hi < df[["open", "close"]].max(axis=1)) | (lo > df[["open", "close"]].min(axis=1))


def repair_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the PAP SS3.1 envelope repair, preserving originals and flagging changes.

    Idempotent including provenance columns: ``repair_ohlc(repair_ohlc(x))`` equals
    ``repair_ohlc(x)`` value-for-value and column-for-column.
    """
    out = df.copy()
    for col, orig in zip(PRICE_COLS, ORIGINAL_COLS):
        if orig not in out.columns:
            out[orig] = out[col]

    out["high"] = out[["high_original", "open", "close"]].max(axis=1)
    out["low"] = out[["low_original", "open", "close"]].min(axis=1)
    out["ohlc_repaired"] = (
        (out["high"] != out["high_original"]) | (out["low"] != out["low_original"])
    )
    return out


def repair_audit_table(repaired: pd.DataFrame, keys=("symbol", "date")) -> pd.DataFrame:
    """One row per field actually changed: key, field, old value, new value, reason."""
    if "ohlc_repaired" not in repaired.columns:
        raise ValueError("pass the output of repair_ohlc()")
    keys = [k for k in keys if k in repaired.columns]
    hits = repaired[repaired["ohlc_repaired"]]
    records = []
    for field, reason in (("high", "high < max(open, close)"), ("low", "low > min(open, close)")):
        changed = hits[hits[field] != hits[f"{field}_original"]]
        if changed.empty:
            continue
        rec = changed[keys].copy()
        rec["field"] = field
        rec["old_value"] = changed[f"{field}_original"].to_numpy()
        rec["new_value"] = changed[field].to_numpy()
        rec["reason"] = reason
        rec["rule"] = "PAP-v4 §3.1 envelope repair"
        records.append(rec)
    cols = keys + ["field", "old_value", "new_value", "reason", "rule"]
    if not records:
        return pd.DataFrame(columns=cols)
    return pd.concat(records, ignore_index=True).sort_values(keys + ["field"]).reset_index(drop=True)


# ------------------------------------------------------------------------ duplicates

def _disagrees(group: pd.DataFrame, cols: list[str]) -> bool:
    """True if any column varies within the group, treating NaN as a distinct value.

    ``nunique()`` is unusable here: it drops NaN, so (NaN, 10) reports one distinct value.
    """
    for c in cols:
        vals = group[c]
        isna = vals.isna()
        if isna.any() and not isna.all():
            return True                      # NaN alongside a present value
        present = vals[~isna]
        if len(present) and present.nunique(dropna=False) > 1:
            return True
    return False


def classify_duplicates(df: pd.DataFrame, keys=("symbol", "date")) -> pd.Series:
    """Label each duplicated key with one of :data:`DUPLICATE_CLASSES`.

    Indexed by key; non-duplicated keys are absent. Independent of row order.
    """
    keys = list(keys)
    dup = df[df.duplicated(keys, keep=False)]
    if dup.empty:
        return pd.Series(dtype=object)

    checks = {
        "CONFLICTING_OHLC": [c for c in EQUALITY_COLS["ohlc"] if c in df.columns],
        "CONFLICTING_VOLUME": [c for c in EQUALITY_COLS["volume"] if c in df.columns],
        "CONFLICTING_TRADES": [c for c in EQUALITY_COLS["trades"] if c in df.columns],
    }
    labels = {}
    for key, group in dup.groupby(keys, sort=True):
        label = "EXACT_DUPLICATE"
        for cls in CLASS_PRECEDENCE:          # most severe wins, order fixed by constant
            cols = checks.get(cls) or []
            if cols and _disagrees(group, cols):
                label = cls
                break
        labels[key] = label
    return pd.Series(labels, dtype=object).sort_index()


def resolve_duplicate_keys(
    df: pd.DataFrame, keys=("symbol", "date"), verbose: bool = True
) -> pd.DataFrame:
    """Collapse exact duplicate security-days; exclude every conflicting class.

    Order-independent: both the surviving rows and their order are invariant to the order
    of `df`. Must run BEFORE :func:`repair_ohlc` -- see :data:`CLEANING_ORDER`.
    """
    keys = list(keys)
    label = classify_duplicates(df, keys)
    ordered = df.sort_values(keys, kind="mergesort").reset_index(drop=True)
    if label.empty:
        if verbose:
            print("  duplicate keys               0")
        return ordered

    drop_keys = set(label.index[label != "EXACT_DUPLICATE"])
    key_tuples = list(zip(*(ordered[k] for k in keys)))
    keep = np.array([k not in drop_keys for k in key_tuples])
    out = ordered[keep].drop_duplicates(keys, keep="first").reset_index(drop=True)

    if verbose:
        counts = label.value_counts()
        parts = ", ".join(f"{c}={int(counts.get(c, 0))}" for c in DUPLICATE_CLASSES)
        print(f"  duplicate keys               {len(label):,}  ({parts})")
        print(f"  rows removed by dedup        {len(df) - len(out):,} "
              f"(exact collapsed, conflicting excluded)")
    return out
