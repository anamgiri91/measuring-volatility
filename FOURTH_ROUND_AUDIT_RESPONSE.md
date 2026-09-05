# Response to the independent editorial and methodological review (4 September 2026)

The review's lead finding is correct, was reproduced exactly before being fixed, and is now
repaired with a regression test. The remaining fourteen mandatory items are triaged honestly
below: five are done or substantially done, three are partly addressable, and six require
inputs this environment does not have (official circulars, paywalled primary texts,
high-frequency data) or a scientific/structural decision the author must make.

---

## M1 — the Yang-Zhang specification contradicted the manuscript. FIXED.

**The finding was right.** `yang_zhang()` had no parameter through which the adopted
corporate-action-adjusted previous close could reach it, so `_logs()` rebuilt an *unadjusted*
previous-session close for the overnight term, while `scripts/26_robustness.py` built the matched
close-to-close denominator from the *adjusted* series. Independent recomputation on the frozen
panel reproduced the review's three figures to six decimals, and its count of differing rows:

| Specification | Numerator | Denominator | SD ratio |
|---|---|---|---|
| Shipped (mixed) | unadjusted | adjusted | 1.309371 |
| Consistent adopted | adjusted | adjusted | **1.279624** |
| Consistent unadjusted | unadjusted | unadjusted | 1.273239 |

4,403 rows differ between the adjusted and unadjusted numerators.

**What changed.** `_logs`, `yang_zhang` and `close_to_close` now take an explicit `prev_close`
series (default: the unadjusted session close, so nothing silently changes for other callers).
`scripts/26_robustness.py` passes the adopted series, and its 2×2 now rebuilds the **numerator**
per definition instead of holding it fixed — two of the four cells were previously mixed. The
adopted figure is **1.280 [1.258, 1.303]** (two-way; block-date [1.223, 1.355]) on 135,899
matched stock-days. The corrected 2×2:

| Previous close | Benchmark horizon | SD ratio |
|---|---|---|
| unadjusted | same-session r_cc² | 1.288 |
| unadjusted | 21-session variance | 1.273 |
| adjusted | same-session r_cc² | 1.295 |
| **adjusted (adopted)** | **21-session variance** | **1.280** |

**Manuscript.** All four prose locations that quoted 1.309 are corrected (abstract, §6.5, §7.2,
§9), Tables 7, 12 and 15 are regenerated, and §9 now *discloses* the correction rather than
quietly replacing the number — including what the superseded figure was and why no consistent
specification produces it. `paper/apply_round4_revisions.py` no longer hardcodes the ratio in the
abstract; it reads it from the frozen table, so a rebuild cannot reintroduce it.

**Tests.** Three new regression tests, one of which (`test_yang_zhang_actually_uses_the_previous
_close_it_is_given`) was **verified to fail when the defect is deliberately reintroduced** — a
test that cannot fail would not have caught this. 111 tests pass.

**Also fixed while here (A-072):** the docx fillers re-parsed the paper-facing CSVs with pandas'
type inference, so a cell written as `"1.280"` rendered as `1.28` while the prose said `1.280`.
They now read `dtype=str`, and ratio columns are written as fixed-precision strings.

---

## Done or substantially done

### M3 — equivalence framing. DONE.

Both criticisms are accepted and implemented.

- **"Prespecified" is withdrawn.** The margin was declared after the estimates existed, and an
  earlier version of its own justification cited effects already observed in this project — the
  exact circularity the term is meant to exclude. It is now described everywhere as *declared
  post hoc, applied consistently*; `prespecified` no longer appears in the manuscript body,
  `nepsevol.equivalence`, the producer scripts, or the verdict sentences.
- **The confidence level is named correctly.** Textbook TOST at one-sided α = .05 corresponds to
  a **90%** interval; this package reports 95% intervals, so the criterion in use is
  **conservative** (it declares equivalence less often than TOST would), not standard. Both are
  now computed and reported.
- **New Table 18** reports every verdict across margins of ±2.5%, ±5% and ±10% *and* at both
  confidence levels. The finding is worth stating plainly: the confidence level changes **no**
  verdict, but the margin changes **4 of 12** — Garman-Klass and Rogers-Satchell both move
  between `inconclusive` and `equivalent` across the grid. A verdict that flips across the grid
  is a statement about the margin, not the estimator, and the manuscript now says so.

### M5 — annualisation. DONE, and it exposed a labelling bug.

- The regime-specific claim is **withdrawn**. §7.1 no longer quotes "about 226 … and about 257";
  it reports A ≈ 229.6 as a *sample-period observed rate*, with the explicit sensitivity that
  annualising with 252 instead inflates variance by 9.7% and volatility by 4.8%.
- The manuscript now states the review's own argument: the post-reform window is 99 sessions over
  0.39 of a year, and **both regimes schedule five sessions per week**, so the reform cannot by
  itself change the annual count — the gap reflects the holiday composition of a short partial
  window. `table46` gained a `usable_as_annualisation_factor` column, `False` for that row.
- **Bug found while doing this (A-073):** the regime interpretation strings in
  `29_calendar_validation.py` were assigned *positionally* to a frame whose rows come out of a
  groupby in alphabetical order, so "Mon-Fri" sorted first and the two descriptions were
  **swapped** — the 99-session Mon-Fri row was labelled "pre-reform Sunday-Thursday" and the
  470-session Sun-Thu row "post-reform Monday-Friday; short span". Now keyed on the regime label,
  with a test asserting each row's label matches its own dates.

### M11 — weighting and distributional robustness. DONE.

- The estimand is now **stated**: every ratio is a ratio of pooled stock-day sums, so a security
  contributes in proportion to how much it traded. A new §6.1 paragraph says this, explains why
  that is the right estimand for the practical question, and concedes it is not neutral.
- **New Table 19** reports, for all six estimators, the stock-day-weighted ratio beside the
  equal-security mean and median and the 5th–95th percentile of the security-level ratio.
  The two weightings agree closely — the largest gap for any estimator is **0.027** — so the
  headline is not a weighting artifact. What the aggregate *does* hide is the spread, which is
  wide for every estimator (Parkinson's security-level ratios run 0.816–1.108 against a pooled
  1.001), and the manuscript now says that too.
- **New Table 20** reports the ratio by length of observed history (terciles), so a reader can
  check directly whether long-lived securities are carrying the pooled sum. They are not: the
  short-history stratum sits slightly lower for the range estimators and the three columns are
  otherwise close.

### M7 — the India VIX comparison. DONE, as a genuine forward test.

The analysis plan, reporting set and **decision rule were frozen in `M7_ANALYSIS_PLAN.md` before
any forward result was computed** — deliberately, because this package has already been caught
declaring a margin after seeing estimates (`R-023`) and defining a group by its own outcome
(`R-025`). A rule chosen after seeing which estimator won would have been the same error a third
time.

**Design.** India VIX at origin *t* against realised NIFTY volatility over **(t, t+30 calendar
days]**, with **session t excluded** (India VIX is disseminated from quotes during session *t*,
so its own return is contemporaneous with the forecast's formation). Non-overlapping windows are
primary — 190 independent origins, 2010-01-04 to 2026-04-30; daily overlapping windows are
reported only as sensitivity, with Newey–West HAC and a moving-block bootstrap.

**The lead–lag result is the substantive finding.** On identical origins, the same VIX
observation correlates far better with the 30 days *before* it than the 30 days *after*:

| Estimator | Backward 30d (contains t) | Forward 30d (excludes t) |
|---|---|---|
| Close-to-close | 0.806 | **0.694** |
| Parkinson | 0.778 | **0.629** |

The trailing comparison the manuscript previously reported was measuring persistence and
contemporaneous co-movement, exactly as the review argued.

**Decision rule outcome: INCONCLUSIVE.** Parkinson minus close-to-close in forward correlation is
**−0.064, 95% interval [−0.169, +0.065]** — contains zero. Per the frozen rule, no
estimator-superiority claim is made. Reported plainly in the manuscript: **close-to-close is
nominally ahead of Parkinson on every forward metric** (levels 0.695 vs 0.630; changes 0.463 vs
0.282; lead–lag as above). Nothing here supports the range estimator over the simple one, and the
paper now says that.

**Calibration.** Slopes on VIX are well below one (0.844 close-to-close, 0.595 Parkinson) — the
familiar volatility risk premium: India VIX sits above the realised volatility that follows it.

**Reconciliation (A-074).** The circulated numbers are now traced: 0.776 and 0.832 differ *only*
by whether the 2012-10-05 flash-crash session is in the sample, and 0.602 and 0.692 are not
independent quantities at all — they are those two correlations squared. All four are
trailing-horizon numbers; none is forecasting evidence.

**Manuscript.** §6.3 retitled and rebuilt around the forward test; the trailing comparison is
**retained and relabelled** as horizon-mismatched descriptive co-movement (not deleted — it has
circulated); the abstract, §8, §10 and §11 are rewritten to match; Tables 23–25 added. The
forward-looking risk-neutral versus backward-looking statistical distinction is stated
explicitly wherever the comparison appears.

**Leakage controls.** Tests assert directly on the window construction that the forward window
starts at origin+1 and never reaches backwards, and that the forward and backward windows are
built by separate code paths so a future edit cannot silently align them.

**Two close-out corrections after the first pass (A-076, A-077).**

- *The premium claim was an overreach.* §6.3 had read the sub-unit calibration slopes as proof
  that VIX exceeds subsequent realised volatility. A slope below one means the response is less
  than one-for-one; it says nothing about the sign of the error. The direct evidence is now
  computed — mean VIX − RV of **+2.99 [2.19, 3.77]** points against close-to-close and **+5.41
  [4.63, 6.08]** against Parkinson, mean VIX/RV of 1.291 and 1.523, VIX larger in 82% and 94% of
  windows — and the direction does hold. It is now described as **consistent with** a volatility
  risk premium, not proof, naming index construction, trading calendars, jump treatment and the
  risk-neutral/physical gap as competing contributors. That the gap is far larger against the
  range estimators than against close-to-close is itself evidence that construction is part of it.
- *The paired comparison was correct but undemonstrated — and one method dissents.* The bootstrap
  always applied one resampled index to VIX and both outcomes together, which is right: the two
  correlations share their VIX observations, their windows, and outcomes correlating at **0.889**.
  Now shown rather than asserted — paired interval [−0.169, +0.065] (width 0.234) against the
  invalid independent [−0.381, +0.266] (width 0.648), plus a Fisher-z paired interval [−0.281,
  +0.135]. **Williams' t = −2.587 disagrees**, rejecting equality in close-to-close's favour; it
  assumes trivariate normality that right-skewed volatility violates, while both
  distribution-free intervals contain zero. Reported as a disagreement rather than resolved by
  preference. The frozen rule was stated on the bootstrap interval, so the outcome stands at
  inconclusive — and no method, including the dissenting one, supports Parkinson.

**Final close-out: non-overlapping was not independent (A-078, A-079).**

A last check asked whether the paired bootstrap preserved *time-series* dependence. It did not,
and that mattered. Non-overlapping windows remove the mechanical overlap between outcomes but not
the persistence of volatility: the lag-1 autocorrelation of India VIX across these origins is
**0.646**. Worse, the per-estimator correlation intervals quoted in the manuscript came from the
**analytic** Fisher-z formula, which assumes both normality *and* independence.

All headline intervals are now from a **paired stationary block bootstrap** — one block-resampled
index sequence per replicate, applied to VIX and both outcomes together, so pairing and serial
dependence both survive. What it cost to have ignored this:

| Quantity | Assuming independence | Dependence-aware | Effect |
|---|---|---|---|
| Close-to-close forward correlation | [0.613, 0.762] | **[0.467, 0.800]** | more than twice as wide |
| Close-to-close calibration slope | "below one" | **[0.528, 1.082]** | **contains one** |
| Parkinson calibration slope | below one | [0.420, 0.741] | still excludes one |
| Parkinson − close-to-close difference | contains zero | contains zero at blocks 1, 3, 6 | unchanged |
| Mean VIX − RV, VIX/RV | as reported | essentially unmoved | unchanged |

**The attenuation claim is withdrawn for close-to-close** — its slope interval contains one, so
the manuscript no longer asserts a less-than-one-for-one response for that estimator. The
premium evidence and the inconclusive verdict both survive intact.

On labelling (A-079): the Fisher-z interval on the *difference* genuinely is distribution-free —
it is a percentile interval over the same paired **nonparametric** bootstrap replicates, on the
Fisher scale. The analytic Fisher-z helper is now labelled in its own docstring as neither
distribution-free nor dependence-aware, and its intervals are demoted to a labelled contrast in
Table 28.

**Block length selected, not chosen (A-080).**

Reporting blocks of 1, 3 and 6 and then quoting one of them would have left the interval open to
hindsight. The primary mean block length is now selected **from the data** by the automatic
Politis–White (2004) / Patton–Politis–White (2009) procedure, run on each series entering the
comparison (10.88, 5.19, 3.56 origins) and combined by taking the maximum. **That aggregation is
our own conservative rule, adopted post hoc** — Politis–White selects a length for a single
series and prescribes nothing about combining several, so the per-series selections are all
reported. With **190 forecast origins** and a selected mean block length of 10.88, each bootstrap
replicate contains approximately **17 expected-length blocks**. That is the expected number of
blocks drawn per replicate, *not* an effective-sample-size estimate — a different quantity, not
computed here. This limited amount of independent temporal information is what motivates
reporting block-length sensitivities. The verdict is unchanged at every
length in the grid, including the selected one: the difference is −0.064 with a
[−0.164, +0.095] interval at 10.88 origins.

Two wording corrections went with it. The manuscript no longer calls the 190 origins
"independent" — the 0.646 autocorrelation contradicts it, and non-overlapping is a property of
the outcome windows, not the origins. And the Fisher-scale interval is no longer called
"distribution-free": a nonparametric bootstrap avoids a parametric normality assumption but is
not literally distribution-free in finite samples. It is now described exactly — *a percentile
interval computed from paired stationary-block bootstrap replicates after Fisher-z
transformation* — and is computed from the block replicates so the description matches what was
actually done.

The volatility-premium language remains **"consistent with"**, unchanged: the persistent positive
gap plausibly reflects both compensation for risk and measurement differences, and the fact that
the gap is much larger against the range estimators than against close-to-close is evidence for
the second.

**Caught in-session (A-075).** A first cut produced *two different* forward correlations for the
same estimator (0.533 and 0.695) because the lead–lag table re-ran the non-overlap selection on a
differently-merged frame and so chose a different origin set. Fixed before either number reached
the manuscript; the two now agree.

### M13 — Nepal literature framing. Matrix frozen first, then the claim narrowed.

Three tables, deliberately separated so the counts reconcile
(`located − duplicates − excluded − inaccessible = included`), built and frozen **before** any
prose was written:

| Table | Rows | Grain |
|---|---|---|
| `table71_nepal_search_log.csv` | 5 | one per executed query |
| `table73_nepal_screening_ledger.csv` | 19 | one per located record |
| `table72_nepal_literature_matrix.csv` | 3 | one per included study, ten frozen fields |

**19 − 1 duplicate − 7 excluded − 8 inaccessible = 3 included**, asserted by the producer script
and by four tests. Inaccessible records are preserved, never folded into exclusions.

**The evidence retired the original claim.** The frozen pre-search statement rested on an
index-versus-security distinction. The search then located Neupane, Neupane and Baral (2022), a
security-level NEPSE volatility study, so "primarily index-level" was no longer supportable and
is retired throughout. What survives is the **measurement** question: that study uses closing
prices only and asks an association question about volume and frequency, not how to measure
volatility from a daily OHLC bar. The claim was narrowed *after* the tables froze — the correct
order.

**Verification discipline.** Only 1 of the 3 included studies was full-text verified; the other
two are publisher-record-and-abstract only, and a test asserts no absence or novelty claim shares
a sentence with either citation.

**Search-quality control (kept out of the manuscript body, per instruction).** A search summary
reported that Neupane et al. (2022) "included 26 securities... out of 147 companies". Parsing the
PDF showed that sentence sits in *that paper's literature review*, describing a study it cites;
its own sample is one security over 2010–2021. Trusting the snippet would have put a fabricated
multi-security NEPSE study into the matrix. Logged as `snippet_conflation` (R17) and excluded.

**Also fixed here:** the structured abstract had drifted to 340 words as successive rounds added
material. Rebuilt at 243 words of body text, with the cap now asserted by a test so it cannot
drift again.

### M4 — thin-tail selection on the outcome. DONE, and it REVERSES the finding.

The criticism was correct and consequential. `MAX_ZERO_RANGE` used zero-range share — the exact
event that drives Parkinson to zero — so a low Parkinson ratio inside that group was partly an
arithmetic consequence of how the group was built, not a finding about liquidity. It also let a
six-session security into the tail.

`scripts/31_lagged_thinness_screen.py` implements a **lagged, outcome-independent liquidity
screen, declared post hoc and applied consistently** (deliberately not called "ex ante", which
would imply the rule predated the results). A stock-day is thin when, over the previous **60
scheduled** sessions using information through t−1 only, participation < 90% **or** the median
trade count *conditional on trading* is at or below the cross-sectional 10th percentile (ties
inclusive). Eligibility requires 60 **scheduled** sessions of history — scheduled, not traded, so
eligibility does not itself depend on activity. Official listing dates are unavailable, so the
first observed trading date is stated as a proxy. The selection reads no price, range, return or
estimator output, and a test asserts that.

**The result reverses the earlier one:**

| Selection rule | Securities | Thin stock-days | Parkinson | Verdict |
|---|---|---|---|---|
| Zero-range grouping (Table 11) | 4 | 919 | **0.814** | different — collapsed |
| Lagged screen (Table 21) | 62 | 12,454 (9.8% of eligible) | **1.020** [0.984, 1.064] | inconclusive — **no collapse** |
| …rest of eligible sample | 274 | 114,253 | 1.015 [0.992, 1.035] | equivalent |

**Sensitivity (Table 22), all 15 specifications.** The 3×3 grid (participation 80/90/95% ×
trade-count tail 5/10/20%), the history-floor sweep (40/60/120 scheduled sessions) and each leg
of the OR on its own keep the thin-group ratio between **0.847 and 1.033**. No cell of the grid
or the floor sweep shows a collapse. The participation threshold barely matters because the
trade-count leg dominates — participation alone flags just 6 securities — and that is reported
rather than hidden.

**The one honest caveat:** the participation leg alone (6 securities, 546 stock-days) does give
0.847, but with an interval of [0.729, 1.104] that straddles the margin. It marks where any
genuine difficulty would lie without establishing one.

**Manuscript.** §6.1 is rewritten around the screen and states plainly why the old grouping was
circular; the "extreme thin tail exception" is **withdrawn** from the abstract and the
conclusion; Table 11 is retained but its caption is demoted to a *descriptive failure-case
inventory, NOT robustness evidence*; §10's limitation now says the two rules disagree and that
the disagreement is itself the finding. Net effect: the paper's central claim is **strengthened**,
because the apparent counter-example to it was a selection artifact.

**M12 (factual labels) — partly done.** The India "developed-market" label is wrong (MSCI
classifies India as an Emerging Market) and Table 7's Yang-Zhang comparator should be named as the
21-session close-to-close sample variance, which the corrected Table 12 now states explicitly. The
SEBI and NEPSE/SEBON primary sources are still missing — see below.

**M15 (repackaging) — partly done.** The abstract is now a 245-word structured abstract and the
audit trail already lives in separate response documents rather than the manuscript body. The
manuscript is still well over AJEB's effective 12,000-word cap and still carries substantial
revision history in §9.

---

## Requires inputs this environment does not have

These are not refusals — they are blocked on material I cannot obtain or verify here, and
inventing any of it would be worse than leaving it open.

- **M2 (event-level corporate-action verification).** Requires the SEBON bonus-share register /
  issuer filings reconciled per security, ex-date and factor. The current rule is a
  reference-price *detection* heuristic, and the review is right that "sit on a bonus-share
  ladder" overstates it. The honest interim step — renaming the variable to
  "source-implied reference-price adjustment" and running the three sensitivities — is doable and
  is the recommended next action.
- **M8/M9 (official historical security master, listing/delisting dates, coverage audit).**
  Needs official historical NEPSE/SEBON listing records. The current master is a
  current-listing snapshot from a third-party portal, already disclosed as such.
- **M12 (SEBI order, NEPSE/SEBON circulars for the April 2026 reform dates).** Needs the primary
  documents.
- **M14 (AddRS primary derivation).** Needs the paywalled Kumar & Maheswaran full text. The
  package already labels this unverified.
- **M6 (high-frequency validation subset).** Needs intraday NEPSE data that does not exist in
  this package.

---

## Requires a scientific decision by the author

- **M13 (novelty framing against Nepal literature).** Requires reading the cited Nepal studies and
  narrowing the contribution claim.
- **M10 (provenance/DOI deposit).** Requires an actual repository deposit and an identified
  independent verifier.

---

## Status

The lead correctness defect is fixed, verified, disclosed, and regression-tested. The package
reproduces cleanly (111 tests; manifest self-consistent at 149/149 files). The review's overall
judgment — that this is a major revision, not a prose pass — stands for the remaining items.
