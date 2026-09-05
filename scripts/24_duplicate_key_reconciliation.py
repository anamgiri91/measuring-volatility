"""Paper-facing duplicate-key reconciliation audit.

Reproduces the duplicate counts reported in Section 3 from a compact extract that contains
only the duplicated security-date rows from the historical long-form source panel.  The full
historical raw panel is not redistributed in the submission package because its source-data
redistribution terms are unresolved.

Run:
    python scripts/24_duplicate_key_reconciliation.py

Produces:
    output/tables/table29_duplicate_reconciliation.csv
"""
from __future__ import annotations

import pathlib
import sys
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import bootstrap
bootstrap()

sys.path.insert(0, str(ROOT / "src"))
from nepsevol.clean.ohlc import classify_duplicates

INFILE = ROOT / "data" / "audit" / "duplicate_key_rows.csv"
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)
KEYS = ["symbol", "date"]

raw = pd.read_csv(INFILE, parse_dates=["date"])
for c in ["open", "high", "low", "close", "volume", "turnover"]:
    raw[c] = pd.to_numeric(raw[c], errors="coerce")

label = classify_duplicates(raw, KEYS)
mult = raw.groupby(KEYS).size()
dup_mult = mult[mult > 1]

rows = []
for cls in ["EXACT_DUPLICATE", "CONFLICTING_OHLC", "CONFLICTING_VOLUME", "CONFLICTING_TRADES"]:
    keys_c = label.index[label == cls]
    if len(keys_c) == 0:
        continue
    m = dup_mult.loc[list(keys_c)]
    removed = int((m - 1).sum()) if cls == "EXACT_DUPLICATE" else int(m.sum())
    rows.append({
        "class": cls,
        "duplicate_keys": int(len(keys_c)),
        "physical_rows": int(m.sum()),
        "max_multiplicity": int(m.max()),
        "rows_removed": removed,
        "rule": "collapse to one" if cls == "EXACT_DUPLICATE" else "exclude key entirely",
    })

recon = pd.DataFrame(rows)
recon.to_csv(OUT / "table29_duplicate_reconciliation.csv", index=False)

exact = recon.loc[recon["class"] == "EXACT_DUPLICATE"]
conf_ohlc = recon.loc[recon["class"] == "CONFLICTING_OHLC"]
summary = {
    "duplicated_keys": int(len(label)),
    "physical_rows_on_duplicate_keys": int(dup_mult.sum()),
    "exact_duplicate_keys": int(exact["duplicate_keys"].sum()),
    "exact_duplicate_physical_rows": int(exact["physical_rows"].sum()),
    "conflicting_ohlc_keys": int(conf_ohlc["duplicate_keys"].sum()),
    "conflicting_ohlc_physical_rows": int(conf_ohlc["physical_rows"].sum()),
    "rows_removed_total": int(recon["rows_removed"].sum()),
}

print("Duplicate-key reconciliation")
print(recon.to_string(index=False))
print("\nSummary")
for k, v in summary.items():
    print(f"  {k:36s} {v:,}")

# Paper invariants: fail loudly if the compact audit extract no longer reproduces the manuscript.
expected = {
    "duplicated_keys": 640,
    "exact_duplicate_keys": 622,
    "exact_duplicate_physical_rows": 1296,
    "conflicting_ohlc_keys": 18,
    "conflicting_ohlc_physical_rows": 36,
    "rows_removed_total": 710,
}
for k, v in expected.items():
    if summary[k] != v:
        raise AssertionError(f"{k}: expected {v}, got {summary[k]}")
print("\nPaper duplicate-count invariants: PASSED")
