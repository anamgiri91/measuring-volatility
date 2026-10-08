# M15 — frozen analysis plan: what the opening price measures, and what a band reform did to it

**Written and frozen on 2026-10-07, before any statistic named in the hypotheses below was
computed.** It follows the M7 and M14 convention: specification, reporting set and decision rules
are fixed here; the results are written afterwards, in `M15_OPENING_PRICE_RESULTS.md`; the
decision rules are applied mechanically by `scripts/37_opening_price.py` into a ledger
(`table96_m15_decisions.csv`). The commit adding this file precedes the commit adding that
script and its outputs, so the order is checkable in the history.

## Why this analysis exists

M14 established that the range estimators' near-unit ratios to the open-to-close proxy are
calibration, not offsetting distortion. Its post hoc follow-up (E2, `table88`) then raised a
harder question: the proxy and the range estimators are both built from the OPENING price, and
the overnight–intraday cross-moment E[o_t c_t] moved sharply when NEPSE widened the pre-open band
on 20 April 2026. If the open carries a transient error, an estimator and its benchmark can agree
because they share that error. M15 asks, in the language of the price-discovery literature, how
well the open anticipates the close under each opening rule, and what the answer does to the
measurement of volatility.

## What was known before freezing (disclosed, so the plan can be judged against it)

1. **Every M14 table** (`table74`–`table88`), in particular, by regime (A1, B, A2, C):
   E[o_t c_t]/E[P] = −0.149, −0.213, −0.180, −0.545; E[c_t o_t+1]/E[P] = 0.012, 0.001, −0.003,
   −0.085; share of opens at the band 28.1%, 22.9%, 22.5%, 8.2%; transient-noise share
   1 − E[K]/E[OC] = 14.4%, 23.4%, 17.9%, 56.2%; E[K]/E[P] = 0.817, 0.693, 0.840, 0.498;
   E[OC]/E[P] = 0.955, 0.905, 1.023, 1.136. The point estimates of H10 below are therefore
   implied by `table88` and H10 is labelled a consequence, not a test.
2. **The Monte Carlo of M14** (`table76`): the kernel K is biased upward under band censoring
   (K/IV = 1.155 in the ±2% scenario) and by stale opens.
3. **Input descriptives computed while designing this plan** — none is an outcome moment
   (no product of o with c or r, no estimator, no K):
   * sessions: A1 239, B 117, A2 123, C 90; 9 sessions fall between 2026-04-06 (the trading-week
     reform) and 2026-04-19; the 40 sessions before 2026-04-06 run 2026-01-28 to 2026-04-05;
     the first 40 after the band reform run 2026-04-20 to 2026-06-17;
   * opens equal to the previous close ("stale"): 10.7% (A1), 3.0% (B), 11.8% (A2), 17.4% (C);
   * opening-return zones, share of defined opens: at the ±2% band 28.1% (A1), 22.8% (B), 22.5%
     (A2); in C, 2.9% within 0.1 pp of ±2%, 15.5% between ±2% and ±5%, 8.2% at the ±5% band.
     (A −5% move is −0.0513 in logs, which exceeds ln 1.05 = 0.0488 in absolute value; the band
     binds at ±5% in simple returns, and every zone below is defined on simple returns.)
   * treatment intensity (H8): 254 securities have at least 60 defined opens in A1 ∪ B; their
     share of band-pinned opens has median 0.260, terciles at 0.229 and 0.294, range 0.085–0.627;
     247 of them also trade in A2 and in C.
4. **One prior real-data result touching H11**: the adopted Yang–Zhang ratio, 1.280 on the
   STANDARD-DEVIATION scale (1.638 on the variance scale), against the horizon-matched
   close-to-close variance (`table48`). Its split by regime has not been computed.

## Notation and the measurement model

For security *i*, session *t*: previous close PC (the adopted corporate-action-adjusted
`prev_close_adj`, NaN across a session gap), open O, close C, VWAP V.
`o = ln(O/PC)` (overnight), `c = ln(C/O)` (intraday), `r = o + c = ln(C/PC)` (close to close),
`a = ln(V/O)`, `q = ln(C/V) = c − a`. Opening return in simple terms `g = O/PC − 1`.

Maintained model (no censoring): `O = O* + η`, `C = C* + ε` (logs), with `O*`, `C*` efficient
prices, `η`, `ε` transient errors independent of efficient returns and across days. Then the open's
error cancels from `r`, and

    b ≡ E[o r] / E[o²] = 1 + E[o c]/E[o²],      E[o c] = −Var(η),

so **b < 1 when the open overreacts** (transient error) and **b > 1 when it underreacts** (a band
that censors the overnight move leaves the remainder to be traded through during the session).
`b` is the unbiasedness coefficient of the price-discovery literature (Biais, Hillion & Spatt,
1999; Barclay & Hendershott, 2003), estimated without intercept as a ratio of sums (daily mean
returns are negligible against daily variances; the opening band bounds `o`, so no tail
dominates). Stale opens (`o = 0`) contribute nothing to either sum, so `b` is invariant to them.

## Specification (fixed)

| Item | Choice |
|---|---|
| Sample | `data/processed/equity_sample.csv` via `load_sample(ROOT, "equity")`; rows with `o` and `c` defined |
| Regimes | M14's: A1 2024-03-04–2025-03-19; B 2025-03-20–2025-09-21; A2 2025-09-23–2026-04-19; C 2026-04-20–2026-08-26; 2025-09-18 excluded |
| Pinned open | `|g| ≥ band − 0.001` (simple return), band 0.02 before 2026-04-20 and 0.05 from it |
| Zones | interior `0 < |g| < 0.019`; old-band zone `0.019 ≤ |g| < 0.049` (C only); new-band pinned `|g| ≥ 0.049` (C only) |
| Moments | unweighted ratios of sums over stock-days |
| Inference | joint bootstrap of M14 (`scripts/34::joint_bootstrap`): stationary block bootstrap over dates (mean block 21) × i.i.d. securities, 499 replicates, **seed 20261007**, 95% percentile intervals, replicates undefined for a statistic dropped as in M14 |
| Noise-robust kernel | `K = c² + o c + c o_next`, `o_next` only when the next session is consecutive and in the same regime (as `table88`) |

## Hypotheses and decision rules (binding)

**H7 — a break at the band reform, not a drift.** `Δb = b(post) − b(pre)`, post = the 40 sessions
from 2026-04-20, pre = the 40 sessions ending 2026-04-05 (the 9 sessions between the two April
reforms belong to neither window and are reported as their own bin). Placebo: the same
construction (40-session windows separated by a 9-session gap) at every 5th session of the
pre-reform calendar (sessions before 2026-04-06, 2025-09-18 excluded) at which both windows fit.
Predicted: Δb < 0 (the open overreacts more once the band no longer binds).
*Sharp break* if the 95% interval of Δb lies below zero **and** Δb is below every placebo Δb;
*break, not unique* if only the first holds; *not detected* otherwise.

**H8 — dose-response across securities.** Securities with ≥ 60 defined opens in A1 ∪ B are split
into terciles of their A1 ∪ B pinned share (predetermined; measured on data that precede both
outcome windows). `DiD = [b(T3, C) − b(T3, A2)] − [b(T1, C) − b(T1, A2)]`. Predicted < 0: the
reform moves the open most where the band bound most. Placebo DiD with the same terciles: the
second half minus the first half of A2 (split at its median date; the 9 inter-reform sessions
excluded). *Confirmed* if the DiD interval lies below zero **and** the placebo interval contains
zero; *confounded* if both lie below zero; *reversed* if the DiD interval lies above zero;
otherwise *not detected*.

**H9 — the mechanism: censoring turned into overshoot.**
(a) Pinned opens in A2 underreact: *delayed price discovery at the band* if the interval of
`b(pinned, A2)` lies above one.
(b) Opens in the old-band zone in C overreact: *overshoot where the band used to bind* if the
interval of `b(zone, C)` lies below one.
Joint verdict: *trade-off* if (a) and (b) both hold; *censoring only* if (a) alone; *overshoot only*
if (b) alone; *neither* otherwise.
(c) Reported, with its reading fixed now: `b(interior, C) − b(interior, A2)`. An interval
containing zero says the reform's effect is concentrated where the band bound; an interval below
zero says auction behaviour changed more broadly.

**H10 — consequence for estimator evaluation (point estimates known; not a test).** By regime,
E[X]/E[OC] and E[X]/E[K] for X ∈ {P, GK, RS, AddRS}, and the A2 → C changes with intervals.
Reported as an *inversion* if the interval of Δ(E[P]/E[OC]) lies below zero and that of
Δ(E[P]/E[K]) above zero.

**H11 — the Yang–Zhang excess is the opening covariance.** Within any window,
`YZ − Var(r) = (1 − k)[mean(RS) − Var(c)] − 2 Cov(o, c)` exactly (sample moments, ddof = 1;
k = 0.34/(1.34 + 22/20)). For 21-session windows lying wholly inside one regime, report by
regime Σ YZ / Σ Var₂₁(r) (variance scale) and the share of Σ(YZ − Var₂₁(r)) carried by the
covariance term. Predicted: the ratio is higher in C than in A2. *Confirmed* if the interval of
ratio(C) − ratio(A2) lies above zero.

**H12 — external contrast (reported, no decision).** NIFTY 50, 2010–2026, previous close = prior
row, with and without 2012-10-05: b, E[o c]/E[P], 1 − E[K]/E[OC], and the H11 decomposition.
An index open aggregates constituents that may not yet have traded, which biases b upward for a
reason unrelated to auction overreaction; no prediction is made.

## Reported whatever they show

b and E[o c]/E[P] by calendar month (figure, with intervals and the four rule dates marked);
the inter-reform bin; b by zone and regime (including the new-band pinned opens in C and the
A1 pinned opens); b by security-level liquidity quintile × regime; the timing split
E[o a]/E[o²] and E[o q]/E[o²] (how much of the opening error is undone before and after the
volume-weighted centre of the session); stale-open shares; H8 under halves instead of terciles
and under intensity measured in A2; H7–H9 excluding the first 5 sessions after the reform.

## Validation where the truth is known (before the data are touched)

`nepsevol.estimators.microsim` gains a mid-sample rule switch (band, limit and auction-error
scale change on one day). `tests/test_opening_price.py` must show, on simulated panels: b = 1
within sampling error with no frictions; b < 1 with an uncensored transient opening error and
`1 − b` close to its true value Var(η)/E[o²]; b > 1 for band-pinned opens under censoring; the H7
statistic negative for a switch that widens the band and adds opening error, and its placebo
distribution centred on zero without a switch; the H8 DiD negative under the switch and its
placebo containing zero; and the H11 identity exact to floating-point precision.

## Wording rules (binding)

1. The unbiasedness regression, the noise kernel and the delayed-price-discovery/overreaction
   dichotomy are not new (Biais, Hillion & Spatt 1999; Barclay & Hendershott 2003; Zhou 1996;
   Kim & Rhee 1997; Amihud & Mendelson 1987; Stoll & Whaley 1990). What is claimed is the
   evidence: a pre-open band reform as a natural experiment on what the open measures, and its
   consequences for daily-bar volatility estimators and their benchmark.
2. No "first". The reform changed the band, the daily limit and the circuit breaker on one date,
   two weeks after a trading-week reform, and C contains 90 sessions; results are evidence about
   that rule package and that window, and are written so.
3. "Transient opening error" or "overreaction", never "noise" without qualification, when the
   censoring channel could also be at work; "unbiasedness coefficient", never "efficiency".
