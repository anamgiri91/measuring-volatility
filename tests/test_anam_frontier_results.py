"""M17: the frozen plan, the panel module, the tables and the results document must agree.

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
from nepsevol.estimators import anam as AN  # noqa: E402

PLAN = (ROOT / "M17_ANAM_FRONTIER_PLAN.md").read_text()
RES = (ROOT / "M17_ANAM_FRONTIER_RESULTS.md").read_text().replace("−", "-")


def f4(v):
    return f"{float(v):.4f}"


def test_the_plan_freezes_the_constants_the_module_uses():
    assert F.CARRY_FORWARD_SHARE == 0.90 and "`CARRY_FORWARD_SHARE` = 0.90" in PLAN
    assert F.MIN_SECURITIES == 10 and "`MIN_SECURITIES` = 10" in PLAN
    assert F.MAX_GAP_DAYS == 14 and "`MAX_GAP_DAYS` = 14" in PLAN
    assert F.BAND_MARGIN == 0.01 and "`BAND_MARGIN` = 0.01" in PLAN
    assert F.MARKETS["DSE"]["band"] == 0.10 and F.MARKETS["VN"]["band"] == 0.15
    assert AN.LAMBDA0 == 0.2 and AN.POOL_SESSIONS == 60
    for digest in (F.DSE_UPLOAD_SHA256, F.DSE_MIRROR_SHA256, F.VN_MANIFEST_SHA256):
        assert f"{digest[:8]}…{digest[-6:]}" in PLAN
    assert F.DSE_MIRROR_COMMIT.startswith("9f11a76") and F.VN_COMMIT.startswith("b52e2fe")


def test_the_plan_quotes_the_panels_the_script_built():
    t = pd.read_csv(TAB / "table107_anam_frontier_panels.csv").set_index("panel")
    for panel, r in t.iterrows():
        row = next(line for line in PLAN.splitlines() if line.startswith(f"| {panel} |"))
        for key in ("stock-days", "train stock-days", "test stock-days", "sessions"):
            assert f"{int(r[key]):,}" in row, (panel, key)
        assert str(int(r["securities"])) in row and r["first test session"] in row


def test_the_results_quote_the_decision_ledger():
    dec = pd.read_csv(TAB / "table111_anam_frontier_decisions.csv")
    top = dec[dec.rule != "rival"]
    for r in top.itertuples():
        line = next((ln for ln in RES.splitlines() if ln.startswith(f"| {r.rule} |") and
                     (r.rule == "G" or f"| {r.market} |" in ln)), None)
        assert line is not None, (r.rule, r.market)
        assert f"**{r.verdict}**" in line, (r.rule, r.market, r.verdict)


def test_the_results_quote_the_forecast_and_level_tables():
    fc = pd.read_csv(TAB / "table108_anam_frontier_forecast.csv").set_index(["market", "window", "estimator"])
    for panel in ("DSE 2023-2026", "Vietnam 2007-2020", "DSE 2009-2021"):
        for win in (5, 21):
            assert f4(fc.loc[(panel, win, "Anam"), "QLIKE"]) in RES, (panel, win)
            assert f4(fc.loc[(panel, win, "CC"), "QLIKE"]) in RES, (panel, win)
    lev = pd.read_csv(TAB / "table109_anam_frontier_level.csv").set_index(["market", "estimator"])
    for panel in ("DSE 2023-2026", "Vietnam 2007-2020", "DSE 2009-2021"):
        assert f"{lev.loc[(panel, 'Anam (calibrated)'), 'ratio_to_close_to_close']:.3f}" in RES, panel
