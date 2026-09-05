"""M13: the Nepal literature search log, screening ledger, and evidence matrix.

Three tables, deliberately separated, because a query-level log cannot cleanly hold study-level
decisions:

    table71_nepal_search_log.csv        one row per EXECUTED QUERY
    table73_nepal_screening_ledger.csv  one row per LOCATED RECORD
    table72_nepal_literature_matrix.csv one row per UNIQUE INCLUDED STUDY

and they must reconcile exactly:

    located - duplicates - excluded - inaccessible = included (= rows in the matrix)

This script asserts that identity and fails if it breaks.

WHAT THIS IS NOT. This is a TARGETED search, not a systematic review: it does not document an
exhaustive database protocol, and it cannot. Much Nepali finance research appears in
NepJOL-indexed national journals with uneven discoverability and inconsistent full-text access,
so coverage is partial by construction. Every claim the manuscript makes about the literature
must therefore be phrased as what this search found, never as a property of the literature.

INACCESSIBLE IS NOT EXCLUDED. A study that is in scope but whose text could not be retrieved is
preserved in the ledger with retrieval_status = "inaccessible". It is not silently dropped, and
it is not counted as evidence.

FULL TEXT IS THE BAR FOR NOVELTY. `full_text_verified` is TRUE only where the full text was
actually read. Rows verified from a journal landing page carry metadata and a verbatim abstract
-- enough to place a study at index or security level when the abstract says so -- but NOT
enough to support a claim that no prior study did something. Only full-text rows may do that.

A WORKED EXAMPLE OF WHY. A search summary reported that Neupane, Neupane & Baral (2022)
"included 26 securities that were actively traded from mid-July 2005 to mid-July 2008 out of 147
companies". Reading the PDF shows that sentence sits in that paper's LITERATURE REVIEW,
describing a study it cites; the paper's own sample is ONE security (Everest Bank) over
2010-2021. Had the snippet been trusted, the matrix would have carried a fabricated
multi-security NEPSE study. That record is kept in the ledger as `snippet_conflation`.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import bootstrap
bootstrap()

import pandas as pd

TAB = ROOT / "output" / "tables"
TAB.mkdir(parents=True, exist_ok=True)

SEARCH_DATE = "2026-09-04"

# ── table 71: one row per executed query ────────────────────────────────────────────────────
search_log = pd.DataFrame([
    {"query_id": "Q1", "source": "web search engine (general index)",
     "exact_query": "NEPSE Nepal Stock Exchange volatility GARCH study journal article",
     "date_run": SEARCH_DATE, "filters": "none",
     "n_results_returned": 6, "n_records_taken_forward": 5,
     "access_limitations": "several hits are aggregator pages (ResearchGate, Academia.edu) "
                           "rather than publisher records; NepJOL PDFs sometimes return "
                           "binary that must be parsed locally"},
    {"query_id": "Q2", "source": "web search engine (general index)",
     "exact_query": "Nepal Stock Exchange NEPSE liquidity market efficiency thin trading "
                    "research paper",
     "date_run": SEARCH_DATE, "filters": "none",
     "n_results_returned": 9, "n_records_taken_forward": 6,
     "access_limitations": "one relevant item (a thin-trading adjustment study) appeared only "
                           "inside the engine's own prose summary, with no resolvable record"},
    {"query_id": "Q3", "source": "web search engine (general index)",
     "exact_query": "NEPSE Nepal range-based volatility Parkinson Garman-Klass estimator high "
                    "low prices",
     "date_run": SEARCH_DATE, "filters": "none",
     "n_results_returned": 9, "n_records_taken_forward": 0,
     "access_limitations": "NO Nepal-specific hits: every result was general or international "
                           "range-estimator literature already cited in this paper"},
    {"query_id": "Q4", "source": "web search engine (general index)",
     "exact_query": "Nepal Stock Exchange firm-level individual securities volatility daily "
                    "data study",
     "date_run": SEARCH_DATE, "filters": "none",
     "n_results_returned": 7, "n_records_taken_forward": 5,
     "access_limitations": "engine summary conflated a cited study with the citing paper; see "
                           "the ledger's snippet_conflation record"},
    {"query_id": "C1", "source": "citation chaining (reference list of R13, read in full text)",
     "exact_query": "reference list of Neupane, Neupane & Baral (2022), Pravaha 28(1)",
     "date_run": SEARCH_DATE, "filters": "Nepal-specific references only",
     "n_results_returned": 2, "n_records_taken_forward": 2,
     "access_limitations": "references give citations only; full texts not retrieved here"},
])
search_log.to_csv(TAB / "table71_nepal_search_log.csv", index=False)

# ── table 73: one row per located record ────────────────────────────────────────────────────
#
# status vocabulary
#   duplicate_of      : canonical record id this row duplicates (blank if canonical)
#   retrieval_status  : full_text | metadata_and_abstract | inaccessible | not_retrieved
#   inclusion         : included | excluded | inaccessible | duplicate
#   exclusion_reason  : required whenever inclusion == "excluded"
L = [
    # ---- Q1
    ("R01", "Volatility of Daily Nepal Stock Exchange (NEPSE) Index Return: A GARCH Family Models",
     "Dangal, D. N.; Gajurel, R. P.", 2021, "Q1", "", "metadata_and_abstract", "included", ""),
    ("R02", "Nepalese Stock Market Volatility Using ARCH and GARCH Models",
     "Dhungana (initials not stated in record)", 2025, "Q1", "", "inaccessible", "inaccessible", ""),
    ("R03", "A Study on Nepalese Stock Market Volatility (Academia.edu posting)",
     "not stated", 0, "Q1", "", "not_retrieved", "excluded",
     "no resolvable bibliographic record: no journal, volume, year or DOI identifiable"),
    ("R04", "Evidence from GARCH-family models (JORI, partial title only)",
     "not stated", 0, "Q1", "", "inaccessible", "inaccessible", ""),
    ("R05", "Butwal Campus Journal 5(1) item surfaced without a resolvable title",
     "not stated", 2022, "Q1", "", "not_retrieved", "excluded",
     "record could not be resolved to a specific article; title not recoverable from the hit"),
    # ---- Q2
    ("R06", "Time-Varying Efficiency and Volatility Regimes in Nepal Stock Exchange (NEPSE): "
            "Evidence from Daily Data under the Adaptive Market Hypothesis",
     "Karki, S.", 2026, "Q2", "", "metadata_and_abstract", "included", ""),
    ("R07", "Weak Form of Efficiency in Nepal Stock Exchange (KMC Research Journal)",
     "not stated in record", 0, "Q2", "", "inaccessible", "inaccessible", ""),
    ("R08", "Technical Analysis and Efficient Market Hypothesis in the Nepal Stock Exchange",
     "not stated in record", 0, "Q2", "", "inaccessible", "inaccessible", ""),
    ("R09", "Weak Form of Market Efficiency in Nepalese Stock Market (ResearchGate posting)",
     "not stated", 0, "Q2", "", "not_retrieved", "excluded",
     "aggregator posting without a resolvable publisher record"),
    ("R10", "Non-linear properties of Nepalese capital market: a multifractal detrended "
            "fluctuation analysis approach",
     "not stated in record", 0, "Q2", "", "inaccessible", "inaccessible", ""),
    ("R11", "Thin-trading-adjusted weak-form efficiency result attributed to Dangol (2012)",
     "Dangol (attribution from a search-engine prose summary only)", 2012, "Q2", "",
     "not_retrieved", "excluded",
     "appeared only inside the search engine's own summary text; no record, DOI or journal "
     "could be resolved, so it cannot be verified or cited"),
    ("R12", "Performance analysis and prediction of NEPSE for investment decision using machine "
            "learning techniques",
     "not stated in record", 0, "Q2", "", "not_retrieved", "excluded",
     "out of scope: return prediction, not volatility measurement or estimator evaluation"),
    # ---- Q4
    ("R13", "Trading Volume, Trading Price, Trading Frequency and Stock Return Volatility of "
            "Everest Bank Limited",
     "Neupane, B.; Neupane, D.; Baral, P.", 2022, "Q4", "", "full_text", "included", ""),
    ("R14", "Pravaha 28(1) direct PDF download URL for the Everest Bank study",
     "Neupane, B.; Neupane, D.; Baral, P.", 2022, "Q4", "R13", "full_text", "duplicate", ""),
    ("R15", "Stock Market Volatility in Nepal (Academia.edu posting)",
     "not stated", 0, "Q4", "", "not_retrieved", "excluded",
     "no resolvable bibliographic record"),
    ("R16", "Volatility Analysis of Nepalese Stock Market (ResearchGate posting)",
     "not stated", 0, "Q4", "", "inaccessible", "inaccessible", ""),
    ("R17", "Multi-security NEPSE study reported by a search summary as '26 securities, "
            "mid-July 2005 to mid-July 2008, 147 listed companies'",
     "misattributed by the search summary to Neupane et al. (2022)", 0, "Q4", "",
     "not_retrieved", "excluded",
     "snippet_conflation: reading R13's full text shows this sentence is in ITS literature "
     "review, describing a study it cites, not R13's own sample; the underlying study could "
     "not be identified from R13's reference list with confidence"),
    # ---- C1 (citation chaining out of R13's verified reference list)
    ("R18", "Daily stock price behavior of commercial banks in Nepal",
     "Baral, K. J.; Shrestha, S. K.", 2006, "C1", "", "inaccessible", "inaccessible", ""),
    ("R19", "A note on price-volume dynamics in an emerging stock market",
     "Bajracharya, K.", 2020, "C1", "", "inaccessible", "inaccessible", ""),
]
ledger = pd.DataFrame(L, columns=[
    "record_id", "title", "authors", "year", "source_query", "duplicate_of",
    "retrieval_status", "inclusion", "exclusion_reason"])
ledger.to_csv(TAB / "table73_nepal_screening_ledger.csv", index=False)

# ── table 72: one row per unique INCLUDED study, the ten frozen evidence fields ──────────────
M = [
    {
        "record_id": "R13",
        "citation": "Neupane, B., Neupane, D., & Baral, P. (2022). Trading Volume, Trading "
                    "Price, Trading Frequency and Stock Return Volatility of Everest Bank "
                    "Limited. Pravaha, 28(1), 45-52.",
        "doi_or_link": "https://nepjol.info/index.php/pravaha/article/view/57970",
        "study_period": "January 2010 - December 2021 (12 years)",
        "frequency": "daily",
        "level": "security-level (ONE security: Everest Bank Limited; 1,873 observations)",
        "volatility_measure": "descriptive dispersion of daily returns computed from CLOSING "
                              "prices only (mean, standard deviation, coefficient of "
                              "variation); no high/low/open information used",
        "model_or_question": "relationship between stock returns and trading volume, trading "
                             "price and trading frequency; correlation and causal-comparative "
                             "design, not volatility-measurement methodology",
        "thin_trading_treatment": "not addressed",
        "ohlc_range_estimators_used": "none",
        "main_finding": "volume and price have a positive and significant association with "
                        "stock returns for this bank over the period",
        "full_text_verified": True,
        "verification_level": "full text read (PDF parsed locally)",
        "verification_note": "sample, period, observation count and closing-price-only data "
                             "confirmed in the Research Methodology section",
    },
    {
        "record_id": "R01",
        "citation": "Dangal, D. N., & Gajurel, R. P. (2021). Volatility of Daily Nepal Stock "
                    "Exchange (NEPSE) Index Return: A GARCH Family Models. Tribhuvan "
                    "University Journal, 36(01), 31-44.",
        "doi_or_link": "https://doi.org/10.3126/tuj.v36i01.43514",
        "study_period": "1 June 2006 - 7 April 2021",
        "frequency": "daily (3,392 observations)",
        "level": "index-level (NEPSE index)",
        "volatility_measure": "conditional variance from GARCH-family models",
        "model_or_question": "GARCH(1,1), GARCH-M(1,1), TGARCH(1,1), EGARCH(1,1), PGARCH(1,1); "
                             "volatility clustering and leverage effects",
        "thin_trading_treatment": "not stated in the abstract or record",
        "ohlc_range_estimators_used": "none stated",
        "main_finding": "volatility clustering and a leverage effect are present; symmetric "
                        "models fit the full period better, asymmetric models the "
                        "before/after-earthquake subperiods",
        "full_text_verified": False,
        "verification_level": "publisher record and verbatim abstract",
        "verification_note": "index level is stated explicitly in the abstract; fields marked "
                             "'not stated' were not checked against the full text",
    },
    {
        "record_id": "R06",
        "citation": "Karki, S. (2026). Time-Varying Efficiency and Volatility Regimes in Nepal "
                    "Stock Exchange (NEPSE): Evidence from Daily Data under the Adaptive "
                    "Market Hypothesis. NRB Economic Review, 37(1), 28-58.",
        "doi_or_link": "https://doi.org/10.3126/nrber.v37i1.92673",
        "study_period": "July 1995 - February 2025",
        "frequency": "daily",
        "level": "index-level (NEPSE index returns)",
        "volatility_measure": "conditional variance from GARCH; Markov-switching volatility "
                              "regimes",
        "model_or_question": "adaptive market hypothesis: time-varying efficiency and "
                             "volatility regimes",
        "thin_trading_treatment": "not stated in the abstract or record",
        "ohlc_range_estimators_used": "none stated",
        "main_finding": "persistent inefficiency 1999-2019 then emerging efficiency 2021-2025; "
                        "two volatility regimes; no statistically significant leverage effect",
        "full_text_verified": False,
        "verification_level": "publisher record and verbatim abstract",
        "verification_note": "index level is stated explicitly in the abstract",
    },
]
matrix = pd.DataFrame(M)
matrix.to_csv(TAB / "table72_nepal_literature_matrix.csv", index=False)

# ── reconciliation: the three tables must agree exactly ─────────────────────────────────────
located = len(ledger)
duplicates = int((ledger.inclusion == "duplicate").sum())
excluded = int((ledger.inclusion == "excluded").sum())
inaccessible = int((ledger.inclusion == "inaccessible").sum())
included = int((ledger.inclusion == "included").sum())

print("M13: Nepal literature search, screening and evidence matrix")
print("=" * 108)
print(f"  queries executed                {len(search_log)}")
print(f"  located records                 {located}")
print(f"    - duplicates                  {duplicates}")
print(f"    - excluded                    {excluded}")
print(f"    - inaccessible (PRESERVED)    {inaccessible}")
print(f"    = included studies            {included}")
assert located - duplicates - excluded - inaccessible == included, "ledger does not reconcile"
assert included == len(matrix), "the matrix does not contain exactly the included studies"
assert set(matrix.record_id) == set(ledger.record_id[ledger.inclusion == "included"]), \
    "matrix rows and ledger inclusions name different studies"
for _, r in ledger[ledger.inclusion == "excluded"].iterrows():
    assert str(r.exclusion_reason).strip(), f"{r.record_id} excluded without a reason"
for _, r in ledger[ledger.inclusion == "duplicate"].iterrows():
    assert str(r.duplicate_of).strip(), f"{r.record_id} marked duplicate without a canonical id"
    assert r.duplicate_of in set(ledger.record_id), f"{r.record_id} points at a missing canonical"

n_full = int(matrix.full_text_verified.sum())
print(f"\n  of the {included} included studies, {n_full} had the FULL TEXT read; "
      f"{included - n_full} are verified only to publisher record and abstract.")
print("  -> only the full-text row(s) may support a claim about what prior work did NOT do.")

print("\nWhat the search found, stated as a finding about the SEARCH:")
lvl = matrix.level.str.split("-").str[0]
print(f"  index-level studies included    {(lvl == 'index').sum()}")
print(f"  security-level studies included {(lvl == 'security').sum()}")
print(f"  studies using OHLC/range estimators (Parkinson, Garman-Klass, Rogers-Satchell, "
      f"Yang-Zhang): {(matrix.ohlc_range_estimators_used.str.lower() != 'none').sum() - (matrix.ohlc_range_estimators_used.str.lower() == 'none stated').sum()}")
print("  Q3, aimed squarely at Nepal-specific range estimators, returned NO Nepal-specific hit.")
print("\n  These are counts from a TARGETED search with documented access limits, not a")
print(f"  characterisation of the Nepali literature as a whole. {inaccessible} located records")
print("  could not be retrieved and are preserved as inaccessible rather than dropped.")
print("\nwrote table71, table72, table73")
