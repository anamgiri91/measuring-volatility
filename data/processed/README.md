# Processed, paper-facing data

These are the frozen inputs for every retained empirical result. `run_paper_analysis.sh` starts
here; the original stock-level NEPSE downloads that produced them are not redistributed (see
`../raw/README.md`).

## Files read by the pipeline

| File | Rows | Read by |
|---|---|---|
| `panel_trades_clean.csv` | 184,430 | `03_descriptive.py` — the cleaned trading panel, before the analysis screens |
| `analysis_sample.csv` | 184,390 | pooled universe, all instrument types (`load_sample(..., "full")`) |
| `equity_sample.csv` | 143,718 | ordinary equity only, the primary estimation universe (`load_sample(..., "equity")`) |
| `nepse_trading_calendar.csv` | 890 dates, 569 sessions | `26_robustness.py` — derives the annualisation factor A |

`analysis_sample.csv` is `panel_trades_clean.csv` after the Section 3 screens (positivity,
`|ln(C/C_prev)| < 0.5`, and the rules-derived feasible-range ceiling). The 40-row difference is
4 rows failing the range ceiling plus rows lost to the return and positivity filters; one
security (`ADBLB`) drops out entirely.

`ADBLB` is worth naming, because the classification audit added in this revision explains it.
It is the **4% Agricultural Bond**, which the ticker-convention rule read as ordinary equity
and which the external security master identifies as a corporate debenture. The Section 3
screens happened to remove it as a data anomaly, so no headline result was ever contaminated
by it — but that was luck rather than design, and it is exactly the vulnerability referee
item 2 identified. It is now excluded as what it is. Independently, `NADEP` (NADEP Laghubitta
Bittiya Sanstha) was wrongly excluded as a promoter share by a ticker pattern matching the
trailing "P" of its name, and is now correctly in the equity universe. The ordinary-equity
universe therefore moves from 291 securities / 143,149 stock-days to **292 / 143,718**.

## Files kept for provenance, not read by any script

These are audit trails, retained so a reviewer can inspect what the cleaning did rather than take
it on trust. Nothing in the pipeline consumes them (audit finding F-10 — previously undocumented).

| File | What it records |
|---|---|
| `audit/panel_long_repair_audit.csv` | Every OHLC envelope repair applied to the long-history panel, original and adjusted values side by side |
| `audit/panel_trades_repair_audit.csv` | The same for the 2024–2026 daily-trades panel |
| `audit/panel_trades_duplicate_audit.csv` | Duplicate-key classification for the daily-trades panel, emitted by `02_build_panel.py` before any collapse. **Now present**; see below |
| `BUILD-MANIFEST.json` | Interpreter, package versions, raw-input hash and count, cleaning-code hash, rule versions, and per-artifact row/security/session counts |

## Provenance of the 2024–2026 daily-trades panel (referee item 1 — RESOLVED)

The previous revision carried this limitation: the shipped panels had been built when the
daily-trades path still applied `drop_duplicates(keep="last")` before classification, the fix
could not be exercised without the raw inputs, and so *the absence of conflicting duplicate keys
was an assumption rather than a result*. The referee correctly refused to treat the dataset as
fully audited on that basis.

**The panel has now been rebuilt from the original raw files under the corrected rule.** Two
things were established:

1. `audit/panel_trades_duplicate_audit.csv` reports **zero duplicated `(symbol, date)` keys** in
   the daily-trades source — `KEYS_EXAMINED = ROWS_EXAMINED = 286,994`, one row per key. Every
   class is listed with its count, including the zeros, so the absence is now evidence rather
   than an empty file. The obsolete `keep="last"` path therefore had nothing to select between.
2. The rebuilt `panel_trades_clean.csv` is **identical to the frozen panel** — 184,430 rows ×
   16 columns, zero differing values in any column. No downstream table or figure changes as a
   consequence of the duplicate rule.

The raw inputs remain undistributable, so this package still ships the frozen panel rather than
the raw files; what has changed is that the frozen panel's conflict-freedom is now a demonstrated
fact. Anyone with lawful access to the raw files can repeat the check with
`python scripts/02_build_panel.py`.

`nepse_trading_calendar.csv` is also now produced by `02_build_panel.py`. It previously shipped
with **no producer anywhere in the package**, which mattered more than it looked: it is the only
source of the session ordinal, and the session ordinal is what makes an overnight return span one
session rather than an arbitrary absence.

## Known provenance limitation

`BUILD-MANIFEST.json` records `"git_commit": "UNKNOWN"` or `"…-dirty"` when the build is run
outside a clean checkout, so the commit hash alone does not identify the code that produced these
artifacts (audit finding B-2). The authoritative identifier is `cleaning_code_sha256`, which
hashes the cleaning code as it stood at build time. A submission build should be made from a
clean tree so the two agree.
