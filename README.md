# NEPSE Volatility — Journal Submission Reproducibility Package

This package accompanies **When the Open Overreacts: Measuring Daily Volatility in a Frontier Market without Options — Evidence from a Pre-Open Band Reform on the Nepal Stock Exchange** (retitled in round 14; earlier versions circulated as *Calculating Volatility in Frontier Markets Without Options* and *Daily OHLC Volatility Measurement in a Cash-Only Frontier Market*).

## What is included

- `paper/NEPSE_Volatility_Manuscript_Revised_2026-09.docx` — **the revised manuscript**, rebuilt from the frozen output tables by the `paper/apply_*_revisions.py` scripts, applied in order (`apply_referee_revisions.py`, then rounds 3-14; round 14, `apply_round14_revisions.py`, adds Sections 6.6-6.7, Tables 29-32 and Figures 7-8 from the M14 and M15 analyses below). Every figure it quotes is interpolated from `output/tables/*.csv`, never typed by hand.
- `paper/submission/` — the double-anonymous submission set: anonymised manuscript, separate title page, and a cover letter for each target journal (three field journals matched to the round-14 contribution, then the referee's three recommendations), rebuilt by `paper/build_submission_set.py`.
- `paper/manuscript_as_reviewed_pre_revision.pdf` — the manuscript **as reviewed** (the PRE-revision PDF the first-round referee actually read), retained only so the revision can be checked against it. **This is not the current manuscript; `paper/NEPSE_Volatility_Manuscript_Revised_2026-09.docx` above is.** (Renamed from the earlier, misleadingly generic `NEPSE_Volatility_Final_Manuscript.pdf` after a forensic audit found the old name being mistaken for the current file.) No PDF rendering of the current `.docx` ships in this package — this development environment has no docx-to-PDF renderer available; export one from the `.docx` before submitting to a journal.
- `PAPER_REVISIONS.md` — **superseded**; the pre-referee revision notes, retained for provenance.
- `REFEREE_RESPONSE.md` — item-by-item response to the 2026-09-02 referee report, with what changed, where, and what did not change and why.
- `REFEREE_RESPONSE_ROUND3.md` — item-by-item response to the second peer-review evaluation (items A-H), applied by `paper/apply_round3_revisions.py` on top of the above.
- `FORENSIC_AUDIT_RESPONSE.md` — response to the third-round forensic packaging/provenance audit: manifest-stability fixes, the historical-vs-current cleaning-hash distinction, and the still-open PDF-regeneration and archive-cleanup items.
- `FOURTH_ROUND_AUDIT_RESPONSE.md` — response to the 4 September independent editorial/methodological review: the Yang-Zhang mixed-previous-close defect (adopted ratio corrected 1.309 → **1.280**), and an honest triage of the remaining mandatory items.
- `M7_ANALYSIS_PLAN.md` — the analysis plan and decision rule for the forward-looking India VIX test, **frozen before any forward result was computed**.
- `M14_CALIBRATION_ANALYSIS_PLAN.md` / `M14_CALIBRATION_RESULTS.md` — the instrumented calibration of the daily-bar estimators (manuscript Section 6.6): plan frozen and committed before any slope was computed; results, mechanical verdicts and every post-result correction.
- `M15_OPENING_PRICE_ANALYSIS_PLAN.md` / `M15_OPENING_PRICE_RESULTS.md` — what the opening price measures, with NEPSE's 20 April 2026 pre-open band reform as a natural experiment (manuscript Section 6.7): plan frozen and committed before any outcome statistic was computed, then the simulation checks, then the results. **Headline:** the trading session undoes 64-87% of NEPSE's overnight move (unbiasedness coefficient 0.13-0.36, NIFTY 50 0.93); the band reform produced a sharp break, unique against 77 placebo dates; three-quarters of Yang-Zhang's excess over close-to-close variance is the opening covariance it assumes away.
- `OPTIONAL_ITEMS_FOLLOWUP.md` — follow-up on the remaining optional items: literature-integration confirmation, the structured abstract, the master-coverage sensitivity check (Table 17), JEL/data-availability/funding/conflict-of-interest statements, and the table-header/CI-precision fixes.
- `data/processed/` — frozen paper-facing stock-day panels in CSV format (see `data/processed/README.md`).
- `data/external/` — NIFTY 50, India VIX, the NEPSE index series, and the NEPSE security master used to validate the instrument classification (see `data/external/README.md`).
- `data/audit/duplicate_key_rows.csv` — compact extract containing only the duplicated historical security-date rows needed to reproduce the duplicate audit in Section 3.
- `scripts/` — the producer scripts for the paper's retained empirical results.
- `src/nepsevol/` — cleaning, calendar, universe-classification, validation, and volatility-estimator code.
- `output/tables/` and `output/figures/` — frozen outputs generated for the submitted manuscript.
- `REPRODUCIBILITY_MAP.csv` — manuscript claim/figure/table → producer → output mapping.
- `AUDIT-REGISTER.md` — resolves the `D-`, `A-`, `SS` and `PAP-` identifiers cited in code comments.

## Environment

The reference environment, recorded in `data/processed/BUILD-MANIFEST.json`, is **Python 3.14.6**
on macOS arm64 with the exact pins in `requirements.txt`.

The pipeline is additionally verified on **Python 3.12 / x86-64 Linux**, where all frozen tables
and figures reproduce byte-identically under the next-nearest available package versions. The
supported floor is Python 3.12; `pyproject.toml` declares the dependency floors and
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

## Paper-facing analysis order

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
19. `scripts/25_submission_tables.py` — manuscript-facing Tables 1, 3–32, and the `PAPER_RESULTS_CHECK.csv` QA ledger. **Runs last**: it reads the artifacts produced by every step above.

## Important implementation conventions

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
