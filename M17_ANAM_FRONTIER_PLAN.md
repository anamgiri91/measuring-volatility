# M17 — frozen plan: Anam's estimator in two more frontier markets

**Written and frozen on 2026-10-08, after the panels below were built and before any estimator,
forecast or variance level was computed on them.** The commit that adds this file also adds the
panel module (`src/nepsevol/frontier.py`) and its tests (`tests/test_frontier_panels.py`). The
evaluation script (`scripts/42_anam_frontier.py`) is written and run only after that commit, so the
order can be checked in the history. The estimator is M16's, unchanged
(`src/nepsevol/estimators/anam.py`, frozen in commit `dc41f1e`), and the decision rules below are
applied mechanically.

## Why these markets

The question is whether Anam's estimator, designed on the Nepal Stock Exchange alone, does what it
was designed to do in other frontier markets. Daily OHLC data for individual stocks could be
reached for two of them: Bangladesh (the Dhaka Stock Exchange) and Vietnam (HOSE, HNX and UPCoM).
Pakistan, Sri Lanka, Kenya and Nigeria were tried and could not be used: the exchanges' sites,
Kaggle, Mendeley Data, Zenodo, Hugging Face and the usual market-data hosts are blocked from the
environment that runs this package, and the public GitHub repositories found for Pakistan hold
download code but no prices. The markets were therefore chosen for data access, not for any
property of their prices.

## What was known before freezing (disclosed, so the plan can be judged against it)

1. **The estimator and its record.** Its constants (`LAMBDA0` = 0.2, `POOL_SESSIONS` = 60, panel
   mode) and the M16 holdout verdicts (commit `3b8af70`) are known. No range-based estimator beat it
   on NEPSE's holdout, NIFTY 50 or the S&P 500. It beat close-to-close on both indices, but not on
   NEPSE's holdout, where close-to-close beat it after the April 2026 band reform.
2. **Inspection of the new data was limited to schema, coverage and record integrity.** That meant:
   * column names, date ranges, and the number of securities and dates;
   * duplicate and conflicting records, non-positive prices and zero volume;
   * OHLC-envelope violations, measured in price units;
   * the weekday pattern of dates and carried-forward dates;
   * the agreement of the two Dhaka files where they overlap.

   No return, range, variance or estimator was computed or examined on these data. The panel module
   was then run to produce the coverage and screen counts below. It computes each bar's
   coordinates, but nothing was printed from them except counts.
3. **The Dhaka upload's dates are wrong before 2023.** The author's file stamps every date whose
   day is 12 or less with day and month exchanged. For example, its 2020-04-02 is 4 February 2020,
   and its stamps from 2 April to 11 May 2020 fall inside the exchange's COVID-19 closure. The
   evidence comes from the calendar alone:
   * every Friday stamp before 2023 has a day of 12 or less;
   * reversing day and month for every such stamp from 2009 to 2021 leaves no Friday session and
     no collision with an existing date;
   * the 2022 stamps hold two copies of the same months, one exchanged and one not — all 9,650
     conflicting records are 2022 stamps with a day of 12 or less;
   * from 2023 on there is no Friday or Saturday stamp, and on the 52,920 stock-days the two Dhaka
     files share (2024-09-30 to 2025-04-08), the upload agrees exactly with the exchange-archive
     mirror in open, high, low, close and volume.

   The 2009–2021 panel therefore uses repaired dates, 2022 is dropped, and dates from 2023 on are
   used as stamped. Before 2009 the exchange's trading week changed, the weekday evidence cannot tell
   a repair from a genuine session, and those years are not used.
4. **Market rules known in outline.** Dhaka has daily price limits — 10% for the great majority of
   prices — and two floor-price periods inside the samples. It ordinarily suspends trading in a security
   on its record date, so the gap rule below removes most ex-dates. Vietnam's three exchanges have different
   daily limits, the widest 15% (UPCoM), and its price file is adjusted for corporate actions. No
   rule-change date is used in any test.

## The panels (fixed)

| Panel | Role | Source | Sessions | Securities | Stock-days | Test span (first session) | Train / test stock-days |
|---|---|---|---|---|---|---|---|
| DSE 2023-2026 | primary, Bangladesh | upload 2023-01-02 to 2025-04-08, mirror from 2025-04-09 | 901 (2023-01-02 to 2026-10-08) | 368 | 299,793 | 2024-11-20 | 141,187 / 158,606 |
| Vietnam 2007-2020 | primary, Vietnam | Vietnam ticker files | 3,290 (2007-01-03 to 2020-03-18) | 927 | 1,455,525 | 2013-08-14 | 616,635 / 838,890 |
| DSE 2009-2021 | secondary (dates repaired) | upload, dates repaired | 3,094 (2009-01-04 to 2021-12-30) | 418 | 812,843 | 2015-06-17 | 349,915 / 462,928 |

**Inputs, pinned by SHA-256.** None is stored in the package; `data/external/README.md` says how to
place them.

* **Dhaka upload.** `DSE_Data.csv`, supplied by the author, SHA-256 `a619a0ff…0c6763`. Its name,
  span and columns match the "Dhaka Stock Exchange Historical Data (1999-2025)" release (Sunny,
  Nafis and Khan, Mendeley Data, 2025), but its row count does not match that listing's.
* **Dhaka mirror.** `data/prices.csv` of github.com/nifty1303/dse-data at commit `9f11a76`,
  SHA-256 `552e1a45…1b9633`.
* **Vietnam.** The 936 three-character `tickers/*.csv` files of
  github.com/88d52bdba0366127fffca9dfa93895/vnstock-data at commit `b52e2fe`, manifest digest
  `69caa964…7e2691`.

The full digests are constants in `nepsevol.frontier` and are checked before any use.

**Rules** (`nepsevol.frontier`, rules 1–8 in its docstring):

* ordinary equity only (`DSE_NON_EQUITY`; Vietnam's three-character codes);
* exact repeats kept once, and conflicting keys dropped;
* no-trade records dropped;
* the OHLC envelope repaired within one price unit (Dhaka 0.1 taka, Vietnam 0.01 thousand dong)
  and the record dropped beyond it;
* not a session: carried-forward dates (`CARRY_FORWARD_SHARE` = 0.90), dates with fewer than
  `MIN_SECURITIES` = 10 securities, and Dhaka's 26 March – 30 May 2020 closure;
* the previous close is the close of the immediately preceding session, at most `MAX_GAP_DAYS` = 14
  calendar days earlier;
* a bar is dropped if its high or low lies beyond the market's widest regular limit plus
  `BAND_MARGIN` = 0.01 from the previous close;
* sessions before the median session are the training span.

**What the rules removed** (counts from `build_panel`):

| Panel | Records in span | No-trade | Envelope dropped / repaired | Dates dropped | No previous close | Outside band |
|---|---|---|---|---|---|---|
| DSE 2023-2026 | 319,840 | 12,731 | 0 / 0 | 0 | 7,139 | 177 |
| Vietnam 2007-2020 | 1,583,027 | 199 | 1,625 / 104,648 | 1 | 123,391 | 2,286 |
| DSE 2009-2021 | 831,805 | 2 | 51 / 19 | 0 | 12,979 | 5,930 |

Vietnam's envelope repairs are rounding: 98% of its violations are within one unit of the adjusted
price, which the source rounds to 0.01.

## Comparison set (fixed, as in M16)

The comparison set is:

* close-to-close r²;
* Parkinson;
* Garman–Klass;
* Rogers–Satchell;
* overnight² + Parkinson;
* overnight² + Garman–Klass;
* the Yang–Zhang daily form, o² + k c² + (1 − k) RS with k for n = 21;
* Anam, in panel mode: b and κ pooled over the panel's securities and the last 60 dates;
* Anam's open-free special case (b = 0), reported as a variant.

For the level test the Yang–Zhang window form is added. The estimator set is
`scripts/40_anam_holdout.py::estimator_set(d, "panel")`, imported unchanged.

## Tests (fixed)

**T1 — forecasts.** `nepsevol.volforecast.fair_forecast_test`, through M16's `t1`.

* **Loss and horizons:** QLIKE at horizons of 5 and 21 sessions.
* **Calibration and shrinkage:** every estimator is calibrated by the pooled 60-date scheme and
  gets its own shrinkage φ, chosen on the panel's training span.
* **Scoring:** a common set of origins in the test span.
* **Inference:** Newey–West t statistics on the per-date loss difference, with lags equal to the
  horizon.

**T2 — level.** Each estimator's raw 21-session window mean is divided by the 21-session mean of r²,
using only windows that lie wholly inside the test span (M16's `t2_level`). Anam enters calibrated.

**T4 — instrumented noise (reported, no decision).** M16's `t4_noise`, on the test span. The
reference is r², the instruments are lagged two sessions, and the weights are 1/S² from trailing
Parkinson (`nepsevol.calibration.predictable_scale`, 22 sessions).

M16's T3 (a rule change) and T5 (implied variance) have no counterpart here. No rule-change date is
pre-specified, and neither market has an implied-volatility index in this package.

## Decision rules (binding)

For each panel, horizon and rival X, Anam **beats** X if its mean QLIKE difference is negative with
t < −1.96. It **loses to** X if the difference is positive with t > 1.96. Otherwise there is **no
difference** (M16's `verdict`).

For each panel P:

* **F1(P).** Anam beats close-to-close at 5 sessions on the test span.
* **F2(P).** Anam beats Parkinson at 5 sessions on the test span.
* **F3(P).** Anam's calibrated level ratio lies in [0.9, 1.1] on the test span. The raw ratios of
  overnight² + Parkinson and of the Yang–Zhang daily form both lie outside it.
* **Best in panel.** No rival beats Anam at 5 or at 21 sessions.

**G (the summary claim).** F1, F2 and "best in panel" all hold in both primary panels, DSE 2023-2026
and Vietnam 2007-2020. DSE 2009-2021 is reported with the same rules but does not enter G, because
its dates were repaired.

## Predictions, written before any estimator was computed on these data

* **DSE 2023-2026 and DSE 2009-2021.** F1, F2 and F3 hold, and no rival beats Anam.
* **Vietnam 2007-2020.** F1 and F2 hold, and F3 holds. If Vietnam's opening auction makes the open
  nearly efficient (b̂ near one), the estimator runs near its overnight² + Parkinson form, and
  Garman–Klass or overnight² + Garman–Klass may beat it at 5 sessions, as in the clean simulated
  market. A loss there would be reported as the cost of the design.
* **G holds.**

## Reporting

Every verdict, including failures, goes into `M17_ANAM_FRONTIER_RESULTS.md` with its table. The
outputs are:

* `table107_anam_frontier_panels.csv` (coverage, screen counts and b̂ on the test span);
* `table108_anam_frontier_forecast.csv` (T1);
* `table109_anam_frontier_level.csv` (T2);
* `table110_anam_frontier_noise.csv` (T4);
* `table111_anam_frontier_decisions.csv`.

Once `scripts/42_anam_frontier.py` has run, it is changed only to fix an error that stops it
running, and any such fix is registered in `AUDIT-REGISTER.md`. Anything computed after the
results are seen is labelled post hoc and kept in a separate script.
