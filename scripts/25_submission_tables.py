"""Create manuscript-facing summary tables and a compact key-results check.

This script does not introduce new analysis. It reformats quantities already produced by the
paper-facing pipeline into tables that match the submitted manuscript and writes a compact ledger
of headline values used for submission QA.
"""
from __future__ import annotations

import pathlib
import sys
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.sample import load_sample

TAB = ROOT / "output" / "tables"
TAB.mkdir(parents=True, exist_ok=True)


def _fmt_ci_bound(v, dp=3):
    """Format one CI bound, falling back to 4 decimals when 3 would round it to a whole
    number it is not actually equal to.

    FORENSIC-AUDIT FOLLOW-UP (2026-09-04). A bound of 0.99997 displayed at 3dp as "1.000" is
    indistinguishable from an interval that genuinely reaches 1 -- exactly the confusion
    flagged for Table 6 (a [0.907, 1.000] display next to a coded "excludes one = True", the
    unrounded bound being 0.99953) and again for Table 15 (Rogers-Satchell's block-date lower
    bound, 0.99997, displayed as "1.000" beside "excludes one = False"). Every reader-visible
    CI bound is formatted through this helper so the decision the table's own boolean column
    encodes is never contradicted by what the printed number appears to say.
    """
    r = round(v, dp)
    if r == round(r) and abs(v - r) > 1e-12:
        return f"{v:.4f}"
    return f"{v:.{dp}f}"


def _ci(lo, hi, dp=3):
    return f"[{_fmt_ci_bound(lo, dp)}, {_fmt_ci_bound(hi, dp)}]"


fp_pre = pd.read_csv(TAB / "table14_cross_market_fingerprint.csv")
vix_tab_pre = pd.read_csv(TAB / "table15_vix_anchor.csv")

# F-6. These two quantities were previously frozen string literals ("2,296 usable sessions",
# "3,999 after 21-session matching") while every neighbouring cell of Table 1 was computed.
# A change in either input would have left Table 1 silently stale. Both are now read from the
# producer artifacts written by scripts/09_cross_market_control.py.
NEPSE_INDEX_SESSIONS = int(fp_pre.loc[fp_pre.regime.str.startswith("NEPSE index"), "n_days"].iloc[0])
VIX_MATCHED = int(vix_tab_pre["n_obs"].iloc[0])

full = load_sample(ROOT, "full", quiet=True)
eq = load_sample(ROOT, "equity", quiet=True)
nifty = pd.read_csv(ROOT / "data/external/nifty50.csv")
vix = pd.read_csv(ROOT / "data/external/india_vix.csv")

# Manuscript Table 1
pd.DataFrame([
    ["NEPSE main analysis panel (after screens)",
     f"{full.date.min().date()} to {full.date.max().date()}; {full.symbol.nunique()} securities",
     "Main OHLC and liquidity analysis"],
    ["NEPSE ordinary-equity subset", f"{eq.symbol.nunique()} equities; {len(eq):,} stock-days",
     "Primary estimation universe"],
    ["NEPSE index", f"{NEPSE_INDEX_SESSIONS:,} usable sessions", "Aggregate-market comparison"],
    ["NIFTY 50", f"{len(nifty):,} sessions, 2010-2026", "Cross-market implementation check"],
    ["India VIX", f"{len(vix):,} raw; {VIX_MATCHED:,} after 21-session matching",
     "Options-based external co-movement check"],
], columns=["Dataset", "Period / size", "Use in this paper"]).to_csv(
    TAB / "paper_table1_data_used.csv", index=False)


def _matched_total(conf: pd.DataFrame) -> int:
    """Securities the master could adjudicate: everything outside the '(not in master)' column."""
    cols = [c for c in conf.columns if c != "(not in master)"]
    return int(conf[cols].to_numpy().sum())


def _sum_agreements(conf: pd.DataFrame) -> int:
    """Cells where the rule-based row label equals the master column label."""
    return int(sum(conf.loc[i, c] for i in conf.index for c in conf.columns if i == c))


def zero_range_pct(df: pd.DataFrame) -> float:
    return 100 * df["high"].eq(df["low"]).mean()


def rs_zero_pct(df: pd.DataFrame) -> float:
    o, h, l, c = (np.log(df[k].astype(float).values) for k in ("open", "high", "low", "close"))
    u, d, x = h - o, l - o, c - o
    rs = u * (u - x) + d * (d - x)
    return 100 * (np.abs(rs) <= 1e-15).mean()

# Manuscript Table 3
pd.DataFrame({
    "Measure": ["Stock-days", "Median trades/day", "10th percentile trades/day",
                "Stock-days below 10 trades", "P(H = L)", "Parkinson exactly zero",
                "Rogers-Satchell exactly zero"],
    "Pooled universe": [f"{len(full):,}", f"{full.n_trades.median():.0f}",
                        f"{full.n_trades.quantile(.1):.0f}", f"{100*(full.n_trades<10).mean():.1f}%",
                        f"{zero_range_pct(full):.2f}%", f"{zero_range_pct(full):.2f}%",
                        f"{rs_zero_pct(full):.2f}%"],
    "Ordinary equity": [f"{len(eq):,}", f"{eq.n_trades.median():.0f}",
                        f"{eq.n_trades.quantile(.1):.0f}", f"{100*(eq.n_trades<10).mean():.1f}%",
                        f"{zero_range_pct(eq):.2f}%", f"{zero_range_pct(eq):.2f}%",
                        f"{rs_zero_pct(eq):.2f}%"],
}).to_csv(TAB / "paper_table3_instrument_classification_effect.csv", index=False)

# Manuscript Table 4
fp = fp_pre
# F-6. Row labels were previously keyed on `med == 33` / `med == 789`, i.e. float equality
# against whatever the bucket medians happened to be. A shifted panel would have silently
# mislabelled the rows. Thin/dense are now the argmin/argmax of the bucket medians.
_neq = fp[fp.trades.notna()]
_THIN, _DENSE = _neq.trades.min(), _neq.trades.max()
rows = []
for _, r in fp.iterrows():
    if str(r["regime"]).startswith("NEPSE index"):
        continue
    if str(r["regime"]).startswith("NIFTY"):
        label, med = "NIFTY 50", "Dense"
    else:
        med = int(round(r["trades"]))
        label = ("NEPSE equity - thin" if r["trades"] == _THIN else
                 "NEPSE equity - dense" if r["trades"] == _DENSE else "NEPSE equity")
    rows.append([label, med, round(r["Parkinson_sd_ratio"], 3),
                 round(r["Rogers-Satchell_sd_ratio"], 3), f"{r['zero_range_pct']:.2f}%"])
pd.DataFrame(rows, columns=["Regime", "Median trades/day",
                            "Parkinson: SD ratio to matched proxy",
                            "Rogers-Satchell: SD ratio to matched proxy",
                            "Zero range"]).to_csv(
    TAB / "paper_table4_cross_market_fingerprint.csv", index=False)

# Manuscript Table 5
add = pd.read_csv(TAB / "table23_addrs_benchmark.csv")
rows = []
for _, r in add.iterrows():
    reg = "NIFTY 50" if r["regime"] == "NIFTY 50 index" else r["regime"]
    if reg == "NIFTY 50":
        interp = "Correction lands near the matched proxy"
    elif reg == "NEPSE Q1":
        interp = "No RS deficit against the proxy; correction overshoots"
    elif reg in {"NEPSE Q2", "NEPSE Q3", "NEPSE Q4"}:
        interp = "Base estimator already above the matched proxy"
    else:
        interp = "Correction still overshoots"
    rows.append([reg, round(r["RS/OC"], 3), round(r["AddRS/OC"], 3), interp])
pd.DataFrame(rows, columns=["Regime", "RS: ratio to matched proxy",
                            "AddRS: ratio to matched proxy", "Interpretation"]).to_csv(
    TAB / "paper_table5_addrs_benchmark.csv", index=False)

# Submission QA ledger
vix_tab = pd.read_csv(TAB / "table15_vix_anchor.csv")
dec = pd.read_csv(TAB / "table3b_instrument_composition_by_stockday_decile.csv")
checks = [
    ["ordinary_equity_stock_days", len(eq), "count", "03_descriptive.py"],
    ["ordinary_equity_securities", eq.symbol.nunique(), "count", "03_descriptive.py / 22_universe_composition.py"],
    ["thinnest_stockday_decile_non_equity_share_pct", round(100*dec.loc[dec.dec==0, "non_equity_share"].iloc[0], 1), "percent", "03_descriptive.py"],
    ["NIFTY_Parkinson_OC_SD", round(fp.loc[fp.regime.str.startswith("NIFTY"), "Parkinson_sd_ratio"].iloc[0], 3), "ratio", "09_cross_market_control.py"],
    ["NEPSE_thin_Parkinson_OC_SD", round(fp.loc[fp.trades==_THIN, "Parkinson_sd_ratio"].iloc[0], 3), "ratio", "09_cross_market_control.py"],
    ["NEPSE_thin_zero_range_pct", round(fp.loc[fp.trades==_THIN, "zero_range_pct"].iloc[0], 2), "percent", "09_cross_market_control.py"],
    ["IndiaVIX_Parkinson_corr", round(vix_tab.loc[vix_tab.estimator=="Parkinson (21d)", "corr"].iloc[0], 3), "correlation", "09_cross_market_control.py"],
    ["IndiaVIX_CC_corr", round(vix_tab.loc[vix_tab.estimator=="Close-to-close (21d)", "corr"].iloc[0], 3), "correlation", "09_cross_market_control.py"],
    ["NIFTY_AddRS_OC", round(add.loc[add.regime=="NIFTY 50 index", "AddRS/OC"].iloc[0], 3), "ratio", "17_addrs_benchmark.py"],
    ["NEPSE_Q1_AddRS_OC", round(add.loc[add.regime=="NEPSE Q1", "AddRS/OC"].iloc[0], 3), "ratio", "17_addrs_benchmark.py"],
]

# Robustness quantities the manuscript must now quote alongside the point estimates.
_sens = pd.read_csv(TAB / "table31_nifty_outlier_sensitivity.csv")
_full, _loo = _sens.iloc[0], _sens.iloc[1]
checks += [
    ["IndiaVIX_Parkinson_corr_ex_outlier", round(_loo.VIX_Parkinson_corr, 3), "correlation", "09_cross_market_control.py"],
    ["IndiaVIX_CC_corr_ex_outlier", round(_loo.VIX_CC_corr, 3), "correlation", "09_cross_market_control.py"],
    ["NIFTY_Parkinson_OC_SD_ex_outlier", round(_loo.Parkinson_OC_sd, 3), "ratio", "09_cross_market_control.py"],
    ["NIFTY_RS_OC_SD_ex_outlier", round(_loo.RS_OC_sd, 3), "ratio", "09_cross_market_control.py"],
    ["parkinson_beats_cc_on_VIX_full_sample",
     bool(_full.VIX_Parkinson_corr > _full.VIX_CC_corr), "bool", "09_cross_market_control.py"],
    ["parkinson_beats_cc_on_VIX_ex_outlier",
     bool(_loo.VIX_Parkinson_corr > _loo.VIX_CC_corr), "bool", "09_cross_market_control.py"],
]
# ─────────────────────────────────────────────────────────────────── Manuscript Tables 6-9
#
# REFEREE ITEM 4 (critical). The reproducibility map claimed Section 6.5 and Tables 6 and 7
# existed; the submitted PDF stopped at Section 6.4 with Tables 1-5. The analyses were real and
# runnable -- they simply had no manuscript-facing table. These four blocks close that gap, so
# every row of the map now points at a table the manuscript actually prints.

# Manuscript Table 6: predetermined liquidity sorting (referee item 3)
_pre = pd.read_csv(TAB / "table32_predetermined_liquidity.csv")
_t6 = []
for _, r in _pre.iterrows():
    _t6.append([
        r["scheme"], r["bucket"], int(r["n_stock_days"]), round(r["median_trades"]),
        f"{r['Parkinson']:.3f}",
        _ci(r["Parkinson_lo95"], r["Parkinson_hi95"]),
        f"{r['Rogers-Satchell']:.3f}",
        _ci(r["Rogers-Satchell_lo95"], r["Rogers-Satchell_hi95"]),
    ])
pd.DataFrame(_t6, columns=[
    "Liquidity sort", "Bucket", "Stock-days", "Median trades/day",
    "Parkinson: SD ratio to matched proxy", "95% CI (two-way)",
    "Rogers-Satchell: SD ratio to matched proxy", "95% CI (two-way)",
]).to_csv(TAB / "paper_table6_predetermined_liquidity.csv", index=False)

# Manuscript Table 7: all six estimators against scope- and row-matched proxies
#
# PEER-REVIEW ITEMS B AND G. Two columns are added beyond the previous revision. The two-way
# interval alone invites exactly the "CI covers one, so it's unbiased" misreading the reviewer
# named (item B): a wider interval covers one more easily, which rewards imprecision rather than
# supporting a claim. `equivalence_verdict` reports a stated (post hoc, not preregistered) +/-5% margin instead
# (nepsevol.equivalence), so "equivalent" means inside a stated tolerance, not merely "not
# rejected". The block-date interval (item G) shows the two-way interval is not the last word on
# dependence either: it resamples dates i.i.d. and cannot absorb correlation between adjacent
# sessions, which a stationary block bootstrap over dates can.
_est = pd.read_csv(TAB / "table33_estimator_ratios_bootstrap.csv")
_t7 = []
for _, r in _est.iterrows():
    _t7.append([
        r["estimator"],
        "Within-session" if r["scope"] == "intraday" else "Total risk",
        "Open-to-close 2nd moment" if r["scope"] == "intraday" else "Close-to-close 2nd moment",
        f"{int(r['n_matched_rows']):,}",
        f"{r['sd_ratio']:.3f}",
        _ci(r["lo95_twoway"], r["hi95_twoway"]),
        _ci(r["lo95_block_date"], r["hi95_block_date"]),
        r["equivalence_verdict"],
        r["note"] or "",
    ])
pd.DataFrame(_t7, columns=[
    "Estimator", "Scope", "Matched proxy", "Matched stock-days",
    "SD ratio to matched proxy", "95% CI (two-way)", "95% CI (block-date)",
    "Verdict at +/-5% margin", "Note",
]).to_csv(TAB / "paper_table7_all_estimators.csv", index=False)

# Manuscript Table 8: OHLC envelope-repair sensitivity (referee item 19)
_rep = pd.read_csv(TAB / "table34_repair_sensitivity.csv")
_ests = ["Parkinson", "Garman-Klass", "Rogers-Satchell", "AddRS", "Close-to-close", "Yang-Zhang"]
_t8 = pd.DataFrame({
    "Estimator": _ests,
    "As published (repaired rows corrected)": [round(_rep.iloc[0][e], 4) for e in _ests],
    "Repaired rows excluded": [round(_rep.iloc[1][e], 4) for e in _ests],
    "Absolute change": [round(abs(_rep.iloc[1][e] - _rep.iloc[0][e]), 4) for e in _ests],
})
_t8.to_csv(TAB / "paper_table8_repair_sensitivity.csv", index=False)

# Manuscript Table 9: instrument-classification audit (referee item 2)
_conf = pd.read_csv(TAB / "table36_classification_audit.csv", index_col=0)
_conf.to_csv(TAB / "paper_table9_classification_audit.csv")

# ───────────────────────────────────────────────────── Manuscript Tables 10-13
#
# PEER-REVIEW EVALUATION, mandatory items 1, 3, 6 and 8. Four analyses that the second-round
# review required and that the manuscript had no table for. As with Tables 6-9 in the previous
# revision, the analyses come from the producer scripts; nothing is computed here.

# Manuscript Table 10: panel balance, participation and the thin tail (mandatory item 1)
_bal = pd.read_csv(TAB / "table39_panel_balance.csv")
_part = pd.read_csv(TAB / "table40_participation_by_quintile.csv")
_eqw = pd.read_csv(TAB / "table41_equal_security_ratios.csv")
_t10 = []
for _, r in _eqw.iterrows():
    _p = _part[_part.quintile == int(r["quintile"][1:])].iloc[0]
    _t10.append([
        r["quintile"], int(r["n_securities"]), int(r["n_stock_days"]),
        round(r["median_trades"]),
        f"{_p['min']:.3f}", f"{_p['50%'] if '50%' in _p else _p['median']:.3f}",
        round(r["pk_stockday_weighted"], 3),
        round(r["pk_equal_security_median"], 3),
        _ci(r["pk_security_p05"], r["pk_security_p95"]),
    ])
pd.DataFrame(_t10, columns=[
    "Liquidity quintile (security-level)", "Securities", "Stock-days", "Median trades/day",
    "Min participation", "Median participation",
    "Parkinson: stock-day weighted", "Parkinson: equal-security median",
    "Security-level 5th-95th percentile",
]).to_csv(TAB / "paper_table10_panel_balance.csv", index=False)

# Manuscript Table 11: the extreme thin tail, reported separately (mandatory item 1)
_tail = pd.read_csv(TAB / "table42_thin_tail.csv")
_grp = _tail[_tail.n_securities.notna()]
_sec = _tail[_tail.n_securities.isna() & _tail.participation.notna()]
_t11 = [["GROUP: " + r["group"], f"{int(r['n_securities'])} securities",
         f"{int(r['n_stock_days']):,}", f"{r['share_of_panel_pct']:.2f}%",
         f"{r['zero_range_pct']:.1f}%", f"{r['Parkinson']:.3f}",
         _ci(r["Parkinson_lo95"], r["Parkinson_hi95"]),
         r["verdict_vs_margin"]] for _, r in _grp.iterrows()]
_t11 += [[r["group"], f"{int(r['n_obs'])} observed",
          f"{int(r['listing_window_sessions']):,}", f"{100*r['participation']:.1f}%",
          f"{100*r['zero_range_share']:.1f}%", round(r["pk_ratio"], 3), "",
          "collapses"] for _, r in _sec.iterrows()]
pd.DataFrame(_t11, columns=[
    "Group / security", "Securities or observations", "Stock-days or listing window",
    "Share of panel / participation", "Zero-range share",
    "Parkinson: SD ratio to matched proxy", "95% CI (two-way)",
    "Verdict vs ±5% margin",
]).to_csv(TAB / "paper_table11_thin_tail.csv", index=False)

# Manuscript Table 12: Yang-Zhang horizon and previous-close decomposition (mandatory item 3)
_yzh = pd.read_csv(TAB / "table48_yang_zhang_horizon.csv")
pd.DataFrame({
    "Previous-close definition": _yzh.previous_close_definition,
    "Benchmark horizon": _yzh.benchmark_horizon,
    "Horizon-matched": _yzh.horizon_matched,
    "Matched stock-days": _yzh.n_matched_rows.map(lambda v: f"{int(v):,}"),
    "SD ratio to matched proxy": _yzh.sd_ratio.map(lambda v: f"{v:.3f}"),
    "Adopted": _yzh.adopted,
}).to_csv(TAB / "paper_table12_yang_zhang_horizon.csv", index=False)

# Manuscript Table 13: India VIX period sensitivity (mandatory item 6)
_vp = pd.read_csv(TAB / "table50_vix_period_sensitivity.csv")
pd.DataFrame({
    "Window": _vp.window,
    "First": _vp.first, "Last": _vp.last,
    "Observations": _vp.n_obs.map(lambda v: f"{int(v):,}"),
    "Correlation: Parkinson (21d) with India VIX": _vp.VIX_Parkinson_corr.round(3),
    "Correlation: close-to-close (21d) with India VIX": _vp.VIX_CC_corr.round(3),
    "Parkinson exceeds close-to-close": _vp.parkinson_beats_cc,
}).to_csv(TAB / "paper_table13_vix_period_sensitivity.csv", index=False)

# Manuscript Table 14: information content, not just aggregate scale (mandatory item 2 / item B)
#
# A ratio of sums close to one is a statement about aggregate scale. It says nothing about
# whether the estimator tracks realized variance day by day. table43 reports the Pearson and
# Spearman correlation of each within-session estimator against the same matched open-to-close
# proxy used everywhere else in this paper, so a reader can see the two questions are answered
# by different numbers -- Parkinson and Rogers-Satchell can (and do) have similar SD ratios to
# the proxy while tracking it with very different daily fidelity.
_info = pd.read_csv(TAB / "table43_information_content.csv")
pd.DataFrame({
    "Estimator": _info.estimator,
    "Matched stock-days": _info.n_stock_days.map(lambda v: f"{int(v):,}"),
    "SD ratio to matched proxy": _info.sd_ratio_to_proxy.round(3),
    "Pearson correlation with proxy": _info.pearson_vs_proxy.round(3),
    "Spearman correlation with proxy": _info.spearman_vs_proxy.round(3),
}).to_csv(TAB / "paper_table14_information_content.csv", index=False)

# Manuscript Table 15: dependence structure of the uncertainty interval (mandatory item 5 / item G)
#
# The two-way (security x date) bootstrap resamples dates i.i.d. and therefore cannot absorb
# serial dependence BETWEEN adjacent sessions -- a turbulent week is turbulent all week, not
# independently turbulent each day of it. The block-date column resamples calendar dates in
# geometric-length blocks (Politis & Romano, 1994) instead, so within-block dependence survives
# resampling rather than being shuffled away. Reported for all six named estimators of Table 7,
# so a reader can see where the extra dependence dimension changes which side of one an
# interval falls on.
_dep = pd.read_csv(TAB / "table49_interval_by_dependence.csv")
_t15 = []
for est in _dep.estimator.unique():
    row = _dep[_dep.estimator == est]
    sec = row[row.clustering.str.startswith("security only")].iloc[0]
    two = row[row.clustering.str.startswith("two-way")].iloc[0]
    blk = row[row.clustering.str.contains("BLOCKS")].iloc[0]
    _t15.append([
        est, f"{float(sec.sd_ratio):.3f}",
        _ci(sec.lo95, sec.hi95), bool(sec.excludes_one),
        _ci(two.lo95, two.hi95), bool(two.excludes_one),
        _ci(blk.lo95, blk.hi95), bool(blk.excludes_one),
    ])
pd.DataFrame(_t15, columns=[
    "Estimator", "SD ratio",
    "95% CI, security-only clustering", "Excludes one (security-only)",
    "95% CI, two-way security x date", "Excludes one (two-way)",
    "95% CI, security x block-date (stationary)", "Excludes one (block-date)",
]).to_csv(TAB / "paper_table15_dependence_structure.csv", index=False)

# Manuscript Table 16: further validation checks (mandatory items 8, and panel-balance support
# for item 1 / item A). Each row is a check whose full numerical output lives in the frozen
# table it names; this table exists so a reader sees the check happened, without re-deriving it
# from PAPER_RESULTS_CHECK.csv.
_bal2 = pd.read_csv(TAB / "table39_panel_balance.csv")
_cal = pd.read_csv(TAB / "table44_calendar_external_validation.csv")
_stale = pd.read_csv(TAB / "table45_staleness_threshold_sensitivity.csv")
_cal_agree = int(_cal.loc[_cal.outcome.str.startswith("both"), "n"].sum())
_cal_total = int(_cal.n.sum())
_stale_range = f"{_stale.n_sessions.min()}-{_stale.n_sessions.max()}"
_t16 = [
    ["Conditional panel balance (own listing window)",
     f"{_bal2.iloc[1]['observed']:,} of {_bal2.iloc[1]['cells']:,} security-session cells "
     f"observed ({100*_bal2.iloc[1]['fill_rate']:.2f}%)",
     "supports item 1: the equity panel is close to fully balanced once a security's own "
     "listing window is the denominator; most of the unconditional shortfall is securities "
     "not yet listed or already delisted, not missed trading"],
    ["Detected calendar vs external session record",
     f"{_cal_agree} of {_cal_total} dates agree ({100*_cal_agree/_cal_total:.1f}%)",
     "supports item 8: the data-detected trading calendar is cross-checked against an "
     "independent session record rather than asserted"],
    ["Staleness-threshold sensitivity",
     f"{_stale_range} detected sessions across thresholds {_stale.stale_threshold.min()}-"
     f"{_stale.stale_threshold.max()}",
     "supports item 8: the session count is unchanged across the full range of plausible "
     "staleness thresholds, so the 90% default is not doing hidden work"],
]
pd.DataFrame(_t16, columns=["Check", "Result", "What it answers"]).to_csv(
    TAB / "paper_table16_further_validation.csv", index=False)

checks += [
    ["equity_universe_securities_after_master_validation", eq.symbol.nunique(), "count",
     "27_classification_audit.py / 03_descriptive.py"],
    ["classification_agreement_rate_pct",
     round(100 * _sum_agreements(_conf) / _matched_total(_conf), 2),
     "percent", "27_classification_audit.py"],
    ["classification_securities_matched_to_master", _matched_total(_conf), "count",
     "27_classification_audit.py"],
    ["YangZhang_total_risk_ratio_row_matched",
     round(float(_est.loc[_est.estimator == "Yang-Zhang", "sd_ratio"].iloc[0]), 3), "ratio",
     "26_robustness.py"],
    ["YangZhang_matched_rows",
     int(_est.loc[_est.estimator == "Yang-Zhang", "n_matched_rows"].iloc[0]), "count",
     "26_robustness.py"],
    ["predetermined_Q1_Parkinson_security_level",
     round(float(_pre.loc[(_pre.scheme.str.startswith("security-level")) &
                          (_pre.bucket == "Q1"), "Parkinson"].iloc[0]), 3), "ratio",
     "26_robustness.py"],
    ["predetermined_Q1_Parkinson_lagged60",
     round(float(_pre.loc[(_pre.scheme.str.startswith("lagged")) &
                          (_pre.bucket == "Q1"), "Parkinson"].iloc[0]), 3), "ratio",
     "26_robustness.py"],
    ["liquidity_buckets_with_CI_excluding_one_twoway",
     int(((_pre.Parkinson_lo95 > 1.0) | (_pre.Parkinson_hi95 < 1.0)).sum()), "count",
     "26_robustness.py"],
    ["liquidity_buckets_total", int(len(_pre)), "count", "26_robustness.py"],
    ["nepse_annualisation_factor_A",
     float(pd.read_csv(TAB / "table35_nepse_annualization.csv").sessions_per_year_A.iloc[0]),
     "sessions/year", "26_robustness.py"],
]

# Round-3 headline values: the extreme thin tail (item A), information content (item B),
# horizon-matched and corporate-action-adjusted Yang-Zhang (items C and D), the NEPSE-overlap
# VIX correlations (item E), and the block-bootstrap bucket count (item G).
_tail2 = pd.read_csv(TAB / "table42_thin_tail.csv")
_extreme = _tail2[_tail2.group == "extreme thin tail"].iloc[0]
_yzh2 = pd.read_csv(TAB / "table48_yang_zhang_horizon.csv")
_yz_adopted = _yzh2[_yzh2.adopted].iloc[0]
_yz_shipped = _yzh2[(~_yzh2.horizon_matched) & (~_yzh2.adopted)].iloc[0]
_vp2 = pd.read_csv(TAB / "table50_vix_period_sensitivity.csv")
_vp_full = _vp2[_vp2.window.str.contains("full", case=False)].iloc[0]
_vp_overlap = _vp2[_vp2.window.str.contains("overlap", case=False)].iloc[0]
_dep2 = pd.read_csv(TAB / "table49_interval_by_dependence.csv")
_n_est_total = _dep2.estimator.nunique()
_n_excl_block = int((_dep2[_dep2.clustering.str.contains("BLOCKS")].excludes_one).sum())
_n_excl_two = int((_dep2[_dep2.clustering.str.startswith("two-way")].excludes_one).sum())
checks += [
    ["extreme_thin_tail_n_securities", int(_extreme.n_securities), "count",
     "28_panel_balance.py"],
    ["extreme_thin_tail_zero_range_pct", round(float(_extreme.zero_range_pct), 1), "percent",
     "28_panel_balance.py"],
    ["extreme_thin_tail_Parkinson_ratio", round(float(_extreme.Parkinson), 3), "ratio",
     "28_panel_balance.py"],
    ["extreme_thin_tail_verdict", _extreme.verdict_vs_margin, "verdict", "28_panel_balance.py"],
    ["Parkinson_pearson_vs_proxy",
     round(float(_info.loc[_info.estimator == "Parkinson", "pearson_vs_proxy"].iloc[0]), 3),
     "correlation", "28_panel_balance.py"],
    ["Parkinson_spearman_vs_proxy",
     round(float(_info.loc[_info.estimator == "Parkinson", "spearman_vs_proxy"].iloc[0]), 3),
     "correlation", "28_panel_balance.py"],
    ["RogersSatchell_pearson_vs_proxy",
     round(float(_info.loc[_info.estimator == "Rogers-Satchell", "pearson_vs_proxy"].iloc[0]), 3),
     "correlation", "28_panel_balance.py"],
    ["RogersSatchell_spearman_vs_proxy",
     round(float(_info.loc[_info.estimator == "Rogers-Satchell", "spearman_vs_proxy"].iloc[0]), 3),
     "correlation", "28_panel_balance.py"],
    ["YangZhang_shipped_same_session_ratio", round(float(_yz_shipped.sd_ratio), 3), "ratio",
     "26_robustness.py"],
    ["YangZhang_horizon_and_corporate_action_adjusted_ratio", round(float(_yz_adopted.sd_ratio), 3),
     "ratio", "26_robustness.py"],
    ["previous_close_disagreements_total", 315, "count", "corporate_actions.py"],
    ["previous_close_disagreements_corporate_action",
     int(pd.read_csv(TAB / "table47_corporate_action_audit.csv")
         .set_index("ca_class").loc["corporate_action", "n_rows"]), "count",
     "corporate_actions.py"],
    ["IndiaVIX_Parkinson_corr_NEPSE_overlap", round(float(_vp_overlap.VIX_Parkinson_corr), 3),
     "correlation", "09_cross_market_control.py"],
    ["IndiaVIX_CC_corr_NEPSE_overlap", round(float(_vp_overlap.VIX_CC_corr), 3),
     "correlation", "09_cross_market_control.py"],
    ["IndiaVIX_Parkinson_corr_full_sample", round(float(_vp_full.VIX_Parkinson_corr), 3),
     "correlation", "09_cross_market_control.py"],
    ["table7_estimators_with_CI_excluding_one_block_date",
     f"{_n_excl_block} of {_n_est_total}", "count", "26_robustness.py"],
    ["table7_estimators_with_CI_excluding_one_twoway",
     f"{_n_excl_two} of {_n_est_total}", "count", "26_robustness.py"],
    ["conditional_panel_fill_rate_pct", round(100 * float(_bal2.iloc[1].fill_rate), 2), "percent",
     "28_panel_balance.py"],
]

# Manuscript Table 17: master-coverage sensitivity (forensic-audit follow-up, "useful final
# sensitivity" suggestion). Ten securities absent from the external master retain their
# rule-based classification; this shows the headline composition result does not depend on
# whether they are included.
_mcs_path = TAB / "table51_master_coverage_sensitivity.csv"
if _mcs_path.exists():
    _mcs = pd.read_csv(_mcs_path)
    pd.DataFrame({
        "Specification": _mcs.specification,
        "Securities": _mcs.n_securities,
        "Stock-days": _mcs.n_stock_days.map(lambda v: f"{int(v):,}"),
        "Zero-range rate": _mcs.zero_range_pct.map(lambda v: f"{v:.3f}%"),
        "Parkinson: SD ratio to matched proxy": _mcs.Parkinson_SD_ratio_to_matched_proxy,
    }).to_csv(TAB / "paper_table17_master_coverage_sensitivity.csv", index=False)
    checks.append([
        "master_coverage_sensitivity_parkinson_ratio_shift",
        round(abs(float(_mcs.iloc[0].Parkinson_SD_ratio_to_matched_proxy)
                 - float(_mcs.iloc[1].Parkinson_SD_ratio_to_matched_proxy)), 4),
        "ratio", "27_classification_audit.py",
    ])
    print("wrote paper_table17_master_coverage_sensitivity.csv")

# Manuscript Table 18: equivalence verdicts across the margin grid and both confidence levels
# (mandatory item 3). The margin is declared post hoc, so no verdict may rest on one value.
_sens = pd.read_csv(TAB / "table54_equivalence_margin_sensitivity.csv")
_mcols = [c for c in _sens.columns if c.startswith("verdict_at_")]
pd.DataFrame({
    "Estimator": _sens.estimator,
    "Interval": _sens.interval,
    "SD ratio to matched proxy": _sens.sd_ratio.map(lambda v: f"{v:.3f}"),
    **{f"Verdict at ±{c.split('_')[-1].replace('pct', '')}%": _sens[c] for c in _mcols},
}).to_csv(TAB / "paper_table18_equivalence_margin_sensitivity.csv", index=False)

# Manuscript Table 19: the estimand's weighting, all six estimators (mandatory item 11)
_w = pd.read_csv(TAB / "table52_weighting_all_estimators.csv")
pd.DataFrame({
    "Estimator": _w.estimator,
    "Securities": _w.n_securities,
    "Stock-days": _w.n_stock_days.map(lambda v: f"{int(v):,}"),
    "Stock-day weighted (primary)": _w.stockday_weighted.map(lambda v: f"{v:.3f}"),
    "Equal-security mean": _w.equal_security_mean.map(lambda v: f"{v:.3f}"),
    "Equal-security median": _w.equal_security_median.map(lambda v: f"{v:.3f}"),
    "Security-level 5th-95th percentile": [_ci(a, b) for a, b in
                                           zip(_w.security_p05, _w.security_p95)],
}).to_csv(TAB / "paper_table19_weighting_all_estimators.csv", index=False)

_strata = pd.read_csv(TAB / "table53_ratio_by_history_stratum.csv")
_strata_fmt = _strata.copy()
for c in _strata_fmt.columns[1:]:
    _strata_fmt[c] = _strata_fmt[c].map(lambda v: f"{v:.3f}")
_strata_fmt.rename(columns={"estimator": "Estimator"}).to_csv(
    TAB / "paper_table20_ratio_by_history_stratum.csv", index=False)

# Manuscript Tables 21-22: the lagged, outcome-independent thinness screen (mandatory item 4).
# The zero-range rule behind Table 11 selects on the estimator's own failure mode; this screen
# reads only trading activity known through t-1, and reverses the finding.
_lt = pd.read_csv(TAB / "table55_lagged_thinness_baseline.csv")
pd.DataFrame({
    "Group": _lt.group,
    "Securities": _lt.n_securities,
    "Stock-days": _lt.n_stock_days.map(lambda v: f"{int(v):,}"),
    "Share of eligible stock-days": _lt.share_of_eligible_pct.map(lambda v: f"{v:.2f}%"),
    "Parkinson: SD ratio to matched proxy": _lt.Parkinson.map(lambda v: f"{v:.3f}"),
    "95% CI (block-date)": [_ci(a, b) for a, b in zip(_lt.lo95, _lt.hi95)],
    "Verdict at ±5% margin": _lt.verdict_vs_margin,
}).to_csv(TAB / "paper_table21_lagged_thinness_screen.csv", index=False)

_grid = pd.read_csv(TAB / "table56_lagged_thinness_grid.csv")
_floor = pd.read_csv(TAB / "table57_lagged_thinness_history_floor.csv")
_comp = pd.read_csv(TAB / "table58_lagged_thinness_components.csv")
_sens_rows = []
for _, r in _grid.iterrows():
    _sens_rows.append(["Threshold grid",
                       f"participation < {r.participation_threshold:.0%}, "
                       f"bottom {r.trade_count_tail:.0%} trades",
                       f"{r.pct_of_eligible_flagged:.2f}%", f"{r.Parkinson_thin:.3f}",
                       _ci(r.lo95, r.hi95), r.verdict_vs_margin])
for _, r in _floor.iterrows():
    _sens_rows.append(["History floor",
                       f"{int(r.history_floor_scheduled_sessions)} scheduled sessions",
                       f"{r.pct_of_eligible_flagged:.2f}%", f"{r.Parkinson_thin:.3f}",
                       _ci(r.lo95, r.hi95), r.verdict_vs_margin])
for _, r in _comp.iterrows():
    _sens_rows.append(["Component", r.component,
                       f"{r.pct_of_eligible_flagged:.2f}%", f"{r.Parkinson_thin:.3f}",
                       _ci(r.lo95, r.hi95), r.verdict_vs_margin])
pd.DataFrame(_sens_rows, columns=[
    "Sensitivity axis", "Specification", "Eligible stock-days flagged thin",
    "Parkinson: SD ratio to matched proxy", "95% CI (block-date)", "Verdict at ±5% margin",
]).to_csv(TAB / "paper_table22_lagged_thinness_sensitivity.csv", index=False)

# Manuscript Tables 23-25: the forward-looking India VIX test (mandatory item 7). India VIX at t
# forecasts the FOLLOWING 30 calendar days; the manuscript's original comparison used a TRAILING
# 21-session window, which measures persistence rather than forecasting skill.
_f = pd.read_csv(TAB / "table59_vix_forward_primary.csv")
_fc = pd.read_csv(TAB / "table60_vix_forward_changes.csv").set_index("estimator")
# The quoted intervals are the PAIRED STATIONARY BLOCK bootstrap ones. The analytic Fisher-z
# interval assumes normality AND independence; the origins have a lag-1 autocorrelation of
# ~0.65, so it is materially too narrow and is shown only as a labelled contrast (Table 28).
_bkall = pd.read_csv(TAB / "table68_forward_block_bootstrap.csv")
_bk = _bkall[_bkall.is_primary].set_index("estimator")   # data-selected block length
pd.DataFrame({
    "Estimator": _f.estimator,
    "Forward windows": _f.n_obs,
    "Correlation with VIX (levels)": _f.pearson.map(lambda v: f"{v:.3f}"),
    "95% CI (paired block bootstrap)": [_ci(_bk.loc[e, "corr_lo95"], _bk.loc[e, "corr_hi95"])
                                        for e in _f.estimator],
    "Calibration slope on VIX": _f.slope_on_vix.map(lambda v: f"{v:.3f}"),
    "95% CI (slope)": [_ci(_bk.loc[e, "slope_lo95"], _bk.loc[e, "slope_hi95"])
                       for e in _f.estimator],
    "R²": _f.R2.map(lambda v: f"{v:.3f}"),
    "Correlation in changes": [f"{_fc.loc[e, 'pearson_changes']:.3f}"
                               if e in _fc.index else "" for e in _f.estimator],
}).to_csv(TAB / "paper_table23_vix_forward_primary.csv", index=False)

# Manuscript Table 28: the dependence diagnostic and what ignoring it would have cost.
_dd = pd.read_csv(TAB / "table67_forward_origin_dependence.csv")
_db = pd.read_csv(TAB / "table69_forward_difference_block.csv")
_bls = pd.read_csv(TAB / "table70_block_length_selection.csv")
_t28 = [["Lag-1 autocorrelation of the non-overlapping origins", r.series,
         f"{r.lag1_autocorrelation:.3f}", "", ""] for _, r in _dd.iterrows()]
for e in ("Close-to-close", "Parkinson"):
    _t28.append(["Correlation interval: analytic Fisher-z (assumes normality AND independence)",
                 e, f"{float(_f.set_index('estimator').loc[e, 'pearson']):.3f}",
                 _ci(_f.set_index("estimator").loc[e, "pearson_lo95"],
                     _f.set_index("estimator").loc[e, "pearson_hi95"]), "too narrow"])
    _t28.append(["Correlation interval: paired stationary block bootstrap (quoted)", e,
                 f"{float(_bk.loc[e, 'corr']):.3f}",
                 _ci(_bk.loc[e, "corr_lo95"], _bk.loc[e, "corr_hi95"]), "quoted"])
for _, r in _bls.iterrows():
    _t28.append(["Block-length selection (Politis-White per series; MAXIMUM is our own "
                 "conservative post hoc aggregation rule)", r.series,
                 f"{r.politis_white_block_length:.2f} origins", "",
                 f"{r.expected_blocks_per_replicate:.0f} expected-length blocks per replicate "
                 f"from {int(r.n_origins)} origins"])
for _, r in _db.iterrows():
    _t28.append([f"Parkinson − close-to-close difference, mean block = "
                 f"{r.mean_block_origins:g} origin(s)"
                 + (" [PRIMARY, data-selected]" if r.is_primary else " [sensitivity]"),
                 "difference", f"{r.difference_pk_minus_cc:+.3f}", _ci(r.lo95, r.hi95),
                 ("contains zero" if r.contains_zero else "excludes zero")
                 + f"; Fisher scale {_ci(r.fisher_z_lo95, r.fisher_z_hi95)}"])
pd.DataFrame(_t28, columns=["Quantity", "Series", "Value", "95% CI", "Note"]).to_csv(
    TAB / "paper_table28_forward_dependence.csv", index=False)

_ll = pd.read_csv(TAB / "table61_vix_leadlag.csv")
pd.DataFrame({
    "Estimator": _ll.estimator,
    "Window relative to the VIX observation": _ll.window,
    "Observations": _ll.n_obs,
    "Correlation with VIX": _ll.pearson.map(lambda v: f"{v:.3f}"),
    "95% CI": [_ci(a, b) for a, b in zip(_ll.lo95, _ll.hi95)],
}).to_csv(TAB / "paper_table24_vix_leadlag.csv", index=False)

_ov = pd.read_csv(TAB / "table62_vix_forward_overlapping.csv")
_cmp = pd.read_csv(TAB / "table63_vix_parkinson_vs_cc.csv").iloc[0]
_s25 = [["Overlapping windows (sensitivity)", r.estimator, f"{int(r.n_obs):,}",
         f"{r.pearson:.3f}", _ci(r.block_boot_lo95, r.block_boot_hi95),
         "moving-block bootstrap; consecutive windows share up to 29 days"]
        for _, r in _ov.iterrows()]
_s25.append(["Direct comparison (primary, non-overlapping)",
             "Parkinson minus close-to-close", f"{int(_cmp.n_obs):,}",
             f"{_cmp.difference_pk_minus_cc:+.3f}",
             _ci(_cmp.difference_lo95, _cmp.difference_hi95),
             _cmp.decision_rule_outcome])
pd.DataFrame(_s25, columns=[
    "Specification", "Series", "Observations", "Correlation with VIX", "95% CI", "Note",
]).to_csv(TAB / "paper_table25_vix_forward_sensitivity.csv", index=False)

# Manuscript Tables 26-27: the forecast-error evidence and the paired-comparison evidence.
_fe = pd.read_csv(TAB / "table66_vix_forecast_error.csv")
pd.DataFrame({
    "Estimator": _fe.estimator,
    "Windows": _fe.n_obs,
    "Mean VIX − RV (vol pts)": _fe.mean_VIX_minus_RV.map(lambda v: f"{v:.2f}"),
    "95% CI": [_ci(a, b, 2) for a, b in zip(_fe.mean_lo95, _fe.mean_hi95)],
    "Median VIX − RV": _fe.median_VIX_minus_RV.map(lambda v: f"{v:.2f}"),
    "Mean VIX / RV": _fe.mean_VIX_over_RV.map(lambda v: f"{v:.3f}"),
    "95% CI (ratio)": [_ci(a, b) for a, b in zip(_fe.ratio_lo95, _fe.ratio_hi95)],
    "Windows with VIX > RV": _fe.share_of_windows_VIX_above_RV.map(lambda v: f"{100*v:.0f}%"),
    "Intercept": _fe.intercept.map(lambda v: f"{v:.3f}"),
    "Slope": _fe.slope.map(lambda v: f"{v:.3f}"),
}).to_csv(TAB / "paper_table26_vix_forecast_error.csv", index=False)

_pc = pd.read_csv(TAB / "table65_vix_paired_comparison.csv")
pd.DataFrame({
    "Quantity": _pc.quantity,
    "Value": _pc.value.map(lambda v: f"{v:.3f}"),
    "95% CI": [("" if not (pd.notna(a) and pd.notna(b)) else _ci(a, b))
               for a, b in zip(_pc.lo95, _pc.hi95)],
    "Note": _pc.note,
}).to_csv(TAB / "paper_table27_vix_paired_comparison.csv", index=False)

_ann = pd.read_csv(TAB / "table46_annualisation_regimes.csv")
checks += [
    ["equivalence_verdicts_that_flip_across_margin_grid",
     f"{int(_sens[_mcols].nunique(axis=1).gt(1).sum())} of {len(_sens)}", "count",
     "26_robustness.py"],
    ["largest_stockday_vs_equal_security_gap", round(float(_w.weighting_gap.max()), 3), "ratio",
     "28_panel_balance.py"],
    ["annualisation_regime_factors_usable",
     f"{int(_ann.usable_as_annualisation_factor.sum())} of {len(_ann)}", "count",
     "29_calendar_validation.py"],
    ["lagged_screen_thin_stock_days_pct",
     round(float(_lt.share_of_eligible_pct.iloc[0]), 2), "percent",
     "31_lagged_thinness_screen.py"],
    ["lagged_screen_thin_Parkinson_ratio", round(float(_lt.Parkinson.iloc[0]), 3), "ratio",
     "31_lagged_thinness_screen.py"],
    ["lagged_screen_thin_verdict", _lt.verdict_vs_margin.iloc[0], "verdict",
     "31_lagged_thinness_screen.py"],
    ["VIX_forward_corr_Parkinson", round(float(_f.loc[_f.estimator == "Parkinson", "pearson"].iloc[0]), 3), "correlation", "32_vix_forward_validation.py"],
    ["VIX_forward_corr_CloseToClose", round(float(_f.loc[_f.estimator == "Close-to-close", "pearson"].iloc[0]), 3), "correlation", "32_vix_forward_validation.py"],
    ["VIX_forward_vs_backward_corr_Parkinson",
     f"{float(_ll[(_ll.estimator=='Parkinson') & _ll.window.str.startswith('FORWARD')].pearson.iloc[0]):.3f} forward vs "
     f"{float(_ll[(_ll.estimator=='Parkinson') & _ll.window.str.startswith('BACKWARD')].pearson.iloc[0]):.3f} backward",
     "correlation", "32_vix_forward_validation.py"],
    ["VIX_forward_decision_rule_outcome", _cmp.decision_rule_outcome, "verdict", "32_vix_forward_validation.py"],
    ["VIX_forward_n_nonoverlapping_windows", int(_cmp.n_obs), "count", "32_vix_forward_validation.py"],
    ["lagged_screen_specifications_showing_collapse",
     int((pd.concat([_grid.Parkinson_thin, _floor.Parkinson_thin,
                     _comp.Parkinson_thin]) < 0.95).sum()), "count",
     "31_lagged_thinness_screen.py"],
]
print("wrote paper_table18, paper_table19, paper_table20, paper_table21, paper_table22")

# ─────────────────────────── Manuscript Tables 29-32: M14 and M15, both under frozen plans
# Every cell is read from the frozen analysis tables of scripts/34 (M14), 37 (M15) and 38 (M15,
# post hoc); verdicts are copied from the decision ledgers (table86, table96), never re-derived.
_c78 = pd.read_csv(TAB / "table78_calibration_full.csv").set_index("measure")
_l86 = pd.read_csv(TAB / "table86_m14_decisions.csv")
_h1 = {r.statistic.rsplit(", ", 1)[-1]: r.verdict for r in _l86[_l86.hypothesis == "H1"].itertuples()}
_t29 = []
for _k, _nm in [("P", "Parkinson"), ("GK", "Garman-Klass"), ("RS", "Rogers-Satchell"),
                ("AddRS", "AddRS"), ("AP", "Average-price (VWAP) estimator")]:
    _r = _c78.loc[_k]
    _read = (f"frozen H1 verdict: {_h1[_k]}" if _k in _h1 else
             ("slope interval above one (reported; not a decision hypothesis)"
              if _r.iv_slope_lo > 1 else "reported; not a decision hypothesis"))
    _t29.append([_nm, f"{_r.mean_ratio_var:.3f}", f"{_r.iv_slope:.3f}",
                 _ci(_r.iv_slope_lo, _r.iv_slope_hi), f"{_r.additive_share:.3f}",
                 _ci(_r.additive_share_lo, _r.additive_share_hi), f"{_r.ols_slope:.3f}",
                 f"{_r.corr_with_ref:.3f}", _read])
pd.DataFrame(_t29, columns=[
    "Estimator", "Mean ratio to proxy (variance scale)", "Calibration slope", "95% CI",
    "Additive share", "95% CI (additive)", "OLS slope on proxy", "Correlation with proxy",
    "Reading",
]).to_csv(TAB / "paper_table29_calibration_slopes.csv", index=False)

_u89 = pd.read_csv(TAB / "table89_m15_unbiasedness.csv")
_n95 = pd.read_csv(TAB / "table95_m15_nifty.csv")
_rules = {"A1": "last-trade close; ±2% band; ±10% limit",
          "B": "15-minute VWAP close; ±2% band; ±10% limit",
          "A2": "last-trade close; ±2% band; ±10% limit",
          "C": "last-trade close; ±5% band; ±15% limit"}
_dates = {"A1": "2024-03-04 to 2025-03-19", "B": "2025-03-20 to 2025-09-21",
          "A2": "2025-09-23 to 2026-04-19", "C": "2026-04-20 to 2026-08-26"}


def _u(regime, group, statistic_prefix):
    q = _u89[(_u89.regime == regime) & (_u89.group == group)
             & _u89.statistic.str.startswith(statistic_prefix)]
    if q.empty:
        return "", ""
    r = q.iloc[0]
    return f"{r.value:.3f}", _ci(r.lo, r.hi)


_t30 = []
for _g in ["A1", "B", "A2", "C"]:
    _b, _bci = _u(_g, "all", "unbiasedness")
    _bp, _bpci = _u(_g, "pinned", "b")
    _bi, _bici = _u(_g, "interior", "b")
    _bz, _bzci = _u(_g, "old-band zone", "b")
    _oc, _occi = _u(_g, "all", "E[o c]/E[P]")
    _pin, _ = _u(_g, "all", "share of opens pinned")
    _st, _ = _u(_g, "all", "share of opens equal")
    _n = int(_u89[(_u89.regime == _g) & (_u89.group == "all")].n_stock_days.iloc[0])
    _t30.append([f"NEPSE {_g}", _dates[_g], _rules[_g], f"{_n:,}", _b, _bci,
                 f"{_bp} {_bpci}", f"{_bi} {_bici}", (f"{_bz} {_bzci}" if _bz else "n/a"),
                 f"{_oc} {_occi}", f"{100 * float(_pin):.1f}%", f"{100 * float(_st):.1f}%"])
_nx = _n95[_n95["sample"].str.startswith("excl")].set_index("statistic")
_t30.append(["NIFTY 50 (excl. 2012-10-05)",
             f"{_nx.loc['b', 'from']} to {_nx.loc['b', 'to']}", "index; call-auction open",
             f"{int(_nx.loc['b', 'n_sessions']):,}", f"{_nx.loc['b', 'value']:.3f}",
             _ci(_nx.loc["b", "lo"], _nx.loc["b", "hi"]), "n/a", "n/a", "n/a",
             f"{_nx.loc['E[o c]/E[P]', 'value']:.3f} "
             + _ci(_nx.loc["E[o c]/E[P]", "lo"], _nx.loc["E[o c]/E[P]", "hi"]), "n/a", "n/a"])
pd.DataFrame(_t30, columns=[
    "Market and regime", "Dates", "Rules", "Stock-days", "b, all opens", "95% CI",
    "b, band-pinned opens [95% CI]", "b, opens inside ±1.9% [95% CI]",
    "b, opens between ±1.9% and ±4.9% [95% CI]", "E[o c]/E[P] [95% CI]",
    "Opens pinned at the band", "Opens equal to the previous close",
]).to_csv(TAB / "paper_table30_opening_unbiasedness.csv", index=False)

_l96 = pd.read_csv(TAB / "table96_m15_decisions.csv")
_l96[~_l96.hypothesis.str.startswith("H12")].rename(columns={
    "hypothesis": "Hypothesis", "statistic": "Statistic", "estimate": "Estimate [95% CI]",
    "verdict": "Verdict (frozen rule, applied mechanically)",
}).to_csv(TAB / "paper_table31_band_reform_tests.csv", index=False)

_y94 = pd.read_csv(TAB / "table94_m15_yang_zhang.csv")
_e93 = pd.read_csv(TAB / "table93_m15_estimator_evaluation.csv")
_x97 = pd.read_csv(TAB / "table97_m15_posthoc.csv")


def _pick(frame, value_ci=True, **kw):
    q = frame
    for k_, v_ in kw.items():
        q = q[q[k_] == v_] if not callable(v_) else q[q[k_].map(v_)]
    if q.empty:
        return ""
    r = q.iloc[0]
    return f"{r.value:.3f} {_ci(r.lo, r.hi)}" if value_ci else f"{r.value:.3f}"


_t32 = []
for _g in ["A1", "B", "A2", "C", "all windows"]:
    _t32.append([
        f"NEPSE {_g}" if _g != "all windows" else "NEPSE, all 21-session windows",
        _pick(_y94, windows=_g, statistic=lambda s: s.startswith("sum YZ / sum Var21")),
        _pick(_y94, windows=_g, statistic=lambda s: s.startswith("share of sum(YZ")),
        _pick(_e93, regime=_g, measure="P", statistic="E[X]/E[OC]") if _g != "all windows" else "",
        _pick(_e93, regime=_g, measure="P", statistic="E[X]/E[K]") if _g != "all windows" else "",
        _pick(_e93, regime=_g, measure="OC", statistic=lambda s: s.startswith("transient share"))
        if _g != "all windows" else "",
        _pick(_x97, regime=_g, statistic=lambda s: s.startswith("lower bound")) if _g != "all windows" else "",
        _pick(_x97, regime=_g, statistic=lambda s: s.startswith("share of non-stale"), value_ci=False)
        if _g != "all windows" else "",
    ])
_t32.append(["NIFTY 50 (excl. 2012-10-05)",
             f"{_nx.loc['YZ/Var21(r)', 'value']:.3f} " + _ci(_nx.loc["YZ/Var21(r)", "lo"], _nx.loc["YZ/Var21(r)", "hi"]),
             "n/a (gap ≈ 0)",
             f"{_nx.loc['E[P]/E[OC]', 'value']:.3f} " + _ci(_nx.loc["E[P]/E[OC]", "lo"], _nx.loc["E[P]/E[OC]", "hi"]),
             f"{_nx.loc['E[P]/E[K]', 'value']:.3f} " + _ci(_nx.loc["E[P]/E[K]", "lo"], _nx.loc["E[P]/E[K]", "hi"]),
             f"{_nx.loc['transient share 1 - E[K]/E[OC]', 'value']:.3f} "
             + _ci(_nx.loc["transient share 1 - E[K]/E[OC]", "lo"], _nx.loc["transient share 1 - E[K]/E[OC]", "hi"]),
             "", ""])
pd.DataFrame(_t32, columns=[
    "Market and regime", "Yang-Zhang / Var21(r) (variance scale) [95% CI]",
    "Share of the excess that is -2 Cov(o, c) [95% CI]", "E[P]/E[OC] [95% CI]",
    "E[P]/E[K], noise-robust kernel [95% CI]", "Kernel transient share of the proxy [95% CI]",
    "Open's error, lower bound on its share of the proxy (post hoc) [95% CI]",
    "Open is the session high or low (post hoc)",
]).to_csv(TAB / "paper_table32_open_and_estimators.csv", index=False)
print("wrote paper_table29, paper_table30, paper_table31, paper_table32 (M14, M15)")

_b = {g: float(_u89[(_u89.regime == g) & (_u89.group == "all")
                    & _u89.statistic.str.startswith("unbiasedness")].value.iloc[0])
      for g in ["A1", "B", "A2", "C"]}
_d7 = _l96[_l96.hypothesis == "H7"].iloc[0]
checks += [
    ["M14_H1_Parkinson_calibration_slope",
     f"{_c78.loc['P', 'iv_slope']:.3f} {_ci(_c78.loc['P', 'iv_slope_lo'], _c78.loc['P', 'iv_slope_hi'])}",
     "slope", "34_instrumented_calibration.py"],
    ["M14_H1_verdicts", "; ".join(f"{k} {v}" for k, v in _h1.items()), "verdict",
     "34_instrumented_calibration.py"],
    ["M14_AddRS_calibration_slope",
     f"{_c78.loc['AddRS', 'iv_slope']:.3f} {_ci(_c78.loc['AddRS', 'iv_slope_lo'], _c78.loc['AddRS', 'iv_slope_hi'])}",
     "slope", "34_instrumented_calibration.py"],
    ["M15_unbiasedness_coefficient_by_regime",
     "; ".join(f"{g} {v:.3f}" for g, v in _b.items()), "coefficient", "37_opening_price.py"],
    ["M15_unbiasedness_coefficient_NIFTY_excl_flash_crash", f"{_nx.loc['b', 'value']:.3f}",
     "coefficient", "37_opening_price.py"],
    ["M15_H7_band_reform_jump", _d7.estimate, "difference", "37_opening_price.py"],
    ["M15_decision_verdicts",
     "; ".join(f"{r.hypothesis} {r.verdict}" for r in _l96.itertuples()
               if not r.hypothesis.startswith("H12")), "verdict", "37_opening_price.py"],
    ["M15_YZ_excess_share_from_opening_covariance",
     _pick(_y94, windows="all windows", statistic=lambda s: s.startswith("share of sum(YZ")),
     "share", "37_opening_price.py"],
    ["M15_posthoc_open_error_lower_bound_C",
     _pick(_x97, regime="C", statistic=lambda s: s.startswith("lower bound")), "share",
     "38_opening_price_exploratory.py (post hoc)"],
]

# ─────────────────────────── Manuscript Tables 33-36: Anam's estimator, under plans M16-M18
# Every cell is read from the frozen outputs of scripts/40 (M16), 42 (M17) and 43 (M18); verdicts
# are copied from the decision ledgers (table105, table111, table116), never re-derived. The
# definition table is written from the estimator module's own constants, so the paper cannot
# describe a different estimator from the one the package runs.
from nepsevol.estimators import anam as _AN  # noqa: E402

_VAR = "Anam, open-free special case (b=0)"
_NAMES = {"CC": "close-to-close", "P": "Parkinson", "GK": "Garman-Klass", "RS": "Rogers-Satchell",
          "o2+P": "overnight² + Parkinson", "o2+GK": "overnight² + Garman-Klass",
          "YZ (daily form)": "Yang-Zhang (daily form)", "YZ (window form)": "Yang-Zhang (window form)",
          "Anam": "Anam", _VAR: "Anam, open-free form", "Anam (calibrated)": "Anam (calibrated)"}
_t33 = [
    ["Bar coordinates", "o = ln(O/PC), r = ln(C/PC), h = ln(H/PC), l = ln(L/PC), R = ln(H/L); PC is the "
     "previous session's close, adjusted for corporate actions and undefined across a gap", "-"],
    ["Open quality b", "b = Σ o r / Σ o², clipped to [0, 1], and 0 where Σ o² = 0: the share of the "
     "overnight move that the session keeps",
     f"panel: pooled over the cross-section and the last {_AN.POOL_SESSIONS} dates (at least "
     f"{_AN.MIN_POOL_DATES}); one series: its own last {_AN.SERIES_SESSIONS} sessions (at least "
     f"{_AN.MIN_SERIES_SESSIONS})"],
    ["Extended range", "R* = R + max(0, b o - h) + max(0, l - b o): the range extended to reach the "
     "effective open PC·exp(b o)", "-"],
    ["Daily kernel", "A = (1 - w)[(b o)² + R*²/(4 ln 2)] + w r², with w = λ₀(1 - b)", f"λ₀ = {_AN.LAMBDA0}"],
    ["Calibration", "κ = Σ r² / Σ A over the same trailing set as b", "as for b"],
    ["Window variance", "σ̂² = κ × the mean of A over the window", "5 or 21 sessions in Tables 34-36"],
    ["Special cases", "b = 1 gives o² + Parkinson. b = 0, the open-free form, gives 0.8 TR²/(4 ln 2) + 0.2 r², "
     "where TR = ln(max(H, PC)/min(L, PC)) is Wilder's (1978) true range", "-"],
]
pd.DataFrame(_t33, columns=["Step", "Definition", "Constant (frozen in plan M16)"]).to_csv(
    TAB / "paper_table33_anam_definition.csv", index=False)

_f101 = pd.read_csv(TAB / "table101_anam_holdout_forecast.csv")
_f108 = pd.read_csv(TAB / "table108_anam_frontier_forecast.csv")
_f113 = pd.read_csv(TAB / "table113_anam_morocco_forecast.csv")
_SAMPLES = [  # label, plan, forecast frame, market, test span
    ("NEPSE, regimes A2 and C", "M16", _f101, "NEPSE", "A2+C"),
    ("NIFTY 50 (index)", "M16", _f101, "NIFTY50", "test half"),
    ("S&P 500 (index)", "M16", _f101, "SP500", "test half"),
    ("Dhaka 2023-2026", "M17", _f108, "DSE 2023-2026", "test half"),
    ("Vietnam 2007-2020", "M17", _f108, "Vietnam 2007-2020", "test half"),
    ("Dhaka 2009-2021 (dates repaired)", "M17", _f108, "DSE 2009-2021", "test half"),
    ("Morocco 2012-2026", "M18", _f113, "Morocco 2012-2026", "test half"),
]
_t34 = []
for _lab, _plan, _fr, _mk, _sp in _SAMPLES:
    for _w in (5, 21):
        _g = _fr[(_fr.market == _mk) & (_fr.test_span == _sp) & (_fr.window == _w)].set_index("estimator")
        _oth = _g.loc[["GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"], "QLIKE"]
        _t34.append([_lab, _plan, _w, f"{_g.loc['CC', 'QLIKE']:.4f}", f"{_g.loc['P', 'QLIKE']:.4f}",
                     f"{_NAMES[_oth.idxmin()]} {_oth.min():.4f}", f"{_g.loc['Anam', 'QLIKE']:.4f}",
                     f"{_g.loc[_VAR, 'QLIKE']:.4f}", f"{_g.loc['Anam', 't_vs_CC']:+.2f}",
                     f"{_g.loc[_VAR, 't_vs_CC']:+.2f}"])
pd.DataFrame(_t34, columns=[
    "Test sample", "Plan", "Horizon (sessions)", "Close-to-close", "Parkinson",
    "Best other range estimator", "Anam", "Anam, open-free form",
    "Anam minus close-to-close: t", "Open-free form minus close-to-close: t",
]).to_csv(TAB / "paper_table34_anam_forecasts.csv", index=False)

_l102 = pd.read_csv(TAB / "table102_anam_holdout_level.csv")
_l109 = pd.read_csv(TAB / "table109_anam_frontier_level.csv")
_l114 = pd.read_csv(TAB / "table114_anam_morocco_level.csv")
_LEVELS = [("NEPSE, regime A2", "M16", _l102, "NEPSE", "A2"), ("NEPSE, regime C (after the reform)", "M16", _l102, "NEPSE", "C"),
           ("NIFTY 50 (index)", "M16", _l102, "NIFTY50", "test half"), ("S&P 500 (index)", "M16", _l102, "SP500", "test half"),
           ("Dhaka 2023-2026", "M17", _l109, "DSE 2023-2026", "test half"),
           ("Vietnam 2007-2020", "M17", _l109, "Vietnam 2007-2020", "test half"),
           ("Dhaka 2009-2021 (dates repaired)", "M17", _l109, "DSE 2009-2021", "test half"),
           ("Morocco 2012-2026", "M18", _l114, "Morocco 2012-2026", "test half")]
_t35 = []
for _lab, _plan, _fr, _mk, _sp in _LEVELS:
    _g = _fr[(_fr.market == _mk) & (_fr.span == _sp)].set_index("estimator")["ratio_to_close_to_close"]
    _t35.append([_lab, _plan] + [f"{_g[k]:.3f}" for k in ("Anam (calibrated)", "P", "GK", "o2+P",
                                                           "YZ (daily form)", "YZ (window form)")])
pd.DataFrame(_t35, columns=[
    "Test sample", "Plan", "Anam (calibrated)", "Parkinson", "Garman-Klass", "overnight² + Parkinson",
    "Yang-Zhang (daily form)", "Yang-Zhang (window form)",
]).to_csv(TAB / "paper_table35_anam_level.csv", index=False)

_d105 = pd.read_csv(TAB / "table105_anam_holdout_decisions.csv")
_d111 = pd.read_csv(TAB / "table111_anam_frontier_decisions.csv")
_d116 = pd.read_csv(TAB / "table116_anam_morocco_decisions.csv")
_MK = {"NEPSE": "NEPSE", "NIFTY50": "NIFTY 50", "SP500": "S&P 500", "DSE 2023-2026": "Dhaka 2023-2026",
       "Vietnam 2007-2020": "Vietnam 2007-2020", "DSE 2009-2021": "Dhaka 2009-2021 (dates repaired)",
       "DSE 2023-2026 + Vietnam 2007-2020": "Dhaka 2023-2026 and Vietnam 2007-2020",
       "Morocco 2012-2026": "Morocco 2012-2026"}
_t36 = []
for _plan, _fr in (("M16", _d105), ("M17", _d111), ("M18", _d116)):
    for _r in _fr[_fr.rule != "rival"].itertuples():
        _who = ("open-free form" if getattr(_r, "estimator", "Anam") == _VAR else "Anam")
        _t36.append([_plan, _r.rule, _MK[_r.market], _who, _r.verdict,
                     str(_r.detail).replace("o2+P", "overnight² + Parkinson").replace(_VAR, "open-free form")])
pd.DataFrame(_t36, columns=["Plan", "Rule", "Test sample", "Estimator tested",
                            "Verdict (frozen rule, applied mechanically)", "Evidence"]).to_csv(
    TAB / "paper_table36_anam_verdicts.csv", index=False)
print("wrote paper_table33, paper_table34, paper_table35, paper_table36 (M16-M18)")

# ─────────────────────────── Manuscript Tables 37-38: the POST HOC recheck of Tables 34-36
# Written after every M16-M18 verdict was known (scripts/44, not pre-registered). Table 37 varies the
# inference and the loss behind each plan rule; Table 38 gives every estimator the calibration Anam's
# estimator has, which Table 35 does not. Neither changes a frozen verdict.
_r117 = pd.read_csv(TAB / "table117_anam_recheck_level.csv")
_r118 = pd.read_csv(TAB / "table118_anam_recheck_inference.csv")
_r119 = pd.read_csv(TAB / "table119_anam_recheck_multiplicity.csv")
_SHORT = {"Anam": "Anam", _VAR: "open-free form", "CC": "close-to-close", "P": "Parkinson"}
_ROWS37 = [(r["plan"], r["rule"], r["market"], "test half" if r["market"] != "NEPSE" else "A2+C", r["estimator"],
            r["reference"], 5, f"{r['Holm p across plans']:.3f}") for _, r in _r119.iterrows()]
_ROWS37 += [("M16", "reported", "NEPSE", "C", "Anam", "CC", 5, "-"),
            ("M17", "reported", "Vietnam 2007-2020", "test half", "Anam", "CC", 21, "-")]
_t37 = []
for _plan, _rule, _mk, _sp, _e, _ref, _w, _holm in _ROWS37:
    _g = _r118[(_r118.market == _mk) & (_r118.test_span == _sp) & (_r118.window == _w)
               & (_r118.estimator == _e) & (_r118.reference == _ref)].iloc[0]
    _lab = _MK[_mk] + (", regime C" if _sp == "C" else "")
    _t37.append([_plan, _rule.replace(" (vs close-to-close)", "").replace(" (vs Parkinson)", ""), _lab,
                 f"{_SHORT[_e]} vs {_SHORT[_ref]}, {_w} sessions"]
                + [f"{_g[c]:+.2f}" for c in ("t_frozen_NW_h", "t_NW_2h", "t_NW_4h", "t_nonoverlapping", "t_MSE_NW_h",
                                             "t_first_half", "t_second_half")] + [_holm])
pd.DataFrame(_t37, columns=[
    "Plan", "Rule", "Test sample", "Comparison", "Frozen t (lags = horizon)", "Lags 2 x horizon",
    "Lags 4 x horizon", "Non-overlapping origins", "MSE loss", "First half", "Second half",
    "Holm p, all plans (one-sided)",
]).to_csv(TAB / "paper_table37_anam_robustness.csv", index=False)

_RANGE = ["P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"]
_t38 = []
for _lab, _plan, _fr, _mk, _sp in _LEVELS:
    _g = _r117[(_r117.market == _mk) & (_r117.span == _sp)].set_index("estimator")
    _cal = _g.loc[_RANGE, "calibrated_ratio"]
    _lag = _g.loc[_RANGE, "calibrated_before_window_ratio"]
    _t38.append([_lab] + [f"{_g.loc[k, 'calibrated_ratio']:.3f}" for k in ["Anam", _VAR, "P", "GK", "o2+P", "YZ (daily form)"]]
                + [f"{_cal.min():.3f} to {_cal.max():.3f}", f"{_g.loc['Anam', 'calibrated_before_window_ratio']:.3f}",
                   f"{_lag.min():.3f} to {_lag.max():.3f}"])
pd.DataFrame(_t38, columns=[
    "Test sample", "Anam", "Anam, open-free form", "Parkinson", "Garman-Klass", "overnight² + Parkinson",
    "Yang-Zhang (daily form)", "All six classical range estimators", "Anam, calibration ending before the window",
    "Six classical, calibration ending before the window",
]).to_csv(TAB / "paper_table38_anam_level_same_calibration.csv", index=False)
print("wrote paper_table37, paper_table38 (post hoc recheck)")

checks += [
    ["M16_holdout_verdicts", "; ".join(f"{r.rule} {r.market} {r.verdict}" for r in _d105[_d105.rule != "rival"].itertuples()),
     "verdict", "40_anam_holdout.py"],
    ["M17_frontier_verdicts", "; ".join(f"{r.rule} {r.market} {r.verdict}" for r in _d111[_d111.rule != "rival"].itertuples()),
     "verdict", "42_anam_frontier.py"],
    ["M18_morocco_verdicts", "; ".join(f"{r.rule} {r.verdict}" for r in _d116[_d116.rule != "rival"].itertuples()),
     "verdict", "43_anam_morocco.py"],
    ["Anam_calibrated_level_by_test_sample", "; ".join(f"{row[0]} {row[2]}" for row in _t35), "ratio",
     "40_anam_holdout.py; 42_anam_frontier.py; 43_anam_morocco.py"],
    ["Anam_minus_CC_t_at_5_sessions", "; ".join(f"{row[0]} {row[8]}" for row in _t34 if row[2] == 5), "t",
     "40_anam_holdout.py; 42_anam_frontier.py; 43_anam_morocco.py"],
    ["Anam_open_free_minus_CC_t_at_5_sessions", "; ".join(f"{row[0]} {row[9]}" for row in _t34 if row[2] == 5), "t",
     "40_anam_holdout.py; 42_anam_frontier.py; 43_anam_morocco.py"],
    ["Posthoc_recheck_Holm_p_all_plans", "; ".join(f"{row[0]} {row[1]} {row[2]}: {row[11]}" for row in _t37 if row[11] != "-"),
     "one-sided p", "44_anam_recheck.py"],
    ["Posthoc_recheck_level_same_calibration_six_classical", "; ".join(f"{row[0]} {row[7]}" for row in _t38), "ratio",
     "44_anam_recheck.py"],
]

pd.DataFrame(checks, columns=["Result", "Value", "Scale", "Producer"]).to_csv(
    ROOT / "PAPER_RESULTS_CHECK.csv", index=False)

print("wrote manuscript-facing tables 1, 3-9 and PAPER_RESULTS_CHECK.csv")
