"""Round 15: Anam's estimator in the manuscript must agree with the frozen M16-M18 tables.

These re-derive the checked figures from the tables independently of
``paper/apply_round15_revisions.py``, and check the anonymous submission copy, in which the
estimator's eponym -- the author's own name -- must not survive anywhere in the file.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
import zipfile

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TAB = ROOT / "output" / "tables"
DOCX = ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"
ANON = ROOT / "paper" / "submission" / "02_manuscript_anonymous.docx"
VARIANT = "Anam, open-free special case (b=0)"

docx = pytest.importorskip("docx")


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def doc():
    return docx.Document(DOCX)


@pytest.fixture(scope="module")
def body(doc):
    return "\n".join(p.text for p in doc.paragraphs)


def tt(v) -> str:
    return f"{float(v):+.2f}".replace("-", "−")


def test_structure_title_and_new_section(doc, body):
    r15 = _load(ROOT / "paper" / "apply_round15_revisions.py", "r15_t")
    assert doc.paragraphs[0].text == r15.TITLE and doc.paragraphs[1].text == r15.SUBTITLE
    heads = [p.text for p in doc.paragraphs if p.style.name == "Heading 2"]
    assert "6.8 An estimator for an overreacting open: Anam's estimator" in heads
    assert len(doc.tables) == 36 and len(doc.inline_shapes) == 8
    for cap in ("Table 33.", "Table 34.", "Table 35.", "Table 36."):
        assert sum(p.text.startswith(cap) for p in doc.paragraphs) == 1, cap
    assert "This paper asks five questions" in body


def test_manuscript_tables_33_to_36_are_the_frozen_paper_tables(doc):
    for k, csv in [(32, "paper_table33_anam_definition.csv"), (33, "paper_table34_anam_forecasts.csv"),
                   (34, "paper_table35_anam_level.csv"), (35, "paper_table36_anam_verdicts.csv")]:
        t = pd.read_csv(TAB / csv, dtype=str).fillna("")
        cells = [[c.text for c in row.cells] for row in doc.tables[k].rows]
        assert cells[0] == list(t.columns), csv
        assert cells[1:] == t.values.tolist(), csv


def test_definition_table_carries_the_module_constants():
    from nepsevol.estimators import anam as AN
    t = pd.read_csv(TAB / "paper_table33_anam_definition.csv").set_index("Step")
    assert f"λ₀ = {AN.LAMBDA0}" == t.loc["Daily kernel", "Constant (frozen in plan M16)"]
    assert f"last {AN.POOL_SESSIONS} dates" in t.loc["Open quality b", "Constant (frozen in plan M16)"]
    assert f"last {AN.SERIES_SESSIONS} sessions" in t.loc["Open quality b", "Constant (frozen in plan M16)"]


def test_forecast_figures_quoted_in_section_6_8_are_the_frozen_ones(body):
    f = pd.concat([pd.read_csv(TAB / "table101_anam_holdout_forecast.csv"),
                   pd.read_csv(TAB / "table108_anam_frontier_forecast.csv"),
                   pd.read_csv(TAB / "table113_anam_morocco_forecast.csv")])
    def row(mk, span, w, est):
        return f[(f.market == mk) & (f.test_span == span) & (f.window == w) & (f.estimator == est)].iloc[0]
    for mk, span in [("NIFTY50", "test half"), ("SP500", "test half"), ("Morocco 2012-2026", "test half"),
                     ("DSE 2009-2021", "test half"), ("NEPSE", "A2+C"), ("DSE 2023-2026", "test half"),
                     ("Vietnam 2007-2020", "test half")]:
        assert f"t = {tt(row(mk, span, 5, 'Anam').t_vs_CC)}" in body or tt(row(mk, span, 5, "Anam").t_vs_CC) in body, mk
    assert tt(row("NEPSE", "C", 5, "Anam").t_vs_CC) in body and tt(row("NEPSE", "C", 21, "Anam").t_vs_CC) in body
    assert tt(row("Vietnam 2007-2020", "test half", 21, "Anam").t_vs_CC) in body
    m = row("Morocco 2012-2026", "test half", 5, VARIANT)
    cc = row("Morocco 2012-2026", "test half", 5, "CC")
    assert f"({m.QLIKE:.4f} against {cc.QLIKE:.4f}, t = {tt(m.t_vs_CC)})" in body
    full = row("Morocco 2012-2026", "test half", 5, "Anam")
    assert f"the full estimator (t = {tt(-full[f't_vs_{VARIANT}'])})" in body


def test_level_claim_is_the_frozen_one(body):
    lv = pd.concat([pd.read_csv(TAB / "table102_anam_holdout_level.csv"),
                    pd.read_csv(TAB / "table109_anam_frontier_level.csv"),
                    pd.read_csv(TAB / "table114_anam_morocco_level.csv")])
    cal = lv[(lv.estimator == "Anam (calibrated)") & lv.span.isin(["A2", "C", "test half"])]
    stable = cal[~((cal.market == "NEPSE") & (cal.span == "C"))].ratio_to_close_to_close
    assert f"within {100 * (stable - 1).abs().max():.1f}% of close-to-close" in body
    assert f"{cal[(cal.market == 'NEPSE') & (cal.span == 'C')].ratio_to_close_to_close.iloc[0]:.3f}" in body


def test_verdicts_failures_and_post_hoc_labels(body):
    d105 = pd.read_csv(TAB / "table105_anam_holdout_decisions.csv")
    d111 = pd.read_csv(TAB / "table111_anam_frontier_decisions.csv")
    d116 = pd.read_csv(TAB / "table116_anam_morocco_decisions.csv")
    assert d105[(d105.rule == "H1") & (d105.market == "NEPSE")].verdict.iloc[0] == "does not hold"
    assert set(d111[d111.rule == "F1"].set_index("market").verdict[["DSE 2023-2026", "Vietnam 2007-2020"]]) == {"does not hold"}
    assert set(d116[d116.rule.isin(["V1", "V2", "V3", "O"])].verdict) == {"holds"}
    assert "the failed predictions are reported as failures" in body
    for s in re.split(r"(?<=[.!?])\s+", body):
        if "lowest five-session" in s and "second plan" in s:
            assert "post hoc" in s, s[:100]
    for phrase in ("first study", "the first to", "is noise", "proves that", "fills a gap"):
        assert phrase not in body.lower()


def test_abstract_cap_and_index_rule(doc):
    ps = doc.paragraphs
    i = next(k for k, p in enumerate(ps) if p.text.strip() == "Abstract")
    assert sum(len(p.text.split()) for p in ps[i + 1:i + 5]) <= 255
    findings = next(p.text for p in ps if p.text.startswith("Findings:"))
    assert "NIFTY" not in findings and "Anam's estimator" in findings


def test_new_references_follow_the_doi_rule(doc):
    paras = [p.text for p in doc.paragraphs]
    i = paras.index("References")
    refs = [t for t in paras[i + 1:] if t.strip()]
    nw = next(r for r in refs if r.startswith("Newey, W. K., & West, K. D. (1987)"))
    assert nw.endswith("https://doi.org/10.2307/1913610")
    for start in ("Diebold, F. X., & Mariano, R. S. (1995)", "Hansen, P. R., & Lunde, A. (2005)"):
        r = next(r for r in refs if r.startswith(start))
        assert "doi.org" not in r, f"{start}: DOI not confirmed (M-019)"
    assert any(r.startswith("Wilder, J. W. (1978)") for r in refs)
    assert "`M-019`" in (ROOT / "AUDIT-REGISTER.md").read_text()


def test_limitations_run_through_fifteenth(doc):
    paras = [p.text for p in doc.paragraphs]
    i = next(k for k, t in enumerate(paras) if t.startswith("Several limitations"))
    j = paras.index("11. Conclusion")
    assert sum(t.startswith("Fifteenth,") for t in paras[i + 1:j]) == 1


def test_anonymous_copy_carries_no_trace_of_the_eponym():
    r15 = _load(ROOT / "paper" / "apply_round15_revisions.py", "r15_anon")
    stem = r15.NAME.split("'")[0]
    with zipfile.ZipFile(ANON) as z:
        for name in z.namelist():
            if name.endswith((".xml", ".rels")):
                assert stem not in z.read(name).decode("utf-8", "replace"), name
    text = "\n".join(p.text for p in docx.Document(ANON).paragraphs)
    assert "6.8 An estimator for an overreacting open: the proposed estimator" in text
    assert "The proposed estimator weights the overnight move" in text
