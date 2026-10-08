"""The post hoc recheck (scripts/44_anam_recheck.py) agrees with the frozen tables it varies.

Reads only committed CSVs, so it runs without the third-party frontier inputs. Every "frozen" t in the
recheck must equal the t in the frozen M16-M18 tables, so each variant differs from the frozen
analysis in one choice only; the recheck document must quote the recheck's own numbers.
"""
from __future__ import annotations

import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
RANGE = ["P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"]
FROZEN = {"NEPSE": "table101_anam_holdout_forecast.csv", "NIFTY50": "table101_anam_holdout_forecast.csv",
          "SP500": "table101_anam_holdout_forecast.csv", "DSE 2023-2026": "table108_anam_frontier_forecast.csv",
          "Vietnam 2007-2020": "table108_anam_frontier_forecast.csv",
          "DSE 2009-2021": "table108_anam_frontier_forecast.csv",
          "Morocco 2012-2026": "table113_anam_morocco_forecast.csv"}


def test_every_frozen_t_is_reproduced():
    inf = pd.read_csv(TAB / "table118_anam_recheck_inference.csv")
    frames = {k: pd.read_csv(TAB / v) for k, v in FROZEN.items()}
    for r in inf.itertuples():
        f = frames[r.market]
        g = f[(f.market == r.market) & (f.test_span == r.test_span) & (f.window == r.window)].set_index("estimator")
        col = f"t_vs_{r.reference}"
        ref = g.loc[r.estimator, col] if col in g.columns else float("nan")
        if pd.isna(ref):
            ref = -g.loc[r.reference, f"t_vs_{r.estimator}"]
        assert abs(r.t_frozen_NW_h - ref) < 1e-6, (r.market, r.test_span, r.window, r.estimator, r.reference)


def test_level_recheck_reproduces_the_frozen_calibrated_level():
    lev = pd.read_csv(TAB / "table117_anam_recheck_level.csv")
    frozen = pd.concat([pd.read_csv(TAB / f) for f in ("table102_anam_holdout_level.csv",
                                                       "table109_anam_frontier_level.csv",
                                                       "table114_anam_morocco_level.csv")])
    fz = frozen[frozen.estimator == "Anam (calibrated)"].set_index(["market", "span"]).ratio_to_close_to_close
    mine = lev[lev.estimator == "Anam (calibrated, frozen T2)"].set_index(["market", "span"]).calibrated_ratio
    a = lev[lev.estimator == "Anam"].set_index(["market", "span"]).calibrated_ratio
    for key in fz.index:
        if key in mine.index:
            assert abs(mine[key] - fz[key]) < 5e-4, key   # same number on the recheck's common sample
            assert abs(a[key] - mine[key]) < 1e-9, key    # the recheck's calibration is the estimator's own


def test_no_classical_range_estimator_beats_anam_under_any_qlike_variant():
    inf = pd.read_csv(TAB / "table118_anam_recheck_inference.csv")
    rr = inf[inf.estimator.isin(RANGE) & (inf.reference == "Anam")]
    for col in ("t_frozen_NW_h", "t_NW_2h", "t_NW_4h", "t_nonoverlapping"):
        assert (rr[col].dropna() > -1.96).all(), col


def test_holm_adjustment_is_monotone_and_never_below_the_raw_p():
    m = pd.read_csv(TAB / "table119_anam_recheck_multiplicity.csv")
    assert (m["Holm p within plan"] >= m["p_one_sided"] - 1e-12).all()
    assert (m["Holm p across plans"] >= m["Holm p within plan"] - 1e-12).all()
    o = m.sort_values("p_one_sided")
    assert o["Holm p across plans"].is_monotonic_increasing


def test_the_recheck_document_quotes_the_recheck_tables():
    text = (ROOT / "ANAM_RECHECK_POSTHOC.md").read_text()
    m = pd.read_csv(TAB / "table119_anam_recheck_multiplicity.csv")
    p = m[(m.plan == "M18") & (m.rule == "F1")]["Holm p across plans"].iloc[0]
    assert f"p = {p:.3f}" in text
    inf = pd.read_csv(TAB / "table118_anam_recheck_inference.csv")
    v = "Anam, open-free special case (b=0)"

    def t(mk, span, w, e, r, col):
        x = inf[(inf.market == mk) & (inf.test_span == span) & (inf.window == w) & (inf.estimator == e)
                & (inf.reference == r)][col].iloc[0]
        return f"{x:+.2f}".replace("-", "−")
    for s in (t("Vietnam 2007-2020", "test half", 5, "Anam", "CC", "t_MSE_NW_h"),
              t("Vietnam 2007-2020", "test half", 5, v, "CC", "t_MSE_NW_h"),
              t("NEPSE", "A2+C", 5, "Anam", "CC", "t_MSE_NW_h"),
              t("Morocco 2012-2026", "test half", 5, "Anam", "CC", "t_NW_2h"),
              t("NIFTY50", "test half", 5, "Anam", "CC", "t_nonoverlapping")):
        assert s.lstrip("+") in text, s
    lev = pd.read_csv(TAB / "table117_anam_recheck_level.csv")
    stable = lev[~((lev.market == "NEPSE") & lev.span.isin(["C", "A2+C"])) & lev.estimator.isin(RANGE)]
    assert f"within {100 * (stable.calibrated_ratio - 1).abs().max():.1f}%" in text
    assert f"within {100 * (stable.calibrated_before_window_ratio - 1).abs().max():.1f}%" in text
