"""Build the NEPSE stock-level panels from the two raw sources.

Source A (long):   372 company files, 2010-2026, OHLC + volume + turnover. No trade counts.
Source B (trades): daily cross-sections, 2024-03 onward, adds Trans. (trade count) and VWAP.

The two-stage design this enables: estimate the trade-count relationship on the
overlap window where Trans. is observed, then use turnover/volume as a calibrated
proxy to extend the analysis back to 2010.
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import bootstrap
bootstrap()

import numpy as np, pandas as pd

sys.path.insert(0, str(ROOT / "src"))
from nepsevol.clean.ohlc import (repair_ohlc, resolve_duplicate_keys, classify_duplicates,
                                 ohlc_violations, repair_audit_table,
                                 DUPLICATE_CLASSES)
from nepsevol.provenance import write_manifest

RAW = ROOT / "data" / "raw"


def _require_raw(subdir: str) -> list:
    """Fail with an actionable message, not `ValueError: No objects to concatenate` (F-7).

    scripts/_env.py refuses to let a missing package produce a bare ImportError; the same
    standard applies to missing INPUTS. This script cannot run from the published submission
    package, by design -- the raw NEPSE downloads are not redistributable -- and the reader
    deserves to be told that rather than to debug a pandas traceback.
    """
    d = RAW / subdir
    files = sorted(d.glob("*.csv")) if d.exists() else []
    if files:
        return files
    import sys as _sys
    print("\n".join([
        "",
        "  Raw NEPSE inputs not found.",
        f"  Expected CSV files in: {d}",
        f"  Found: {'directory does not exist' if not d.exists() else '0 CSV files'}",
        "",
        "  This script rebuilds the processed panels from the ORIGINAL stock-level NEPSE",
        "  downloads, which are NOT redistributed in this submission package (see",
        "  data/raw/README.md for the licensing reason and the expected layout).",
        "",
        "  To reproduce the PAPER, you do not need this script. Run instead:",
        "",
        "      bash run_paper_analysis.sh",
        "",
        "  which starts from the frozen, audited panels in data/processed/.",
        "",
    ]), file=_sys.stderr)
    raise SystemExit(1)
OUT = ROOT / "data" / "processed"; OUT.mkdir(parents=True, exist_ok=True)


def build_long() -> pd.DataFrame:
    frames = []
    for f in _require_raw("stock-daily-long"):
        try:
            d = pd.read_csv(f)
        except Exception:
            continue
        if "published_date" not in d.columns or d.empty:
            continue
        d = d.rename(columns={"published_date": "date", "traded_quantity": "volume",
                              "traded_amount": "turnover"})
        d["symbol"] = f.stem
        frames.append(d[["date", "symbol", "open", "high", "low", "close", "volume", "turnover"]])
    p = pd.concat(frames, ignore_index=True)
    p["date"] = pd.to_datetime(p["date"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume", "turnover"]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p.dropna(subset=["date", "close"]).sort_values(["symbol", "date"]).reset_index(drop=True)

    # PAP SS3.1 envelope repair and the security-day sample definition, applied once at the
    # source so every downstream script inherits them. Both were pre-committed; neither was
    # implemented until 2026-08-28. The primary panel carried 1,154 OHLC-inconsistent rows
    # (2 of them with high < low) and 640 duplicated security-days.
    print("\nPANEL A - pre-committed cleaning (PAP SS3.1)")
    n_viol = int(ohlc_violations(p).sum())
    p = resolve_duplicate_keys(p)
    p = repair_ohlc(p)
    print(f"  OHLC violations repaired     {int(p.ohlc_repaired.sum()):,} "
          f"(detected before dedup: {n_viol:,}); originals retained as open_original..close_original")

    # Turnover is NOT populated in the source before 2011: every zero-turnover row there has
    # POSITIVE volume (99.9% of 3,702 such rows) and 56% show High != Low, so those securities
    # traded and their prices moved. This is missingness encoded as zero. Left uncorrected, any
    # turnover-conditioned rule silently reclassifies traded days as untraded ones.
    missing_turnover = (p["turnover"] == 0) & (p["volume"] > 0)
    p.loc[missing_turnover, "turnover"] = np.nan
    p["turnover_missing"] = missing_turnover
    return p


def _num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")


def build_trades() -> pd.DataFrame:
    frames = []
    for f in _require_raw("stock-daily-trades"):
        try:
            d = pd.read_csv(f)
        except Exception:
            continue
        if d.empty or "Symbol" not in d.columns:
            continue
        d["date"] = pd.to_datetime(f.stem.replace("_", "-"), errors="coerce")
        frames.append(d)
    p = pd.concat(frames, ignore_index=True)
    ren = {"Symbol": "symbol", "Open": "open", "High": "high", "Low": "low",
           "Close": "close", "Vol": "volume", "Turnover": "turnover",
           "Trans.": "n_trades", "VWAP": "vwap", "Prev. Close": "prev_close"}
    p = p.rename(columns=ren)
    keep = ["date", "symbol", "open", "high", "low", "close", "volume",
            "turnover", "n_trades", "vwap", "prev_close"]
    p = p[[c for c in keep if c in p.columns]]
    for c in p.columns:
        if c not in ("date", "symbol"):
            p[c] = _num(p[c])
    p = p.dropna(subset=["date", "close", "symbol"]).sort_values(["symbol", "date"])

    # REFEREE #7 FIX. This previously read
    #     p = p.drop_duplicates(subset=["symbol","date"], keep="last")
    # which silently selected one row of every duplicated security-day BY FILE ORDER, before
    # resolve_duplicate_keys() ran at the caller. That contradicts the stated policy in
    # nepsevol.clean.ohlc and in the manuscript's Section 3 -- conflicting duplicates are
    # classified and EXCLUDED, never resolved by row order -- and it silently applied to the
    # daily-trades panel that carries the paper's main equity estimates.
    #
    # Duplicates are now classified first and audited to disk, and only exact duplicates are
    # collapsed. Any conflicting class is excluded by resolve_duplicate_keys, exactly as in
    # the long-history panel. The audit is emitted whether or not conflicts are found, so the
    # absence of conflicts becomes evidence rather than an assumption.
    # The audit is emitted with a ROW FOR EVERY CLASS whether or not that class occurs, and with
    # the number of keys examined. An empty file cannot distinguish "no conflicts were found"
    # from "the audit never ran", and referee item 1 is precisely a complaint that conflict-
    # freedom was an assumption rather than a demonstrated fact. A zero has to be printed to
    # count as evidence.
    audit_dir = ROOT / "data" / "processed" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    label = classify_duplicates(p)
    counts = label.value_counts() if len(label) else pd.Series(dtype=int)
    summary = pd.DataFrame({
        "class": list(DUPLICATE_CLASSES),
        "duplicate_keys": [int(counts.get(c, 0)) for c in DUPLICATE_CLASSES],
    })
    summary.loc[len(summary)] = ["KEYS_EXAMINED", int(len(p.groupby(["symbol", "date"]).size()))]
    summary.loc[len(summary)] = ["ROWS_EXAMINED", int(len(p))]
    summary.to_csv(audit_dir / "panel_trades_duplicate_audit.csv", index=False)
    print("\n  daily-trades duplicate classes (audited before any collapse):")
    print(summary.to_string(index=False))
    if not len(label):
        print("  -> zero duplicated (symbol, date) keys. The obsolete drop_duplicates(keep='last')")
        print("     path therefore had nothing to select between, so the frozen panel is")
        print("     unaffected by it. This is now a demonstrated fact, not an assumption.")

    p = resolve_duplicate_keys(p).reset_index(drop=True)
    return p


def diagnose(p: pd.DataFrame, name: str):
    ok_hi = p["high"] >= p[["open", "close"]].max(axis=1) - 1e-9
    ok_lo = p["low"] <= p[["open", "close"]].min(axis=1) + 1e-9
    viol = ~(ok_hi & ok_lo)
    print(f"\n{name}")
    print(f"  rows            {len(p):,}")
    print(f"  symbols         {p['symbol'].nunique():,}")
    print(f"  dates           {p['date'].nunique():,}  ({p['date'].min().date()} -> {p['date'].max().date()})")
    print(f"  OHLC violations {viol.sum():,} ({100*viol.mean():.2f}%)")
    print(f"  H == L          {(p['high'] == p['low']).sum():,} ({100*(p['high']==p['low']).mean():.2f}%)")
    if "n_trades" in p.columns:
        t = p["n_trades"].dropna()
        print(f"  n_trades        median={t.median():.0f}  p10={t.quantile(.1):.0f}  p90={t.quantile(.9):.0f}  max={t.max():.0f}")
    return viol


from nepsevol.trading_calendar import build_calendar, detect_sessions


def clean_trades_panel(p: pd.DataFrame, stale_threshold: float = 0.90) -> pd.DataFrame:
    """Keep only genuine trading sessions, detected from the data, and WRITE THE CALENDAR.

    A fixed weekday filter is WRONG for this market. NEPSE traded Sunday-Thursday historically and
    switched to Monday-Friday effective 6 April 2026, so a hard-coded Sun-Thu rule deletes genuine
    Friday sessions and retains stale Sundays after the change -- contaminating precisely the
    window that also contains the widened price-band regime of 20 April. It also silently keeps
    public holidays, on which the archive carries the previous session forward.

    Sessions are therefore identified by the staleness signature: a dated file whose cross-section
    is >= `stale_threshold` identical to the prior file is a carried-forward record, not a session.

    The calendar is written here rather than shipped as an orphan artifact. It previously had no
    producer anywhere in the package: ``data/processed/nepse_trading_calendar.csv`` was consumed
    by script 26 and named in no reproducibility-map row, so a reader could neither regenerate it
    nor check what schedule constants it was built under. It is the ONLY place the session
    ordinal comes from -- and the session ordinal is what makes an overnight return an overnight
    return -- so an unreproducible calendar silently fixes the Yang-Zhang sample.
    """
    cal = build_calendar(p, stale_threshold=stale_threshold)
    live = set(cal.index[cal.is_session])
    q = p[p["date"].isin(live)].copy()

    cal_out = cal.reset_index().rename(columns={"index": "date"})
    cal_out.to_csv(OUT / "nepse_trading_calendar.csv", index=False, date_format="%Y-%m-%d")

    n_days = q["date"].nunique()
    span = (q["date"].max() - q["date"].min()).days / 365.25
    dis = int(detect_sessions(p, stale_threshold=stale_threshold).rule_data_disagree.sum())
    print(f"\nPANEL B - cleaned (data-detected calendar)")
    print(f"  dated files                  {p['date'].nunique():,}")
    print(f"  genuine sessions             {n_days}")
    print(f"  rule/data disagreements      {dis}  (holidays, and the Apr-2026 schedule change)")
    print(f"  off-schedule sessions        {int(cal.off_schedule_session.sum())}")
    print(f"  inferred holidays            {int(cal.inferred_holiday.sum())}")
    print(f"  rows                         {len(q):,}")
    print(f"  span                         {q['date'].min().date()} -> {q['date'].max().date()}")
    print(f"  sessions per year            {n_days/span:.0f}")
    print(f"  wrote                        {(OUT/'nepse_trading_calendar.csv').name}")
    return q


if __name__ == "__main__":
    print("Building panels from", RAW)
    long_ = build_long();  diagnose(long_, "PANEL A - long history (no trade counts)")

    trades = build_trades()
    # PAP SS3.1 binds on EVERY dataset, not only panel A.
    print("\nPANEL B - pre-committed cleaning (PAP SS3.1)")
    trades = resolve_duplicate_keys(trades)
    trades = repair_ohlc(trades)
    print(f"  OHLC violations repaired     {int(trades.ohlc_repaired.sum()):,}; "
          f"originals retained as open_original..close_original")
    diagnose(trades, "PANEL B - with trade counts")

    clean = clean_trades_panel(trades)

    long_.to_csv(OUT / "panel_long.csv", index=False, date_format="%Y-%m-%d")
    trades.to_csv(OUT / "panel_trades.csv", index=False, date_format="%Y-%m-%d")
    clean.to_csv(OUT / "panel_trades_clean.csv", index=False, date_format="%Y-%m-%d")

    # Provenance: every repaired field, and a versioned manifest for the artefacts.
    audit_dir = OUT / "audit"; audit_dir.mkdir(exist_ok=True)
    for name, frame in (("panel_long", long_), ("panel_trades", trades)):
        tbl = repair_audit_table(frame)
        tbl.to_csv(audit_dir / f"{name}_repair_audit.csv", index=False)
        print(f"  repair audit: {len(tbl):,} field-level changes -> "
              f"{audit_dir.name}/{name}_repair_audit.csv")
    write_manifest(ROOT, OUT, {"panel_long": long_, "panel_trades": trades,
                               "panel_trades_clean": clean})
    print(f"\nwrote {OUT/'panel_long.csv'}")
    print(f"wrote {OUT/'panel_trades.csv'}")
    print(f"wrote {OUT/'panel_trades_clean.csv'}")
