# M20 — frozen plan: the corrected forecast evaluation, after the 9 October 2026 audit

**Written and frozen on 2026-10-09, after the audit and before any corrected forecast loss was computed
on real data.** The commit that adds this file also adds:

* `anam-estimator/src/anam_estimator/evaluation.py`, the corrected target, loss, purging, inference and
  model confidence set, used both by the paper and by the installable package;
* the package's forecasting model rewired to it (`anam_estimator.AnamModel`, version 0.2.0);
* `src/nepsevol/forecast_baselines.py`, the return-only baselines and range variants of Part B;
* tests of all three on simulated data;
* `tests/test_anam_package.py`, rewritten to check that the package model and the research features give
  the same corrected forecast, origin by origin, on NEPSE and the two indices. That check computes the
  corrected forecast of the full and open-free forms on real data. It asserts agreement and reports
  nothing, and no loss, φ or verdict from it was looked at.

The evaluation script (`scripts/47_corrected_evaluation.py`) is written and run only after that commit,
so the order can be checked in the history. The decision rules below are applied mechanically.

## Why this plan

An independent audit of commit `55a3ab4` (9 October 2026; kept in `audits/2026-10-09_research_audit.md`)
found four defects in the forecast evaluation behind plans M16–M18, in `nepsevol.volforecast`, in the
package model and in the post hoc recheck (script 44). Each was reproduced before this plan was
written. The counts below are from that reproduction; no loss was computed.

| Item | Defect | Reproduced on NEPSE |
|---|---|---|
| A01 | The training mask applied to the forecast origin only, so training targets ran into the test span and chose the shrinkage φ with test-period returns. | Origins using outcomes on or after the test start: 1,239 of 66,931 at 5 sessions, 5,191 of 66,917 at 21. |
| A02 | A target of "h sessions" was the next h retained rows, stitched across sessions on which a security had no bar. | Stitched test targets: 218 of 53,168 at 5 sessions (longest span 47 sessions), 618 of 48,912 at 21 (longest 81). |
| A08 | Zero targets were dropped. φ ranged over [0, 2], so a candidate above one could turn negative and be scored on fewer origins. | Training-sample size varies by up to 33,410 origins across the φ grid. No zero target in the NEPSE or index samples. |
| A09 | The reported mean difference weighted stock-days equally; its t statistic was for the equal-date mean. | Morocco, Anam against overnight² + Parkinson at 21 sessions: difference −0.0000999, t +0.19. |

It also observed (A12) that "no classical range estimator has significantly lower loss" is a weak claim
when every comparator is a daily kernel inside the same calibration-and-shrinkage forecast. It asked for:

* return-only baselines;
* ablations that remove one ingredient at a time;
* joint inference, by a model confidence set;
* stated practical-effect margins.

The paper's frozen verdicts stay in the record as what the plans found. This plan fixes how they are
re-run without the defects, and how the extended comparison is judged.

## What was known before freezing (disclosed, so the plan can be judged against it)

1. **Every frozen result.** M16–M18 (tables 101–116), M19 (tables 121–123) and the post hoc recheck
   (tables 117–120).
2. **The audit's own sensitivities.** They were run by the auditor and quoted in the audit.
   * Purging alone moves NEPSE's fitted φ for the full and open-free forms from 0.65 to 0.70 at
     5 sessions and from 0.65 to 0.75 at 21.
   * Purging plus consecutive-session targets puts the full form's five-session φ at 0.75. Its loss
     difference against close-to-close then rises from 0.01598 to 0.01938, and its equal-date t from
     1.19 to 1.58. Close-to-close still has the lower loss, not significantly.
   * The 21-session NEPSE comparison stays inconclusive.
   * The indices' weights and results are unchanged.
   * No published conclusion flips in the audited samples.
3. **The frozen selections.** Every φ selected in tables 101, 108 and 113 lies between 0.10 and 0.80.
4. **Counts only, from reproducing A01, A02 and A08 on NEPSE.** The counts in the table above, and that
   no NEPSE or index target is zero. No loss, forecast or verdict under the corrected design has been
   computed for any sample, and no return-only baseline has been computed at all.

## Samples, spans and horizons (unchanged from M16–M18)

| Sample | Training span | Test span(s) | Calibration | Calendar |
|---|---|---|---|---|
| NEPSE (equity) | regimes A1 + B | A2 + C (primary); A2 and C reported | pooled, 60 dates | the 569 sessions of `data/processed/nepse_trading_calendar.csv` |
| NIFTY 50, S&P 500 | first half | second half | the series' own 250 sessions | the index's own dates |
| DSE 2023–2026, Vietnam 2007–2020 (primary); DSE 2009–2021 (secondary) | first half | second half | pooled, 60 dates | the panel's sessions (`nepsevol.frontier.build_panel`) |
| Morocco 2012–2026 | first half | second half | pooled, 60 dates | the panel's sessions |

The horizons are h = 5 and h = 21 sessions. The panels are built exactly as in scripts 40, 42 and 43. No
constant of the estimator changes: b, κ, λ₀ = 0.2 and the 60-date pool all stay as frozen in M16.

## The corrected design (implemented in `anam_estimator.evaluation`)

1. **The target.** At the close of session t, y_t(h) is the mean of r² over the security's next h
   exchange sessions of the calendar above. It is observed only if the security has a close-to-close
   return on each of those sessions. A target is scored in a test span only if its whole outcome window
   lies inside the span. y may be zero. Its conditional mean is the conditional second moment of
   observed close-to-close returns. That is not latent integrated variance (`ESTIMAND_NOTE.md`).
2. **Purging.** A training origin is used only if its outcome ends before the first session of the test
   span.
3. **The loss.** QLIKE in its canonical form, L(y, f) = y/f + ln f, so zero targets are scored. Levels
   are also reported in the normalised form, y/f − ln(y/f) − 1, on the origins with y > 0, for
   comparison with the frozen tables.
4. **The forecasts of the frozen design.** f = κ_t [φ cur_t + (1 − φ) lr_t]:
   * cur is the mean of the kernel over the security's last h observed bars;
   * lr is its mean over the last 250 observed bars, with at least 60;
   * κ is unchanged.

   The candidate weights are φ ∈ {0, 0.05, …, 0.95}. They are convex, so every candidate is positive
   wherever κ > 0 and lr > 0. A candidate that is not positive on every selection origin is rejected,
   not scored on fewer origins.

   Features computed over a security's last observed bars stay as they are. They are known at the
   origin, so they are legitimate predictors in transaction time. The calendar governs only what is
   being forecast.
5. **The common samples.** The test sample of a span is every test origin with an observed target at
   which every model of the comparison has a defined forecast:
   * for kernel forecasts, κ > 0, lr > 0 and cur defined, where cur may now be zero;
   * for the recursive baselines, a defined long-run level.

   The training sample is defined the same way on the purged training origins. Exclusions are counted
   by reason (Part D).
6. **Inference.** The primary estimand is the stock-day mean loss difference, the quantity φ is chosen
   to minimise.
   * Its standard error comes from the date-level linearisation u_t = Σ_{i on t}(d_i − d̄), with a
     Bartlett long-run variance over dates and bandwidth L = 2h.
   * The frozen bandwidth h gives the lag-(h−1) overlap autocovariance a weight of only 2/(h+1).
     With 2h it gets a weight above one half.
   * Verdicts: "beats" if d̄ < 0 and t < −1.96; "loses to" if d̄ > 0 and t > 1.96; otherwise "no
     significant difference".
   * Under the Giacomini–White (2006) reading, with φ estimated once on the training span, this tests
     the forecasting method including its fitted φ. No separate correction for parameter uncertainty is
     made.

## Part A — the correction, one step at a time (the nine frozen estimators)

Each step adds one correction to the previous one. All nine frozen estimators (close-to-close,
Parkinson, Garman–Klass, Rogers–Satchell, overnight² + Parkinson, overnight² + Garman–Klass, the
Yang–Zhang daily form, and Anam's estimator in its full and open-free forms) are scored at every step.

| Step | Adds | Inference reported |
|---|---|---|
| S0 | nothing: the frozen code, which must reproduce tables 101, 108 and 113 to 1e-9 | frozen |
| S1 | purged training origins (outcome end, by the frozen row target, before the test start) | frozen |
| S2 | the calendar target, inside the span | frozen |
| S3 | canonical QLIKE with zero targets kept, φ ∈ [0, 0.95], the eligibility rule of design item 5 | frozen |
| S4 | the corrected inference of design item 6 | corrected |

Each step reports, for every estimator:

* φ, the number of origins, and both loss levels;
* the difference from close-to-close, from Parkinson and from the full form, each with its t.

**Rule A.** Every per-rival verdict of tables 105, 111 and 116 is re-read at S4 and listed with its
frozen verdict (table 126). The S4 verdicts are the corrected record of M16–M18.

## Part B — the extended comparison (17 forecasts, on the S4 design)

**Return-only, 5 forecasts:**

| Model | Definition | Selection grid |
|---|---|---|
| CC | φ-shrinkage of r² (as frozen) | φ |
| EWMA | s_{t+1} = λ s_t + (1 − λ) r_t², flat over the horizon | λ ∈ {0.80, 0.85, 0.90, 0.94, 0.96, 0.97, 0.98, 0.99} |
| GARCH | variance-targeted GARCH(1,1), level v_t = the security's trailing mean of r² (250 observed sessions, at least 60), h-step mean forecast | α ∈ {0.02, …, 0.20} by 0.02; p = α + β ∈ {0.80, 0.85, 0.90, 0.93, 0.95, 0.97, 0.98, 0.99} |
| GJR | variance-targeted GJR-GARCH(1,1), same level | α ∈ {0, 0.02, …, 0.10}, γ ∈ {0.04, 0.08, 0.12, 0.16, 0.20}, p = α + β + γ/2 on the same grid |
| HAR-CC | c₁ r_t² + c₂ mean₅ + c₃ mean₂₂ + c₄ lr of r² | convex c on a 0.1 grid with c₄ ≥ 0.1 (220 points) |

The recursions run in calendar time. A session without a return replaces the shock by its expectation.
Parameters are common to all securities of a sample.

**Range-based, 11 forecasts:**

* the seven frozen classical forecasts other than close-to-close: Parkinson, Garman–Klass,
  Rogers–Satchell, overnight² + Parkinson, overnight² + Garman–Klass, the Yang–Zhang daily form, and
  Anam's estimator;
* Anam's open-free form;
* **TR-P**: Wilder's true range in Parkinson's form, TR²/(4 ln 2), calibrated and shrunk like the
  others;
* **HAR-open-free**: κ times the convex HAR of the open-free kernel;
* **Anam posterior (exploratory)**: the full kernel with (b o)² replaced by b² o² + b(1 − b) m₂, where
  m₂ is the security's trailing mean of o² (250 observed sessions, at least 60). It was derived after
  the audit (item A04) and has never been tested out of sample.

**Combination, 1 forecast:** ½ CC + ½ open-free, fixed weights.

Every tuned parameter is chosen to minimise the mean canonical QLIKE over the purged common training
sample.

**Rule B1 (does the range add forecasting information?).** In each sample, span and horizon, take:

* r\*, the return-only model with the lowest training loss;
* g\*, the range-based model with the lowest training loss.

Both are chosen on the training span only. On the test span, the verdict is:

* "range adds information" if g\* beats r\*;
* "returns suffice" if r\* beats g\*;
* otherwise "no significant difference".

**Rule B2 (model confidence set).** Hansen, Lunde and Nason's (2011) MCS over the 17 forecasts:

* the T_max statistic on stock-day mean canonical losses;
* a stationary bootstrap of dates with mean block max(2h, 10), 1,999 resamples, seed
  20261010 + 100·(sample index) + h.

It reports the 90% set (α = 0.10, primary) and the 75% set.

**Rule B3 (multiplicity).** Holm's adjustment over the seven samples' primary spans at 5 sessions,
separately for "full form beats close-to-close" and "open-free form beats close-to-close". It uses
one-sided p = Φ(t), and holds at an adjusted p < 0.025.

**Rule B4 (practical margin, secondary).** A form is practically equivalent to close-to-close if the 90%
interval of its stock-day mean difference (±1.645 se) lies within ±1% of close-to-close's normalised
QLIKE on the common sample.

## Part C — ablations (reported, no decisions)

All on the Part B test sample, with the S4 inference:

| Contrast | What it isolates |
|---|---|
| Parkinson raw (κ ≡ 1) against Parkinson; open-free raw against open-free | calibration |
| TR-P against Parkinson | the previous-close anchor |
| open-free against TR-P | the 0.2 r² blend |
| full against open-free (estimated b against b = 0); full against overnight² + Parkinson (b = 1) | estimating the open's reliability |
| open-free with its own 250-session calibration against pooled (panels only) | cross-sectional pooling |
| open-free with κ fixed at its purged training-span ratio against rolling κ | an adaptive scale |
| HAR-open-free against open-free; HAR-CC against CC; the open-free and full kernels with close-to-close's φ against close-to-close | forecasting dynamics against measurement |
| Anam posterior against Anam | the residual-uncertainty correction |

## Part D — coverage

For each sample, span and horizon, counts of test origins:

* **by target status:** complete, missing session, missing return, or outcome beyond the span;
* **among complete targets:**
  * eligible;
  * excluded because a forecast is not yet defined;
  * excluded because a long-run level or calibration is zero;
* the number of zero targets that are eligible.

The counts are split by liquidity tercile. Terciles use the security's median trade count (NEPSE) or
volume (frontier panels) over its training-span bars, fixed before the test span. Securities without
training bars form a fourth group.

## Part E — inference sensitivity (reported)

The comparisons:

* full form against close-to-close;
* open-free form against close-to-close;
* open-free form against the full form;
* g\* against r\*.

For each, the t statistic is reported under:

* bandwidths h, 2h (primary), 4h and Andrews' AR(1) plug-in (at least h);
* the equal-date mean and the equal-security mean, each with its own t;
* non-overlapping origins (every h-th session from the first test session), with a rule-of-thumb
  bandwidth.

## How the paper's claims will be rewritten (fixed now)

* The forecasting record of Anam's estimator becomes the S4 verdicts, MCS membership and Rule B1,
  whatever they are. The frozen M16–M18 verdicts stay as the plans' historical record, with the
  audit's defects described.
* "No classical range estimator has significantly lower loss than Anam's estimator in any test sample"
  is kept only if it holds at S4 in every sample and horizon. Otherwise it is replaced by the count.
* Where Rule B1 is not "range adds information", the paper says so for that sample. "Returns suffice"
  means the best return-only forecast beat the best range-based one. "No significant difference" means
  the range added no detectable forecasting information beyond it.
* The open-free form keeps "lowest loss" or "best" wording only where it is in the 90% MCS and has the
  lowest test loss among the 17.

## Outputs

| File | Contents |
|---|---|
| `output/tables/table125_m20_correction_steps.csv` | Part A, every step |
| `table126_m20_verdict_changes.csv` | Rule A |
| `table127_m20_comparison.csv` | Part B: parameters, training and test losses, differences from close-to-close, the full form and the open-free form |
| `table128_m20_mcs.csv` | Rule B2 |
| `table129_m20_claims.csv` | Rules B1, B3, B4 |
| `table130_m20_ablations.csv` | Part C |
| `table131_m20_coverage.csv` | Part D |
| `table132_m20_inference.csv` | Part E |
| `M20_CORRECTED_EVALUATION_RESULTS.md` | the results, with every deviation from this plan disclosed |
