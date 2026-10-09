# M20 — results: the corrected forecast evaluation

**Plan.** [`M20_CORRECTED_EVALUATION_PLAN.md`](M20_CORRECTED_EVALUATION_PLAN.md) was frozen and pushed in commit
`984dfbc` (9 October 2026), together with the shared evaluation module, the baselines and their tests, before
`scripts/47_corrected_evaluation.py` existed or any corrected loss was computed.

**Script and outputs.** `scripts/47_corrected_evaluation.py` writes `output/tables/table125`–`table132`. It was
run on all seven samples; this document reports what it found. Every number below is read from those tables.

**Deviations.** Every deviation from the plan is listed in the section "Deviations and implementation notes",
and the defects are registered as `M-028` and `M-033` in `AUDIT-REGISTER.md`.

The plan's decision rules are applied mechanically. Interpretations are labelled as such.

---

## Summary

1. **The frozen record does not survive intact.**
   * Rule A re-reads the 288 per-rival verdicts of plans M16–M18 under the corrected design; 47 change.
   * Most changes are frozen wins over classical range estimators that are no longer significant.
   * The headline sentence "no classical range estimator has significantly lower loss than Anam's estimator in
     any test sample" is false at the corrected step. Parkinson beats the full form in Dhaka 2023–2026 at 5
     sessions (t = +2.09). By the plan's rule it is replaced by the count: a classical range estimator beats the
     full form in **1 of 84** primary comparisons and the open-free form in **none**.
2. **Against close-to-close, the open-free form survives the corrections.**
   * The forecast here is close-to-close with the frozen φ-shrinkage dynamics.
   * At 5 sessions the open-free form beats it after Holm's adjustment in **6 of 7** samples, every sample
     except NEPSE.
   * The full form does so in **3 of 7**: Dhaka 2009–2021 and the two indices.
3. **Against strong return-only forecasts, the range adds detectable information in two samples only.**
   Rule B1 takes the best range-based forecast and the best return-only forecast (GARCH, GJR-GARCH, EWMA or a
   HAR on squared returns), each chosen on the training span. The range-based one beats the return-only one
   in Dhaka 2009–2021 and Morocco at both horizons. It loses in Dhaka 2023–2026 at both horizons and in
   NEPSE's post-reform regime. It is not distinguishable on NEPSE's holdout, the NIFTY 50, the S&P 500 and in
   Vietnam.
4. **The best single forecast combines the open-free kernel with HAR dynamics,** but the return-only
   GJR-GARCH forecast is just as hard to reject.
   * HAR-open-free (the calibrated open-free kernel with HAR dynamics, a forecast M20 specified in advance) has
     the lowest test loss in **10 of 14** primary cells and is in the 90% model confidence set in all 14.
   * GJR-GARCH, which uses returns only, is also in all 14 sets.
   * Plain close-to-close is in only **6**.
5. **What helps, from the ablations** (reported without decisions):
   * calibration;
   * the previous-close anchor (true range);
   * the 0.2 r² blend;
   * setting b to zero rather than estimating it;
   * HAR dynamics rather than φ-shrinkage.

   **What does not help:** the posterior-moment correction of the overnight term derived after the audit
   (Proposition 7(a)), which loses to the frozen full form in 6 of 14 cells.
6. **The open-free form loses its "lowest loss" wording.** The plan keeps it only where the form has the
   lowest loss of all 17 forecasts and is in the 90% set. It never has the lowest loss.

---

## Part A — the correction, one step at a time

**S0 reproduces the frozen tables exactly** in all seven samples, through the frozen function itself:

* QLIKE to 1e-9;
* every φ;
* every n.

The script asserts this before it corrects anything.

**The two forms against close-to-close, t at each step** (primary spans; negative favours the form):

| Sample | h | Form | S0 | S1 purge | S2 calendar target | S3 loss, zeros, grid, eligibility | S4 inference |
|---|---|---|---|---|---|---|---|
| NEPSE, A2 and C | 5 | full | +1.19 | +1.09 | +1.58 | +1.59 | +1.37 |
| | | open-free | +0.93 | +0.84 | +0.80 | +0.81 | +0.72 |
| | 21 | full | +0.37 | +0.40 | +0.40 | +0.40 | +0.39 |
| | | open-free | +0.21 | +0.24 | +0.24 | +0.24 | +0.25 |
| NIFTY 50 | 5 | full | −3.07 | −3.07 | −3.07 | −3.07 | −2.91 |
| | | open-free | −3.31 | −3.31 | −3.31 | −3.31 | −2.99 |
| S&P 500 | 5 | full | −6.39 | −6.39 | −6.39 | −6.39 | −6.08 |
| | | open-free | −7.10 | −7.10 | −7.10 | −7.10 | −6.65 |
| Dhaka 2023–2026 | 5 | full | −0.90 | −0.90 | −0.66 | +1.55 | +1.47 |
| | | open-free | −2.55 | −2.55 | −2.11 | −2.78 | −2.57 |
| | 21 | full | −2.22 | −1.82 | −2.50 | −0.06 | +0.17 |
| | | open-free | −2.30 | −2.30 | −2.93 | −1.43 | −1.30 |
| Vietnam 2007–2020 | 5 | full | +0.20 | +0.20 | −2.01 | −0.47 | −0.51 |
| | | open-free | −3.58 | −3.58 | −4.96 | −4.37 | −4.05 |
| | 21 | full | +7.27 | +7.27 | +0.63 | +0.74 | +1.51 |
| | | open-free | +1.60 | +1.60 | −0.91 | −0.85 | −0.70 |
| Dhaka 2009–2021 | 5 | full | −6.17 | −6.17 | −6.74 | −7.54 | −6.63 |
| | | open-free | −8.30 | −8.30 | −8.66 | −9.21 | −8.13 |
| | 21 | full | −3.02 | −3.16 | −3.08 | −2.68 | −2.46 |
| | | open-free | −3.91 | −4.78 | −3.84 | −3.36 | −3.02 |
| Morocco 2012–2026 | 5 | full | −2.06 | −2.06 | −2.37 | −0.11 | −0.62 |
| | | open-free | −4.53 | −4.53 | −4.17 | −2.65 | −2.71 |
| | 21 | full | −1.00 | −1.00 | −1.70 | −1.16 | −2.08 |
| | | open-free | −1.94 | −1.94 | −1.90 | −1.58 | −2.63 |

At 21 sessions the indices are unchanged by S1 to S3 (t −0.04 and −0.20 for the full form throughout).

**What each step did:**

* **S1, purging training origins whose outcome reaches the test span.** As the audit measured, NEPSE's φ rises
  from 0.65 to 0.70 at 5 sessions and to 0.75 at 21, for both forms; close-to-close's from 0.50 to 0.55 and from
  0.55 to 0.60. The indices are unchanged. In Dhaka 2023–2026 at 21 sessions the full form's frozen win over
  close-to-close is no longer significant at this step (t −2.22 to −1.82).
* **S2, the calendar target.** Targets that stitched sessions across gaps are removed. The sample shrinks most
  where trading is thinnest:
  * Morocco: 65,894 to 53,246 origins at 5 sessions, and 71,433 to 39,873 at 21;
  * Vietnam: 740,302 to 642,067, and 797,796 to 540,997.

  Vietnam's frozen 21-session loss of the full form to close-to-close (t = +7.27) disappears (t = +0.63). It
  was carried by stitched targets.
* **S3, the loss, the zero targets, the grid and the eligibility rule.** This step moves the two Dhaka panels
  most.
  * **Dhaka 2023–2026.** φ falls for the two forms from 0.60 to 0.25–0.30 at 5 sessions and from 0.60 to
    0.20–0.25 at 21, and for close-to-close from 0.40 to 0.20 and from 0.55 to 0.25. The training span is
    stale: in 2023, a year in which Bangladesh's regulator kept floor prices on most listed shares, 44–51% of
    the panel's daily returns are exactly zero, against 7–16% from 2024 on. Admitting origins where a
    comparator's recent kernel is zero (audit item A08) brings those spells into the training sample. A single
    φ cannot serve both quiet and active states. A lower φ, with more weight on the long-run level, protects
    against the large losses that a near-zero forecast takes when trading resumes. The full form's record
    against close-to-close in that panel goes from −0.66 to +1.55 at 5 sessions.
  * **Dhaka 2009–2021.** The same admitted rows (mostly stale spells in which Parkinson's range is zero) give
    Parkinson a few very large losses. The two forms' mean advantage over Parkinson at 5 sessions grows
    eightfold, from −0.0086 to −0.0678 for the full form, but becomes far noisier. Its t falls from −7.06 to
    −1.60.
* **S4, the corrected inference** (the stock-day mean with its own standard error, 2h lags). It moves the t
  statistics by up to about one, most in Dhaka 2009–2021 at 5 sessions (−7.54 to −6.63 and −9.21 to −8.13).
  It changes one verdict against close-to-close: Morocco at 21 sessions, where both forms now beat it (t −1.16
  to −2.08 and −1.58 to −2.63).

**Rule A (table 126).** Of the 288 per-rival verdicts of the two forms against the other eight frozen
estimators, over every span and horizon, **47 change**:

| Frozen verdict | Corrected: beats | Corrected: no significant difference | Corrected: loses to |
|---|---|---|---|
| beats | 140 | 35 | 1 |
| no significant difference | 5 | 90 | 2 |
| loses to | 0 | 4 | 11 |

**Against the six classical range estimators,** over all spans:

* the full form beat them in 79 of 108 comparisons frozen and in 61 corrected, and now loses one: to
  Parkinson in Dhaka 2023–2026 at 5 sessions (t = +2.09);
* the open-free form went from 73 to 62 wins and loses none.

On the primary spans (84 comparisons each), the full form's wins fall from 64 to 49 and the open-free form's
from 60 to 50.

The largest single change is Dhaka 2009–2021 at 5 sessions. The two forms' frozen wins over Parkinson and
Garman–Klass (t from −9.55 to −12.89) are no longer significant (t from −1.37 to −1.80).

**Against close-to-close,** on the primary spans:

* the full form beats it in 5 of 14 cells: NIFTY 50 and S&P 500 at 5 sessions, Dhaka 2009–2021 at both
  horizons, and Morocco at 21. It was 6 frozen: Dhaka 2023–2026 at 21 and Morocco at 5 are no longer
  significant, and Morocco at 21 now is;
* the open-free form beats it in 8 of 14, as frozen, though in a different set of cells;
* neither form loses to close-to-close in any primary cell.

In NEPSE's post-reform regime, close-to-close still beats both forms at both horizons (t +3.36 and +3.14 at 5
sessions, +2.49 and +2.46 at 21).

## Part B — seventeen forecasts

The comparison adds:

* **Return-only forecasts:** EWMA, variance-targeted GARCH(1,1) and GJR-GARCH(1,1) run in calendar time, and a
  convex HAR on squared returns.
* **Range variants:** true-range Parkinson (TR-P), a HAR on the open-free kernel, and the posterior-moment
  variant of the full form.
* **A fixed combination:** ½ close-to-close + ½ open-free.

Parameters are chosen on the purged training span. Table 127 has every loss and difference.

**Per primary cell.** The columns:

* r\* and g\* are the best return-only and range-based forecasts by training loss.
* B1 tests g\* against r\* on the test span.
* "Lowest" is the lowest test loss of the 17.
* The four MCS columns give membership of the 90% model confidence set.
* The last two columns are each form's t against close-to-close.

| Sample | h | r\* | g\* | Rule B1 (t) | Lowest | CC in MCS | Anam in MCS | Open-free in MCS | HAR-open-free in MCS | Anam vs CC: t | Open-free vs CC: t |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NEPSE, A2 and C | 5 | GARCH | HAR-open-free | no significant difference (+0.35) | HAR-CC | yes | yes | yes | yes | +0.82 | +0.63 |
| NEPSE, A2 and C | 21 | GJR | HAR-open-free | no significant difference (+0.06) | HAR-CC | yes | yes | yes | yes | +0.16 | +0.02 |
| NIFTY 50 | 5 | GJR | HAR-open-free | no significant difference (−0.08) | HAR-open-free | no | yes | yes | yes | −2.91 | −2.99 |
| NIFTY 50 | 21 | GJR | HAR-open-free | no significant difference (−1.75) | HAR-open-free | yes | yes | yes | yes | −0.04 | +0.31 |
| S&P 500 | 5 | GJR | HAR-open-free | no significant difference (−1.18) | TR-P | no | yes | yes | yes | −6.08 | −6.65 |
| S&P 500 | 21 | GJR | HAR-open-free | no significant difference (−1.21) | HAR-open-free | yes | yes | yes | yes | −0.18 | −0.09 |
| Dhaka 2023–2026 | 5 | GJR | HAR-open-free | returns suffice (+2.66) | GJR | no | no | no | yes | +1.45 | −2.56 |
| Dhaka 2023–2026 | 21 | GJR | YZ daily | returns suffice (+3.63) | HAR-open-free | no | no | yes | yes | −0.60 | −1.99 |
| Vietnam 2007–2020 | 5 | GARCH | HAR-open-free | no significant difference (−1.51) | HAR-open-free | no | no | no | yes | −0.86 | −3.94 |
| Vietnam 2007–2020 | 21 | GARCH | HAR-open-free | no significant difference (−1.19) | HAR-open-free | no | no | yes | yes | +1.64 | −0.63 |
| Dhaka 2009–2021 | 5 | GJR | HAR-open-free | range adds information (−6.31) | HAR-open-free | yes | yes | yes | yes | −6.52 | −8.02 |
| Dhaka 2009–2021 | 21 | GJR | HAR-open-free | range adds information (−3.14) | HAR-open-free | yes | yes | yes | yes | −2.45 | −3.04 |
| Morocco 2012–2026 | 5 | HAR-CC | HAR-open-free | range adds information (−2.30) | HAR-open-free | no | no | yes | yes | −0.53 | −2.62 |
| Morocco 2012–2026 | 21 | GARCH | HAR-open-free | range adds information (−2.72) | HAR-open-free | no | yes | yes | yes | −2.03 | −2.61 |

NEPSE's post-reform regime C, a secondary span, gives "returns suffice" at both horizons (t = +3.75 and +3.35),
and its 90% set contains no range-based forecast at all.

**Rule B1, does the range add forecasting information?**

| Verdict | Where |
|---|---|
| Range adds information | Dhaka 2009–2021 and Morocco, at both horizons |
| Returns suffice | Dhaka 2023–2026 at both horizons, and NEPSE regime C |
| No significant difference | NEPSE's holdout, the NIFTY 50, the S&P 500 and Vietnam |

**Rule B2, the model confidence sets.** Membership of the 90% set over the 14 primary cells:

| Forecasts | Cells (of 14) |
|---|---|
| GJR-GARCH; HAR-open-free | 14 |
| HAR-CC; GARCH | 13 |
| the open-free form | 12 |
| the combination | 11 |
| TR-P; the posterior variant | 10 |
| the full form; EWMA; Garman–Klass; Parkinson | 9 |
| overnight² + Parkinson; overnight² + Garman–Klass | 8 |
| the Yang–Zhang daily form | 7 |
| close-to-close | 6 |
| Rogers–Satchell | 5 |

The lowest test loss belongs to:

* HAR-open-free in 10 cells;
* HAR-CC in 2 (NEPSE);
* GJR in 1 (Dhaka 2023–2026 at 5 sessions);
* TR-P in 1 (the S&P 500 at 5 sessions).

**Rule B3, Holm across the seven samples at 5 sessions.** One-sided, adjusted p < 0.025.

| Form | Beats close-to-close after Holm | Not after Holm |
|---|---|---|
| Full form | Dhaka 2009–2021, the S&P 500, the NIFTY 50 | Vietnam, Morocco, NEPSE, Dhaka 2023–2026 |
| Open-free form | Dhaka 2009–2021, the S&P 500, Vietnam, the NIFTY 50, Morocco (adjusted p 0.013), Dhaka 2023–2026 (0.013) | NEPSE |

**Rule B4, the ±1% practical margin.**

* One comparison is practically equivalent to close-to-close: the full form in Vietnam at 5 sessions (90%
  interval [−0.0057, +0.0018], margin ±0.0058).
* Every other comparison is "not shown equivalent". That includes the significant wins, whose intervals cross
  the margin, and NEPSE's holdout, where the intervals are wide.

**The plan's claim rules, applied:**

* **"No classical range estimator has significantly lower loss than Anam's estimator in any test sample".** It
  fails once at S4. It is replaced by the count: one of 84 primary comparisons for the full form (Parkinson in
  Dhaka 2023–2026 at 5 sessions), none for the open-free form.
* **Rule B1.** Where Rule B1 is not "range adds information", the paper says so for that sample:
  * Dhaka 2023–2026: returns suffice;
  * NEPSE, the indices and Vietnam: the range added no detectable forecasting information beyond the best
    return-only forecast.
* **"Lowest loss" for the open-free form.** Withdrawn: in no cell does it have the lowest loss of the 17.

## Part C — ablations (reported, no decisions)

Primary spans, S4 inference; 14 cells per contrast, 10 for pooling (panels only). Negative t favours the first
model.

| Ingredient | Contrast | First model beats | First model loses | t range |
|---|---|---|---|---|
| Calibration | Parkinson raw vs calibrated | 0 | 9 | +0.32 to +7.54 |
| | open-free raw vs calibrated | 0 | 7 | −0.29 to +4.42 |
| Previous-close anchor | TR-P vs Parkinson | 7 | 0 | −19.12 to +1.52 |
| The 0.2 r² blend | open-free vs TR-P | 8 | 1 (S&P 500, 5 sessions) | −26.90 to +4.65 |
| Estimating b | full vs open-free (b = 0) | 0 | 7 | −1.25 to +14.88 |
| | full vs overnight² + Parkinson (b = 1) | 10 | 0 | −10.18 to +0.61 |
| Cross-sectional pooling | own-series vs pooled calibration | 0 | 4 | −0.26 to +4.47 |
| Adaptive scale | constant vs rolling calibration | 2 (S&P 500) | 3 | −2.97 to +3.66 |
| Dynamics | HAR-open-free vs open-free | 7 | 0 | −11.43 to −0.11 |
| | HAR-CC vs CC | 10 | 0 | −11.96 to −1.01 |
| Measurement, with close-to-close's φ | open-free vs CC | 5 | 1 (Dhaka 2023–2026, 5 sessions) | −6.93 to +2.50 |
| | full vs CC | 3 | 2 | −5.39 to +4.46 |
| Residual uncertainty (exploratory) | posterior vs full form | 1 (Morocco, 5 sessions) | 6 | −2.30 to +11.09 |

Read together (interpretation):

* **Discounting the open helps, and leaving it out helps most.**
  * The full form beats overnight² + Parkinson (b = 1) in 10 of 14 cells.
  * It loses to the open-free form (b = 0) in 7, every one of them a frontier panel. In the five frontier
    samples it never beats the open-free form.
  * Estimating b is therefore not where the gain comes from. The paper already said so; the ablation now
    measures it.
* **The previous-close anchor and the r² blend carry the open-free form's advantage over Parkinson** in the
  frontier panels:
  * the anchor wins in 7 of 10 frontier cells;
  * the blend wins in 8 of 10;
  * on the S&P 500 the blend hurts.
* **Calibration matters.** Uncalibrated kernels never win.
* **Dynamics matter as much as measurement.** A HAR beats the frozen φ-shrinkage in 10 of 14 cells for
  squared returns and 7 of 14 for the open-free kernel. Much of the frozen forecasts' gap to good return-only
  models is the dynamics, not the measure.
* **With the dynamics held equal** (close-to-close's φ), the open-free measure beats squared returns in 5 of 14
  cells: Dhaka 2009–2021 at both horizons, Morocco at 21, the NIFTY 50 and Vietnam at 5. It loses in one.
* **The posterior moment does not help a calibrated forecast.** It is theoretically correct for the
  overnight second moment (Proposition 7(a)) but loses to the frozen kernel in 6 of 14 cells: Dhaka 2023–2026
  (t = +11.09 and +5.67), the NIFTY 50 and Vietnam, at both horizons.

  Once a common calibration sets the level, the extra b(1 − b)m₂ term adds a slowly moving component that
  dilutes the daily signal. The audit's arithmetic stands; it does not translate into better forecasts.

## Part D — coverage (table 131)

**Eligible share of test origins** (primary spans):

| Sample | 5 sessions | 21 sessions |
|---|---|---|
| NEPSE | 91.8% | 83.7% |
| NIFTY 50 | 99.8% | 99.0% |
| S&P 500 | 99.8% | 99.2% |
| Dhaka 2023–2026 | 96.3% | 87.0% |
| Vietnam | 79.0% | 63.5% |
| Dhaka 2009–2021 | 92.9% | 81.1% |
| Morocco | 71.8% | 51.0% |

Most exclusions are targets with a missing session, which the calendar target refuses to stitch:

* Morocco: 20,207 of 78,923 origins at 5 sessions;
* Vietnam: 150,118 of 838,890.

The least liquid tercile is hit hardest. In Morocco only 44% of its 5-session origins and 22% of its 21-session
origins have a complete target; in Vietnam, 63% and 39%. The corrected comparison is therefore a comparison on
securities that trade on every session of the horizon. Thin securities are under-represented in it. No forecast
of variance over sessions on which a security does not trade can be scored against an observed return.

**Zero targets kept and scored** (5 sessions):

| Sample | Zero targets |
|---|---|
| Dhaka 2009–2021 | 8,166 |
| Vietnam | 5,165 |
| Dhaka 2023–2026 | 443 |
| Morocco | 198 |

NEPSE and the indices have none.

## Part E — inference sensitivity (table 132)

The rows compared:

* h, 2h (primary) and 4h;
* Andrews' plug-in bandwidth;
* the equal-date and equal-security means;
* non-overlapping origins.

**Robust:**

* Rule B1 in Dhaka 2009–2021 at both horizons (t from −5.03 to −7.23 at 5 sessions);
* "returns suffice" in Dhaka 2023–2026 at 21 sessions (t from +3.61 to +4.63), and at 5 sessions except with
  non-overlapping origins (+1.67);
* the open-free form against close-to-close in Dhaka 2009–2021 and the S&P 500;
* the open-free form against the full form in Vietnam and Dhaka 2023–2026 at both horizons, and in Dhaka
  2009–2021 at 5 sessions. At 21 sessions there it is not significant with equal security weights (−0.96) or
  Andrews' bandwidth (−1.93).

**Fragile:**

* **Morocco's Rule B1.** At 5 sessions it is not significant with the equal-date mean (−1.86), the
  equal-security mean (−0.81) or non-overlapping origins (−1.87). At 21 sessions it is not significant with the
  equal-date mean (−1.66) or non-overlapping origins (−1.40).
* **Vietnam's open-free win over close-to-close at 5 sessions** reverses sign with equal security weights
  (+0.95), and the full form's position worsens sharply (+5.48). Vietnam's stock-day result is carried by its
  long-lived, frequently traded securities.
* **The open-free form against close-to-close in Morocco at 5 sessions** is not significant with equal
  security weights (−0.92).

## What this changes in the paper (fixed by the plan, applied here)

* **The forecasting record of Anam's estimator becomes the corrected one.** The frozen M16–M18 verdicts stay in
  the paper as the plans' historical record, with the defects described (manuscript round 19).
* **Against the classical range estimators**, the claim becomes a count:
  * the full form is beaten in 1 of 84 primary comparisons;
  * the open-free form in none;
  * each form beats a classical estimator in 49 and 50 of them.
* **Against close-to-close**, the open-free form's 5-session win survives Holm's adjustment in six of seven
  samples, NEPSE excepted; the full form's in three.
* **Against the best return-only forecast** (GARCH-type or HAR), the range adds detectable information in
  Dhaka 2009–2021 and Morocco only. Morocco's verdict is fragile to the weighting. Returns suffice in Dhaka
  2023–2026 and after NEPSE's reform.
* **The best forecast** in most samples combines the open-free measure with HAR dynamics. It is in every 90%
  confidence set, but so is GJR-GARCH.
* **The paper's estimator contribution is narrower than the frozen plans suggested.** The useful part is a
  calibrated, open-free range measure:
  * the previous-close-anchored range;
  * a small r² blend;
  * a pooled calibration.

  It works as an input to a good forecasting model, and in two of seven samples it carries information that
  returns do not.

## Deviations and implementation notes

1. **Floating-point residues of equal prices (found in the first run; `M-033`).** A return between equal
   prices is computed as o + c and can be stored as about 1e-16, so its square is about 1e-32, not zero.
   * In Dhaka 2023–2026 these residues passed the eligibility rule's "long-run level > 0":
     * 179 rows had a positive long-run level below 1e-15, the smallest 2.3e-36;
     * 706 rows had a positive recent mean below 1e-15.
   * They produced near-zero forecasts. The return-only forecasts' training losses were of order 1e26, and
     close-to-close's selected φ was 0.
   * The first run was stopped from informing anything: its tables are kept outside the repository, and none of
     its numbers is used.
   * The fix sets squared quantities below 1e-18 to zero; a genuine one-tick move squares to more than 1e-12.
     Rolling means of zeros are exactly zero. The same rule applies in the package and the research code
     (`ZERO_SQUARE`, with a test that keeps the two equal).
   * It applies from step S3 on and in Parts B–E. Steps S0–S2 keep the frozen arithmetic, so that S0 still
     reproduces the frozen tables.
   * Only Dhaka 2023–2026 had absurd losses in the first run. The rerun changed its r\* from close-to-close to
     GJR and its Rule B1 verdict at 5 sessions from "range adds information" to "returns suffice".
2. **One purge cutoff per sample.** Training outcomes must end before the first session of the sample's primary
   test span, for every span. One fitted φ then serves all of NEPSE's spans, as in the frozen design. The plan
   says "before the test start" without saying which span's.
3. **The frozen record contains the same residues (post hoc, `scripts/51_frozen_residue_check.py`, table 137).**
   The frozen evaluation dropped zero targets, as its plans said. A target made only of residues was not zero,
   so it was kept and scored.
   * Each such target adds about 35–70 to every forecast's normalised loss. The added term differs across
     forecasts only through ln f.
   * So the frozen loss levels in four frontier panels are inflated; in each case, the full form's normalised
     QLIKE at 5 sessions:
     * Vietnam: from 0.5786 to 0.7705;
     * Dhaka 2023–2026: from 0.5119 to 0.6316;
     * Dhaka 2009–2021: from 0.5527 to 0.6044;
     * Morocco: from 0.6522 to 0.6706.
   * The differences move little. Setting the residues to zero, as the frozen plans intended, changes the
     verdicts among the two forms and close-to-close in **one** of 18 sample-span-horizon cells: Dhaka 2023–2026
     at 21 sessions. There the full form's win over close-to-close is no longer significant (t −2.22 to −1.82),
     and the open-free form now beats the full form (t −0.18 to −3.04), because 89 residue targets in the
     training span had moved the full form's φ. The corrected evaluation agrees on both (t = +0.17 and −3.74).
   * NEPSE and the indices have no residue target in any test sample.
4. **The audit's diagnostic files** (`opening_noise_counterexample.csv` and the others it cites) were not
   supplied. Every count the audit quotes was reproduced from the code and data instead (see
   `RESEARCH_AUDIT_RESPONSE.md`).
