"""The composition warning: a frontier "liquidity gradient" that is really an asset-class gradient.

NEPSE, like many frontier exchanges, publishes one daily file covering every listed instrument and
carries no instrument-type field. Sorting that file by trading intensity and calling the result a
liquidity cross-section produces a strong, clean, entirely spurious gradient: the thin end is
corporate debentures, closed-end funds, and restricted promoter shares, not thin equities.

Restricted to ordinary common equity the gradient disappears -- participation is 1.000 in every
quintile and RS/Var(x) stays near one.

Produces Figure 21 (the paper's methodological centrepiece) and Table 27.
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); from _env import bootstrap; bootstrap()

import numpy as np, pandas as pd, matplotlib.pyplot as plt
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.sample import load_sample
from matplotlib.patches import Patch
from nepsevol.utils import plotstyle as ps

ps.apply()
FIG = ROOT / "output" / "figures"; TAB = ROOT / "output" / "tables"

TYPES  = ["equity", "promoter", "debenture", "fund"]
TLABEL = {"equity": "Ordinary equity", "promoter": "Promoter share",
          "debenture": "Corporate debenture", "fund": "Closed-end fund"}
TCOL   = {"equity": ps.SERIES["blue"], "promoter": ps.SERIES["yellow"],
          "debenture": ps.SERIES["orange"], "fund": ps.SERIES["aqua"]}


def quintiles(df):
    liq = df.groupby("symbol").n_trades.median()
    b = (pd.qcut(liq, 5, labels=False, duplicates="drop") + 1)
    return df.assign(q=df.symbol.map(b))


def profile(df, sessions):
    """Per-quintile participation, P(H=L) and RS/Var(x)."""
    span = df.groupby("symbol").date.agg(["min", "max"])
    listed = {s: int(((sessions >= a) & (sessions <= b)).sum())
              for s, a, b in zip(span.index, span["min"], span["max"])}
    part = (df.groupby("symbol").size() / pd.Series(listed)).clip(upper=1.0)
    out = []
    for q, g in df.groupby("q", sort=True):
        o, h, l, c = (np.log(g[k].values) for k in ("open", "high", "low", "close"))
        u, d, x = h - o, l - o, c - o
        rs = u * (u - x) + d * (d - x)
        out.append(dict(q=int(q), securities=g.symbol.nunique(), rows=len(g),
                        participation=part[g.symbol.unique()].median(),
                        trades=g.n_trades.median(),
                        p_hl=(g.high.values == g.low.values).mean(),
                        ratio=rs.mean() / x.var(ddof=1)))
    return pd.DataFrame(out)


full = load_sample(ROOT, "full")
eq   = pd.read_parquet(ROOT / "data/processed/equity_sample.parquet")
sessions = pd.Series(sorted(full.date.unique()))

full_q, eq_q = quintiles(full), quintiles(eq)
pf, pe = profile(full_q, sessions), profile(eq_q, sessions)

comp = (full_q.groupby("symbol").agg(q=("q", "first"), t=("sec_type", "first"))
        .pipe(lambda d: pd.crosstab(d.q, d.t)).reindex(columns=TYPES, fill_value=0))
share = comp.div(comp.sum(1), axis=0)

tab = pf.assign(universe="full").merge(pe.assign(universe="equity"), how="outer")
tab.to_csv(TAB / "table27_universe_composition.csv", index=False)

print("=== FULL universe (every listed instrument) ===")
print(pf.to_string(index=False, formatters={"participation": "{:.3f}".format,
      "trades": "{:.0f}".format, "p_hl": "{:.1%}".format, "ratio": "{:.3f}".format}))
print("\n=== ORDINARY EQUITY only ===")
print(pe.to_string(index=False, formatters={"participation": "{:.3f}".format,
      "trades": "{:.0f}".format, "p_hl": "{:.1%}".format, "ratio": "{:.3f}".format}))
print("\n=== instrument composition of the full-universe quintiles ===")
print(comp.to_string())
print(f"\nQ1 non-equity: {1 - share.loc[1,'equity']:.1%}   Q2 non-equity: {1 - share.loc[2,'equity']:.1%}")

# ------------------------------------------------------------------------------ FIGURE 21
fig = plt.figure(figsize=(7.8, 6.4))
gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], hspace=0.62, wspace=0.32,
                      left=0.085, right=0.955, top=0.775, bottom=0.205)
axA, axB, axC = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])

for ax, col, ylab, ttl, fmt in [
        (axA, "p_hl", "Share of stock-days with H = L", "A.  The estimator's failure rate", "pct"),
        (axB, "ratio", "RS ÷ Var(x)", "B.  Rogers–Satchell against its own target", "num")]:
    ax.plot(pf.q, pf[col], color=ps.SERIES["orange"], marker="s", lw=2.0, ms=7,
            markeredgecolor=ps.SURFACE, markeredgewidth=1.0, label="Every listed instrument")
    ax.plot(pe.q, pe[col], color=ps.SERIES["blue"], marker="o", lw=2.0, ms=7,
            markeredgecolor=ps.SURFACE, markeredgewidth=1.0, label="Ordinary equity only")
    if col == "ratio":
        ax.axhline(1.0, color=ps.INK_MUTED, lw=1.0, zorder=0)
        ax.annotate("unbiased", (0.985, 1.0), xycoords=("axes fraction", "data"),
                    fontsize=7, color=ps.INK_MUTED, va="bottom", ha="right")
    if fmt == "pct":
        ax.set_yticks([0, .15, .30, .45, .60])
        ax.set_yticklabels([f"{v:.0%}" for v in (0, .15, .30, .45, .60)])
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(["Q1\nthinnest", "Q2", "Q3", "Q4", "Q5\ndeepest"], fontsize=7.5)
    ps.finish(ax, ttl, None, None, ylab)

axA.legend(fontsize=7.5, loc="upper right", frameon=False)
# Both labels are read off the data, never typed: an earlier draft carried a hardcoded
# "59.6%" that survived the OHLC-repair rebuild and contradicted its own panel.
axA.annotate(f"{pf.p_hl.iloc[0]:.1%}", (1, pf.p_hl.iloc[0]),
             textcoords="offset points", xytext=(16, -6), fontsize=7.2,
             color=ps.SERIES["orange"], fontweight="bold")
axA.annotate(f"{pe.p_hl.iloc[0]:.1%}", (1, pe.p_hl.iloc[0]), textcoords="offset points",
             xytext=(8, 8), fontsize=7.2, color=ps.SERIES["blue"], fontweight="bold")

bottom = np.zeros(len(share))
for t in TYPES:
    axC.bar(share.index, share[t], bottom=bottom, width=0.62, color=TCOL[t],
            edgecolor=ps.SURFACE, linewidth=1.6, label=TLABEL[t])
    for q, v, b in zip(share.index, share[t], bottom):
        if v > 0.085:
            axC.text(q, b + v / 2, f"{comp.loc[q, t]}", ha="center", va="center",
                     fontsize=7.4, color=ps.SURFACE, fontweight="bold")
    bottom += share[t].values
axC.set_ylim(0, 1.0); axC.set_yticks([0, .25, .50, .75, 1.0])
axC.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
axC.set_xticks([1, 2, 3, 4, 5])
axC.set_xticklabels(["Q1\nthinnest", "Q2", "Q3", "Q4", "Q5\ndeepest"], fontsize=7.5)
axC.legend(fontsize=7.5, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.78), frameon=False)
ps.finish(axC, "C.  What is actually in each quintile", None, None, "Share of securities")
# The equity sliver in Q1 is 1 of 152 securities -- far too thin to label in place, and a leader
# line to it would cross the bar. The counts are written under the axis instead, in the series
# colour, so they read against the legend without a pointer.
for q in share.index:
    axC.annotate(f"{comp.loc[q, 'equity']}", xy=(q, 0), xycoords=("data", "axes fraction"),
                 xytext=(0, -30), textcoords="offset points", ha="center", va="top",
                 fontsize=8.6, color=TCOL["equity"], fontweight="bold", annotation_clip=False)
axC.annotate("ordinary equities in the quintile", xy=(0.5, 0), xycoords="axes fraction",
             xytext=(0, -47), textcoords="offset points", ha="center", va="top",
             fontsize=7.4, color=ps.INK_SOFT, annotation_clip=False)

ps.header(fig, "A frontier liquidity gradient that is really an asset-class gradient",
          "NEPSE publishes one daily file for every listed instrument and no instrument-type field. Sorting it by\n"
          "trading intensity yields a strong, clean, spurious gradient: the thin end is debentures, closed-end funds\n"
          "and restricted promoter shares. Within ordinary equity the gradient is absent.", top=0.775)
for e in ("png", "pdf"):
    fig.savefig(FIG / f"fig21_universe_composition.{e}")
plt.close(fig)
print(f"\nwrote {FIG/'fig21_universe_composition.png'}")
