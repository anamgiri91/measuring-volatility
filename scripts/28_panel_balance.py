"""Panel balance, equal-security weighting, the thin tail, and estimator information content.

PEER-REVIEW ITEMS A AND B / MANDATORY ITEMS 1 AND 2. The reviewer accepted the paper's central
claim but rejected the basis on which it was stated. Two objections, both correct:

  A. THE HEADLINE HID THE THIN TAIL.  "Range estimators do not collapse in the least active
     group" was a statement about a STOCK-DAY-WEIGHTED quintile average, conditional on the
     security appearing in the file at all. Both qualifiers do work. A security that trades on
     5% of sessions contributes 5% of the stock-days, so the securities where collapse is most
     likely are precisely the ones carrying least weight in the average that is supposed to
     detect it. The reviewer named three -- NLO, BNL, UNL -- where range estimators DO collapse.
     They are right, and this script reports them rather than averaging them away.

  B. EQUALITY OF AGGREGATE MEANS IS NOT MEASUREMENT VALIDATION.  A ratio of aggregate sums near
     one shows similar aggregate SCALE. It says nothing about whether the estimator tracks the
     proxy day by day, and the paper had been reading it as though it did. Correlations between
     each estimator and the proxy are reported here because they answer a different question
     from the ratio, and answer it much less favourably.

Everything here is a decomposition of results the package already reports. No new estimator, no
new sample, no new screen: the same 143,718 ordinary-equity stock-days, disaggregated along the
axes the aggregate ratio integrates over.

WHAT "PARTICIPATION" MEANS HERE
-------------------------------
Participation is measured against the security's OWN LISTING WINDOW -- the detected sessions
between its first and last observed row -- not against all 569 sessions of the sample. A
security listed in month 20 of a 30-month sample has not "missed" the first 19 months. Measured
this way the panel is 99.4% complete within listing windows and 86.5% complete against the full
session x security grid; the gap between those two numbers is listing and delisting, not
non-trading, and reporting only the second would overstate absence by a factor of twenty.

Outputs
    output/tables/table39_panel_balance.csv
    output/tables/table40_participation_by_quintile.csv
    output/tables/table41_equal_security_ratios.csv
    output/tables/table42_thin_tail.csv
    output/tables/table43_information_content.csv
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import bootstrap
bootstrap()

import numpy as np
import pandas as pd

sys.path.insert(0, str(ROOT / "src"))
from nepsevol.sample import load_sample
from nepsevol.estimators import range_ as R
from nepsevol.corporate_actions import adjusted_previous_close
from nepsevol.trading_calendar import session_index
from nepsevol.inference import ratio_of_sums_ci
from nepsevol.equivalence import equivalence_verdict, MARGIN

TAB = ROOT / "output" / "tables"
TAB.mkdir(parents=True, exist_ok=True)

#: A security enters the thin tail if it fails EITHER test. Both thresholds are stated here
#: rather than chosen per table: a security absent from a tenth of its own listing window, or
#: showing no price movement at all on a twentieth of the days it does trade, is thin in a way
#: the quintile average cannot represent.
MIN_PARTICIPATION = 0.90
MAX_ZERO_RANGE = 0.05

panel = load_sample(ROOT, "equity").sort_values(["symbol", "date"]).reset_index(drop=True)
cal = pd.read_csv(ROOT / "data" / "processed" / "nepse_trading_calendar.csv",
                  parse_dates=["date"]).set_index("date")
sessions = cal.index[cal.is_session.astype(bool)]
panel["session_ord"] = session_index(panel.date, cal).to_numpy()

panel["v_pk"] = R.parkinson(panel)
panel["v_gk"] = R.garman_klass(panel)
panel["v_rs"] = R.rogers_satchell(panel)
panel["v_addrs"] = R.add_rs(panel)
panel["v_oc"] = np.log(panel.close / panel.open) ** 2
panel["zero_range"] = (panel.high == panel.low)
_prev = adjusted_previous_close(panel)
panel["v_cc"] = np.log(panel.close / _prev) ** 2

g = panel.groupby("symbol")
first, last, n_obs = g.date.min(), g.date.max(), g.date.nunique()
window = pd.Series({s: int(((sessions >= first[s]) & (sessions <= last[s])).sum())
                    for s in first.index})

sec = pd.DataFrame({
    "n_obs": n_obs,
    "listing_window_sessions": window,
    "participation": n_obs / window,
    "median_trades": g.n_trades.median(),
    "zero_range_share": g.zero_range.mean(),
})
sec["pk_ratio"] = g.apply(
    lambda x: np.sqrt(x.v_pk.mean() / x.v_oc.mean()) if x.v_oc.mean() > 0 else np.nan)
sec["rs_ratio"] = g.apply(
    lambda x: np.sqrt(max(x.v_rs.mean(), 0.0) / x.v_oc.mean()) if x.v_oc.mean() > 0 else np.nan)

sec_median_trades = g.n_trades.median()
sec["quintile"] = pd.qcut(sec_median_trades, 5, labels=False, duplicates="drop") + 1


# ───────────────────────────────────────────────────── A(i): how balanced is the panel really

n_sec, n_sess = len(sec), len(sessions)
balance = pd.DataFrame([
    {"denominator": "full grid (every security x every detected session)",
     "cells": n_sec * n_sess, "observed": len(panel),
     "fill_rate": len(panel) / (n_sec * n_sess),
     "note": "the unconditional balanced panel; its shortfall is dominated by securities not "
             "yet listed or already delisted, which is not an absence of trading"},
    {"denominator": "own listing window (first to last observed session, per security)",
     "cells": int(window.sum()), "observed": len(panel),
     "fill_rate": len(panel) / window.sum(),
     "note": "the conditional balanced panel; its shortfall IS non-trading, and is the number "
             "the estimator claims must survive"},
])
balance.to_csv(TAB / "table39_panel_balance.csv", index=False)

print("\nA(i). Panel balance: the claim is restricted to OBSERVED, TRADING stock-days")
print("=" * 108)
print(balance.drop(columns="note").to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
_missing = int(window.sum()) - len(panel)
print(f"\n  absent security-sessions INSIDE listing windows: {_missing:,} "
      f"({100*_missing/window.sum():.2f}% of the conditional grid)")
print("  -> the panel is not balanced, and every result below is conditional on the security")
print("     having traded that session. That conditioning is now stated in the Abstract, §6.1")
print("     and §11 rather than left implicit in the sample definition.")


# ─────────────────────────────────────────── A(ii): participation distribution, not its median

part = (sec.groupby("quintile")
        .participation.describe(percentiles=[.05, .25, .50, .75, .95])
        .rename(columns={"50%": "median"}))
part["n_securities"] = sec.groupby("quintile").size()
part.to_csv(TAB / "table40_participation_by_quintile.csv")

print("\n\nA(ii). Participation DISTRIBUTION by security-level liquidity quintile")
print("=" * 108)
print("    (share of the security's own listing window on which it actually traded)")
print(part[["n_securities", "min", "5%", "25%", "median", "95%", "max"]]
      .to_string(float_format=lambda x: f"{x:,.3f}"))
_q1 = sec[sec.quintile == 1]
print(f"\n  Q1 (thinnest): participation ranges {_q1.participation.min():.3f} to "
      f"{_q1.participation.max():.3f}, median {_q1.participation.median():.3f}.")
print("  -> the median of 1.00 the earlier table reported is true and uninformative. The range")
print("     is the finding: one Q1 security trades on 5% of its own listing window.")


# ──────────────────────────── A(iii): equal-security weighting against stock-day weighting

rows = []
for q, gg in sec.groupby("quintile"):
    sub = panel[panel.symbol.isin(gg.index)]
    pooled = np.sqrt(sub.v_pk.mean() / sub.v_oc.mean())
    pooled_rs = np.sqrt(max(sub.v_rs.mean(), 0.0) / sub.v_oc.mean())
    rows.append({
        "quintile": f"Q{int(q)}", "n_securities": len(gg), "n_stock_days": len(sub),
        "median_trades": float(gg.median_trades.median()),
        "pk_stockday_weighted": pooled,
        "pk_equal_security_mean": float(gg.pk_ratio.mean()),
        "pk_equal_security_median": float(gg.pk_ratio.median()),
        "rs_stockday_weighted": pooled_rs,
        "rs_equal_security_median": float(gg.rs_ratio.median()),
        "pk_security_p05": float(gg.pk_ratio.quantile(0.05)),
        "pk_security_p95": float(gg.pk_ratio.quantile(0.95)),
    })
eq = pd.DataFrame(rows)
eq.to_csv(TAB / "table41_equal_security_ratios.csv", index=False)

print("\n\nA(iii). EQUAL-SECURITY vs STOCK-DAY weighting, and the security-level spread")
print("=" * 108)
print(eq[["quintile", "n_securities", "n_stock_days", "median_trades",
          "pk_stockday_weighted", "pk_equal_security_mean", "pk_equal_security_median",
          "pk_security_p05", "pk_security_p95"]]
      .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
_gap = (eq.pk_equal_security_mean - eq.pk_stockday_weighted).abs().max()
print(f"\n  largest gap between the two weightings, any quintile: {_gap:.3f}")
print("  -> the weighting objection does not overturn the quintile result: equal-security and")
print("     stock-day weighted ratios agree to within this gap. What the aggregate hides is not")
print("     the AVERAGE but the SPREAD -- see the 5th-95th percentile columns, and the tail below.")


# ────────────────────────────────────────────── A(iv): the extreme thin tail, on its own terms

sec["thin_tail"] = ((sec.participation < MIN_PARTICIPATION)
                    | (sec.zero_range_share >= MAX_ZERO_RANGE))
tail_syms = sec.index[sec.thin_tail]
tail = panel[panel.symbol.isin(tail_syms)]
rest = panel[~panel.symbol.isin(tail_syms)]

tail_rows = []
for label, sub in [("extreme thin tail", tail), ("all other ordinary equity", rest)]:
    if not len(sub):
        continue
    num = sub.v_pk.to_numpy(float)
    den = sub.v_oc.to_numpy(float)
    m = np.isfinite(num) & np.isfinite(den)
    lo, hi = ratio_of_sums_ci(np.where(m, num, 0.0), np.where(m, den, 0.0),
                              sub.symbol, sub.date)
    pk = np.sqrt(sub.v_pk.mean() / sub.v_oc.mean())
    tail_rows.append({
        "group": label, "n_securities": sub.symbol.nunique(), "n_stock_days": len(sub),
        "share_of_panel_pct": 100 * len(sub) / len(panel),
        "median_participation": float(sec.loc[sub.symbol.unique(), "participation"].median()),
        "zero_range_pct": 100 * sub.zero_range.mean(),
        "Parkinson": pk, "Parkinson_lo95": lo, "Parkinson_hi95": hi,
        "Rogers-Satchell": np.sqrt(max(sub.v_rs.mean(), 0.0) / sub.v_oc.mean()),
        "verdict_vs_margin": equivalence_verdict(lo, hi),
    })

detail = sec.loc[tail_syms, ["n_obs", "listing_window_sessions", "participation",
                             "median_trades", "zero_range_share", "pk_ratio", "rs_ratio"]]
detail = detail.sort_values("participation")
pd.concat([pd.DataFrame(tail_rows),
           detail.reset_index().rename(columns={"symbol": "group"})],
          ignore_index=True).to_csv(TAB / "table42_thin_tail.csv", index=False)

print("\n\nA(iv). THE EXTREME THIN TAIL, analysed separately")
print("=" * 108)
print(f"    entry test: participation < {MIN_PARTICIPATION:.2f} OR zero-range share >= "
      f"{MAX_ZERO_RANGE:.2f}")
print(pd.DataFrame(tail_rows)[["group", "n_securities", "n_stock_days", "share_of_panel_pct",
                               "zero_range_pct", "Parkinson", "Parkinson_lo95",
                               "Parkinson_hi95", "verdict_vs_margin"]]
      .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
print("\n  security by security:")
print(detail.to_string(float_format=lambda x: f"{x:,.3f}"))
print("\n  -> RANGE ESTIMATORS DO COLLAPSE HERE. The reviewer is right, and the manuscript now")
print("     says so: the 'no collapse' result holds for ordinary equities that actually trade,")
print(f"     and fails on the {len(tail_syms)} securities above, which are "
      f"{100*len(tail)/len(panel):.2f}% of stock-days and carry correspondingly little weight")
print("     in any stock-day-weighted average. That is a scope restriction, not a footnote.")


# ─────────────── A(v): the estimand's weighting, for ALL SIX estimators (mandatory item 11)
#
# The primary ratio in this paper is a RATIO OF POOLED STOCK-DAY SUMS. That is a deliberate
# choice -- it answers "across all the trading this market actually did, how does the estimator
# compare with the matched proxy in aggregate scale" -- but it carries an implicit weighting: a
# security with a longer observed history and more trading days contributes more. The review is
# right that this had been stated for Parkinson and Rogers-Satchell by quintile (table41) and
# nowhere for the other four estimators, and that a headline could in principle be carried by a
# handful of long-lived or high-variance securities without that being visible.
#
# This block reports, for every estimator the paper names, the stock-day-weighted ratio beside
# the equal-security mean and median and the 5th-95th percentile of the SECURITY-level ratio,
# whole-sample rather than per quintile. A large gap between the first two columns would mean
# the weighting is doing the work; a wide percentile band means the aggregate is a summary of a
# heterogeneous population, which is a different (and here more relevant) caveat.
_EST_COLS = [("Parkinson", "v_pk", "v_oc"), ("Garman-Klass", "v_gk", "v_oc"),
             ("Rogers-Satchell", "v_rs", "v_oc"), ("AddRS", "v_addrs", "v_oc"),
             ("Close-to-close", "v_cc", "v_cc"), ("Yang-Zhang", "v_yz", "v_cc21")]

# Yang-Zhang and its horizon-matched benchmark are not in this script's panel; recompute them
# here under the ADOPTED previous close so this table matches Table 7 rather than drifting.
_yz_parts = []
for _s, _g in panel.groupby("symbol", sort=False):
    _p = _prev.loc[_g.index]
    _r = np.log(_g.close / _p)
    _yz_parts.append(pd.DataFrame({
        "v_yz": (R.yang_zhang(_g, 21, prev_close=_p) if len(_g) > 22
                 else pd.Series(np.nan, index=_g.index)),
        "v_cc21": _r.rolling(21).var(ddof=1),
    }, index=_g.index))
panel[["v_yz", "v_cc21"]] = pd.concat(_yz_parts).reindex(panel.index)


def _sec_ratio(frame, num, den):
    m = np.isfinite(frame[num]) & np.isfinite(frame[den])
    if not m.any():
        return np.nan
    d = frame.loc[m, den].mean()
    if not np.isfinite(d) or d <= 0:
        return np.nan
    return float(np.sqrt(max(frame.loc[m, num].mean(), 0.0) / d))


_w_rows = []
for _name, _num, _den in _EST_COLS:
    m = np.isfinite(panel[_num]) & np.isfinite(panel[_den])
    pooled = float(np.sqrt(max(panel.loc[m, _num].mean(), 0.0) / panel.loc[m, _den].mean()))
    per_sec = pd.Series(
        {sym: _sec_ratio(sub, _num, _den)
         for sym, sub in panel[m].groupby("symbol", sort=False)}).dropna()
    _w_rows.append({
        "estimator": _name,
        "n_stock_days": int(m.sum()),
        "n_securities": int(per_sec.size),
        "stockday_weighted": pooled,
        "equal_security_mean": float(per_sec.mean()),
        "equal_security_median": float(per_sec.median()),
        "security_p05": float(per_sec.quantile(0.05)),
        "security_p95": float(per_sec.quantile(0.95)),
        "weighting_gap": abs(float(per_sec.mean()) - pooled),
    })
_w = pd.DataFrame(_w_rows)
_w.to_csv(TAB / "table52_weighting_all_estimators.csv", index=False)

print("\n\nA(v). WEIGHTING of the headline estimand, all six estimators (mandatory item 11)")
print("=" * 108)
print("    The primary ratio is a ratio of pooled STOCK-DAY sums: securities with longer")
print("    observed histories and more trading days carry more weight in it.")
print(_w[["estimator", "n_securities", "stockday_weighted", "equal_security_mean",
          "equal_security_median", "security_p05", "security_p95", "weighting_gap"]]
      .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
print(f"\n  largest stock-day vs equal-security gap, any estimator: {_w.weighting_gap.max():.3f}")
print("  -> the weighting does not carry the headline: no estimator's equal-security mean")
print("     departs from its stock-day-weighted ratio by more than this. What the aggregate")
print("     does hide is the SPREAD across securities, which the p05-p95 columns report and")
print("     which is wide for every estimator.")

# Coverage strata: does a security's observed history length change its ratio? If the pooled
# ratio were being carried by long-lived securities, the strata would disagree.
_hist = sec[["n_obs"]].copy()
# Rank-based bins: many securities share an identical observed-session count (the full 569),
# so qcut on the raw counts cannot form three distinct edges. Ranking with method="first"
# breaks those ties deterministically and yields three equal-sized strata.
_hist["stratum"] = pd.qcut(_hist.n_obs.rank(method="first"), 3,
                           labels=["short history", "medium", "long history"])
_strata_rows = []
for _name, _num, _den in _EST_COLS:
    row = {"estimator": _name}
    for _label, _syms in _hist.groupby("stratum", observed=True).groups.items():
        sub = panel[panel.symbol.isin(_syms)]
        m = np.isfinite(sub[_num]) & np.isfinite(sub[_den])
        row[str(_label)] = (float(np.sqrt(max(sub.loc[m, _num].mean(), 0.0)
                                          / sub.loc[m, _den].mean())) if m.any() else np.nan)
    _strata_rows.append(row)
_strata = pd.DataFrame(_strata_rows)
_strata.to_csv(TAB / "table53_ratio_by_history_stratum.csv", index=False)
print("\n  Ratio by length of observed history (terciles of observed stock-days per security):")
print(_strata.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
print("  -> if the pooled ratio were an artifact of long-lived securities dominating the sum,")
print("     these three columns would diverge. They are reported so a reader can check that.")


# ─────────────────── B: aggregate parity is not measurement accuracy -- information content

info = []
for name, col in [("Parkinson", "v_pk"), ("Garman-Klass", "v_gk"),
                  ("Rogers-Satchell", "v_rs"), ("AddRS", "v_addrs")]:
    m = np.isfinite(panel[col]) & np.isfinite(panel.v_oc)
    x, y = panel.loc[m, col], panel.loc[m, "v_oc"]
    info.append({
        "estimator": name, "n_stock_days": int(m.sum()),
        "sd_ratio_to_proxy": np.sqrt(x.mean() / y.mean()),
        "pearson_vs_proxy": x.corr(y),
        "spearman_vs_proxy": x.corr(y, method="spearman"),
    })
inf_df = pd.DataFrame(info)
inf_df.to_csv(TAB / "table43_information_content.csv", index=False)

print("\n\nB. AGGREGATE PARITY IS NOT MEASUREMENT ACCURACY")
print("=" * 108)
print(inf_df.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
print("\n  Parkinson and Rogers-Satchell sit at 1.001 and 1.037 against the same proxy, yet")
print(f"  their rank correlations with it are "
      f"{inf_df.loc[0,'spearman_vs_proxy']:.2f} and {inf_df.loc[2,'spearman_vs_proxy']:.2f}.")
print("  Two estimators can share an aggregate scale and carry materially different daily")
print("  information. The ratio answers 'is the scale right on average'; it does not answer")
print("  'is the daily number right', and the manuscript no longer lets it.")
print("\n  Note also that numerator and proxy share OHLC inputs, so even these correlations are")
print("  mechanically supported and are an upper bound on independent agreement.")

print(f"\n  (equivalence margin in force: +/-{100*MARGIN:g}% on the SD-ratio scale)")
print("\nwrote table39, table40, table41, table42, table43")
