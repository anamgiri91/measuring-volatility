"""E6: consolidated candidates under expanding-window validation (three folds; NEPSE two cross-regime folds)."""
import sys, time
NAME = sys.argv[1]
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
from kernels2 import *
from models2 import LinearConvex, market_state
from runner2 import run
OUT = pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2"

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
    sym = d["symbol"]; zero = pd.Series(0.0, index=d.index)
    b = (AN.open_quality_panel(o, r, d["date"]) if mode == "panel" else AN.open_quality_series(o, r, d["symbol"]))
    if mode == "panel":
        bM, bI, oM, oI = two_component_b(o, r, d["date"])
        ost2c = (bM * oM + bI * oI).where(oM.notna(), b * o)
        ostMT = (oM + bI * oI).where(oM.notna(), b * o)
        ostM1 = oM.fillna(0.0)
    else:
        ost2c = ostMT = ostM1 = b * o
    K = {"OF": AN.kernel(o, c, u, dd, zero),
         "OFzr": bar_kernel(o, c, u, dd, zero, 0.2, exclude=0.0, overnight=False, zero_range_r2=True),
         "OFzr-w3": bar_kernel(o, c, u, dd, zero, 0.3, exclude=0.0, overnight=False, zero_range_r2=True),
         "2Czr": bar_kernel(o, c, u, dd, ost2c, 0.2, exclude=1.0, zero_range_r2=True),
         "2Czr-w3": bar_kernel(o, c, u, dd, ost2c, 0.3, exclude=1.0, zero_range_r2=True),
         "MTzr": bar_kernel(o, c, u, dd, ostMT, 0.2, exclude=1.0, zero_range_r2=True),
         "MTzr-w3": bar_kernel(o, c, u, dd, ostMT, 0.3, exclude=1.0, zero_range_r2=True),
         "M1zr": bar_kernel(o, c, u, dd, ostM1, 0.2, exclude=1.0, zero_range_r2=True)}
    comps = {}
    models = {}
    for k, X in K.items():
        Xc = FB.clean_square(X)
        comp = FB.har_components(Xc.where(Xc.notna() & d["CC"].notna()), sym)
        kap = kappa_for(d, X, mode)
        models["HAR-" + k] = LinearConvex(comp[["d1", "m5", "m22", "lr"]], kap)
        if mode == "panel" and k in ("OF", "OFzr-w3", "2Czr-w3", "MTzr-w3"):
            M5 = market_state(comp["m5"] / comp["lr"], d["date"]); M22 = market_state(comp["m22"] / comp["lr"], d["date"])
            Z = pd.DataFrame({"d1": comp["d1"], "m5": comp["m5"], "m22": comp["m22"], "lrM5": comp["lr"] * M5,
                              "lrM22": comp["lr"] * M22, "lr": comp["lr"]})
            models["FHAR-" + k] = LinearConvex(Z, kap)
    compR = FB.har_components(FB.clean_square(d["CC"]), sym)
    models["HAR-CC"] = LinearConvex(compR[["d1", "m5", "m22", "lr"]], 1.0)
    if mode == "panel":
        M5 = market_state(compR["m5"] / compR["lr"], d["date"]); M22 = market_state(compR["m22"] / compR["lr"], d["date"])
        models["FHAR-CC"] = LinearConvex(pd.DataFrame({"d1": compR["d1"], "m5": compR["m5"], "m22": compR["m22"],
                                                       "lrM5": compR["lr"] * M5, "lrM22": compR["lr"] * M22, "lr": compR["lr"]}), 1.0)
    vb = FB.rolling_rows(FB.clean_square(d["CC"]), sym, s47.LONGRUN_SESSIONS, s47.LONGRUN_MIN)
    ledger, res = [], []
    for win in (5, 21):
        mm = dict(models); mm["GJR"] = s47.Recursion(d, "GJR", win, vb)
        best_rng = "FHAR-MTzr-w3" if mode == "panel" else "HAR-MTzr-w3"
        best_ret = "FHAR-CC" if mode == "panel" else "HAR-CC"
        combos = {f"1/2 {best_rng} + 1/2 GJR": (best_rng, "GJR", 0.5), f"1/2 {best_rng} + 1/2 {best_ret}": (best_rng, best_ret, 0.5),
                  "1/2 HAR-OF + 1/2 GJR": ("HAR-OF", "GJR", 0.5)}
        res.append(run(D, mm, win, "HAR-OF", "E6", ledger, combos=combos))
    out = pd.concat(res)
    out.to_csv(OUT / f"e6_{name.replace(' ', '_')}.csv", index=False)
    piv = out.groupby(["window", "model"]).apply(lambda g: pd.Series({"d": g.d_vs_base.mean(), "t": g.t_vs_base.mean(), "wins": int((g.d_vs_base < 0).sum()), "folds": len(g)}))
    print(name, f"{time.time() - t0:.0f}s"); print(piv.unstack(0).round(4).to_string(), flush=True)

if __name__ == "__main__":
    main(NAME)
