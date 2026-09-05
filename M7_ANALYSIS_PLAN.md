# M7 — frozen analysis plan for the forward-looking India VIX test

**Written and frozen on 2026-09-04, BEFORE any forward-horizon result was computed.** The purpose
of freezing it is that this package has already been criticised, correctly, for a margin declared
after the estimates existed (`R-023`) and for a group defined by its own outcome (`R-025`). A
decision rule chosen after seeing which estimator wins would repeat that error in a third place.

Nothing in this file is conditional on results. The results are written to
`FOURTH_ROUND_AUDIT_RESPONSE.md` and the manuscript afterwards, and the decision rule below is
applied mechanically.

## The object being tested

India VIX at time *t* is the option market's forward-looking, risk-neutral expectation of NIFTY 50
volatility over the **following 30 calendar days**. The existing manuscript analysis correlates it
with a **trailing 21-session** realised measure. Those are different horizons pointing in opposite
directions in time, so a high correlation between them is evidence of *persistence and
co-movement*, not of forecasting validity. This test replaces that comparison with one whose
timing matches the object.

## Specification (fixed in advance)

1. **Forward realised volatility.** For each origin date *t*, realised volatility is computed from
   NIFTY sessions with date **strictly greater than *t***, up to and including *t* + 30 calendar
   days. Day *t* itself is **excluded**: India VIX is disseminated from quotes during session *t*,
   so including session *t*'s own return would let information from the forecast window's own
   origin leak into the outcome.
2. **Estimators.** Close-to-close, Parkinson, Garman–Klass and Rogers–Satchell, each annualised
   with A = 252 (the NSE convention, as already used for the NIFTY block in script 09) and
   expressed in volatility points so it is comparable in level with India VIX.
3. **Primary sample: non-overlapping windows.** Starting from the first available origin, each
   window's successor origin is the first session after the previous window closes. This yields
   independent observations and is the specification the headline result is taken from.
4. **Sensitivity: daily overlapping windows**, with inference that accounts for the induced
   serial correlation — Newey–West HAC with a lag length of at least the window length, and a
   moving-block bootstrap as a second check.
5. **Minimum window occupancy.** A window must contain at least 15 NIFTY sessions to be used,
   so a holiday-shortened window cannot enter as a low-volatility artifact.

## What will be reported, whatever it shows

- Correlations in **levels** (Pearson and Spearman), with confidence intervals.
- **Calibration regressions** RV = a + b·VIX: slope, intercept, R², and a joint test of the
  calibration null (a = 0, b = 1).
- Correlations and regressions in **changes** (ΔVIX vs ΔRV).
- **Lead–lag**: the same correlation computed against the *backward* 30-day window and at a range
  of leads and lags, so persistence can be distinguished from forecasting.
- **Observation counts and exact date coverage** for every specification.
- A **direct Parkinson vs close-to-close comparison**, with an interval on the difference.

## Decision rule (binding, fixed before results)

Applied to the **primary non-overlapping specification**, using the correlation with forward
realised volatility and the interval on the Parkinson-minus-close-to-close difference:

| Outcome | Action |
|---|---|
| Parkinson clearly outperforms close-to-close (difference interval excludes 0 in Parkinson's favour) | Retain a **narrowly worded** validation claim, restricted to what the forward test shows |
| The two intervals overlap / the difference interval contains 0 | Call the comparison **inconclusive**; no estimator-superiority claim |
| Close-to-close performs better (difference interval excludes 0 against Parkinson) | **Withdraw** the estimator-superiority claim entirely |
| Implementation or data limitations prevent a defensible forward test | **Demote the whole VIX section to descriptive evidence** |

## Disposition of the existing analysis, fixed in advance

- The trailing 21-session correlation is **retained only as descriptive co-movement**, explicitly
  labelled horizon-mismatched and unsuitable for forecasting validation. It is not deleted,
  because it is a circulated number.
- The words "validation", "predictive" and "forecasting" are rewritten to match whatever the
  forward test supports, including removal if it supports none of them.
- The distinction between forward-looking risk-neutral implied volatility and backward-looking
  statistical volatility is stated explicitly wherever the comparison appears.

## Reconciliation task (independent of the decision rule)

The manuscript history contains two Parkinson–VIX correlations, 0.832 and 0.776, and two R²
values, 0.692 and 0.602. Both pairs must be traced to the dataset, sample period and
implementation that produced them, and the finding reported regardless of which is "better".

## Leakage controls

Tests must fail if any forward-window computation can see a return dated on or before its own
origin. This is asserted directly on the window construction, not inferred from the results.
