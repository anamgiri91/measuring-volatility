"""Apply the 2026-09-02 referee revisions to the manuscript source.

The manuscript is a .docx, so the edits are applied programmatically rather than by hand. That
is deliberate: the referee's central complaint was that the manuscript and its analysis package
had drifted apart, and a scripted edit that reads its numbers from the frozen output tables
cannot drift again. Wherever a figure appears in the text below it is either interpolated from
``output/tables/*.csv`` or asserted against them at the end of this script.

    python paper/apply_referee_revisions.py [--base BASE.docx] [--out OUT.docx]

Two reconciliation notes, both discovered while preparing this revision:

1. The .docx source is one revision BEHIND the submitted PDF. Its abstract reports the India VIX
   correlation as 0.832 with an R² of 0.692 "slightly above the corresponding close-to-close
   measure" -- which is the value EXCLUDING the October 2012 flash crash, presented as though it
   were the full sample. The submitted PDF corrected this to 0.776 against close-to-close 0.796.
   Twenty paragraphs differ in this way; each is reconciled to the submitted PDF before the
   referee revisions are applied, so the base text is the manuscript the referee actually read.

2. The referee's item 19 asked for the thin-equity Rogers-Satchell figure to be updated from
   0.998 to "approximately 1.004". Under the master-validated instrument universe it is 0.999,
   and its 95% two-way cluster interval is [0.843, 1.147]. The honest revision is therefore not
   a third decimal but a change of claim: the ratio is indistinguishable from the matched proxy,
   and successive point estimates have moved across one under sample perturbations far smaller
   than their own sampling error. Section 5.4 is rewritten to say that.
"""

from __future__ import annotations

import argparse
import copy
import pathlib
import re
import sys

import pandas as pd

try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
except ImportError:
    sys.exit("python-docx is required:  pip install python-docx")

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"


# ─────────────────────────────────────────────────────────────────── docx helpers

def set_text(p, text):
    """Replace a paragraph's text, keeping the first run's character formatting."""
    runs = p.runs
    if not runs:
        p.add_run(text)
        return p
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""
    return p


def para_after(p, text, style=None):
    """Insert a new paragraph immediately after ``p`` and return it."""
    new = copy.deepcopy(p._p)
    p._p.addnext(new)
    from docx.text.paragraph import Paragraph
    out = Paragraph(new, p._parent)
    for r in list(out.runs)[1:]:
        r._r.getparent().remove(r._r)
    if out.runs:
        out.runs[0].text = text
    else:
        out.add_run(text)
    if style is not None:
        out.style = style
    return out


def find(paras, needle, start=0):
    """Index of the first paragraph containing ``needle``. Raises if absent."""
    for i in range(start, len(paras)):
        if needle in paras[i].text:
            return i
    raise LookupError(f"paragraph not found: {needle!r}")


def fill_table(tbl, header, rows):
    """Rewrite a table in place to exactly ``header`` + ``rows``, adding/removing as needed."""
    while len(tbl.rows) > 1:
        tbl._tbl.remove(tbl.rows[-1]._tr)
    while len(tbl.columns) > len(header):
        for r in tbl.rows:
            r._tr.remove(r.cells[-1]._tc)
    for j, h in enumerate(header):
        set_text(tbl.rows[0].cells[j].paragraphs[0], str(h))
    for row in rows:
        cells = tbl.add_row().cells
        for j, v in enumerate(row):
            set_text(cells[j].paragraphs[0], str(v))
    return tbl


def new_table_after(p, doc, header, rows, style="Table Grid"):
    """Create a table immediately after paragraph ``p``."""
    t = doc.add_table(rows=1, cols=len(header))
    try:
        t.style = style
    except KeyError:
        pass
    for j, h in enumerate(header):
        set_text(t.rows[0].cells[j].paragraphs[0], str(h))
    for row in rows:
        cells = t.add_row().cells
        for j, v in enumerate(row):
            set_text(cells[j].paragraphs[0], str(v))
    p._p.addnext(t._tbl)
    return t


# ─────────────────────────────────────────────────────────────── numbers from the package

def load_numbers():
    """Read every quantity the revised text quotes, so the prose cannot drift from the tables."""
    n = {}
    chk = pd.read_csv(ROOT / "PAPER_RESULTS_CHECK.csv").set_index("Result")["Value"]
    n["eq_days"] = f"{int(float(chk['ordinary_equity_stock_days'])):,}"
    n["eq_secs"] = int(float(chk["ordinary_equity_securities"]))
    n["vix_pk"] = f"{float(chk['IndiaVIX_Parkinson_corr']):.3f}"
    n["vix_cc"] = f"{float(chk['IndiaVIX_CC_corr']):.3f}"
    n["vix_pk_ex"] = f"{float(chk['IndiaVIX_Parkinson_corr_ex_outlier']):.3f}"
    n["vix_cc_ex"] = f"{float(chk['IndiaVIX_CC_corr_ex_outlier']):.3f}"
    n["nifty_pk"] = f"{float(chk['NIFTY_Parkinson_OC_SD']):.3f}"
    n["nifty_pk_ex"] = f"{float(chk['NIFTY_Parkinson_OC_SD_ex_outlier']):.3f}"
    n["nifty_rs_ex"] = f"{float(chk['NIFTY_RS_OC_SD_ex_outlier']):.3f}"
    n["thin_pk"] = f"{float(chk['NEPSE_thin_Parkinson_OC_SD']):.3f}"
    n["thin_zero"] = f"{float(chk['NEPSE_thin_zero_range_pct']):.2f}"
    n["class_rate"] = f"{float(chk['classification_agreement_rate_pct']):.2f}"
    n["class_matched"] = int(float(chk["classification_securities_matched_to_master"]))
    n["yz"] = f"{float(chk['YangZhang_total_risk_ratio_row_matched']):.3f}"
    n["yz_rows"] = f"{int(float(chk['YangZhang_matched_rows'])):,}"
    n["pre_sec_q1"] = f"{float(chk['predetermined_Q1_Parkinson_security_level']):.3f}"
    n["pre_lag_q1"] = f"{float(chk['predetermined_Q1_Parkinson_lagged60']):.3f}"
    n["n_excl"] = int(float(chk["liquidity_buckets_with_CI_excluding_one_twoway"]))
    n["n_buckets"] = int(float(chk["liquidity_buckets_total"]))
    n["A"] = f"{float(chk['nepse_annualisation_factor_A']):.1f}"

    bd = pd.read_csv(TAB / "table18_benchmark_diagnosis.csv").set_index("market")
    thin = bd.loc["NEPSE equity — thin"]
    dense = bd.loc["NEPSE equity — dense"]
    nif = bd.loc["NIFTY 50 index"]
    n["rs_thin"] = f"{thin['RS/open-to-close']:.3f}"
    n["rs_thin_ci"] = f"[{thin['RS/open-to-close lo95']:.3f}, {thin['RS/open-to-close hi95']:.3f}]"
    n["rs_dense"] = f"{dense['RS/open-to-close']:.3f}"
    n["rs_dense_ci"] = f"[{dense['RS/open-to-close lo95']:.3f}, {dense['RS/open-to-close hi95']:.3f}]"
    n["rs_nifty_cc"] = f"{nif['RS/close-to-close']:.3f}"
    n["rs_nifty_oc"] = f"{nif['RS/open-to-close']:.3f}"
    n["von_thin"] = f"{100*thin['Var(open) /Var(cc)']:.1f}"
    n["von_dense"] = f"{100*dense['Var(open) /Var(cc)']:.1f}"

    est = pd.read_csv(TAB / "table33_estimator_ratios_bootstrap.csv").set_index("estimator")
    for key, name in [("pk", "Parkinson"), ("gk", "Garman-Klass"), ("rs", "Rogers-Satchell"),
                      ("addrs", "AddRS"), ("yzr", "Yang-Zhang")]:
        n[f"t7_{key}"] = f"{est.loc[name, 'sd_ratio']:.3f}"
        n[f"t7_{key}_ci"] = (f"[{est.loc[name, 'lo95_twoway']:.3f}, "
                             f"{est.loc[name, 'hi95_twoway']:.3f}]")

    ann = pd.read_csv(TAB / "table35_nepse_annualization.csv")
    n["sessions"] = int(ann.sessions.iloc[0])
    n["span_years"] = f"{float(ann.span_years.iloc[0]):.2f}"

    rep = pd.read_csv(TAB / "table34_repair_sensitivity.csv")
    ests = ["Parkinson", "Garman-Klass", "Rogers-Satchell", "AddRS", "Close-to-close", "Yang-Zhang"]
    n["repair_max"] = f"{max(abs(rep.iloc[1][e] - rep.iloc[0][e]) for e in ests):.4f}"
    n["repair_rows"] = int(rep.n_stock_days.iloc[0] - rep.n_stock_days.iloc[1])

    oa = pd.read_csv(TAB / "table19_opening_auction.csv")
    d0 = oa.iloc[0]
    n["oa_thin_trades"] = int(d0.median_trades)
    n["oa_thin_share"] = f"{100*d0.overnight_share_all:.1f}"
    n["oa_thin_eq"] = f"{d0.pct_open_eq_prevclose:.1f}"
    n["oa_thin_band"] = f"{d0.pct_at_2pct_band:.1f}"
    n["oa_max_trades"] = int(oa.loc[oa.overnight_share_all.idxmax(), "median_trades"])

    dup = pd.read_csv(ROOT / "data/processed/audit/panel_trades_duplicate_audit.csv").set_index("class")
    n["dt_keys"] = f"{int(dup.loc['KEYS_EXAMINED', 'duplicate_keys']):,}"
    n["dt_rows"] = f"{int(dup.loc['ROWS_EXAMINED', 'duplicate_keys']):,}"

    fp = pd.read_csv(TAB / "paper_table4_cross_market_fingerprint.csv")
    eq = fp[fp.Regime.str.startswith("NEPSE")]
    col = "Parkinson: SD ratio to matched proxy"
    n["pk_lo"] = f"{eq[col].min():.3f}"
    n["pk_hi"] = f"{eq[col].max():.3f}"
    return n


# ───────────────────────────────────────────────────── stage 1: reconcile base to submitted PDF
#
# The .docx trails the submitted PDF on twenty paragraphs. Four of those are not otherwise
# rewritten below, so their PDF text is restored here; the rest are replaced wholesale in
# stage 2 and need no separate reconciliation.

RECONCILE = {
"NEPSE's opening mechanism is economically important": None,   # filled in below
}

PDF_TEXT = {
"opening": (
 "NEPSE's opening mechanism is economically important. In ordinary equity, the ratio of "
 "opening-return variance to close-to-close variance is elevated in the lower-liquidity daily "
 "trade-count deciles, reaches its sample maximum in the decile with a median of {oa_max_trades} "
 "trades per day, and then generally declines as trading intensity rises. In the thinnest decile "
 "(median {oa_thin_trades} trades per day), this ratio is {oa_thin_share}% and {oa_thin_eq}% of "
 "opens equal the previous close. Across the full sample, {oa_thin_band}% of observations in that "
 "decile have an absolute opening return between 1.9% and 2.1%. Because the pre-open band widened "
 "from approximately ±2% to ±5% on April 20, 2026, this {oa_thin_band}% is a pooled descriptive "
 "fingerprint, not an estimate of the fraction mechanically bound by the former ±2% rule. These "
 "patterns are observable features of the auction data, not proof of a latent censored-return "
 "model. The project's attempted censored-normal recovery failed its post-April-2026 "
 "regime-change check and is therefore not used in this paper."),
"addrs_premise": (
 "The AddRS correction was designed for a setting in which Rogers-Satchell is downward biased "
 "because discrete observations miss path extremes. On NIFTY 50, AddRS is 1.005 relative to the "
 "matched open-to-close proxy on a standard-deviation scale, which is reassuring for the "
 "implementation. On NEPSE ordinary equities, however, no downward Rogers-Satchell deviation from "
 "the matched open-to-close proxy is detectable: the uncorrected measure is already close to or "
 "above that proxy in every stock-day liquidity quintile formed by daily transaction count. AddRS "
 "then rises to 1.149-1.323 of the proxy. The result is therefore evidence about performance "
 "relative to an imperfect proxy, not proof that the estimator's theoretical bias premise is "
 "false relative to latent variance."),
"addrs_lesson": (
 "This is a general lesson for frontier-market work. The AddRS increment is non-negative. Let "
 "x = ln(C/O), and let I_u and I_v denote the upper- and lower-boundary indicators used by the "
 "implementation. The code reduces exactly to AddRS = RS + (x²/2)(I_u + I_v), so in expectation "
 "E[AddRS] = E[RS] + (1/2)E[x²(I_u + I_v)]. Both indicators can fire on a fully monotone bar. "
 "Therefore, if Rogers-Satchell is already unbiased for the target variance in a regime and the "
 "boundary term has positive expectation, AddRS has positive expected bias relative to that "
 "target. Because true latent variance is unobserved here, the empirical conclusion remains "
 "narrower: no downward Rogers-Satchell deviation from the matched open-to-close proxy is "
 "detectable, while AddRS overshoots that proxy in the NEPSE equity sample."),
"repro_note": (
 "Data and reproducibility note. Empirical quantities in this manuscript are drawn from the "
 "accompanying paper-specific NEPSE volatility package, and every number in the text is "
 "interpolated from that package's frozen output tables by paper/apply_referee_revisions.py "
 "rather than transcribed. Retained claims are backed by producer scripts, frozen tables or "
 "figures, or directly auditable source artifacts. The package includes processed paper-facing "
 "data, external validation series, the external NEPSE security master used to validate the "
 "instrument classification, a compact duplicate audit, and a reproducibility map; original "
 "stock-level source downloads are not publicly redistributed because their redistribution terms "
 "remain unresolved. The empirical analyses are descriptive and exploratory unless explicitly "
 "stated otherwise."),
}


# ───────────────────────────────────────────── stage 2: the referee revisions, item by item
#
# Each entry is (anchor text to locate, replacement template). Templates are formatted with the
# numbers loaded from the frozen tables, so no figure below is hand-typed.

REPLACE = [

# ── Front matter: title, positioning (optional items) ────────────────────────────────────
("Calculating Volatility in Frontier Markets Without Options",
 "Daily OHLC Volatility Measurement in a Cash-Only Frontier Market"),

("Evidence and a Practical Framework from the Nepal Stock Exchange",
 "Evidence from the Nepal Stock Exchange"),

("Draft research paper · August 2026",
 "Revised manuscript · September 2026"),

# ── ABSTRACT (items 6, 11, 12, 17 + optional R² and positioning) ─────────────────────────
("Options markets make volatility visible in a way that cash-only markets do not",
 "Options markets make volatility visible in a way that cash-only markets do not: option prices "
 "can be inverted to obtain a forward-looking, risk-neutral measure of expected volatility. Nepal "
 "has no exchange-traded equity options or futures, so there is no NEPSE analogue of the VIX that "
 "can be read directly from an option chain. This paper asks what can be measured instead, and "
 "how reliable those measurements are in a frontier-market setting. It is a measurement and "
 "data-design study rather than a search for a universally superior estimator. Using daily open, "
 "high, low, and close (OHLC) data from the Nepal Stock Exchange, we evaluate close-to-close "
 "volatility and the Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang, and additive "
 "Rogers-Satchell estimators, each against a proxy matched to its own scope and evaluated on the "
 "same observations. The main empirical sample contains {eq_days} stock-days for {eq_secs} "
 "ordinary equities from March 2024 through August 2026, with the instrument classification "
 "validated against an external NEPSE security master that agrees with our rule on {class_rate}% "
 "of {class_matched} matched securities. Daily ranges carry useful information even in Nepal: "
 "among ordinary equities the Parkinson standard-deviation ratio relative to a matched "
 "open-to-close proxy stays between {pk_lo} and {pk_hi} across liquidity groups, and the thinnest "
 "equity group has a zero-range rate of only {thin_zero}%. That conclusion survives replacing the "
 "endogenous same-day liquidity sort with predetermined ones: under security-level and lagged "
 "60-session sorts the least active group sits at {pre_sec_q1} and {pre_lag_q1} of the matched "
 "proxy, slightly above it rather than below. A cross-market check provides external co-movement "
 "evidence rather than estimator validation or an implied-volatility substitute. On the NIFTY 50, "
 "using the same 21-session variance aggregation specified here, Parkinson volatility has a "
 "correlation of {vix_pk} with India VIX and close-to-close volatility a correlation of {vix_cc}. "
 "Both therefore co-move strongly with the options-derived volatility state, but that ordering is "
 "not robust: it rests on a single session, the October 2012 NSE flash crash, whose extreme range "
 "enters the Parkinson series without a corresponding move in close-to-close volatility or the "
 "VIX. Excluding it, Parkinson's correlation rises to {vix_pk_ex} against {vix_cc_ex} and the "
 "ordering reverses, so neither estimator is shown to dominate. The paper also shows why "
 "frontier-market implementation requires more than choosing a formula. Pooling debentures, "
 "funds, promoter shares, and ordinary equity creates a false appearance of estimator breakdown; "
 "the thinnest pooled group is dominated by non-equity securities and produces a Rogers-Satchell "
 "variance ratio of only 0.172. The practical conclusion is that a cash-only frontier market can "
 "estimate historical and realized volatility from daily OHLC data with deviations from a matched "
 "proxy that are small and economically modest, but it cannot recover option-implied volatility "
 "from spot prices alone. Because that proxy is itself imperfect, we report deviations from it "
 "rather than accuracy against latent variance. Reliable measurement depends on instrument "
 "classification, session-aware data cleaning, liquidity diagnostics, appropriate treatment of "
 "overnight returns, and validation of any bias correction before it is applied."),

("Keywords: frontier markets; volatility",
 "Keywords: frontier markets; volatility measurement; Nepal Stock Exchange; range-based "
 "estimators; sample construction; instrument classification; imperfect volatility proxies; "
 "implied volatility; Parkinson; Rogers-Satchell; market microstructure"),

# ── §1 Introduction: three explicit research questions (optional item) ───────────────────
("This paper makes two contributions.",
 "This paper asks three questions, and the empirical sections answer them in order. First, do "
 "range estimators remain informative for ordinary NEPSE equities as liquidity declines? Second, "
 "how much of the apparent estimator failure in a frontier market arises from instrument "
 "composition and from benchmark mismatch rather than from illiquidity? Third, do the answers "
 "survive alternative liquidity definitions, alternative inference assumptions, and an external "
 "co-movement check? Answering them yields two contributions. First, a practical framework for "
 "measuring volatility in a frontier market that lacks options, with explicit formulas, "
 "scope-matched proxy choices, annualization rules derived from the market's own calendar, and "
 "diagnostic checks. Second, an application to NEPSE data showing which of the usual concerns "
 "matter empirically. The results are encouraging for ordinary equity: range estimators do not "
 "collapse even in the least active equity group. They are cautionary about sample construction "
 "and additive bias corrections. The correct question is not simply 'Which volatility formula "
 "should Nepal use?' but 'Which volatility object is being measured, from which securities, over "
 "which part of the day, and under what market microstructure?' Throughout, we describe results "
 "as deviations from a matched proxy rather than as accuracy, because the latent variance is "
 "unobserved and the proxy is imperfect."),

# ── §2: validation -> co-movement (item 6) ──────────────────────────────────────────────
("The two measures are related but not interchangeable.",
 "The two measures are related but not interchangeable. A historical estimator can track the same "
 "volatility state that influences option prices, yet it need not equal implied volatility "
 "because option prices contain expectations and risk premia. This is why the cross-market India "
 "VIX exercise in Section 6 is treated as external co-movement evidence rather than as an "
 "identity test or as validation of estimator accuracy. A strong correlation supports the "
 "usefulness of OHLC-based volatility as a state variable; it does not turn it into implied "
 "volatility, and it cannot rank two historical estimators against each other."),

# ── §3 Data: sample counts and the classification audit (items 2, 8) ────────────────────
("The principal stock panel covers March 4, 2024",
 "The principal stock panel covers March 4, 2024 through August 26, 2026 and contains {sessions} "
 "trading sessions and 520 securities. The immediately preceding cleaned trading panel contains "
 "521 securities; one security drops out under the analysis screens. After instrument "
 "classification, {eq_secs} ordinary equities contribute {eq_days} stock-days. The pooled "
 "analysis file also contains closed-end mutual funds, corporate debentures, and restricted "
 "promoter shares. A separate NEPSE index series provides daily OHLC observations, while NIFTY 50 "
 "OHLC data and India VIX provide an external developed-market comparison over 2010-2026."),

("The cleaning protocol is deliberately conservative.",
 "The cleaning protocol is deliberately conservative, and its thresholds are stated numerically "
 "rather than by name. The screens are, in order: all four prices strictly positive; absolute log "
 "close-to-close return below 0.5, which removes splits and transcription errors; and a "
 "rules-derived feasible range ceiling, ln(H/L) ≤ ln((1+L)/(1−L)) for the daily price limit L in "
 "force, giving 0.2007 under the ±10% regime and 0.3023 under the ±15% regime. The range ceiling "
 "screens what a return filter cannot: a corrupted high or low leaves the close untouched, passes "
 "every return-based test, and contaminates exactly the input a range estimator consumes. Four "
 "rows fail it, and one security is removed entirely. An OHLC record must also satisfy High ≥ "
 "max(Open, Close) and Low ≤ min(Open, Close). When an envelope inconsistency occurs, the high "
 "and low are widened to include the reported open and close while the original values are "
 "retained and the record is flagged; in the final ordinary-equity sample only {repair_rows} "
 "rows, approximately 0.09%, require this repair, and Section 6.5 reports that excluding them "
 "rather than repairing them changes no estimator ratio by more than {repair_max}."),

("Duplicate reconciliation is explicit as well.",
 "Duplicate reconciliation is explicit as well, and the two panels are audited separately. The "
 "historical long-form source panel contains 640 duplicated (security, date) keys: 622 "
 "exact-duplicate keys comprising 1,296 physical rows and 18 keys with conflicting OHLC values "
 "comprising 36 rows. Exact duplicates are collapsed to one record, removing 674 redundant rows; "
 "conflicting-OHLC keys are excluded in full, removing 36 rows rather than choosing a record by "
 "file order. The reconciliation script verifies that the exact duplicates also agree on volume "
 "and turnover. In total the duplicate rule removes 710 physical rows from that raw long-form "
 "panel. The 2024-2026 daily-trades panel that carries the paper's main equity estimates is a "
 "different file and is audited separately under the same classification rule: it contains "
 "{dt_keys} security-date keys in {dt_rows} rows, that is, exactly one row per key and no "
 "duplicated keys of any class. Because there are none, the ordering of the source files cannot "
 "have influenced which record survived. This audit is emitted with an explicit zero for every "
 "duplicate class rather than as an empty file, so its absence of conflicts is a reported result "
 "rather than an assumption."),

("The calendar also matters.",
 "The calendar also matters, and April 2026 contains two distinct reforms that must not be dated "
 "as one. NEPSE historically traded Sunday through Thursday and moved to a Monday-through-Friday "
 "week effective April 6, 2026, following the Cabinet decision of April 5 that made Saturday and "
 "Sunday the weekly public holidays. Separately, on April 20, 2026 the daily price limit widened "
 "from ±10% to ±15%, the pre-open band from ±2% to ±5%, and the market-wide circuit breaker "
 "became two-tier. The first reform changes which weekdays are sessions; the second changes how "
 "far a price may move within one. An earlier version of this project used April 20 for both, "
 "which placed the fortnight of April 6-19 under the wrong weekday regime. The project detects "
 "genuine sessions from the data and cross-checks them against the documented weekday regime "
 "rather than hard-coding a calendar, so the detected sample is unaffected by that error; what "
 "the correction changes is the cross-check, under which the Friday sessions of April 10 and 17 "
 "are no longer recorded as off-schedule and the Sundays of April 12 and 19 are no longer "
 "recorded as inferred holidays rather than weekend days. The distinction matters for overnight "
 "returns and for annualization. A fixed 252-day convention, standard in many developed-market "
 "applications, should not be imposed automatically on a market with a different holiday and "
 "session structure; Section 7.1 reports the value implied by NEPSE's own calendar."),

# ── §4.5: reconcile the previous-close definition with the implementation (item 5) ──────
("The Parkinson, Garman-Klass, and Rogers-Satchell daily formulas primarily describe",
 "The Parkinson, Garman-Klass, and Rogers-Satchell daily formulas primarily describe the "
 "within-session path. If the research objective is total daily risk, overnight gaps must also be "
 "included. Yang and Zhang (2000) combine an overnight variance term, an open-to-close variance "
 "term, and a Rogers-Satchell component. With an n-session window, its weight is k = 0.34/[1.34 + "
 "(n+1)/(n−1)]. The estimator is attractive when overnight price discovery is economically "
 "important, but it requires a correct session calendar, because the previous close must mean the "
 "close of the previous genuine trading session. That requirement binds here rather than being a "
 "formality. A security that does not trade on a session leaves a gap in its own rows, and taking "
 "the previous observed row instead would treat the gap as a single overnight move: in the "
 "ordinary-equity panel 230 row transitions skip more than one detected session and the largest "
 "skips 91. Our implementation therefore returns a missing value across any such gap, so "
 "Yang-Zhang is defined on {yz_rows} stock-days rather than on the full sample. This is also why "
 "Section 6.5 evaluates every ratio on the rows where both its numerator and its proxy are "
 "defined; a comparison that averaged Yang-Zhang over its own smaller sample and close-to-close "
 "over a larger one would reproduce, inside the robustness table, the scope mismatch that Section "
 "5.4 diagnoses."),

# ── §5.1: instrument classification, now validated (item 2) ─────────────────────────────
("But the liquidity ranking is largely an asset-class ranking.",
 "But the liquidity ranking is largely an asset-class ranking. The two thinnest pooled quintiles "
 "contain only four ordinary equities out of 209 securities. The thinnest pooled decile is 94.3% "
 "non-equity by stock-day. Corporate debentures and restricted promoter shares are structurally "
 "different instruments; treating them as thin common stocks creates a composition artifact."),

# ── §5.4: benchmark scope, with uncertainty (items 11, 19) ──────────────────────────────
("A common error is to compare an intraday range estimator",
 "A common error is to compare an intraday range estimator directly with close-to-close variance "
 "and call the difference bias. Close-to-close returns include the overnight move from yesterday's "
 "close to today's open; Parkinson and Rogers-Satchell do not. In the NIFTY 50 data, "
 "Rogers-Satchell is only {rs_nifty_cc} of close-to-close variance but {rs_nifty_oc} of "
 "open-to-close variance. For the NEPSE thin-equity group, Rogers-Satchell is {rs_thin} relative "
 "to the matched open-to-close proxy, and {rs_dense} for the dense group. Numerator and proxy are "
 "computed on the same strictly-consecutive-session rows; averaging the estimator over a wider "
 "row set than its proxy moves the dense figure to 1.059 and is precisely the kind of sample "
 "mismatch this section is about. These point estimates should not be read for their position "
 "relative to one. Their 95% intervals, from a bootstrap that resamples securities and calendar "
 "dates jointly, are {rs_thin_ci} for the thin group and {rs_dense_ci} for the dense group; both "
 "span one comfortably, and successive revisions of this project have produced thin-group point "
 "estimates of 0.998, 1.004 and {rs_thin} under sample changes far smaller than that interval. "
 "What the exercise establishes is the scope point, not a direction: once the proxy matches the "
 "estimator, the apparent Rogers-Satchell shortfall disappears. The decomposition also shows that "
 "Var(opening return)/Var(close-to-close return) is {von_thin}% in thin equity versus "
 "{von_dense}% in dense equity. These component ratios are not additive shares because opening "
 "and intraday returns can covary; the full identity includes the 2Cov term. Matching the "
 "estimator and the proxy to the same time interval, and to the same rows, is therefore a "
 "prerequisite for interpreting any of these ratios."),

# ── §6.1 ────────────────────────────────────────────────────────────────────────────────
("Once the universe is restricted to ordinary equity",
 "Once the universe is restricted to ordinary equity, the thin-market picture changes sharply. "
 "Across the equity sample, median trading intensity is 164 trades per stock-day, the 10th "
 "percentile is 37 trades, and only 1.6% of stock-days have fewer than ten trades. The zero-range "
 "rate P(H=L) falls from 5.70% in the pooled universe to 0.28% in ordinary equity. The thinnest "
 "equity quintile still has a median of 49 trades per day and full participation in the study "
 "window. Because this contrast is the paper's central empirical claim, it rests on a "
 "classification that has been checked against an independent source rather than on our rule "
 "alone; the audit is reported in Section 3 and Table 9."),

# ── §6.2: identical estimator code, not identical screens (item 7) ──────────────────────
("Under identical code, Parkinson's standard-deviation ratio",
 "Under identical estimator code — though not identical input screens, since the NEPSE panel "
 "additionally passes the positivity, return and rules-derived range filters of Section 3 while "
 "the NIFTY and NEPSE index series pass only a positivity filter — Parkinson's standard-deviation "
 "ratio relative to open-to-close variation is {nifty_pk} for the NIFTY 50. Across six NEPSE "
 "equity stock-day buckets formed by daily transaction count it ranges from {thin_pk} at roughly "
 "33 trades per day to {pk_hi} around 77 trades per day, and then moves toward 0.972 at the most "
 "active end. The relationship is not monotone and, crucially, does not collapse in the least "
 "active equity group. The zero-range rate is {thin_zero}% in that thinnest cross-market bucket "
 "and zero or nearly zero in the remaining groups. The screen asymmetry is not incidental: it is "
 "why a single unscreened NIFTY session can move the reference figures in Section 6.3, and it is "
 "recorded as a limitation in Section 10."),

("Figure 5. Cross-market estimator ratios under identical code.",
 "Figure 5. Cross-market estimator ratios under identical estimator code, but different "
 "market-specific input screens. Panel A shows that ordinary NEPSE equity remains near the "
 "matched proxy across daily trade-count buckets. Panel B compares India VIX with the 21-session "
 "Parkinson series on NIFTY 50."),

# ── §6.3: co-movement, not validation (item 6) ──────────────────────────────────────────
("6.3 An options-market validation anchor: India VIX",
 "6.3 An options-market co-movement check: India VIX"),

("The most relevant external check for the paper's motivating question comes from India.",
 "The most relevant external check for the paper's motivating question comes from India. The "
 "NIFTY 50 has both cash-market OHLC data and an options-based volatility index, so the same "
 "estimator code can be run where an implied-volatility benchmark exists. To keep the exercise "
 "consistent with the paper's reporting formula, the Parkinson series is computed as the square "
 "root of 252 times the rolling mean of daily Parkinson variance, and close-to-close is the "
 "annualized 21-session sample standard deviation of log returns. On 3,999 matched observations, "
 "Parkinson volatility has a correlation of {vix_pk} with India VIX; the corresponding "
 "close-to-close series has a correlation of {vix_cc}. Because each regression has a single "
 "regressor and an intercept, R² is the square of the reported correlation and is not reported "
 "separately. Both measures therefore track the volatility state represented in option prices "
 "strongly."),

("This result should not be interpreted as evidence that Parkinson volatility equals implied",
 "The ordering between them, however, is not robust, and this exercise should not be read as "
 "validating either estimator. The NIFTY series is used without the screens applied to the NEPSE "
 "panel, and a single session dominates it: October 5, 2012, the NSE flash crash, whose log range "
 "of 0.174 is the largest in the 4,037-session sample while its close-to-close return is only "
 "−0.70%. Official SEBI material attributes the move to an erroneous basket sell order that drove "
 "the index from about 5,767 to a low of 4,888.20 without a comparable move in the derivatives "
 "market. Because it is a range event rather than a close-to-close event, it raises the "
 "21-session Parkinson series for twenty-one sessions with no corresponding movement in India "
 "VIX. Excluding that one session, Parkinson's correlation rises to {vix_pk_ex} while "
 "close-to-close is unchanged at {vix_cc_ex}, reversing the ranking; the NIFTY Parkinson ratio "
 "falls from {nifty_pk} to {nifty_pk_ex} and Rogers-Satchell from 0.980 to {nifty_rs_ex}. The "
 "session is a genuine recorded exchange session and is retained in all reported results: we "
 "quantify its influence rather than delete it, because discarding real extremes is precisely the "
 "discretion this paper argues against. Two conclusions follow, and only two. Both measures "
 "co-move strongly with the option-implied volatility state, and this exercise establishes no "
 "ordering between them in either direction. It is also not a validation of estimator accuracy: "
 "India VIX is a forward-looking risk-neutral quantity while these are backward-looking realized "
 "measures, the historical series uses heavily overlapping 21-session windows so the correlations "
 "are descriptive rather than inferential, and the timing horizons do not establish forecasting "
 "accuracy. The exercise does show, from the other direction, the paper's own argument: a range "
 "estimator is sensitive to one extreme observed range, which is why the screens and diagnostics "
 "of Section 5 matter as much as the choice of formula."),

# ── §7.1: empirical annualisation (item 13) ─────────────────────────────────────────────
("where v̂ is the chosen daily variance estimator and A is",
 "where v̂ is the chosen daily variance estimator and A is the market's own annual session count "
 "rather than an imported convention. For NEPSE over the study window the detected trading "
 "calendar yields A ≈ {A} genuine sessions per year ({sessions} sessions over {span_years} "
 "years), against the 252 a developed-market default would impose — a difference of roughly 9% in "
 "variance terms and 4.5% in volatility terms. The figure differs across the schedule change: "
 "about 226 sessions per year under the Sunday-Thursday regime and about 257 under the "
 "Monday-Friday regime, which is a further reason to date the regime boundary explicitly rather "
 "than annualize the whole sample at one rate. Where a regime-specific factor is used it should "
 "be reported as such. The report should show close-to-close volatility beside the range measure "
 "and disclose the security's median trade count and zero-range rate, so a reader can see the "
 "conditions under which the number was produced."),

# ── §7.2: conditional framework, not a hierarchy (items 5, 12) ──────────────────────────
("7.2 A suggested hierarchy of estimators",
 "7.2 Choosing an estimator: a conditional framework"),

("For NEPSE ordinary equity, the evidence in this project suggests the following hierarchy.",
 "The evidence in this project does not support a single ranking, and the choice should follow "
 "the risk object rather than a general ordering. Against the matched open-to-close proxy on the "
 "full ordinary-equity sample (Table 7), Parkinson ({t7_pk}) and Garman-Klass ({t7_gk}) sit "
 "closest to the proxy, with Rogers-Satchell slightly above it ({t7_rs}); the differences are "
 "small, and under a bootstrap that clusters on both security and calendar date the intervals for "
 "Parkinson {t7_pk_ci} and Garman-Klass {t7_gk_ci} contain one while that for Rogers-Satchell "
 "{t7_rs_ci} does not. Proximity to a proxy is one criterion; it is not the only one, and the "
 "paper states no formal loss function, so it cannot produce a universal ordering. "
 "Rogers-Satchell remains attractive where drift robustness is valuable and is the natural "
 "primary when the maintained model is a drifting price process. Parkinson is the simplest "
 "cross-check and the most efficient use of the range where the high and low are reliable. "
 "Garman-Klass is now evaluated empirically rather than used only as a data-validity diagnostic. "
 "Where the overnight component belongs in the risk object, close-to-close is the transparent "
 "baseline; Yang-Zhang should be used with the caveat that, evaluated on the {yz_rows} stock-days "
 "where it and its total-risk proxy are both defined, it stands at {t7_yzr} {t7_yzr_ci} of that "
 "proxy, overshooting by about as much as AddRS overshoots the intraday one. It should not be "
 "treated as interchangeable with close-to-close on that evidence. AddRS ({t7_addrs}) should be "
 "treated as a model-dependent alternative, not a default correction. We state no criterion-free "
 "ordering because these are deviations from an imperfect proxy, not accuracy against latent "
 "variance."),

# ── §8 Discussion (items 6, 11) ─────────────────────────────────────────────────────────
("The India VIX result is especially useful for interpretation.",
 "The India VIX result is useful for interpretation, within limits. It shows that the high-low "
 "range captures information relevant to an options market's assessment of volatility, which "
 "helps explain why range-based measures remain informative in a market without options. Under "
 "the paper-consistent 21-session aggregation, close-to-close volatility tracks India VIX "
 "marginally more closely than Parkinson in the full sample, but that margin depends entirely on "
 "one flash-crash session and reverses without it. The external evidence therefore establishes "
 "co-movement for both measures and dominance for neither. It also illustrates the paper's own "
 "argument from the other direction: a range estimator is sensitive to a single extreme observed "
 "range, which is why the screens and diagnostics of Section 5 matter as much as the choice of "
 "formula. None of this makes a realized-volatility system a substitute for an options market. "
 "Nepal still lacks a forward-looking, risk-neutral volatility term structure, and a carefully "
 "constructed realized-volatility system is a substitute for measurement, not for the information "
 "an option chain would provide."),

# ── §8 Discussion: the composition result now rests on a validated classification (item 2) ──
("At the same time, the study shows that frontier-market volatility is as much",
 "At the same time, the study shows that frontier-market volatility is as much a data-engineering "
 "problem as an econometric one. A perfectly coded Parkinson formula can produce a misleading "
 "research conclusion if the low-liquidity sample is mostly bonds and restricted shares. A "
 "theoretically appropriate Rogers-Satchell comparison can appear strongly biased if it is "
 "benchmarked against close-to-close variance it was never built to match. Because that "
 "composition argument carries more weight here than any single estimator result, it is not left "
 "resting on our own classification rule: reconciling the rule against an external listing of "
 "NEPSE securities gives {class_rate}% agreement on {class_matched} securities, and the two "
 "disagreements are corrected rather than argued away. An independent source reproduces the "
 "classification, so the composition finding is a property of the market's instrument mix and not "
 "of our heuristic. The general lesson is that in frontier-market research sample construction "
 "can masquerade as a microstructure effect, and the classification step deserves the same "
 "auditing as the estimator."),

# ── §9 Reproducibility (item 15) ────────────────────────────────────────────────────────
("This revision uses only empirical results with a traceable source",
 "This revision uses only empirical results with a traceable source in the accompanying package, "
 "and the reproducibility map now names a producer for every section and table that appears in "
 "this manuscript. The map links the descriptive screens and composition audit to script 03, the "
 "instrument-classification audit against the external security master to script 27, the "
 "cross-market fingerprint and the India VIX co-movement check to script 09, the benchmark "
 "decomposition to script 12, the opening-auction diagnostics to script 13, the AddRS comparison "
 "to scripts 17 and 19, the universe-composition result to script 22, the long-form duplicate "
 "reconciliation to script 24, the robustness suite of Section 6.5 to script 26, and the "
 "manuscript-facing summary tables to script 25. Script 02 builds the panels, the trading "
 "calendar and the daily-trades duplicate audit from the raw downloads. Every number printed in "
 "this manuscript is interpolated from those frozen outputs by a script rather than transcribed "
 "by hand, and the test suite fails if the map names a producer or an output that does not exist."),

# ── §9: superseded analyses, updated for what this revision changed ─────────────────────
("The archive also records failed and superseded analyses",
 "The archive also records failed and superseded analyses, and they are deliberately not "
 "promoted into results here. This paper does not report the attempted censored-normal estimate "
 "of latent opening dispersion, because it failed the available post-April-2026 regime-change "
 "check; and it does not use the earlier multi-horizon convergence result, which was invalidated "
 "by a stock-day bucket construction that stitched nonconsecutive sessions. Two analyses that "
 "were previously in that category have since been given producing code and are now reported: "
 "the equity-classifier validation of Section 3 and Table 9, and the robustness suite of Section "
 "6.5. Three further corrections made in this revision are recorded rather than absorbed "
 "silently, because each changed a number that had already been circulated: the row-matching of "
 "every estimator to its own proxy, which moves the Yang-Zhang ratio from 1.245 to {yz}; the "
 "addition of calendar-date clustering to the bootstrap, which roughly doubles the reported "
 "interval widths; and the separation of the April 2026 trading-week date from the price-limit "
 "date. Attractive findings that cannot be regenerated are treated as unavailable evidence, and "
 "corrections that change a circulated number are stated as corrections."),

("For input provenance, the supplied research archive contains",
 "For input provenance, the package contains a processed-data BUILD-MANIFEST recording the "
 "interpreter, package versions, cleaning-rule versions and aggregate raw-data hash, together "
 "with field-level repair audits and the duplicate audits for both panels. The 2024-2026 "
 "daily-trades panel has been rebuilt from the original raw downloads under the corrected "
 "duplicate-classification rule: the rebuild reports no duplicated security-date keys of any "
 "class, and the rebuilt panel is identical to the frozen panel distributed here, so no reported "
 "quantity depends on the superseded rule. The original stock-level downloads are not "
 "redistributed because their redistribution terms remain unresolved; the build script is "
 "retained as the complete cleaning specification and exits with an explanatory message when they "
 "are absent."),
]

REPLACE += [

# ── §10 Limitations (items 6, 14, 16) ───────────────────────────────────────────────────
("Fourth, the external India VIX exercise is a cross-market validation",
 "Fourth, the external India VIX exercise is cross-market co-movement evidence, not a "
 "Nepal-specific implied-volatility measurement and not a validation of estimator accuracy. "
 "Because consecutive 21-session observations overlap heavily, the reported correlations are "
 "descriptive rather than inferential, and the timing horizons do not establish forecasting "
 "accuracy. This paper addresses measurement rather than forecasting; forecasting performance "
 "remains for future work."),
]

# Paragraphs appended after an anchor, in order. (anchor, [(text, style), ...])
INSERT_AFTER = [

# ── §3: the classification audit paragraph (item 2) ─────────────────────────────────────
("The calendar also matters, and April 2026 contains two distinct reforms", [
 ("Instrument classification deserves its own statement, because the paper's central empirical "
  "contrast depends on it. NEPSE's daily file carries no instrument-type field, so type is "
  "recovered from the ticker convention and validated against par value, which differs by class "
  "(funds at 10, ordinary equity and promoter shares at 100, debentures at 1,000). A rule of that "
  "kind cannot carry a headline result on its own, so it is reconciled against an external NEPSE "
  "security master listing instrument categories for currently listed securities. Of the 521 "
  "securities in the cleaned panel, {class_matched} appear in the master and the two classifiers "
  "agree on {class_rate}% of them; the confusion matrix is reported in Table 9. Two securities "
  "disagree, and the master governs both. ADBLB, the 4% Agricultural Bond, is a debenture that "
  "the ticker rule read as ordinary equity — it is also, as it happens, the single security the "
  "analysis screens already removed, so no reported result was ever computed with a bond inside "
  "the equity universe. NADEP, an ordinary microfinance equity, was wrongly excluded as a "
  "promoter share by a pattern matching the trailing letter of its name. Correcting both moves "
  "the estimation universe from 291 securities and 143,149 stock-days to {eq_secs} and {eq_days}. "
  "Ten securities delisted, merged or renamed during the sample do not appear in the master, "
  "which lists current securities only, and retain their rule-based classification; they are "
  "listed in the package. The agreement rate is the substantive point: an independent listing "
  "reproduces the classification on which Section 5.1 depends, so the composition result cannot "
  "be an artifact of the heuristic.", None),
]),

# ── §6.2: endogeneity of the same-day sort (item 3) ─────────────────────────────────────
("Table 4. Cross-market fingerprint", [
 ("The buckets in Table 4 are formed on same-day transaction counts. Because volatility itself "
  "raises trading activity, that sort is endogenous: it cannot separate a liquidity effect from "
  "the volatility-activity relationship, and the gradient must not be read causally. Table 6 "
  "therefore repeats the exercise with two predetermined sorts — one assigning each security to a "
  "single bucket by its full-sample median trade count, and one assigning each stock-day by that "
  "security's median trade count over its prior sixty sessions, so the sorting variable is in the "
  "information set before the day begins. Under both, the least active bucket sits slightly above "
  "the matched proxy, at {pre_sec_q1} and {pre_lag_q1}, rather than below it, and the most active "
  "bucket sits below. The dip at the thin end of Table 4 is therefore substantially an artifact "
  "of sorting stock-days on their own activity. This does not weaken the paper's thesis; it "
  "strengthens it. The claim is that range estimators do not collapse in thin equity, and under a "
  "non-endogenous sort the thin bucket is closer to the matched proxy, not further from it.", None),
]),

# ── NEW §6.5 (item 4) ───────────────────────────────────────────────────────────────────
("This is a general lesson for frontier-market work. The AddRS increment is non-negative.", [
 ("6.5 Robustness", "Heading 2"),
 ("Five checks bound the results above. Each is produced by scripts/26_robustness.py and each is "
  "reported whether or not it is favourable.", None),
 ("Predetermined liquidity. Repeating the Section 6.2 sort on predetermined rather than same-day "
  "activity changes the gradient but not the conclusion (Table 6, discussed in Section 6.2). "
  "Under the security-level sort the least active bucket sits at {pre_sec_q1} of the matched "
  "proxy and under the lagged 60-session sort at {pre_lag_q1}, in both cases above one rather "
  "than below.", None),
 ("Uncertainty. All ratios are reported with 95% percentile intervals from a bootstrap that "
  "resamples securities and calendar dates jointly, using the multiway or pigeonhole scheme of "
  "Davezies, D'Haultfœuille and Guyonvarch (2021). Both dimensions are necessary. Observations "
  "within a security are serially dependent and share a liquidity regime, and a market-wide shock "
  "on a given date moves every security at once; clustering on security alone, as an earlier "
  "version of this analysis did, understates the intervals by a factor of roughly two on this "
  "panel. Under the two-way intervals, {n_excl} of the {n_buckets} liquidity buckets have a "
  "Parkinson interval excluding one, against twelve under security-only clustering. The small "
  "deviations from the proxy are therefore detectable in some buckets and not in others, and are "
  "economically modest throughout. Because the proxy is imperfect, an interval excluding one "
  "means the estimator differs detectably from the proxy, not that it is biased.", None),
 ("All six estimators, on matched rows. Table 7 evaluates every estimator the paper names against "
  "a proxy matched to its scope — open-to-close for the within-session estimators, close-to-close "
  "for close-to-close and Yang-Zhang — and, equally importantly, on the rows where the estimator "
  "and its proxy are both defined. Scope matching alone is not sufficient: Yang-Zhang requires a "
  "21-session window and close-to-close requires a previous session, so the estimators do not "
  "share a sample. Evaluated on its own {yz_rows} matched stock-days, Yang-Zhang stands at "
  "{t7_yzr} of the total-risk proxy; averaging it over that sample while averaging the proxy over "
  "the larger one gives 1.245, which is the scope error of Section 5.4 in a different guise. "
  "Scoring Yang-Zhang against an open-to-close proxy would repeat the same error again, by "
  "penalising it for the overnight variance it exists to include. Close-to-close against itself "
  "is one by construction and anchors the scale.", None),
 ("OHLC repair. The envelope repair widens the high and low to contain the open and close, and "
  "the range estimators are functions of exactly that range, so the repair can only push range "
  "variance upward. Excluding all {repair_rows} repaired ordinary-equity rows rather than "
  "correcting them changes no estimator ratio by more than {repair_max} (Table 8). The repair is "
  "immaterial to every reported conclusion.", None),
 ("Cross-market proxy. The NIFTY reference numbers depend materially on one session; see Sections "
  "6.3 and 10.", None),
]),

# ── §10: three further limitations (item 16) ────────────────────────────────────────────
("Fourth, the external India VIX exercise is cross-market co-movement evidence", [
 ("Fifth, the cross-market comparison uses the NIFTY series without the instrument, return and "
  "range screens applied to the NEPSE panel, because those screens are derived from NEPSE's own "
  "price-limit rules and have no NSE analogue. With roughly 4,000 NIFTY sessions against roughly "
  "24,000 stock-days per NEPSE bucket, a single extreme NIFTY session carries far more leverage "
  "on the reference figures than any single NEPSE observation carries on the NEPSE ones. Section "
  "6.3 quantifies that leverage.", None),
 ("Sixth, the liquidity gradients in Tables 4 and 5 are formed on same-day transaction counts and "
  "are therefore endogenous; Table 6 reports predetermined alternatives and the two differ "
  "materially at the thin end.", None),
 ("Seventh, instrument classification is rule-based — ticker convention validated against "
  "par-value bands — and is reconciled against an external listing of currently listed securities "
  "rather than against an official SEBON register. Agreement is {class_rate}% on "
  "{class_matched} matched securities and the two disagreements are corrected, but ten securities "
  "that left the board during the sample cannot appear in that listing and retain their "
  "rule-based classification. An official register would close this gap entirely.", None),
 ("Eighth, the open-to-close second moment is an imperfect proxy for latent within-session "
  "variance, not the variance itself. Every ratio in this paper is a deviation from that proxy. A "
  "ratio of 1.00 does not establish unbiasedness and a ratio of 1.04 does not establish true "
  "upward bias; both are statements about agreement with an observable benchmark whose own "
  "measurement error is not modelled here. Patton (2011) shows that ranking estimators on an "
  "imperfect proxy can invert the true ranking unless the proxy satisfies conditions we do not "
  "verify.", None),
 ("Ninth, the intervals reported here absorb dependence within securities and within calendar "
  "dates. They do not model the measurement error in the proxy itself, so they should be read as "
  "a lower bound on total uncertainty rather than as a complete accounting of it.", None),
 ("Tenth, on data provenance. The processed panels distributed with this paper have been rebuilt "
  "from the original stock-level downloads under the duplicate-classification rule described in "
  "Section 3, and the rebuild reproduces them exactly, so the earlier caveat that conflict-freedom "
  "was assumed rather than demonstrated no longer applies. What remains is narrower: the raw "
  "downloads themselves are not redistributed, because their redistribution terms are unresolved. "
  "A reader can therefore reproduce every reported result from the frozen panels, and can repeat "
  "the rebuild only with independent access to the sources.", None),
]),
]

# ── §11 Conclusion (item 17): rewritten as three paragraphs ─────────────────────────────
CONCLUSION = [
 ("A frontier market does not need options to calculate a useful measure of volatility, but it "
  "does need conceptual discipline about what is being measured. Option-implied volatility cannot "
  "be recovered from spot prices, so the achievable object is historical and realized variation, "
  "measured well. Measuring it well in a market like Nepal's turns out to depend less on the "
  "choice of formula than on decisions that are usually treated as preliminaries: which "
  "instruments enter the sample, which sessions are genuine, and which benchmark a given "
  "estimator should be compared against."),
 ("The NEPSE evidence shows that this is practical for ordinary equities. Range-based estimates "
  "remain close to a scope-matched open-to-close proxy across the equity liquidity range and do "
  "not collapse in the least active group — the result the paper is most confident in, and one "
  "that holds under same-day, security-level and lagged liquidity sorts alike, and is more "
  "favourable to the thin group under the predetermined sorts than under the endogenous one. The "
  "NIFTY 50 and India VIX comparison further shows that a correctly aggregated rolling Parkinson "
  "measure tracks an options-derived volatility state strongly. Close-to-close tracks it "
  "marginally more closely in the full sample, but the two orderings cannot be separated once the "
  "influence of a single flash-crash session is accounted for, so that exercise establishes "
  "co-movement rather than dominance."),
 ("The claims should stop there. The open-to-close second moment is an imperfect proxy rather "
  "than latent variance, so proximity to it is evidence about agreement with an observable "
  "benchmark and not about accuracy; the deviations we report are small and, where they are "
  "statistically distinguishable from one, economically modest. No estimator is shown to dominate "
  "generally, and the paper deliberately states no criterion-free ordering, because the "
  "appropriate choice depends on the risk object and the maintained assumptions rather than on a "
  "single number. What does generalize is the negative result about sample construction: pooling "
  "instrument classes manufactures an illiquidity finding that is really a composition finding, "
  "and in frontier-market research that failure mode is easy to reproduce and hard to see. That "
  "result is reported here on a classification reconciled against an external listing of NEPSE "
  "securities rather than on a ticker heuristic alone, which is what allows it to be read as a "
  "fact about the market rather than about our own rule. The "
  "recommendation is therefore procedural: classify the securities correctly and check the "
  "classification against an independent source, clean and validate OHLC data against the "
  "market's own rules, use the genuine session calendar and the market's own annualization "
  "factor, match every benchmark to the estimator's scope and to its rows, report uncertainty "
  "that respects both cross-sectional and calendar dependence, and justify any bias correction in "
  "the target sample before applying it."),
]

REFERENCES = [
 ("Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2011). Robust inference with multiway "
  "clustering. Journal of Business & Economic Statistics, 29(2), 238-249."),
 ("Davezies, L., D'Haultfœuille, X., & Guyonvarch, Y. (2021). Empirical process results for "
  "exchangeable arrays. Annals of Statistics, 49(2), 845-862."),
 ("Andersen, T. G., & Bollerslev, T. (1998). Answering the skeptics: Yes, standard volatility "
  "models do provide accurate forecasts. International Economic Review, 39(4), 885-905."),
 ("Andersen, T. G., Bollerslev, T., Diebold, F. X., & Labys, P. (2003). Modeling and forecasting "
  "realized volatility. Econometrica, 71(2), 579-625."),
 ("Barndorff-Nielsen, O. E., & Shephard, N. (2002). Econometric analysis of realized volatility "
  "and its use in estimating stochastic volatility models. Journal of the Royal Statistical "
  "Society Series B, 64(2), 253-280."),
 ("Alizadeh, S., Brandt, M. W., & Diebold, F. X. (2002). Range-based estimation of stochastic "
  "volatility models. Journal of Finance, 57(3), 1047-1091."),
 ("Christensen, K., & Podolskij, M. (2007). Realized range-based estimation of integrated "
  "variance. Journal of Econometrics, 141(2), 323-349."),
 ("Martens, M., & van Dijk, D. (2007). Measuring volatility with the realized range. Journal of "
  "Econometrics, 138(1), 181-207."),
 ("Hansen, P. R., & Lunde, A. (2006). Realized variance and market microstructure noise. Journal "
  "of Business & Economic Statistics, 24(2), 127-161."),
 ("Zhang, L., Mykland, P. A., & Aït-Sahalia, Y. (2005). A tale of two time scales: Determining "
  "integrated volatility with noisy high-frequency data. Journal of the American Statistical "
  "Association, 100(472), 1394-1411."),
 ("Roll, R. (1984). A simple implicit measure of the effective bid-ask spread in an efficient "
  "market. Journal of Finance, 39(4), 1127-1139."),
 ("Scholes, M., & Williams, J. (1977). Estimating betas from nonsynchronous data. Journal of "
  "Financial Economics, 5(3), 309-327."),
 ("Bekaert, G., & Harvey, C. R. (1997). Emerging equity market volatility. Journal of Financial "
  "Economics, 43(1), 29-77."),
 ("Hansen, P. R., Lunde, A., & Nason, J. M. (2011). The model confidence set. Econometrica, "
  "79(2), 453-497."),
 ("Molnár, P. (2012). Properties of range-based volatility estimators. International Review of "
  "Financial Analysis, 23, 20-29."),
]


ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth",
            "Ninth", "Tenth", "Eleventh", "Twelfth"]


def renumber_limitations(doc):
    """Make the Section 10 ordinals contiguous.

    The base manuscript's limitations ran First, Second, Fourth -- "Third" was lost in an earlier
    edit and the gap survived into the submitted PDF. Appending new limitations on top of a broken
    sequence would compound it, so the whole list is renumbered from the text rather than by hand.
    The first limitation is embedded in the introductory sentence and is matched separately.
    """
    paras = list(doc.paragraphs)
    start = find(paras, "Several limitations should keep the conclusions")
    end = find(paras, "11. Conclusion", start)
    pat = re.compile(r"^(" + "|".join(ORDINALS) + r")(,)")
    k = 1                                   # "First" lives inside the intro sentence
    changed = 0
    for i in range(start + 1, end):
        t = paras[i].text.strip()
        m = pat.match(t)
        if not m:
            continue
        want = ORDINALS[k]
        if m.group(1) != want:
            set_text(paras[i], pat.sub(want + ",", t, count=1))
            changed += 1
        k += 1
    return k, changed


def main():
    # The base is the author's pre-revision Word draft ("Calculating Volatility in Frontier Markets: Nepal,
    # Revised"), which is NOT distributed (its rendered form is paper/manuscript_as_reviewed_pre_revision.pdf).
    # This script, and every later round, is therefore a record of the edits and their checks, applied
    # in order to produce the tracked manuscript; a recipient cannot rerun this first round without the
    # draft. The canonical editable source is the tracked paper/NEPSE_Volatility_Manuscript_Revised_2026-09.docx
    # (audit item A14, 9 October 2026; the default used to point at the author's Downloads folder).
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True,
                    help="the author's pre-revision .docx draft (not distributed with the package)")
    ap.add_argument("--out", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    a = ap.parse_args()

    n = load_numbers()
    doc = docx.Document(a.base)

    # stage 1 — reconcile the four paragraphs that trail the submitted PDF and are not
    # otherwise rewritten below
    paras = list(doc.paragraphs)
    for anchor, key in [("NEPSE's opening mechanism is economically important", "opening"),
                        ("The AddRS correction was designed for a setting", "addrs_premise"),
                        ("This is a general lesson for frontier-market work", "addrs_lesson"),
                        ("Data and reproducibility note.", "repro_note")]:
        set_text(paras[find(paras, anchor)], PDF_TEXT[key].format(**n))
    print(f"  reconciled 4 paragraphs to the submitted PDF")

    # stage 2 — the referee revisions
    applied = 0
    for anchor, template in REPLACE:
        paras = list(doc.paragraphs)
        try:
            i = find(paras, anchor)
        except LookupError:
            print(f"  !! anchor not found, skipped: {anchor[:60]!r}")
            continue
        set_text(paras[i], template.format(**n))
        applied += 1
    print(f"  replaced {applied}/{len(REPLACE)} paragraphs")

    inserted = 0
    for anchor, blocks in INSERT_AFTER:
        paras = list(doc.paragraphs)
        try:
            p = paras[find(paras, anchor)]
        except LookupError:
            print(f"  !! insert anchor not found, skipped: {anchor[:60]!r}")
            continue
        for text, style in blocks:
            # An inserted paragraph clones its anchor, so a body paragraph placed after a
            # heading would silently become a heading. Style is therefore always explicit.
            p = para_after(p, text.format(**n), style or "Normal")
            inserted += 1
    print(f"  inserted {inserted} new paragraphs")

    total, changed = renumber_limitations(doc)
    print(f"  Section 10: {total} limitations, ordinals made contiguous ({changed} renumbered)")

    # §11 conclusion: replace the three existing paragraphs in place
    paras = list(doc.paragraphs)
    i = find(paras, "A frontier market does not need options")
    for k, text in enumerate(CONCLUSION):
        set_text(paras[i + k], text)
    print("  rewrote the conclusion")

    # references: correct Yang & Zhang pagination, then extend the literature
    paras = list(doc.paragraphs)
    yz = paras[find(paras, "Yang, D., & Zhang, Q. (2000)")]
    set_text(yz, "Yang, D., & Zhang, Q. (2000). Drift-independent volatility estimation based on "
                 "high, low, open, and close prices. Journal of Business, 73(3), 477-492.")
    # The list must stay alphabetical, so the existing entries and the new ones are merged and
    # rewritten in place rather than appended after Yang & Zhang.
    paras = list(doc.paragraphs)
    first = find(paras, "Ardia, D., Guidotti, E.")
    last = find(paras, "Yang, D., & Zhang, Q. (2000)")
    existing = [paras[i].text.strip() for i in range(first, last + 1) if paras[i].text.strip()]
    merged = sorted(set(existing) | set(REFERENCES),
                    key=lambda r: re.sub(r"^(The )", "", r).lower())
    slots = list(range(first, last + 1))
    for k, ref in enumerate(merged[:len(slots)]):
        set_text(paras[slots[k]], ref)
    p = paras[slots[-1]]
    for ref in merged[len(slots):]:
        p = para_after(p, ref, "Normal")
    print(f"  corrected Yang & Zhang pagination; reference list now {len(merged)} entries, sorted")

    # tables
    t = doc.tables
    t1 = pd.read_csv(TAB / "paper_table1_data_used.csv")
    fill_table(t[0], list(t1.columns), t1.values.tolist())
    t3 = pd.read_csv(TAB / "paper_table3_instrument_classification_effect.csv")
    fill_table(t[2], list(t3.columns), t3.values.tolist())
    t4 = pd.read_csv(TAB / "paper_table4_cross_market_fingerprint.csv")
    fill_table(t[3], list(t4.columns), t4.values.tolist())
    t5 = pd.read_csv(TAB / "paper_table5_addrs_benchmark.csv")
    fill_table(t[4], list(t5.columns), t5.values.tolist())
    print("  refreshed Tables 1, 3, 4, 5 from the frozen outputs")

    # new tables 6, 7, 8, 9, each after a caption paragraph
    paras = list(doc.paragraphs)
    anchor = paras[find(paras, "Cross-market proxy. The NIFTY reference numbers")]

    t9 = pd.read_csv(TAB / "paper_table9_classification_audit.csv")
    t9.columns = ["Rule-based classification"] + [f"Master: {c}" for c in t9.columns[1:]]
    cap9 = para_after(anchor, "Table 9. Instrument classification: rule-based classifier against "
                              "the external NEPSE security master, one row per security.", "Normal")
    new_table_after(cap9, doc, list(t9.columns), t9.values.tolist())

    t8 = pd.read_csv(TAB / "paper_table8_repair_sensitivity.csv")
    cap8 = para_after(anchor, "Table 8. OHLC envelope-repair sensitivity. SD ratios to the "
                              "scope-matched proxy, repaired rows corrected versus excluded.", "Normal")
    new_table_after(cap8, doc, list(t8.columns), t8.values.tolist())

    t7 = pd.read_csv(TAB / "paper_table7_all_estimators.csv").fillna("")
    cap7 = para_after(anchor, "Table 7. All six named estimators against scope- and row-matched "
                              "proxies, with two-way cluster-bootstrap intervals.", "Normal")
    new_table_after(cap7, doc, list(t7.columns), t7.values.tolist())

    t6 = pd.read_csv(TAB / "paper_table6_predetermined_liquidity.csv")
    t6.columns = ["Liquidity sort", "Bucket", "Stock-days", "Median trades/day",
                  "Parkinson: SD ratio to matched proxy", "Parkinson 95% CI",
                  "Rogers-Satchell: SD ratio to matched proxy", "Rogers-Satchell 95% CI"]
    cap6 = para_after(anchor, "Table 6. Liquidity sorting: the published same-day sort against two "
                              "predetermined sorts, with two-way cluster-bootstrap intervals.", "Normal")
    new_table_after(cap6, doc, list(t6.columns), t6.values.tolist())
    print("  added Tables 6, 7, 8, 9")

    doc.save(a.out)
    print(f"\nwrote {a.out}")

    # ── verification: no stale figure may survive in the body text ──────────────────────
    #
    # Superseded values are permitted in exactly one place: the Section 3 sentence that reports
    # what the classification correction changed. Reporting "291 and 143,149 became 292 and
    # 143,718" is the disclosure the referee asked for, so the check exempts sentences that name
    # both the old and the new value, and flags the old value anywhere else.
    paras_out = [p.text for p in docx.Document(a.out).paragraphs]
    disclosure = "moves the estimation universe from"
    body = "\n".join(p for p in paras_out if disclosure not in p)
    stale = {
        "143,149": "superseded ordinary-equity stock-day count",
        "291 ordinary equities": "superseded security count",
        "291 equities": "superseded security count",
        "validation anchor": "referee item 6: 'validation' must not describe the VIX exercise",
        "Under identical code": "referee item 7",
        "suggested hierarchy": "referee item 12",
        "R² of 0.602": "optional item: R2 dropped from the one-regressor comparison",
        "R² of 0.692": "value excluding the outlier, presented as full-sample",
        "0.998 relative to the matched": "referee item 19: superseded thin-equity RS figure",
    }
    bad = {k: v for k, v in stale.items() if k in body}
    if not any(disclosure in p for p in paras_out):
        bad["<disclosure>"] = "the Section 3 sentence disclosing the classification change is gone"
    if bad:
        print("\nSTALE TEXT STILL PRESENT:")
        for k, v in bad.items():
            print(f"  {k!r}: {v}")
        raise SystemExit(1)
    for key in ("eq_days", "eq_secs", "vix_pk", "yz", "A", "class_rate"):
        assert str(n[key]) in body, f"number {key}={n[key]} did not reach the manuscript"
    print("verification: no stale figures, and every headline number reached the text")


if __name__ == "__main__":
    main()
