# Post hoc recheck of the claims made for Anam's estimator

**Written on 2026-10-08, after every verdict of plans M16, M17 and M18 was known.** The author asked
whether anything had been overclaimed or overassumed, and for every result to be rechecked. Nothing
here was pre-registered, and no frozen verdict changes. The corrections it led to are registered as
`M-020` to `M-025` in `AUDIT-REGISTER.md` and applied to the manuscript by
`paper/apply_round16_revisions.py`. The new evidence comes from `scripts/44_anam_recheck.py`
(package tables 117-120, manuscript Tables 37 and 38).

## 1. Do the results reproduce?

Yes. Scripts 39 to 43 and 25 were rerun from the committed code and inputs, and every committed table
came back byte for byte. Before varying anything, script 44 reproduces the frozen Newey-West t of every
comparison it reports (it asserts agreement to 10⁻⁶), so each variant below differs from the frozen
analysis in one choice only.

## 2. What was overstated, and how it now reads

| Claim (round 15) | Where | What the evidence shows | Now | Register |
|---|---|---|---|---|
| "Every analysis follows a plan frozen before testing" | abstract, README | Sections 6.1-6.5 had no frozen plan; only M7, M14, M15 and M16-M18 did | "Later analyses follow plans frozen before testing" | `M-020` |
| Designed on NEPSE's first two regimes "alone"; frozen "before any later observation was read" | introduction, 6.8, Table 33 | M16's own disclosure: M15's findings on the whole NEPSE sample, including the holdout, informed the design, and NIFTY 50's b was known | disclosed; "before the estimator was computed on any holdout sample" | `M-020` |
| "Pre-registered test in Morocco" | abstract, cover letter | the plans are timestamped only by the package's own history, which was rewritten once (`M-017`); there is no external registry | "prespecified", "fixed in advance"; Section 9 says how the plans are timestamped | `M-020` |
| "No classical range estimator beats it" | abstract, introduction, 6.8, conclusion, README, letters | true as "no significantly lower loss". On the S&P 500 b̂ is capped at one in every test session, so the estimator is exactly overnight² + Parkinson, and four classical estimators had nominally lower loss | "significantly lower loss"; the S&P 500 coincidence stated | `M-021` |
| Wins over close-to-close on the indices credited to the estimator | 6.8, Discussion | three classical range estimators also beat close-to-close on the NIFTY 50, and five on the S&P 500 | stated | `M-021` |
| "Lowest loss of all nine estimators in Bangladesh, Vietnam and Morocco" | Discussion | five sessions only; at 21 sessions in Vietnam close-to-close is lower (0.2737 against 0.2770) | "lowest five-session loss" | `M-021` |
| Ten-date calibration "closes" the regime-C gap | 6.8 | best of four windows and a reset tried post hoc; close-to-close keeps the lower loss under every variant | the full menu stated | `M-021` |
| Beats close-to-close "in Morocco (t = −2.06)" | 6.8, README | comes from the 4% band regime of 2020-21 (t = −5.95); fragile (Section 3) | fragility stated | `M-021` |
| "Does not beat close-to-close … in Nepal, Bangladesh or Vietnam" | abstract, introduction | it does in the repaired 2009-2021 Dhaka panel (t = −6.17) | "the recent Dhaka panel" | `M-021` |
| Level within 1.1%, against classical formulas that "miss by tens of percent" | abstract, introduction, 6.8, conclusion, README, letters | compares a calibrated estimator with raw ones; calibrated the same way, every classical range estimator is within 2.2% (Section 4) | "the calibration's doing" | `M-022` |
| "A market-design rule determines what daily bars measure" | abstract, JEF fit statement | one natural experiment in a rule package; the dose-response was not detected | "a market-design rule change altered" | `M-023` |
| "Validated out of sample" | abstract, JFEC fit statement, Section 9 | key predictions failed in Nepal, Bangladesh and Vietnam | "tested" | `M-023` |
| "What is added is that the open's weight is measured from the data" | 6.8 | Hansen and Lunde (2005) also estimate the overnight weight from data | narrowed to what is specific: the weight is the open's unbiasedness coefficient, from daily bars alone, and it also moves the range's anchor and sets the close-to-close blend | `M-023` |
| "The data say that trust should be measured" | Discussion | where b was well below one, fixing it at zero beat using the measured value | "checked rather than assumed" | `M-023` |
| "Markets whose open overreacts" | 6.8, Discussion, README | overreaction is shown for NEPSE only (Section 6.7); elsewhere only b < 1 is measured, and a bid-ask bounce in the first trade lowers b too | "unreliable" | `M-023` |
| b of 0.33-0.64 (new markets) beside 0.130-0.356 (NEPSE) | 6.8, Discussion | two different statistics (trailing 60-date medians against whole-regime pooled b) | both pooled over the whole span: 0.343-0.653 | `M-023` |
| "Where the open is close to efficient" (both indices) | 6.8, README | the S&P 500's raw b is 2.21: its index open lags | "whose opens do not overreact" | `M-023` |
| "The session undoes two-thirds or more of the overnight move" | submission set's short abstract | the range is 64-87% | "most of the overnight move" | `M-023` |
| "Four frontier markets" | title, abstract | undefined | defined in 6.8: MSCI's classification for Bangladesh, Vietnam and Morocco over the test periods; FTSE Russell's reclassification of Vietnam announced for September 2026; Nepal is outside the providers' indices and frontier in the descriptive sense | `M-023` |
| "Where one daily estimator must serve, use Anam's estimator" | protocol for Nepal (Section 7) | in NEPSE's holdout close-to-close had the lower loss, and after the reform it beat both forms | close-to-close stays NEPSE's primary measure | `M-024` |

## 3. How robust are the verdicts? (Table 37)

Each plan rule's frozen t is shown beside six variants: Newey-West lags of two and four times the
horizon, non-overlapping forecast origins, an MSE loss on the same forecasts, and each half of the
test span. Table 37 also gives the Holm-adjusted one-sided p across all three plans.

* **Against the classical range estimators: robust.** Under QLIKE, no classical range estimator has
  significantly lower loss than the estimator in any sample, at either horizon, under any lag choice
  or with non-overlapping origins. Every F2-type win over Parkinson survives every variant except one
  half-sample (NEPSE's first half). The exception is the loss function: under MSE, the three classical
  estimators with a full overnight term beat the estimator in Vietnam at 21 sessions (t from −9.19 to
  −1.98).
* **Against close-to-close: loss-dependent.** Every frozen win survives lags of two and four times the
  horizon and a Holm correction across the plans, except Morocco's F1. Under MSE, the ranking against
  close-to-close changes in both directions:
  * close-to-close beats both forms in Vietnam (t = +14.48 and +6.89 at five sessions);
  * both forms beat close-to-close in NEPSE's holdout (t = −3.19 and −3.56) and on the S&P 500;
  * close-to-close's advantage after NEPSE's reform is no longer significant (t = −1.19).

  The plans fixed QLIKE in advance, and the frozen verdicts stand on it. But no claim about
  close-to-close should be read as loss-free.
* **The fragile ones.**
  * *Morocco F1* (full form beats close-to-close, t = −2.06). It fails under:
    * lags of twice the horizon (−1.85);
    * non-overlapping origins (−1.10);
    * MSE (+1.12);
    * the second half (−0.10);
    * Holm across the plans (p = 0.079).

    By band regime, it comes from the 4% regime of March 2020 to October 2021, which spans the
    pandemic shock (t = −5.95). The other three regimes show no difference (−0.77 to +0.83), and in
    the 6% regime close-to-close beats the full form at 21 sessions (t = +2.99).
  * *NIFTY 50 H4.* It fails with non-overlapping origins (−1.90) and under MSE (−1.38).
  * *M18 V1* (open-free form beats close-to-close, −4.53). It survives the lags and non-overlapping
    origins (−3.07), but not MSE (−1.22) or the second half (−1.84). Its sign is negative in every
    Moroccan band regime.
  * *M18 V2* (open-free form beats the full form, −4.75). It survives every variant.

## 4. The level (Table 38)

The frozen level table (Table 35) compares Anam's calibrated estimator with raw classical estimators.
Table 38 gives every estimator the same pooled calibration:

* **With the calibration ending at the window's last session**, as frozen, every classical range
  estimator is within 2.2% of close-to-close variance outside regime C (Anam: 1.1%).
* **With the calibration ending before the window starts**, so that the level is out of sample:
  * Anam is within 2.2% (NEPSE A2: 0.978);
  * the classical estimators are within 4.8% (Parkinson on the NIFTY 50: 0.952).
* **In regime C**, where every calibration lags the rule change, the kernel does matter. Anam is at
  1.195 and the open-free form at 1.190, against 1.241 to 1.339 for the classical estimators.

So the level hypotheses of the plans (M16 H2, M17-M18 F3) were weak tests. They are near-mechanical
for any calibrated estimator in a stable span. Their frozen verdicts stand as recorded.

## 5. The data assumptions (table 120)

| Assumption | Check | Result |
|---|---|---|
| Dhaka 2009-2021: day and month exchanged when the day is 12 or less | repaired dates against dates stamped correctly | indistinguishable: 8.7% and 8.5% of returns beyond 5%; b 0.53 and 0.52; mean r² and Parkinson equal to four decimals; no repaired date on a Friday or Saturday. In the unrepaired 2023-2026 panel the same split differs more (7.4% and 6.4%; b 0.40 and 0.33). |
| Morocco's daily limits, from press reports (10%, 4%, 6%, 10%) | 99.9th percentile of the absolute return in each regime, before the band screen | 10.5%, 4.2%, 6.2%, 10.5%: the moves stop at the reported limits |
| Vietnam: one pooled b and κ across HOSE, HNX and UPCoM | exchanges inferred from each ticker's 99.5th-percentile move (7%, 10%, 15% limits) | b of 0.49, 0.49 and 0.55; stock-day shares 38%, 34%, 26% |
| Dhaka's "close" is a closing price | official close against last trade in the mirror (190,246 stock-days with trades) | the close differs from the last trade on 18% of stock-days and always lies within [low, high] |
| Morocco is thin | share of test-span bars with high = low | 21% |
| Opens are informative | share of test-span bars whose open equals the previous close | 19% (Morocco) to 35% (Vietnam); 6.4% on the S&P 500, whose raw b is 2.21 |

## 6. What stands

* The tables reproduce, and every number the manuscript quotes matches them (the tests enforce it).
* Under the plans' loss, the classical range estimators never beat the estimator significantly, under
  any inference variant tried.
* Its open-free form had lower loss than the full form in every frontier comparison. In Morocco it
  beat close-to-close and the full form under a rule fixed in advance; the comparison with the full form
  is robust to every variant.
* The failed predictions remain failures:
  * NEPSE H1-H3;
  * F1 in both M17 primary panels;
  * G;
  * close-to-close after NEPSE's reform and in Vietnam at 21 sessions.

## 7. What remains open

* **Single confirmation.** The open-free form's prespecified test has been passed once, in one market.
  A further frozen test on later data would put it on two: NEPSE after 26 August 2026, or Dhaka after
  the mirror's last date.
* **No external timestamps.** The plans have none. A future plan lodged with an external registry
  before its data are read would remove the dependence on the package's own history.
* **Data provenance.** The Vietnamese and Moroccan files do not document their source. Morocco's
  prices and Dhaka's are not adjusted for corporate actions.
* **The loss function.** It decides some comparisons with close-to-close. A plan that fixes both QLIKE
  and MSE in advance, with a rule for disagreement, would settle that.
