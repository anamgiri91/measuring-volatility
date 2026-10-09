"""POST HOC sensitivities asked for by the independent audit of 9 October 2026 (not pre-registered).

Each part measures how much a criticised choice matters. None of them changes a frozen verdict.

S1  (audit item A13) The M14 precision weight floors its scale at the 1% quantile over the WHOLE panel,
    which uses future observations. The primary calibration (table78) is re-estimated with a floor
    that uses only earlier dates.
S2  (A06) The first stage's strength. table78 reports the conventional, homoskedastic F. Here it is
    reported with the cluster-robust Wald F and Montiel Olea and Pflueger's (2013) effective F, both
    clustered by security and date, for the primary specification and its two-session-lag variant.
S3  (A11) NEPSE's corporate-action rule calls a disagreement between the published previous close
    and the prior close "rounding" when it is within 0.5%. Here the disagreements are tabulated
    against what two-decimal rounding of the price can produce (0.005/price), and the rule's split is
    recounted at tolerances of 0.1% and 0.25%.
S4  (A15) The processed panels' row counts, against the figures the data README states.

Outputs (output/tables/): table135_audit_sensitivities.csv
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap(["scipy"])

import importlib.util

import numpy as np
import pandas as pd
from scipy import stats as sstats

from nepsevol import corporate_actions as CA
from nepsevol.calibration import calibrate, predictable_scale

TAB = ROOT / "output" / "tables"
FLOAT_FMT = "%.10g"

_spec = importlib.util.spec_from_file_location("s34", ROOT / "scripts" / "34_instrumented_calibration.py")
s34 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s34)


def calib(frame, instr, w, robust=False):
    return calibrate(frame[s34.MEASURES].to_numpy(), frame[list(instr)].to_numpy(), frame["symbol"], s34.MEASURES,
                     "OC", weights=w, date=frame["date"], composite_over=s34.COMPOSITE_NAMED,
                     robust_first_stage=robust)


def s1_s2(d: pd.DataFrame) -> list[dict]:
    rows = []
    frozen = pd.read_csv(TAB / "table78_calibration_full.csv").set_index("measure")
    u = s34.usable(d, s34.MEASURES)
    full = calib(u, s34.INSTR, u["w"].to_numpy(), robust=True)
    for k, m in enumerate(s34.MEASURES):          # the frozen point estimates first
        assert abs(full.beta[k] - frozen.loc[m, "iv_slope"]) < 1e-9, m
    # S1: the past-only floor
    d2 = d.copy()
    d2["w_past"] = predictable_scale(d2, "P", window=22, floor="past")
    u2 = s34.usable(d2.drop(columns="w").rename(columns={"w_past": "w"}), s34.MEASURES)
    past = calib(u2, s34.INSTR, u2["w"].to_numpy())
    same = u2[["symbol", "date"]].merge(u[["symbol", "date"]].assign(i=1), how="left")["i"].notna().mean()
    for k, m in enumerate(s34.MEASURES):
        jp_f = float(sstats.chi2.sf(full.J[k], full.J_df)) if np.isfinite(full.J[k]) else np.nan
        jp_p = float(sstats.chi2.sf(past.J[k], past.J_df)) if np.isfinite(past.J[k]) else np.nan
        rows += [dict(part="S1", item="A13", statistic=f"{m}: IV slope, frozen whole-panel floor", value=full.beta[k]),
                 dict(part="S1", item="A13", statistic=f"{m}: IV slope, past-only floor", value=past.beta[k]),
                 dict(part="S1", item="A13", statistic=f"{m}: J p-value, frozen whole-panel floor", value=jp_f),
                 dict(part="S1", item="A13", statistic=f"{m}: J p-value, past-only floor", value=jp_p)]
    changed = float((u2["w"].to_numpy() != u.set_index(["symbol", "date"]).reindex(
        pd.MultiIndex.from_frame(u2[["symbol", "date"]]))["w"].to_numpy()).mean())
    rows += [dict(part="S1", item="A13", statistic="share of rows whose weight changes", value=changed),
             dict(part="S1", item="A13", statistic="share of the past-floor rows that are in the frozen sample",
                  value=float(same))]
    # S2: first-stage strength, conventional and robust, for t-1 and t-2 instruments
    lag2 = [c.replace("L1m", "L2m") for c in s34.INSTR]
    u3 = s34.usable(d, s34.MEASURES, instr=lag2)
    res2 = calib(u3, lag2, u3["w"].to_numpy(), robust=True)
    for label, r in (("instruments dated t-1 (primary)", full), ("instruments dated t-2", res2)):
        rows += [dict(part="S2", item="A06", statistic=f"first-stage F, conventional ({label})", value=r.first_stage_F),
                 dict(part="S2", item="A06", statistic=f"first-stage F, two-way cluster-robust Wald ({label})",
                      value=r.first_stage_F_robust),
                 dict(part="S2", item="A06", statistic=f"effective F, Montiel Olea-Pflueger, two-way ({label})",
                      value=r.first_stage_F_eff)]
    return rows


def s3(d: pd.DataFrame) -> list[dict]:
    dis = CA.classify_disagreements(d)
    f = dis["implied_factor"]
    gap = (f - 1.0).abs()
    rounding = 0.005 / dis["prev_close"]                  # what two-decimal rounding of the price can produce
    rows = [dict(part="S3", item="A11", statistic="previous-close disagreements", value=len(dis)),
            dict(part="S3", item="A11", statistic="median price at a disagreement", value=float(dis["prev_close"].median())),
            dict(part="S3", item="A11", statistic="largest relative gap two-decimal rounding can produce (median over disagreements)",
                 value=float(rounding.median())),
            dict(part="S3", item="A11", statistic="disagreements within two-decimal rounding", value=int((gap <= rounding).sum())),
            dict(part="S3", item="A11", statistic="disagreements between rounding and 0.5% (called 'rounding' by the rule)",
                 value=int(((gap > rounding) & (gap <= CA.ROUNDING_TOL)).sum()))]
    for tol in (0.001, 0.0025, CA.ROUNDING_TOL):
        down = f > 1 + tol
        rows.append(dict(part="S3", item="A11", statistic=f"downward revisions beyond {100 * tol:g}% (corporate-action label)",
                         value=int(down.sum())))
    return rows


def s4() -> list[dict]:
    """Row counts of the processed files, against what data/processed/README.md stated. The two analysis
    samples are read through load_sample(), the only door to the mixed universe (policy SS12)."""
    from nepsevol.sample import UNIVERSES, load_sample
    n = sum(1 for _ in open(ROOT / "data" / "processed" / "panel_trades_clean.csv")) - 1
    rows = [dict(part="S4", item="A15", statistic="panel_trades_clean.csv: rows (README stated 184,430)", value=n)]
    for universe, stated in (("full", 184390), ("equity", 143718)):
        rows.append(dict(part="S4", item="A15", statistic=f"{UNIVERSES[universe][0]}: rows (README stated {stated:,})",
                         value=len(load_sample(ROOT, universe, quiet=True))))
    return rows


def main() -> None:
    print("POST HOC audit sensitivities (A13, A06, A11, A15)")
    d = s34.build_nepse()
    rows = s1_s2(d) + s3(d) + s4()
    out = pd.DataFrame(rows)
    out.to_csv(TAB / "table135_audit_sensitivities.csv", index=False, float_format=FLOAT_FMT)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 110)
    print(out.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
