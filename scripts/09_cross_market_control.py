"""Cross-market control: does the bias vanish where trading is dense?

The single most damaging objection to this paper is that something is wrong with NEPSE,
with the data, or with our code, rather than with range estimators under thin trading.
This script answers it with real data rather than simulation.

The identical estimator code is run on three regimes:

    NIFTY 50      dense, clean, liquid, has a listed implied-volatility index
    NEPSE index   moderate: aggregates every listed security
    NEPSE equity  thin, split by published daily trade count

Under GBM with a continuously observed path, E[Parkinson] = E[(ln C/O)^2] = intraday
variance, so their ratio is 1. Departures from 1 are diagnostic rather than causal: in NEPSE,
instrument composition, session structure, price limits, and trading intensity can all affect
the observed ratio. The final paper therefore evaluates ordinary equities separately from the
pooled exchange universe.

Also implements a Martens & van Dijk (2007) style scaling correction to demonstrate the
data requirement that makes it unavailable in a frontier market.

Produces Figures 12-13 and Tables 14-15.
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import bootstrap
bootstrap(["statsmodels"])

import numpy as np, pandas as pd
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.sample import load_sample
from nepsevol.estimators.ratios import sd_ratio
import matplotlib.pyplot as plt
import statsmodels.api as sm
from nepsevol.utils import plotstyle as ps
from nepsevol.estimators import range_ as R

ps.apply()
FIG = ROOT/"output"/"figures"; TAB = ROOT/"output"/"tables"
EXT = ROOT.parent/"private"/"data-vault"/"raw"/"external"
VAULT = ROOT.parent/"private"/"data-vault"/"raw"
LN2 = np.log(2)


def fingerprint(df):
    """Ratio of Parkinson (and GK, RS) variance to the matched open-to-close benchmark.

    The benchmark is deliberately open-to-close, not close-to-close: Parkinson measures the
    intraday session only, and close-to-close also carries overnight variance, which would
    manufacture a ratio below one even with no friction at all.
    """
    d = df[(df[["open","high","low","close"]] > 0).all(axis=1)].copy()
    hl = np.log(d.high/d.low); c = np.log(d.close/d.open)
    u  = np.log(d.high/d.open); l = np.log(d.low/d.open)
    var_pk = (hl**2)/(4*LN2)
    var_gk = 0.5*hl**2 - (2*LN2-1)*c**2
    var_rs = u*(u-c) + l*(l-c)
    var_oc = c**2
    m = var_oc.mean()
    out = {}
    for name, v in [("Parkinson",var_pk),("Garman-Klass",var_gk),("Rogers-Satchell",var_rs)]:
        # SD-scale ratio, labelled at source (A-038). Column names carry the scale.
        out[f"{name}_sd_ratio"], _ = sd_ratio(v, m)
    out["n_days"] = len(d)
    out["zero_range_pct"] = 100*(d.high == d.low).mean()
    return out

# ─────────────────────────────────────────────────────── load the three regimes
nifty = pd.read_csv(EXT/"nifty50.csv", parse_dates=["Date"])
nifty.columns = [x.lower() for x in nifty.columns]
nifty = nifty.sort_values("date")

idx = pd.read_csv(VAULT/"nepse_index_history.csv", parse_dates=["Date"])
idx.columns = [x.lower() for x in idx.columns]
nepse_idx = idx[idx.date >= pd.Timestamp("2016-06-06")].sort_values("date")

panel = load_sample(ROOT, "equity")

rows = [{"regime":"NIFTY 50 (dense, liquid)", "trades":np.nan, **fingerprint(nifty)},
        {"regime":"NEPSE index (aggregate)",  "trades":np.nan, **fingerprint(nepse_idx)}]
panel["b"] = pd.qcut(panel.n_trades, 6, labels=False, duplicates="drop")
for b, g in panel.groupby("b"):
    rows.append({"regime":f"NEPSE equity · ~{g.n_trades.median():.0f} trades/day",
                 "trades":g.n_trades.median(), **fingerprint(g)})
fp = pd.DataFrame(rows)
fp.to_csv(TAB/"table14_cross_market_fingerprint.csv", index=False)

# The pooled-universe comparison §6 draws in one sentence. Emitted to its own artifact rather
# than appended to table14, so neither the figure nor the manuscript table changes shape.
# It had been a prose-only number and did not reproduce (A-069).
pooled = load_sample(ROOT, "full")
pooled["b"] = pd.qcut(pooled.n_trades, 6, labels=False, duplicates="drop")
thin = pooled[pooled.b == pooled.b.min()]
prow = {"universe": "pooled (every instrument type)", "buckets": 6,
        "median_trades": thin.n_trades.median(), **fingerprint(thin)}
pd.DataFrame([prow]).to_csv(TAB/"table30_pooled_thin_comparison.csv", index=False)
print(f"\nPooled-universe thinnest bucket (§6 comparison): "
      f"{prow['median_trades']:.0f} trades/day, Parkinson/OC {prow['Parkinson_sd_ratio']:.3f}, "
      f"zero-range {prow['zero_range_pct']:.2f}%")
print("Cross-market estimator fingerprint  (1.000 = no net friction)\n" + "="*100)
print(fp.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

# ─────────────────────────────────────────────────────── India VIX as an external anchor
vix = pd.read_csv(EXT/"india_vix.csv", parse_dates=["Date"])
vix.columns = ["date","india_vix"]
nf = nifty.copy()
# 21-session volatility must aggregate DAILY VARIANCE first and take the square root last.
# The previous implementation averaged daily sigmas, which is a different smoother and was
# inconsistent with the manuscript's reporting formula (sqrt(A * mean(v_t))).
nf["pk_var"] = R.parkinson(nf.set_index("date")).values.clip(min=0)
nf["cc_ret"] = np.log(nf.close).diff()
nf["pk_21"] = np.sqrt(nf["pk_var"].rolling(21).mean() * 252) * 100
nf["cc_21"] = nf["cc_ret"].rolling(21).std(ddof=1) * np.sqrt(252) * 100
mm = nf.merge(vix, on="date").dropna(subset=["pk_21","cc_21","india_vix"])
anchor = []
for nm, col in [("Parkinson (21d)","pk_21"), ("Close-to-close (21d)","cc_21")]:
    r = sm.OLS(mm.india_vix, sm.add_constant(mm[[col]], has_constant="add")).fit(cov_type="HC1")
    anchor.append({"estimator":nm, "slope on India VIX":r.params.iloc[1],
                   "intercept":r.params.iloc[0], "R2":r.rsquared,
                   "corr":mm.india_vix.corr(mm[col]), "mean level":mm[col].mean()})
an = pd.DataFrame(anchor).set_index("estimator")
an.to_csv(TAB/"table15_vix_anchor.csv")
print(f"\n\nIndia VIX as an external anchor on NIFTY  ({len(mm):,} days)\n" + "="*82)
print(an.to_string(float_format=lambda x: f"{x:,.3f}"))
print(f"\nmean India VIX = {mm.india_vix.mean():.1f}%   "
      f"mean Parkinson = {mm.pk_21.mean():.1f}%   mean close-to-close = {mm.cc_21.mean():.1f}%")

# ─────────────────────────────────────────────────────── FIGURE 12
fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.0))
ax = axes[0]
sub = fp[fp.trades.notna()].sort_values("trades")
ax.axhline(1.0, color=ps.INK_MUTED, lw=1.0)
for e in ["Parkinson","Garman-Klass","Rogers-Satchell"]:   # style keys are plain names
    c, ls, mk = ps.STYLE[e]
    ax.plot(sub.trades, sub[f"{e}_sd_ratio"], color=c, ls=ls, marker=mk, ms=6,
            markeredgecolor=ps.SURFACE, markeredgewidth=1.0, label=f"{e} (NEPSE equity)")
for lbl, colr, mark in [("NIFTY 50 (dense, liquid)", ps.SERIES["green"], "*"),
                        ("NEPSE index (aggregate)",  ps.SERIES["violet"], "P")]:
    v = fp.loc[fp.regime == lbl, "Parkinson_sd_ratio"].iloc[0]
    ax.axhline(v, color=colr, ls=":", lw=1.4)
    ax.annotate(f"{lbl.split(' (')[0]}: {v:.3f}", (sub.trades.min(), v),
                textcoords="offset points", xytext=(2, 4), ha="left",
                fontsize=7.5, color=colr, fontweight="bold",
                bbox=dict(fc=ps.SURFACE, ec="none", pad=1.2))
ax.set_xscale("log"); ps.plain_log_axis(ax, "x")
ax.set_xticks([30, 100, 300])   # a lone "100" left the decade axis unreadable
ax.legend(fontsize=7.2, loc="lower right", frameon=True, facecolor=ps.SURFACE,
          edgecolor="none", framealpha=0.95)
ps.finish(ax, "A. NEPSE equity ratios stay near one", None,
          "Median trades per day (log)", "Range estimator ÷ open-to-close")

ax = axes[1]
ax.plot(mm.date, mm.india_vix, color=ps.SERIES["blue"], lw=0.9, label="India VIX (implied)")
ax.plot(mm.date, mm.pk_21, color=ps.SERIES["orange"], lw=0.9, label="Parkinson, 21d (NIFTY)")
ax.legend(fontsize=7.5)
ps.finish(ax, "B. NIFTY Parkinson vs India VIX", None,
          None, "Annualized volatility (%)")
ps.header(fig, "The same estimator code across three regimes",
          "Range estimators remain usable in NEPSE equity; on NIFTY, the correctly aggregated\n"
          "21-session Parkinson series still co-moves strongly with India VIX.", top=0.83)
for e in ("png","pdf"): fig.savefig(FIG/f"fig12_cross_market.{e}")
plt.close(fig)
print(f"\nwrote fig12_cross_market.png")
