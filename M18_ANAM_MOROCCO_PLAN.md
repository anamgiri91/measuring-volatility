# M18 — frozen plan: Anam's estimator and its open-free form in Morocco

**Written and frozen on 2026-10-08, after the Morocco panel was built and before any estimator,
forecast or variance level was computed on it.** The commit that adds this file also adds the
Casablanca reader and the dated band schedule to `src/nepsevol/frontier.py`, with their tests. The
evaluation script (`scripts/43_anam_morocco.py`) is written and run only after that commit. The
decision rules below are applied mechanically.

## Why this test

M17 left one question open. Anam's estimator, frozen in M16, beat every classical range-based
estimator in Bangladesh and Vietnam, but it did not beat plain close-to-close at 5 sessions in either
primary panel. Its open-free special case (b = 0) had the lowest loss at 5 sessions in every M17 panel.
That form reads only the previous close, the high, the low and the close:

* A₀ = 0.8 · TR²/(4 ln 2) + 0.2 · r²;
* TR = max(H, PC) − min(L, PC), Wilder's true range in logs;
* κ₀ = Σr² / ΣA₀ over the last 60 dates, pooled across securities.

Its numbers in M16 and M17 were reported, never decided on. The comparison that singled it out was
drawn after the verdicts, on data already seen. The author then supplied daily data for the
Casablanca Stock Exchange, which nobody had examined in this project. This plan tests both forms
there: the frozen estimator as in M17, and the open-free form as a hypothesis fixed before the data
are read.

## What was known before freezing (disclosed)

1. **The estimator and both forms' records** in M16 and M17 (`M17_ANAM_FRONTIER_RESULTS.md`): the
   open-free form had lower loss than the full estimator in every frontier-market comparison, and
   higher loss on NIFTY 50 and the S&P 500.
2. **The data.** `archive_2.zip`, supplied by the author (SHA-256 `c9cc8888…0e02e0ef1be`), holds:
   * `cse-data/stock/`: one file per share, 77 shares, columns `Time, Open, High, Low, Close,
     Volume`, 2012-03-26 to 2026-03-27, prices not adjusted for corporate actions;
   * `cse-data/index/`: 32 indices, not used;
   * `info.csv`: names and types.

   The source of the files is not stated, and they are pinned by checksum (manifest digest
   `41a7ecde…5ebd5e0e`).
3. **Inspection was limited to schema, coverage and record integrity:**
   * no duplicate keys;
   * no non-positive price;
   * 145 zero-volume records;
   * no OHLC-envelope violation;
   * weekdays only, and no carried-forward date;
   * 18 to 77 shares per date (median 43);
   * 29% of bars with high equal to low, and 37% with open equal to close.

   No return, range, variance or estimator was computed or examined.
4. **Casablanca's daily price limits changed by regulatory decision inside the sample.** The values
   are from press reports of the AMMC's decisions; the decisions themselves were not obtained.

   | Regime | Shares in continuous trading | Shares in fixing |
   |---|---|---|
   | Until 16 March 2020 | 10% | narrower |
   | 17 March 2020 to 11 October 2021 | 4% | 2% |
   | 12 October 2021 to 8 October 2023 | 6% | 4% |
   | From 9 October 2023 | 10% | 6% |

   The files do not say which shares trade continuously, so the band screen uses the
   continuous-trading limit in force on the day (`MA_BANDS`).
5. **Morocco is in MSCI's frontier-markets universe.** Its exchange opens continuous trading with a
   pre-opening call auction. Many shares do not trade every day: the median date has 43 of 77.

## The panel (fixed)

`nepsevol.frontier.market_panel("Morocco 2012-2026", ...)` applies M17's rules 1–8 unchanged
(`CARRY_FORWARD_SHARE` = 0.90, `MIN_SECURITIES` = 10, `MAX_GAP_DAYS` = 14, `BAND_MARGIN` = 0.01, an
envelope unit of 0.01 dirham). The one change is that the band limit is the one in force on the day.

**Coverage:**

* 3,473 sessions (2012-03-27 to 2026-03-27), 77 shares, 129,273 stock-days.
* Training span 50,350 stock-days; test span 78,923 stock-days, from 2019-04-01.
* Removed by the rules:
  * 145 no-trade records;
  * 23,430 bars without a previous close in the preceding session — Casablanca's thin shares skip
    sessions;
  * 47 bars outside the band.
* Test span by band regime:

  | Regime | Stock-days | Sessions |
  |---|---|---|
  | 10%, to 2020-03-16 | 7,379 | 237 |
  | 4% | 15,279 | 390 |
  | 6% | 21,605 | 500 |
  | 10%, from 2023-10-09 | 34,660 | 610 |

## Comparison set and tests (fixed)

**Comparison set.** As in M16 and M17 (`scripts/40_anam_holdout.py::estimator_set(d, "panel")`):

* close-to-close r²;
* Parkinson, Garman–Klass and Rogers–Satchell;
* overnight² + Parkinson and overnight² + Garman–Klass;
* the Yang–Zhang daily form;
* Anam, in panel mode;
* the open-free form ("Anam, open-free special case (b=0)").

**T1 — forecasts.** `nepsevol.volforecast.fair_forecast_test`.

* **Loss and horizons:** QLIKE at 5 and 21 sessions.
* **Calibration and shrinkage:** every estimator is calibrated by the pooled 60-date scheme, with
  its own shrinkage φ chosen on the training span.
* **Scoring:** a common set of origins in the test span.
* **Inference:** Newey–West t statistics with lags equal to the horizon.
* **References:** the open-free form, Anam, Parkinson and close-to-close, so that every estimator
  is compared with both forms.

**T2 — level.** Raw 21-session window means divided by the 21-session mean of r², using windows
wholly inside the span (M16's `t2_level`). Anam enters calibrated, and so does the open-free form,
by κ₀ (reported).

**T4 — instrumented noise (reported).** M16's `t4_noise` on the test span.

**Band regimes (reported, no decision).** T1 and T2 within each of the four regimes of the test
span, together with b̂ by regime.

## Decision rules (binding)

For an estimator E and a rival X at a horizon:

* E **beats** X if E's mean QLIKE minus X's is negative with t < −1.96.
* E **loses to** X if that difference is positive with t > 1.96.
* Otherwise there is **no difference**.

All rules are on the full test span.

**The frozen estimator, as in M17:**

* **F1.** Anam beats close-to-close at 5 sessions.
* **F2.** Anam beats Parkinson at 5 sessions.
* **F3.** Anam's calibrated level ratio lies in [0.9, 1.1], while the raw ratios of
  overnight² + Parkinson and of the Yang–Zhang daily form both lie outside it.
* **Best in panel.** None of the seven rivals beats Anam at 5 or at 21 sessions.

**The open-free form (the new hypothesis):**

* **V1.** The open-free form beats close-to-close at 5 sessions.
* **V2.** The open-free form beats the full estimator at 5 sessions.
* **V3.** No estimator in the comparison set beats the open-free form at 5 or at 21 sessions. That
  includes close-to-close, the six range-based rivals and the full estimator.
* **O (the summary claim).** V1 and V3 both hold.

## Predictions, written before any estimator was computed on these data

* F1 does not hold. In three of the four frontier-market primary tests so far, the frozen estimator
  showed no difference from close-to-close at 5 sessions.
* F2 and F3 hold, and no rival beats the frozen estimator.
* V1, V2 and V3 hold, so O holds.

## Reporting

Every verdict, including failures, goes into `M18_ANAM_MOROCCO_RESULTS.md` with its table. The
outputs are:

* `table112_anam_morocco_panel.csv` (coverage, screens and b̂ by band regime);
* `table113_anam_morocco_forecast.csv` (T1, full test span and by regime);
* `table114_anam_morocco_level.csv`;
* `table115_anam_morocco_noise.csv`;
* `table116_anam_morocco_decisions.csv`.

Once run, the script is changed only to fix an error that stops it running, and any such fix is
registered. Anything computed after the results are seen is labelled post hoc.
