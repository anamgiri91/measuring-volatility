# Response to the independent research audit of 9 October 2026

The audit and its publication plan are kept as received in `audits/2026-10-09_research_audit.md` and
`audits/2026-10-09_publication_plan.md`. This document answers it item by item:

* what was checked;
* where the audit is right, partly right or, in our reading, wrong;
* what was changed, and with what effect.

The corrections are registered as `M-028` to `M-034` in `AUDIT-REGISTER.md`. They reach the manuscript in
round 19 (`paper/apply_round19_revisions.py`).

**Summary.**

* **Every quantified finding reproduced exactly** before anything was changed:
  * A01: 1,239 of 66,931 and 5,191 of 66,917 leaked training origins;
  * A02: 218 and 618 stitched targets, spanning up to 47 and 81 sessions;
  * A08: a 33,410-origin swing across the φ grid;
  * A09: the Moroccan sign reversal.
* **We accept twelve findings in full and three in part** (A02, A09 and A13).
* **Where we part from the audit, it is on three narrow points:**
  * forecast features over a security's last observed bars are legitimate predictors (A02);
  * a test of forecasting methods with a once-estimated φ needs no extra parameter-uncertainty
    correction (A09);
  * the full-sample weight floor is an orthogonal nuisance with negligible effect, now measured (A13).
* **On one point the audit understated its own case.** The instruments behind the calibration slopes
  are weaker than the conventional F suggests (A06, below).

**What was built in response.**

* **Plan M20, frozen before any corrected loss was computed** (commit `984dfbc`). It re-runs every
  forecast test without the four defects and adds:
  * return-only baselines;
  * ablations;
  * a model confidence set;
  * Holm corrections and a practical margin.
* **A seventh proposition in the theory supplement.** It makes the audit's objections A04 and A05
  exact and measures what remains.
* **A post hoc sensitivity script** (`scripts/49_audit_sensitivities.py`) for A06, A11, A13 and A15.
* **A frozen prospective protocol, M21**, for data not yet in the repository.

The results of M20 are in `M20_CORRECTED_EVALUATION_RESULTS.md` and summarised under A12 below.

---

## A01 — training outcomes crossed the holdout boundary. ACCEPTED; FIXED.

**Right.** `fair_forecast_test` masked origins, not outcomes. The package's `train_end` did the same, and
script 44 copied it. The counts reproduce exactly on NEPSE, NIFTY 50 and the S&P 500.

**Fixed.** `anam_estimator.evaluation.forward_target` records each origin's outcome-end session, and
`purged` keeps only training origins whose outcome ends before the first test session.

* The package's `AnamModel` (0.2.0) and the paper's corrected evaluation both use these functions.
* The ML model already purged by date; it now uses the same calendar target.
* A test changes every price on or after a cutoff by a random factor and checks that the fitted φ does
  not move. It would have failed on version 0.1.0.

**Effect.** Purging alone (M20 step S1) moves NEPSE's φ for both forms from 0.65 to 0.70 at 5 sessions
and to 0.75 at 21, exactly the audit's figures. No verdict changes at that step.

## A02 — horizons stitched across missing sessions. ACCEPTED for the target; the feature point DISPUTED.

**Right about the target.** A target of h sessions is now h consecutive sessions of the exchange
calendar:

* NEPSE's 569-session calendar;
* each frontier panel's own sessions;
* each index's own dates.

It is observed only if the security has a return on every one of them, and it must lie inside the test
span. The counts reproduce exactly (218 and 618 stitched NEPSE targets, longest 47 and 81 sessions).

**Effect** (step S2). Test samples shrink most where trading is thinnest:

* Morocco: 65,894 to 53,246 origins at 5 sessions;
* Vietnam: 740,302 to 642,067.

Table 131 counts every exclusion by reason and liquidity tercile.

**Where we differ.** The audit adds that "historical forecast features also use retained rows" and asks for
a full redesign of feature windows. A feature only has to be known at the origin. "The mean of the kernel
over the security's last h observed bars" is known at the close of t, however many calendar sessions those
bars span. So the forecasts remain valid predictors, and their losses remain valid evaluations.

The calendar governs what is forecast, not what may be used to forecast it. The features are kept as they
were, and plan M20 says so explicitly. A calendar-time feature is a modelling choice the corrected
comparison can test later; it is not a validity requirement.

## A03 — the QLIKE argument assumed an unbiased latent proxy. ACCEPTED; FIXED.

**Right.** "Ranking by expected QLIKE loss matches the ranking that the true variance would give" was too
strong. Patton's result ranks forecasts by the target's conditional mean, here the conditional second
moment of observed close-to-close returns. That is not integrated variance: the squared drift and the
closing-price errors (2E[ε²] under independent closing errors) separate them.

**Fixed.** `ESTIMAND_NOTE.md` defines four objects and says which claim is about which:

* the observed-return second moment;
* the conditional return variance;
* integrated variance;
* jump-inclusive quadratic variation.

The forecast comparison is now described as a comparison of measurement-plus-forecasting procedures for
the first of these. The same correction is made in the manuscript (round 19), the docstrings of
`nepsevol.volforecast` and `anam_estimator.evaluation`, the README and the model card.

## A04 — a linear predictor is not the permanent overnight move. ACCEPTED; turned into a result.

**Right.** The theory supplement had already moved to "on the log scale" (`M-027`), but the estimator's
docstring and Section 6.8 still called b·o "the permanent overnight move" and PC·exp(b·o) "the best linear
predictor of the efficient opening price". Both are corrected: b·o is a shrinkage predictor of the
efficient log move, and PC·exp(b·o) is the anchor price it implies.

**Proposition 7(a)**, new in the theory supplement, makes the audit's arithmetic a theorem:

* **The identity.** E[(b o)²] = E[o*²] − E[(o* − b o)²]. The overnight term never overstates the
  efficient overnight second moment, and it is exact only under proportional overreaction.
* **An uncorrelated error.** The term carries the fraction b of the moment, so it understates by
  (1 − b)E[o*²].
* **The correction.** The linear posterior moment b²o² + b(1−b)E[o²] is unbiased under an uncorrelated
  error, and equals E[o*² | o] under joint normality.
* **Without a restriction on the error's correlation with the news**, the deficit is identified only up
  to [0, E[r²] − b²E[o²]] (Proposition 1(e)).

The audit's example, Var(x) = 1 and Var(η) = 3, gives b = 1/4 and E[(b o)²] = 1/4, as the proposition says.

**Evaluated.** The posterior-moment variant is one of M20's seventeen forecasts, labelled exploratory (see
A12). The construction as frozen is now described as a heuristic whose level the calibration sets.

## A05 — the extended range cannot remove an opening error already in an extreme. ACCEPTED; MEASURED.

**Right.** R* = max(h, b o) − min(l, b o), so R ≤ R* ≤ TR. The extension moves the anchor and never the
extremes. The audit's bar (C₋ = C = L = 100, O = H = 105) gives an open-free kernel of 4.1×10⁻⁴ from the
print alone. A package test now pins exactly that bar. The docstring's "cannot inflate it" was true only
of the extension term with H and L held fixed, and is withdrawn.

**Proposition 7(c) measures the limits,** as the audit asked. Under the supplement's Brownian model:

* To first order in the error, true-range Parkinson absorbs γ_TR(s) = ¼ + s·E[ψ(U/s)]/(2√(2π) ln 2) of
  the error's variance:
  * U is the maximum of a Brownian meander, and s the efficient overnight scale relative to the session;
  * γ_TR rises from ¼ to about s/(4π ln 2);
  * so the open-free form absorbs 0.8·γ_TR(s).
* At first order the full kernel absorbs −½: its overnight shrinkage over-corrects. With the posterior
  moment it absorbs +½.
* At the error sizes the data imply, first order fails. The exact exposures, by simulation at each
  sample's implied scales:

  | Kernel | Share of the error's variance absorbed |
  |---|---|
  | open-free form | 0.25 to 0.38 |
  | Parkinson | 0.50 |
  | full kernel | −0.36 to +0.33 |
  | overnight² + Parkinson | 1.50 |
  | close-to-close | 0 |

Leaving the open out reduces the exposure; it does not remove it. Script 48 has 63 checks, all passing,
and script 46 verifies the proof step by step.

## A06 — "calibration, not cancelling errors" was too strong. ACCEPTED; and the audit understated it.

**Right about the wording.**

* Containing one does not establish equivalence: Parkinson's [0.760, 1.056] allows 24% attenuation.
* The pooled overidentifying restrictions are rejected (J p = 0.0002).
* Persistence gives relevance, not exclusion.

The manuscript's M14 verdict ("no detectable attenuation") and limitation 13 were already narrow, but
the abstract, introduction, README and letters were not. They now say that a unit slope is not rejected
and give the interval. The calibration module's docstring now states that instrument validity is an
assumption of the model, not a consequence of persistence.

**Stronger than the audit said.** The audit noted that `first_stage_F` is the conventional,
homoskedastic statistic. Computed with two-way (security and date) clustering:

| Statistic | Instruments dated t−1 (primary) | Instruments dated t−2 |
|---|---|---|
| conventional F | 556 | 171 |
| cluster-robust Wald F | 41.7 | 25.4 |
| Montiel Olea–Pflueger effective F | **19.4** | **29.9** |

At 19.4, the primary specification is below the conservative 23.1 threshold for a worst-case bias under
10%. The two-session-lag specification, which the supplement's Proposition 6(c) already called the
relevant check, clears it. Both are now reported (Section 6.6 and limitation 13; table 135). The
calibrate function computes both statistics on request.

## A07 — event timing does not identify the band's effect. ACCEPTED (wording); already disclosed in the body.

The rule package and the failed dose-response were disclosed (limitation 3, `M-013`, `M-023`). The
abstract ("natural experiment"), introduction, conclusion, keywords, a table caption and every cover
letter still implied a causal band effect. Round 19 rewrites each to say that the break coincided with the April
2026 rule package (an "event", not a "natural experiment") and that the band's separate effect is not identified.
"The narrow band had been capping overreaction rather than delaying price discovery" becomes "consistent with
the narrow band capping overreaction".

"The session undoes 64-87%" now says what it is: 1 − b, a pooled projection weighted by squared opening
moves.

What the audit asks beyond wording needs the author or new data. Obtaining dated NEPSE circulars, a longer
post-event window, pre-trends and auction data are listed under "what needs the author" below.

## A08 — zero targets and parameter-dependent samples. ACCEPTED; impact now measured externally.

**Right about the logic, and right that the frozen selections were unaffected.** Every frozen φ lies in
[0.10, 0.80], and the NEPSE and index samples have no zero targets.

**Fixed:**

* zero targets are scored, with canonical QLIKE y/f + ln f;
* φ ∈ {0, …, 0.95}, so every candidate forecast is positive;
* a non-positive candidate is rejected rather than rescored;
* an origin is no longer dropped because a comparator's recent kernel is zero.

**The audit could not measure the frontier panels; this environment can.** Zero targets exist there:

| Sample | Zero targets at 5 sessions |
|---|---|
| Vietnam | 1,360 |
| Morocco | 111 |
| Dhaka 2023–2026 | 67 |

Admitting zero-kernel origins matters more than the zero targets themselves. It re-weights the training
sample toward stale spells, where a single φ cannot serve both quiet and active states.

**A numerical defect, found and fixed.** The first M20 run exposed a second, numerical defect. Equal
prices stored as floating-point numbers gave squared returns of order 10⁻³². In Dhaka those passed the
"long-run level > 0" test and produced near-zero forecasts and training losses of 10²⁶. Squared
quantities below 10⁻¹⁸ now count as zero (a genuine one-tick move squares to more than 10⁻¹²), and
rolling means of zeros are exactly zero, in the package and the research code alike. This is disclosed
in the results document; the affected first-run numbers are not used.

## A09 — the mean and its t statistic estimated different weightings. ACCEPTED in substance; one request DISPUTED.

**Right.** The Moroccan sign reversal reproduces. M20 uses one estimand throughout, the stock-day mean,
for selection, reported differences and inference.

* **Inference:** the date-level linearisation of the ratio estimator with a Bartlett long-run variance.
* **Bandwidth:** 2h rather than h. With h the lag-(h−1) overlap covariance gets weight 2/(h+1); with 2h
  it gets more than a half.
* **Other estimands:** the equal-date and equal-security means are reported separately with their own
  t, as are h, 4h, Andrews' plug-in bandwidth and non-overlapping origins (table 132).

**Where we differ.** The audit asks for "fitted-parameter uncertainty in the final comparison". Each
method's φ is estimated once, on a training span that ends before the test span. The test then compares
the forecasting methods, estimation included. Under Giacomini and White (2006) the usual statistic is
valid for that null, with no correction for estimating φ. A correction would be needed to test the
population models' predictive ability. The paper does not claim that.

## A10 — the four-market headline could not be regenerated from the distributed inputs. ACCEPTED; FIXED.

The third-party inputs were present in this environment, supplied by the author, so all seven samples
were recomputed here. A reviewer without them cannot recompute them.

**Fixed:**

* **The runner.** `run_paper_analysis.sh` records every analysis that ran or was skipped in
  `output/run_status.json`, and ends with "PARTIAL reproduction" when the frontier inputs are absent,
  naming what was reused rather than regenerated.
* **The manifest** copies that status instead of a description of earlier runs.
* **The manuscript's** limitation 10 and data availability statement, the title page and every cover
  letter now delimit what the package reproduces: everything on the NEPSE panels and the two indices.
  The Bangladeshi, Vietnamese and Moroccan results need files the package documents and pins by digest
  but does not distribute.
* **The JFEC route.** The audit's point about JFEC's replication policy stands. A JFEC submission would
  need either reviewer access to those files or an exemption request (see A15).

## A11 — external-panel data assumptions. ACCEPTED as limitations; the provenance work needs the author.

**Already disclosed.** These were disclosed in `data/external/README.md`, M17, M18 and limitation 15:

* the Dhaka row count and date repair;
* Vietnam's provider, labels and adjustment;
* Casablanca's provider and fixing/continuous status.

**Done here:**

* **The full sample funnel** (table 131): every test origin, by target status (complete, missing
  session, missing return, outcome beyond the span) and by eligibility, split by liquidity tercile.
* **NEPSE's corporate-action tolerance.** Its justification was wrong, as the audit said. Two-decimal
  rounding of a median price of 635 is about 0.001%, and none of the 315 disagreements is that small.
  The 0.5% threshold is a classification choice, now described as one. It barely matters: the
  corporate-action count is 216 at 0.5%, 219 at 0.25% and 221 at 0.1% (table 135). The code comment, the
  robustness script's interpretation string and table 47 are corrected.

**Needs the author** (listed below): the original providers and licences, adjustment factors, historical
security identities, an independent check of the Dhaka date repair, and exchange labels for Vietnam.

## A12 — "not significantly beaten" was weak evidence. ACCEPTED; the comparison is rebuilt.

M20 compares seventeen forecasts on each sample's test span:

* **Return-only, five:** the historical close-to-close forecast, EWMA, variance-targeted GARCH(1,1)
  and GJR-GARCH(1,1) run in calendar time, and a convex HAR on squared returns.
* **Range-based, eleven:** the six classical kernels, both forms of Anam's estimator, pure calibrated
  true range, a HAR on the open-free kernel, and the posterior-moment variant of A04 (exploratory).
* **One fixed combination.**

Parameters are chosen on the purged training span. M20 then reports:

* a model confidence set at 90% and 75%;
* Rule B1: whether the best range-based forecast, chosen on the training span, beats the best
  return-only one;
* Holm's adjustment across the seven samples;
* a ±1% practical margin;
* ablations that switch off one ingredient at a time.

The results are summarised in the section "What the corrected evaluation found" below.

**Partly already conceded.** That the open-free form beat the full form "weakens the argument that
estimating b is the innovation" was already the paper's own reading (M19's P4a; Section 6.8, "setting it
to zero did better"). The ablations now quantify it.

**The docstring's "before any holdout data were read" is corrected** (see `M-020` for the same wording in
the manuscript).

**Not adopted.** The publication plan suggests renaming the estimator descriptively. The name is the
author's choice. The anonymous submission copy already calls it "the proposed estimator", and the build
fails if the name survives there.

## A13 — the "predictable" weight used a full-sample floor. ACCEPTED as stated; its importance DISPUTED, and measured.

**Right.** The floor at the 1% quantile of S over the whole panel uses future observations, so the
weight is not strictly F_{t−1}-measurable, and the docstring's "by construction" was wrong.

**Why it matters little.** Every moment condition E[w U Z] = 0 holds for any fixed floor, because
E[U | F_{t−1}] = 0 whatever constant enters w. The population moment therefore does not move with the
floor, and estimating it is an orthogonal nuisance with no first-order effect on the estimator.

**Measured** (table 135). A past-only expanding floor (`predictable_scale(floor="past")`):

* changes 1.7% of the weights;
* moves the slopes by at most 0.007 (Parkinson 0.919 to 0.922);
* moves the J p-values by at most 0.002 (AddRS 0.061 to 0.063); every rejection stays a rejection.

The docstring now says all of this.

## A14 — the manuscript could not be rebuilt from the shipped sources. ACCEPTED; FIXED where possible.

**Fixed:**

* **The base draft.** `paper/apply_referee_revisions.py` no longer defaults to a file in the author's
  Downloads folder; `--base` is required and documented. The pre-revision draft is not distributed, so
  the revision scripts are a record of every edit and its check. The tracked
  `NEPSE_Volatility_Manuscript_Revised_2026-09.docx` is the canonical editable source, and the README
  and manifest now say so instead of implying a rebuild from scratch.
* **python-docx** is pinned in `requirements.txt`.
* **The manifest** records the captured run status (A10) rather than descriptions of earlier runs.

**Not done.** A single deterministic build of results, manuscript, anonymous set and rendered PDF does
not exist yet. There is no .docx-to-PDF renderer in this environment, and the manuscript is still built
by incremental revision scripts. This remains open, as does a current rendered PDF.

## A15 — format and smaller statements. ACCEPTED; FIXED except what needs the author.

**Fixed:**

| Item | Was | Now |
|---|---|---|
| Section 7.2 | 1.280 called "higher than" 1.288 | "slightly lower than" |
| `data/processed/README.md` | 184,390 rows, a "40-row difference" | 184,391 rows, a 39-row difference |
| Section 7.1 notation | the daily estimator written as κA | v̂ₜ₋ⱼ = κₜAₜ₋ⱼ, the calibration of the window's last session applied to the whole window, as implemented |
| Limitation 4 | NEPSE forecasting cannot be tested without options | corrected: the limitation now concerns implied volatility only, and says that Section 6.8 tests forecasts of realised return variation, which needs no options |
| Limitation 9 | "a lower bound on total uncertainty" | the intervals quantify sampling uncertainty for stated observable statistics and do not bound uncertainty about latent variance |

**Not fixed: the author, contact and ORCID placeholders, and the letters' date and signature.** Only the
author can supply them.

**Not addressed: JFEC's format** (an abstract of at most 100 words, two to six keywords). The audit and
its plan both advise against submitting to JFEC now, so no JFEC-format version is produced. The JFEC
cover letter remains in the set with its claims corrected. It should not be sent until the format, the
replication-access question (A10) and the research gates are met.

---

## What the corrected evaluation found

`M20_CORRECTED_EVALUATION_RESULTS.md` has the details, and manuscript Table 39 the summary.

* **Step S0 reproduces the frozen tables exactly** in all seven samples before anything is corrected.
* **47 of the 288 frozen per-rival verdicts change.** Most are wins over a classical range estimator that are no
  longer significant.
* **The audit's predictions for the frozen record hold.** "No classical range estimator has significantly lower
  loss" is false once:
  * Parkinson beats the full form in Dhaka 2023–2026 at 5 sessions (t = +2.09);
  * it is now 1 of 84 primary comparisons for the full form and 0 for the open-free form.
* **Against plain close-to-close the open-free form survives the corrections.** After Holm's adjustment across
  the seven samples, it beats close-to-close at 5 sessions in six of them, NEPSE excepted; the full form does so
  in three (Dhaka 2009–2021 and the two indices).
* **Against strong return-only forecasts the range adds detectable information in two samples only** (Rule B1):
  * it adds information in Dhaka 2009–2021 and Morocco, and the Moroccan verdict is fragile to the weighting;
  * returns suffice in Dhaka 2023–2026 and after NEPSE's reform;
  * there is no detectable difference on NEPSE's holdout, the indices and Vietnam.
* **The best single forecast pairs the open-free kernel with HAR dynamics.** It has the lowest test loss in 10 of
  14 cells and is in every 90% model confidence set. GJR-GARCH, which uses returns only, is in every set too;
  plain close-to-close with φ-shrinkage is in six.
* **The ablations** say what the useful part of the estimator is:
  * calibration;
  * the previous-close anchor;
  * the r² blend;
  * leaving the open out: estimating b never beats setting it to zero.

  The posterior-moment overnight term of Proposition 7(a) does not improve forecasts.
* **The frozen loss levels in four frontier panels include floating-point residues of equal prices** (post hoc,
  `scripts/51`). They are inflated by 0.02 to 0.19, and one frozen verdict changes once the residues are zero.

The paper's estimator claim is therefore narrower than M16–M18 suggested, and more defensible. It now says:

* a calibrated, open-free range measure helps against the plain close-to-close forecast in most samples;
* it carries information beyond strong return-only models in two of seven;
* it is the best measurement input to a HAR forecast.

The prospective plan M21 tests those claims on sessions that did not exist at the freeze.

## What needs the author

* **The inputs, for reviewers.** Reviewer access to the Dhaka, Vietnamese and Casablanca inputs, or a
  replication exemption request worded for the target journal.
* **The external panels:** providers, licences, adjustment factors and historical identities, an
  independent check of the Dhaka date repair, and exchange labels for Vietnam.
* **NEPSE's rules:** dated circulars for the April 2026 rule package, with publication and effective
  dates.
* **Intraday validation:** high-frequency data for a liquid market, to validate measurement against a
  realised-variance benchmark (the publication plan's Phase 4).
* **An external timestamp for plan M21**, for example OSF or AsPredicted. A git commit is
  author-controlled.
* **The submission details:** author, affiliation, contact, ORCID, and the cover letters' date and
  signature.
* **A rendered PDF** of the current manuscript.
