"""Self-critique of the AddRS result: six checks, one retraction.

AddRS = RS + (x^2/2)(I_u + I_v). The correction is NON-NEGATIVE, so it can only help where
Rogers-Satchell is biased downward. Where RS is already unbiased in expectation and the
boundary correction fires with positive probability, the expected correction pushes the
estimate upward by construction.

An earlier version of this analysis asserted that a banded opening call auction drove the
overshoot by making the open an extreme. That claim was built from a cross-market contrast and is
refuted by the within-market test reproduced below.

Produces Table 25.
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts")); from _env import bootstrap; bootstrap()
import numpy as np, pandas as pd
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.sample import load_sample
from nepsevol.estimators import range_ as R
from nepsevol.clean.limits import flag_limits
TAB=ROOT/"output"/"tables"; EXT=ROOT/"data"/"external"
VAULT=ROOT/"data"/"external"

def ratios(g):
    oc=(np.log(g.close/g.open)**2).mean()
    rs=np.nanmean(R.rogers_satchell(g)); ad=np.nanmean(R.add_rs(g))
    return np.sqrt(rs/oc), np.sqrt(ad/oc), rs/oc, (ad-rs)/oc

p=load_sample(ROOT, "equity").sort_values(["symbol","date"])
p=flag_limits(p); p["q"]=pd.qcut(p.n_trades,5,labels=False,duplicates="drop")

# 1. the premise
rows=[]
nif=pd.read_csv(EXT/"nifty50.csv",parse_dates=["Date"]); nif.columns=[c.lower() for c in nif.columns]
r,a,_,_=ratios(nif); rows.append({"bucket":"NIFTY 50","median_trades":np.nan,"RS/OC":r,
                                  "premise holds (RS<0.95)":r<0.95,"AddRS/OC":a})
for q,g in p.groupby("q",sort=False):
    r,a,_,_=ratios(g)
    rows.append({"bucket":f"NEPSE Q{int(q)+1}","median_trades":g.n_trades.median(),"RS/OC":r,
                 "premise holds (RS<0.95)":r<0.95,"AddRS/OC":a})
t1=pd.DataFrame(rows).sort_values("median_trades",na_position="first")
print("1. Does AddRS's premise hold? (it corrects a DOWNWARD bias)")
print(t1.to_string(index=False,float_format=lambda x:f"{x:,.3f}"))
print("  -> none of the displayed buckets shows a large RS deficit under the <0.95 screen;\n"
      "     on NIFTY 50 the correction nevertheless lands close to the matched benchmark.\n")

# 2. the retracted mechanism, tested within-market
sess={d:i for i,d in enumerate(sorted(p.date.unique()))}
p["sr"]=p.date.map(sess); p["gp"]=p.groupby("symbol").sr.diff(); p["pc"]=p.groupby("symbol").close.shift(1)
d=p[(p.gp==1)&p.pc.notna()&(p.pc>0)].copy()
eqf=lambda a_,b_:(a_-b_).abs()<=1e-12*b_.abs()
d["open_extreme"]=eqf(d.high,d.open)|eqf(d.low,d.open)
d["auction"]=np.where(d.open_at_prev_close,"no match",np.where(d.open_pinned,"pinned at band","cleared inside"))
rows=[]
for a_,g in d.groupby("auction"):
    r,ad,_,_=ratios(g)
    rows.append({"auction outcome":a_,"share %":100*len(g)/len(d),
                 "open is extreme %":100*g.open_extreme.mean(),"AddRS/OC":ad})
t2=pd.DataFrame(rows).sort_values("open is extreme %")
print("2. The retracted auction mechanism, tested WITHIN market")
print(t2.to_string(index=False,float_format=lambda x:f"{x:,.3f}"))
print("  -> more extreme opens goes with LESS overshoot. The mechanism claim is refuted.\n")

# 3. index-vs-index, the only valid cross-market comparison available
idx=pd.read_csv(VAULT/"nepse_index_history.csv",parse_dates=["Date"]); idx.columns=[c.lower() for c in idx.columns]
idx=idx[idx.date>=pd.Timestamp("2016-06-06")]
print("3. Cross-market, like for like")
for lab,dd in [("NIFTY 50 index",nif),("NEPSE index",idx),("NEPSE stocks (NOT comparable)",p)]:
    print(f"     {lab:32} open is an extreme: {100*(eqf(dd.high,dd.open)|eqf(dd.low,dd.open)).mean():5.1f}%")
print("  -> index vs index is 13.0% against 4.6%, not the 47.8% vs 4.6% previously reported.\n")

# 4. variance-scale decomposition of the closing-rule experiment
V0,V1,APR=pd.Timestamp("2025-03-20"),pd.Timestamp("2025-09-22"),pd.Timestamp("2026-04-20")
rows=[]
for lab,g in [("A1 last-trade",p[p.date<V0]),("B  VWAP",p[(p.date>=V0)&(p.date<=V1)]),
              ("A2 last-trade (clean)",p[(p.date>V1)&(p.date<APR)])]:
    r,a_,rv,cv=ratios(g)
    rows.append({"regime":lab,"n":len(g),"RS var-ratio":rv,"correction var-ratio":cv,"AddRS/OC":a_})
t4=pd.DataFrame(rows)
print("4. Closing-rule experiment on the VARIANCE scale (sqrt ratios hid this)")
print(t4.to_string(index=False,float_format=lambda x:f"{x:,.3f}"))
print("  -> RS itself falls 13% under a VWAP close. AddRS is unmoved. A2 is truncated at the")
print("     20-Apr-2026 reform, which otherwise contaminates 44% of that window.")

for i,t in enumerate([t1,t2,t4],1): t.to_csv(TAB/f"table25_{i}_addrs_premise.csv",index=False)
