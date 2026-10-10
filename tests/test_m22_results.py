"""M22: the frozen plan, the tables and the results document must agree.

The quoted figures are re-derived from the tables, so drift between the document and the numbers it cites
fails here."""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TAB = ROOT / "output" / "tables"

from nepsevol import frontier as F  # noqa: E402
from nepsevol.estimators import anam2 as A2  # noqa: E402

PLAN = (ROOT / "M22_ANAM2_PLAN.md").read_text()
RES = (ROOT / "M22_ANAM2_RESULTS.md").read_text().replace("−", "-")
PANELS = ["NEPSE", "DSE 2023-2026", "DSE 2009-2021", "Vietnam 2007-2020", "Morocco 2012-2026", "Pakistan 2016-2026"]


def test_the_plan_pins_the_unseen_market_and_the_module_constants():
    assert F.PSX_SHA256 in PLAN and F.PSX_META_SHA256 in PLAN and F.PSX_COMMIT in PLAN
    assert F.PSX_BANDS == ((None, 0.05), ("2020-01-20", 0.075), ("2024-05-27", 0.10))
    assert "5% before 20 January 2020" in PLAN and "10% from 27 May 2024" in PLAN
    assert A2.LAMBDA0 == 0.2 and A2.FLOOR == 0.05 and A2.EPS == 1e-12
    assert "at least 0.05" in PLAN and "|o| < 1e−12" in PLAN


def test_the_reference_forecast_reproduces_m20_on_its_rows():
    m22 = pd.read_csv(TAB / "table138_m22_comparison.csv")
    m20 = pd.read_csv(TAB / "table127_m20_comparison.csv")
    a = m22[m22.model == "HAR-open-free"].merge(m20[m20.model == "HAR-open-free"],
                                                 on=["market", "span", "window"], suffixes=("", "_m20"))
    assert len(a) == len(m20[m20.model == "HAR-open-free"]) == 18
    assert (a["n"] == a["n_m20"]).all() and (a["n_m20_rows"] == a["n_m20"]).all()
    assert np.allclose(a["QLIKE_canonical"], a["QLIKE_canonical_m20"], rtol=0, atol=1e-9)
    assert (a["parameters"] == a["parameters_m20"]).all()


def test_the_claims_follow_the_plans_rules():
    cl = pd.read_csv(TAB / "table139_m22_claims.csv")
    for (h, w), g in cl[cl.hypothesis.isin(["H1", "H2", "H3"])].groupby(["hypothesis", "window"]):
        assert sorted(g.market) == sorted(PANELS), (h, w)
        p = g.sort_values("p")["p"].to_numpy()
        adj = np.maximum.accumulate(np.minimum(1.0, (len(p) - np.arange(len(p))) * p))
        assert np.allclose(np.sort(g["p_holm"].to_numpy()), np.sort(adj))
        for r in g.itertuples():
            want = ("better" if r.d < 0 else "worse") if r.p_holm < 0.05 else "no detectable difference"
            assert r.verdict == want, (h, w, r.market)
    h1 = cl[cl.hypothesis == "H1"]
    better5 = int(((h1.window == 5) & (h1.verdict == "better")).sum())
    worse = int((h1.verdict == "worse").sum())
    assert (better5, worse) == (3, 0)
    p1 = cl.loc[cl.hypothesis == "P1", "verdict"].iloc[0]
    assert p1.startswith("supported") and "supported" in RES and '"supported"' in RES


def test_the_results_quote_the_primary_table():
    cl = pd.read_csv(TAB / "table139_m22_claims.csv")
    short = {"NEPSE": "NEPSE (A2+C)", "DSE 2023-2026": "Dhaka 2023–26", "DSE 2009-2021": "Dhaka 2009–21",
             "Vietnam 2007-2020": "Vietnam", "Morocco 2012-2026": "Morocco", "Pakistan 2016-2026": "**Pakistan (unseen)**"}
    for h in ("H1", "H2", "H3"):
        for mk in PANELS:
            r5 = cl[(cl.hypothesis == h) & (cl.market == mk) & (cl.window == 5)].iloc[0]
            lines = [ln for ln in RES.splitlines() if ln.startswith(f"| {short[mk]} | {r5.d:+.4f} | {r5.t:+.2f} |")]
            assert lines, (h, mk)
    pk = cl[(cl.hypothesis == "H1") & (cl.market == "Pakistan 2016-2026")].set_index("window")
    assert f"d = {pk.loc[5, 'd']:.4f}, t = {pk.loc[5, 't']:.2f}" in RES
    assert f"Holm p = {pk.loc[21, 'p_holm']:.3f}" in RES


def test_the_results_quote_the_pakistan_panel():
    pan = pd.read_csv(TAB / "table141_m22_panels.csv").set_index("sample").loc["Pakistan 2016-2026"]
    for key in ("rule: no-trade records", "rule: envelope violations dropped", "rule: bars outside the band",
                "rule: stock-days", "rule: test stock-days", "rule: bars without a previous close"):
        assert f"{int(pan[key]):,}" in RES, key
    assert pan["rule: first test session"] in RES and int(pan["securities"]) == 101
    assert f"{pan['b_pooled']:.2f}" in RES and f"{pan['b_market']:.2f}" in RES and f"{pan['b_stock']:.2f}" in RES


def test_the_prospective_table_covers_every_sample_and_horizon():
    fw = pd.read_csv(TAB / "table142_m22_frozen_weights.csv")
    assert set(fw["sample"]) == set(PANELS) | {"NIFTY50", "SP500"}
    for (s, w), g in fw.groupby(["sample", "window"]):
        want = {"Anam II", "HAR-open-free"} | ({"FHARL open-free"} if s in PANELS else set())
        assert set(g.model) == want, (s, w)
        for p in g[g.model != "HAR-open-free"]["parameters"]:
            c = np.array(eval(p))
            assert abs(c.sum() - 1) < 1e-9 and c[-1] >= A2.FLOOR - 1e-9 and (c >= -1e-12).all()
