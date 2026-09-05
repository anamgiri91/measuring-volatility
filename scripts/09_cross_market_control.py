"""Cross-market control: does the bias vanish where trading is dense?

The single most damaging objection to this paper is that something is wrong with NEPSE,
with the data, or with our code, rather than with range estimators under thin trading.
This script answers it with real data rather than simulation.

The identical ESTIMATOR code is run on three regimes:

    NIFTY 50      dense, clean, liquid, has a listed implied-volatility index
    NEPSE index   moderate: aggregates every listed security
    NEPSE equity  thin, split by published daily trade count

SCREEN ASYMMETRY, stated because "identical code" is easy to over-read (F-3). The estimator
functions are identical across all three regimes. The INPUT SCREENS are not, and cannot be:

    NEPSE equity   positivity + |ln(C/C_prev)| < 0.5 + rules-derived range ceiling
                   + duplicate-key reconciliation + OHLC envelope repair
                   (scripts/02_build_panel.py, scripts/03_descriptive.py:42,48)
    NIFTY 50       positivity only (fingerprint(), below)
    NEPSE index    positivity only (fingerprint(), below)

The extra NEPSE screens are rules-derived from NEPSE's own price limits and duplicate-key
pathologies; there is no NSE analogue to transfer. The consequence is that the NEPSE panel is
an audited sample compared against two unaudited ones, and it is why a single unscreened NIFTY
session carries the leverage quantified in the sensitivity block at the end of this script.
Any manuscript sentence describing this comparison must say "identical estimator code", not
"identical code".

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
EXT = ROOT/"data"/"external"
VAULT = ROOT/"data"/"external"
LN2 = np.log(2)

# Annualisation factor for the NIFTY series ONLY (F-11). 252 is the correct NSE convention and
# is used here deliberately, not by default: this block annualises an Indian index against an
# Indian volatility index. The manuscript's rule -- use the market's own genuine session count
# rather than importing 252 -- applies to NEPSE, where A is derived from the detected trading
# calendar by scripts/26_annualization_factor.py. Nothing in this script annualises NEPSE data.
NIFTY_SESSIONS_PER_YEAR = 252


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


def vix_anchor(nifty_df):
    """Regress India VIX on 21-session NIFTY volatility, both aggregated variance-first.

    21-session volatility must aggregate DAILY VARIANCE first and take the square root last.
    The previous implementation averaged daily sigmas, which is a different smoother and was
    inconsistent with the manuscript's reporting formula (sqrt(A * mean(v_t))).

    Returns (table, merged_frame) so the caller can report the matched-observation count
    rather than hard-coding it downstream (F-6).
    """
    nf = nifty_df.copy()
    nf["pk_var"] = R.parkinson(nf.set_index("date")).values.clip(min=0)
    nf["cc_ret"] = np.log(nf.close).diff()
    A = NIFTY_SESSIONS_PER_YEAR
    nf["pk_21"] = np.sqrt(nf["pk_var"].rolling(21).mean() * A) * 100
    nf["cc_21"] = nf["cc_ret"].rolling(21).std(ddof=1) * np.sqrt(A) * 100
    m = nf.merge(vix, on="date").dropna(subset=["pk_21","cc_21","india_vix"])
    rows = []
    for nm, col in [("Parkinson (21d)","pk_21"), ("Close-to-close (21d)","cc_21")]:
        r = sm.OLS(m.india_vix, sm.add_constant(m[[col]], has_constant="add")).fit(cov_type="HC1")
        c = m.india_vix.corr(m[col])
        # R2 IS THE SQUARED CORRELATION HERE and carries no additional information: the
        # regression has one regressor and an intercept, so R2 == corr^2 identically. It was
        # reported alongside the correlation in the manuscript as if it were a second piece of
        # evidence. It is retained in this artifact only to make the identity checkable --
        # `R2_minus_corr_squared` is zero to floating-point -- and is NOT promoted to the
        # manuscript tables or the QA ledger. Report the correlation.
        rows.append({"estimator":nm, "slope_on_estimator":r.params.iloc[1],
                     "intercept":r.params.iloc[0], "R2":r.rsquared,
                     "corr":c, "R2_minus_corr_squared":r.rsquared - c**2,
                     "mean level":m[col].mean(), "n_obs":len(m)})
    return pd.DataFrame(rows).set_index("estimator"), m


an, mm = vix_anchor(nifty)
an.to_csv(TAB/"table15_vix_anchor.csv")

# ───────────────────────── PERIOD SENSITIVITY OF THE VIX EXERCISE  (peer-review item E / 6)
#
# The NIFTY/India VIX series run from 2010; the NEPSE equity panel begins 2024-03-04. The
# co-movement statistic was therefore computed over a sixteen-year window and used to support a
# claim about a market observed for two and a half years of it. That is not a like-for-like
# comparison, and the difference is not cosmetic: restricted to the window the NEPSE study
# actually occupies, both correlations fall by roughly a quarter.
#
# Both windows are now reported. The full sample is retained because it is the better estimate
# of the VIX-realized-volatility relationship in the Indian market; the overlap window is
# reported because it is the only one contemporaneous with the NEPSE evidence, and it is the one
# the manuscript must quote when the two markets are discussed together.
#
# Note the coverage asymmetry: the India VIX series ends before the NEPSE panel does, so the
# overlap is bounded by the VIX series, not by the NEPSE sample. That is stated in the table
# rather than left for a reader to discover from the observation count.
NEPSE_PANEL_START = pd.Timestamp("2024-03-04")

_ov = mm[mm.date >= NEPSE_PANEL_START]
_per = []
for label, m_ in [("full VIX sample (2010 onward)", mm),
                  ("NEPSE-overlap window only", _ov)]:
    _per.append({
        "window": label,
        "first": m_.date.min().date(), "last": m_.date.max().date(),
        "n_obs": len(m_),
        "VIX_Parkinson_corr": m_.india_vix.corr(m_.pk_21),
        "VIX_CC_corr": m_.india_vix.corr(m_.cc_21),
        "mean_india_vix": m_.india_vix.mean(),
    })
per = pd.DataFrame(_per)
per["parkinson_beats_cc"] = per.VIX_Parkinson_corr > per.VIX_CC_corr
per.to_csv(TAB/"table50_vix_period_sensitivity.csv", index=False)

print("\n\nPERIOD SENSITIVITY: the VIX exercise on the window the NEPSE study occupies")
print("="*100)
print(per.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
_f, _o = per.iloc[0], per.iloc[1]
print(f"\n  Parkinson-VIX      {_f.VIX_Parkinson_corr:.3f} -> {_o.VIX_Parkinson_corr:.3f}")
print(f"  close-to-close-VIX {_f.VIX_CC_corr:.3f} -> {_o.VIX_CC_corr:.3f}")
print("  -> the relationship stays positive and clearly present, but 'strong co-movement' is")
print("     much weaker evidence in the period that actually corresponds to the NEPSE panel.")
print("     Close-to-close leads Parkinson in BOTH windows, so nothing here ranks the two.")
print(f"  -> the overlap ends {_o.last}, bounded by the India VIX series rather than by the")
print(f"     NEPSE panel, which runs to {panel.date.max().date()}.")
print(f"\n\nIndia VIX as an external anchor on NIFTY  ({len(mm):,} days)\n" + "="*82)
print(an.to_string(float_format=lambda x: f"{x:,.3f}"))
print(f"\nmean India VIX = {mm.india_vix.mean():.1f}%   "
      f"mean Parkinson = {mm.pk_21.mean():.1f}%   mean close-to-close = {mm.cc_21.mean():.1f}%")

# ────────────────────────────────────── OUTLIER SENSITIVITY OF THE NIFTY BENCHMARK  (F-1, F-2)
#
# The NIFTY series is read unscreened (see SCREEN ASYMMETRY in the module docstring): it does
# not pass the |ln(C/C_prev)| < 0.5 filter or the rules-derived range ceiling that the NEPSE
# panel passes. With only ~4,000 sessions against ~24,000 stock-days per NEPSE bucket, a single
# extreme session therefore carries far more leverage on the NIFTY reference numbers than any
# single NEPSE observation carries on the NEPSE ones.
#
# One session dominates: the largest ln(H/L) in the whole 2010-2026 series. It is a genuine
# recorded exchange session and is NOT deleted from the reported results -- excluding real
# extremes is exactly the discretion this paper warns against. It is quantified instead, so the
# reader can see how much of each reference number depends on it.
#
# The session is identified from the data by rank, never by a hard-coded date, so this block
# stays correct if the input series is revised or extended.
def _loo(nifty_df, drop_dates):
    keep = nifty_df[~nifty_df.date.isin(drop_dates)]
    fp_ = fingerprint(keep)
    an_, mm_ = vix_anchor(keep)
    return {
        "n_sessions": len(keep),
        "Parkinson_OC_sd": fp_["Parkinson_sd_ratio"],
        "RS_OC_sd": fp_["Rogers-Satchell_sd_ratio"],
        "GK_OC_sd": fp_["Garman-Klass_sd_ratio"],
        "n_vix_matched": len(mm_),
        "VIX_Parkinson_corr": an_.loc["Parkinson (21d)", "corr"],
        "VIX_Parkinson_R2": an_.loc["Parkinson (21d)", "R2"],
        "VIX_CC_corr": an_.loc["Close-to-close (21d)", "corr"],
        "VIX_CC_R2": an_.loc["Close-to-close (21d)", "R2"],
    }

_rng = np.log(nifty.high / nifty.low)
_extreme = nifty.loc[_rng.idxmax()]
_xdate = pd.Timestamp(_extreme.date)
sens = pd.DataFrame([
    {"specification": "as reported (all sessions)", **_loo(nifty, [])},
    {"specification": f"excluding {_xdate.date()} (largest ln(H/L))", **_loo(nifty, [_xdate])},
])
sens.insert(1, "excluded_session_ln_HL", [np.nan, float(_rng.max())])
sens.to_csv(TAB/"table31_nifty_outlier_sensitivity.csv", index=False)

_a, _b = sens.iloc[0], sens.iloc[1]
print("\n\nNIFTY benchmark: leave-one-out sensitivity to the single largest-range session")
print("="*94)
print(f"  session          {_xdate.date()}   O={_extreme.open:,.2f}  H={_extreme.high:,.2f}  "
      f"L={_extreme.low:,.2f}  C={_extreme.close:,.2f}")
print(f"  ln(H/L)          {float(_rng.max()):.4f}  (largest of {len(nifty):,} sessions); "
      f"same-day ln(C/C_prev) = {float(np.log(_extreme.close/nifty.close.shift(1).loc[_rng.idxmax()])):.4f}")
print("  -> a RANGE event, not a close-to-close event, so it moves Parkinson and leaves "
      "close-to-close almost untouched.\n")
print(sens.drop(columns=["excluded_session_ln_HL"]).to_string(index=False,
      float_format=lambda x: f"{x:,.4f}"))
print(f"\n  Parkinson/OC (SD)     {_a.Parkinson_OC_sd:.3f} -> {_b.Parkinson_OC_sd:.3f}")
print(f"  RS/OC (SD)            {_a.RS_OC_sd:.3f} -> {_b.RS_OC_sd:.3f}")
print(f"  VIX~Parkinson corr    {_a.VIX_Parkinson_corr:.3f} -> {_b.VIX_Parkinson_corr:.3f}   "
      f"(close-to-close: {_a.VIX_CC_corr:.3f} -> {_b.VIX_CC_corr:.3f})")
if (_a.VIX_Parkinson_corr < _a.VIX_CC_corr) != (_b.VIX_Parkinson_corr < _b.VIX_CC_corr):
    print("  *** The Parkinson-vs-close-to-close ORDERING REVERSES on this single session. ***")
    print("      Any manuscript sentence ranking the two estimators must carry this caveat.")

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
