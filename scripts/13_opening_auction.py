"""The opening auction, and what it does to volatility measurement.

NEPSE runs a pre-open call auction (10:30-10:45) with orders restricted to +/-2% of the previous
close, clearing at the volume-maximising price. If no orders match, the open is SET EQUAL to the
previous close.

Three consequences this script establishes:

  1. The +/-2% band is a hard CENSOR on the opening return, visible as truncation and a pile-up
     at the boundary. Latent overnight moves larger than 2% cannot be incorporated at the open.
  2. The no-match rule manufactures r_co == 0 exactly, concentrated in thin securities.
  3. Any claim that "variance migrates overnight" must first exclude the MECHANICAL channel:
     a security trading once has O=H=L=C, so the intraday return is zero by construction and
     the whole daily move is forced into the opening return. That is not price discovery
     migrating; it is intraday variance being unobservable.

Produces Figure 15 and Table 19.
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts")); from _env import bootstrap; bootstrap()
import numpy as np, pandas as pd, matplotlib.pyplot as plt
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.sample import load_sample
from nepsevol.utils import plotstyle as ps
ps.apply(); FIG=ROOT/"output"/"figures"; TAB=ROOT/"output"/"tables"

p=load_sample(ROOT, "equity").sort_values(["symbol","date"])
sess={d:i for i,d in enumerate(sorted(p.date.unique()))}
p["sr"]=p.date.map(sess); p["gap"]=p.groupby("symbol").sr.diff()
p["prev_c"]=p.groupby("symbol").close.shift(1)
d=p[(p.gap==1)&p.prev_c.notna()&(p.prev_c>0)].copy()
d["r_co"]=np.log(d.open/d.prev_c); d["r_oc"]=np.log(d.close/d.open); d["r_cc"]=np.log(d.close/d.prev_c)
d["zero_range"]=(d.high==d.low)
d["dec"]=pd.qcut(d.n_trades,10,labels=False,duplicates="drop")

rows=[]
for b,g in d.groupby("dec"):
    nz=g[~g.zero_range]
    rows.append({"decile":int(b),"median_trades":g.n_trades.median(),
                 "overnight_share_all":g.r_co.var()/g.r_cc.var(),
                 "overnight_share_excl_degenerate":nz.r_co.var()/nz.r_cc.var() if len(nz)>100 else np.nan,
                 "pct_zero_range":100*g.zero_range.mean(),
                 "pct_open_eq_prevclose":100*(g.r_co==0).mean(),
                 "pct_at_2pct_band":100*((g.r_co.abs()>0.019)&(g.r_co.abs()<=0.021)).mean()})
t=pd.DataFrame(rows); t.to_csv(TAB/"table19_opening_auction.csv",index=False)
print("Opening auction and the mechanical channel, by liquidity decile")
print(t.to_string(index=False,float_format=lambda x:f"{x:,.3f}"))

fig,axes=plt.subplots(1,3,figsize=(12.4,3.9))
ax=axes[0]
b=d[d.r_co.abs()>1e-12]
ax.hist(b.r_co.clip(-0.05,0.05)*100,bins=200,color=ps.SERIES["blue"],edgecolor=ps.SURFACE,linewidth=0.2)
for x in (-2,2):
    ax.axvline(x,color=ps.SERIES["red"],ls="--",lw=1.4)
for x in (-5,5):                       # band widened to +/-5% on 2026-04-20; both regimes are plotted
    ax.axvline(x,color=ps.INK_MUTED,ls=":",lw=1.0)
ax.annotate("±2% band\n(to Apr 2026)",(2.15,ax.get_ylim()[1]*0.70),fontsize=7.5,
            color=ps.SERIES["red"],fontweight="bold")
ax.annotate("±5%\nfrom\nApr 2026",(-4.85,ax.get_ylim()[1]*0.55),fontsize=7,color=ps.INK_SOFT)
ps.finish(ax,"A. Opening returns pile up at the pre-open band",None,"ln(Open / prev Close), %","Stock-days")

ax=axes[1]
ax.axhline(0,color=ps.INK_MUTED,lw=0.8)
ax.plot(t.median_trades,t.overnight_share_all*100,color=ps.SERIES["orange"],ls="--",marker="s",
        markeredgecolor=ps.SURFACE,markeredgewidth=0.9,label="all days (inflated)")
ax.plot(t.median_trades,t.overnight_share_excl_degenerate*100,color=ps.SERIES["aqua"],ls="-",marker="o",
        markeredgecolor=ps.SURFACE,markeredgewidth=0.9,label="excluding H=L days")
ax.set_xscale("log"); ps.plain_log_axis(ax,"x"); ax.legend(fontsize=7.5)
ax.annotate("The two series coincide: within ordinary equity\nthere are almost no H=L days to remove.",
            (t.median_trades.iloc[0]*1.15,12),fontsize=7.2,color=ps.INK_SOFT)
ps.finish(ax,"B. Opening share of variance",None,"Median trades/day (log)","Percent of daily variance")

ax=axes[2]
ax.plot(t.median_trades,t.pct_open_eq_prevclose,color=ps.SERIES["violet"],marker="v",
        markeredgecolor=ps.SURFACE,markeredgewidth=0.9,label="open = prev close (no match)")
ax.plot(t.median_trades,t.pct_at_2pct_band,color=ps.SERIES["red"],marker="D",
        markeredgecolor=ps.SURFACE,markeredgewidth=0.9,label="open in (1.9%, 2.1%]")
ax.set_xscale("log"); ps.plain_log_axis(ax,"x"); ax.legend(fontsize=7.5)
ps.finish(ax,"C. Auction outcomes by liquidity",None,"Median trades/day (log)","Percent of stock-days")
ps.header(fig,"NEPSE's pre-open call auction is visible in the data",
          "Orders may be placed only within a band of the previous close; if none match, the open is set to that close.\n"
          "Both rules leave clear fingerprints. The band widened from ±2% to ±5% on 2026-04-20; both regimes are shown.",top=0.84)
for e in ("png","pdf"): fig.savefig(FIG/f"fig15_opening_auction.{e}")
plt.close(fig); print("\nwrote fig15_opening_auction.png")
