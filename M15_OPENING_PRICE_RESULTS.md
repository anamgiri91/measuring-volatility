# M15 — results, the frozen decisions, and every change made after seeing them

This file reports what `scripts/37_opening_price.py` found when it executed the plan frozen in
`M15_OPENING_PRICE_ANALYSIS_PLAN.md` (commit `6b71646`, pushed before the script existed; the
simulation checks of its statistics followed in `f2699aa`), applies the plan's decision rules
exactly as written, and records — separately and by name — every change made after the first
results were seen. Numbers are read from the frozen tables named in brackets; none is typed from
memory. The central statistic is the unbiasedness coefficient of the open for the close,
`b = E[o r]/E[o²]`: b = 1 when the open anticipates the close, b < 1 when the session undoes part
of the opening move, b > 1 when it completes a move the open only began.

## The verdicts, applied mechanically (`table96_m15_decisions.csv`)

| Hypothesis | Statistic | Estimate [95% interval] | Verdict |
|---|---|---|---|
| H7 | jump in b, 40 sessions from 2026-04-20 minus the 40 ending 2026-04-05 | −0.333 [−0.627, −0.067]; 0 of 77 placebo jumps at or below it (placebo range −0.176 to +0.289) | **sharp break** |
| H8 | DiD in b, top minus bottom tercile of pre-reform band exposure, C − A2 | −0.019 [−0.173, +0.104]; placebo −0.011 [−0.242, +0.179] | **not detected** |
| H9(a) | b, band-pinned opens in A2 (predicted > 1) | 0.447 [0.274, 0.668] | **not detected** — the interval lies *below* one |
| H9(b) | b, opens in the old-band zone in C (predicted < 1) | 0.174 [0.112, 0.249] | **overshoot where the band used to bind** |
| H9 | joint verdict | | **overshoot only** |
| H9(c) (reported) | b, interior opens, C − A2 | −0.011 [−0.192, +0.156] | concentrated where the band bound |
| H10 (consequence) | change A2 → C in E[P]/E[OC] and in E[P]/E[K] | −0.097 [−0.224, +0.024]; +0.818 [+0.362, +1.413] | **no inversion established** |
| H11 | Σ YZ / Σ Var₂₁(r), C − A2 (predicted > 0) | +1.132 [+0.689, +1.727] | **confirmed** |
| H12 (reported) | NIFTY 50, b and the Yang–Zhang ratio | b 0.929 [0.854, 0.999]; YZ/Var₂₁(r) 1.015 [0.940, 1.158] (0.960 [0.922, 1.006] excl. 2012-10-05) | reported, no decision |

Two of the plan's predictions failed outright and are reported as such: band-pinned opens did not
underreact (H9(a)), and the reform's effect did not scale with how often the old band bound a
security (H8). What the analysis does establish is stated next.

## What the frozen analysis establishes

1. **NEPSE's opening price is mostly transient.** The session undoes between two-thirds and
   nine-tenths of the overnight move: b is 0.307 [0.247, 0.376] (A1), 0.216 [0.128, 0.281] (B),
   0.356 [0.252, 0.512] (A2) and 0.130 [0.082, 0.196] (C) (`table89`). On NIFTY 50, where the
   open comes from a call auction among liquid constituents, b is 0.929 [0.854, 0.999]
   (`table95`). The reversal is not a thin-stock phenomenon: b is below one in every security-level
   liquidity quintile in every regime — between 0.12 and 0.45 under the ±2% band and between 0.12
   and 0.17 after the reform. It is
   fast: of the 69% of the opening move that the session undoes in A1, 58 points are undone before
   the session's volume-weighted centre (E[o a]/E[o²] = −0.575) and 12 after (E[o q]/E[o²] =
   −0.118); in C the split is 79 and 8.
2. **The band widening produced a sharp, unique break (H7).** b fell from 0.436 in the 40
   sessions before the trading-week reform to 0.102 in the 40 after the band reform; the nine
   sessions between the two reforms sit at 0.454, with the pre-reform window, so the break belongs
   to 20 April and not to the change of trading week. No placebo split in the two pre-reform years
   — including those straddling both closing-rule changes and the September 2025 halt — comes
   within 0.15 of the reform's jump (`table90`, `table90b`). The jump is the same when the post
   window starts at the sixth session (−0.336 [−0.625, −0.071]), and the monthly series stays at
   its new level through August (`table91`, `fig23`): E[o c]/E[P] runs from −0.08 to −0.28 in
   every full month before the reform (March 2024 to March 2026) and from −0.48 to −0.63 in every
   full month after it (May to August 2026).
3. **The narrow band capped transient opening moves; it did not delay price discovery (H9).**
   The price-limit literature asks whether a binding limit delays the incorporation of
   information (continuation, b > 1) or prevents an overreaction (reversal, b < 1). Under the ±2%
   band, opens pinned at the band were reversed like every other open: b = 0.349 (A1), 0.242 (B),
   0.447 (A2), all intervals below one. After the reform, the opens the old band would have pinned
   (between ±1.9% and ±4.9%) retain 0.174 of their move and those pinned at the new ±5% band
   0.057 [0.008, 0.121], while opens inside ±1.9% are unchanged (0.249 against 0.261). The
   widening let the opening price travel further from where the session would close, and
   the session took the extra distance back.
4. **Yang–Zhang's overstatement is the opening covariance it assumes away (H11).** Over every
   21-session window the package's Yang–Zhang is 1.637 times the matched close-to-close variance
   on the variance scale (`table94`) — the manuscript's adopted 1.280 on the standard-deviation
   scale, reproduced here on the same 135,899 windows. By the exact identity
   `YZ − Var(r) = (1 − k)[mean RS − Var(c)] − 2 Cov(o, c)`, 75.6% [66.2, 86.9] of that excess is
   −2 Cov(o, c), the overnight–intraday covariance Yang and Zhang assume to be zero; the rest is
   Rogers–Satchell's own excess over Var(c). The ratio is 1.446, 1.858 and 1.551 under the ±2%
   band and 2.682 after the widening, a rise of 1.132 [0.689, 1.727]. On NIFTY 50, where the open
   is nearly unbiased, Yang–Zhang matches close-to-close (0.960 [0.922, 1.006] excluding the 2012
   flash-crash session).
5. **Every estimator that reads the open inherits its error, and a ratio to the open-to-close
   proxy cannot see it (H10).** The open-to-close proxy, Garman–Klass, Rogers–Satchell and the
   VWAP estimators read the open directly; Parkinson reads it whenever the open is the session's
   high or low, which a non-stale NEPSE open is on 36% of sessions in A1 and 51% in C (post hoc X3,
   `table97`). Close-to-close does not read the open at all. Against the open-to-close proxy,
   Parkinson moves from 0.977 to 0.880 across the reform, a change whose interval contains zero
   (−0.097 [−0.224, +0.024]); against the noise-robust kernel K it moves from 1.191 to 2.009, a
   rise of 0.818 [0.362, 1.413] (`table93`). The conventional evaluation reports the estimator
   roughly where it was; the kernel, under its maintained assumption, reports it doubling its
   distance from efficient within-session variance. On NIFTY, E[P]/E[K] and E[P]/E[OC] coincide
   (0.921 and 0.920 excluding 2012-10-05), as they should where the open carries no transient
   error.

## What the frozen analysis does not establish

* **No dose-response (H8).** Before the reform, b was the same in all three terciles of band
  exposure (0.318, 0.323, 0.323), and all three fell by similar amounts (to 0.119, 0.083, 0.105).
  This is what point 3 implies — if pinned opens were not censored information, how often a
  security was pinned predicts nothing — but it removes the cross-sectional leg of the causal
  argument. The reform's timing (H7) carries the identification alone.
* **No delayed price discovery at the band (H9(a)).** The plan predicted b > 1 for pinned opens;
  the interval lies below one. The prediction came from a censoring model that the data reject.
* **No established inversion (H10).** The conventional ratio's change has an interval containing
  zero, so the rule's first leg fails; the kernel's rise is large and excludes zero.
* **The kernel's shares are model-dependent, in both directions.** K is unbiased for efficient
  within-session variance only if the opening error is independent of overnight news. A band that
  censors the open biases K upward (M14's E2 noted only this); an open that overreacts *in
  proportion* to the news biases it downward, by E[e_o η]. M14's description of its E2 shares as
  lower bounds was therefore too strong (correction `M-007` below). The post hoc bound X4 replaces
  it with one that holds whatever that correlation: the open's error alone accounts for at least
  5.0% [3.8, 6.5] (A1), 7.8% (B), 5.4% (A2) and 17.2% [13.9, 19.8] (C) of the open-to-close
  benchmark, against 15.6%, 23.0%, 17.6% and 48.0% if the error is independent of news
  (`table97`). The model-free facts — b, E[o c] and the Yang–Zhang identity — need neither.
* **Causality reaches the rule package, not the band alone.** The reform changed the pre-open
  band, the daily limit and the circuit breaker on one date, two weeks after the trading-week
  reform, and C holds 90 sessions. The share of opens equal to the previous close also rose, from
  11.8% (A2) to 17.4% (C); b is invariant to such opens by construction, but the other moments
  are not.
* **The mechanism inside the auction.** Without pre-open order-book or auction-volume data the
  analysis cannot say whether the transient error is retail overreaction, a thin pre-open match
  setting the print, or deliberate placement of orders at the band.

## Not in the plan: post hoc, exploratory (`scripts/38_opening_price_exploratory.py`, `table97`)

Written after the frozen results were seen; none changes a frozen verdict.

* **X1, the central statistic by two other routes.** b as an OLS slope with an intercept: 0.296,
  0.218, 0.359, 0.123; with the exchange's published (unadjusted) previous close: 0.328, 0.211,
  0.357, 0.132 (A1, B, A2, C).
* **X2, what follows a band-pinned open.** Under the ±2% band, a +2% open is followed by an
  intraday return of −1.18% (A1), −1.50% (B) and −0.75% (A2). After the reform, an open pinned at
  +5% (mean +4.86%) is followed by −4.85%: the close retains 0.4% [−8.0, 12.0] of the opening move
  and ends, on average, where the previous session closed. A −5% open (mean −5.11%) is followed by
  +4.57%.
* **X3, the open as the session's extreme**: 36.4%, 38.9%, 42.2% and 51.5% of non-stale opens.
* **X4, the bound above.** Derived in the script's docstring.

## Changes made after the first results were seen

| ID | Change | Effect |
|---|---|---|
| M-007 | M14's E2 (`M14_CALIBRATION_RESULTS.md`, `scripts/36`) called the kernel-based transient shares lower bounds, considering only band censoring. An opening error that overreacts in proportion to news biases the kernel the other way. The claim is withdrawn and replaced by the X4 bound, which assumes nothing about that correlation. | The E2 figures stand as point estimates under independence; their description changes. No verdict depends on them. |
| M-008 | H12 planned to report the covariance *share* of the Yang–Zhang gap on NIFTY. The gap there is near zero, so the share is a ratio of two near-zero sums (2.7 [−29.0, 7.0]). The same decomposition is added scaled by Var₂₁(r): −2 Cov(o, c) = 0.041 [0.003, 0.090] and the RS term −0.026 [−0.091, 0.106] of Var₂₁(r). | Presentation only; H12 carries no decision. |
| M-009 | The figure's rule-date labels collided with the series and with each other; they became numbered tags with a key. | Layout only. |
