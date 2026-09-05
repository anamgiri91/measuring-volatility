# M13 — the contribution claim, frozen, and the search protocol behind it

**The contribution statement below is frozen before the literature search is expanded**, for the
same reason the M7 decision rule was: a claim written after reading the search results tends to
be shaped to fit whatever the search happened to return.

## The contribution statement

### As frozen before the search (superseded)

> This study does not introduce volatility analysis to Nepal. It contributes a security-level
> evaluation of daily OHLC volatility measurement under NEPSE-specific market microstructure and
> data-quality constraints, complementing literature focused primarily on index-level volatility
> dynamics, GARCH modeling, and market efficiency.

### As narrowed after the matrix was frozen (current)

> A targeted search located both index-level research and at least one security-level NEPSE
> study based on closing prices. Accordingly, this study does not claim to introduce
> security-level volatility analysis to Nepal. Its contribution is a reproducible comparison of
> daily OHLC volatility estimators under NEPSE-specific calendar, staleness, thin-trading, and
> closing-rule constraints.

**Why it changed, and in which order.** The first version rested on an index-versus-security
distinction. The search then located Neupane, Neupane and Baral (2022), a security-level NEPSE
volatility study — so "complementing literature focused primarily on index-level volatility
dynamics" was no longer supportable, and the phrase "primarily index-level" is retired
throughout. What survives the evidence is not the level of analysis but the **measurement**
question: that study uses closing prices only and asks an association question about volume and
frequency, not a question about how to measure volatility from a daily OHLC bar.

The narrowing happened **after** the three tables were frozen and reconciled, which is the
correct order: the claim was tested against the evidence rather than the evidence assembled to
fit the claim.

## Wording rules (binding)

1. **No "almost entirely".** The claim that the Nepal literature is index-level may be stated
   only as what a documented search found, with its coverage and its limits, never as a
   characterisation of the whole literature.
2. **"Targeted" or "structured", never "systematic".** A systematic review requires documented
   databases, date ranges, queries, screening rules, inclusion/exclusion criteria and counts at
   each stage. This is not that, and will not be described as that.
3. **No "first".** Not unless a reproducible search returns no prior security-level OHLC study —
   and even then, "we did not find" is the honest form, not "there is none".
4. **Thin-trading adjustment is adjacent prior work.** Papers that correct returns for thin
   trading (e.g. the weak-form-efficiency strand) address a related problem but are not
   estimator evaluations. They are cited as adjacent, not as equivalent or superseded.
5. **Nepal-specific novelty is separated from frontier-market novelty.** The range-estimator
   literature (Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang, realised range, microstructure
   noise) is large and international; nothing here is novel *to that literature*. What is
   specific to Nepal is the market's own constraints and the measurement decisions they force.

## The literature matrix

`output/tables/table70_nepal_literature_matrix.csv`, one row per study, with:

| Field | Purpose |
|---|---|
| `citation` | Full reference as it will appear in the manuscript |
| `doi_or_link` | Verifiable identifier — prevents citation errors |
| `study_period`, `frequency` | Coverage |
| `level` | index-level / security-level / other — carries the contribution distinction |
| `volatility_measure` | Identifies direct comparators |
| `model_or_question` | Separates measurement from model fitting |
| `thin_trading_treatment` | Connects to this paper's subject |
| `ohlc_range_estimators_used` | Tests the actual novelty claim |
| `main_finding` | Represents the study accurately |
| `full_text_verified` | TRUE only where the full text was read, not a snippet |

**Rows with `full_text_verified = FALSE` may not support any novelty claim in the manuscript.**
They may be listed as located-but-unverified, and the count of each is reported.

## Search protocol, to be recorded as executed

Sources queried, the exact query strings, the dates run, what was screened in and out, and why.
Recorded in `output/tables/table71_nepal_search_log.csv` so the coverage claim is reproducible
rather than asserted. Known limitation to state plainly: much Nepali finance research appears in
NepJOL-indexed national journals with uneven discoverability, so a search of this kind cannot
claim exhaustive coverage — which is itself a reason rule 1 above exists.
