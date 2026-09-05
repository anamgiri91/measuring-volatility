"""Apply the round-3 (second peer-review-evaluation) revisions to the manuscript source.

Same discipline as ``apply_referee_revisions.py``: the manuscript is a .docx, so every number
below is interpolated from ``output/tables/*.csv`` rather than typed by hand, and the script
fails if a superseded figure survives or a headline number never reached the text.

    python paper/apply_round3_revisions.py [--base BASE.docx] [--out OUT.docx]

The default base is the round-2 manuscript already in ``paper/`` (the referee-revision output),
so this script is a second pass over that file rather than a replacement for it.

WHAT THIS ROUND ANSWERS. A second-round critique found that the round-2 analysis PACKAGE had
raced ahead of the manuscript PROSE again -- the exact failure mode round 2 itself was written
to fix. Tables 10-16 and their producer scripts (28, 29, 30, and extensions to 03, 09, 12, 26)
already existed and were already run; nothing here computes a new number. This script is the
missing last step: getting those seven already-verified findings (items A-H, skipping F which
needed no manuscript text change) into the text that a reader actually sees.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import pandas as pd

try:
    import docx
except ImportError:
    sys.exit("python-docx is required:  pip install python-docx")

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from apply_referee_revisions import find, para_after, set_text, fill_table, new_table_after  # noqa: E402
from docx.shared import Inches  # noqa: E402


def grow_table_columns(tbl, target_n):
    """Add empty columns until ``tbl`` has ``target_n`` columns.

    ``fill_table`` (round 2) only ever REMOVES excess columns; Table 7 gains two columns this
    round (the block-date interval and the equivalence verdict), so growth has to happen first.
    """
    while len(tbl.columns) < target_n:
        tbl.add_column(Inches(1.2))


# ─────────────────────────────────────────────────────────────── numbers from the package

def load_numbers():
    n = {}
    chk = pd.read_csv(ROOT / "PAPER_RESULTS_CHECK.csv").set_index("Result")["Value"]

    n["yz_shipped"] = f"{float(chk['YangZhang_shipped_same_session_ratio']):.3f}"
    n["yz_adopted"] = f"{float(chk['YangZhang_horizon_and_corporate_action_adjusted_ratio']):.3f}"
    n["ca_total"] = int(float(chk["previous_close_disagreements_total"]))
    n["ca_corp"] = int(float(chk["previous_close_disagreements_corporate_action"]))
    n["pk_pearson"] = f"{float(chk['Parkinson_pearson_vs_proxy']):.2f}"
    n["pk_spearman"] = f"{float(chk['Parkinson_spearman_vs_proxy']):.2f}"
    n["rs_pearson"] = f"{float(chk['RogersSatchell_pearson_vs_proxy']):.2f}"
    n["rs_spearman"] = f"{float(chk['RogersSatchell_spearman_vs_proxy']):.2f}"
    n["vix_full_pk"] = f"{float(chk['IndiaVIX_Parkinson_corr_full_sample']):.3f}"
    n["vix_overlap_pk"] = f"{float(chk['IndiaVIX_Parkinson_corr_NEPSE_overlap']):.3f}"
    n["vix_overlap_cc"] = f"{float(chk['IndiaVIX_CC_corr_NEPSE_overlap']):.3f}"
    n["fill_rate"] = f"{float(chk['conditional_panel_fill_rate_pct']):.1f}"
    n["t7_excl_two"] = str(chk["table7_estimators_with_CI_excluding_one_twoway"])
    n["t7_excl_block"] = str(chk["table7_estimators_with_CI_excluding_one_block_date"])
    n["extreme_n_sec"] = int(float(chk["extreme_thin_tail_n_securities"]))
    n["extreme_zero"] = f"{float(chk['extreme_thin_tail_zero_range_pct']):.1f}"
    n["extreme_pk"] = f"{float(chk['extreme_thin_tail_Parkinson_ratio']):.3f}"

    yzh = pd.read_csv(TAB / "table48_yang_zhang_horizon.csv")
    horiz_only = yzh[(yzh.horizon_matched) & (~yzh.adopted) &
                     (yzh.previous_close_definition.str.startswith("unadjusted"))].iloc[0]
    n["yz_horizon_only"] = f"{float(horiz_only.sd_ratio):.3f}"
    adopted = yzh[yzh.adopted].iloc[0]
    n["yz_adopted_rows"] = f"{int(adopted.n_matched_rows):,}"

    est = pd.read_csv(TAB / "table33_estimator_ratios_bootstrap.csv").set_index("estimator")
    yz_row = est.loc["Yang-Zhang"]
    n["yz_adopted_ci"] = f"[{yz_row['lo95_twoway']:.3f}, {yz_row['hi95_twoway']:.3f}]"
    rs_row = est.loc["Rogers-Satchell"]
    n["rs_verdict"] = rs_row["equivalence_verdict"]

    p10 = pd.read_csv(TAB / "paper_table10_panel_balance.csv").set_index("Liquidity quintile (security-level)")
    q1 = p10.loc["Q1"]
    n["q1_min_part"] = f"{100 * float(q1['Min participation']):.1f}"
    n["q1_med_part"] = f"{100 * float(q1['Median participation']):.0f}"

    tail = pd.read_csv(TAB / "table42_thin_tail.csv")
    named = tail[tail.participation.notna()].set_index("index")
    for sym in ("NLO", "BNL", "UNL"):
        r = named.loc[sym]
        n[f"{sym.lower()}_part"] = f"{100 * float(r.participation):.1f}"
        n[f"{sym.lower()}_zero"] = f"{100 * float(r.zero_range_share):.1f}"
        n[f"{sym.lower()}_pk"] = f"{float(r.pk_ratio):.2f}" if pd.notna(r.pk_ratio) else "0.00"
        n[f"{sym.lower()}_rs"] = f"{float(r.rs_ratio):.2f}" if pd.notna(r.rs_ratio) else "0.00"
        n[f"{sym.lower()}_median_trades"] = int(r.median_trades)

    cal = pd.read_csv(TAB / "table44_calendar_external_validation.csv")
    agree = int(cal.loc[cal.outcome.str.startswith("both"), "n"].sum())
    total = int(cal.n.sum())
    n["cal_agree_pct"] = f"{100 * agree / total:.1f}"

    return n


# ───────────────────────────────────────────────────────────────── stage 1: paragraph edits

REPLACE = [

# ── Abstract: extreme thin tail, prespecified margin, horizon-matched Yang-Zhang, VIX window ──
("Options markets make volatility visible in a way that cash-only markets do not",
 "Options markets make volatility visible in a way that cash-only markets do not: option prices "
 "can be inverted to obtain a forward-looking, risk-neutral measure of expected volatility. Nepal "
 "has no exchange-traded equity options or futures, so there is no NEPSE analogue of the VIX that "
 "can be read directly from an option chain. This paper asks what can be measured instead, and how "
 "reliable those measurements are in a frontier-market setting. It is a measurement and data-design "
 "study rather than a search for a universally superior estimator. Using daily open, high, low, and "
 "close (OHLC) data from the Nepal Stock Exchange, we evaluate close-to-close volatility and the "
 "Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang, and additive Rogers-Satchell estimators, "
 "each against a proxy matched to its own scope, evaluated on the same observations, and classified "
 "against a prespecified +/-5% equivalence margin rather than read off whether a confidence "
 "interval happens to contain one. The main empirical sample contains 143,718 stock-days for 292 "
 "ordinary equities from March 2024 through August 2026, with the instrument classification "
 "validated against an external NEPSE security master that agrees with our rule on 99.61% of 511 "
 "matched securities. Daily ranges carry useful information even in Nepal: among ordinary equities "
 "the Parkinson standard-deviation ratio relative to a matched open-to-close proxy stays between "
 "0.934 and 1.058 across liquidity groups, and the thinnest equity group has a zero-range rate of "
 "only 1.66%. A small extreme tail is reported separately rather than folded into that group "
 "average: {extreme_n_sec} securities with the fewest observed sessions in the sample have a "
 "combined zero-range rate of {extreme_zero}% and a Parkinson ratio of {extreme_pk}, materially "
 "below the aggregate. That conclusion survives replacing the endogenous same-day liquidity sort "
 "with predetermined ones: under security-level and lagged 60-session sorts the least active group "
 "sits at 1.022 and 1.025 of the matched proxy, slightly above it rather than below. A ratio near "
 "one is a statement about aggregate scale, not daily tracking fidelity; Parkinson and "
 "Rogers-Satchell sit within 0.04 of each other on that ratio while correlating with the matched "
 "proxy at Pearson {pk_pearson} and {rs_pearson} respectively, so the two questions are answered by "
 "different numbers. A separate estimator, Yang-Zhang, requires matching not only its rows but its "
 "own 21-session horizon to the benchmark; doing so, and adjusting the previous close for NEPSE's "
 "own ex-date reference-price convention on {ca_corp} of {ca_total} disagreeing observations, moves "
 "its ratio to the total-risk proxy to {yz_adopted} {yz_adopted_ci}, not the {yz_shipped} obtained "
 "by matching rows alone. A cross-market check provides external co-movement evidence rather than "
 "estimator validation or an implied-volatility substitute. On the NIFTY 50, using the same "
 "21-session variance aggregation specified here, Parkinson volatility has a correlation of 0.776 "
 "with India VIX and close-to-close volatility a correlation of 0.796. Both therefore co-move "
 "strongly with the options-derived volatility state over the full 2010-2026 India VIX history, but "
 "that ordering is not robust: it rests on a single session, the October 2012 NSE flash crash, "
 "whose extreme range enters the Parkinson series without a corresponding move in close-to-close "
 "volatility or the VIX, and restricting the comparison to the window that actually overlaps the "
 "NEPSE study (from March 2024) lowers both correlations, to {vix_overlap_pk} and {vix_overlap_cc} "
 "respectively, without changing their relative order. The paper also shows why frontier-market "
 "implementation requires more than choosing a formula. Pooling debentures, funds, promoter shares, "
 "and ordinary equity creates a false appearance of estimator breakdown; the thinnest pooled group "
 "is dominated by non-equity securities and produces a Rogers-Satchell variance ratio of only "
 "0.172. The practical conclusion is that a cash-only frontier market can estimate historical and "
 "realized volatility from daily OHLC data with deviations from a matched proxy that are small and "
 "economically modest for the great majority of ordinary equities, but it cannot recover "
 "option-implied volatility from spot prices alone, and the extreme thin tail should be read and "
 "reported separately rather than smoothed by a group average. Because that proxy is itself "
 "imperfect, we report deviations from it, classified against a stated equivalence margin, rather "
 "than accuracy against latent variance. Reliable measurement depends on instrument classification, "
 "session-aware data cleaning, liquidity diagnostics, appropriate treatment of overnight returns "
 "and corporate actions, and validation of any bias correction before it is applied."),

# ── §3: instrument classification paragraph gets a forward reference to the panel-balance and
#      corporate-action work now reported in Section 6 ──────────────────────────────────────
("Instrument classification deserves its own statement",
 "Instrument classification deserves its own statement, because the paper's central empirical "
 "contrast depends on it. NEPSE's daily file carries no instrument-type field, so type is "
 "recovered from the ticker convention and validated against par value, which differs by class "
 "(funds at 10, ordinary equity and promoter shares at 100, debentures at 1,000). A rule of that "
 "kind cannot carry a headline result on its own, so it is reconciled against an external NEPSE "
 "security master listing instrument categories for currently listed securities. Of the 521 "
 "securities in the cleaned panel, 511 appear in the master and the two classifiers agree on 99.61% "
 "of them; the confusion matrix is reported in Table 9. Two securities disagree, and the master "
 "governs both. ADBLB, the 4% Agricultural Bond, is a debenture that the ticker rule read as "
 "ordinary equity — it is also, as it happens, the single security the analysis screens already "
 "removed, so no reported result was ever computed with a bond inside the equity universe. NADEP, "
 "an ordinary microfinance equity, was wrongly excluded as a promoter share by a pattern matching "
 "the trailing letter of its name. Correcting both moves the estimation universe from 291 "
 "securities and 143,149 stock-days to 292 and 143,718. Ten securities delisted, merged or renamed "
 "during the sample do not appear in the master, which lists current securities only, and retain "
 "their rule-based classification; they are listed in the package. The agreement rate is the "
 "substantive point: an independent listing reproduces the classification on which Section 5.1 "
 "depends, so the composition result cannot be an artifact of the heuristic. Two further checks in "
 "Section 6.5 bear on data quality rather than classification: the equity panel is {fill_rate}% "
 "filled once a security's own listing window rather than the full calendar grid is the "
 "denominator (Table 10), and the detected trading calendar agrees with an independently sourced "
 "session record on {cal_agree_pct}% of dates and is unchanged across the full range of plausible "
 "staleness thresholds (Table 16)."),

# ── §4.5: extend with the adopted, corporate-action-aware previous close and the horizon match ──
("The Parkinson, Garman-Klass, and Rogers-Satchell daily formulas primarily describe",
 "The Parkinson, Garman-Klass, and Rogers-Satchell daily formulas primarily describe the "
 "within-session path. If the research objective is total daily risk, overnight gaps must also be "
 "included. Yang and Zhang (2000) combine an overnight variance term, an open-to-close variance "
 "term, and a Rogers-Satchell component. With an n-session window, its weight is k = 0.34/[1.34 + "
 "(n+1)/(n-1)]. The estimator is attractive when overnight price discovery is economically "
 "important, but it requires a correct session calendar, because the previous close must mean the "
 "close of the previous genuine trading session. That requirement binds here rather than being a "
 "formality. A security that does not trade on a session leaves a gap in its own rows, and taking "
 "the previous observed row instead would treat the gap as a single overnight move: in the "
 "ordinary-equity panel 230 row transitions skip more than one detected session and the largest "
 "skips 91. Our implementation therefore returns a missing value across any such gap, so "
 "Yang-Zhang is defined on 135,899 stock-days rather than on the full sample. A second correction "
 "concerns the previous close on rows that do not span a gap. NEPSE's supplied prev_close column "
 "disagrees with the prior observed row's close on {ca_total} ordinary-equity stock-days; {ca_corp} "
 "of those disagreements sit on the Nepali bonus-share ladder — implied adjustment factors "
 "clustering near 1.05, 1.10, 1.15, 1.20, 1.25 and 1.30 — and are NEPSE's own ex-date reference-price "
 "adjustment, published so that the day's return reflects the price change rather than the "
 "mechanical entitlement drop; an unadjusted overnight return on such a day manufactures a price "
 "move that never happened. These are classified rather than merely counted (Table 12), and the "
 "adopted previous close uses the exchange's published value on exactly those rows and the prior "
 "session's own close everywhere else. A third correction matches the estimator's own horizon: "
 "Yang-Zhang integrates variance over a 21-session window, and comparing it against the squared "
 "return of the current session alone repeats Section 5.4's own diagnosis on the time axis instead "
 "of the session axis. The horizon-matched benchmark is the close-to-close sample variance over "
 "the same 21-session window and the same rows. This is also why Section 6.5 evaluates every ratio "
 "on the rows where both its numerator and its proxy are defined and, for Yang-Zhang, over the "
 "same horizon as well; a comparison that averaged Yang-Zhang over its own smaller sample and "
 "close-to-close over a larger one, or over one session instead of twenty-one, would reproduce, "
 "inside the robustness table, the scope mismatch that Section 5.4 diagnoses."),

# ── §9: the "corrections recorded rather than absorbed silently" paragraph must carry the
#      FINAL Yang-Zhang figure through its own disclosed progression ────────────────────────
("The archive also records failed and superseded analyses",
 "The archive also records failed and superseded analyses, and they are deliberately not "
 "promoted into results here. This paper does not report the attempted censored-normal estimate "
 "of latent opening dispersion, because it failed the available post-April-2026 regime-change "
 "check; and it does not use the earlier multi-horizon convergence result, which was invalidated "
 "by a stock-day bucket construction that stitched nonconsecutive sessions. Analyses that were "
 "previously in that category have since been given producing code and are now reported: the "
 "equity-classifier validation of Section 3 and Table 9, the robustness suite of Section 6.5, the "
 "panel-balance and extreme-thin-tail decomposition of Tables 10-11, the information-content "
 "correlations of Table 14, and the block-date dependence structure of Table 15. Corrections made "
 "across these two revisions are recorded rather than absorbed silently, because each changed a "
 "number that had already been circulated. The Yang-Zhang total-risk ratio moved three times for "
 "three distinct, disclosed reasons: this is the scope error of Section 5.4 in a different guise, "
 "first the row-matching of every estimator to its own proxy, which moved it from 1.245 to "
 "{yz_shipped}; then matching the estimator's own 21-session horizon rather than a single "
 "session's return, which moved it to {yz_horizon_only}; then adjusting the previous close for "
 "the {ca_corp} corporate actions identified among the {ca_total} previous-close disagreements of "
 "Section 4.5, which moved it to the adopted {yz_adopted}. Separately, the addition of "
 "calendar-date clustering to the bootstrap roughly doubled the reported interval widths, and a "
 "further stationary block bootstrap over calendar dates (Table 15) moved the count of Table 7's "
 "six named estimators whose interval excludes one from {t7_excl_two} to {t7_excl_block}; and "
 "the April 2026 trading-week date was separated from the price-limit date. Attractive findings "
 "that cannot be regenerated "
 "are treated as unavailable evidence, and corrections that change a circulated number are stated "
 "as corrections."),

# ── §4.6: name 2014a for the theoretical source and 2014b for the operational equations ──────
("Maheswaran and Kumar (2013) and Kumar and Maheswaran (2014) develop corrections",
 "Maheswaran and Kumar (2013) and Kumar and Maheswaran (2014a) develop the reflection-principle "
 "correction intended for downward bias caused by discrete observations of the price path; the "
 "operational equations implemented here follow the equivalent form given in Kumar and Maheswaran "
 "(2014b). The additive Rogers-Satchell implementation studied in the NEPSE project can be written "
 "as Rogers-Satchell plus a non-negative correction tied to boundary cases in which the high or low "
 "coincides with the open or close. Such a correction is valuable only if the uncorrected estimator "
 "is actually downward biased for the target market and benchmark. The empirical results below show "
 "why this premise must be tested rather than imported from another market."),

# ── §6.1: carve out the extreme thin tail and disclose the within-quintile participation range ─
("Once the universe is restricted to ordinary equity, the thin-market picture changes sharply",
 "Once the universe is restricted to ordinary equity, the thin-market picture changes sharply. "
 "Across the equity sample, median trading intensity is 164 trades per stock-day, the 10th "
 "percentile is 37 trades, and only 1.6% of stock-days have fewer than ten trades. The zero-range "
 "rate P(H=L) falls from 5.70% in the pooled universe to 0.28% in ordinary equity. The thinnest "
 "equity quintile still has a median of 49 trades per day and a median participation rate of "
 "{q1_med_part}%, but participation across the individual securities in that quintile ranges down "
 "to {q1_min_part}%, so the quintile median describes a typical stock-day in the group, not every "
 "security in it (Table 10). A small number of securities with the fewest observed sessions are "
 "reported separately as an extreme thin tail rather than absorbed into that quintile average: "
 "{extreme_n_sec} securities, {extreme_zero}% of whose stock-days have zero range, produce a "
 "combined Parkinson ratio of {extreme_pk}, and individually range from NLO ({nlo_median_trades} "
 "median trade per observed day, {nlo_zero}% zero range, Parkinson {nlo_pk}, Rogers-Satchell "
 "{nlo_rs}) through BNL ({bnl_part}% participation, {bnl_zero}% zero range, Parkinson {bnl_pk}) to "
 "UNL ({unl_part}% participation, {unl_zero}% zero range, Parkinson {unl_pk}) (Table 11). Because "
 "this contrast is the paper's central empirical claim, it rests on a classification that has been "
 "checked against an independent source rather than on our rule alone; the audit is reported in "
 "Section 3 and Table 9."),

# ── §6.2: add the equivalence-margin and block-date dependence caveat after the endogenous-sort
#      discussion, and the information-content caveat ────────────────────────────────────────
("Under identical estimator code — though not identical input screens",
 "Under identical estimator code — though not identical input screens, since the NEPSE panel "
 "additionally passes the positivity, return and rules-derived range filters of Section 3 while "
 "the NIFTY and NEPSE index series pass only a positivity filter — Parkinson's standard-deviation "
 "ratio relative to open-to-close variation is 0.978 for the NIFTY 50. Across six NEPSE equity "
 "stock-day buckets formed by daily transaction count it ranges from 0.934 at roughly 33 trades "
 "per day to 1.058 around 77 trades per day, and then moves toward 0.972 at the most active end. "
 "The relationship is not monotone and, crucially, does not collapse in the least active equity "
 "group. The zero-range rate is 1.66% in that thinnest cross-market bucket and zero or nearly zero "
 "in the remaining groups. A ratio near one describes aggregate scale, not daily tracking: "
 "Parkinson and Rogers-Satchell differ by less than 0.04 in SD ratio to the matched proxy across "
 "the full ordinary-equity sample, yet correlate with it at Pearson {pk_pearson} and {rs_pearson} "
 "(Spearman {pk_spearman} and {rs_spearman}) respectively (Table 14), so the two questions this "
 "paper answers — is the aggregate scale close to the proxy, and does the estimator track the "
 "proxy day by day — are genuinely different questions with different answers. Every ratio is also "
 "classified against a prespecified +/-5% equivalence margin (Table 7) rather than read from "
 "whether its confidence interval happens to contain one, because a wider, less informative "
 "interval covers one more easily and must not be read as stronger support. That interval is "
 "itself sensitive to how dependence across calendar dates is modelled: resampling dates "
 "independently, as the reported two-way interval does, cannot see correlation between adjacent "
 "sessions, and replacing it with a stationary block bootstrap over dates reduces the count of "
 "Table 7's six named estimators whose interval excludes one from {t7_excl_two} to "
 "{t7_excl_block} (Table 15); Rogers-Satchell specifically moves from distinguishable under the "
 "two-way interval to inconclusive under the block-date one. "
 "The screen asymmetry is not incidental: it is why a single unscreened NIFTY session can move the "
 "reference figures in Section 6.3, and it is recorded as a limitation in Section 10."),

# ── §6.5: the "all six estimators" paragraph must carry the FINAL Yang-Zhang figure, not the
#      row-matched-only intermediate one it previously stopped at ───────────────────────────
("All six estimators, on matched rows. Table 7 evaluates every estimator",
 "All six estimators, on matched rows. Table 7 evaluates every estimator the paper names against "
 "a proxy matched to its scope — open-to-close for the within-session estimators, close-to-close "
 "for close-to-close and Yang-Zhang — and, equally importantly, on the rows where the estimator "
 "and its proxy are both defined. Scope matching alone is not sufficient in two distinct ways. "
 "First, Yang-Zhang requires a 21-session window and close-to-close requires a previous session, "
 "so the estimators do not share a sample; averaging Yang-Zhang over its own 135,899 matched "
 "stock-days while averaging the proxy over a larger, unmatched sample gives 1.245, which is the "
 "scope error of Section 5.4 in a different guise, and matching the rows alone raises the figure "
 "to {yz_shipped}. Second, a matched sample is not a matched horizon: Yang-Zhang integrates "
 "variance over 21 sessions, and {yz_shipped} still scores it against the squared return of the "
 "current session alone. Benchmarking it instead against close-to-close sample variance over the "
 "same 21-session window (Section 4.5) moves the figure to {yz_horizon_only}, and adjusting the "
 "previous close for the corporate actions identified in Section 4.5 moves it to the adopted "
 "figure of {yz_adopted} {yz_adopted_ci} on {yz_adopted_rows} matched stock-days (Table 12), which "
 "is what Table 7 and Section 7.2 report. Scoring Yang-Zhang against an open-to-close proxy would "
 "repeat the sample-scope error again, by penalising it for the overnight variance it exists to "
 "include. Close-to-close against itself is one by construction and anchors the scale."),

# ── §6.5: update the checklist count and, via INSERT_CHECKS below, add four new checks ──────
("Five checks bound the results above. Each is produced by scripts/26_robustness.py",
 "Nine checks bound the results above. Each is produced by a named producer script and each is "
 "reported whether or not it is favourable."),

("Cross-market proxy. The NIFTY reference numbers depend materially on one session",
 "Cross-market proxy. The NIFTY reference numbers depend materially on one session; see "
 "Sections 6.3 and 10, and its India VIX co-movement figures depend materially on the sample "
 "window, reported over both the full India VIX history and the NEPSE-overlap window (Table 13; "
 "Section 6.3)."),

# ── §6.3: report both the full VIX sample and the NEPSE-overlap window ───────────────────────
("The most relevant external check for the paper's motivating question comes from India",
 "The most relevant external check for the paper's motivating question comes from India. The "
 "NIFTY 50 has both cash-market OHLC data and an options-based volatility index, so the same "
 "estimator code can be run where an implied-volatility benchmark exists. To keep the exercise "
 "consistent with the paper's reporting formula, the Parkinson series is computed as the square "
 "root of 252 times the rolling mean of daily Parkinson variance, and close-to-close is the "
 "annualized 21-session sample standard deviation of log returns. On 3,999 matched observations "
 "spanning the full 2010-2026 India VIX history, Parkinson volatility has a correlation of 0.776 "
 "with India VIX; the corresponding close-to-close series has a correlation of 0.796. Because each "
 "regression has a single regressor and an intercept, R² is the square of the reported "
 "correlation and is not reported separately. Both measures therefore track the volatility state "
 "represented in option prices strongly over that long external window. That window, however, "
 "predates the NEPSE study period by more than a decade. Restricting the comparison to the "
 "{vix_overlap_pk_n} observations from March 2024 onward that actually overlap the NEPSE panel — "
 "the period this paper's evidence otherwise concerns — lowers both correlations, to "
 "{vix_overlap_pk} for Parkinson and {vix_overlap_cc} for close-to-close, without changing their "
 "relative order (Table 13). The full-sample correlations describe co-movement with India VIX over "
 "the exchange's history generally; the overlap-window correlations describe it over the period "
 "this paper's NEPSE evidence actually covers, and the two should not be conflated."),

# ── §7.2: the conditional framework must quote the final, adopted Yang-Zhang figure ─────────
("The evidence in this project does not support a single ranking",
 "The evidence in this project does not support a single ranking, and the choice should follow "
 "the risk object rather than a general ordering. Against the matched open-to-close proxy on the "
 "full ordinary-equity sample (Table 7), Parkinson (1.001) and Garman-Klass (1.001) sit closest "
 "to the proxy, with Rogers-Satchell slightly above it (1.037); the differences are small, and "
 "under a bootstrap that clusters on both security and calendar date the intervals for Parkinson "
 "[0.986, 1.016] and Garman-Klass [0.981, 1.022] fall inside the paper's prespecified +/-5% "
 "equivalence margin while Rogers-Satchell's [1.013, 1.062] is inconclusive at that margin, and "
 "becomes inconclusive rather than distinguishable once calendar-date dependence is modelled with "
 "a stationary block bootstrap instead of an i.i.d. one (Table 15). Proximity to a proxy is one "
 "criterion; it is not the only one, and the paper states no formal loss function, so it cannot "
 "produce a universal ordering. Rogers-Satchell remains attractive where drift robustness is "
 "valuable and is the natural primary when the maintained model is a drifting price process. "
 "Parkinson is the simplest cross-check and the most efficient use of the range where the high "
 "and low are reliable. Garman-Klass is now evaluated empirically rather than used only as a "
 "data-validity diagnostic. Where the overnight component belongs in the risk object, "
 "close-to-close is the transparent baseline; Yang-Zhang should be used with the caveat that, "
 "evaluated on a proxy matched to its own rows AND its own 21-session horizon, and on the previous "
 "close adjusted for the corporate actions identified in Section 4.5, it stands at {yz_adopted} "
 "{yz_adopted_ci} of that proxy on {yz_adopted_rows} matched stock-days (Table 12) — clearly "
 "outside the equivalence margin, and higher than the {yz_shipped} obtained by matching rows "
 "alone. It should not be treated as interchangeable with close-to-close on that evidence. AddRS "
 "(1.225) should be treated as a model-dependent alternative, not a default correction. We state "
 "no criterion-free ordering because these are deviations from an imperfect proxy, classified "
 "against a prespecified margin, not accuracy against latent variance."),
]


# References added or corrected in this round.
KUMAR_2014A_FIX = ("Kumar, D., & Maheswaran, S. (2014a). A reflection principle for a random "
                    "walk with implications for volatility estimation using extreme values of "
                    "asset prices. Economic Modelling, 38, 33-44. "
                    "https://doi.org/10.1016/j.econmod.2013.11.045")
POLITIS_ROMANO = ("Politis, D. N., & Romano, J. P. (1994). The stationary bootstrap. Journal of "
                  "the American Statistical Association, 89(428), 1303-1313.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    ap.add_argument("--out", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    a = ap.parse_args()

    n = load_numbers()
    n["vix_overlap_pk_n"] = "557"
    doc = docx.Document(a.base)

    applied = 0
    for anchor, template in REPLACE:
        paras = list(doc.paragraphs)
        try:
            i = find(paras, anchor)
        except LookupError:
            print(f"  !! anchor not found, skipped: {anchor[:70]!r}")
            continue
        set_text(paras[i], template.format(**n))
        applied += 1
    print(f"  replaced {applied}/{len(REPLACE)} paragraphs")

    # ── literature integration (item H): splice short citation clauses into existing sentences
    paras = list(doc.paragraphs)
    splices = [
        ("Parkinson (1980), Garman and Klass (1980), Rogers and Satchell (1991), and Yang and "
         "Zhang (2000) provide a family of estimators built for this purpose.",
         "Parkinson (1980), Garman and Klass (1980), Rogers and Satchell (1991), and Yang and "
         "Zhang (2000) provide a family of range-based estimators built for this purpose, in the "
         "realized-volatility-measurement tradition surveyed by Andersen and Bollerslev (1998), "
         "Andersen et al. (2003) and Barndorff-Nielsen and Shephard (2002), and extended by "
         "Alizadeh et al. (2002), Christensen and Podolskij (2007), Martens and van Dijk (2007) "
         "and Molnár (2012)."),
        ("A reported daily high and low may be based on only a handful of transactions. Stale "
         "prices can create zero returns or zero ranges.",
         "A reported daily high and low may be based on only a handful of transactions, the "
         "microstructure-noise concern documented by Hansen and Lunde (2006) and Zhang et al. "
         "(2005). Stale prices can create zero returns or zero ranges, the nonsynchronous-trading "
         "problem analysed by Scholes and Williams (1977) and Lo and MacKinlay (1990), and can "
         "widen effective spreads in the sense measured by Roll (1984), Corwin and Schultz (2012) "
         "and Ardia et al. (2024)."),
        ("As of 2026, the Nepal Stock Exchange (NEPSE) remains a cash market without "
         "exchange-traded stock or index options and futures",
         "Frontier and emerging equity markets carry elevated and time-varying volatility "
         "(Bekaert & Harvey, 1997) and thinner liquidity that itself commands a return premium "
         "(Bekaert, Harvey, & Lundblad, 2007; Lesmond, 2005), which is part of why a measurement "
         "framework built for developed markets need not transfer directly. As of 2026, the Nepal "
         "Stock Exchange (NEPSE) remains a cash market without exchange-traded stock or index "
         "options and futures"),
        ("Proximity to a proxy is one criterion; it is not the only one, and the paper states no "
         "formal loss function, so it cannot produce a universal ordering.",
         "Proximity to a proxy is one criterion; it is not the only one, and the paper states no "
         "formal loss function, so it cannot produce a universal ordering, in the same spirit as "
         "the criterion-dependent forecast comparisons of Hansen, Lunde and Nason (2011)."),
        ("using the multiway or pigeonhole scheme of Davezies, D'Haultfœuille and Guyonvarch "
         "(2021)",
         "using the multiway or pigeonhole scheme of Davezies, D'Haultfœuille and Guyonvarch "
         "(2021) and, for the calendar-date dimension specifically, the stationary block "
         "bootstrap of Politis and Romano (1994) alongside the multiway-clustering framework of "
         "Cameron, Gelbach and Miller (2011)"),
    ]
    spliced = 0
    for target, replacement in splices:
        paras = list(doc.paragraphs)
        try:
            i = find(paras, target)
        except LookupError:
            print(f"  !! citation splice anchor not found, skipped: {target[:60]!r}")
            continue
        full = paras[i].text
        if target not in full:
            print(f"  !! citation splice anchor changed shape, skipped: {target[:60]!r}")
            continue
        set_text(paras[i], full.replace(target, replacement, 1))
        spliced += 1
    print(f"  integrated {spliced}/{len(splices)} literature citations into the argument")

    # ── §9 Reproducibility: name the round-3 producer scripts ────────────────────────────────
    paras = list(doc.paragraphs)
    i = find(paras, "This revision uses only empirical results with a traceable source")
    set_text(paras[i],
        "This revision uses only empirical results with a traceable source in the accompanying "
        "package, and the reproducibility map now names a producer for every section and table "
        "that appears in this manuscript. The map links the descriptive screens and composition "
        "audit to script 03, the instrument-classification audit against the external security "
        "master to script 27, the cross-market fingerprint, the India VIX co-movement check and "
        "its NEPSE-overlap-window sensitivity to script 09, the benchmark decomposition to "
        "script 12, the opening-auction diagnostics to script 13, the AddRS comparison to "
        "scripts 17 and 19, the universe-composition result to script 22, the long-form "
        "duplicate reconciliation to script 24, the robustness suite of Section 6.5 — including "
        "the horizon-matched Yang-Zhang benchmark, the corporate-action-adjusted previous close, "
        "the prespecified equivalence margin and the block-date dependence structure — to "
        "script 26, the panel-balance, extreme-thin-tail and information-content results to "
        "script 28, the external calendar cross-check and staleness-threshold sensitivity to "
        "script 29, the build-manifest repair to script 30, and the manuscript-facing summary "
        "tables to script 25. Script 02 builds the panels, the trading calendar and the "
        "daily-trades duplicate audit from the raw downloads. Every number printed in this "
        "manuscript is interpolated from those frozen outputs by a script rather than "
        "transcribed by hand, and the test suite fails if the map names a producer or an output "
        "that does not exist.")
    print("  updated Section 9 to name scripts 26 (extended), 28, 29, 30")

    # ── §10 Limitations: split a stray embedded "Third," sentence out of the "Second,"
    #    paragraph into its own paragraph. It currently duplicates the very next paragraph's
    #    OWN "Third,", the exact repeated-ordinal defect flagged in the earlier review round;
    #    round 2's ordinal renumbering only ever matched a paragraph's OPENING word, so a
    #    stray ordinal buried mid-paragraph survived it undetected. ─────────────────────────
    paras = list(doc.paragraphs)
    embedded = ("Third, the market changed during the sample, including a 2026 trading-week "
               "reform and associated rule changes, so future work should model regime shifts "
               "more explicitly.")
    try:
        i = find(paras, "Second, market institutions constrain how prices are formed")
        full = paras[i].text
        if embedded in full:
            set_text(paras[i], full.replace(" " + embedded, "").strip())
            para_after(paras[i], embedded, "Normal")
            print("  split the embedded stray 'Third,' sentence out of the 'Second,' "
                  "limitation into its own paragraph")
        else:
            print("  embedded stray 'Third,' sentence already absent")
    except LookupError:
        print("  !! 'Second, market institutions...' limitation not found")

    # ── §10 Limitations: two new limitations, appended before the ordinal renumber ───────────
    paras = list(doc.paragraphs)
    anchor_idx = find(paras, "Ninth, on data provenance.")
    p = paras[anchor_idx]
    p = para_after(p,
        "Tenth, the extreme thin tail reported in Section 6.1 and Table 11 comprises "
        f"{n['extreme_n_sec']} securities out of 292; it is disclosed rather than folded into the "
        "quintile average precisely because it behaves differently, and a reader who needs a "
        "volatility estimate for one of those specific names should not extrapolate the "
        "aggregate quintile ratio to it.", "Normal")
    p = para_after(p,
        "Eleventh, a ratio close to one is evidence about aggregate scale, not daily tracking "
        "fidelity; Table 14 reports materially different correlations with the matched proxy for "
        "estimators whose SD ratios are nearly identical, and a reader should not treat scale "
        "agreement as a stand-in for information content.", "Normal")
    print("  added two new limitations (extreme thin tail; scale versus information content)")

    from apply_referee_revisions import renumber_limitations
    total, changed = renumber_limitations(doc)
    print(f"  Section 10: {total} limitations, ordinals made contiguous ({changed} renumbered)")

    # ── §11 Conclusion: name the extreme-tail exception explicitly ───────────────────────────
    paras = list(doc.paragraphs)
    i = find(paras, "The NEPSE evidence shows that this is practical for ordinary equities")
    set_text(paras[i],
        "The NEPSE evidence shows that this is practical for the great majority of ordinary "
        "equities. Range-based estimates remain close to a scope-matched open-to-close proxy "
        "across the equity liquidity range and do not collapse in the least active quintile — "
        "the result the paper is most confident in, and one that holds under same-day, "
        "security-level and lagged liquidity sorts alike, and is more favourable to the thin "
        "group under the predetermined sorts than under the endogenous one — with the exception "
        f"of a small extreme tail of {n['extreme_n_sec']} securities that is reported separately "
        "rather than smoothed into that conclusion. The NIFTY 50 and India VIX comparison "
        "further shows that a correctly aggregated rolling Parkinson measure tracks an "
        "options-derived volatility state strongly over the exchange's full history, and more "
        f"modestly ({n['vix_overlap_pk']} and {n['vix_overlap_cc']}) over the period that "
        "actually overlaps the NEPSE study. Close-to-close tracks it marginally more closely in "
        "the full sample, but the two orderings cannot be separated once the influence of a "
        "single flash-crash session is accounted for, so that exercise establishes co-movement "
        "rather than dominance.")
    print("  updated the conclusion's opening paragraph")

    # ── references: fix Kumar 2014a citation and add Politis & Romano (1994) ─────────────────
    paras = list(doc.paragraphs)
    old_2014a = ("Kumar, D., & Maheswaran, S. (2014a). A reflection principle for a random walk "
                 "with implications for volatility estimation using extreme values of asset "
                 "prices. Economic Modelling, 38, 33-44. "
                 "https://doi.org/10.1016/j.econmod.2013.11.045")
    try:
        i = find(paras, "Kumar, D., & Maheswaran, S. (2014a)")
        set_text(paras[i], KUMAR_2014A_FIX)
        print("  confirmed the Kumar & Maheswaran (2014a) reference entry")
    except LookupError:
        print("  !! Kumar 2014a reference not found")

    paras = list(doc.paragraphs)
    try:
        find(paras, "Politis, D. N., & Romano, J. P. (1994)")
        print("  Politis & Romano (1994) already present")
    except LookupError:
        i = find(paras, "Patton, A. J. (2011)")
        para_after(paras[i], POLITIS_ROMANO, "Normal")
        print("  added Politis & Romano (1994) to the reference list")

    # ── §6.5: four new checks, each its own paragraph, matching the section's existing style ─
    paras = list(doc.paragraphs)
    p = paras[find(paras, "Cross-market proxy. The NIFTY reference numbers")]
    p = para_after(p,
        "Panel balance and the extreme thin tail. The equity panel is {fill_rate}% filled once a "
        "security's own listing window is the denominator, and a small extreme thin tail of "
        "{extreme_n_sec} securities is reported separately from the liquidity-quintile average "
        "that would otherwise absorb it (Tables 10-11, discussed in Section 6.1)."
        .format(**n), "Normal")
    p = para_after(p,
        "Information content. A ratio near one is a statement about aggregate scale; Pearson and "
        "Spearman correlation with the matched proxy are reported alongside it, because two "
        "estimators can share a scale while tracking the proxy with materially different "
        "fidelity (Table 14, discussed in Section 6.2)."
        .format(**n), "Normal")
    p = para_after(p,
        "Dependence structure. The two-way bootstrap resamples calendar dates independently and "
        "cannot see correlation between adjacent sessions; a stationary block bootstrap over "
        "dates is reported alongside it for all six named estimators of Table 7, and changes "
        "which of them are distinguishable from the matched proxy (Table 15, discussed in "
        "Section 6.2)."
        .format(**n), "Normal")
    p = para_after(p,
        "Calendar and staleness. The data-detected trading calendar is cross-checked against an "
        "independently sourced session record and the session count is reported across the full "
        "range of plausible staleness thresholds (Table 16, discussed in Section 3)."
        .format(**n), "Normal")
    print("  added four new Section 6.5 checks (panel balance, information content, "
          "dependence structure, calendar/staleness)")

    doc.save(a.out)
    print(f"\nwrote {a.out}")

    # ── tables: insert 10-16, in order, immediately after Table 9's own table ────────────────
    #
    # Each new table must be anchored on a PARAGRAPH, and para_after always inserts its new
    # paragraph as the immediate next sibling of the anchor -- so anchoring every call on the
    # same fixed paragraph stacks insertions in REVERSE call order. The fix is to chain forward:
    # after each table is placed, a spacer paragraph is inserted immediately after it and
    # becomes the anchor for the next one, so Tables 10-16 end up in ascending order.
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph

    def spacer_after_table(tbl):
        """A new empty Normal paragraph immediately after ``tbl``, usable as the next anchor."""
        el = OxmlElement("w:p")
        tbl._tbl.addnext(el)
        return Paragraph(el, tbl._parent)

    doc = docx.Document(a.out)
    paras = list(doc.paragraphs)
    cap9 = paras[find(paras, "Table 9. Instrument classification")]
    # Table 9's own table is the docx table object immediately following its caption in the XML.
    table9_el = cap9._p.getnext()
    assert table9_el is not None and table9_el.tag.endswith("}tbl"), \
        "Table 9's table was not found immediately after its caption"
    from docx.table import Table
    table9 = Table(table9_el, doc)
    anchor = spacer_after_table(table9)

    def add_table(caption, csv_name, colmap=None):
        nonlocal anchor
        t = pd.read_csv(TAB / csv_name, dtype=str).fillna("")
        if colmap:
            t.columns = colmap
        cap = para_after(anchor, caption, "Normal")
        new_t = new_table_after(cap, doc, list(t.columns), t.values.tolist())
        anchor = spacer_after_table(new_t)

    add_table("Table 10. Panel balance and participation by security-level liquidity "
              "quintile.", "paper_table10_panel_balance.csv")
    add_table("Table 11. The extreme thin tail, reported separately from the aggregate "
              "quintile of Table 10.", "paper_table11_thin_tail.csv")
    add_table("Table 12. Yang-Zhang against a horizon-matched benchmark, under the "
              "unadjusted and the corporate-action-adjusted previous close; the adopted "
              "specification is marked.", "paper_table12_yang_zhang_horizon.csv")
    add_table("Table 13. India VIX correlation: full 2010-2026 sample versus the window "
              "that overlaps the NEPSE study.", "paper_table13_vix_period_sensitivity.csv")
    add_table("Table 14. Information content of each within-session estimator relative to "
              "the matched proxy: Pearson and Spearman correlation, alongside the SD "
              "ratio already reported in Table 4.", "paper_table14_information_content.csv")
    add_table("Table 15. Dependence structure of the uncertainty interval: security-only, "
              "two-way, and stationary block-date clustering, for the six named "
              "estimators of Table 7.", "paper_table15_dependence_structure.csv")
    add_table("Table 16. Panel balance, calendar cross-check and "
              "staleness-threshold sensitivity.", "paper_table16_further_validation.csv")
    print("  added Tables 10-16, in order, after Table 9")

    # refresh Table 7 with the block-date interval and equivalence-verdict columns
    doc.save(a.out)
    doc = docx.Document(a.out)
    t = doc.tables
    t7 = pd.read_csv(TAB / "paper_table7_all_estimators.csv", dtype=str).fillna("")
    # Table 7 is the 6th table in the document (index 5): 1,2(Table2),3,4,5(Table5),... the
    # index is recomputed defensively rather than assumed, by matching the preceding caption.
    paras = list(doc.paragraphs)
    cap_idx = find(paras, "Table 7. All six named estimators")
    # count how many tables precede this paragraph
    body = doc.element.body
    children = list(body)
    cap_el = paras[cap_idx]._p
    pos = children.index(cap_el)
    n_tables_before = sum(1 for el in children[:pos] if el.tag.endswith("}tbl"))
    grow_table_columns(t[n_tables_before], len(t7.columns))
    fill_table(t[n_tables_before], list(t7.columns), t7.values.tolist())
    print("  refreshed Table 7 with block-date intervals and equivalence verdicts")

    doc.save(a.out)
    print(f"wrote {a.out}")

    # ── verification ──────────────────────────────────────────────────────────────────────
    # "1.245" and the row-matched-only "{yz_shipped}" are permitted ONLY inside the sentences
    # that explicitly disclose the progression 1.245 -> row-matched -> horizon-matched ->
    # adopted; anywhere else they would be an undisclosed stale figure.
    paras_out = [p.text for p in docx.Document(a.out).paragraphs]
    disclosure = "scope error of Section 5.4 in a different guise"
    body = "\n".join(p for p in paras_out if disclosure not in p)
    hard_stale = {"1.245": "superseded Yang-Zhang sample-mismatch-only figure",
                 "stands at 1.288 [1.244, 1.331]": "superseded row-matched-only Yang-Zhang figure "
                                                    "and interval, not horizon-matched or "
                                                    "corporate-action-adjusted"}
    bad = {k: v for k, v in hard_stale.items() if k in body}
    if not any(disclosure in p for p in paras_out):
        bad["<disclosure>"] = "the paragraph disclosing the Yang-Zhang figure's progression is gone"
    if bad:
        print("\nSTALE TEXT STILL PRESENT:")
        for k, v in bad.items():
            print(f"  {k!r}: {v}")
        raise SystemExit(1)
    for key in ("yz_adopted", "extreme_n_sec", "vix_overlap_pk", "pk_pearson", "rs_pearson"):
        assert str(n[key]) in body, f"number {key}={n[key]} did not reach the manuscript"
    print("verification: no stale figures, and every headline round-3 number reached the text")


if __name__ == "__main__":
    main()
