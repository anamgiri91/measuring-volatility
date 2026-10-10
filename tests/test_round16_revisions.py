"""Round 16: the overstatements a recheck found are corrected, and the recheck is in the manuscript.

These re-derive the corrected figures from the frozen tables independently of
``paper/apply_round16_revisions.py``, and check that no corrected wording survives in the
manuscript, the anonymous copy, the cover letters or the README.
"""
from __future__ import annotations

import pathlib
import re
import zipfile

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
DOCX = ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"
ANON = ROOT / "paper" / "submission" / "02_manuscript_anonymous.docx"
RANGE = ["P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"]

docx = pytest.importorskip("docx")


@pytest.fixture(scope="module")
def doc():
    return docx.Document(DOCX)


@pytest.fixture(scope="module")
def body(doc):
    return "\n".join(p.text for p in doc.paragraphs)


def tt(v) -> str:
    return f"{float(v):+.2f}".replace("-", "−")


def test_tables_37_and_38_are_the_frozen_paper_tables(doc):
    assert len(doc.tables) >= 38 and len(doc.inline_shapes) == 8   # round 19 adds Table 39
    for cap in ("Table 37.", "Table 38."):
        assert sum(p.text.startswith(cap) for p in doc.paragraphs) == 1, cap
    for k, csv in [(36, "paper_table37_anam_robustness.csv"), (37, "paper_table38_anam_level_same_calibration.csv")]:
        t = pd.read_csv(TAB / csv, dtype=str).fillna("")
        cells = [[c.text for c in row.cells] for row in doc.tables[k].rows]
        assert cells[0] == list(t.columns), csv
        assert cells[1:] == t.values.tolist(), csv


OVERSTATED = [
    "Every analysis follows a plan frozen", "first two rule regimes alone", "before any later observation was read",
    "before any holdout observation was read", "pre-registered test", "determines what daily bars measure",
    "validated out of sample", "developed and validated", "the data say that trust should be measured",
    "where the open is close to efficient", "No classical range estimator beats", "beaten by no classical range",
    "many bars have no range at all", "Where one daily estimator must serve", "pooled medians between",
    "What is added is that the open's weight is measured", "Nepal, Bangladesh or Vietnam",
]


def test_no_corrected_overstatement_survives_in_the_manuscript(body):
    for phrase in OVERSTATED:
        assert phrase not in body, phrase


def test_no_corrected_overstatement_survives_in_the_letters_or_the_readme():
    letters = sorted((ROOT / "paper" / "submission").glob("03_cover_letter_*.docx"))
    assert len(letters) == 6
    for f in letters:
        text = "\n".join(p.text for p in docx.Document(f).paragraphs)
        for phrase in ("determines what", "validated out of sample", "pre-registered", "two-thirds or more",
                       "No classical range estimator beats", "whose opening price overreacts"):
            assert phrase not in text, (f.name, phrase)
        assert "a post hoc recheck reports both" in text, f.name
    readme = (ROOT / "README.md").read_text()
    for phrase in ("Every analysis ran under a plan", "within 1.2%", "Designed on NEPSE regimes A1 and B only",
                   "No classical range estimator beats", "It is the form the frontier-market evidence supports"):
        assert phrase not in readme, phrase
    assert "ANAM_RECHECK_POSTHOC.md" in readme


def test_the_level_is_attributed_to_the_calibration(body):
    lev = pd.read_csv(TAB / "table117_anam_recheck_level.csv")
    stable = lev[~((lev.market == "NEPSE") & lev.span.isin(["C", "A2+C"]))]
    cls = stable[stable.estimator.isin(RANGE)]
    assert f"within {100 * (cls.calibrated_ratio - 1).abs().max():.1f}% of close-to-close variance" in body
    lag_cls = 100 * (cls.calibrated_before_window_ratio - 1).abs().max()
    lag_anam = 100 * (stable[stable.estimator == "Anam"].calibrated_before_window_ratio - 1).abs().max()
    assert f"the estimator is within {lag_anam:.1f}% and the classical estimators within {lag_cls:.1f}%" in body
    assert "the calibration's doing" in body
    c = lev[(lev.market == "NEPSE") & (lev.span == "C")].set_index("estimator").calibrated_ratio
    assert c["Anam"] < c[RANGE].min()
    assert f"({c[RANGE].min():.3f} to {c[RANGE].max():.3f})" in body


def test_fragile_results_are_disclosed(body):
    mult = pd.read_csv(TAB / "table119_anam_recheck_multiplicity.csv")
    ma = mult[(mult.plan == "M18") & (mult.rule == "F1")].iloc[0]
    assert bool(ma["frozen verdict: beats"]) and not bool(ma["beats after Holm across plans"])
    assert f"(p = {ma['Holm p across plans']:.3f})" in body
    others = mult[mult["frozen verdict: beats"] & ~((mult.plan == "M18") & (mult.rule == "F1"))]
    assert others["beats after Holm across plans"].all()
    f113 = pd.read_csv(TAB / "table113_anam_morocco_forecast.csv")
    four = f113[(f113.window == 5) & (f113.estimator == "Anam") & f113.test_span.str.startswith("4%")].t_vs_CC.iloc[0]
    assert f"(t = {tt(four)} there" in body
    assert "The Moroccan difference is the least secure." in body


def test_the_sp500_coincidence_and_the_index_attribution(body):
    f = pd.read_csv(TAB / "table101_anam_holdout_forecast.csv")
    sp = f[(f.market == "SP500") & (f.window == 5)].set_index("estimator")
    assert abs(sp.loc["Anam", "QLIKE"] - sp.loc["o2+P", "QLIKE"]) < 1e-9
    lower = int((sp.loc[RANGE, "QLIKE"] < sp.loc["Anam", "QLIKE"]).sum())
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    assert f"{words[lower]} classical estimators had nominally lower loss there" in body
    assert "the estimator coincides with overnight² + Parkinson" in body
    assert "On the indices it shares those wins with the classical range estimators" in body


def test_nepse_protocol_keeps_close_to_close_primary(body):
    assert "so close-to-close remains the primary measure here" in body


def test_every_reading_of_the_recheck_is_labelled_post_hoc(body):
    # Round 19 adds plan M20, whose Holm adjustment was fixed in advance; a sentence that reports it is labelled
    # by its table (39) or its plan instead, so this rule now accepts either label too. Round 20 does the same for
    # plan M22 (Table 40).
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if "MSE" in sentence or "Holm" in sentence:
            assert ("post hoc" in sentence.lower() or "Table 37" in sentence or "Tables 37 and 38" in sentence
                    or "Table 39" in sentence or "plan M20" in sentence or "Table 40" in sentence
                    or "plan M22" in sentence), sentence[:100]


def test_limitations_run_through_sixteenth():
    paras = [p.text for p in docx.Document(DOCX).paragraphs]
    i = next(k for k, t in enumerate(paras) if t.startswith("Several limitations"))
    j = paras.index("11. Conclusion")
    assert sum(t.startswith("Sixteenth,") for t in paras[i + 1:j]) == 1
    assert sum(t.startswith("Fifteenth,") for t in paras[i + 1:j]) == 1


def test_abstract_still_within_cap_and_free_of_index_figures(doc):
    ps = doc.paragraphs
    i = next(k for k, p in enumerate(ps) if p.text.strip() == "Abstract")
    assert sum(len(p.text.split()) for p in ps[i + 1:i + 5]) <= 255
    findings = next(p.text for p in ps if p.text.startswith("Findings:"))
    assert "NIFTY" not in findings and "depend partly on the loss function" in findings


def test_anonymous_copy_still_carries_no_trace_of_the_eponym():
    with zipfile.ZipFile(ANON) as z:
        for name in z.namelist():
            if name.endswith((".xml", ".rels")):
                assert "Anam" not in z.read(name).decode("utf-8", "replace"), name
    text = "\n".join(p.text for p in docx.Document(ANON).paragraphs)
    assert "Table 37." in text and "Table 38." in text
