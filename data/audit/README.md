# Audit-only data

`duplicate_key_rows.csv` contains only the 1,332 physical rows belonging to the 640 duplicated `(symbol, date)` keys in the historical long-form source panel. It is a compact audit extract, not the full historical dataset.

`scripts/24_duplicate_key_reconciliation.py` uses this extract to reproduce the paper's duplicate counts:

- 640 duplicated keys
- 622 exact-duplicate keys / 1,296 physical rows
- 18 conflicting-OHLC keys / 36 physical rows
- 710 physical rows removed under the stated rule
