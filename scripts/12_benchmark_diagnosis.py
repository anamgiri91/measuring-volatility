"""Diagnosing the reported downward bias of Rogers-Satchell.

Maheswaran & Kumar (2013) report VRatio = RS / "usual" = 0.82 on the Nifty index and attribute
the shortfall to the random-walk (discrete-step) effect, motivating their ABC correction.

Rogers-Satchell is an OPEN-TO-CLOSE estimator: it is built from log(H/O), log(L/O) and log(C/O)
and cannot, by construction, see the overnight gap. The "usual" estimator is the variance of
CLOSE-TO-CLOSE returns and spans the full calendar day. Any ratio between them therefore mixes
two distinct things: discretisation bias, and the share of daily variance that occurs overnight.

This script separates them exactly:  RS/CC = (RS/OC) x (OC/CC).

Produces Figure 14 and Table 18.
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
from _env import bootstrap
bootstrap()
import numpy as np, pandas as pd, matplotlib.pyplot as plt
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.sample import load_sample
from nepsevol.estimators.ratios import variance_ratio, assert_same_scale
from nepsevol.inference import weighted_stat_ci, weighted_var
from nepsevol.utils import plotstyle as ps
ps.apply()
N_BOOT, SEED = 1000, 20260901   # same convention as scripts/26_robustness.py
EXT=ROOT/"data"/"external"
VAULT=ROOT/"data"/"external"
FIG=ROOT/"output"/"figures"; TAB=ROOT/"output"/"tables"

def decompose(df, label, panel=False):
    """panel=True: close-to-close and overnight must be computed WITHIN security.
    Differencing a pooled panel differences across securities and is meaningless."""
    d=df[(df[["open","high","low","close"]]>0).all(axis=1)].copy()
    d=d.sort_values(["symbol","date"]) if panel else d.sort_values("date")
    o,h,l,c=np.log(d.open),np.log(d.high),np.log(d.low),np.log(d.close)
    # A-005 EXTENSION. rs is kept as a SERIES here, not collapsed to a mean yet. The original
    # code averaged it at this point -- over every row of d -- while the denominators below are
    # restricted to strictly consecutive sessions. RS/open-to-close was therefore a ratio of two
    # different samples. On the dense group that moved the published figure from 1.021 to 1.059
    # and on the thin group from 1.004 to 0.998, i.e. across one. The A-005 note below already
    # stated the same-rows principle for r_cc/r_on/r_oc; rs simply escaped it by being computed
    # nineteen lines earlier. Collapse it AFTER the ok_all mask, with everything else.
    rs_daily=((h-o)*((h-o)-(c-o))+(l-o)*((l-o)-(c-o)))
    if panel:
        # Restrict to strictly consecutive TRADING SESSIONS. Otherwise a thin security's
        # "overnight" return spans however many days since it last traded (mean 4.3 days in
        # the thin sixth), which mechanically inflates overnight variance.
        sess={dt:i for i,dt in enumerate(sorted(d.date.unique()))}
        sr=d.date.map(sess)
        gap=sr.groupby(d.symbol).diff()
        prev_c=np.log(d.groupby("symbol").close.shift(1))
        r_cc=(c-prev_c).where(gap==1); r_on=(o-prev_c).where(gap==1)
    else:
        r_cc=c.diff(); r_on=(o-c.shift(1))
    r_oc=(c-o)
    r_co = r_on
    # A-005 FIX. Var(cc) = Var(co) + Var(oc) + 2Cov(co,oc) holds only if all four moments
    # are computed on THE SAME rows. r_cc and r_on are restricted to consecutive sessions
    # via .where(gap==1); r_oc previously was not, so v_oc used a larger sample than the
    # rest and the identity failed to close by up to 11% on the panel rows (it closed on
    # the index rows only because they take the non-panel path). Restrict all four here.
    ok_all = r_cc.notna() & r_on.notna() & r_oc.notna()
    r_cc, r_on, r_oc = r_cc[ok_all], r_on[ok_all], r_oc[ok_all]
    rs_daily = rs_daily[ok_all]          # same rows as every denominator (A-005 extension)
    rs = rs_daily.mean()
    r_co = r_on
    v_cc,v_oc,v_on=r_cc.var(),r_oc.var(),r_on.var()
    # Var(cc) = Var(co) + Var(oc) + 2 Cov(co, oc). The covariance term is NOT optional: without
    # it, Var(oc)/Var(cc) is not a variance "share" and can exceed 1, as it does for dense
    # securities here. Report all three components.
    cov = float(r_co.cov(r_oc))
    # F-5. Bare division is what produced the 0.965-vs-0.980 confusion documented in
    # nepsevol.estimators.ratios. Every ratio below is produced by a helper that RETURNS ITS
    # SCALE, and the scale is asserted before the two are placed in one row.
    rs_cc, sc1 = variance_ratio(rs, v_cc)
    rs_oc, sc2 = variance_ratio(rs, v_oc)
    oc_cc, sc3 = variance_ratio(v_oc, v_cc)
    assert_same_scale((rs_cc, sc1), (rs_oc, sc2), (oc_cc, sc3))

    # REFEREE ITEMS 11, 14 AND 19. RS/open-to-close on thin equity is the number Section 5.4
    # quotes, and successive revisions have printed it as 0.998, then 1.004, and now 0.999 --
    # moving across one under sample changes far smaller than its own sampling error. Reporting
    # it as a bare point estimate invites exactly the over-reading item 11 objects to, so an
    # interval is attached here and Section 5.4 must quote it.
    #
    # This is a ratio involving a VARIANCE, whose centring mean moves under resampling, so it
    # is not a ratio of sums and the general weighted path is used. Panels cluster on security
    # AND date; the two index series have no cross-section, so they cluster on date alone.
    sub = pd.DataFrame({"rs": rs_daily.to_numpy(), "oc": r_oc.to_numpy()})
    keys = (d.loc[ok_all[ok_all].index] if panel else None)
    lo, hi = weighted_stat_ci(
        lambda f, w: (w * f["rs"]).sum() / w.sum() / weighted_var(f["oc"].to_numpy(), w),
        sub,
        sec=(keys.symbol.to_numpy() if panel else np.zeros(len(sub))),
        date=(keys.date.to_numpy() if panel else d.date[ok_all].to_numpy()),
        dims=(("security", "date") if panel else ("date",)),
        n_boot=N_BOOT, seed=SEED,
    )
    return {"market":label,"n_rows":len(d),"n":int(ok_all.sum()),
            "RS/close-to-close":rs_cc,"RS/open-to-close":rs_oc,
            "RS/open-to-close lo95":lo,"RS/open-to-close hi95":hi,
            "OC/CC ratio":oc_cc,
            "Var(open) /Var(cc)":v_on/v_cc,
            "Var(intraday)/Var(cc)":v_oc/v_cc,
            "2Cov/Var(cc)":2*cov/v_cc,
            "components sum":(v_on+v_oc+2*cov)/v_cc,
            "zero-range %":100*(d.high==d.low).mean()}

nifty=pd.read_csv(EXT/"nifty50.csv",parse_dates=["Date"]); nifty.columns=[x.lower() for x in nifty.columns]
idx=pd.read_csv(VAULT/"nepse_index_history.csv",parse_dates=["Date"]); idx.columns=[x.lower() for x in idx.columns]
nep=idx[idx.date>=pd.Timestamp("2016-06-06")]
panel=load_sample(ROOT, "equity")
thin=panel[panel.n_trades<=panel.n_trades.quantile(0.167)]
dense=panel[panel.n_trades>=panel.n_trades.quantile(0.833)]

rows=[decompose(nifty,"NIFTY 50 index"), decompose(nep,"NEPSE index"),
      decompose(dense,"NEPSE equity — dense",panel=True), decompose(thin,"NEPSE equity — thin",panel=True)]
t=pd.DataFrame(rows).set_index("market")
t.to_csv(TAB/"table18_benchmark_diagnosis.csv")
print("Where does the reported Rogers-Satchell 'bias' come from?")
print("  Maheswaran & Kumar (2013) report RS/usual = 0.82 on Nifty (1996-2011) and attribute it")
print("  to the random-walk effect. Ratio identity: RS/CC = (RS/OC) x (OC/CC).")
print("  NOTE: OC/CC is a RATIO, not a variance share. Var(cc) = Var(co)+Var(oc)+2Cov(co,oc),")
print("  so the three components are reported separately and must sum to 1.\n")
print(t.to_string(float_format=lambda x:f"{x:,.3f}"))
print("\n  RS / open-to-close with 95% multiway-cluster intervals (referee items 11, 14, 19):")
for _m, _r in t.iterrows():
    _spans = _r["RS/open-to-close lo95"] <= 1.0 <= _r["RS/open-to-close hi95"]
    print(f"    {_m:<22} {_r['RS/open-to-close']:.3f}  "
          f"[{_r['RS/open-to-close lo95']:.3f}, {_r['RS/open-to-close hi95']:.3f}]  "
          f"{'spans 1.000' if _spans else 'EXCLUDES 1.000'}")
print("  -> where the interval spans one, the point estimate's position relative to one carries")
print("     no information, and Section 5.4 must not be written as though it does.")

fig,axes=plt.subplots(1,2,figsize=(10.4,4.0))
ax=axes[0]
ix=np.arange(len(t)); w=0.38
ax.bar(ix-w/2,t["RS/close-to-close"],w,color=ps.SERIES["orange"],label="RS ÷ close-to-close  (M&K statistic)")
ax.bar(ix+w/2,t["RS/open-to-close"],w,color=ps.SERIES["aqua"],label="RS ÷ open-to-close  (matched scope)")
ax.axhline(1.0,color=ps.INK_MUTED,lw=1.0)
for i,(a,b) in enumerate(zip(t["RS/close-to-close"],t["RS/open-to-close"])):
    ax.text(i-w/2,a,f"{a:.2f}",ha="center",va="bottom",fontsize=7,color=ps.INK_SOFT)
    ax.text(i+w/2,b,f"{b:.2f}",ha="center",va="bottom",fontsize=7,color=ps.INK_SOFT)
ax.set_xticks(ix); ax.set_xticklabels([s.replace(" — ","\n") for s in t.index],fontsize=7.5)
ax.set_ylim(0,1.35); ax.legend(fontsize=7.2,loc="upper left")
ps.finish(ax,"A. The benchmark choice drives the verdict",None,None,"Ratio")

ax=axes[1]
ax.bar(ix,t["Var(open) /Var(cc)"]*100,color=ps.SERIES["violet"],width=0.55)
for i,v in enumerate(t["Var(open) /Var(cc)"]*100):
    ax.text(i,v,f"{v:.0f}%",ha="center",va="bottom",fontsize=8,color=ps.INK_SOFT)
ax.set_xticks(ix); ax.set_xticklabels([s.replace(" — ","\n") for s in t.index],fontsize=7.5)
ax.margins(y=0.2)
ps.finish(ax,"B. Var(opening return) ÷ Var(close-to-close)",None,None,"Percent")
ps.header(fig,"Rogers-Satchell cannot see the overnight gap, so a close-to-close benchmark conflates two effects",
          "RS is built from open, high, low and close within the session, so comparing it to close-to-close variance\n"
          "mixes estimator error with variation occurring outside the session. Panel B is a ratio, not a share: "
          "Var(cc)=Var(co)+Var(oc)+2Cov.",top=0.82)
for e in ("png","pdf"): fig.savefig(FIG/f"fig14_benchmark_diagnosis.{e}")
plt.close(fig); print(f"\nwrote fig14_benchmark_diagnosis.png")
