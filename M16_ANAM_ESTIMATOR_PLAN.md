# M16 — frozen plan: validating Anam's estimator on held-out data

**Written and frozen on 2026-10-08, after the estimator was designed on the development sample and
before any holdout observation was read.** The commit that adds this file also adds the estimator
(`src/nepsevol/estimators/anam.py`), its property tests (`tests/test_anam_estimator.py`), the
evaluation module (`src/nepsevol/volforecast.py`) and the development evidence
(`scripts/39_anam_development.py`, tables 98–100b). The holdout script
(`scripts/40_anam_holdout.py`) is written and run only after that commit, so the order is checkable
in the history. The decision rules below are applied mechanically.

## What was known before freezing (disclosed, so the plan can be judged against it)

1. **The design used only the development sample** — NEPSE regimes A1 (2024-03-04 to 2025-03-19)
   and B (2025-03-20 to 2025-09-21), 86,675 stock-days of 261 securities — and simulated panels. Every design choice
   was scored on cross-regime forecasts: tuned on one regime, scored on the other.
2. **M15's findings informed the design and were computed on the FULL NEPSE sample**, including the
   holdout regimes A2 and C: the open is mostly transient (b between 0.13 and 0.36 by regime), the
   20 April 2026 band reform lowered b sharply, and Yang–Zhang's excess over close-to-close variance
   is mostly the overnight–intraday covariance. The NEPSE holdout is therefore not pristine with
   respect to those facts, though no estimator considered here was ever evaluated on it.
3. **NIFTY 50's index-level b (0.929) and its range-estimator ratios** were reported in M14/M15; no
   estimator was tuned on NIFTY data in this work.
4. **The S&P 500 file** (`arch` 8.0.0, `arch.data.sp500`, 1999-01-04 to 2018-12-31, originally from
   Yahoo Finance) was opened once, to confirm it exists: its first and last rows were printed, and it
   was noticed that early opens equal the previous close. No estimator was computed on it.
5. **Alternatives tried and rejected on development data** (table 98d and the history in the results
   document): learned minimum-noise quadratic composites (in-sample efficiency up to 3.2× close-to-close
   on the instrumented criterion, but worse than close-to-close in cross-regime forecasts, and
   indefinite quadratic forms that go negative); positive-semidefinite versions; up/down-symmetric
   versions; state-dependent (open = high/low) versions; open-excluded one-sided ranges; a trade-count
   discreteness correction; robust window aggregators (geometric mean, median, trimmed, bipower:
   better at 5 sessions, worse at 21); a mean-zero-calibrated control variate; a Garman–Klass control
   switched on by b²; open-quality weights b² and b³ (within 0.001 of b).

## The estimator (fixed)

For a bar (O, H, L, C) with previous close PC (adjusted for corporate actions, NaN across gaps):
o = ln(O/PC), r = ln(C/PC), h = ln(H/PC), l = ln(L/PC), R = ln(H/L).

| Step | Definition | Constant |
|---|---|---|
| Open quality | b = Σ o r / Σ o², clipped to [0, 1]; 0 where Σ o² = 0 | panel: pooled over all securities, last `POOL_SESSIONS` = 60 dates (≥ 20); single series: own last `SERIES_SESSIONS` = 250 sessions (≥ 60) |
| Extended range | R* = R + max(0, b o − h) + max(0, l − b o) | — |
| Daily kernel | A = (1 − w)[(b o)² + R*²/(4 ln 2)] + w r², w = `LAMBDA0`·(1 − b) | `LAMBDA0` = 0.2 |
| Calibration | κ = Σ r² / Σ A over the same trailing set as b | as for b |
| Window variance | σ̂² = κ · mean(A over the window) | window = 5 or 21 sessions here |

Implementation: `nepsevol.estimators.anam.anam_estimator(df, window, mode)`; `mode="panel"` for
NEPSE, `mode="series"` for each index.

## Development evidence at freezing (tables 98–100b; regimes A1, B only)

* **Forecasts (table 98; pooled calibration and own shrinkage for every estimator; QLIKE, lower is
  better).** At 5 sessions Anam is second only to its own open-free special case in both directions
  (0.5687 vs Parkinson 0.5747, t = −5.4; 0.4857 vs 0.4888, t = −1.5), and beats close-to-close
  (t = −3.6, −3.0). At 21 sessions it is second when trained on A1 (0.2987 vs Parkinson 0.3017) but
  fifth when trained on B (0.3163, behind overnight² + Parkinson 0.3105 and the Yang–Zhang family);
  no difference from Parkinson at 21 sessions is significant. Every open-anchored estimator
  (Garman–Klass, Rogers–Satchell, Yang–Zhang) is significantly worse than Parkinson at 5 sessions.
* **Calibration (table 98b).** Pooled calibration beats per-security calibration in all 12
  comparisons.
* **Constant (table 98c).** `LAMBDA0` = 0.2 is within 0.0035 of the best value in every column.
* **Simulation with known truth (table 99).** Anam is the most accurate estimator under thin trading
  and moderate or heavy opening errors, within 0.0006 of the best with stale opens and in the
  simulator's default world — and about 30% less accurate than Garman–Klass in a clean continuous
  market (0.0107 vs 0.0080), the price of not trusting a good open.
* **Level (table 100).** Raw classical estimators overstate close-to-close variance in A1 and B:
  Parkinson by 15% and 29%, overnight² + Parkinson by 39% and 65%, the Yang–Zhang daily form by 48%
  and 75%. Anam's calibrated 21-session variance: 0.999 and 1.023.
* **Instrumented noise (table 100b).** Anam's efficiency lower bound against close-to-close is 2.05,
  against 2.16 for Parkinson; its calibration slope is 0.98, the closest to one among the range
  estimators.

## Holdout samples (fixed)

| Market | Data | Rows | Mode |
|---|---|---|---|
| NEPSE holdout | `data/processed/equity_sample.csv`, regimes A2 (2025-09-23 to 2026-04-19) and C (2026-04-20 to 2026-08-26), 2025-09-18 excluded | all equity stock-days with a defined previous close | panel |
| NIFTY 50 | `data/external/nifty50.csv` (NSE index OHLC) | 2010-01-04 to 2026-06-12 | series |
| S&P 500 | `arch.data.sp500` (arch 8.0.0; Yahoo Finance OHLC) | 1999-01-04 to 2018-12-31 | series |
| Implied variance (reported only) | India VIX (`data/external/india_vix.csv`); `arch.data.vix` (2014–2019) | overlapping dates | — |

## Comparison set (fixed)

Close-to-close r²; Parkinson; Garman–Klass; Rogers–Satchell; overnight² + Parkinson; overnight² +
Garman–Klass; the Yang–Zhang daily form (o² + k c² + (1 − k) RS, k for n = 21); Anam; and Anam's
open-free special case (b = 0) as a reported variant. For the level test, the window form of
Yang–Zhang with sample variances is added.

## Tests (fixed)

**T1 — forecasts.** `nepsevol.volforecast.fair_forecast_test`, QLIKE, horizons of 5 and 21
sessions; every estimator calibrated by the same scheme (NEPSE: pooled, 60 dates; indices: own
history, 250 sessions) and given its own shrinkage φ chosen on a training span, all scored on a
common set of origins. Training span: NEPSE — the development sample; NIFTY 50 and S&P 500 — the
first half of each series by date. Test span: NEPSE — A2 ∪ C (also reported separately for A2 and
for C); indices — the second half. Newey–West t statistics on the per-date loss difference, lags
equal to the horizon.

**T2 — level.** Each estimator's raw 21-session window mean divided by the 21-session mean of r²,
over the test span (NEPSE: separately for A2 and C). Anam enters calibrated.

**T3 — the band reform (NEPSE only).** The change in T2's ratio from A2 to C.

**T4 — instrumented noise (reported, no decision).** The M14 machinery with reference r² and
instruments lagged two sessions, on the NEPSE holdout.

**T5 — implied variance (reported, no decision).** Correlation of each calibrated 21-session
estimate with the implied variance (VIX², India VIX²) on the same date.

## Decision rules (binding)

For each market, horizon and rival X: Anam **beats** X if its mean QLIKE difference is negative with
t < −1.96; **loses to** X if positive with t > 1.96; otherwise **no difference**.

* **H1 (NEPSE, primary).** Anam beats close-to-close and Parkinson at 5 sessions on A2 ∪ C.
* **H2 (NEPSE level).** Anam's calibrated ratio lies within [0.9, 1.1] in both A2 and C, while the
  raw ratios of overnight² + Parkinson and of the Yang–Zhang daily form lie outside it in both.
* **H3 (the reform).** Anam's ratio changes by less than 0.10 between A2 and C; the Yang–Zhang
  window form's ratio changes by more.
* **H4 (NIFTY 50)** and **H5 (S&P 500).** Anam beats close-to-close at 5 sessions. Against the other
  rivals the verdicts are reported as they fall.
* **"Best in a market"** is declared only if no rival beats Anam at either horizon in that market.

## Predictions, written before the holdout was read

* NEPSE: H1, H2 and H3 hold; no rival beats Anam at either horizon.
* NIFTY 50 and S&P 500: H4 and H5 hold; Anam beats Parkinson where opens are stale or noisy; in a
  clean index, Garman–Klass or overnight² + Garman–Klass may beat it at 5 sessions, as in the clean
  simulated market. A loss there would be reported as the cost of the design, not explained away.

## Reporting

Every verdict, including failures, goes into `M16_ANAM_ESTIMATOR_RESULTS.md` with its table.
Anything computed after the holdout results are seen is labelled post hoc and kept in a separate
script.
