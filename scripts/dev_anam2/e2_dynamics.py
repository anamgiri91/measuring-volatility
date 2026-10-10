"""E3: a cross-sectional market variance factor in HAR dynamics, for range-based and return-only measures alike."""
import sys, time
NAME = sys.argv[1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
from runner2 import run
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"; OUT.mkdir(exist_ok=True)

def kappa_for(d, X, mode):
    Xc, r2 = FB.clean_square(X), FB.clean_square(d["CC"])
    v = Xc.notna() & r2.notna()
    if mode == "panel":
        return FB.pooled_kappa(Xc.where(v), r2, d["date"], AN.POOL_SESSIONS, AN.MIN_POOL_DATES)
    return FB.series_kappa(Xc.where(v), r2, d["symbol"], AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)

def components(d, X):
    Xc = FB.clean_square(X)
    comp = FB.har_components(Xc.where(Xc.notna() & d["CC"].notna()), d["symbol"])
    return comp

def main(name):
    t0 = time.time()
    D = load_dev(name); d = D["d"]; mode = D["mode"]
    o, c, u, dd, r = d["o"], d["c"], d["u"], d["d"], d["r"]
    zero = pd.Series(0.0, index=d.index)
    b = (AN.open_quality_panel(o, r, d["date"]) if mode == "panel" else AN.open_quality_series(o, r, d["symbol"]))
    if mode == "panel":
        bM, bI, oM, oI = two_component_b(o, r, d["date"])
        ostar = (bM * oM + bI * oI).where(oM.notna(), b * o)
    else:
        ostar = b * o
    K = {"OF": AN.kernel(o, c, u, dd, zero), "2CXw2": bar_kernel(o, c, u, dd, ostar, 0.2, exclude=1.0), "CC": d["CC"]}
    models = {}
    for k, X in K.items():
        kap = 1.0 if k == "CC" else kappa_for(d, X, mode)
        comp = components(d, X)
        models[f"HAR-{k}"] = LinearConvex(comp[["d1", "m5", "m22", "lr"]], kap)
        if mode == "panel":
            q5 = (comp["m5"] / comp["lr"]); q22 = (comp["m22"] / comp["lr"])
            M5 = market_state(q5, d["date"]); M22 = market_state(q22, d["date"])
            Z = pd.DataFrame({"d1": comp["d1"], "m5": comp["m5"], "m22": comp["m22"],
                              "lrM5": comp["lr"] * M5, "lrM22": comp["lr"] * M22, "lr": comp["lr"]})
            models[f"FHAR-{k}"] = LinearConvex(Z, kap)
    vb = s47.FB.rolling_rows(FB.clean_square(d["CC"]), d["symbol"], s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
    ledger, res = [], []
    for win in (5, 21):
        mm = dict(models)
        mm["GJR"] = s47.Recursion(d, "GJR", win, vb)
        combos = {"1/2 HAR-2CXw2 + 1/2 GJR": ("HAR-2CXw2", "GJR", 0.5), "1/2 HAR-OF + 1/2 GJR": ("HAR-OF", "GJR", 0.5)}
        if mode == "panel":
            combos["1/2 FHAR-2CXw2 + 1/2 GJR"] = ("FHAR-2CXw2", "GJR", 0.5)
            combos["1/2 FHAR-2CXw2 + 1/2 FHAR-CC"] = ("FHAR-2CXw2", "FHAR-CC", 0.5)
        res.append(run(D, mm, win, "HAR-OF", "E3", ledger, combos=combos))
    out = pd.concat(res)
    out.to_csv(OUT / f"e3_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"val_loss": g.val_loss.mean(), "d": g.d_vs_base.mean(), "t": g.t_vs_base.mean()}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).to_string(), flush=True)
    print(out[out.model.str.startswith("FHAR")][["fold", "window", "model", "params"]].to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
