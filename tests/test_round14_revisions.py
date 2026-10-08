"""Round 14: the manuscript, the results documents and the submission set must agree with the
frozen M14 and M15 tables.

These re-derive every checked figure from the tables independently of
``paper/apply_round14_revisions.py``, so a drift in either the script or the documents fails here.
They also enforce the wording rules both frozen plans set: frozen verdicts quoted as the ledgers
state them, post hoc results labelled where they are quoted, failed predictions reported, the
identification devices credited rather than claimed, and no priority claims.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))     # scripts/34 imports its _env helper
TAB = ROOT / "output" / "tables"
DOCX = ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"

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


@pytest.fixture(scope="module")
def sentences(body):
    return re.split(r"(?<=[.!?])\s+", body)


def f3(v) -> str:
    return f"{float(v):.3f}"


def ci(lo, hi) -> str:
    return f"[{float(lo):.3f}, {float(hi):.3f}]"


def md(s: str) -> str:
    """The results documents print minus signs as U+2212; compare on ASCII."""
    return s.replace("−", "-")


# ─────────────────────────────────────────────────────────────── structure and title

def test_title_matches_the_submission_builder(doc):
    r14 = _load(ROOT / "paper" / "apply_round14_revisions.py", "r14")
    sub = (ROOT / "paper" / "build_submission_set.py").read_text()
    assert doc.paragraphs[0].text == r14.TITLE
    assert doc.paragraphs[1].text == r14.SUBTITLE
    assert f'TITLE = "{r14.TITLE}"' in sub and f'SUBTITLE = "{r14.SUBTITLE}"' in sub


def test_new_sections_tables_and_figures_are_present(doc, body):
    heads = [p.text for p in doc.paragraphs if p.style.name == "Heading 2"]
    assert "6.6 Calibration slopes: what a ratio cannot see" in heads
    assert "6.7 What the opening price measures: a pre-open band reform" in heads
    assert len(doc.tables) == 32
    assert len(doc.inline_shapes) == 8
    for cap in ("Table 29.", "Table 30.", "Table 31.", "Table 32.", "Figure 7.", "Figure 8."):
        assert sum(p.text.startswith(cap) for p in doc.paragraphs) == 1, cap


def test_manuscript_tables_29_to_32_are_the_frozen_paper_tables(doc):
    for k, csv in [(28, "paper_table29_calibration_slopes.csv"),
                   (29, "paper_table30_opening_unbiasedness.csv"),
                   (30, "paper_table31_band_reform_tests.csv"),
                   (31, "paper_table32_open_and_estimators.csv")]:
        t = pd.read_csv(TAB / csv, dtype=str).fillna("")
        cells = [[c.text for c in row.cells] for row in doc.tables[k].rows]
        assert cells[0] == list(t.columns), csv
        assert cells[1:] == t.values.tolist(), csv


# ─────────────────────────────────────────────────────────────── numbers, from the tables

def test_m14_calibration_figures_are_the_frozen_ones(body):
    t = pd.read_csv(TAB / "table78_calibration_full.csv").set_index("measure")
    for k in ("P", "GK", "RS", "AddRS", "AP"):
        assert f"{f3(t.loc[k, 'iv_slope'])} {ci(t.loc[k, 'iv_slope_lo'], t.loc[k, 'iv_slope_hi'])}" in body, k
    h2 = pd.read_csv(TAB / "table79b_slope_gradient.csv").set_index("measure").loc["P"]
    assert f"{f3(h2.slope_Q1_minus_Q5)} {ci(h2.lo, h2.hi)}" in body


def test_m15_unbiasedness_figures_are_the_frozen_ones(body):
    u = pd.read_csv(TAB / "table89_m15_unbiasedness.csv")
    for g in ("A1", "B", "A2", "C"):
        r = u[(u.regime == g) & (u.group == "all") & u.statistic.str.startswith("unbiasedness")].iloc[0]
        if g != "C":
            assert f"{f3(r.value)} {ci(r.lo, r.hi)}" in body, g
        else:
            assert f3(r.value) in body
    n = pd.read_csv(TAB / "table95_m15_nifty.csv")
    r = n[n["sample"].str.startswith("excl") & (n.statistic == "b")].iloc[0]
    assert f"{f3(r.value)} {ci(r.lo, r.hi)}" in body
    w = pd.read_csv(TAB / "table90_m15_event_window.csv")
    j = w[w.window == "jump: post - pre"].iloc[0]
    assert f"{f3(j.value)} {ci(j.lo, j.hi)}" in body
    pl = pd.read_csv(TAB / "table90b_m15_placebo_breaks.csv")
    assert f"None of {len(pl)} placebo splits" in body
    assert f"the most negative is {f3(pl.jump.min())}" in body
    assert (pl.jump > float(j.value)).all(), "the uniqueness claim needs every placebo above the jump"


def test_m15_measurement_figures_are_the_frozen_ones(body):
    y = pd.read_csv(TAB / "table94_m15_yang_zhang.csv")
    r = y[(y.windows == "all windows") & y.statistic.str.startswith("sum YZ")].iloc[0]
    assert f"{f3(r.value)} {ci(r.lo, r.hi)}" in body
    assert f"{float(r.value) ** 0.5:.3f} of Section 6.5" in body
    s = y[(y.windows == "all windows") & y.statistic.str.startswith("share of sum(YZ")].iloc[0]
    assert f"{100 * s.value:.1f}% [{100 * s.lo:.1f}%, {100 * s.hi:.1f}%]" in body
    e = pd.read_csv(TAB / "table93_m15_estimator_evaluation.csv")
    for stat in ("change in E[X]/E[OC]", "change in E[X]/E[K]"):
        r = e[(e.regime == "C - A2") & (e.measure == "P") & (e.statistic == stat)].iloc[0]
        assert f"{f3(r.value)} {ci(r.lo, r.hi)}" in body, stat


def test_m15_figures_quoted_in_the_abstract_are_the_frozen_ones(doc):
    findings = next(p.text for p in doc.paragraphs if p.text.startswith("Findings:"))
    t = pd.read_csv(TAB / "table78_calibration_full.csv").set_index("measure").loc["P"]
    assert f"{f3(t.iv_slope)} {ci(t.iv_slope_lo, t.iv_slope_hi)}" in findings
    j = pd.read_csv(TAB / "table90_m15_event_window.csv")
    jump = float(j[j.window == "jump: post - pre"].value.iloc[0])
    assert f"fell by {abs(jump):.3f}" in findings
    assert f"{len(pd.read_csv(TAB / 'table90b_m15_placebo_breaks.csv'))} placebo dates" in findings


# ─────────────────────────────────────────────────────────────── verdicts and wording rules

def test_frozen_verdicts_are_quoted_as_the_ledgers_state_them(body):
    led = pd.read_csv(TAB / "table96_m15_decisions.csv").set_index("hypothesis")["verdict"]
    assert led["H7"] == "sharp break" and "The frozen verdict is a sharp break" in body
    assert led["H11"] == "confirmed" and "(frozen verdict: confirmed)" in body
    assert f"returns '{led['H10 (consequence)']}'" in body
    assert led["H8"] == "not detected" and "was not detected (difference-in-differences" in body
    assert led["H9(a)"] == "not detected" and "predicted delayed price discovery, and the data reject it" in body
    m14 = pd.read_csv(TAB / "table86_m14_decisions.csv")
    assert set(m14[m14.hypothesis == "H1"].verdict) == {"no detectable attenuation"}
    assert "the frozen verdict for all three is no detectable attenuation" in body


def test_failed_predictions_are_reported(body):
    assert "Three pre-specified predictions failed and are reported as such" in body
    assert "its dose-response leg was not detected" in body


def test_post_hoc_results_are_labelled_where_quoted(sentences):
    markers = ("open's error at no less than", "off the exchange's 0.1-rupee price grid",
               "an open pinned at the new upper band", "which a non-stale NEPSE open is on",
               "of opens sat at the band")
    for s in sentences:
        for m in markers:
            if m in s:
                assert "post hoc" in s, f"unlabelled post hoc result: {s[:100]!r}"


def test_identification_devices_are_credited_and_listed(body):
    paras = body.split("\n")
    i = paras.index("References")
    refs = "\n".join(paras[i + 1:])
    for cite, ref in [("Christensen and Prabhala (1998)", "Christensen, B. J., & Prabhala, N. R. (1998)"),
                      ("Hansen and Lunde (2014)", "Hansen, P. R., & Lunde, A. (2014)"),
                      ("Arellano & Bover, 1995", "Arellano, M., & Bover, O. (1995)"),
                      ("Biais, Hillion & Spatt, 1999", "Biais, B., Hillion, P., & Spatt, C. (1999)"),
                      ("Barclay & Hendershott, 2003", "Barclay, M. J., & Hendershott, T. (2003)"),
                      ("Kim & Rhee, 1997", "Kim, K. A., & Rhee, S. G. (1997)"),
                      ("Zhou's (1996)", "Zhou, B. (1996)"),
                      ("Amihud & Mendelson, 1987", "Amihud, Y., & Mendelson, H. (1987)"),
                      ("Stoll & Whaley, 1990", "Stoll, H. R., & Whaley, R. E. (1990)")]:
        assert cite in body, cite
        assert ref in refs, ref
    assert "only its application to daily-bar estimators is new here" in body


def test_no_priority_claims_or_unqualified_noise(body):
    low = body.lower()
    for phrase in ("first study", "the first to", "fills a gap", "no prior study", "is noise",
                   "systematic review", "primarily index-level", "proves that"):
        assert phrase not in low, phrase


def test_the_m13_honesty_statements_survive(body):
    assert "no claim is made to introduce security-level" in body
    assert "makes no claim to introduce security-level" in body
    assert "addresses a measurement question not identified in the targeted search" in body


def test_rule_dates_in_the_text_match_the_code():
    s34 = _load(ROOT / "scripts" / "34_instrumented_calibration.py", "s34_r14")
    r = {name: (a, b) for name, a, b, _ in s34.REGIMES}
    assert r["B"] == ("2025-03-20", "2025-09-21") and r["C"][0] == "2026-04-20"
    from nepsevol import opening as op
    assert str(op.BAND_REFORM.date()) == "2026-04-20" and str(op.WEEK_REFORM.date()) == "2026-04-06"
    text = "\n".join(p.text for p in docx.Document(DOCX).paragraphs)
    assert "From 20 March to 21 September 2025" in text
    assert "On 20 April 2026 NEPSE widened the pre-open band" in text


def test_limitations_run_contiguously_through_fourteenth(doc):
    paras = [p.text for p in doc.paragraphs]
    i = next(k for k, t in enumerate(paras) if t.startswith("Several limitations"))
    j = next(k for k, t in enumerate(paras) if t == "11. Conclusion")
    ords = ["Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
            "Eleventh", "Twelfth", "Thirteenth", "Fourteenth"]
    found = [t.split(",")[0] for t in paras[i + 1:j] if t.split(",")[0] in ords]
    assert found == ords


def test_reference_list_is_alphabetical(doc):
    paras = [p.text for p in doc.paragraphs]
    i = paras.index("References")
    j = next(k for k, t in enumerate(paras) if t.startswith("Data and reproducibility note"))
    refs = [t for t in paras[i + 1:j] if t.strip()]
    keys = [re.sub(r"^(The )", "", r).lower() for r in refs]
    assert keys == sorted(keys)


# ─────────────────────────────────────────────────────────────── results documents (M-010)

def test_m14_results_document_matches_its_tables():
    text = md((ROOT / "M14_CALIBRATION_RESULTS.md").read_text())
    h2 = pd.read_csv(TAB / "table79b_slope_gradient.csv").set_index("measure").loc["P"]
    assert f"+{f3(h2.slope_Q1_minus_Q5)} [{f3(h2.lo)}, +{f3(h2.hi)}]" in text
    em = pd.read_csv(TAB / "table83_endpoint_moments.csv")
    oc = em[em.moment == "E[o_t c_t]/E[P]"].set_index("regime").value
    assert f"{f3(oc['A1'])}, {f3(oc['B'])}, {f3(oc['A2'])} under the ±2% band" in text
    mc = pd.read_csv(TAB / "table74_mc_calibration.csv")
    rng = mc[mc.measure.isin(["P", "GK", "RS"]) & (mc.scenario != "S0_brownian")].iv_slope_bias
    assert f"+{f3(rng.min())} to +{f3(rng.max())} for the range estimators" in text
    t78 = pd.read_csv(TAB / "table78_calibration_full.csv").set_index("measure")
    for k in ("P", "GK", "RS"):
        r = t78.loc[k]
        assert (f"{f3(r.iv_slope)} [{f3(r.iv_slope_lo)}, {f3(r.iv_slope_hi)}]; "
                f"{f3(r.additive_share)} [{f3(r.additive_share_lo)}, {f3(r.additive_share_hi)}]") in text, k
    e2 = pd.read_csv(TAB / "table88_endpoint_noise_share.csv")
    sh = e2[e2.quantity.str.startswith("transient")].set_index("regime")
    for g in ("A1", "B", "A2", "C"):
        r = sh.loc[g]
        assert f"{100 * r.value:.1f}% [{100 * r.lo:.1f}, {100 * r.hi:.1f}]" in text, g
    assert "*[Description corrected by `M-007`.]*" in text


def test_m15_results_document_matches_its_tables():
    text = md((ROOT / "M15_OPENING_PRICE_RESULTS.md").read_text())
    led = pd.read_csv(TAB / "table96_m15_decisions.csv").set_index("hypothesis")
    for h in ("H9(a)", "H9(b)"):
        assert led.loc[h, "estimate"] in text, h
    u = pd.read_csv(TAB / "table89_m15_unbiasedness.csv")
    for g in ("A1", "B", "A2", "C"):
        r = u[(u.regime == g) & (u.group == "all") & u.statistic.str.startswith("unbiasedness")].iloc[0]
        assert f"{f3(r.value)} {ci(r.lo, r.hi)}" in text, g
    x = pd.read_csv(TAB / "table97_m15_posthoc.csv")
    lb = x[(x.regime == "C") & x.statistic.str.startswith("lower bound")].iloc[0]
    assert f"{100 * lb.value:.1f}% [{100 * lb.lo:.1f}, {100 * lb.hi:.1f}]" in text
    y = pd.read_csv(TAB / "table94_m15_yang_zhang.csv")
    s = y[(y.windows == "all windows") & y.statistic.str.startswith("share of sum(YZ")].iloc[0]
    assert f"{100 * s.value:.1f}% [{100 * s.lo:.1f}, {100 * s.hi:.1f}]" in text
    for verdict in ("sharp break", "overshoot only", "no inversion established"):
        assert verdict in text


def test_every_correction_id_cited_is_in_the_audit_register():
    reg = (ROOT / "AUDIT-REGISTER.md").read_text()
    cited = set()
    for f in ("M14_CALIBRATION_RESULTS.md", "M15_OPENING_PRICE_RESULTS.md"):
        cited |= set(re.findall(r"M-0\d\d", (ROOT / f).read_text()))
    missing = {c for c in cited if f"`{c}`" not in reg}
    assert not missing, f"cited but not registered: {missing}"


# ─────────────────────────────────────────────────────────────── package ledgers

def test_results_check_carries_the_m14_and_m15_figures():
    chk = pd.read_csv(ROOT / "PAPER_RESULTS_CHECK.csv").set_index("Result")["Value"]
    u = pd.read_csv(TAB / "table89_m15_unbiasedness.csv")
    for g in ("A1", "B", "A2", "C"):
        v = u[(u.regime == g) & (u.group == "all") & u.statistic.str.startswith("unbiasedness")].value.iloc[0]
        assert f"{g} {f3(v)}" in chk["M15_unbiasedness_coefficient_by_regime"]
    assert "H7 sharp break" in chk["M15_decision_verdicts"]
    assert chk["M14_H1_Parkinson_calibration_slope"].startswith("0.919")


def test_cover_letters_drop_the_superseded_vix_ordering_claim():
    src = (ROOT / "paper" / "build_submission_set.py").read_text()
    assert "its apparent estimator ordering reverses" not in src
    assert "TOP_TIER + JOURNALS" in src
