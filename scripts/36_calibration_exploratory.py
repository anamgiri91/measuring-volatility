"""POST HOC, EXPLORATORY follow-ups to the frozen M14 calibration (scripts/34).

Nothing in this script was in M14_CALIBRATION_ANALYSIS_PLAN.md. Both analyses were written AFTER
the frozen results were seen, because those results raised them, and they are labelled post hoc
wherever they are reported. Neither changes a frozen verdict; the decision ledger (table86) is
produced by scripts/34 alone.

E1  Security x regime fixed effects. The frozen specification gives each security ONE additive
    component alpha_i for the whole sample. The frozen cross-moments then showed that the
    transient noise in the opening price shifts sharply across market-design regimes -- the
    overnight-intraday reversal triples when the opening band widens -- so alpha_i is not
    constant within security, and a regime shift in alpha that the lagged instruments partly
    track can leak into the slope. E1 re-estimates the full-sample slopes with alpha_{i,regime},
    forward orthogonal deviations taken within security x regime.

E2  How much of the matched proxy is transient endpoint noise. Under i.i.d. open and close errors
    the kernel K = c^2 + o c + c o' is conditionally unbiased for efficient intraday variance
    (nepsevol.calibration.noise_kernel), so 1 - E[K]/E[OC] estimates the share of the proxy's
    mean that is transient noise. The kernel is biased upward where the band censors the open, so
    the share is a LOWER bound in the +/-2% regimes and most credible in regime C, where only 8%
    of opens sit at the band. Reported by regime with stationary block-bootstrap intervals.

Outputs: output/tables/table87_calibration_regime_fe.csv, table88_endpoint_noise_share.csv
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util

import numpy as np
import pandas as pd

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"

_spec = importlib.util.spec_from_file_location("s34", ROOT / "scripts" / "34_instrumented_calibration.py")
s34 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s34)


def e1_regime_fe(d: pd.DataFrame) -> pd.DataFrame:
    u = s34.usable(d[d["regime"].notna()], s34.MEASURES)
    grp = u["symbol"] + "|" + u["regime"]
    rows = []
    for label, kw in [("security x regime FE, FOD (frozen transformation)", {}),
                      ("security x regime FE, whole-sample within", {"transform": "within"})]:
        point = s34.calib(u, group=grp, **kw)

        def f(frame, mult, kw=kw):
            return s34.calib(u, mult, group=grp, compute_J=False, **kw).beta
        boot = s34.joint_bootstrap(u, {"b": f})
        lo, hi = s34.ci(boot["b"])
        for k, m in enumerate(s34.MEASURES):
            rows.append({"specification": label, "measure": m, "n_stock_days": point.n_obs,
                         "iv_slope": point.beta[k], "lo": lo[k], "hi": hi[k],
                         "additive_share": point.delta[k], "mean_ratio_var": point.ratio[k],
                         "first_stage_F": point.first_stage_F,
                         "J_pvalue": float(s34.j_pvalue(point.J[k], point.J_df))})
    # the frozen security-only FE, both transformations, for side-by-side reading
    u0 = s34.usable(d, s34.MEASURES)
    for label, kw in [("security FE only, FOD (frozen primary)", {}),
                      ("security FE only, whole-sample within (frozen sensitivity)", {"transform": "within"})]:
        point = s34.calib(u0, compute_J=False, **kw)

        def f(frame, mult, kw=kw):
            return s34.calib(u0, mult, compute_J=False, **kw).beta
        boot = s34.joint_bootstrap(u0, {"b": f})
        lo, hi = s34.ci(boot["b"])
        for k, m in enumerate(s34.MEASURES):
            rows.append({"specification": label, "measure": m, "n_stock_days": point.n_obs,
                         "iv_slope": point.beta[k], "lo": lo[k], "hi": hi[k],
                         "additive_share": point.delta[k], "mean_ratio_var": point.ratio[k],
                         "first_stage_F": point.first_stage_F, "J_pvalue": np.nan})
    return pd.DataFrame(rows)


def e2_noise_share(d: pd.DataFrame) -> pd.DataFrame:
    x = d[d["regime"].notna()].copy()
    x["next_regime"] = x.groupby("symbol")["regime"].shift(-1)
    x["K"] = x["c"] ** 2 + x["o"] * x["c"] + np.where(x["next_regime"] == x["regime"],
                                                        x["c"] * x["o_next"], np.nan)
    names = [r[0] for r in s34.REGIMES]

    def stat(frame, mult):
        out = []
        for g in names:
            m = (frame["regime"] == g).to_numpy()
            f, ww = frame[m], mult[m]
            k, oc, p = f["K"].to_numpy(), f["OC"].to_numpy(), f["P"].to_numpy()
            ok = np.isfinite(k) & np.isfinite(oc) & np.isfinite(p)
            sk, soc, sp = (ww[ok] * k[ok]).sum(), (ww[ok] * oc[ok]).sum(), (ww[ok] * p[ok]).sum()
            out += [1.0 - sk / soc, sk / sp, soc / sp]
        return np.array(out)
    point = stat(x, np.ones(len(x)))
    boot = s34.joint_bootstrap(x, {"m": stat})
    lo, hi = s34.ci(boot["m"])
    rows = []
    for i, (g, a, b, desc) in enumerate(s34.REGIMES):
        for j, lab in enumerate(["transient-noise share of the proxy, 1 - E[K]/E[OC]",
                                 "E[K]/E[P]", "E[OC]/E[P]"]):
            rows.append({"regime": g, "from": a, "to": b, "rules": desc, "quantity": lab,
                         "value": point[3 * i + j], "lo": lo[3 * i + j], "hi": hi[3 * i + j]})
    return pd.DataFrame(rows)


def main() -> None:
    print("POST HOC exploratory follow-ups to M14 (not in the frozen plan)")
    d = s34.build_nepse()
    t1 = e1_regime_fe(d)
    t1.to_csv(TAB / "table87_calibration_regime_fe.csv", index=False, float_format=FLOAT_FMT)
    print(t1[t1.measure.isin(["P", "GK", "RS", "AddRS", "AP"])].to_string(
        index=False, float_format=lambda v: f"{v:.3f}"))
    t2 = e2_noise_share(d)
    t2.to_csv(TAB / "table88_endpoint_noise_share.csv", index=False, float_format=FLOAT_FMT)
    print(t2.to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
