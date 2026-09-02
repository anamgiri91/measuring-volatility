"""Descriptive analysis of NEPSE trading intensity and estimator pathologies.

Produces Figure 1 (how thin is NEPSE), Figure 5 (estimator pathologies vs
trading intensity), and Tables 1-2.
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import bootstrap
bootstrap()

import numpy as np, pandas as pd
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.validate import validate_analysis_sample
import matplotlib.pyplot as plt
from nepsevol.utils import plotstyle as ps
from nepsevol.universe import classify_panel
from nepsevol.clean.limits import flag_infeasible_range
from nepsevol.estimators import range_ as R

ps.apply()
FIG = ROOT / "output" / "figures"; FIG.mkdir(parents=True, exist_ok=True)
TAB = ROOT / "output" / "tables";  TAB.mkdir(parents=True, exist_ok=True)

p = pd.read_parquet(ROOT / "data/processed/panel_trades_clean.parquet")
p = p.dropna(subset=["n_trades", "open", "high", "low", "close", "prev_close"])
p = p[(p[["open","high","low","close","prev_close"]] > 0).all(axis=1)]
p = p[p["n_trades"] >= 1]

# ---------------------------------------------------------------- per-stock-day estimators
p["hl"]  = np.log(p["high"] / p["low"])
p["cc"]  = np.log(p["close"] / p["prev_close"])
p["u"]   = np.log(p["high"] / p["open"])
p["d"]   = np.log(p["low"] / p["open"])
p["c"]   = np.log(p["close"] / p["open"])
LN2 = np.log(2)
p["var_pk"] = p["hl"]**2 / (4*LN2)
p["var_cc"] = p["cc"]**2
p["var_gk"] = 0.5*p["hl"]**2 - (2*LN2 - 1)*p["c"]**2
p["var_rs"] = p["u"]*(p["u"]-p["c"]) + p["d"]*(p["d"]-p["c"])
p = p[p["cc"].abs() < 0.5]                      # drop implausible returns (splits/errors)

# ---------------------------------------------------------------- RANGE screen
# The return filter above cannot protect a range estimator: a corrupted high or low leaves the
# close untouched and passes it. A legal session satisfies log(H/L) <= log((1+L)/(1-L)) given the
# prevailing daily price limit. See DD-018.
_bad = flag_infeasible_range(p)
if _bad.any():
    print(f"\ninfeasible range (exceeds the price limit's ceiling): dropping {int(_bad.sum())} row(s)")
    print(p.loc[_bad, ["symbol","date","open","high","low","close","n_trades"]].to_string(index=False))
p = p[~_bad]

# ---------------------------------------------------------------- instrument type
# NEPSE publishes no instrument-type field. Type is recovered from the ticker convention and
# confirmed against par value. The two thinnest liquidity quintiles of the FULL universe hold
# four ordinary equities between them out of 209 securities, so a liquidity contrast drawn across
# the full universe is largely an asset-class contrast. See DD-018 and D-0012.
p = classify_panel(p)

print(f"\nfull universe:  {len(p):,} stock-days, {p['symbol'].nunique()} symbols, "
      f"{p['date'].nunique()} sessions ({p['date'].min().date()} -> {p['date'].max().date()})")
print("  composition:", p.groupby("sec_type").symbol.nunique().to_dict())
_eq = p[p.sec_type == "equity"]
print(f"ordinary equity: {len(_eq):,} stock-days, {_eq['symbol'].nunique()} symbols")

# ---------------------------------------------------------------- TABLE 1: descriptives
q = [.01,.05,.10,.25,.50,.75,.90,.99]
t1 = pd.DataFrame({
    "Trades per stock-day":   p["n_trades"].describe(percentiles=q),
    "Turnover (NPR '000)":    (p["turnover"]/1e3).describe(percentiles=q),
    "|Close-to-close return|":p["cc"].abs().describe(percentiles=q),
    "High-low range ln(H/L)": p["hl"].describe(percentiles=q),
}).T
t1.to_csv(TAB / "table1_descriptives.csv")
print("\n=== TABLE 1: NEPSE stock-day descriptives ===")
print(t1[["count","mean","1%","10%","50%","90%","99%","max"]].to_string(float_format=lambda x: f"{x:,.4g}"))

# ---------------------------------------------------------------- TABLE 2: friction inventory
# Standard Rogers-Satchell and Garman-Klass CANNOT be negative on a valid OHLC bar.
#   RS = ln(H/O)ln(H/C) + ln(L/O)ln(L/C); with H >= max(O,C) and L <= min(O,C) both products
#        are non-negative.
#   GK = 0.5 ln(H/L)^2 - (2ln2-1) ln(C/O)^2; a valid bar satisfies |ln(C/O)| <= ln(H/L), so
#        GK >= (0.5 - (2ln2-1)) ln(C/O)^2 >= 0.
# A negative value is therefore evidence of an OHLC-INCONSISTENT RECORD, not of estimator
# failure under illiquidity. Reporting it as a pathology confuses a data defect with a
# property of the estimator, so negatives are cross-tabbed against violations and reported
# as such. Zeros are a separate and genuine phenomenon and are split out.
zero_range = (p["high"] == p["low"])
viol = ~((p["high"] >= p[["open","close"]].max(axis=1) - 1e-12) &
         (p["low"]  <= p[["open","close"]].min(axis=1) + 1e-12))
rs_neg, gk_neg = p["var_rs"] < -1e-15, p["var_gk"] < -1e-15
rs_zero = p["var_rs"].abs() <= 1e-15

frictions = pd.DataFrame([
    ("F1  Thin trading: median trades/stock-day",            f"{p['n_trades'].median():.0f}"),
    ("F1  Stock-days with < 10 trades",                      f"{100*(p['n_trades']<10).mean():.1f}%"),
    ("F1  Stock-days with < 30 trades",                      f"{100*(p['n_trades']<30).mean():.1f}%"),
    ("F1  Stock-days with < 100 trades",                     f"{100*(p['n_trades']<100).mean():.1f}%"),
    ("F7  Zero observed range (H == L)",                     f"{100*zero_range.mean():.1f}%"),
    ("F7  -> Parkinson variance exactly zero (uninformative)", f"{100*(p['var_pk']==0).mean():.1f}%"),
    ("--  Rogers-Satchell exactly zero",                     f"{100*rs_zero.mean():.1f}%"),
    ("      ...of which H == L",                             f"{100*zero_range[rs_zero].mean():.1f}%"),
    ("      ...remainder are MONOTONE days (a known RS property)", f"{100*(1-zero_range[rs_zero].mean()):.1f}%"),
    ("F3  Zero close-to-close return (stale price)",         f"{100*(p['cc']==0).mean():.1f}%"),
    ("DATA  OHLC-inconsistent records",                      f"{100*viol.mean():.2f}%"),
    ("DATA  Rogers-Satchell negative (impossible if valid)", f"{100*rs_neg.mean():.3f}%"),
    ("      ...share of those that are OHLC-inconsistent",   f"{100*viol[rs_neg].mean() if rs_neg.any() else 0:.1f}%"),
    ("DATA  Garman-Klass negative (impossible if valid)",    f"{100*gk_neg.mean():.3f}%"),
    ("      ...share of those that are OHLC-inconsistent",   f"{100*viol[gk_neg].mean() if gk_neg.any() else 0:.1f}%"),
], columns=["Friction / data defect", "NEPSE"])
frictions.to_csv(TAB / "table2_frictions.csv", index=False)
print("\n=== TABLE 2: friction inventory, with data defects separated ===")
print(frictions.to_string(index=False))
print(f"\n  negatives among VALID records: RS {100*(rs_neg & ~viol).mean():.4f}%  "
      f"GK {100*(gk_neg & ~viol).mean():.4f}%   (theory says both must be 0)")

# ---------------------------------------------------------------- FIGURE 1
fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.1))

ax = axes[0]
lg = np.log10(p["n_trades"].clip(lower=1))
ax.hist(lg, bins=60, color=ps.SERIES["blue"], edgecolor=ps.SURFACE, linewidth=0.3)
med = p["n_trades"].median()
ax.axvline(np.log10(med), color=ps.SERIES["orange"], linestyle="--", linewidth=1.4)
ax.text(np.log10(med)+.14, ax.get_ylim()[1]*.97, f"median {med:.0f}",
        color=ps.SERIES["orange"], fontsize=8, va="top", fontweight="bold",
        bbox=dict(fc=ps.SURFACE, ec="none", pad=1.5))
ax.set_xticks([0,1,2,3,4]); ax.set_xticklabels(["1","10","100","1,000","10,000"])
ps.finish(ax, "A. Trades per stock-day", None, "Transactions (log scale)", "Stock-days")

ax = axes[1]
thr = np.unique(np.round(np.logspace(0, 3.6, 90)).astype(int))
share = [(p["n_trades"] <= t).mean()*100 for t in thr]
ax.plot(thr, share, color=ps.SERIES["blue"], linewidth=1.8)
ax.set_xscale("log"); ps.plain_log_axis(ax, "x")
for t, lbl in [(10,"10"), (30,"30"), (100,"100")]:
    s = (p["n_trades"] <= t).mean()*100
    ax.plot([t],[s], marker="o", ms=5, color=ps.SERIES["orange"], zorder=5,
            markeredgecolor=ps.SURFACE, markeredgewidth=1.2)
    ax.annotate(f"{s:.0f}% at or below {lbl}", (t, s), textcoords="offset points",
                xytext=(10, -12), fontsize=7.5, color=ps.INK_SOFT,
                bbox=dict(fc=ps.SURFACE, ec="none", pad=1.2))
ax.set_ylim(0, 100)
ps.finish(ax, "B. Cumulative share of stock-days", None, "Trades per day (log scale)", "Percent at or below")

ps.header(fig,
    "Trading intensity in the pooled universe, before any instrument filter",
    f"Every listed instrument type · {len(p):,} stock-days · {p['symbol'].nunique()} securities · "
    f"{p['date'].min().date()} to {p['date'].max().date()}", top=0.86)
for ext in ("png","pdf"): fig.savefig(FIG / f"fig1_trading_intensity.{ext}")
plt.close(fig)
print(f"\nwrote {FIG/'fig1_trading_intensity.png'}")

# ---------------------------------------------------------------- FIGURE 5: pathologies vs N
p["dec"] = pd.qcut(p["n_trades"], 10, labels=False, duplicates="drop")
g = p.groupby("dec").agg(
    n_med=("n_trades","median"),
    pk_zero=("var_pk", lambda s: 100*(s==0).mean()),
    gk_neg=("var_gk", lambda s: 100*(s<0).mean()),
    cc_zero=("cc",    lambda s: 100*(s==0).mean()),
).reset_index()

fig, ax = plt.subplots(figsize=(5.6, 3.4))
for col, lbl, key in [("pk_zero","Parkinson variance = 0","Parkinson"),
                      ("gk_neg","Garman-Klass variance < 0","Garman-Klass"),
                      ("cc_zero","Zero return (stale price)","Close-to-close")]:
    c, ls, mk = ps.STYLE[key]
    ax.plot(g["n_med"], g[col], color=c, linestyle=ls, marker=mk,
            markeredgecolor=ps.SURFACE, markeredgewidth=1.0, label=lbl)
    ax.annotate(lbl, (g["n_med"].iloc[0], g[col].iloc[0]), textcoords="offset points",
                xytext=(6, 6), fontsize=7.5, color=c, fontweight="bold")
ax.set_xscale("log")
ps.plain_log_axis(ax, "x")
ps.finish(ax, None, None, "Median trades per day in decile (log scale)", "Percent of stock-days")
# Header text is wrapped by hand: savefig runs with bbox_inches="tight", so a line
# wider than the axes silently widens the saved canvas and strands the plot in whitespace.
ps.header(fig, "Degenerate estimator values, by liquidity decile",
          "Pooled universe, every instrument type. The gradient is a composition\n"
          "artifact (Figure 1); within ordinary equity it is absent.",
          top=0.80)
for ext in ("png","pdf"): fig.savefig(FIG / f"fig5_pathologies.{ext}")
plt.close(fig)
print(f"wrote {FIG/'fig5_pathologies.png'}")

g.to_csv(TAB / "table3_pathologies_by_decile.csv", index=False)
print("\n=== Pathology rates by liquidity decile ===")
print(g.rename(columns={"n_med":"median trades","pk_zero":"PK=0 %","gk_neg":"GK<0 %","cc_zero":"zero ret %"})
      .to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
# Two samples are written. Downstream scripts must choose explicitly rather than inherit a
# default, because the choice determines whether a "liquidity" contrast is a liquidity contrast.
# Hard invariant gate: a failure raises and stops the build (audit policy SS8).
validate_analysis_sample(_eq, universe="equity")
validate_analysis_sample(p, universe="full", expect_sec_type=False)
print("  invariant gate: PASSED for both samples")

p.to_parquet(ROOT / "data/processed/analysis_sample.parquet", index=False)          # full universe
_eq.to_parquet(ROOT / "data/processed/equity_sample.parquet", index=False)          # ordinary equity
print(f"\nwrote analysis_sample.parquet ({len(p):,} rows, all instrument types)")
print(f"wrote equity_sample.parquet   ({len(_eq):,} rows, ordinary equity only)")
