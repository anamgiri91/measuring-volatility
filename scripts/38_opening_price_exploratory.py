"""POST HOC, EXPLORATORY follow-ups to the frozen M15 analysis (scripts/37).

Nothing in this script was in M15_OPENING_PRICE_ANALYSIS_PLAN.md. Every analysis here was
written AFTER the frozen results were seen, because those results raised it, and each is labelled
post hoc wherever it is reported. None changes a frozen verdict; the decision ledger (table96) is
produced by scripts/37 alone.

X1  The central statistic by two other routes: b as an OLS slope WITH an intercept, and b with
    the exchange's published (unadjusted) previous close in place of the adopted one.
X2  What follows a band-pinned open: the mean opening return, the mean intraday return, and the
    share of the opening move the close retains, E[r]/E[o], for upward and downward pinned opens.
X3  How often a non-stale open is the session's high or low -- the channel through which
    Parkinson, which never reads the open directly, inherits the open's error.
X4  A bound that does NOT assume the opening error is independent of overnight news. The kernel
    of M14's E2 (table88) and of M15's H10 is unbiased only under that independence: if the open
    instead overreacts in proportion to the news, the kernel UNDERSTATES efficient variance, and
    the transient shares built on it are overstated, not understated. Write the open's error eta,
    the efficient overnight return e_o, and assume only what the unbiasedness regression needs
    (efficient overnight and intraday returns uncorrelated; eta and the closing error uncorrelated
    with the intraday efficient return and with each other). Then -E[o c] = E[e_o eta] + E[eta^2]
    and, whatever the sign or size of E[e_o eta],

        E[eta^2] >= E[o^2] * ((sqrt(5 - 4b) - 1) / 2)^2        (b < 1),

    by Cauchy-Schwarz when E[e_o eta] >= 0 (then E[e_o^2] <= E[o^2]; raw moments, as in b) and directly when it is
    negative (then E[eta^2] > -E[o c] = (1 - b) E[o^2], which exceeds the bound). The bound is
    attained when eta is perfectly correlated with the news; under independence the value is
    (1 - b) E[o^2]. Both are reported as shares of the open-to-close benchmark E[OC], beside the
    kernel-based share.
X5  The regime fingerprints the manuscript uses to date the closing rule (descriptive): the share
    of closes off the exchange's 0.1-rupee price grid, which a last-trade close cannot produce and
    a fifteen-minute VWAP close almost always does, by regime and on the excluded 2025-09-18
    session (the early close on resumption after the September 2025 halt), with that session's
    share of band-pinned opens.
X6  Market-wide or security by security? An opening overreaction produced inside each security's
    auction should show up in the idiosyncratic part of the opening move, while a market-wide gap
    that the session corrects would show up in the cross-sectional average. Each session's
    equal-weighted cross-sectional means o_m and r_m split the moves; b is reported for the market
    component (dates weighted by their row weight) and for the idiosyncratic one, o - o_m against
    r - r_m, with the market component's share of E[o^2].

Outputs: output/tables/table97_m15_posthoc.csv
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util

import numpy as np
import pandas as pd

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"

_spec = importlib.util.spec_from_file_location("s37", ROOT / "scripts" / "37_opening_price.py")
s37 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s37)
s34 = s37.s34
REGIMES = s37.REGIMES


def g_bound(b: float) -> float:
    """((sqrt(5 - 4b) - 1)/2)^2 for b < 1, else 0 (no transient error is implied)."""
    return ((np.sqrt(5.0 - 4.0 * b) - 1.0) / 2.0) ** 2 if b < 1 else 0.0


def build_stats(d: pd.DataFrame):
    """Index sets and arrays for every post hoc statistic, evaluated under one weight vector."""
    o, c, r = (d[k].to_numpy() for k in ("o", "c", "r"))
    ok = np.isfinite(o) & np.isfinite(c)
    o_pub = np.log(d["open"] / d["prev_close"]).to_numpy()
    r_pub = np.log(d["close"] / d["prev_close"]).to_numpy()
    okp = np.isfinite(o_pub) & np.isfinite(r_pub)
    OC, K = d["OC"].to_numpy(), d["K"].to_numpy()
    okk = ok & np.isfinite(K)
    regime, zone, g = d["regime"].to_numpy(), d["zone"].to_numpy(), d["g"].to_numpy()
    extreme = ((d["open"] == d["high"]) | (d["open"] == d["low"])).to_numpy().astype(float)
    nonstale = ok & (zone != "stale")
    # X5: a close is on the 0.1 grid when 10 x close is an integer (to floating-point tolerance)
    tenths = d["close"].to_numpy() * 10.0
    off_grid = (np.abs(tenths - np.round(tenths)) > 1e-6).astype(float)
    pinned = (zone == "pinned").astype(float)
    excluded = (d["date"] == s37.EXCLUDED).to_numpy()
    labels, specs = [], []

    for reg in REGIMES:
        m = ok & (regime == reg)
        mp = okp & (regime == reg)
        mk = okk & (regime == reg)
        specs.append(("ols", m))
        labels.append((reg, "X1", "b as an OLS slope with an intercept"))
        specs.append(("b_pub", mp))
        labels.append((reg, "X1", "b with the published (unadjusted) previous close"))
        band = 0.05 if reg == "C" else 0.02
        for side, sel in [("up", g >= band - 0.001), ("down", g <= -(band - 0.001))]:
            mm = m & sel
            for stat, lab in [("mean_o", "mean opening return"), ("mean_c", "mean intraday return"),
                              ("retained", "share of the opening move retained by the close, E[r]/E[o]")]:
                specs.append((stat, mm))
                labels.append((reg, "X2", f"{side}ward band-pinned opens: {lab}"))
        specs.append(("share_extreme", nonstale & (regime == reg)))
        labels.append((reg, "X3", "share of non-stale opens that are the session high or low"))
        for stat, lab in [("o2_OC", "E[o^2]/E[OC]"),
                          ("b", "b"),
                          ("lb", "lower bound on E[eta^2]/E[OC], any correlation with news"),
                          ("indep", "E[eta^2]/E[OC] if eta is independent of news, (1 - b) E[o^2]/E[OC]")]:
            specs.append((stat, m))
            labels.append((reg, "X4", lab))
        specs.append(("kernel", mk))
        labels.append((reg, "X4", "kernel-based transient share 1 - E[K]/E[OC] (table88)"))
        specs.append(("off_grid", np.isfinite(d["close"].to_numpy()) & (regime == reg)))
        labels.append((reg, "X5", "share of closes off the 0.1 price grid"))
    specs.append(("off_grid", excluded))
    labels.append(("2025-09-18 (excluded)", "X5", "share of closes off the 0.1 price grid"))
    specs.append(("pinned_share", excluded & np.isfinite(g)))
    labels.append(("2025-09-18 (excluded)", "X5", "share of opens pinned at the band"))
    for reg in REGIMES:
        m = ok & (regime == reg)
        for stat, lab in [("b_market", "b, market component (cross-sectional mean move)"),
                          ("b_idio", "b, idiosyncratic component (move minus the session mean)"),
                          ("market_share", "market component's share of E[o^2]")]:
            specs.append((stat, m))
            labels.append((reg, "X6", lab))

    idx = [np.flatnonzero(m) for _, m in specs]
    date_code = pd.factorize(d["date"], sort=True)[0]

    def split(ii, w):
        """Weighted per-session means of o and r over rows ii, broadcast back to the rows."""
        dc = date_code[ii]
        n_d = date_code.max() + 1
        sw = np.bincount(dc, weights=w, minlength=n_d)
        # a session a bootstrap replicate did not draw has zero weight; its mean is set to zero
        # rather than 0/0, because NaN times a zero weight would still poison every sum
        safe = np.where(sw > 0, sw, 1.0)
        om = np.where(sw > 0, np.bincount(dc, weights=w * o[ii], minlength=n_d) / safe, 0.0)
        rm = np.where(sw > 0, np.bincount(dc, weights=w * r[ii], minlength=n_d) / safe, 0.0)
        return om[dc], rm[dc]

    def evaluate(mult=None):
        w_all = np.ones(len(d)) if mult is None else mult
        out = []
        for (stat, _), ii in zip(specs, idx):
            w = w_all[ii]
            sw = w.sum()
            if sw <= 0:
                out.append(np.nan)
                continue
            if stat == "ols":
                x, y = o[ii], r[ii]
                mx, my = (w * x).sum() / sw, (w * y).sum() / sw
                out.append(float((w * (x - mx) * (y - my)).sum() / (w * (x - mx) ** 2).sum()))
            elif stat == "b_pub":
                x, y = o_pub[ii], r_pub[ii]
                out.append(float((w * x * y).sum() / (w * x * x).sum()))
            elif stat == "mean_o":
                out.append(float((w * o[ii]).sum() / sw))
            elif stat == "mean_c":
                out.append(float((w * c[ii]).sum() / sw))
            elif stat == "retained":
                out.append(float((w * r[ii]).sum() / (w * o[ii]).sum()))
            elif stat == "share_extreme":
                out.append(float((w * extreme[ii]).sum() / sw))
            elif stat in ("o2_OC", "b", "lb", "indep"):
                x, y, oc = o[ii], r[ii], OC[ii]
                o2 = (w * x * x).sum()
                bb = float((w * x * y).sum() / o2)
                o2_oc = float(o2 / (w * oc).sum())
                out.append({"o2_OC": o2_oc, "b": bb, "lb": g_bound(bb) * o2_oc,
                            "indep": (1.0 - bb) * o2_oc}[stat])
            elif stat == "kernel":
                out.append(float(1.0 - (w * K[ii]).sum() / (w * OC[ii]).sum()))
            elif stat == "off_grid":
                out.append(float((w * off_grid[ii]).sum() / sw))
            elif stat == "pinned_share":
                out.append(float((w * pinned[ii]).sum() / sw))
            elif stat in ("b_market", "b_idio", "market_share"):
                om, rm = split(ii, w)
                x, y = o[ii], r[ii]
                if stat == "b_market":
                    out.append(float((w * om * rm).sum() / (w * om * om).sum()))
                elif stat == "b_idio":
                    out.append(float((w * (x - om) * (y - rm)).sum() / (w * (x - om) ** 2).sum()))
                else:
                    out.append(float((w * om * om).sum() / (w * x * x).sum()))
        return np.array(out)

    return labels, evaluate, specs


def main() -> None:
    print("POST HOC exploratory follow-ups to M15 (not in the frozen plan)")
    d = s37.build()
    labels, evaluate, specs = build_stats(d)
    point = evaluate()
    boot = s34.joint_bootstrap(d, {"m": lambda fr, mult: evaluate(mult)}, seed=s37.SEED)
    lo, hi = s34.ci(boot["m"])
    rows = []
    for (reg, block, lab), (_, m), p, l, h in zip(labels, specs, point, lo, hi):
        rows.append({"regime": reg, "analysis": block, "statistic": lab,
                     "n_stock_days": int(m.sum()), "value": p, "lo": l, "hi": h})
    t = pd.DataFrame(rows)
    t.to_csv(TAB / "table97_m15_posthoc.csv", index=False, float_format=FLOAT_FMT)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 90)
    print(t.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
