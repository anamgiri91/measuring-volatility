# M19 — frozen plan: checking the theory of the noisy open, and its one new prediction

**Written and frozen on 2026-10-09.** At that point `scripts/45_theory_checks.py` did not exist and
no statistic in Part C had been computed. The commit that adds this file precedes the commit that
adds the script, its outputs and the LaTeX theory section (`paper/theory/`), so the order can be
checked in the history.

The theory is **post hoc** relative to plans M14–M18. Its six propositions were derived after those
plans' results were known, in order to explain them. This plan has three parts:

* **Part A** verifies the mathematics.
* **Part B** reports applications that are arithmetic on frozen tables, or recomputations with
  frozen code.
* **Part C** is the only new test. Its prediction and decision rule are fixed here.

## The model in one paragraph

The notation is the manuscript's, from its Appendix A:

* the overnight return is o = e_o + η − ε₋ and the intraday return is c = e_c − η + ε;
* e_o and e_c are efficient returns, η is the open's transient error, and ε, ε₋ are the closing
  errors;
* o\* = e_o − ε₋ is the efficient open measured from the printed previous close, so o = o\* + η
  and r = o\* + e_c + ε.

Assumption A is that nothing known at the open predicts the rest of the session:

* E[o\*(e_c + ε)] = 0;
* E[η(e_c + ε)] = 0.

The error η may be correlated with o\* in either direction. Assumption B adds the shape of the
session path. The printed open is followed by the efficient path o\* + W(s), where W is a Brownian
motion with session variance σ_c² that is independent of (o\*, η). The high and the low are the
extremes of the printed path. Under this assumption the open's error is corrected at once.

The propositions are:

| | Statement |
|---|---|
| 1 | Identification: what b identifies, including a sharp bound on E[η²] |
| 2 | The bias of each classical estimator under a noisy open |
| 3 | How a price band inflates b |
| 4 | How a pooled calibration penalises securities whose opens differ |
| 5 | How a rolling calibration lags a rule change, and the window that balances lag against noise |
| 6 | The validity and asymptotics of the instrumented calibration test of M14 |

## What was known before freezing (disclosed)

1. **Every table up to `table120`.** In particular:
   * `table89`: b by regime and by zone;
   * `table97`: E[o²]/E[OC], b, the Appendix A bound, and the share of non-stale opens that are
     the session high or low;
   * `paper_table32`;
   * `table106` and `table106b`. In 10-session blocks, the applied calibration fell from 0.93 at
     the band reform to 0.66–0.68 50–60 sessions later. A reading by eye found the path close to
     linear interpolation between the regimes' ratios. Calibration windows of 10, 20, 60 and 120
     dates rank in that order in regime C.
2. **Exploratory simulations of each proposition**, run in a scratch session. These covered:
   * the small-noise constants of Parkinson, Rogers–Satchell and Garman–Klass;
   * the censoring factor;
   * the lag formula;
   * the instrumented calibration under valid and invalid instruments.

   For Proposition 4 they used panels of 30–120 simulated securities:
   * **Common opening-error variance.** The full form had the lower loss. Each security's loss
     difference was uncorrelated with its own b (Spearman −0.03 and +0.04).
   * **Opening-error variances spread over two orders of magnitude.** The open-free form had the
     lower loss, and all of its advantage came from the level component; the full form kept the
     lower shape loss. The loss difference fell with own b (Spearman −0.47 and −0.37).
   * **A dropped predictor.** An earlier candidate, |b_i − b̄|, was not diagnostic in those
     simulations. It was dropped before this plan was written.
3. **Nothing in Part C has been computed on any real panel.** No security's loss under either
   form, and no security-level b on a training span, has been computed.
4. **An error found while deriving Proposition 1.** Appendix A of the manuscript gives the bound
   E[η²] ≥ E[o²]((√(5 − 4b) − 1)/2)². It says the bound is attained when η is perfectly
   correlated with news. It is not attained. The sharp bound is (1 − b)²E[o²], and its value under
   perfect correlation is exactly that. This is registered as M-026 and corrected in this series
   of commits. The published bound remains valid but is not sharp.

## Part A — verifying the propositions (binding on the text)

Each closed form, identity and inequality in Propositions 1–6 is compared with a simulation or a
numerical integral by `scripts/45_theory_checks.py`. The comparisons are listed in the ledger
`table121_theory_checks.csv`.

| Kind of claim | Pass rule |
|---|---|
| Algebraic identity | Holds to a relative error of 1e-9 |
| Closed form against Monte Carlo | Within 4 Monte Carlo standard errors |
| Closed form against a numerical integral | Within 1e-6 |
| Asymptotic (n → ∞) or small-noise statement | Error shrinks as the design approaches the limit, and is within the stated tolerance at the largest design |
| Inequality | Holds in every design |

* **Paths.** Brownian extremes are simulated with an exact Brownian-bridge maximum and minimum
  within each step.
* **Seeds.** Seeds are fixed at 20261009 plus an offset per check.
* **Failures.** A failure means the statement is wrong. It is corrected or withdrawn before the
  LaTeX is final, and the ledger records both the failure and the correction.

The script also writes `paper/theory/generated/numbers.tex`. Every number quoted in the LaTeX is a
macro defined there and is never typed by hand.

## Part B — applications (reported, no decision)

### B1 (Proposition 1)

* **What is reported.** By NEPSE regime and for the NIFTY 50: the sharp lower bound on the
  opening error's share of the proxy, (1 − b)²E[o²]/E[OC]. It is reported beside the published
  bound and the value under independence, (1 − b)E[o²]/E[OC].
* **How intervals are computed.** With the joint bootstrap of M14/M15 (`scripts/34::joint_bootstrap`,
  seed 20261007, 499 replicates), over the same rows as `table97`.

### B2 (Proposition 2)

This compares two estimates of the error's scale relative to the session's efficient volatility,
σ_η/σ_c:

* **From the share s of non-stale opens that are the session's high or low.** Under Assumption B
  with Gaussian η, the scale is tan(πs/2).
* **From b under independence.** The scale is √(x/(1 − x)), with x = (1 − b)E[o²]/E[OC].

Both are arithmetic on `table97`. The reading is fixed now: if the arctan-implied scale is larger,
the open is a session extreme more often than an instantly corrected Gaussian error explains. That
points to discrete trading or slow correction, not to a larger error.

### B3 (Proposition 3)

These are arithmetic on `table89`, already seen.

* **The censoring factor.** For A1, B and A2 (the ±2% band), the Gaussian factor F(k) is
  compared with the observed b/b_interior. Here k = Φ⁻¹(1 − π/2), with π the pinned share among
  non-stale opens.
* **The pinned ratio.** The Gaussian ratio of pinned to interior b, λ(k)/k (λ the inverse Mills
  ratio), is compared with the observed ratio.
* **The decomposition.** The exact three-term decomposition of ln(b_A2/b_C):
  * censoring under the old band, ln(b_A2/b_int,A2);
  * the interior change, ln(b_int,A2/b_int,C);
  * departure from linearity in C, ln(b_int,C/b_C).

### B4 (Proposition 5)

This uses NEPSE with the frozen Anam kernel and its 60-date pooled calibration. For the sessions of
regime C it reports:

* **The predicted calibration path.** It is ω_t ρ₁ + (1 − ω_t) ρ₀:
  * ρ₀ is the ratio Σr²/ΣA over the 60 dates before 2026-04-20;
  * ρ₁ is the same ratio over C;
  * ω_t is the post-reform share of the window's kernel mass.
* **Its fit to the applied path.** The RMSE, and the share of Σ(κ_t − ρ₁)² that the prediction
  explains.
* **The linear-weight approximation**, ω = min((j+1)/60, 1).
* **The variance per date of the calibration's log**, v. It is the Newey–West long-run variance
  (10 lags) of z_s = (R_s − ρA_s)/(ρĀ) over the regimes before the reform, each with its own ρ.
* **The bias–variance window.** L\* = √(3vT/Σδ_b²) from the three regime boundaries of M14 (δ_b
  the log change in the regime ratio).
* **Predicted loss differences** between calibration windows of 10, 20, 60 and 120 dates over C,
  against `table106`. Their order is known, so this is a consistency check, not a test.

## Part C — the test: one b pooled across securities whose opens differ (Proposition 4)

### Samples

There are five panel test spans, as frozen in M16–M18:

* NEPSE `A2+C`;
* `DSE 2023-2026`;
* `Vietnam 2007-2020`;
* `DSE 2009-2021`;
* `Morocco 2012-2026`.

Each is taken at windows of 5 and 21 sessions, which makes ten cases. The two indices are excluded,
since nothing is pooled across securities there.

### Forecasts and per-security statistics

* **The forecasts** are exactly those of the frozen fair forecast test. They are rebuilt row by
  row by `scripts/44::forecast_rows` with the nine-estimator set of `scripts/40::estimator_set`.
  They are those of "Anam" (the full form) and "Anam, open-free special case (b=0)", on their
  common scored rows.
* **For each security** with at least 20 scored test rows at that window:
  * loss_i: its mean QLIKE under each form;
  * c\*_i = mean(Y/f);
  * level_i = c\*_i − 1 − ln c\*_i, the loss removed by rescaling that security's forecasts
    optimally;
  * shape_i = loss_i − level_i.

  The decomposition is exact.
* **b_i** is the security's own Σor/Σo² over its training-span rows. At least 60 of those rows
  must have o ≠ 0.
* **d_i** is loss_i(full) − loss_i(open-free).

### P4a — mechanism (descriptive)

* **What is computed.** The row-weighted means Δtotal, Δlevel and Δshape (full minus open-free).
* **Prediction.** Wherever Δtotal > 0, Δlevel > 0 and Δlevel ≥ Δtotal. That is, the open-free
  form's advantage is a level advantage, and the full form keeps the better or equal shape.
* **Reading.**
  * *Supported* if this holds in every case with Δtotal > 0.
  * *Partly supported* if it holds in a majority of them.
  * *Not supported* otherwise.

### P4b — cross-section (the test)

* **What is computed.** Spearman's correlation between d_i and b_i, with a 95% percentile interval
  from 1,999 resamples of securities (seed 20261009).
* **Prediction.** Negative: the open-free form gains most where the security's own open is
  noisiest.
* **Verdict per case.**
  * *Confirmed* if the interval lies below zero.
  * *Not detected* if it contains zero.
  * *Reversed* if it lies above zero.
* **Overall.**
  * *Supported* if a majority of the ten cases are confirmed and none is reversed.
  * *Not supported* otherwise.

The ten cases are reported without a multiplicity adjustment, and that is stated.

### Also reported, not decided

* Spearman's correlation of level_i(full) − level_i(open-free) with b_i.
* P4b with b_i measured on the test span instead of the training span.

## Outputs

| File | Contents |
|---|---|
| `output/tables/table121_theory_checks.csv` | Part A ledger: one row per check |
| `output/tables/table122_theory_applications.csv` | Part B |
| `output/tables/table123_theory_pooling.csv` | Part C: per-case statistics and verdicts |
| `paper/theory/generated/numbers.tex` | The LaTeX macros |

## Wording rules (binding)

1. **Labels.** The theory is labelled post hoc relative to M14–M18. Part C is labelled
   "theory-motivated, prediction fixed before computation".
2. **Assumptions.** Each proposition holds under its stated assumptions. The applications do not
   test those assumptions except where Part C says so.
3. **No novelty claimed for standard tools.** These are:
   * the best-linear-predictor and attenuation algebra of errors in variables;
   * Stein's lemma;
   * the reflection principle and the joint law of Brownian extremes;
   * Gordon's inequality for the Gaussian tail;
   * GMM asymptotics;
   * the bias–variance choice of an estimation window under breaks (Pesaran & Timmermann, 2007).

   What is claimed is their application to the daily bar with a noisy open, and the specific
   results that follow.
