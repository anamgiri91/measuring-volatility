"""Diagnostic: where does the market-implied open lose in Vietnam's first development fold?"""
import sys
sys.argv = sys.argv[:1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex
from e10_marketopen import kappa_for, har_Z
D = load_dev("Vietnam 2007-2020"); d = D["d"]; mode = D["mode"]
o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]; sym, date = d["symbol"], d["date"]
zero = pd.Series(0.0, index=d.index); oM = loo_market(o, date).fillna(0.0)
XP = bar_kernel(o, c, u, dd, zero, 0.3, exclude=0.0, overnight=False, zero_range_r2=True)
XM = bar_kernel(o, c, u, dd, oM, 0.3, exclude=0.0, overnight=True, zero_range_r2=True)
mP = LinearConvex(har_Z(d, XP, True), kappa_for(d, XP, mode)); mM = LinearConvex(har_Z(d, XM, True), kappa_for(d, XM, mode))
win = 5
tgt = EV.forward_target(FB.clean_square(d["CC"]), sym, d["ses"], win); y = tgt["y"]
defined = mP.defined & mM.defined & y.notna()
fit_m, val_m = D["masks"][0]
v0, v1 = int(d.loc[val_m, "ses"].min()), int(d.loc[val_m, "ses"].max())
fr = fit_m & defined & (tgt["end_session"] < v0); vr = val_m & defined & (tgt["end_session"] <= v1)
pP, _ = mP.fit(y, fr); pM, _ = mM.fit(y, fr)
print("weights PC", np.round(pP, 3), "M1", np.round(pM, 3))
fP, fM = mP.forecast(pP), mM.forecast(pM)
LP = EV.qlike_canonical(y[vr], fP[vr]); LM = EV.qlike_canonical(y[vr], fM[vr])
df = pd.DataFrame({"date": date[vr], "sym": sym[vr], "diff": LM - LP, "ratio": (fM / fP)[vr], "y": y[vr], "fP": fP[vr]})
print("mean diff", df["diff"].mean(), "median ratio fM/fP", df["ratio"].median())
# by forecast ratio decile
df["rq"] = pd.qcut(df["ratio"], 10, labels=False, duplicates="drop")
print(df.groupby("rq").agg(n=("diff", "size"), diff=("diff", "mean"), ratio=("ratio", "mean"), ybar=("y", "mean"), fP=("fP", "mean")).round(5).to_string())
# by date: top contributors
bd = df.groupby("date")["diff"].agg(["mean", "size"])
bd["contrib"] = bd["mean"] * bd["size"] / len(df)
print(bd.sort_values("contrib").tail(8).round(5).to_string())
print(bd.sort_values("contrib").head(5).round(5).to_string())
# month profile
df["m"] = df["date"].dt.to_period("Q")
print(df.groupby("m")["diff"].agg(["mean", "size"]).round(5).to_string())
