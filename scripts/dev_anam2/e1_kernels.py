"""E1/E2: the two-component effective open and the open-excluded extremes, under HAR and phi dynamics."""
import sys, time
NAME = sys.argv[1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from runner import run
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"; OUT.mkdir(exist_ok=True)

def kappa_for(d, X, mode):
    Xc, r2 = FB.clean_square(X), FB.clean_square(d["CC"])
    v = Xc.notna() & r2.notna()
    if mode == "panel":
        return FB.pooled_kappa(Xc.where(v), r2, d["date"], AN.POOL_SESSIONS, AN.MIN_POOL_DATES)
    return FB.series_kappa(Xc.where(v), r2, d["symbol"], AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    zero = pd.Series(0.0, index=d.index)
    b = (AN.open_quality_panel(o, r, d["date"]) if mode == "panel" else AN.open_quality_series(o, r, d["symbol"]))
    K = {"OF": AN.kernel(o, c, u, dd, zero), "Anam": AN.kernel(o, c, u, dd, b)}
    if mode == "panel":
        bM, bI, oM, oI = two_component_b(o, r, d["date"])
        ostar = (bM * oM + bI * oI).where(oM.notna(), b * o)
        bmix = b
    else:
        ostar = b * o; bM = bI = b
    K["2C"] = bar_kernel(o, c, u, dd, ostar, 0.2 * (1 - b), exclude=0.0)          # two-component open
    K["X0"] = bar_kernel(o, c, u, dd, zero, 0.2, exclude=1.0, overnight=False)    # open-excluded, PC anchor
    K["2CX"] = bar_kernel(o, c, u, dd, ostar, 0.2 * (1 - b), exclude=1.0)        # both
    K["2CXw2"] = bar_kernel(o, c, u, dd, ostar, 0.2, exclude=1.0)                # both, fixed blend
    K["X0half"] = bar_kernel(o, c, u, dd, zero, 0.2, exclude=0.5, overnight=False)
    K["CC"] = d["CC"]
    models = {}
    for k, X in K.items():
        kap = 1.0 if k == "CC" else kappa_for(d, X, mode)
        models["HAR-" + k] = s47.HAR(d, X, kap)
    for k in ("OF", "X0", "2CX"):
        models["phi-" + k] = s47.Kernel(d, K[k], 5, mode)   # window replaced per horizon below
    ledger = []
    res = []
    for win in (5, 21):
        for k in ("OF", "X0", "2CX"):
            models["phi-" + k] = s47.Kernel(d, K[k], win, mode)
        res.append(run(D, models, win, "HAR-OF", "E1", ledger))
    out = pd.concat(res)
    out.to_csv(OUT / f"e1_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"val_loss": g.val_loss.mean(), "t": g.t_vs_base.mean()}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
