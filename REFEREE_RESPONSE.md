# Response to the referee report of 2 September 2026

> **Editorial note (2026-09-03, added by the round-3 forensic-audit follow-up, not part of the
> original response).** This document is a historical record of the state as of the 2 September
> response and is left otherwise unedited. Two things it says have since moved and should not be
> read as current: (1) "seventy-nine [tests] pass now" — the package now ships 108, after
> `REFEREE_RESPONSE_ROUND3.md`'s additions; see `SUBMISSION_MANIFEST.json` for the count current
> to any given release rather than a number fixed in prose. (2) Item 18's claim that a
> transcription error in a docstring's non-negativity proof "would surface as a proof that
> fails" is overstated — see the corrected wording in `AUDIT-REGISTER.md` and
> `src/nepsevol/estimators/range_.py`: these are necessary-condition sanity checks, not
> sufficient verification of an equation's coefficients.

Recommendation received: **Major Revision — do not submit the current PDF yet.** Twenty mandatory
items, of which items 1, 2, 3 and 5 were declared non-negotiable.

This document answers every item: what changed, where, and — where a number moved — what it moved
to and why. Three items produced findings the report did not anticipate; those are flagged
**beyond the report**. Nothing is marked resolved on the strength of an argument alone: each row
points at a file, a table, or a test.

The report's own caution applies to this response. Fifty-two tests passed before these revisions
and seventy-nine pass now, but passing tests establish that code behaves as programmed, not that
a comparison is correctly specified. The new tests were therefore written to target
specifications — that a numerator and its denominator describe the same rows, that an overnight
return spans exactly one session, that two reforms keep two dates — rather than plumbing.

---

## The four non-negotiable items

### Item 1 (Critical) — rebuild the panel under the corrected duplicate rule ✅ RESOLVED

The report was right that conflict-freedom was an assumption. It is now a demonstrated fact.

The raw sources were located and the 2024–2026 daily-trades panel was rebuilt from them under the
corrected classification rule. Two results:

- **Zero duplicated `(symbol, date)` keys.** `data/processed/audit/panel_trades_duplicate_audit.csv`
  reports `KEYS_EXAMINED = ROWS_EXAMINED = 286,994` — exactly one row per key — with an explicit
  zero printed for each of the four duplicate classes. An empty file could not distinguish "no
  conflicts" from "the audit never ran", so absence is now written down as evidence.
- **The rebuilt panel is identical to the frozen panel**: 184,430 rows × 16 columns, zero
  differing values in any column.

The obsolete `drop_duplicates(keep="last")` path therefore had nothing to select between, and **no
downstream table or figure changes as a consequence of the duplicate rule.**

*Beyond the report:* `data/processed/nepse_trading_calendar.csv` had **no producer anywhere in the
package** — an orphan artifact consumed by script 26 and named in no map row. That mattered more
than it looked, because it is the only source of the session ordinal, and the session ordinal is
what makes an overnight return an overnight return. It is now produced by `02_build_panel.py`.

**Where:** `scripts/02_build_panel.py`, `data/processed/audit/panel_trades_duplicate_audit.csv`,
`data/processed/README.md`, §3 duplicate paragraph, §9. **Test:**
`test_daily_trades_duplicate_audit_is_shipped_and_explicit`.

### Item 2 (Critical) — validate the instrument classification ✅ RESOLVED, and it found two errors

An external NEPSE security master covering 652 currently listed securities, with instrument
category and par value, now ships as `data/external/nepse_security_master.csv`.
`scripts/27_classification_audit.py` reconciles it against the rule-based classifier and emits the
confusion table the report asked for (manuscript Table 9).

**Agreement: 509 of 511 matched securities, 99.61%.** That rate is the substantive answer to
*"How do we know the result is not itself an artifact of the classification heuristic?"* — an
independent listing reproduces the classification on which §5.1 depends.

The two disagreements were both genuine rule failures, in opposite directions, and both are
corrected because the master governs:

| Symbol | Rule said | Master says | What it is |
|---|---|---|---|
| `ADBLB` | equity | **debenture** | "4% Agricultural Bond" — the debenture ticker pattern does not match `ADBLB`, so a bond sat inside the ordinary-equity universe |
| `NADEP` | promoter | **equity** | "NADEP Laghubitta Bittiya Sanstha" — the promoter pattern `(?:PO|P)$` fired on the trailing letter of the company's own name |

*Beyond the report:* **`ADBLB` turned out to be the single security the Section 3 analysis screens
were already dropping.** So no headline result was ever computed with a bond in the equity
universe — but that was luck rather than design, which is exactly the vulnerability the report
identified. The correction is disclosed in §3 rather than absorbed silently.

**Headline effect:** the estimation universe moves from 291 securities / 143,149 stock-days to
**292 / 143,718**. Ten securities delisted, merged or renamed during the sample do not appear in
the master and retain their rule-based classification; they are listed in
`table37_classification_disagreements.csv` and disclosed in §10.

**Where:** `src/nepsevol/universe/__init__.py`, `scripts/27_classification_audit.py`, §3, §6.1,
Table 9, §8 Discussion, §10, §11 Conclusion — the item names all five locations, and the
agreement rate now appears in the Discussion and the Conclusion as well as in §3. **Tests:** `test_master_overrides_the_rule_on_the_two_known_rule_failures`,
`test_rule_and_master_agree_on_the_overwhelming_majority`,
`test_equity_sample_contains_no_security_the_master_calls_non_equity`.

### Item 3 (Critical) — the same-day liquidity sort is endogenous ✅ RESOLVED

§6.2 now states plainly that sorting stock-days on their own transaction count cannot separate a
liquidity effect from the volatility–activity relationship, and that the gradient must not be read
causally. Table 6 reports both predetermined sorts alongside the published one.

Under the predetermined sorts the least active bucket sits **above** the matched proxy, at
**1.022** (security-level) and **1.025** (lagged 60-session), rather than below. As the report
observed, this strengthens the paper: the claim is that range estimators do not collapse in thin
equity, and under a non-endogenous sort the thin bucket is *closer* to the proxy.

**Where:** §6.2 (new paragraph after Table 4), §6.5, Table 6, §10 sixth limitation,
`scripts/26_robustness.py`.

### Item 5 (Critical) — the Yang–Zhang sample mismatch ✅ RESOLVED

Both halves reproduced exactly before being fixed.

**Numerator/denominator mismatch.** Confirmed: `mean(v_yz)` over 137,107 rows divided by
`mean(v_cc)` over 142,858 gives 1.2455; row-matched on the common set gives 1.2849 — the report
predicted ~1.285. Every ratio is now evaluated on the intersection of its own numerator and
benchmark masks (`_matched()` in `scripts/26_robustness.py`), and each table reports the matched
row count so the reader can see the supports differ.

**Previous close.** Confirmed: 230 transitions skip more than one detected session, the largest
skipping 91, and the supplied `prev_close` column disagrees with the prior observed row on 315
rows. §4.5 defines the previous close as the previous *genuine session*, so
`previous_session_close()` now returns NaN across any gap and Yang–Zhang is undefined there.
`table38_prev_close_reconciliation.csv` sets all three candidate definitions side by side.

**Final figure: Yang–Zhang stands at 1.288 [1.244, 1.331] on 135,899 matched stock-days**, not
1.245. §7.2 no longer treats it as interchangeable with close-to-close.

**Where:** `src/nepsevol/estimators/range_.py`, `scripts/26_robustness.py`, §4.5, §6.5, §7.2,
Table 7. **Tests:** `test_ratio_is_computed_on_the_intersection_of_numerator_and_denominator`,
`test_previous_close_is_nan_across_a_session_gap`, `test_yang_zhang_does_not_span_gaps`, and
`test_unmatched_rows_change_the_ratio_so_matching_is_not_cosmetic` — which fails if row matching
ever becomes a no-op, so the other tests cannot pass vacuously.

---

## The remaining mandatory items

| # | Item | Status | Where |
|---|---|---|---|
| 4 | Add the missing §6.5 and its tables | ✅ | New §6.5 with five checks; Tables 6, 7, 8 added; every map row now points at a table the manuscript prints |
| 6 | "Validation" → co-movement; report the Oct 2012 sensitivity | ✅ | Abstract, §2, §6.3 (retitled "An options-market co-movement check"), §8, §10, §11. Both orderings reported: 0.776/0.796 full sample, 0.832/0.796 excluding the session; explicitly "no ordering in either direction" |
| 7 | "Under identical code" | ✅ | §6.2 and the Figure 5 caption now read "under identical estimator code — though not identical input screens…" |
| 8 | State the actual numerical screens | ✅ | §3: positive prices; \|ln(C/C₋₁)\| < 0.5; range ceiling ln((1+L)/(1−L)) = 0.2007 (±10%) and 0.3023 (±15%); 4 rows fail; one security removed |
| 9 | Separate the trading-week date from the price-limit date | ✅ | **Mon–Fri effective 2026-04-06; ±15% effective 2026-04-20.** Split into `trading_calendar.WEEK_REFORM` and `clean.limits.REGIMES` |
| 10 | Duplicate-audit scope | ✅ | §3 now audits the two panels separately; the frozen-build limitation is gone because item 1 resolved it |
| 11 | Proxy-relative language | ✅ | Abstract, §5.4, §6.2, §6.4, §8, §10, §11; table headers read "SD ratio to matched proxy" |
| 12 | Delete the estimator hierarchy | ✅ | §7.2 retitled "Choosing an estimator: a conditional framework"; explicitly states no loss function, therefore no universal ordering |
| 13 | Report the empirical annualisation factor | ✅ | §7.1: **A ≈ 229.6** sessions/year (569 sessions over 2.48 years); 226 under Sun–Thu, 257 under Mon–Fri |
| 14 | Address cross-sectional dependence | ✅ | Two-way (security × date) multiway bootstrap in `src/nepsevol/inference.py` |
| 15 | Synchronise §9 with the repository | ✅ | §9 names scripts 02, 03, 09, 12, 13, 17, 19, 22, 24, 25, 26, 27; map rewritten; two tests fail if the map names a producer or output that does not exist |
| 16 | Expand §10 Limitations | ✅ | Six new limitations: screen asymmetry, endogenous sorting, rule-based classification, imperfect proxy, the bounds of the intervals, and data provenance. **Also fixed a defect inherited from the submitted PDF:** the list ran First, Second, *Fourth* — "Third" had been lost in an earlier edit. The ordinals are now renumbered contiguously by script rather than by hand, so appending to the list cannot reintroduce a gap |
| 17 | Soften the conclusion | ✅ | §11 rewritten in three paragraphs; keeps "do not collapse", drops accuracy claims |
| 18 | Verify equations and expand the literature | ◐ Partial | See below |
| 19 | Update the stale §5.4 Rogers–Satchell figure | ✅ | See below |
| 20 | One internally consistent package | ✅ | Full pipeline re-run; 79 tests pass; every manuscript number interpolated from the frozen tables by script |

### Item 14, in detail

The previous bootstrap clustered on security only, then supported "statistically distinguishable"
language. A security-clustered interval absorbs serial dependence within a security; it does not
absorb the common market-date shocks that dominate a frontier cash market.

The multiway (pigeonhole) bootstrap of Davezies, D'Haultfœuille & Guyonvarch (2021) now resamples
securities and calendar dates jointly. **Two-way intervals are 1.8× to 2.8× wider**, and the
count of liquidity buckets whose Parkinson interval excludes 1.000 falls from **12 of 15 to 8 of
15**. The manuscript quotes the two-way intervals, and §10 states that even these are a lower
bound on total uncertainty because they do not model the proxy's own measurement error. The paper
therefore took option 1 of the two the report offered, and kept option 2's caution as well.

### Item 19, in detail — the report's suggested number is superseded

The report asked for the stale 0.998 to become "approximately 1.004". Under the master-validated
universe it is **0.999**. Rather than argue about a third decimal, §5.4 now reports what the
uncertainty shows: the 95% two-way interval is **[0.843, 1.147]**, and successive revisions of
this project have produced thin-group point estimates of 0.998, 1.004 and 0.999 under sample
perturbations far smaller than that interval. The defensible claim is that the ratio is
indistinguishable from the matched proxy, and §5.4 makes the scope point — that a matched proxy
removes the apparent shortfall — rather than a claim about direction. This is item 11 applied to
item 19.

### Item 18, in detail — partially resolved, and honestly labelled

**Bibliographic records: all five confirmed** against publisher-deposited Crossref metadata. This
corrected one error the report also caught: **Yang & Zhang (2000) is *Journal of Business* 73(3),
477–492**, not 477–491. The reference list is fixed and re-sorted.

**Equations: still transcribed from secondary presentations**, because the primary full texts are
paywalled. This is labelled as such in `estimators/range_.py` rather than quietly upgraded. Two
partial offsets: the Rogers & Satchell abstract was obtained and independently confirms both
claims the docstring makes (the estimator uses high, low and closing prices; the authors
themselves propose a discretisation correction), and the non-negativity proofs in the docstrings
are derived from the equations *as written in this code*, so a transcription error would surface
as a proof that fails — which the test suite checks numerically. For AddRS the three provenance
levels remain distinguished and the primary derivation remains unverified; "AddRS is unbiased" is
never written unqualified.

**Literature:** fifteen references added across realized-volatility measurement (Andersen &
Bollerslev 1998; Andersen et al. 2003; Barndorff-Nielsen & Shephard 2002), range-based estimation
(Alizadeh et al. 2002; Christensen & Podolskij 2007; Martens & van Dijk 2007; Molnár 2012),
microstructure noise (Hansen & Lunde 2006; Zhang et al. 2005; Roll 1984), non-synchronous trading
(Scholes & Williams 1977), emerging-market volatility (Bekaert & Harvey 1997), imperfect proxies
(Patton 2011, already present, now load-bearing in §10), forecast comparison (Hansen et al. 2011),
and multiway inference (Cameron et al. 2011; Davezies et al. 2021).

---

## Optional changes

| Suggestion | Status |
|---|---|
| Retitle to something the evidence supports | ✅ **"Daily OHLC Volatility Measurement in a Cash-Only Frontier Market: Evidence from the Nepal Stock Exchange"** |
| Three explicit research questions | ✅ §1 now poses them and the empirical sections answer them in order |
| "SD ratio relative to matched proxy" in tables | ✅ All table headers |
| Drop R² from the one-regressor comparison | ✅ Removed from the manuscript and the QA ledger. Retained in `table15_vix_anchor.csv` with a `R2_minus_corr_squared` column that is 0.000, so the identity is checkable |
| Position as a measurement/data-design paper | ✅ Abstract and §1 |
| Anonymisation and submission formatting | ✅ `paper/submission/`: anonymised manuscript (body **and** file metadata, verified by reading the saved file back), separate title page, and one cover letter per recommended journal in the recommended order |

---

## Corrections made while auditing this response

Three gaps surfaced when the delivered manuscript was checked back against each item's stated
*scope* rather than its headline, and all three are now fixed:

- **Item 2 names §5.1, §6.1, Table 3, the Discussion and the Conclusion.** The validation result
  had reached the first three but not the last two. §8 and §11 now both state that the
  composition finding rests on a classification reconciled against an external listing, which is
  what lets it be read as a fact about the market rather than about our rule.
- **Item 16 names duplicate-panel provenance.** Item 1 discharged that limitation, but silently.
  §10 now says so explicitly — the panels were rebuilt and reproduce exactly, and what remains is
  only that the raw downloads are not redistributable.
- **The §10 ordinals were broken in the submitted PDF** (First, Second, Fourth) and appending to
  a broken sequence would have compounded it. They are renumbered by script.

## What did not change, and why

- **The frozen data.** The rebuild reproduced the shipped panel exactly, so the panel was not
  replaced — it was verified.
- **The detected sessions.** Correcting the April 2026 schedule date changed the schedule
  *cross-check*, not the detector, which reads the data. Sessions: 569 before and after. What
  changed is that two Friday sessions are no longer recorded as off-schedule and two Sundays no
  longer as inferred holidays. The genuine weekday holiday of 14 April (Nepali New Year) is still
  detected — a test asserts this, because an over-broad version of that test failed and was
  corrected rather than loosened.
- **The paper's central claim.** Range estimators do not collapse in thin ordinary equity. It
  survives every robustness check and is stronger under the predetermined sorts.

## Numbers that moved

| Quantity | Was | Now | Cause |
|---|---|---|---|
| Ordinary-equity securities | 291 | **292** | Item 2: −ADBLB (a bond), +NADEP (an equity) |
| Ordinary-equity stock-days | 143,149 | **143,718** | Item 2 |
| Yang–Zhang / total-risk proxy | 1.245 | **1.288** | Item 5: row matching + session-aware previous close |
| Thin-equity RS / open-to-close | 0.998 → 1.004 | **0.999 [0.843, 1.147]** | Items 2 and 19; the interval is the point |
| Liquidity buckets with CI excluding 1 | 12 of 15 | **8 of 15** | Item 14: date clustering added |
| Trading-week reform date | 2026-04-20 | **2026-04-06** | Item 9 |
| Yang & Zhang (2000) pages | 477–491 | **477–492** | Item 18 |
| Tests passing | 52 | **79** | Items 1, 2, 5, 9, 14, 15 |

Everything else — Tables 1–5, Figures 1–6, and every §3, §5, §6.1–6.4 quantity not listed above —
moves only by the small amounts implied by the one-security change to the equity universe.

## Reproducing this response

```bash
pip install -r requirements.txt && pip install -e .
bash run_paper_analysis.sh          # runs every producer script, the test suite, then refreshes
                                     # SUBMISSION_MANIFEST.json; see that file for the current
                                     # script and test counts rather than a number fixed here
python paper/apply_referee_revisions.py
python paper/build_submission_set.py
```

`run_paper_analysis.sh` regenerates every table and figure from the frozen panels.
`apply_referee_revisions.py` rebuilds the manuscript from those tables and **fails** if a
superseded figure survives in the text or if a headline number does not reach it.
`scripts/02_build_panel.py` reproduces the item-1 rebuild, given lawful access to the raw
downloads.
