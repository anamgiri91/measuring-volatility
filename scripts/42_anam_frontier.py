"""M17: Anam's estimator in two more frontier markets -- Bangladesh (Dhaka) and Vietnam.

Implements M17_ANAM_FRONTIER_PLAN.md, frozen and pushed in commit db417ac together with the panel
module (nepsevol.frontier) and its tests, before this script existed or any estimator was computed
on these data. The estimator set, the forecast test, the level test and the instrumented-noise
report are M16's, imported from scripts/40 unchanged; the decision rules are applied mechanically in
``decisions()``.

Inputs: data/external/frontier/ (third-party, not packaged; see data/external/README.md), checked
against the SHA-256 digests frozen in nepsevol.frontier before use.

Outputs (output/tables/):
    table107_anam_frontier_panels.csv     coverage, screen counts and b-hat on each test span
    table108_anam_frontier_forecast.csv   T1: fair forecast test, every panel and horizon
    table109_anam_frontier_level.csv      T2: raw and calibrated level against close-to-close
    table110_anam_frontier_noise.csv      T4: instrumented noise on each test span (reported)
    table111_anam_frontier_decisions.csv  F1-F3, best in panel, G, and the per-rival verdicts
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util
import time

import numpy as np
import pandas as pd

from nepsevol import frontier as F
from nepsevol.calibration import predictable_scale
from nepsevol.estimators import anam as AN

TAB = ROOT / "output" / "tables"
INPUTS = ROOT / "data" / "external" / "frontier"
FLOAT_FMT = "%.10g"
PRIMARY = ("DSE 2023-2026", "Vietnam 2007-2020")
SECONDARY = ("DSE 2009-2021",)
SPAN = "test half"

_spec = importlib.util.spec_from_file_location("s40", ROOT / "scripts" / "40_anam_holdout.py")
s40 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s40)


def decisions(fc: pd.DataFrame, lev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    # per-rival verdicts: Anam's loss minus the rival's = -(rival minus Anam)
    for (panel, win), g in fc.groupby(["market", "window"], sort=False):
        g = g.set_index("estimator")
        for rv in s40.RIVALS:
            dq, t = -g.loc[rv, "dQLIKE_vs_Anam"], -g.loc[rv, "t_vs_Anam"]
            rows.append(dict(rule="rival", market=panel, span=SPAN, window=win, rival=rv,
                             dQLIKE_Anam_minus_rival=dq, t=t, verdict=f"Anam {s40.verdict(dq, t)} {rv}"))
    v = pd.DataFrame(rows)

    def get(panel, win, rv):
        r = v[(v.market == panel) & (v.window == win) & (v.rival == rv)]
        return r["verdict"].iloc[0]

    out, held = [], {}
    for panel in PRIMARY + SECONDARY:
        role = "primary" if panel in PRIMARY else "secondary"
        f1 = get(panel, 5, "CC") == "Anam beats CC"
        f2 = get(panel, 5, "P") == "Anam beats P"
        L = lev[lev.market == panel].set_index("estimator")["ratio_to_close_to_close"]
        an, op, yz = L["Anam (calibrated)"], L["o2+P"], L["YZ (daily form)"]
        f3 = (0.9 <= an <= 1.1) and not (0.9 <= op <= 1.1) and not (0.9 <= yz <= 1.1)
        losses = v[(v.market == panel) & v.verdict.str.startswith("Anam loses")]
        best = losses.empty
        held[panel] = f1 and f2 and best
        out += [
            dict(rule="F1", market=panel, role=role, verdict="holds" if f1 else "does not hold",
                 detail=f"5 sessions: {get(panel, 5, 'CC')}"),
            dict(rule="F2", market=panel, role=role, verdict="holds" if f2 else "does not hold",
                 detail=f"5 sessions: {get(panel, 5, 'P')}"),
            dict(rule="F3", market=panel, role=role, verdict="holds" if f3 else "does not hold",
                 detail=f"Anam (calibrated) {an:.3f}; o2+P {op:.3f}; YZ daily form {yz:.3f}"),
            dict(rule="best in panel", market=panel, role=role, verdict="yes" if best else "no",
                 detail="no rival beats Anam at 5 or 21 sessions" if best else
                 "; ".join(f"{r.verdict} at {r.window}" for r in losses.itertuples())),
        ]
    g_ok = all(held[p] for p in PRIMARY)
    out.append(dict(rule="G", market=" + ".join(PRIMARY), role="primary", verdict="holds" if g_ok else "does not hold",
                    detail="; ".join(f"{p}: F1, F2 and best in panel {'all hold' if held[p] else 'not all hold'}"
                                     for p in PRIMARY)))
    return pd.concat([pd.DataFrame(out), v], ignore_index=True)


def main() -> None:
    print("M17 FRONTIER MARKETS (frozen plan, commit db417ac)")
    panels, fc, lev, noise = [], [], [], []
    for name in PRIMARY + SECONDARY:
        t0 = time.time()
        d, log = F.market_panel(name, INPUTS)
        est, b = s40.estimator_set(d, "panel")
        tr, te = d["span"] == "train", d["span"] == "test"
        log = {"panel": name, "role": "primary" if name in PRIMARY else "secondary", **log,
               "b median (test span)": float(b[te].median()), "b mean (test span)": float(b[te].mean()),
               "stale opens (o = 0, test span)": float((d.loc[te, "o"] == 0).mean())}
        panels.append(log)
        print(f"  {name}: {log['stock-days']:,} stock-days, {log['securities']} securities, test from "
              f"{log['first test session']}; b median on the test span {log['b median (test span)']:.3f}")
        fc.append(s40.t1(d, est, tr, te, ("pool", AN.POOL_SESSIONS), name, SPAN))
        lev.append(s40.t2_level(d, est, {SPAN: te}, name, "panel"))
        nz = s40.t4_noise(d.assign(w=predictable_scale(d, "P", window=22)), est, te)
        nz.insert(0, "market", name)
        noise.append(nz)
        print(f"    done in {time.time() - t0:.0f}s")
    panels = pd.DataFrame(panels)
    fc = pd.concat(fc, ignore_index=True)
    lev = pd.concat(lev, ignore_index=True)
    noise = pd.concat(noise, ignore_index=True)
    dec = decisions(fc, lev)
    panels.to_csv(TAB / "table107_anam_frontier_panels.csv", index=False, float_format=FLOAT_FMT)
    fc.to_csv(TAB / "table108_anam_frontier_forecast.csv", index=False, float_format=FLOAT_FMT)
    lev.to_csv(TAB / "table109_anam_frontier_level.csv", index=False, float_format=FLOAT_FMT)
    noise.to_csv(TAB / "table110_anam_frontier_noise.csv", index=False, float_format=FLOAT_FMT)
    dec.to_csv(TAB / "table111_anam_frontier_decisions.csv", index=False, float_format=FLOAT_FMT)

    pd.set_option("display.width", 230)
    pd.set_option("display.max_colwidth", 140)
    print("\nDECISIONS")
    print(dec[dec.rule != "rival"][["rule", "market", "verdict", "detail"]].to_string(index=False))
    for (panel, win), g in fc.groupby(["market", "window"], sort=False):
        print(f"\n{panel} [{SPAN}] window {win}")
        print(g.sort_values("QLIKE")[["estimator", "QLIKE", "phi", "n", "t_vs_Anam", "t_vs_P", "t_vs_CC"]].to_string(
            index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nLEVEL (ratio to close-to-close, test span)")
    print(lev.pivot_table(index="estimator", columns="market", values="ratio_to_close_to_close").round(3).to_string())
    print("\nINSTRUMENTED NOISE (reported)")
    print(noise[["market", "measure", "iv_slope", "efficiency_vs_CC_lower_bound", "first_stage_F"]].to_string(
        index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
