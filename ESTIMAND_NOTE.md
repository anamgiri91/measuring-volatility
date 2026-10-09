# What the forecasts and estimators measure: an estimand note

Written on 9 October 2026, after the independent audit of that date (items A03, A04 and A06;
`audits/2026-10-09_research_audit.md`). This is Phase 2 of the audit's publication plan. It fixes four
objects that the earlier text sometimes ran together, and says which one each claim in the paper is
about.

## Notation

Log prices and the paper's Appendix A decomposition, for session t:

* **Overnight return:** o_t = e_{o,t} + η_t − ε_{t−1}.
* **Intraday return:** c_t = e_{c,t} − η_t + ε_t.

Here:

* e_o and e_c are the efficient (permanent) overnight and intraday moves;
* η_t is the transient error of the printed open;
* ε_t is the error of the printed close.

The observed close-to-close return is r_t = o_t + c_t = e_t + ε_t − ε_{t−1}, with e_t = e_{o,t} + e_{c,t}.
F_t is the information at the close of session t.

## Four objects

| Object | Definition | What it is |
|---|---|---|
| **m_t(h)**, the conditional second moment of observed returns | E[(1/h) Σ_{j=1..h} r_{t+j}² \| F_t] | the forecast target of Section 6.8 and of plan M20 |
| **v_t(h)**, the conditional return variance | (1/h) Σ_j Var(r_{t+j} \| F_t) = m_t(h) − (1/h) Σ_j E[r_{t+j} \| F_t]² | what a risk model usually means by "variance" |
| **IV_t(h)**, efficient integrated variance | the efficient price's continuous quadratic variation over the h sessions; in the daily notation E[(1/h) Σ_j e_{t+j}² \| F_t] when e has no jumps | what range estimators were derived to measure |
| **QV_t(h)**, jump-inclusive quadratic variation | IV plus the squared jumps of the efficient price | what squared returns measure when the price can jump |

## How they differ

* **m and v** differ by the squared conditional mean of returns. At daily horizons this is small, but
  not zero in a market whose returns are predictable: the opening reversal of Section 6.7 is such
  predictability.
* **v and IV** differ by everything the printed close adds to the efficient price. With closing errors
  that are serially uncorrelated and independent of e,
  E[r_t²] = E[e_t²] + 2 E[ε²],
  so a squared observed return overstates efficient variance by twice the closing error's variance.
  Other differences:
  * NEPSE's fifteen-minute VWAP close of regime B smooths the endpoint and changes E[ε²].
  * A daily limit that binds truncates r, so E[r²] < E[e²] on those days.
  * A session without a trade has no close-to-close return. M20's target treats it as unobserved and
    fills nothing with zero.
* **IV and QV** differ by jumps. Squared returns include them. Range estimators derived for a
  continuous path do not measure them correctly.

## Which object each claim is about

* **The forecast comparison (Section 6.8; M20).** The target y_t(h) = (1/h) Σ r_{t+j}² is
  conditionally unbiased for m_t(h) by construction. QLIKE therefore ranks forecasts as their
  distance from m_t(h) would (Patton 2011). It ranks forecasting methods, each a daily measure plus a
  calibration plus a shrinkage, for m_t(h). It does not by itself rank daily estimators of IV.
  * The closing-error term 2E[ε²] can be thought of as a fixed addition to m.
  * But a forecast's distance from m and its distance from IV need not order the same way under
    QLIKE, which is not translation invariant. A method that is better for m can be worse for IV.
* **The calibration κ of Anam's estimator.** κ sets the estimator's level to the close-to-close scale,
  that is, to m, not to IV. "The level comes from close-to-close variance, which no opening error can
  bias" is true of the open. It is not true of the close, whose errors enter r² and therefore κ.
* **The calibration slopes (Section 6.6).**
  * They are slopes relative to the open-to-close proxy, whose loading on latent variance is
    normalised to one.
  * They identify relative scale under the maintained measurement model.
  * They do not show that the proxy responds one-for-one to IV.
  * A slope interval containing one does not establish equivalence: [0.760, 1.056] for Parkinson is
    compatible with 24% attenuation.
* **The unbiasedness coefficient b (Section 6.7).** b = E[o r]/E[o²] is a projection coefficient. Under
  the paper's Assumption 1 (the theory supplement), b·o is the best through-origin linear predictor of
  o* = e_o − ε_{t−1} given o, on the log scale.
  * PC·exp(b o) is an anchor price that this implies. It is not the linear predictor, or the
    conditional mean, of the efficient opening price.
  * Read as "the share of the overnight move that survives", 1 − b is weighted by squared opening
    moves. It is neither the share reversed on a typical day nor the share of erroneous opens.
* **The overnight term of Anam's kernel.** E[(b o)²] = b² E[o²], the lower end of the identified set
  for E[o*²] (theory supplement, Proposition 1(e)). When η is uncorrelated with o*, it equals
  b·E[o*²], so it understates the efficient overnight second moment by the factor b. The linear
  posterior second moment b² o² + b(1 − b) E[o²] is unbiased for it under that condition, and equals
  E[o*² | o] under joint normality (Proposition 7). The kernel as frozen is therefore a heuristic
  shrinkage construction, not an unbiased estimator of efficient overnight variance.

## What would be needed to rank estimators of IV

A benchmark with known or independently measured IV:

* a simulation with a stated price model (the theory supplement's Assumption 2, extended with jumps,
  closing errors and limits);
* or a liquid market with intraday data and a realised-variance benchmark matched in scope and
  horizon.

Neither is in the present evidence. Until one is, the paper's forecast claims are about m_t(h), and its
level claims are about agreement with an observable benchmark.
