# Response to the second peer-review evaluation

> **Editorial note (2026-09-04, added by the fourth-round audit follow-up; this document is
> otherwise left as the historical record).** Every Yang-Zhang figure of **1.309** below is
> **superseded**. A subsequent independent audit found that the adjustment had been applied to the
> benchmark only: `yang_zhang()` had no parameter through which the adopted corporate-action-
> adjusted previous close could reach its overnight term, so the numerator used the unadjusted
> close and the ratio mixed two definitions. Applied consistently to both sides, the adopted
> figure is **1.280 [1.258, 1.303]**; the consistent unadjusted figure is 1.273. See
> `FOURTH_ROUND_AUDIT_RESPONSE.md` and audit-register entry `R-022`. Items C and D below remain
> correctly described in substance — the horizon mismatch and the corporate-action classification
> were both real — but the numbers they quote are not the current ones.

This document answers the eight lettered findings (A-H) of the second-round critique, delivered
after `REFEREE_RESPONSE.md` (the response to the referee report of 2 September 2026, "items 1-20")
had already been applied. Read together with that file: this round found that most of the analysis
work answering A-H already existed in the package — written, run, and producing frozen output
tables — but had not reached the manuscript. That is the same failure the first response opened
on ("the manuscript currently lags behind its own analysis package"), recurring. Nothing in this
round changes the paper's central claim; several items strengthen it or make its scope more
precise.

Every number below is interpolated into the manuscript by `paper/apply_round3_revisions.py` from
`output/tables/*.csv`, the same discipline `apply_referee_revisions.py` used for the first
response. 29 new tests were added (`tests/test_round3_revisions.py`); 108 tests pass in total,
against 79 before this round.

---

## Item A — the headline claim hides the truly illiquid equities

**Status: addressed. The extreme thin tail is now disclosed separately, not smoothed into the
quintile average.**

The critique was right about the aggregate table: the thinnest security-level liquidity quintile
reports a median participation of 1.00 while individual securities in it range down to 5.3%
participation (`table40_participation_by_quintile.csv`; the exact figures the critique itself
computed).

`scripts/28_panel_balance.py` now separates a small **extreme thin tail** — securities with the
fewest observed sessions in the sample — from the rest of the equity universe and reports it as
its own row (Table 11), rather than letting the quintile median absorb it:

| Security | Median trades/day | Zero-range | Parkinson ratio | Rogers-Satchell ratio |
|---|---|---|---|---|
| NLO | 1 | 86.2% | 0.60 | 0.00 |
| BNL | 3 (65.7% participation) | 31.6% | 0.80 | — |
| UNL | 4 (90.1% participation) | 19.0% | 0.84 | — |

These numbers match the critique's own audit almost exactly. The extreme tail as a whole is
**4 securities (0.64% of the panel, 919 stock-days)**, zero-range 26.2%, Parkinson ratio 0.814 —
materially below the ordinary-equity aggregate (Parkinson ≈ 1.001).

**What changed, and what did not.** The paper's central claim — range estimators do not collapse
in the least active *ordinary-equity* group — is unchanged and still supported: the quintile-level
and predetermined-sort results (1.022, 1.025) describe the group as a whole and remain correct
descriptions of it. What changed is that the group is no longer the whole story: a named,
quantified exception is now reported alongside it, so a reader is not left inferring from the
quintile median that every security in the thinnest quintile behaves like the median one.

**Where:** Abstract; §6.1 (new sentence naming NLO, BNL, UNL individually); §6.5 (new "Panel
balance and the extreme thin tail" check); §10 (new Tenth limitation); §11 Conclusion (explicit
exception clause); Tables 10-11. **Tests:**
`test_shipped_thin_tail_table_separates_extreme_securities_from_the_rest`,
`test_named_extreme_securities_have_materially_higher_zero_range_than_the_aggregate`.

---

## Item B — equality of aggregate means is not measurement validation

**Status: addressed on both halves of the critique.**

**Half 1: a CI containing one is not evidence of equivalence.** `src/nepsevol/equivalence.py`
implements a prespecified ±5% TOST-style margin (chosen below the pooled-composition effect the
paper is about, above the sample's own repair/classification noise, and symmetric on the SD scale
every table already uses). Every ratio in Table 7 is now classified `equivalent` / `different` /
`inconclusive` against that margin instead of being read off whether its interval happens to
straddle one — a wide, uninformative interval can no longer read as support. Table 7 gained a
"Verdict at ±5% margin" column; Rogers-Satchell, for instance, is `inconclusive`, not "close to
one."

**Half 2: aggregate scale is not information content.** `table43_information_content.csv`
(new Table 14) reports Pearson and Spearman correlation of each within-session estimator against
the same matched proxy used everywhere else:

| Estimator | SD ratio to proxy | Pearson | Spearman |
|---|---|---|---|
| Parkinson | 1.001 | 0.70 | 0.63 |
| Rogers-Satchell | 1.037 | 0.21 | 0.14 |

These reproduce the critique's own numbers. Parkinson and Rogers-Satchell sit within 0.04 of each
other on aggregate scale while their day-by-day tracking of the proxy differs by more than 3x on
Pearson correlation — the two questions this paper answers (is the scale close? does it track day
by day?) are now both answered, with different numbers, rather than only the first.

**Where:** Abstract; §6.2 (new paragraph); §6.5 (new "Information content" check); §7.2 (Table 7
verdicts replace loose "close to one" language); §10 (new Eleventh limitation); Table 14.
**Tests:** `test_margin_is_five_percent_and_symmetric`,
`test_equivalence_verdict_classifies_correctly`,
`test_a_wide_interval_covering_one_is_not_equivalence`,
`test_verdict_sentence_never_says_unbiased_or_accurate`,
`test_shipped_table7_uses_the_equivalence_verdict_not_ci_coverage`,
`test_ratio_near_one_does_not_imply_high_correlation_with_the_proxy`.

---

## Item C — Yang-Zhang is row-matched but not horizon-matched

**Status: addressed. The reviewer's own recomputed number (≈1.273) is reproduced and then
superseded by a further, disclosed correction.**

`nepsevol.estimators.range_.yang_zhang_benchmark` now provides the horizon-matched benchmark: the
close-to-close sample variance over the *same* 21-session window Yang-Zhang itself integrates
over, rather than the squared return of the current session alone. On the shipped panel:

| Benchmark | SD ratio |
|---|---|
| Same-session r_cc² (row-matched only, previous revision) | 1.288 |
| 21-session close-to-close variance (horizon-matched) | **1.273** |

This confirms the critique's recomputation almost exactly. A further correction (item D, below)
compounds with it: adjusting the previous close for NEPSE's own corporate-action convention moves
the horizon-matched figure to the **adopted 1.309 [1.285, 1.335]** on 135,899 matched stock-days —
which is what Table 7 and §7.2 now report, with the full three-step progression (1.245 → 1.288 →
1.273/1.309) disclosed rather than presenting only the final number.

**Where:** §4.5 (third correction, new paragraph); §6.5 ("All six estimators" paragraph rewritten
to carry the full progression); §7.2; §9 (disclosed as a correction to a previously circulated
number); Table 7; Table 12. **Tests:**
`test_yang_zhang_benchmark_is_rolling_21session_variance_not_same_session_return`,
`test_horizon_matched_ratio_differs_from_same_session_ratio_on_shipped_data`,
`test_exactly_one_adopted_row_in_the_horizon_table`.

---

## Item D — previous-close definitions remain inconsistent

**Status: addressed. The 315 disagreements are classified by cause, not merely counted, and the
cause changes what the paper does with them.**

`src/nepsevol/corporate_actions.py` classifies every one of the 315 previous-close disagreements
against an implied adjustment factor `f = close_{t-1} / prev_close_t`:

| Class | n | What it is |
|---|---|---|
| `corporate_action` | 214 | NEPSE's own ex-date reference-price adjustment (bonus/rights); `f` clusters at 1.05, 1.10, 1.15, 1.20, 1.25, 1.30 |
| `reference_rounding` | 34 | within the 0.5% rounding floor, not separable from tick rounding |
| `upward_adjustment` | 62 | published previous close *above* the prior close; not explicable as an entitlement, left unadjusted and disclosed |
| `session_gap` | 5 | the "prior observed row" is not the previous genuine session; no overnight return to define |

One definition is now adopted package-wide: the previous genuine session's close, replaced by
NEPSE's own published `prev_close` on exactly the rows classified `corporate_action`. Adopting it
(rather than the unadjusted previous-session close) moves the Yang-Zhang total-risk ratio from
1.273 to the adopted 1.309 — a real, disclosed, further correction, not a wash.

**What is not claimed.** This is a detection rule keyed on the exchange's own published reference
price, not a corporate-action feed; it cannot name the entitlement, and the residual
`upward_adjustment` and `reference_rounding` classes are reported rather than swept into
`corporate_action`.

**Where:** §3 (forward reference); §4.5 (full paragraph); §6.5; §9; Table 12 (both definitions
shown side by side, adopted marked). **Tests:** `test_classes_are_exhaustive_and_mutually_exclusive`,
`test_corporate_action_requires_downward_revision_of_prev_close`,
`test_rounding_floor_is_not_swept_into_corporate_action`,
`test_adjusted_previous_close_only_moves_on_flagged_rows`,
`test_adjusted_previous_close_is_nan_across_a_gap_even_with_corporate_actions`,
`test_shipped_corporate_action_audit_accounts_for_all_315_disagreements`.

---

## Item E — cross-market evidence is period-sensitive

**Status: addressed. Both windows are now reported side by side.**

`scripts/09_cross_market_control.py` reports the India VIX correlation over the full available
history and over the window that overlaps the NEPSE study:

| Window | n | Parkinson–VIX | CC–VIX |
|---|---|---|---|
| Full VIX sample (2010 onward) | 3,999 | 0.776 | 0.796 |
| NEPSE-overlap window (March 2024 onward) | 557 | **0.508** | **0.570** |

These reproduce the critique's numbers (≈0.510, ≈0.570) closely. The relative ordering is
unchanged (close-to-close still edges Parkinson in both windows), but the magnitude of
"co-movement" is materially weaker in the period this paper's evidence actually covers, and the
manuscript now says so explicitly rather than reporting only the longer, stronger-looking window.

**Where:** Abstract; §6.3 (new sentence + Table 13); §6.5; §11 Conclusion (both figures quoted).
**Tests:** `test_vix_period_sensitivity_reports_both_windows`,
`test_overlap_correlations_are_materially_lower_than_full_sample`.

---

## Item F — the provenance claims exceed the shipped evidence

**Status: mostly already resolved by the first response; the residual gap (exact provider URLs)
is closed here.**

`data/processed/BUILD-MANIFEST.json`'s `raw_data` block already carried an honest
`"status": "NOT_REDISTRIBUTED"` claim with an explanatory `"claim"` field as of the first
response (`scripts/30_repair_build_manifest.py`); it no longer contradicts §9 or the README. The
manuscript already describes the security master as "an external listing... rather than an
official SEBON register" (§3), correctly declining to call it official.

What was still missing: `data/external/README.md` named the providers but not their current
public access points. It now does, with an explicit note that the *original* acquisition predates
this package and was not logged with per-file retrieval timestamps — that limitation is stated
rather than backfilled with a fabricated retrieval log.

**Where:** `data/external/README.md` (new provenance table). **Tests:**
`test_manifest_raw_data_claim_is_never_contradictory`,
`test_shipped_manifest_matches_build_manifest_claim`.

---

## Item G — the inference still misses serially correlated market shocks

**Status: addressed. A stationary block bootstrap over dates is reported alongside the two-way
one, and it changes a reported conclusion.**

`nepsevol.inference.ratio_of_sums_ci_block` implements the stationary bootstrap of Politis and
Romano (1994) over calendar dates — geometric-length blocks of consecutive sessions, mean length
21 (the paper's own volatility horizon) — combined with i.i.d. security resampling. Reported for
all six named estimators of Table 7 (new Table 15):

| Estimator | Two-way CI | Excludes one | Block-date CI | Excludes one |
|---|---|---|---|---|
| Rogers-Satchell | [1.013, 1.062] | Yes | [1.000, 1.074] | **No** |

Modeling serial dependence between adjacent sessions — which i.i.d. date resampling cannot see —
reduces the count of Table 7 estimators distinguishable from the matched proxy from 3 of 6 to
2 of 6. Rogers-Satchell specifically moves from "distinguishable" to "inconclusive." This is
disclosed as a finding that changes a reported conclusion, not absorbed silently.

**Where:** §6.2; §6.5 (new "Dependence structure" check); §7.2; §9 (disclosed); Table 15.
**Tests:** `test_stationary_date_multiplicities_sum_to_n_date`,
`test_stationary_block_reduces_to_iid_at_mean_block_one`,
`test_block_bootstrap_runs_and_brackets_the_point_estimate`,
`test_block_interval_is_not_narrower_than_the_iid_twoway_interval`,
`test_shipped_block_interval_table_reports_all_six_estimators`.

---

## Item H — the literature was expanded but not integrated

**Status: fully addressed (updated 2026-09-04).** A surname-by-surname audit of the reference
list against the manuscript body — re-run after the initial "5 splice points" pass below was
first reported, using narrative-citation-safe matching (e.g. "Lo and MacKinlay (1990)", not only
the reference-list form "Lo, A. W., & MacKinlay") — confirms **every one of the 30 references
now has at least one in-text citation**. The five splices described below account for most of
them; a few others (e.g. Politis & Romano, Cameron/Gelbach/Miller, Lo & MacKinlay, Zhang et al.)
turned out to already be integrated via the §6.5 bootstrap paragraph's citation list, which was
not fully credited in the original version of this section.

**The AddRS/Kumar-2018 citation problem no longer exists, because the claim was withdrawn.** The
code previously cited "a later author reproduction, Kumar (2018), open access" for the operational
AddRS equations. That citation could not be resolved to any bibliographic record the author can
produce. Rather than reconstruct a plausible-looking one, it has been **withdrawn** and replaced
with Kumar and Maheswaran (2014b) — the companion modelling-and-forecasting paper, already in the
reference list, in which the operational equations are given in the form implemented here. §4.6
now names 2014a (the theoretical reflection-principle source) and 2014b (the operational-equations
source) separately, rather than the ambiguous single "(2014)" citation the manuscript used before.

**The fifteen previously-added references are now integrated into the argument at five points**
(Introduction's estimator-family sentence; the frontier-market complications paragraph; the
emerging-market framing sentence; the §7.2 loss-function sentence; the §6.5 bootstrap paragraph),
rather than standing only in the reference list. Politis and Romano (1994) — the source for the
block bootstrap of item G — was added to the reference list and integrated at the same time.

**Where:** §4.6 (Kumar citation split); Introduction, §5.2 (citation splices); §6.5; §7.2;
References (Politis & Romano added). **No new test**: this item is manuscript prose only, but it
was checked programmatically (surname-match audit, reported above) rather than by inspection.

---

## Two defects fixed along the way (not in the critique, found while making these edits)

- **A stray "Third," sentence was embedded inside the "Second," limitation**, duplicating the
  next paragraph's own "Third," — the repeated-ordinal defect the *first* review round's optional
  items flagged and that round 2's paragraph-start-only renumbering could not see, because the
  duplicate was mid-paragraph rather than at its start. It is now its own paragraph (the new
  Third), and §10 renumbers contiguously through Twelfth.
- **`scripts/25_submission_tables.py` had computed four analyses (information content, block-date
  dependence, calendar validation, corporate-action detail) that were never wired into a
  manuscript-facing table** — the same "orphan artifact" failure mode `R-015` (the trading
  calendar) named in the first response. `REPRODUCIBILITY_MAP.csv` gained eleven new rows so this
  class of defect is caught by `test_every_manuscript_table_named_by_the_map_has_a_frozen_output`
  going forward.

## Numbers that moved

| Quantity | Was | Now | Cause |
|---|---|---|---|
| Yang-Zhang / total-risk proxy | 1.288 [1.244, 1.331] | **1.309 [1.285, 1.335]** | Items C + D: horizon match, then corporate-action-adjusted previous close |
| Table 7 estimators with two-way CI excluding one | (not previously cross-checked) | **3 of 6**, falling to **2 of 6** under block-date clustering | Item G |
| Ordinary-equity zero-range rate (aggregate) vs. extreme thin tail | 1.66% (aggregate only) | 1.66% aggregate; **26.2%** for the named 4-security extreme tail | Item A |
| India VIX correlation (Parkinson / CC) | 0.776 / 0.796 (2010-2026 only) | 0.776 / 0.796 full sample; **0.508 / 0.570** NEPSE-overlap window | Item E |
| §10 limitations | 9 | **12** | Items A, B (new Tenth, Eleventh) + the embedded-ordinal fix (split Third) |
| Tests passing | 79 | **108** | This round |

## Reproducing this response

```bash
pip install -r requirements.txt && pip install -e .
bash run_paper_analysis.sh                    # regenerates tables 1-50, runs the test suite,
                                               # then refreshes SUBMISSION_MANIFEST.json --
                                               # see that file for the current test count
python paper/apply_referee_revisions.py       # round 2 (idempotent if already applied)
python paper/apply_round3_revisions.py        # this round
python paper/build_submission_set.py
python build_manifest.py
```
