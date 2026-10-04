# M14 — frozen analysis plan: instrumented calibration of daily-bar volatility estimators, and two market-design natural experiments

**Written and frozen on 2026-10-04, before any calibration slope, composite weight, kernel moment
or regime comparison was computed on NEPSE or NIFTY data.** It follows the M7 convention: the
specification, the reporting set and the decision rules are fixed here, the results are written
afterwards, and the decision rules are applied mechanically. The commit that adds this file
precedes the commit that adds `scripts/34_instrumented_calibration.py` and its outputs, so the
order is checkable in the history.

## What was known before freezing (disclosed, so the plan can be judged against it)

1. **Simulation only.** The method was developed and checked on simulated panels
   (`nepsevol.estimators.microsim`, `scripts/35_calibration_simulation.py`). The Monte Carlo
   fixed three design choices reported below: forward orthogonal deviations (the whole-sample
   within transformation is biased at order 1/T and over-rejects the J test in a correctly
   specified model), instruments in levels (closer to the oracle when the measurement relation
   is nonlinear), and predictable precision weights (unweighted estimates are far noisier under
   nonlinearity). The simulation also supplied the **predicted signs** for H4 and H5 below.
2. **Descriptive input features**, used only to set simulation parameters: security
   trade-intensity quantiles (median 168, log-sd 0.97); daily close-to-close volatility (median
   2.4%, cross-sectional log-sd 0.51); the share of opens equal to the previous close (10.6%);
   the share of opening returns pinned at the band (24% at ±2% before 20 April 2026, 8% at ±5%
   after); the share of closes off the 0.1 price grid by month (0% before 20 March 2025, ~85%
   from then to 21 September 2025, 0% after), which locates the closing-rule regime; and two
   moments computed while checking the VWAP field, E[a²]/E[c²] = 0.62 and E[ac]/E[c²] = 0.70
   with a = ln(VWAP/O), c = ln(C/O). No estimator ratio, slope or correlation entered any
   simulation parameter.
3. **A prior real-data result touching H4.** `scripts/19_addrs_premise.py` (an earlier revision)
   reports Rogers–Satchell/open-to-close variance ratios of 1.129 (A1), 1.158 (B) and 1.035 (A2)
   across the closing-rule regimes. Those are ratios, which this plan argues are confounded by
   the volatility level through the additive component; H4 is stated on slopes, but the author
   knew these ratios when writing it.

## The measurement model and the estimands

For security *i*, session *t*: `X_k,it = α_k,i + β_k·IV_it + U_k,it`, `E[U_it | IV_it, F_i,t−1] = 0`.
Estimands, all relative to the matched proxy `OC = c²` (normalised `β_OC = 1`):

* **calibration slope** `β_k` — the slope of estimator *k*'s conditional mean on the proxy's
  conditional mean, identified with instruments dated *t−1* or earlier. Where the measurement
  relation is nonlinear it is the linear-projection slope on predictable variance; the Monte
  Carlo shows the instrumented estimate then errs toward one by 0.02–0.03 for the range
  estimators (conservative for an attenuation claim);
* **additive share** `δ_k = mean(X_k)/mean(OC) − β_k` (exact decomposition of the variance-scale ratio);
* **composite** `w* = Σ⁻¹β / (β'Σ⁻¹β)` and the identified excess noise `D_k` and efficiency lower
  bound `UB_k/(UB_k − D_k)` (definitions in `nepsevol.calibration`).

## Specification (fixed)

| Item | Choice |
|---|---|
| Sample | `data/processed/equity_sample.csv`, all 143,718 stock-days, rows with all inputs defined |
| Previous close | the adopted corporate-action-adjusted `prev_close_adj`, NaN across session gaps |
| Measures (intraday system) | OC (reference), P, GK, RS, AddRS, AP, GKV |
| Blocks (empirical best quadratic) | u², d², c², ud, uc, dc, a², ac, au, ad; reference c² |
| Instruments | trailing means of OC and P over the previous 1, 5 and 22 observed sessions of the same security (6 instruments, `skip=1`), in levels, plus a constant |
| Weights | `1/S²_{t−1}`, S = trailing 22-session mean of P, floored at its 1% quantile |
| Fixed effects | security; removed by forward orthogonal deviations |
| Inference | stationary block bootstrap over dates (mean block 21 sessions) × i.i.d. securities, 499 replicates, 95% percentile intervals; Hansen J per measure with two-way (security × date) clustering |
| Liquidity groups | security-level quintiles of full-sample median trade count (the manuscript's predetermined security-level sort) |
| Sensitivity (reported, not decisive) | whole-sample within transformation; unweighted; past-demeaned instruments; instruments lagged two sessions |

## Hypotheses and decision rules (binding)

**H1 — ratios mask calibration.** Full sample, k ∈ {P, GK, RS}. *Masking* is declared for k if the
95% interval of β_k lies entirely below one **and** that of δ_k entirely above zero. If β_k's
interval contains one: *no detectable attenuation* (the ratio then does describe the slope). If
it lies entirely above one: *amplification*.

**H2 — the slope gradient in liquidity.** β_P in the thinnest versus the most active security-level
quintile. Discreteness theory predicts a lower slope in the thinnest. A *gradient* is declared if
the 95% interval of β_P(Q1) − β_P(Q5) lies entirely below zero; *reversed* if entirely above;
otherwise *not detected*.

**H3 — the composite improves out of sample.** Split the sample at the median date. Estimate the
block composite's weights on the first half. On the second half, compute the identified noise
difference `Δ_k = Var(w'X)/(w'β₂)² − Var(X_k)/β²_k,2` (β₂ re-estimated on the second half), for
k ∈ {OC, P, GK, RS, GKV}. *Improvement over k* is declared if Δ_k's 95% interval lies entirely
below zero.

**H4 — the closing-rule reversal (A1 → B → A2).** Regimes: A1 2024-03-04 to 2025-03-19 (last-trade
close); B 2025-03-20 to 2025-09-21 (VWAP of 14:45–15:00), excluding 2025-09-18 (the early-close
session on resumption after the September 2025 halt, on which no off-grid closes print); A2
2025-09-23 to 2026-04-19 (last-trade close). All three share the ±2% band and ±10% limit.
Predicted from the simulation: the averaged close lowers the proxy's response, so **β_P is higher
in B than in A1 and than in A2**. *Confirmed* if both differences' 95% intervals exclude zero in the
predicted direction; *partial* if one does; *not detected* otherwise. Also reported, with the
predicted sign from the simulation: E[c_t·o_t+1]/E[P] higher in B (the Working averaging effect).

**H5 — the opening-band widening (A2 → C).** C = 2026-04-20 to 2026-08-26 (±5% band, ±15% limit).
Predicted from the simulation: less overnight leakage into the session, so **β_P higher in C than
in A2**, and E[o_t·c_t]/E[P] lower in C. *Confirmed* if the 95% interval of β_P(C) − β_P(A2) lies
above zero. The reform changed the band, the limit and the circuit breaker on one date, and C
contains only about four months, so a confirmed H5 is evidence about the package of rules, not
about the band alone.

**H6 — an external instrument for NIFTY 50.** Measures OC, P, GK, RS, AddRS on NIFTY 50, 2010–2026
(previous close = prior row; gapless index), single series, FOD, weights as above, stationary
block bootstrap over dates. Instrument sets: (i) lagged means of OC and P (as for NEPSE);
(ii) India VIX only — the squared index on t−1 and its trailing 5-session mean, in daily variance
units; (iii) both. *Corroborated* if, for every measure, the 95% interval of β(i) − β(ii) contains
zero; otherwise the disagreement is reported as a failed overidentification. The 5 October 2012
session is retained (primary) and excluded (sensitivity), as in the manuscript.

## Reported whatever they show

Slopes, additive shares, mean ratios, OLS slopes and correlations (to show what the naive
statistics would have said), J statistics, rank-one shares, first-stage F, composite weights,
excess-noise and efficiency bounds, observation counts and date coverage, for every specification
above; the Monte Carlo validation tables (74–77).

## Wording rules (binding)

1. "Calibration slope relative to the matched proxy", never "bias"; noise *levels* are stated
   only as bounds.
2. The identification device is not claimed as new. Lagged-instrument calibration of noisy
   measurements, the rank-one lagged-covariance structure and data-based ranking have precedents
   (Christensen & Prabhala 1998; Hansen & Lunde 2014; Su et al. 2014; Lam, Yao & Bathia 2011;
   Patton 2011; Patton & Sheppard 2009; Hansen & Huang 2016). The claim is its application to
   daily OHLC(+VWAP) estimators without a high-frequency benchmark, the slope-constrained
   composite, and the evidence.
3. No "first". Natural-experiment results are described as evidence about the rule package in
   force, with the confounds named.
