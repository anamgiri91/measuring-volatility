"""Does AddRS repair the finite-sampling failure as trading becomes ultra-thin?

This is the experiment that determines what the paper is. Rogers-Satchell is exactly zero on
15.2% of NEPSE stock-days, and 59.6% of those are MONOTONE rather than degenerate -- which is
precisely the case AddRS (Kumar & Maheswaran 2014) is built to repair, since it substitutes the
squared open-to-close return whenever the observed extremes coincide with the open and close.

Three outcomes, all publishable:
  A  AddRS/OC ~ 1 throughout       -> the finite-sampling correction works even at extreme
                                      thinness; the paper's remaining contribution is scope and
                                      institutional censoring, not estimator failure.
  B  AddRS improves RS but degrades -> the correction extends the usable range and then fails,
                                      which locates the boundary. Strongest outcome.
  C  AddRS pathological when thin   -> investigate the mechanism before calling it failure.

Produces Figure 18 and Table 23.
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts")); from _env import bootstrap; bootstrap()
import numpy as np, pandas as pd, matplotlib.pyplot as plt
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.sample import load_sample
from nepsevol.utils import plotstyle as ps
from nepsevol.estimators import range_ as R
ps.apply(); FIG=ROOT/"output"/"figures"; TAB=ROOT/"output"/"tables"
EXT=ROOT.parent/"private"/"data-vault"/"raw"/"external"

def block(df, label, trades=np.nan):
    d=df[(df[["open","high","low","close"]]>0).all(axis=1)].copy()
    oc=(np.log(d.close/d.open)**2).mean()
    out={"regime":label,"median_trades":trades,"n":len(d),
         "P(H=L) %":100*(d.high==d.low).mean()}
    for nm,fn in [("Parkinson",R.parkinson),("RS",R.rogers_satchell),("AddRS",R.add_rs)]:
        m=np.nanmean(np.asarray(fn(d),dtype=float))
        out[f"{nm}/OC"]=np.sqrt(m/oc) if m>0 and oc>0 else np.nan
    out["RS==0 %"]=100*(np.abs(np.asarray(R.rogers_satchell(d),dtype=float))<=1e-15).mean()
    return out

nifty=pd.read_csv(EXT/"nifty50.csv",parse_dates=["Date"]); nifty.columns=[c.lower() for c in nifty.columns]
panel=load_sample(ROOT, "equity")
panel["q"]=pd.qcut(panel.n_trades,5,labels=False,duplicates="drop")

rows=[block(nifty,"NIFTY 50 index")]
for q,g in panel.groupby("q", sort=False):
    rows.append(block(g,f"NEPSE Q{int(q)+1}",g.n_trades.median()))
t=pd.DataFrame(rows).sort_values("median_trades",na_position="first")
t.to_csv(TAB/"table23_addrs_benchmark.csv",index=False)

cols=["regime","median_trades","n","Parkinson/OC","RS/OC","AddRS/OC","RS==0 %","P(H=L) %"]
print("Does AddRS repair the finite-sampling failure?  (1.000 = matches the intraday benchmark)")
print("="*102)
print(t[cols].to_string(index=False,float_format=lambda x:f"{x:,.3f}"))

thin=t[t.regime=="NEPSE Q1"].iloc[0]; dense=t[t.regime=="NEPSE Q5"].iloc[0]
print(f"\n  ultra-thin  (median {thin.median_trades:.0f} trades):  RS/OC {thin['RS/OC']:.3f}  →  "
      f"AddRS/OC {thin['AddRS/OC']:.3f}   (RS exactly zero on {thin['RS==0 %']:.1f}% of days)")
print(f"  dense       (median {dense.median_trades:.0f} trades):  RS/OC {dense['RS/OC']:.3f}  →  "
      f"AddRS/OC {dense['AddRS/OC']:.3f}")
nif=t[t.regime=="NIFTY 50 index"].iloc[0]
print(f"  NIFTY 50                       :  RS/OC {nif['RS/OC']:.3f}  →  AddRS/OC {nif['AddRS/OC']:.3f}")

fig,axes=plt.subplots(1,2,figsize=(10.4,4.0))
ax=axes[0]
sub=t[t.median_trades.notna()]
ax.axhline(1.0,color=ps.INK_MUTED,lw=.9)
for nm,key,colr,mk in [("Parkinson","Parkinson/OC",ps.SERIES["orange"],"s"),
                       ("Rogers–Satchell","RS/OC",ps.SERIES["yellow"],"D"),
                       ("AddRS (corrected)","AddRS/OC",ps.SERIES["aqua"],"o")]:
    ax.plot(sub.median_trades,sub[key],color=colr,marker=mk,ms=7,lw=1.8,
            markeredgecolor=ps.SURFACE,markeredgewidth=1.0,label=nm)
for key,colr,lab in [("RS/OC",ps.SERIES["yellow"],"RS"),("AddRS/OC",ps.SERIES["aqua"],"AddRS")]:
    ax.axhline(nif[key],color=colr,ls=":",lw=1.2)
ax.annotate("NIFTY 50 reference lines",(sub.median_trades.min(),nif["AddRS/OC"]),
            textcoords="offset points",xytext=(2,5),ha="left",fontsize=7,color=ps.INK_SOFT,
            bbox=dict(fc=ps.SURFACE,ec="none",pad=1.2))
ax.set_xscale("log"); ps.plain_log_axis(ax,"x")
ax.set_xticks([30,100,300])   # a lone "100" left the decade axis unreadable
ax.legend(fontsize=7.5,loc="upper right",frameon=True,facecolor=ps.SURFACE,
          edgecolor="none",framealpha=0.95)
ps.finish(ax,"A. Does the correction hold as trading thins?",None,
          "Median trades per day (log)","Estimator ÷ open-to-close")
ax=axes[1]
ax.plot(sub.median_trades,sub["RS==0 %"],color=ps.SERIES["yellow"],marker="D",ms=7,
        markeredgecolor=ps.SURFACE,markeredgewidth=1.0,label="RS exactly zero")
ax.plot(sub.median_trades,sub["P(H=L) %"],color=ps.SERIES["violet"],marker="v",ms=7,
        markeredgecolor=ps.SURFACE,markeredgewidth=1.0,label="H = L (zero range)")
ax.set_xscale("log"); ps.plain_log_axis(ax,"x")
ax.set_xticks([30,100,300])
ax.legend(fontsize=7.5)
ps.finish(ax,"B. What AddRS is repairing",None,"Median trades per day (log)","Percent of stock-days")
ps.header(fig,"AddRS against Rogers–Satchell across the liquidity range",
          "AddRS substitutes the squared open-to-close return whenever the observed extremes coincide with "
          "the open and close.\nPanel B shows the gap it targets: RS is exactly zero far more often than the "
          "range is degenerate.",top=0.82)
for e in ("png","pdf"): fig.savefig(FIG/f"fig18_addrs_benchmark.{e}")
plt.close(fig); print("\nwrote fig18_addrs_benchmark.png")
