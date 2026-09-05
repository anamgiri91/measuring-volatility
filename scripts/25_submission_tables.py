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

pd.DataFrame(checks, columns=["Result", "Value", "Scale", "Producer"]).to_csv(
    ROOT / "PAPER_RESULTS_CHECK.csv", index=False)

print("wrote manuscript-facing tables 1, 3-9 and PAPER_RESULTS_CHECK.csv")
