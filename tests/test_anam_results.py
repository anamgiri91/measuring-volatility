"""M16: the frozen plan, the estimator and the results document must agree with each other and with
the tables they cite. These re-derive the quoted figures from the tables, so drift fails here."""
from __future__ import annotations

import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TAB = ROOT / "output" / "tables"

from nepsevol.estimators import anam as AN  # noqa: E402

PLAN = (ROOT / "M16_ANAM_ESTIMATOR_PLAN.md").read_text()
RES = (ROOT / "M16_ANAM_ESTIMATOR_RESULTS.md").read_text().replace("−", "-")


def f4(v):
    return f"{float(v):.4f}"


def test_the_plan_freezes_the_constants_the_module_uses():
    assert AN.LAMBDA0 == 0.2 and "`LAMBDA0` = 0.2" in PLAN
    assert AN.POOL_SESSIONS == 60 and "`POOL_SESSIONS` = 60" in PLAN
    assert AN.SERIES_SESSIONS == 250 and "`SERIES_SESSIONS` = 250" in PLAN


def test_the_plan_quotes_the_development_tables():
    t = pd.read_csv(TAB / "table98_anam_dev_forecast.csv").set_index(["window", "train", "estimator"])
    for win, tr in ((5, "A1"), (5, "B")):
        assert f4(t.loc[(win, tr, "Anam"), "QLIKE"]) in PLAN
        assert f4(t.loc[(win, tr, "P"), "QLIKE"]) in PLAN
    assert f4(t.loc[(21, "B", "Anam"), "QLIKE"]) in PLAN and f4(t.loc[(21, "B", "o2+P"), "QLIKE"]) in PLAN


def test_the_results_quote_the_decision_ledger():
    dec = pd.read_csv(TAB / "table105_anam_holdout_decisions.csv")
    rules = dec[dec.rule.isin(["H1", "H2", "H3", "H4", "H5"])].set_index("rule")["verdict"]
    assert rules.to_dict() == {"H1": "does not hold", "H2": "does not hold", "H3": "does not hold",
                               "H4": "holds", "H5": "holds"}
    for rule, verdict in rules.items():
        assert re.search(rf"\| {rule} \|[^\n]*\*\*{verdict}\*\*", RES), rule
    best = dec[dec.rule == "best in market"].set_index("market")["verdict"]
    assert (best == "yes").all() and "**yes, in all three**" in RES


def test_the_results_quote_the_forecast_and_level_tables():
    f = pd.read_csv(TAB / "table101_anam_holdout_forecast.csv").set_index(["market", "test_span", "window", "estimator"])
    for key in [("NEPSE", "A2+C", 5, "Anam"), ("NEPSE", "A2+C", 5, "CC"), ("NEPSE", "A2+C", 5, "P"),
                ("NIFTY50", "test half", 5, "Anam"), ("NIFTY50", "test half", 5, "CC"),
                ("SP500", "test half", 5, "Anam"), ("SP500", "test half", 5, "CC"), ("NEPSE", "C", 5, "Anam")]:
        assert f4(f.loc[key, "QLIKE"]) in RES, key
    # Anam-minus-rival t statistics quoted in the text
    for key, t in [(("NEPSE", "C", 5, "CC"), "+3.51"), (("NEPSE", "C", 21, "CC"), "+2.47"),
                   (("NIFTY50", "test half", 5, "CC"), "-3.07"), (("SP500", "test half", 5, "CC"), "-6.39")]:
        assert f"{-f.loc[key, 't_vs_Anam']:+.2f}" == t and t in RES, key
    lev = pd.read_csv(TAB / "table102_anam_holdout_level.csv").set_index(["market", "span", "estimator"])["ratio_to_close_to_close"]
    for key in [("NEPSE", "A2", "Anam (calibrated)"), ("NEPSE", "C", "Anam (calibrated)"),
                ("NIFTY50", "test half", "Anam (calibrated)"), ("SP500", "test half", "Anam (calibrated)"),
                ("SP500", "test half", "YZ (window form)"), ("NEPSE", "C", "YZ (window form)")]:
        assert f"{lev[key]:.3f}" in RES, key


def test_post_hoc_material_is_labelled_and_kept_apart():
    assert "## Not in the plan: post hoc, exploratory" in RES
    src = (ROOT / "scripts" / "41_anam_posthoc.py").read_text()
    assert src.startswith('"""POST HOC, EXPLORATORY')
    pc = pd.read_csv(TAB / "table106_anam_posthoc_calibration.csv").set_index(["window", "estimator"])["QLIKE"]
    assert f4(pc[(5, "Anam, calibration 10 dates")]) in RES and f4(pc[(21, "Anam, calibration 10 dates")]) in RES


def test_correction_ids_cited_by_m16_are_registered():
    reg = (ROOT / "AUDIT-REGISTER.md").read_text()
    for c in set(re.findall(r"M-0\d\d", (ROOT / "M16_ANAM_ESTIMATOR_RESULTS.md").read_text())):
        assert f"`{c}`" in reg, c
