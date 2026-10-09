"""Post hoc: how the frozen forecast tables move when equal prices give exact zeros.

The first run of plan M20 found that a return between equal prices can be stored as about 1e-16 rather than
zero, because the return is computed as o + c = ln(O/C_prev) + ln(C/O). Its square, about 1e-32, then passes
every "> 0" test (``AUDIT-REGISTER.md`` M-033). The frozen evaluation (``fair_forecast_test``) dropped zero
targets, as its plans said. A target made only of such residues is not zero, so it was kept and scored:

* it adds about ln(f / y) ~ 60 to every forecast's normalised loss;
* the added term differs across forecasts only through ln f, exactly as a zero target does under the
  canonical QLIKE that M20 adopts;
* so the frozen differences move little, but the reported loss levels are inflated, and the extra term can
  move a selected phi.

This script measures that. It runs the frozen arithmetic (step S0 of M20's Part A) twice for each sample,
horizon and test span:

* **as frozen.** It must reproduce the frozen tables 101, 108 and 113.
* **with residues set to zero.** Every squared quantity and every rolling mean below ``ZERO_SQUARE`` is set
  to zero, so the frozen rules drop what they were written to drop.

It is not part of plan M20, and it is post hoc. The frozen tables stay the record, and the corrected
evaluation (script 47) supersedes both runs.

Output (output/tables/): table137_frozen_residue_check.csv
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import importlib.util
import sys

import numpy as np
import pandas as pd

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"

_spec = importlib.util.spec_from_file_location("s47", ROOT / "scripts" / "47_corrected_evaluation.py")
s47 = importlib.util.module_from_spec(_spec)
sys.argv = sys.argv[:1]
_spec.loader.exec_module(s47)
EV, FB, AN = s47.EV, s47.FB, s47.AN
OF, FROZEN9 = s47.OF, s47.FROZEN9
FOCUS = ("CC", "Anam", OF)


def zero_residue(x: pd.Series) -> pd.Series:
    return x.where(~(x.abs() < FB.ZERO_SQUARE), 0.0)


def frozen_eval(d, est, train, test, win, scheme, clean: bool):
    """Step S0 of M20 (the frozen ``fair_forecast_test``), optionally with residues set to zero."""
    sym, date = d["symbol"], d["date"]
    if clean:
        d = d.assign(CC=FB.clean_square(d["CC"]))
        est = {k: FB.clean_square(X) for k, X in est.items()}
    r2 = d["CC"]
    parts = {k: s47.frozen_parts(d, X, win, scheme) for k, X in est.items()}
    fut = r2.groupby(sym, sort=False).transform(
        lambda z: z[::-1].rolling(win, min_periods=win).mean()[::-1].shift(-1))
    if clean:
        parts = {k: (kap, zero_residue(cur), zero_residue(lr)) for k, (kap, cur, lr) in parts.items()}
        fut = zero_residue(fut)
    trm = train.reindex(d.index).fillna(False).astype(bool)
    tem = test.reindex(d.index).fillna(False).astype(bool)
    ok_all = fut.notna() & (fut > 0)
    for kappa, cur, lr in parts.values():
        ok_all &= kappa.notna() & cur.notna() & lr.notna() & (kappa * cur > 0) & (lr > 0)
    res = {}
    for name, (kappa, cur, lr) in parts.items():
        fc = lambda p: kappa * (p * cur + (1 - p) * lr)

        def loss(p, m):
            f = fc(p)
            ok = m & ok_all & (f > 0)
            return s47.norm_q(fut[ok], f[ok])

        best = min(s47.FROZEN_GRID, key=lambda p: loss(p, trm).mean())
        res[name] = dict(phi=float(best), loss=loss(best, tem))
    residue = (r2.notna() & (r2.abs() < FB.ZERO_SQUARE) & (r2 != 0))
    fut_raw = d["CC"].groupby(sym, sort=False).transform(
        lambda z: z[::-1].rolling(win, min_periods=win).mean()[::-1].shift(-1))
    counts = dict(residue_targets_test=int((tem & ok_all & (fut_raw < FB.ZERO_SQUARE)).sum()),
                  residue_targets_train=int((trm & ok_all & (fut_raw < FB.ZERO_SQUARE)).sum()),
                  residue_returns=int(residue.sum()))
    return res, counts, date


def t_diff(res, a, b, date, win):
    la, lb = res[a]["loss"], res[b]["loss"]
    j = la.index.intersection(lb.index)
    diff = la.loc[j] - lb.loc[j]
    per_date = pd.DataFrame({"diff": diff, "date": date[j]}).groupby("date")["diff"].mean().sort_index()
    return float(diff.mean()), float(s47.nw_t(per_date.to_numpy(), lags=win))


def main() -> None:
    print("POST HOC: the frozen forecast tables with floating-point residues of equal prices set to zero")
    rows = []
    for name in s47.SAMPLES:
        if name not in ("NEPSE", "NIFTY50", "SP500") and not s47.INPUTS.exists():
            print(f"  {name}: skipped (data/external/frontier/ not present)")
            continue
        S = s47.load(name)
        d, mode = S["d"], S["mode"]
        scheme = ("pool", AN.POOL_SESSIONS) if mode == "panel" else ("series", AN.SERIES_SESSIONS)
        est, _ = s47.s40.estimator_set(d, mode)
        frozen_tab = pd.read_csv(TAB / s47.FROZEN_TABLE[name])
        for win in s47.WINDOWS:
            for span, test in S["spans"].items():
                fz = frozen_tab[(frozen_tab.market == name) & (frozen_tab.test_span == span) &
                                (frozen_tab.window == win)].set_index("estimator")
                as_is, counts, date = frozen_eval(d, est, S["train"], test, win, scheme, clean=False)
                for e in FROZEN9:
                    assert abs(as_is[e]["loss"].mean() - fz.loc[e, "QLIKE"]) < 1e-9, (name, span, win, e)
                    assert abs(as_is[e]["phi"] - fz.loc[e, "phi"]) < 1e-12 and len(as_is[e]["loss"]) == int(fz.loc[e, "n"])
                zero, _, _ = frozen_eval(d, est, S["train"], test, win, scheme, clean=True)
                row = dict(market=name, span=span, window=win, **counts)
                for e in FOCUS:
                    key = "OF" if e == OF else e
                    row[f"phi_{key}_frozen"], row[f"phi_{key}_zero"] = as_is[e]["phi"], zero[e]["phi"]
                    row[f"QLIKE_{key}_frozen"] = float(as_is[e]["loss"].mean())
                    row[f"QLIKE_{key}_zero"] = float(zero[e]["loss"].mean())
                    row[f"n_{key}_frozen"], row[f"n_{key}_zero"] = len(as_is[e]["loss"]), len(zero[e]["loss"])
                for a, b, lab in (("Anam", "CC", "Anam_CC"), (OF, "CC", "OF_CC"), (OF, "Anam", "OF_Anam")):
                    for tag, res in (("frozen", as_is), ("zero", zero)):
                        dq, tv = t_diff(res, a, b, date, win)
                        row[f"d_{lab}_{tag}"], row[f"t_{lab}_{tag}"] = dq, tv
                        row[f"verdict_{lab}_{tag}"] = s47.verdict(dq, tv)
                    row[f"verdict_{lab}_changed"] = row[f"verdict_{lab}_frozen"] != row[f"verdict_{lab}_zero"]
                rows.append(row)
                print(f"  {name} [{span}] h={win}: {counts['residue_targets_test']} residue targets in the test "
                      f"sample; QLIKE(Anam) {row['QLIKE_Anam_frozen']:.4f} -> {row['QLIKE_Anam_zero']:.4f}; "
                      f"t(Anam-CC) {row['t_Anam_CC_frozen']:.2f} -> {row['t_Anam_CC_zero']:.2f}; "
                      f"t(OF-CC) {row['t_OF_CC_frozen']:.2f} -> {row['t_OF_CC_zero']:.2f}")
    out = pd.DataFrame(rows)
    suffix = "" if set(out["market"]) == set(s47.SAMPLES) else "_partial"
    out.to_csv(TAB / f"table137_frozen_residue_check{suffix}.csv", index=False, float_format=FLOAT_FMT)
    ch = out[[c for c in out.columns if c.endswith("_changed")]].any(axis=1)
    print(f"\n{int(ch.sum())} of {len(out)} sample-span-horizon cells change a verdict among Anam-CC, OF-CC, OF-Anam")


if __name__ == "__main__":
    main()
