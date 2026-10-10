"""E4: variants of the effective-bar kernel, all under the same HAR dynamics (continuous fit)."""
import sys, time
NAME = sys.argv[1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex
from runner2 import run
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

def kappa_for(d, X, mode):
    Xc, r2 = FB.clean_square(X), FB.clean_square(d["CC"])
    v = Xc.notna() & r2.notna()
    if mode == "panel":
        return FB.pooled_kappa(Xc.where(v), r2, d["date"], AN.POOL_SESSIONS, AN.MIN_POOL_DATES)
    return FB.series_kappa(Xc.where(v), r2, d["symbol"], AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)

def har(d, X, mode):
    Xc = FB.clean_square(X)
    comp = FB.har_components(Xc.where(Xc.notna() & d["CC"].notna()), d["symbol"])
    return LinearConvex(comp[["d1", "m5", "m22", "lr"]], kappa_for(d, X, mode))

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    zero = pd.Series(0.0, index=d.index)
    b = (AN.open_quality_panel(o, r, d["date"]) if mode == "panel" else AN.open_quality_series(o, r, d["symbol"]))
    if mode == "panel":
        bM, bI, oM, oI = two_component_b(o, r, d["date"])
        ost = (bM * oM + bI * oI).where(oM.notna(), b * o)
        ost_m = (bM * oM).where(oM.notna(), 0.0)            # market part only
        ost_m1 = oM.fillna(0.0)                              # the market move itself
    else:
        ost = ost_m = ost_m1 = b * o
    K = {
        "OF": AN.kernel(o, c, u, dd, zero),
        "OF-zr": bar_kernel(o, c, u, dd, zero, 0.2, exclude=0.0, overnight=False, zero_range_r2=True),
        "2CXw2": bar_kernel(o, c, u, dd, ost, 0.2, exclude=1.0),
        "2CXw1": bar_kernel(o, c, u, dd, ost, 0.1, exclude=1.0),
        "2CXw3": bar_kernel(o, c, u, dd, ost, 0.3, exclude=1.0),
        "2CXw4": bar_kernel(o, c, u, dd, ost, 0.4, exclude=1.0),
        "2CXe5": bar_kernel(o, c, u, dd, ost, 0.2, exclude=0.5),
        "2CXzr": bar_kernel(o, c, u, dd, ost, 0.2, exclude=1.0, zero_range_r2=True),
        "MXw2": bar_kernel(o, c, u, dd, ost_m, 0.2, exclude=1.0),
        "M1Xw2": bar_kernel(o, c, u, dd, ost_m1, 0.2, exclude=1.0),
        "2CXnoext": bar_kernel(o, c, u, dd, ost, 0.2, exclude=1.0, extend=False),
        "CC": d["CC"],
    }
    models = {"HAR-" + k: har(d, X, mode) if k != "CC" else LinearConvex(
        FB.har_components(FB.clean_square(d["CC"]), d["symbol"])[["d1", "m5", "m22", "lr"]], 1.0) for k, X in K.items()}
    ledger, res = [], []
    for win in (5, 21):
        res.append(run(D, models, win, "HAR-OF", "E4", ledger))
    out = pd.concat(res)
    out.to_csv(OUT / f"e4_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"val": g.val_loss.mean(), "d": g.d_vs_base.mean(), "t": g.t_vs_base.mean()}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
