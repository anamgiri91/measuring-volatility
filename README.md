# When the Open Overreacts: Measuring Daily Volatility in Frontier Markets without Options

*Evidence from Nepal's Pre-Open Band Reform and an Estimator Tested in Four Frontier Markets*

This repository holds the manuscript, code, frozen outputs and reproducibility package for the paper.
Earlier versions circulated as *Calculating Volatility in Frontier Markets Without Options*, *Daily OHLC
Volatility Measurement in a Cash-Only Frontier Market* and, in round 14, *When the Open Overreacts:
Measuring Daily Volatility in a Frontier Market without Options — Evidence from a Pre-Open Band Reform
on the Nepal Stock Exchange*.

## The paper in brief

Nepal has no exchange-traded options and no public intraday data, so volatility has to be measured from
each day's open, high, low and close. The paper answers five questions:

1. **Do range estimators survive thin trading?** Against benchmarks matched in scope, sample and horizon,
   on 292 ordinary equities and 143,718 stock-days, they do. The apparent failure of range estimators in a
   pooled frontier-market file is mostly an instrument-composition artifact: bonds, funds and promoter
   shares mistaken for thin stocks.
2. **Is their agreement with the benchmark calibration or cancelling errors?** A unit calibration slope is
   not rejected: instrumented slopes put Parkinson at 0.919 [0.760, 1.056]. That rests on instruments whose
   validity is assumed, and whose first stage is weak once errors are clustered by security and date
   (effective F 19.4; 29.9 for instruments dated two sessions back).
3. **What does the opening price measure?** Mostly a transient error. The trading session undoes
   64–87% of NEPSE's overnight move (1 − b, a projection pooled across securities and dates). When NEPSE's
   20 April 2026 rule package widened its pre-open band, among other changes, the share of the open that
   survives to the close fell by 0.333, more than at any of 77 placebo dates. The band's separate effect is
   not identified. Three-quarters of Yang–Zhang's excess over close-to-close
   variance is the overnight–intraday covariance it assumes away.
4. **So which benchmark survives?** Close-to-close returns, which never read the open.
5. **Can an estimator do better?** **Anam's estimator**, introduced in Section 6.8 of the paper, was
   designed on part of the NEPSE sample and tested out of sample under three frozen plans, in Nepal,
   Bangladesh, Vietnam and Morocco and on the NIFTY 50 and S&P 500 indices. An independent audit then found
   defects in that forecast evaluation. The corrected evaluation (plan M20) finds:
   * its open-free form beats plain close-to-close at five sessions in six of seven samples;
   * forecasts built from returns alone are about as accurate in most of them (below).

The forward India VIX test and the calibration, opening-price and estimator analyses (questions 2 to 5)
ran under plans frozen and committed before their results existed; the earlier estimator comparison and
its robustness checks did not. The predictions that failed are reported alongside the ones that held.

The record of checks and corrections:

* **A post hoc recheck** of every claim made for the estimator: [`ANAM_RECHECK_POSTHOC.md`](ANAM_RECHECK_POSTHOC.md).
* **An independent audit of 9 October 2026**, kept as received in [`audits/`](audits/), and the answer to each
  of its fifteen findings: [`RESEARCH_AUDIT_RESPONSE.md`](RESEARCH_AUDIT_RESPONSE.md).
* **What each claim is about**, and what it is not: [`ESTIMAND_NOTE.md`](ESTIMAND_NOTE.md). For example, the
  forecast comparisons concern the second moment of observed close-to-close returns, not integrated variance.
* **A prospective test** on sessions after the audit, with every parameter frozen now:
  [`M21_PROSPECTIVE_PLAN.md`](M21_PROSPECTIVE_PLAN.md).

**The theory.** The statistics behind these answers are in a theory supplement written in LaTeX,
[`paper/theory/theory.pdf`](paper/theory/theory.pdf). It states seven propositions, with proofs:

1. what the open's unbiasedness coefficient b identifies, with a sharp bound on the opening error
   that corrects the paper's Appendix A;
2. how much of that error each classical estimator absorbs;
3. what a price band does to b;
4. why one b pooled across securities penalises reading the open;
5. how a rolling calibration lags a rule change;
6. when lagged realised measures identify an estimator's calibration;
7. what Anam's kernel does with a noisy open, added after the audit:
   * its overnight term understates the efficient overnight second moment unless the opening error is
     proportional to the move;
   * the extended range cannot remove an error already in the high or low;
   * the open-free form still absorbs about a quarter to two-fifths of the error's variance.

`scripts/45_theory_checks.py` checks every closed form, identity and inequality against simulation or
numerical integration (187 checks, all passing). `scripts/48_kernel_theory.py` does the same for the seventh
proposition (63 checks, all passing). `scripts/46_theory_proofs.py` then verifies every step of every proof,
together with the paper's own mathematical claims (321 steps, all passing). Of those steps, 166 are verified
symbolically with SymPy; the rest numerically, by simulation, pathwise or on the data. The supplement's one prediction about real data was
fixed in advance under [`M19_THEORY_CHECKS_PLAN.md`](M19_THEORY_CHECKS_PLAN.md) and was not
supported.

## Anam's estimator

Classical daily-bar estimators either trust the opening price completely (Garman–Klass, Rogers–Satchell,
Yang–Zhang) or ignore it (Parkinson, close-to-close). Anam's estimator instead **measures how far the open
can be trusted**, then reads it only that far. (Hansen and Lunde (2005) also weight the overnight return
by an amount estimated from data, chosen for efficiency from intraday returns; here the weight is the
open's unbiasedness coefficient, from daily bars alone.) For a bar (O, H, L, C) with previous close PC,
write o = ln(O/PC), r = ln(C/PC), h = ln(H/PC), l = ln(L/PC) and R = ln(H/L).

| Step | Definition |
|---|---|
| Open quality | b = Σ o·r / Σ o², clipped to [0, 1]: the share of the overnight move the session keeps on average, a projection pooled over the cross-section and the last 60 dates in which large opening moves weigh most (a single series uses its own last 250 sessions). b·o is a shrinkage predictor of the efficient overnight log move, not the move itself |
| Extended range | R* = R + max(0, b·o − h) + max(0, l − b·o): the range extended to the effective open PC·exp(b·o) |
| Daily kernel | A = (1 − w)·[(b·o)² + R*²/(4 ln 2)] + w·r², with w = 0.2·(1 − b) |
| Calibration | κ = Σ r² / Σ A over the same trailing set, which puts the level on the close-to-close scale |
| Window variance | σ̂² = κ × mean(A) over the window |

**Two forms.**

- **Full form** (b measured from the data). Where the open is close to unbiased, b ≈ 1 and the estimator
  approaches overnight² + Parkinson. On the S&P 500, whose index open lags the overnight move (b above
  one, capped at one), it *is* overnight² + Parkinson. Of the two forms it had the lower loss on the
  NIFTY 50 and the S&P 500, though not significantly.
- **Open-free form** (b set to 0). It becomes 0.8 × true-range Parkinson + 0.2 r² and reads only the
  previous close, the high, the low and the close. Of the two forms it did better wherever the open was
  unreliable (b well below one), as in every frontier market tested. In NEPSE neither form beat
  close-to-close, which remains the primary measure there.

### Using it

Install the standalone package (Python 3.9 or later; it needs only numpy and pandas):

```bash
pip install "anam-estimator @ git+https://github.com/anamgiri91/measuring-volatility.git#subdirectory=anam-estimator"
```

```python
import pandas as pd
from anam_estimator import AnamModel, anam_estimator

prices = pd.read_csv("prices.csv")   # date, open, high, low, close (+ symbol for several securities)

est = anam_estimator(prices, form="open-free", annualize="observed")   # the estimate on every bar
model = AnamModel(form="open-free", horizon=5).fit(prices)            # a fitted forecasting model
print(model.forecast())                                               # the next 5 sessions, per security
```

The package also offers a command line (`anam-estimator prices.csv --form open-free`), a backtest, a way
to save fitted models, and simulated data to try it on (`simulate_bars()`).
[`anam-estimator/README.md`](anam-estimator/README.md) covers input formats, the two forms, the model
and its model card. Annualise with the market's own session count (`annualize="observed"`), not an
imported 252.

Inside this repository, `src/nepsevol/estimators/anam.py` is the original that produced the paper's
tables, with property tests in `tests/test_anam_estimator.py`.

* **The estimator.** The package reproduces it exactly.
* **The forecasting model** (version 0.2.0). It uses the corrected evaluation of plan M20: outcomes purged at
  the training cutoff, calendar targets, zero targets scored. `tests/test_anam_package.py` checks both against
  the research code.

The construction is a heuristic whose level the calibration sets (theory supplement, Proposition 7).

### How it did out of sample

**The corrected evaluation (plan M20, paper Table 39).** An independent audit (9 October 2026) found four
defects in the forecast evaluation of plans M16–M18:

* training outcomes crossed into the test span;
* 5- and 21-session targets stitched sessions across trading gaps;
* zero targets were dropped;
* the reported mean and its t statistic weighted forecast origins differently.

Plan M20 was frozen before any corrected loss was computed. It removes the four defects and adds:

* forecasts built from returns alone: EWMA, GARCH, GJR-GARCH, and a HAR on squared returns;
* true-range Parkinson;
* a HAR on the open-free kernel;
* a model confidence set over all seventeen forecasts.

Every forecast predicts the mean squared close-to-close return over the next 5 sessions and is scored by QLIKE
(lower is better). A negative t favours the first-named forecast, and |t| > 1.96 is significant.

| Test sample | Anam vs CC: t | Open-free vs CC: t | Holm p (Anam / open-free) | Best return-only | Best range-based | Range-based minus return-only: t | Lowest test loss of 17 |
|---|---|---|---|---|---|---|---|
| NEPSE, regimes A2 and C | +0.82 | +0.63 | 1.000 / 0.736 | GARCH | HAR on the open-free kernel | +0.35 (no significant difference) | HAR on r² |
| NIFTY 50 (index) | -2.91 | -2.99 | 0.009 / 0.006 | GJR-GARCH | HAR on the open-free kernel | -0.08 (no significant difference) | HAR on the open-free kernel |
| S&P 500 (index) | -6.08 | -6.65 | 0.000 / 0.000 | GJR-GARCH | HAR on the open-free kernel | -1.18 (no significant difference) | true-range Parkinson |
| Dhaka 2023-2026 | +1.45 | -2.56 | 1.000 / 0.013 | GJR-GARCH | HAR on the open-free kernel | +2.66 (returns suffice) | GJR-GARCH |
| Vietnam 2007-2020 | -0.86 | -3.94 | 0.785 / 0.000 | GARCH | HAR on the open-free kernel | -1.51 (no significant difference) | HAR on the open-free kernel |
| Dhaka 2009-2021 (dates repaired) | -6.52 | -8.02 | 0.000 / 0.000 | GJR-GARCH | HAR on the open-free kernel | -6.31 (range adds information) | HAR on the open-free kernel |
| Morocco 2012-2026 | -0.53 | -2.62 | 0.890 / 0.013 | HAR on r² | HAR on the open-free kernel | -2.30 (range adds information) | HAR on the open-free kernel |

**What this shows:**

- **Against the classical estimators.** A classical range estimator beats the full form in 1 of 84 primary
  comparisons (Parkinson in Dhaka 2023–2026 at 5 sessions) and beats the open-free form in none. Of the frozen
  record's 288 per-rival verdicts, 47 change.
- **Against plain close-to-close.** After Holm's adjustment across the seven samples:
  - the open-free form wins at 5 sessions in six of seven, all but NEPSE;
  - the full form wins in three: Dhaka 2009–2021 and both indices.
- **Against forecasts built from returns alone.** The best range-based forecast beats the best return-only
  one in Dhaka 2009–2021 and Morocco only, and Morocco's verdict depends on how securities and dates are
  weighted. Returns suffice in Dhaka 2023–2026 and after NEPSE's reform. Elsewhere there is no detectable
  difference.
- **The best single forecast** is a HAR on the open-free kernel. It has the lowest test loss in 10 of 14
  sample-horizon cells and is in every 90% model confidence set. So is GJR-GARCH; plain close-to-close is in
  only six.
- **What helps** (ablations):
  - calibration;
  - the previous-close anchor (true range);
  - the 0.2 r² blend;
  - leaving the open out. Estimating b never beats setting it to zero.

  The overnight term with residual uncertainty from the theory supplement's Proposition 7 does not help.
- **After a sudden rule change, use close-to-close.** The 60-date calibration needs time to catch up.
- **Coverage.** Thin securities are under-represented, because a target over sessions without trading cannot
  be scored. In Morocco's least liquid tercile, only 44% of 5-session origins are.

**Forecasts, as the plans found them.** Each estimator forecasts the next 5 sessions' close-to-close variance and is scored by
QLIKE loss (lower is better). Every estimator gets the same calibration and its own shrinkage, and all
are scored on common forecast origins. A negative t favours the estimator; |t| > 1.96 is significant.
The table is paper Table 34, which also reports the 21-session horizon. These are the plans' results, with the defects the audit found; in the Bangladeshi, Vietnamese and Moroccan panels the loss levels also include floating-point residues of equal prices, which inflate them (the full form's by 0.02 to 0.19; post hoc, `scripts/51_frozen_residue_check.py`).

| Test sample | Plan | Close-to-close | Parkinson | Best other classical | Anam | Anam, open-free | Anam vs CC: t | Open-free vs CC: t |
|---|---|---|---|---|---|---|---|---|
| NEPSE, regimes A2 and C | M16 | 0.6478 | 0.6764 | Garman-Klass 0.6904 | 0.6637 | 0.6585 | +1.19 | +0.93 |
| NIFTY 50 (index) | M16 | 0.4725 | 0.4546 | overnight² + Garman-Klass 0.4373 | 0.4314 | 0.4374 | -3.07 | -3.31 |
| S&P 500 (index) | M16 | 0.5219 | 0.4631 | Garman-Klass 0.4575 | 0.4648 | 0.4681 | -6.39 | -7.10 |
| Dhaka 2023-2026 | M17 | 0.6341 | 0.6520 | Garman-Klass 0.6513 | 0.6316 | 0.6273 | -0.90 | -2.55 |
| Vietnam 2007-2020 | M17 | 0.7699 | 0.8225 | overnight² + Parkinson 0.7937 | 0.7705 | 0.7629 | +0.20 | -3.58 |
| Dhaka 2009-2021 (dates repaired) | M17 | 0.6214 | 0.6162 | overnight² + Parkinson 0.6228 | 0.6044 | 0.6008 | -6.17 | -8.30 |
| Morocco 2012-2026 | M18 | 0.6784 | 0.7352 | overnight² + Parkinson 0.6794 | 0.6706 | 0.6633 | -2.06 | -4.53 |

Against close-to-close these verdicts depend on the loss function. Under MSE, a post hoc check,
close-to-close beats both forms in Vietnam, while both forms beat close-to-close in NEPSE's holdout and on
the S&P 500 (paper Table 37).

**Level.** The table shows the 21-session variance divided by close-to-close variance on each test span
(paper Table 35). Anam's estimator is calibrated; the classical estimators are raw. Given the same
calibration, every classical range estimator is also within 2.2% of close-to-close variance outside
regime C (paper Table 38), so the level comes from the calibration, not from the kernel.

| Test sample | Anam (calibrated) | Parkinson | Garman-Klass | overnight² + Parkinson | Yang-Zhang (daily form) |
|---|---|---|---|---|---|
| NEPSE, regime A2 | **1.011** | 1.155 | 1.161 | 1.493 | 1.583 |
| NEPSE, regime C (after the reform) | **1.195** | 1.669 | 1.594 | 2.761 | 2.848 |
| NIFTY 50 (index) | **1.011** | 0.606 | 0.594 | 1.014 | 0.998 |
| S&P 500 (index) | **1.009** | 0.660 | 0.579 | 0.698 | 0.645 |
| Dhaka 2023-2026 | **1.002** | 1.128 | 1.116 | 1.662 | 1.709 |
| Vietnam 2007-2020 | **1.009** | 0.721 | 0.633 | 1.556 | 1.594 |
| Dhaka 2009-2021 (dates repaired) | **1.004** | 0.995 | 0.988 | 1.392 | 1.418 |
| Morocco 2012-2026 | **1.005** | 0.544 | 0.453 | 1.283 | 1.273 |

**What the frozen record showed.** It is superseded where the corrected evaluation differs:

- **Against the classical estimators.** Under the plans' QLIKE loss, no classical range estimator had
  significantly lower loss than Anam's estimator. Two caveats: on the S&P 500 it coincides with
  overnight² + Parkinson, and under MSE the three classical estimators with a full overnight term beat it in
  Vietnam at 21 sessions.
- **Level.** Its level is within 1.1% of close-to-close variance everywhere except NEPSE's post-reform regime.
  That is the calibration's doing: uncalibrated, the classical formulas miss by up to 71% upward and 55%
  downward, but calibrated the same way they come within 2.2%. The audit's corrections do not touch the level
  comparisons.
- **The open-free form.** It had the lowest 5-session loss of the plans' nine estimators in every M17 panel,
  a post hoc reading, and then passed a test fixed in advance in Morocco (M18).

Details: paper Section 6.8 and Tables 33–39; `M20_CORRECTED_EVALUATION_*` (the corrected evaluation); `M16_ANAM_ESTIMATOR_*`, `M17_ANAM_FRONTIER_*` and
`M18_ANAM_MOROCCO_*` (plan and results for each test); `ANAM_RECHECK_POSTHOC.md` (the post hoc recheck).

## Manuscript and submission set

- **The manuscript.** `paper/NEPSE_Volatility_Manuscript_Revised_2026-09.docx` is the canonical editable source.
  Its revisions since the pre-revision draft are recorded as scripts: `paper/apply_referee_revisions.py`, then
  rounds 3–19, applied in order. The pre-revision draft is not distributed (it is the `--base` those scripts
  require), so the scripts document every edit and its checks rather than rebuild the file from nothing. Round 15
  (`paper/apply_round15_revisions.py`) adds Anam's estimator: Section 6.8, Tables 33–36, a new title, and
  changes to the abstract, introduction, protocol, discussion, limitations, conclusion and references.
  Round 16 (`paper/apply_round16_revisions.py`) corrects what a recheck of those claims found
  (`AUDIT-REGISTER.md` M-020 to M-025) and adds the post hoc recheck as Tables 37–38. Round 17
  (`paper/apply_round17_revisions.py`) corrects Appendix A's bound on the opening error, which the
  theory supplement showed is not sharp (M-026), and points Section 9 to the supplement. Round 18
  (`paper/apply_round18_revisions.py`) states Appendix A's attainment condition exactly (M-027) and
  adds the step-by-step verification to Section 9. Round 19 (`paper/apply_round19_revisions.py`) answers the
  audit of 9 October 2026 (M-028 to M-034). It:
  - frames Tables 34–38 as the plans' record and adds the corrected evaluation as Table 39;
  - corrects the overstated wording ("natural experiment", "genuine calibration", the QLIKE target, the
    reading of b·o);
  - adds Proposition 7 and the prospective plan M21 to Section 9;
  - says which results the package reproduces.
- **The theory supplement.** `paper/theory/` holds the LaTeX theory section and its proof appendix,
  with the compiled `theory.pdf`. Every number in it is a macro written to `paper/theory/generated/` by
  `scripts/45_theory_checks.py`, `scripts/46_theory_proofs.py` and `scripts/48_kernel_theory.py`. Build it with
  `latexmk -pdf theory.tex` in that directory.
  Every figure the manuscript quotes is interpolated from `output/tables/*.csv`.
- **The submission set.** `paper/submission/` is the double-anonymous submission set, rebuilt by
  `paper/build_submission_set.py`. Because the estimator carries the author's name, the anonymous copy
  calls it "the proposed estimator", and the build fails if any trace of the name survives in that file.
  The reproducibility package itself still names the estimator. For double-anonymous review, withhold
  the package link or supply an anonymised copy.

## Reproducing the results

### Environment

The reference environment, recorded in `data/processed/BUILD-MANIFEST.json`, is **Python 3.14.6**
on macOS arm64 with the exact pins in `requirements.txt`.

The pipeline is additionally verified on **Python 3.12 / x86-64 Linux**, where all frozen tables
and figures reproduce byte-identically under the next-nearest available package versions.
Round 14 reran every producer step in a clean copy on **Python 3.13.16 / numpy 2.5.3 / x86-64
Linux**: every manuscript-facing table, `PAPER_RESULTS_CHECK.csv` and every M14/M15 table
reproduced byte-for-byte, and 36 earlier intermediate tables differed only in floating-point
rounding (largest relative difference 9e-13; one Spearman correlation by 1e-7 through near-tie
ordering), consistent with the newer numpy build. The committed outputs remain the
reference-environment ones. The supported floor is Python 3.12; `pyproject.toml` declares the dependency floors and
`requirements.txt` is the exact lock for the reference environment.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
pip install -e .
```

Then run:

```bash
bash run_paper_analysis.sh
pytest -q
```

The paper-facing pipeline intentionally starts from the included **processed CSV panel**. The original NEPSE stock-level downloads used to build that panel are not redistributed in this submission package because their redistribution terms are unresolved. `scripts/02_build_panel.py` is retained as the cleaning/build specification; it expects the original source files under `data/raw/stock-daily-long/` and `data/raw/stock-daily-trades/` if the author has lawful access to them, and exits with an explanatory message if they are absent.

### Analysis order

`run_paper_analysis.sh` runs these in order. Step 0 runs first because the classification decides
which securities are in the ordinary-equity universe, and step 10 runs last because it only
reformats what the others produce.

`scripts/30_repair_build_manifest.py` runs first (it depends on nothing) and repairs the build
manifest's provenance fields. Step 0 runs next because the classification decides which
securities are in the ordinary-equity universe. `scripts/28_panel_balance.py` and
`scripts/29_calendar_validation.py` run after step 1 (they read the equity sample) and before the
final formatting step, which runs last.

0. `scripts/27_classification_audit.py` — validates the rule-based instrument classification against the external NEPSE security master and writes the confusion table and disagreement list (paper Table 9).
1. `scripts/03_descriptive.py` — pooled/equity sample screens, descriptive tables, Figure 2 support, and the 94.3% stock-day composition audit.
2. `scripts/09_cross_market_control.py` — cross-market estimator fingerprint, India VIX co-movement anchor (full sample and NEPSE-overlap window), and the single-session sensitivity of the NIFTY benchmark (paper Figure 5; Tables 4, 13 and VIX statistics).
3. `scripts/12_benchmark_diagnosis.py` — matched-benchmark and variance-decomposition analysis (paper Figure 4).
4. `scripts/13_opening_auction.py` — opening-auction descriptive diagnostics (paper Figure 3).
5. `scripts/17_addrs_benchmark.py` — AddRS benchmark comparison (paper Figure 6 and Table 5).
6. `scripts/19_addrs_premise.py` — diagnostic checks underlying the AddRS interpretation.
7. `scripts/22_universe_composition.py` — instrument-composition result and one-row-per-security classification audit (paper Figure 1).
8. `scripts/24_duplicate_key_reconciliation.py` — Section 3 duplicate-count reconciliation.
9. `scripts/26_robustness.py` — predetermined-liquidity sorting, multiway-cluster bootstrap intervals, all six named estimators against scope- **and row-**matched **and horizon-matched** benchmarks (with a stated, post hoc ±5% equivalence-margin verdict reported across a margin grid), OHLC-repair sensitivity, the previous-close reconciliation and corporate-action-adjusted previous close, the stationary block-date bootstrap, and the NEPSE annualisation factor.
10. `scripts/28_panel_balance.py` — security-level and lagged liquidity quintiles, conditional panel-balance/fill-rate, the extreme thin tail (Table 11), and information-content (Pearson/Spearman) correlations (Table 14).
11. `scripts/29_calendar_validation.py` — the detected trading calendar cross-checked against an independent session record, and its sensitivity to the staleness threshold (Table 16).
12. `scripts/31_lagged_thinness_screen.py` — the lagged, outcome-independent liquidity screen for the thin tail and its sensitivity grids (Tables 21-22).
13. `scripts/32_vix_forward_validation.py` — India VIX as a forward forecast of realised NIFTY volatility, lead-lag profile, overlapping-window sensitivity, and the reconciliation of the circulated 0.776/0.832 correlations (Tables 23-25).
14. `scripts/34_instrumented_calibration.py` — M14, frozen plan: instrumented calibration slopes, additive shares, the empirical composite, regimes, NIFTY with India VIX as an external instrument, and the decision ledger (Tables 74-86 of the package; manuscript Table 29, Figure 7). About ten minutes.
15. `scripts/35_calibration_simulation.py` — M14's Monte Carlo validation where the truth is known (package Tables 74-77). About ten minutes.
16. `scripts/36_calibration_exploratory.py` — M14 post hoc follow-ups E1 and E2, labelled as such (package Tables 87-88).
17. `scripts/37_opening_price.py` — M15, frozen plan: the unbiasedness coefficient of the open, the band-reform event window and placebo breaks, dose-response, mechanism, estimator evaluation, the Yang-Zhang decomposition, NIFTY, and the decision ledger (package Tables 89-96; manuscript Tables 30-32, Figure 8).
18. `scripts/38_opening_price_exploratory.py` — M15 post hoc follow-ups X1-X6, labelled as such (package Table 97).
19. `scripts/39_anam_development.py` — Anam's estimator, DEVELOPMENT evidence on NEPSE regimes A1 and B and simulated panels, including rejected alternatives (package Tables 98-100b).
20. `scripts/40_anam_holdout.py` — M16, frozen plan: the holdout on NEPSE A2 and C, NIFTY 50 and the S&P 500 (`arch` package data), and the decision ledger (package Tables 101-105).
21. `scripts/41_anam_posthoc.py` — M16 post hoc follow-ups Y1-Y2 on calibration speed after the band reform, labelled as such (package Tables 106-106b).
22. `scripts/42_anam_frontier.py` — M17, frozen plan: Anam's estimator on the Dhaka and Vietnam panels and the decision ledger (package Tables 107-111). Needs the third-party inputs under `data/external/frontier/` (see `data/external/README.md`); `run_paper_analysis.sh` skips it when they are absent.
23. `scripts/43_anam_morocco.py` — M18, frozen plan: both forms of Anam's estimator on the Casablanca panel, by band regime, and the decision ledger (package Tables 112-116). Needs `data/external/frontier/casablanca/`; skipped when absent.
24. `scripts/44_anam_recheck.py` — POST HOC recheck of the M16-M18 claims, run after every verdict was known: every estimator under the same calibration, longer Newey-West lags, non-overlapping origins, an MSE loss, halves of each test span, Holm corrections, and the data assumptions (package Tables 117-120; paper Tables 37-38). Needs `data/external/frontier/`; skipped when absent.
25. `scripts/45_theory_checks.py` — plan M19: every proposition of the theory supplement checked against simulation or numerical integration (Part A), its applications to the NEPSE data (Part B), and the pooling test across the five panel test spans (Part C) (package Tables 121-123; `paper/theory/generated/`). Post hoc relative to M14-M18; Part C needs `data/external/frontier/` and is skipped with the script when absent. About five minutes.
26. `scripts/46_theory_proofs.py` — every step of every proof in the theory supplement, and the paper's own mathematical claims. Each step is verified symbolically with SymPy where it is algebra or calculus, and otherwise numerically, by simulation, pathwise or on every NEPSE stock-day it applies to (package Table 124; `paper/theory/generated/proofs.tex`). It reads script 45's committed outputs, so it always runs. About two minutes.
27. `scripts/47_corrected_evaluation.py` — plan M20, frozen: the forecast evaluation of M16–M18 corrected step by step (S0 must reproduce the frozen tables), seventeen forecasts with return-only baselines, the model confidence set, Holm, the practical margin, ablations, coverage by liquidity and inference sensitivity (package Tables 125–132; manuscript Table 39). Needs `data/external/frontier/` for four of its seven samples; skipped when absent. About twenty minutes.
28. `scripts/48_kernel_theory.py` — the theory supplement's Proposition 7: how much of the opening error each kernel absorbs, checked against simulation and numerical integration, and the exposures at each sample's implied scales (package Tables 133–134; `paper/theory/generated/kernel.tex`). Its Part C needs `data/external/frontier/`; skipped when absent.
29. `scripts/49_audit_sensitivities.py` — POST HOC, after the audit: the calibration weight's floor without future observations, the cluster-robust and effective first-stage F, the corporate-action tolerance, and the processed row counts (package Table 135). Reads the NEPSE sample only, so it always runs.
30. `scripts/50_m21_freeze.py` — plan M21: every forecast's parameters fixed on all current data for the prospective test (package Table 136, whose digest the plan records). It never overwrites the frozen table: a rerun reports whether it reproduces it. Needs `data/external/frontier/`; skipped when absent.
31. `scripts/51_frozen_residue_check.py` — POST HOC: floating-point residues of equal prices in the frozen forecast tables, and those tables recomputed with the residues set to zero (package Table 137). Needs `data/external/frontier/`; skipped when absent.
32. `scripts/25_submission_tables.py` — manuscript-facing Tables 1, 3–39, and the `PAPER_RESULTS_CHECK.csv` QA ledger. **Runs last**: it reads the artifacts produced by every step above.

A run without `data/external/frontier/` is a **partial reproduction**. It regenerates every NEPSE and index result, reuses the committed tables of the skipped analyses, and writes what ran and what was skipped to `output/run_status.json`, which the manifest copies.

## Implementation conventions

- The 21-session Parkinson series is computed as `sqrt(A * rolling_mean(daily_variance))`; daily standard deviations are **not** averaged.
- Intraday range estimators are compared with an open-to-close benchmark. The cross-market and AddRS ratio scripts use the open-to-close **second moment**; the variance-decomposition script uses sample variance because the decomposition is stated in variance terms. The difference is numerically small in this sample, but the distinction is explicit here and every ratio is produced by a helper in `nepsevol.estimators.ratios` that returns its scale.
- **Estimator code is identical across regimes; input screens are not.** The NEPSE panel passes positivity, return and rules-derived range screens plus duplicate reconciliation and envelope repair. NIFTY 50 and the NEPSE index are read with a positivity filter only, because the NEPSE screens are derived from NEPSE's own price-limit rules and have no NSE analogue. Any sentence describing the cross-market comparison must say "identical estimator code".
- Annualisation uses the market's own genuine session count. `scripts/26_robustness.py` derives **A ≈ 229.6 sessions/year** for NEPSE from the detected trading calendar; 252 appears only in the NIFTY block of `scripts/09`, where it is the correct NSE convention.
- **April 2026 was two reforms, not one, and they have two dates.** The trading week moved from Sunday–Thursday to Monday–Friday effective **2026-04-06** (`nepsevol.trading_calendar.WEEK_REFORM`); the price band widened from ±2%→±5% and the daily limit from 10%→15% effective **2026-04-20** (`nepsevol.clean.limits.REGIMES`). Both were previously written as 2026-04-20, which put 6–19 April under the wrong calendar regime. The detected sessions are unaffected — the detector reads the data, not the schedule — but the schedule cross-check now labels those two weeks correctly, and the two Fridays and two Sundays in them are no longer recorded as off-schedule sessions and inferred holidays.
- Instrument classification is performed before interpreting the liquidity gradient, and is now **validated against an external NEPSE security master** (`scripts/27_classification_audit.py`): the rule and the master agree on **509 of 511** matched securities, 99.61%. The two disagreements are corrected — `ADBLB` is a bond the ticker rule read as equity, `NADEP` an ordinary equity it read as a promoter share — so the principal estimation universe is **292 ordinary equities / 143,718 stock-days**, up from 291 / 143,149.
- **Every ratio is evaluated on rows where both its numerator and its benchmark are defined, and — for Yang–Zhang — over the same horizon too.** Scope-matching a benchmark is not enough if the two series have different support: Yang–Zhang needs a 21-session window and close-to-close needs a previous session, so an unmatched comparison divided a mean over 137,107 rows by a mean over 142,858 (**1.245**). Matching rows alone raises it to **1.288** — but 1.288 still scores a 21-session estimator against a single session's squared return. Benchmarking it against close-to-close variance over its own 21-session window moves the figure to **1.273**, and adjusting the previous close for NEPSE's own corporate-action convention (below) — **on both sides of the comparison** — moves it to the adopted **1.280 [1.258, 1.303]**, which is what the manuscript reports. The previous close enters Yang–Zhang's own overnight term as well as the benchmark's close-to-close return; an earlier revision adjusted only the benchmark and reported the resulting mixed-definition ratio of 1.309, which no single specification produces (see `FOURTH_ROUND_AUDIT_RESPONSE.md`, audit register `R-022`).
- **315 previous-close disagreements are classified, not just counted.** `nepsevol.corporate_actions` finds that 214 of them are NEPSE's own ex-date reference-price adjustment (implied factors clustering at 1.05–1.30), 34 are within a rounding floor, 62 are unexplained upward revisions, and 5 span a session gap. The adopted previous close uses NEPSE's published value on the 214 corporate-action rows and the prior session's own close everywhere else.
- **A ratio near one is not evidence of daily tracking fidelity.** `nepsevol.equivalence` classifies every ratio against a stated ±5% margin — declared post hoc, applied consistently, and reported across a ±2.5/5/10% grid — instead of reading support from whether a CI contains one, and Pearson/Spearman correlation with the matched proxy is reported alongside every SD ratio — Parkinson and Rogers-Satchell sit within 0.04 of each other in SD ratio but correlate with the proxy at 0.70 vs. 0.21.
- **The two-way bootstrap resamples calendar dates independently and cannot see correlation between adjacent sessions.** `nepsevol.inference.ratio_of_sums_ci_block` adds a stationary block bootstrap over dates (Politis & Romano, 1994); it reduces the count of Table 7 estimators distinguishable from the matched proxy from 3 of 6 to 2 of 6.
- **A small extreme thin tail (4 securities) is reported separately from the thinnest liquidity quintile**, because the quintile's own median (100% participation) does not describe its own worst members (participation as low as 5.3%, zero-range up to 86%).
- **Overnight returns span exactly one genuine trading session.** `nepsevol.estimators.range_.previous_session_close` returns NaN across a gap; a plain `.shift(1)` would treat a 91-session absence as one overnight return, and 230 such transitions exist in the equity panel.
- **Inference clusters on security *and* date.** `nepsevol.inference` implements the multiway (pigeonhole) bootstrap; security-only intervals understate width by roughly a factor of two on this panel, because a market-wide shock moves every security on the same date.
- The India VIX exercise is external **co-movement** evidence, not a claim that historical OHLC volatility equals option-implied volatility, and not estimator validation.
- Liquidity buckets in Tables 4 and 5 are formed on **same-day** trade counts, which is endogenous. `scripts/26_robustness.py` reproduces them under two predetermined sorts and the manuscript reports both (Table 6); the gradient differs materially and the original must not be read causally.

## Data and licensing

The MIT `LICENSE` applies to code only. Data remain subject to their original source terms. The package includes the frozen inputs needed to reproduce the submitted paper's empirical outputs; do not assume that inclusion grants broader redistribution rights.

The frontier-market tests of Anam's estimator (M17, M18) read third-party files that are **not**
redistributed: the Dhaka Stock Exchange history, its public mirror, the Vietnam ticker files and the
Casablanca share files. `data/external/README.md` gives each file's source, its SHA-256 digest and how to
place it under `data/external/frontier/`. The scripts refuse a file whose digest differs. The S&P 500
series used by M16 is read from the `arch` package (version 8.0.0).

## Repository map

- `paper/NEPSE_Volatility_Manuscript_Revised_2026-09.docx` — **the revised manuscript**, rebuilt from the frozen output tables by the `paper/apply_*_revisions.py` scripts, applied in order (`apply_referee_revisions.py`, then rounds 3-19; the pre-revision draft they start from is not distributed, so the `.docx` itself is the canonical source). Round 14 (`apply_round14_revisions.py`) added Sections 6.6-6.7, Tables 29-32 and Figures 7-8 from the M14 and M15 analyses; round 15 (`apply_round15_revisions.py`) added Section 6.8 and Tables 33-36 on Anam's estimator from M16-M18; round 16 (`apply_round16_revisions.py`) corrects the overstatements a recheck found and adds Tables 37-38; round 17 (`apply_round17_revisions.py`) corrects Appendix A's bound on the opening error (M-026); round 18 (`apply_round18_revisions.py`) states its attainment condition exactly and cites the step-by-step verification (M-027); round 19 (`apply_round19_revisions.py`) answers the audit of 9 October 2026 and adds the corrected evaluation as Table 39 (M-028 to M-034). Every figure it quotes is interpolated from `output/tables/*.csv`, never typed by hand.
- `paper/submission/` — the double-anonymous submission set: anonymised manuscript (with the estimator's eponym replaced by "the proposed estimator"), separate title page, and a cover letter for each target journal (three field journals, then the referee's three recommendations), rebuilt by `paper/build_submission_set.py`.
- `paper/manuscript_as_reviewed_pre_revision.pdf` — the manuscript **as reviewed** (the PRE-revision PDF the first-round referee actually read), retained only so the revision can be checked against it. **This is not the current manuscript; `paper/NEPSE_Volatility_Manuscript_Revised_2026-09.docx` above is.** (Renamed from the earlier, misleadingly generic `NEPSE_Volatility_Final_Manuscript.pdf` after a forensic audit found the old name being mistaken for the current file.) No PDF rendering of the current `.docx` ships in this package — this development environment has no docx-to-PDF renderer available; export one from the `.docx` before submitting to a journal.
- `PAPER_REVISIONS.md` — **superseded**; the pre-referee revision notes, retained for provenance.
- `REFEREE_RESPONSE.md` — item-by-item response to the 2026-09-02 referee report, with what changed, where, and what did not change and why.
- `REFEREE_RESPONSE_ROUND3.md` — item-by-item response to the second peer-review evaluation (items A-H), applied by `paper/apply_round3_revisions.py` on top of the above.
- `FORENSIC_AUDIT_RESPONSE.md` — response to the third-round forensic packaging/provenance audit: manifest-stability fixes, the historical-vs-current cleaning-hash distinction, and the still-open PDF-regeneration and archive-cleanup items.
- `FOURTH_ROUND_AUDIT_RESPONSE.md` — response to the 4 September independent editorial/methodological review: the Yang-Zhang mixed-previous-close defect (adopted ratio corrected 1.309 → **1.280**), and an honest triage of the remaining mandatory items.
- `M7_ANALYSIS_PLAN.md` — the analysis plan and decision rule for the forward-looking India VIX test, **frozen before any forward result was computed**.
- `M14_CALIBRATION_ANALYSIS_PLAN.md` / `M14_CALIBRATION_RESULTS.md` — the instrumented calibration of the daily-bar estimators (manuscript Section 6.6): plan frozen and committed before any slope was computed; results, mechanical verdicts and every post-result correction.
- `M15_OPENING_PRICE_ANALYSIS_PLAN.md` / `M15_OPENING_PRICE_RESULTS.md` — what the opening price measures, with NEPSE's 20 April 2026 rule package, which widened the pre-open band, analysed as an event (manuscript Section 6.7): plan frozen and committed before any outcome statistic was computed, then the simulation checks, then the results. **Headline:** the trading session undoes 64-87% of NEPSE's overnight move (unbiasedness coefficient 0.13-0.36), an error inside each security's own auction (post hoc: NEPSE's market-wide opening move shows no detectable reversal; the NIFTY 50 index, an average like it, has b 0.93; `M-014`); the 20 April 2026 rule package, which widened the pre-open band among other changes (`M-013`), produced a sharp break, unique against 77 placebo dates; three-quarters of Yang-Zhang's excess over close-to-close variance is the opening covariance it assumes away.
- `M16_ANAM_ESTIMATOR_PLAN.md` / `M16_ANAM_ESTIMATOR_RESULTS.md` — **Anam's estimator** (`src/nepsevol/estimators/anam.py`), a daily-bar volatility estimator for markets whose opening price cannot be trusted: the overnight move weighted by the open's measured unbiasedness b, the range extended to the effective open, a close-to-close blend that grows as the open degrades, and calibration to close-to-close variance across the market's cross-section. Designed on NEPSE regimes A1 and B, with M15's full-sample findings already known (the plan lists them); plan frozen (commit `3296dad`; cited as `dc41f1e` in the frozen documents, see the commit map under `M-017` in `AUDIT-REGISTER.md`) before the estimator was computed on the holdout. **Holdout:** no range-based estimator has significantly lower loss on the NEPSE holdout, NIFTY 50 or the S&P 500 (where b̂ is capped at one and the estimator is exactly overnight² + Parkinson), it ranks first on NIFTY 50, and its calibrated level is within 1.1% of close-to-close where rules were stable (as any estimator's is under the same calibration; see `ANAM_RECHECK_POSTHOC.md`); but plain close-to-close beats it in the 90 sessions after NEPSE's April 2026 band reform, and three of the plan's NEPSE predictions failed. Manuscript Section 6.8.
- `M17_ANAM_FRONTIER_PLAN.md` / `M17_ANAM_FRONTIER_RESULTS.md` — Anam's estimator, unchanged, in two more frontier markets: Bangladesh (Dhaka Stock Exchange, 2023-2026 and, with repaired dates, 2009-2021) and Vietnam (2007-2020), panels built by `src/nepsevol/frontier.py`. Plan frozen (commit `ff124bd`; cited as `db417ac`, see `M-017`) before any estimator was computed on these data. **Result:** it beats every classical range-based estimator in all three panels at both horizons (36 of 36 comparisons, under the plan's QLIKE loss) and its calibrated level is within 1% of close-to-close variance, but it does not beat plain close-to-close at 5 sessions in either primary panel and loses to it in Vietnam at 21 sessions, so the plan's summary claim G fails. Its open-free special case, a reported variant, had the lowest loss at 5 sessions in every panel (post hoc reading). The author's Dhaka file has day and month exchanged in pre-2023 dates; see the plan and `data/external/README.md`. Inputs are third-party and not packaged. Manuscript Section 6.8.
- `M18_ANAM_MOROCCO_PLAN.md` / `M18_ANAM_MOROCCO_RESULTS.md` — both forms of Anam's estimator on the Casablanca Stock Exchange (Morocco, 77 shares, 2012-2026, data supplied by the author), with the open-free form tested as a hypothesis fixed before any return or estimator was computed on the data. Plan frozen (commit `b4de86d`). **Result:** every binding hypothesis holds. The open-free form has the lowest loss of all nine estimators at 5 and 21 sessions and beats close-to-close (t = -4.53) and the full estimator (t = -4.75) at 5; the full estimator also beats close-to-close at 5 (t = -2.06); both calibrated levels are 1.005. Manuscript Section 6.8.
- `anam-estimator/` — **the installable package**: Anam's estimator and the `AnamModel` forecasting model, a command line, simulated data and a model card (`anam-estimator/README.md`); numpy and pandas only, installable straight from GitHub with pip. The estimator's arithmetic is a verbatim copy of `src/nepsevol/estimators/anam.py`. The model (version 0.2.0) uses the corrected evaluation of plan M20 through `anam_estimator.evaluation`, which the research code shares. `tests/test_anam_package.py` checks both against the research code; the package's own tests are in `anam-estimator/tests/`.
- `paper/theory/` — **the theory supplement**, in LaTeX: the theory section (`section_theory.tex`), Appendix B with the proofs (`appendix_proofs.tex`), the bibliography, the wrapper `theory.tex` and the compiled `theory.pdf`. Its seven propositions cover:
  - identification of the open's unbiasedness coefficient b, with the sharp bound on the opening error;
  - the classical estimators' exact biases under a noisy open;
  - band censoring;
  - pooling across securities;
  - calibration lag;
  - instrumented calibration;
  - what Anam's kernel does with a noisy open (Proposition 7, added after the audit).

  Every number is a macro in `paper/theory/generated/`, written by `scripts/45_theory_checks.py`, `scripts/46_theory_proofs.py` and `scripts/48_kernel_theory.py`. Script 46 verifies every step of every proof and writes one row per step to `output/tables/table124_theory_proof_steps.csv` (321 steps, 166 of them symbolic).
- `M19_THEORY_CHECKS_PLAN.md` / `M19_THEORY_CHECKS_RESULTS.md` — the plan for checking the theory, frozen in its own commit before `scripts/45_theory_checks.py` existed, and its results. It sets out:
  - Part A, the propositions against simulation;
  - Part B, the applications to frozen data;
  - Part C, one prediction tested on the five panel test spans.

  **Results:**
  - All checks pass.
  - The prediction (that the open-free form gains most where a security's own open is noisiest) was not supported. It was confirmed in NEPSE and recent Dhaka data, not detected in Vietnam and Morocco, and reversed once in the repaired Dhaka panel.
  - The open-free form's lower loss always had a level component, but in most panels its forecasts also tracked better.
- `M20_CORRECTED_EVALUATION_PLAN.md` / `M20_CORRECTED_EVALUATION_RESULTS.md` — the forecast evaluation of M16–M18 corrected after the audit of 9 October 2026, under a plan frozen before any corrected loss was computed (`scripts/47_corrected_evaluation.py`, package Tables 125–132, manuscript Table 39). The results are summarised above under "How it did out of sample". The M16–M18 entries above describe the frozen evaluation.
- `M21_PROSPECTIVE_PLAN.md` — the prospective test. Every forecast's parameters are frozen on the current data (`scripts/50_m21_freeze.py`, package Table 136) and will be scored, unchanged, on sessions after 9 October 2026. The plan recommends lodging it with an external registry before any new data is read.
- `ESTIMAND_NOTE.md` — the four objects the paper's claims concern: the observed-return second moment, conditional return variance, integrated variance and quadratic variation. It also says which claim concerns which.
- `audits/` and `RESEARCH_AUDIT_RESPONSE.md` — the independent audit and publication plan of 9 October 2026, kept as received, and the answer to each finding (A01–A15). It says what was accepted, what was disputed and why, what was changed, and what needs the author.
- `ANAM_RECHECK_POSTHOC.md` — the POST HOC recheck of every claim made for Anam's estimator, run after all M16-M18 verdicts were known (`scripts/44_anam_recheck.py`, package Tables 117-120, paper Tables 37-38): what was overstated and how it was corrected (`M-020` to `M-025`), which verdicts survive other inference, another loss function and a Holm correction, the level under a shared calibration, and the data assumptions tested. No frozen verdict changes.
- `OPTIONAL_ITEMS_FOLLOWUP.md` — follow-up on the remaining optional items: literature-integration confirmation, the structured abstract, the master-coverage sensitivity check (Table 17), JEL/data-availability/funding/conflict-of-interest statements, and the table-header/CI-precision fixes.
- `data/processed/` — frozen paper-facing stock-day panels in CSV format (see `data/processed/README.md`).
- `data/external/` — NIFTY 50, India VIX, the NEPSE index series, and the NEPSE security master used to validate the instrument classification (see `data/external/README.md`).
- `data/audit/duplicate_key_rows.csv` — compact extract containing only the duplicated historical security-date rows needed to reproduce the duplicate audit in Section 3.
- `scripts/` — the producer scripts for the paper's retained empirical results.
- `src/nepsevol/` — cleaning, calendar, universe-classification, validation, and volatility-estimator code.
- `output/tables/` and `output/figures/` — frozen outputs generated for the submitted manuscript.
- `REPRODUCIBILITY_MAP.csv` — manuscript claim/figure/table → producer → output mapping.
- `AUDIT-REGISTER.md` — resolves the `D-`, `A-`, `SS` and `PAP-` identifiers cited in code comments, and records every post-result correction (`M-` entries, through `M-034` for the audit of 9 October 2026), including the map from the original commit identifiers cited in frozen documents to the current ones (`M-017`).
