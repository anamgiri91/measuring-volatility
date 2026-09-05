> **SUPERSEDED — 2026-09-02.** This document was written *before* the referee report of
> 2 September 2026 and lists the manuscript changes required by package revision 2. Every change
> it specifies has since been applied, and all five items it left unresolved at the end (§D) have
> been resolved or explicitly bounded. **Read `REFEREE_RESPONSE.md` instead.** This file is
> retained for provenance: it records what was known before the report, which is what makes the
> report's findings legible.
>
> In particular §D is now out of date. D1 (classification validation) and D3 (rebuilding the
> panels from raw) are resolved; D2 (the April 2026 dates) is resolved against contemporary
> reporting; D5 (recompiling the manuscript) is resolved by
> `paper/apply_referee_revisions.py`. One item from §A is superseded rather than applied: the
> thin-equity Rogers-Satchell figure is 0.999 under the corrected instrument universe, not 1.004,
> and Section 5.4 now reports its interval instead of arguing about the third decimal.

---

# Manuscript revisions

Every change below is required by the code in this package revision. Each entry gives the **exact
current sentence** and its **exact replacement**, so the edits can be applied to the LibreOffice
source without re-deriving anything.

Three categories:

- **[NUMBER]** — a printed figure changed because a defect was fixed. Not optional.
- **[CLAIM]** — the evidence no longer supports the sentence as written.
- **[ADD]** — new material the referee report requires.

At the end: **items I could not resolve**, which need the author's own inputs.

---

## A. Numbers that changed

Only two published figures moved. Both come from the corrected Rogers-Satchell numerator in
`scripts/12_benchmark_diagnosis.py` (audit register `A-005 extension`; referee item 9): RS was
averaged over every row while its benchmark used only strictly consecutive sessions, so the ratio
divided two different samples.

| Location | Was | Now |
|---|---|---|
| §5.4 | NEPSE thin equity RS / open-to-close = **0.998** | **1.004** |
| §5.4 (implicit, Figure 4) | NEPSE dense equity RS / open-to-close = 1.059 | **1.021** |
| Figure 4 Panel A | RS/CC dense 1.092, thin 1.260 | **1.053**, **1.266** |

Everything else — Tables 1, 3, 4, 5, Figures 1, 2, 3, 5, 6, and every Section 3, 5.1, 5.3, 6.1,
6.2, 6.3 and 6.4 quantity — is **byte-identical** to the submitted version. Replace
`output/figures/fig14_benchmark_diagnosis.*` with the regenerated file.

### §5.4 — [NUMBER]

> **Current:** "For the NEPSE thin-equity group, Rogers-Satchell is 0.998 relative to the matched open-to-close benchmark."

> **Replace with:** "For the NEPSE thin-equity group, Rogers-Satchell is 1.004 relative to the matched open-to-close benchmark, and 1.021 for the dense group. Numerator and benchmark are computed on the same strictly-consecutive-session rows; averaging the estimator over a wider row set than its benchmark moves the dense figure to 1.059 and is the kind of sample mismatch this section is about."

The rhetorical point is unaffected — arguably strengthened. The uncorrected 0.998 sat just *below*
one, which invited the reading that some downward bias remained; the corrected 1.004 sits just
above, consistent with the rest of §6.4.

---

## B. Claims the evidence no longer supports

### B1. The India VIX ordering — the single most important change

`output/tables/table31_nifty_outlier_sensitivity.csv`. The NIFTY series is read without the
screens the NEPSE panel passes, and one session dominates it: **2012-10-05**, the NSE flash crash
(O 5815.00, H 5815.35, L 4888.20, C 5746.95). Its log range is 0.1737, the largest of 4,037
sessions, while its close-to-close return is only −0.70%. It is a *range* event, so it inflates
21-session Parkinson for 21 sessions and leaves close-to-close almost untouched — and India VIX
does not move, because a fat-finger order is not a volatility regime change.

| | Full sample | Excluding 2012-10-05 |
|---|---|---|
| VIX ~ Parkinson correlation | 0.776 | **0.832** |
| VIX ~ close-to-close correlation | 0.796 | 0.796 |
| NIFTY Parkinson / OC (SD) | 0.978 | 0.959 |
| NIFTY RS / OC (SD) | 0.980 | **0.932** |

**The ordering reverses.** The day is retained in all reported results — excluding real recorded
extremes is exactly the discretion this paper warns against — but every sentence ranking the two
estimators must carry the caveat.

#### Abstract — [CLAIM]

> **Current:** "Both therefore co-move strongly with the options-derived volatility state, but Parkinson does not outperform close-to-close in this validation."

> **Replace with:** "Both therefore co-move strongly with the options-derived volatility state. Parkinson does not outperform close-to-close in the full sample, but that ordering is not robust: it rests on a single session, the October 2012 NSE flash crash, whose extreme range enters the Parkinson series without a corresponding move in either close-to-close volatility or the VIX. Excluding it, Parkinson's correlation rises to 0.832 and the ordering reverses. Neither estimator is shown to dominate."

Also in the Abstract, replace "A cross-market check provides an external validation anchor rather
than an implied-volatility substitute" with "**A cross-market check provides external co-movement
evidence rather than estimator validation or an implied-volatility substitute**". Apply the same
substitution wherever "validation anchor" appears (§2, §6.3 heading, Table 1's India VIX row —
already updated in `paper_table1_data_used.csv` if you regenerate; if you keep the printed table,
change the last cell to "Options-based external co-movement check").

#### §6.3 — [CLAIM] + [ADD]

Retitle **6.3 An options-market validation anchor: India VIX** →
**6.3 An options-market co-movement check: India VIX**.

> **Current:** "On 3,999 matched observations, Parkinson volatility has a correlation of 0.776 with India VIX and an R² of 0.602 in a simple linear relationship. The corresponding close-to-close series has a correlation of 0.796 and an R² of 0.634. Both measures therefore track the volatility state represented in option prices strongly, but the range-based measure does not outperform close-to-close in this particular validation."

> **Replace with:** "On 3,999 matched observations, Parkinson volatility has a correlation of 0.776 with India VIX; the corresponding close-to-close series has a correlation of 0.796. (Because each regression has a single regressor and an intercept, R² is the square of the reported correlation and is not reported separately.) Both measures therefore track the volatility state represented in option prices strongly.
>
> The ordering between them, however, is not robust. The NIFTY series is used without the screens applied to the NEPSE panel, and a single session dominates it: 5 October 2012, the NSE flash crash, whose log range of 0.174 is the largest in the 4,037-session sample while its close-to-close return is only −0.70%. Because it is a range event rather than a close-to-close event, it raises the 21-session Parkinson series for twenty-one sessions with no corresponding movement in India VIX. Excluding that one session, Parkinson's correlation rises to 0.832 and close-to-close is unchanged at 0.796, reversing the ranking. The session is a genuine recorded exchange session and is retained in all reported results; we quantify its influence rather than delete it, because discarding real extremes is precisely the discretion this paper argues against. The conclusion we draw is therefore only that both measures co-move strongly with the option-implied volatility state, and that this exercise does not establish an ordering between them in either direction."

Add a sentence noting that consecutive 21-session windows overlap heavily, so the correlations
are descriptive (already in §10 — cross-reference it here).

#### §8 Discussion — [CLAIM]

> **Current:** "Under the paper-consistent 21-session aggregation, however, close-to-close volatility tracks India VIX somewhat more closely than Parkinson in this sample, so the external validation does not establish range-estimator dominance."

> **Replace with:** "Under the paper-consistent 21-session aggregation, close-to-close volatility tracks India VIX marginally more closely than Parkinson in the full sample, but that margin depends entirely on one flash-crash session and reverses without it. The external evidence therefore establishes co-movement for both measures and dominance for neither. It also illustrates the paper's own argument from the other direction: a range estimator is sensitive to a single extreme observed range, which is why the screens and diagnostics of Section 5 matter as much as the choice of formula."

#### §11 Conclusion — [CLAIM]

> **Current:** "The NIFTY 50 and India VIX comparison further shows that a correctly aggregated rolling Parkinson measure tracks an options-derived volatility state strongly, although close-to-close volatility tracks it somewhat more closely in this sample."

> **Replace with:** "The NIFTY 50 and India VIX comparison further shows that a correctly aggregated rolling Parkinson measure tracks an options-derived volatility state strongly. Close-to-close tracks it marginally more closely in the full sample, but the two orderings cannot be separated once the influence of a single flash-crash session is accounted for."

### B2. "Under identical code" — [CLAIM]

The estimator functions are identical across regimes. The input screens are not, and cannot be:
the NEPSE screens are derived from NEPSE's own price limits and duplicate pathologies and have no
NSE analogue. The NEPSE panel is an audited sample compared against two unaudited ones — which is
*why* B1 above is possible.

#### §6.2 — [CLAIM]

> **Current:** "Under identical code, Parkinson's standard-deviation ratio relative to open-to-close variation is 0.978 for the NIFTY 50."

> **Replace with:** "Under identical estimator code — though not identical input screens, since the NEPSE panel additionally passes the positivity, return and rules-derived range filters of Section 3 while the NIFTY and NEPSE index series pass only a positivity filter — Parkinson's standard-deviation ratio relative to open-to-close variation is 0.978 for the NIFTY 50."

Also update the Figure 5 caption: "Cross-market estimator ratios under identical code" →
"**Cross-market estimator ratios under identical estimator code**".

### B3. The open-to-close benchmark is a proxy, not ground truth — [CLAIM]

`output/tables/table32_predetermined_liquidity.csv` now supplies cluster-bootstrap intervals, and
**12 of 15 liquidity buckets have a Parkinson 95% interval that excludes 1.000**. A ratio near one
is therefore not "no detectable bias"; it is a small but statistically distinguishable deviation
from an imperfect proxy.

Apply throughout §6.2, §6.4, §8 and §11:

| Replace | With |
|---|---|
| "no downward Rogers-Satchell bias is detectable" | "no downward Rogers-Satchell deviation from the matched open-to-close proxy is detectable" |
| "estimate historical and realized volatility credibly" | "estimate historical and realized volatility with deviations from a matched open-to-close proxy that are small and, where they are statistically distinguishable from one, economically modest" |
| "range estimators do not collapse" | (keep — this one is supported) |

§6.4 already contains the right qualification ("The result is therefore evidence about performance
relative to the available proxy, not proof that the estimator's theoretical bias premise is
false"). Promote that sentence: it should appear once in §6.2 and once in §11, not only in §6.4.

### B4. Same-day liquidity buckets are endogenous — [CLAIM] + [ADD]

Volatility causes trading activity, so sorting stock-days on their **own** trade count cannot
separate a liquidity effect from the volatility–activity relationship. `scripts/26_robustness.py`
re-runs the sort two predetermined ways, and **the gradient changes materially**:

| Bucket | Same-day (Table 4/5) | Security-level | Lagged 60-session |
|---|---|---|---|
| Q1 (thinnest) | 0.951 [0.922, 0.978] | **1.023** [1.002, 1.044] | **1.025** [1.005, 1.046] |
| Q2 | 1.058 [1.042, 1.075] | 1.036 [1.021, 1.051] | 1.030 [1.017, 1.043] |
| Q3 | 1.041 [1.028, 1.055] | 1.012 [1.000, 1.024] | 1.028 [1.014, 1.042] |
| Q4 | 1.005 [0.993, 1.016] | 0.982 [0.964, 0.999] | 1.011 [1.000, 1.021] |
| Q5 (densest) | 0.975 [0.966, 0.983] | **0.938** [0.915, 0.958] | 0.987 [0.975, 0.999] |

*Parkinson / open-to-close, SD scale, 95% security-cluster bootstrap intervals.*

Under both predetermined sorts the thinnest bucket sits **above** one, not below, and the
densest sits below. The dip at Q1 in Table 4 is therefore substantially an artifact of sorting
stock-days on their own activity. **This does not damage the paper's thesis — it strengthens it.**
The headline claim is that range estimators do not collapse in thin equity; under a
non-endogenous sort the thin bucket is *closer* to the benchmark, not further.

Add to §6.2, after the Table 4 discussion:

> "The buckets in Table 4 are formed on same-day transaction counts. Because volatility itself
> raises trading activity, that sort is endogenous and cannot separate a liquidity effect from
> the volatility–activity relationship. Table 6 therefore repeats the exercise with two
> predetermined sorts: one assigning each security to a single bucket by its full-sample median
> trade count, and one assigning each stock-day by that security's median trade count over its
> prior sixty sessions. Under both, the least active bucket sits slightly above the matched
> benchmark rather than below it, and the most active bucket sits below. The non-monotonicity in
> Table 4 is therefore partly an artifact of endogenous sorting; the substantive conclusion, that
> range estimators remain close to the matched benchmark across the equity liquidity range, holds
> under every sort and is if anything more favourable to the thin group under the predetermined
> ones."

### B5. Claimed vs. evaluated estimator set — [CLAIM] + [ADD]

The Abstract names six estimators; the empirical core reported three.
`output/tables/table33_estimator_ratios_bootstrap.csv` now evaluates all six against
**scope-matched** benchmarks:

| Estimator | Scope | Benchmark | SD ratio | 95% CI |
|---|---|---|---|---|
| Parkinson | intraday | open-to-close 2nd moment | 1.000 | [0.992, 1.009] |
| Garman-Klass | intraday | open-to-close 2nd moment | 1.001 | [0.988, 1.012] |
| Rogers-Satchell | intraday | open-to-close 2nd moment | 1.036 | [1.022, 1.050] |
| AddRS | intraday | open-to-close 2nd moment | 1.225 | [1.214, 1.236] |
| Close-to-close | total | close-to-close 2nd moment | 1.000 | definitional anchor |
| Yang-Zhang | total | close-to-close 2nd moment | 1.245 | [1.227, 1.264] |

Yang-Zhang and close-to-close are scored against close-to-close scope because they include
overnight variation; scoring Yang-Zhang against open-to-close would repeat the exact benchmark
mismatch §5.4 diagnoses. Close-to-close against itself is 1 by construction and carries no
information — it anchors the scale.

Two consequences for the text. First, Yang-Zhang at 1.245 against total-risk scope is a **new
substantive finding** and belongs in §7.2: it overshoots the total-risk benchmark by about as
much as AddRS overshoots the intraday one, so the §7.2 recommendation to "use close-to-close or
Yang-Zhang when the overnight component is part of the risk object" should be qualified. Second,
Garman-Klass at 1.001 is now empirically evaluated rather than used only as a data-validity
diagnostic, which closes the scope gap.

### B6. Estimator hierarchy without a stated criterion — [CLAIM]

§7.2 recommends Rogers-Satchell as primary, yet Table 7 places Parkinson (1.000) and
Garman-Klass (1.001) closer to the matched benchmark than Rogers-Satchell (1.036). Replace the
ranked hierarchy with a conditional framework:

> **Replace §7.2's hierarchy paragraph with:** "The evidence in this project does not support a
> single ranking, and the choice should follow the risk object rather than a general ordering.
> Against the matched open-to-close benchmark on the full ordinary-equity sample, Parkinson
> (1.000) and Garman-Klass (1.001) sit closest to the benchmark, with Rogers-Satchell slightly
> above it (1.036); the differences are small but, under a security-cluster bootstrap,
> statistically distinguishable. Rogers-Satchell remains attractive where drift robustness is
> valuable and is the natural primary when the maintained model is a drifting price process.
> Parkinson is the simplest cross-check and the most efficient use of the range where the high
> and low are reliable. Where the overnight component belongs in the risk object, close-to-close
> is the transparent baseline, and Yang-Zhang should be used with the caveat that it stands at
> 1.245 of the matched total-risk benchmark in this sample. AddRS should be treated as a
> model-dependent alternative, not a default correction. We state no criterion-free ordering
> because we report no loss function: these are deviations from an imperfect proxy, not accuracy
> against latent variance."

---

## C. New material

### C1. New §6.5 — [ADD]

Insert after §6.4, before §7:

> **6.5 Robustness**
>
> Four checks bound the results above.
>
> *Predetermined liquidity.* Repeating the Section 6.2 sort on predetermined rather than same-day
> activity changes the gradient but not the conclusion (Table 6, discussed in Section 6.2).
>
> *Uncertainty.* All ratios are reported with 95% percentile intervals from a bootstrap that
> resamples securities, not stock-days, because observations within a security are serially
> dependent and share a liquidity regime. Twelve of the fifteen liquidity buckets have a Parkinson
> interval excluding one, so the small deviations from the benchmark are statistically
> distinguishable even though they are economically modest. The bootstrap does not absorb common
> market-date shocks, so the intervals should be read as a lower bound on total uncertainty.
>
> *OHLC repair.* The envelope repair widens the high and low to contain the open and close, and
> the range estimators are functions of exactly that range, so the repair can only push range
> variance upward. Excluding all 122 repaired ordinary-equity rows rather than correcting them
> changes no estimator ratio by more than 0.0001 (Table 8). The repair is therefore immaterial to
> every reported conclusion.
>
> *Cross-market benchmark.* The NIFTY reference numbers depend materially on one session; see
> Section 6.3 and Section 10.

### C2. §7.1 annualisation — [ADD]

Sections 4 and 7 argue that A should be the market's own session count, but no reported quantity
demonstrated it. `output/tables/table35_nepse_annualization.csv` now derives it.

Add after the §7.1 formula:

> "For NEPSE over the study window, the detected trading calendar yields **A ≈ 230 genuine
> sessions per year** (569 sessions over 2.48 years), against the 252 a developed-market default
> would impose — a difference of roughly 9% in variance terms and 4.5% in volatility terms. The
> figure differs across the schedule change: about 226 sessions per year under the Sunday–Thursday
> regime and about 257 under the Monday–Friday regime, which is a further reason to date the
> regime boundary explicitly rather than annualise the whole sample at one rate."

### C3. §10 Limitations — [ADD]

Add three paragraphs:

> "Fifth, the cross-market comparison uses the NIFTY series without the instrument, return and
> range screens applied to the NEPSE panel, because those screens are derived from NEPSE's own
> price-limit rules and have no NSE analogue. With roughly 4,000 NIFTY sessions against roughly
> 24,000 stock-days per NEPSE bucket, a single extreme NIFTY session carries far more leverage on
> the reference figures than any single NEPSE observation carries on the NEPSE ones. Section 6.3
> quantifies that leverage.
>
> Sixth, the liquidity gradients in Tables 4 and 5 are formed on same-day transaction counts and
> are therefore endogenous; Table 6 reports predetermined alternatives and the two differ.
>
> Seventh, instrument classification is rule-based — ticker convention validated against par-value
> bands — and has not been checked against an authoritative SEBON or NEPSE security master. The
> price separation between funds and other classes is clean in this sample, and the debenture
> band is tight, but the classification carries substantial evidentiary weight in Section 5.1 and
> an independent listing-master validation remains outstanding."

### C4. §9 Reproducibility — [ADD]

> **Current:** "The reproducibility map links the cross-market fingerprint to script 09, the benchmark decomposition to script 12, the opening-auction diagnostics to script 13, the AddRS comparison to scripts 17 and 19, the universe-composition result to script 22, and duplicate reconciliation to script 24."

> **Replace with:** "The reproducibility map links the descriptive screens and composition audit to script 03, the cross-market fingerprint and the India VIX co-movement check to script 09, the benchmark decomposition to script 12, the opening-auction diagnostics to script 13, the AddRS comparison to scripts 17 and 19, the universe-composition result to script 22, duplicate reconciliation to script 24, the robustness suite of Section 6.5 to script 26, and the manuscript-facing summary tables to script 25."

This closes a real gap: script 25 produces Tables 1, 3, 4 and 5 and was previously named nowhere
in the paper, the README order, or the map.

### C5. §3 — explicit cleaning thresholds and duplicate scope — [ADD]

Add to the cleaning paragraph:

> "The screens are, in order: all four prices strictly positive; absolute log close-to-close
> return below 0.5, which removes splits and transcription errors; and a rules-derived feasible
> range ceiling, log(H/L) ≤ log((1+L)/(1−L)) for the daily price limit L in force, giving 0.2007
> under the ±10% regime and 0.3023 under the ±15% regime. The range ceiling screens what a
> return filter cannot: a corrupted high or low leaves the close untouched and passes every
> return-based test while contaminating exactly the input a range estimator consumes. Four rows
> fail it. One security is removed entirely."

Also add, after the existing duplicate-reconciliation paragraph:

> "This duplicate audit covers the historical long-form panel. The 2024–2026 daily-trades panel
> that carries the paper's main equity estimates is subject to the same classification rule, but
> its audit was not produced for the frozen build; the reconciliation is reported here for the
> long-form panel only."

---

## D. Items I could not resolve — these need you

1. **Instrument classification validation (referee 6).** Requires an authoritative SEBON/NEPSE
   listing master, which is not in the package and which I cannot obtain. Until it is done, C3's
   third paragraph is the honest disclosure. This is the single largest remaining referee item.

2. **The April 2026 regime dates (referee 12).** The referee states that the Monday–Friday
   trading-week change took effect in early April 2026, while 20 April 2026 is the price-band and
   circuit-rule date, and that the code conflates them. The code currently uses `2026-04-20` for
   **both** (`trading_calendar/__init__.py:38` and `clean/limits.py:37`). I have **not** changed
   this, because it needs a primary NEPSE/SEBON notice rather than my inference, and because
   `trading_calendar`'s own docstring records data evidence (`2026-04-05` is a Sunday with full
   activity) that appears to contradict an early-April weekday break. Please verify against the
   official notices and, if the two dates differ, split `SCHEDULES` from `REGIMES` — they are
   already separate constants in separate modules, so the change is one line each. Note that the
   detected-session logic is data-driven and does not depend on the documented date; only the
   `scheduled` cross-check column does.

3. **Rebuilding the processed panels under the corrected duplicate rule (referee 7).** The fix is
   in `scripts/02_build_panel.py` and is correct, but it cannot be exercised without the raw
   inputs. The shipped panels were built under the old `keep="last"` path. If you have the raw
   files, re-run `02_build_panel.py`, confirm `panel_trades_duplicate_audit.csv` shows no
   conflicting classes, and regenerate. If it *does* show conflicts, the affected rows must be
   excluded and every downstream number re-derived.

4. **Literature expansion, raw-data provenance detail, and journal targeting** (referee 13, 14,
   15, and section 5). These are authorial. The one mechanical item: the referee reports Yang &
   Zhang (2000) as pp. 477–492; your reference list has 477–491. Verify against JSTOR.

5. **Recompiling the PDF.** This package contains only the compiled
   `paper/NEPSE_Volatility_Final_Manuscript.pdf`, not its LibreOffice source. I cannot apply the
   edits above to the PDF without degrading the layout, equations and tables. Send me the `.odt`
   or `.docx` and I will apply every change in this document directly and return a compiled
   manuscript.
