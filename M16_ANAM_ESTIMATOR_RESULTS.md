# M16 — results: Anam's estimator on held-out data

This file reports what `scripts/40_anam_holdout.py` found when it executed the plan frozen in
`M16_ANAM_ESTIMATOR_PLAN.md` (commit `dc41f1e`, pushed together with the estimator, its tests and the
development evidence before the holdout script existed), applies the plan's decision rules exactly as
written, and records separately everything examined after the verdicts were seen. Numbers are read
from the tables named in brackets. QLIKE is the forecast loss (lower is better); "t" is the
Newey–West statistic of Anam's loss minus the rival's (negative favours Anam).

## The verdicts, applied mechanically (`table105_anam_holdout_decisions.csv`)

| Rule | Market | Verdict | Evidence |
|---|---|---|---|
| H1 | NEPSE (A2 ∪ C) | **does not hold** | 5 sessions: Anam 0.6637 vs close-to-close 0.6478 (t = +1.19, no difference); beats Parkinson 0.6764 (t = −3.97) |
| H2 | NEPSE | **does not hold** | calibrated level 1.011 (A2) but 1.195 (C); overnight² + Parkinson 1.493 and 2.761; Yang–Zhang daily form 1.583 and 2.848 |
| H3 | NEPSE | **does not hold** | change A2 → C: Anam +0.184; Yang–Zhang window form +1.170 |
| H4 | NIFTY 50 (2018-04-05 to 2026-06-12) | **holds** | 5 sessions: Anam 0.4314 beats close-to-close 0.4725 (t = −3.07) |
| H5 | S&P 500 (2009-01-05 to 2018-12-31) | **holds** | 5 sessions: Anam 0.4648 beats close-to-close 0.5219 (t = −6.39) |
| Best in market | NEPSE, NIFTY 50, S&P 500 | **yes, in all three** | no rival beats Anam at 5 or 21 sessions on the plan's test span |

Three of the plan's predictions failed, all in NEPSE and all for one reason, set out below: the
20 April 2026 band reform changed the relation between the range and close-to-close variance faster
than the estimator's 60-date calibration could follow. In regime C taken alone, close-to-close beats
Anam at both horizons (t = +3.51 at 5 sessions, +2.47 at 21) — the only rival that beats it anywhere
(`table101`).

## What the holdout establishes

1. **No range-based estimator beats Anam in any market, horizon or regime.** Across NEPSE (A2 ∪ C,
   A2, C), NIFTY 50 and the S&P 500 at 5 and 21 sessions, the only significant loss is to
   close-to-close in regime C. On the NEPSE holdout Anam beats Parkinson, Garman–Klass,
   Rogers–Satchell, overnight² + Parkinson, overnight² + Garman–Klass and the Yang–Zhang daily form
   at both horizons — 12 of 14 rival comparisons, the other two being close-to-close (`table105`).
   In regime C, where every estimator that reads the high, the low or the open deteriorates, Anam is
   the least affected by a wide margin (against Parkinson, t = −8.19 at 5 sessions and −8.44 at 21).
2. **NIFTY 50: first of nine at both horizons** (5 sessions 0.4314, 21 sessions 0.4131). At 5
   sessions it beats close-to-close (t = −3.07), the Yang–Zhang daily form (t = −3.99) and
   overnight² + Parkinson (t = −3.19). The index's open is nearly clean (b̂ median 0.953 over the test
   half), so the estimator runs close to its b = 1 form and still adds the extension to the
   effective open and the pooled-in-time calibration.
3. **S&P 500: level with the best range estimators, ahead of close-to-close.** b̂ is 1 over the test
   half, where the estimator coincides exactly with overnight² + Parkinson (both 0.4648 at 5
   sessions). Garman–Klass (0.4575) and Parkinson (0.4631) are ahead at 5 sessions and Parkinson at 21
   (0.3858 against 0.3919), none significantly (t = +1.13, +0.44, +1.82). It beats close-to-close at
   5 sessions (t = −6.39).
4. **The level is right wherever the rules were stable.** The calibrated 21-session variance is
   1.011, 1.011 and 1.009 times close-to-close variance in NEPSE A2, NIFTY 50 and the S&P 500
   (`table102`). The classical estimators are biased in BOTH directions: the Yang–Zhang window form
   is 1.534 (A2) and 2.704 (C) in NEPSE but 0.646 on the S&P 500, and Parkinson 1.155 and 1.669 in
   NEPSE but 0.606 and 0.660 on the two indices. The S&P 500's open under-reacts — its b is at the
   clip of one, and 39.8% of its opens equal the previous close over the full sample — so the
   overnight–intraday covariance that Yang–Zhang omits is positive there, the mirror image of NEPSE.

## What the holdout does not establish

* **H1 — Anam does not beat close-to-close on the NEPSE holdout.** Close-to-close has the lower loss
  on A2 ∪ C at both horizons, insignificantly (t = +1.19, +0.37); the difference comes from regime C.
  In A2 alone, Anam has the lower loss (0.5991 against 0.6162 at 5 sessions; t = −1.15, not
  significant).
* **H2, H3 — the level drifts after a sudden rule change.** In regime C the calibrated level is
  1.195, a change of +0.184 from A2. The estimator calibrates on the last 60 pooled dates; at the
  reform the ratio of close-to-close variance to the kernel fell abruptly, and regime C holds only 90
  sessions, so most of it ran under a partly pre-reform calibration (post hoc Y2 below).
* **Regime C belongs to close-to-close.** After the reform close-to-close is significantly better
  than Anam and than every range estimator. This is the paper's own recommendation — treat a change
  in opening rules as a break and fall back on close-to-close returns — and the estimator does not
  overturn it.
* **Instrumented noise (T4, reported only).** On the NEPSE holdout Anam's efficiency lower bound
  against close-to-close is 2.895, below Parkinson (3.142) and Garman–Klass (3.010), above the
  Yang–Zhang daily form (2.103) and overnight² + Parkinson (2.111); every range estimator's slope is
  above one (Anam 1.227, Parkinson 1.237), the regime C over-response (`table103`).
* **Implied variance (T5, reported only).** All estimators correlate similarly with VIX² and India
  VIX² (NIFTY 50: 0.824 to 0.843; S&P 500: 0.720 to 0.742); Anam's 0.841 and 0.741 are at the top of
  that narrow band (`table104`).

## Not in the plan: post hoc, exploratory (`scripts/41_anam_posthoc.py`, `table106`, `table106b`)

Written after the verdicts were seen; none changes a verdict.

* **Y2, the trajectory.** In the 60 sessions before the reform, the pooled ratio of mean r² to the
  mean kernel ran between 0.763 and 1.174; in the 90 after, between 0.526 and 0.827. The applied
  60-date calibration moved from 0.934 to 0.664 over five blocks of ten sessions, and b̂ fell from
  0.384 to 0.126. The reform made the high–low range itself a worse measure of volatility: an open
  that may now travel ±5% before the session reverses it sets the day's high or low more often (51.5%
  of non-stale opens in C, against 36.4–42.2% before; M15's post hoc X3).
* **Y1, faster or reset calibration.** With the calibration pooled over 10 dates instead of 60, or
  reset at the known rule change, Anam's regime C loss falls from 0.7532 to 0.7063 and 0.7128 at 5
  sessions and from 0.4529 to 0.4001 and 0.4012 at 21 (the 60-date figures are recomputed on the
  post hoc comparison's own common sample; the frozen `table101` has 0.7533 and 0.4529), and the gap
  to close-to-close is no longer
  significant (t = +1.16 and +1.17; +1.18 and +1.31). Close-to-close remains ahead. Whether a faster
  or rule-aware calibration should replace the frozen one can only be settled on NEPSE data after
  August 2026, which this package does not have.

## Bottom line

Anam's estimator does what it was designed to do against the classical daily-bar estimators: in a
frontier market whose open overreacts, in a clean index and in an index whose open under-reacts, no
range-based estimator beats it, and its level is right where the rules are stable while theirs is
off by as much as −44% (Rogers–Satchell, S&P 500) and +185% (the Yang–Zhang daily form, NEPSE C). It is not a better forecaster than plain close-to-close in NEPSE immediately
after a sudden market-design change, and its 60-date calibration needs most of a 90-session regime to
adjust. Those failures are reported as the plan's verdicts, not explained away.

## Implementation details fixed before the holdout ran

| ID | Detail | Effect |
|---|---|---|
| `M-015` | Two details the plan left implicit were fixed in `scripts/40` before it was run: level ratios by regime use only 21-session windows lying wholly inside the regime (or the index's test half); H3's "the Yang–Zhang window form's ratio changes by more" is read as "by more than 0.10". | Neither affects a forecast verdict; under the alternative reading of H3 (Yang–Zhang changes by more than Anam) H3 still fails, because Anam's own change exceeds 0.10. |
