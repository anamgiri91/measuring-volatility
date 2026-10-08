"""M18: Anam's estimator and its open-free form in Morocco (Casablanca Stock Exchange).

Implements M18_ANAM_MOROCCO_PLAN.md, frozen and pushed in commit b4de86d together with the Casablanca
reader and the dated band schedule (nepsevol.frontier), before this script existed or any estimator
was computed on these data. The estimator set, the forecast test, the level test and the
instrumented-noise report are M16's (scripts/40); the decision rules are applied mechanically in
``decisions()``.

Inputs: data/external/frontier/casablanca/ (supplied by the author, not packaged; see
data/external/README.md), checked against the SHA-256 digest frozen in nepsevol.frontier.

Outputs (output/tables/):
    table112_anam_morocco_panel.csv      coverage, screen counts, b-hat by span and band regime
    table113_anam_morocco_forecast.csv   T1 on the full test span and within each band regime
    table114_anam_morocco_level.csv      T2, including the open-free form calibrated by kappa_0
    table115_anam_morocco_noise.csv      T4 on the test span (reported)
    table116_anam_morocco_decisions.csv  F1-F3, best in panel, V1-V3, O, and per-rival verdicts
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
from nepsevol.volforecast import fair_forecast_test

TAB = ROOT / "output" / "tables"
INPUTS = ROOT / "data" / "external" / "frontier"
FLOAT_FMT = "%.10g"
PANEL = "Morocco 2012-2026"
SPAN = "test half"
#: band regimes of the test span (plan, item 4): name, first day, last day
REGIMES = (("10% to 2020-03-16", None, "2020-03-16"), ("4% 2020-03-17 to 2021-10-11", "2020-03-17", "2021-10-11"),
           ("6% 2021-10-12 to 2023-10-08", "2021-10-12", "2023-10-08"), ("10% from 2023-10-09", "2023-10-09", None))

_spec = importlib.util.spec_from_file_location("s40", ROOT / "scripts" / "40_anam_holdout.py")
s40 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s40)
VARIANT = s40.VARIANT
REFS = (VARIANT, "Anam", "P", "CC")


def regime_masks(d: pd.DataFrame) -> dict:
    out = {}
    for name, a, b in REGIMES:
        m = pd.Series(True, index=d.index)
        if a is not None:
            m &= d["date"] >= pd.Timestamp(a)
        if b is not None:
            m &= d["date"] <= pd.Timestamp(b)
        out[name] = m
    return out


def t1(d, est, train, test, span) -> pd.DataFrame:
    rows = []
    for win in s40.WINDOWS:
        t, _ = fair_forecast_test(d, est, train, test, win=win, scheme=("pool", AN.POOL_SESSIONS), refs=REFS)
        t = t.reset_index()
        t.insert(0, "test_span", span)
        t.insert(0, "window", win)
        t.insert(0, "market", PANEL)
        rows.append(t)
        best = t.sort_values("QLIKE")["estimator"].iloc[0]
        print(f"  T1 [{span}] window {win}: best {best!r}; Anam rank "
              f"{int(t['QLIKE'].rank().loc[t['estimator'] == 'Anam'].iloc[0])}, open-free rank "
              f"{int(t['QLIKE'].rank().loc[t['estimator'] == VARIANT].iloc[0])} of {len(t)}")
    return pd.concat(rows, ignore_index=True)


def open_free_level(d, A0, spans: dict) -> pd.DataFrame:
    """The open-free form's calibrated 21-session level: kappa_0 (pooled, 60 dates) times the window mean."""
    sym = d["symbol"]
    kappa0 = AN.calibration_panel(A0, d["CC"], d["date"])
    v = kappa0 * s40.window_mean(A0, sym)
    r2w = s40.window_mean(d["CC"], sym)
    rows = []
    for span, mask in spans.items():
        ok = s40.inside(mask, sym) & r2w.notna() & v.notna()
        rows.append(dict(market=PANEL, span=span, estimator=f"{VARIANT} (calibrated)", n=int(ok.sum()),
                         ratio_to_close_to_close=float(v[ok].mean() / r2w[ok].mean())))
    return pd.DataFrame(rows)


def decisions(fc: pd.DataFrame, lev: pd.DataFrame) -> pd.DataFrame:
    full = fc[fc["test_span"] == SPAN]
    rows = []
    for win, g in full.groupby("window", sort=False):
        g = g.set_index("estimator")
        for name, ref in (("Anam", "Anam"), (VARIANT, VARIANT)):
            rivals = list(s40.RIVALS) + (["Anam"] if name == VARIANT else [])
            for rv in rivals:
                # E's loss minus the rival's = -(rival minus E)
                dq, t = -g.loc[rv, f"dQLIKE_vs_{ref}"], -g.loc[rv, f"t_vs_{ref}"]
                rows.append(dict(rule="rival", estimator=name, market=PANEL, span=SPAN, window=win, rival=rv,
                                 dQLIKE_estimator_minus_rival=dq, t=t, verdict=s40.verdict(dq, t)))
    v = pd.DataFrame(rows)

    def get(name, win, rv):
        return v[(v.estimator == name) & (v.window == win) & (v.rival == rv)]["verdict"].iloc[0]

    def lost(name):
        r = v[(v.estimator == name) & (v.verdict == "loses to")]
        return r, r.empty

    L = lev[lev.span == SPAN].set_index("estimator")["ratio_to_close_to_close"]
    an, op, yz = L["Anam (calibrated)"], L["o2+P"], L["YZ (daily form)"]
    f1, f2 = get("Anam", 5, "CC") == "beats", get("Anam", 5, "P") == "beats"
    f3 = (0.9 <= an <= 1.1) and not (0.9 <= op <= 1.1) and not (0.9 <= yz <= 1.1)
    la, best = lost("Anam")
    v1, v2 = get(VARIANT, 5, "CC") == "beats", get(VARIANT, 5, "Anam") == "beats"
    lv, v3 = lost(VARIANT)
    yes = lambda b: "holds" if b else "does not hold"  # noqa: E731
    out = [
        dict(rule="F1", estimator="Anam", verdict=yes(f1), detail=f"5 sessions: Anam {get('Anam', 5, 'CC')} CC"),
        dict(rule="F2", estimator="Anam", verdict=yes(f2), detail=f"5 sessions: Anam {get('Anam', 5, 'P')} P"),
        dict(rule="F3", estimator="Anam", verdict=yes(f3),
             detail=f"Anam (calibrated) {an:.3f}; o2+P {op:.3f}; YZ daily form {yz:.3f}"),
        dict(rule="best in panel", estimator="Anam", verdict="yes" if best else "no",
             detail="no rival beats Anam at 5 or 21 sessions" if best else
             "; ".join(f"loses to {r.rival} at {r.window}" for r in la.itertuples())),
        dict(rule="V1", estimator=VARIANT, verdict=yes(v1), detail=f"5 sessions: open-free form {get(VARIANT, 5, 'CC')} CC"),
        dict(rule="V2", estimator=VARIANT, verdict=yes(v2), detail=f"5 sessions: open-free form {get(VARIANT, 5, 'Anam')} Anam"),
        dict(rule="V3", estimator=VARIANT, verdict=yes(v3),
             detail="no estimator beats the open-free form at 5 or 21 sessions" if v3 else
             "; ".join(f"loses to {r.rival} at {r.window}" for r in lv.itertuples())),
        dict(rule="O", estimator=VARIANT, verdict=yes(v1 and v3), detail=f"V1 {yes(v1)}; V3 {yes(v3)}"),
    ]
    out = pd.DataFrame(out)
    out.insert(2, "market", PANEL)
    return pd.concat([out, v], ignore_index=True)


def main() -> None:
    print("M18 MOROCCO (frozen plan, commit b4de86d)")
    t0 = time.time()
    d, log = F.market_panel(PANEL, INPUTS)
    est, b = s40.estimator_set(d, "panel")
    tr, te = d["span"] == "train", d["span"] == "test"
    regs = {k: te & m for k, m in regime_masks(d).items()}
    panel = {"panel": PANEL, **log, "b median (test span)": float(b[te].median()),
             "stale opens (o = 0, test span)": float((d.loc[te, "o"] == 0).mean())}
    for k, m in regs.items():
        panel[f"b median ({k})"] = float(b[m].median())
    print(f"  {PANEL}: {log['stock-days']:,} stock-days, {log['securities']} shares, test from "
          f"{log['first test session']}; b median on the test span {panel['b median (test span)']:.3f}")
    fc = [t1(d, est, tr, te, SPAN)] + [t1(d, est, tr, m, k) for k, m in regs.items()]
    fc = pd.concat(fc, ignore_index=True)
    spans = {SPAN: te, **regs}
    lev = pd.concat([s40.t2_level(d, est, spans, PANEL, "panel"), open_free_level(d, est[VARIANT], spans)],
                    ignore_index=True)
    noise = s40.t4_noise(d.assign(w=predictable_scale(d, "P", window=22)), est, te)
    noise.insert(0, "market", PANEL)
    dec = decisions(fc, lev)
    pd.DataFrame([panel]).to_csv(TAB / "table112_anam_morocco_panel.csv", index=False, float_format=FLOAT_FMT)
    fc.to_csv(TAB / "table113_anam_morocco_forecast.csv", index=False, float_format=FLOAT_FMT)
    lev.to_csv(TAB / "table114_anam_morocco_level.csv", index=False, float_format=FLOAT_FMT)
    noise.to_csv(TAB / "table115_anam_morocco_noise.csv", index=False, float_format=FLOAT_FMT)
    dec.to_csv(TAB / "table116_anam_morocco_decisions.csv", index=False, float_format=FLOAT_FMT)
    print(f"  done in {time.time() - t0:.0f}s")

    pd.set_option("display.width", 230)
    pd.set_option("display.max_colwidth", 140)
    print("\nDECISIONS")
    print(dec[dec.rule != "rival"][["rule", "estimator", "verdict", "detail"]].to_string(index=False))
    for (span, win), g in fc.groupby(["test_span", "window"], sort=False):
        print(f"\n{PANEL} [{span}] window {win}")
        print(g.sort_values("QLIKE")[["estimator", "QLIKE", "phi", "n", f"t_vs_{VARIANT}", "t_vs_Anam", "t_vs_P", "t_vs_CC"]]
              .rename(columns={f"t_vs_{VARIANT}": "t_vs_open_free"}).to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nLEVEL (ratio to close-to-close)")
    print(lev.pivot_table(index="estimator", columns="span", values="ratio_to_close_to_close").round(3).to_string())
    print("\nINSTRUMENTED NOISE (reported)")
    print(noise[["measure", "iv_slope", "efficiency_vs_CC_lower_bound", "first_stage_F"]].to_string(
        index=False, float_format=lambda x: f"{x:.3f}"))
    print("\nb by span and regime:", {k: round(v, 3) for k, v in panel.items() if k.startswith("b median")})


if __name__ == "__main__":
    main()
