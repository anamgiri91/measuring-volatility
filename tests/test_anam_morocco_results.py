"""M18: the frozen plan, the panel module, the tables and the results document must agree.

These re-derive the quoted figures from the tables, so drift between a document and the numbers it
cites fails here."""
from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TAB = ROOT / "output" / "tables"

from nepsevol import frontier as F  # noqa: E402

PLAN = (ROOT / "M18_ANAM_MOROCCO_PLAN.md").read_text()
RES = (ROOT / "M18_ANAM_MOROCCO_RESULTS.md").read_text().replace("−", "-")
VARIANT = "Anam, open-free special case (b=0)"


def f4(v):
    return f"{float(v):.4f}"


def test_the_plan_freezes_the_band_schedule_and_inputs_the_module_uses():
    assert F.MA_BANDS == ((None, 0.10), ("2020-03-17", 0.04), ("2021-10-12", 0.06), ("2023-10-09", 0.10))
    for day in ("17 March 2020", "12 October 2021", "9 October 2023"):
        assert day in PLAN
    # the plan's abbreviation of the archive digest has a typo in its tail (M-018); the full digest lives
    # in the module and the data README, and the code checks the share files themselves
    assert f"{F.CSE_ARCHIVE_SHA256[:8]}…" in PLAN
    assert F.CSE_ARCHIVE_SHA256 in (ROOT / "data" / "external" / "README.md").read_text()
    assert "`M-018`" in (ROOT / "AUDIT-REGISTER.md").read_text()
    assert f"{F.CSE_MANIFEST_SHA256[:8]}…{F.CSE_MANIFEST_SHA256[-8:]}" in PLAN
    assert F.SPANS_M18 == {"Morocco 2012-2026": ("MA", "2012-03-26", "2026-03-27")}


def test_the_plan_quotes_the_panel_the_script_built():
    p = pd.read_csv(TAB / "table112_anam_morocco_panel.csv").iloc[0]
    for key in ("stock-days", "train stock-days", "test stock-days", "sessions", "bars without a previous close"):
        assert f"{int(p[key]):,}" in PLAN, key
    assert p["first test session"] in PLAN and str(int(p["securities"])) in PLAN


def test_the_results_quote_the_decision_ledger():
    dec = pd.read_csv(TAB / "table116_anam_morocco_decisions.csv")
    for r in dec[dec.rule != "rival"].itertuples():
        line = next((ln for ln in RES.splitlines() if ln.startswith(f"| {r.rule} |")), None)
        assert line is not None, r.rule
        assert f"**{r.verdict}**" in line, (r.rule, r.verdict)


def test_the_results_quote_the_forecast_and_level_tables():
    fc = pd.read_csv(TAB / "table113_anam_morocco_forecast.csv")
    full = fc[fc.test_span == "test half"].set_index(["window", "estimator"])
    for win in (5, 21):
        for est in (VARIANT, "Anam", "CC"):
            assert f4(full.loc[(win, est), "QLIKE"]) in RES, (win, est)
    assert f"{full.loc[(5, VARIANT), 't_vs_CC']:.2f}" in RES
    assert f"{full.loc[(5, VARIANT), 't_vs_Anam']:.2f}" in RES
    assert f"{full.loc[(5, 'Anam'), 't_vs_CC']:.2f}" in RES
    lev = pd.read_csv(TAB / "table114_anam_morocco_level.csv")
    lev = lev[lev.span == "test half"].set_index("estimator")["ratio_to_close_to_close"]
    for est in ("Anam (calibrated)", "o2+P", "YZ (daily form)", "P", "GK"):
        assert f"{lev[est]:.3f}" in RES, est
