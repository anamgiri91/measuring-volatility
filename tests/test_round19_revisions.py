"""Round 19: the 9 October 2026 audit, the corrected forecast evaluation (plan M20) and the claims it changed.

These re-derive the corrected figures from the tables independently of ``paper/apply_round19_revisions.py``.
They also check four things:

* that the overstatements the audit found survive nowhere: the manuscript, the anonymous copy, the cover letters
  or the README;
* that the frozen record is still reported, and labelled as such;
* that every correction is registered;
* that the M21 plan names the parameter table it froze.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import zipfile

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
DOCX = ROOT / "paper" / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"
ANON = ROOT / "paper" / "submission" / "02_manuscript_anonymous.docx"
OF = "Anam, open-free special case (b=0)"
CLASSICAL = ["P", "GK", "RS", "o2+P", "o2+GK", "YZ (daily form)"]

docx = pytest.importorskip("docx")


@pytest.fixture(scope="module")
def doc():
    return docx.Document(DOCX)


@pytest.fixture(scope="module")
def body(doc):
    return "\n".join(p.text for p in doc.paragraphs)


def primary(df):
    return df[df.apply(lambda r: r["span"] == ("A2+C" if r["market"] == "NEPSE" else "test half"), axis=1)]


def test_table_39_is_the_paper_table_and_follows_table_38(doc):
    assert len(doc.tables) == 39
    assert sum(p.text.startswith("Table 39.") for p in doc.paragraphs) == 1
    t = pd.read_csv(TAB / "paper_table39_m20_corrected.csv", dtype=str).fillna("")
    cells = [[c.text for c in row.cells] for row in doc.tables[38].rows]
    assert cells[0] == list(t.columns) and cells[1:] == t.values.tolist()
    assert len(t) == 14


def test_table_39_rederived_from_the_m20_tables():
    t = pd.read_csv(TAB / "paper_table39_m20_corrected.csv", dtype=str)
    c = primary(pd.read_csv(TAB / "table127_m20_comparison.csv"))
    m = primary(pd.read_csv(TAB / "table128_m20_mcs.csv"))
    for (mk, w), g in c.groupby(["market", "window"]):
        g = g.set_index("model")
        lab = {"NEPSE": "NEPSE, regimes A2 and C", "NIFTY50": "NIFTY 50 (index)", "SP500": "S&P 500 (index)",
               "DSE 2023-2026": "Dhaka 2023-2026", "Vietnam 2007-2020": "Vietnam 2007-2020",
               "DSE 2009-2021": "Dhaka 2009-2021 (dates repaired)", "Morocco 2012-2026": "Morocco 2012-2026"}[mk]
        row = t[(t["Test sample"] == lab) & (t["Horizon (sessions)"] == str(w))].iloc[0]
        assert row["Anam minus close-to-close: t"] == f"{g.loc['Anam', 't_vs_CC']:+.2f}"
        assert row["Open-free form minus close-to-close: t"] == f"{g.loc[OF, 't_vs_CC']:+.2f}"
        mm = m[(m.market == mk) & (m.window == w)].set_index("model")
        ins = " / ".join("yes" if mm.loc[k, "in_mcs_90"] else "no" for k in ("CC", "Anam", OF, "HAR-open-free"))
        assert row.iloc[-1] == ins


def test_the_corrected_claims_quoted_in_the_text_are_the_tables(body):
    v = primary(pd.read_csv(TAB / "table126_m20_verdict_changes.csv"))
    full = v[(v.estimator == "Anam") & v.rival.isin(CLASSICAL)]
    lost = full[full.verdict_corrected == "loses to"]
    assert len(lost) == 1 and lost.iloc[0].rival == "P" and lost.iloc[0].market == "DSE 2023-2026"
    assert f"in one of {len(full)} comparisons on the primary test spans" in body
    assert f"t = {lost.iloc[0].t_corrected:+.2f}".replace("-", "−") in body
    of = v[(v.estimator == OF) & v.rival.isin(CLASSICAL)]
    assert (of.verdict_corrected == "loses to").sum() == 0 and "and than the open-free form in none" in body
    allv = pd.read_csv(TAB / "table126_m20_verdict_changes.csv")
    assert f"Of the {len(allv)} frozen comparisons" in body and f", {int(allv.changed.sum())} then change verdict" in body
    cl = pd.read_csv(TAB / "table129_m20_claims.csv")
    b3 = cl[cl.rule == "B3"]
    of_holm = b3[b3.detail.str.startswith(OF)]
    assert set(of_holm[of_holm.verdict != "beats after Holm"].market) == {"NEPSE"}
    assert "in every sample except NEPSE" in body
    b1 = primary(cl[cl.rule == "B1"])
    assert set(b1[b1.verdict == "range adds information"].market) == {"DSE 2009-2021", "Morocco 2012-2026"}
    assert set(b1[b1.verdict == "returns suffice"].market) == {"DSE 2023-2026"}
    assert "only in the long Dhaka history and in Morocco" in body


def test_the_mcs_and_ablation_counts_quoted_are_the_tables(body):
    m = primary(pd.read_csv(TAB / "table128_m20_mcs.csv"))
    best = m.loc[m.groupby(["market", "window"])["loss"].idxmin(), "model"]
    words = {6: "six", 7: "seven", 10: "ten", 14: "fourteen"}
    assert f"lowest test loss in {words[int((best == 'HAR-open-free').sum())]} of the fourteen" in body
    inn = m.groupby("model")["in_mcs_90"].sum()
    assert inn["HAR-open-free"] == inn["GJR"] == 14
    assert f"is in only {words[int(inn['CC'])]}" in body
    assert not (best == OF).any() and "the open-free form never has the lowest loss" in body
    a = primary(pd.read_csv(TAB / "table130_m20_ablations.csv"))
    full_of = a[(a.model == "Anam") & (a.reference == OF)]
    assert (full_of.verdict == "beats").sum() == 0
    assert f"loses to it in {words[int((full_of.verdict == 'loses to').sum())]} of the fourteen cells" in body


def test_the_audit_corrections_reached_the_manuscript(body):
    for gone in ("natural experiment;", "as a natural experiment", "A natural experiment analysed", "genuine calibration",
                 "had been capping overreaction", "a conditionally unbiased target",
                 "matches the ranking that the true variance would give",
                 "the part of the overnight move that the session keeps", "lower bound on total uncertainty",
                 "can therefore reproduce every reported result", "higher than the 1.288", "v̂ = κA",
                 "shows to be calibration rather than cancellation", "Widening it let transient opening moves grow"):
        assert gone not in body, gone
    for needle in ("slightly lower than the 1.288", "v̂ₜ₋ⱼ = κₜAₜ₋ⱼ", "effective F (Montiel Olea & Pflueger, 2013)",
                   "say nothing about uncertainty concerning latent variance", "which persistence alone does not guarantee",
                   "the band's separate effect is not identified", "not integrated variance", "Proposition 7",
                   "plan M21", "reports itself as partial"):
        assert needle in body, needle


def test_the_frozen_record_is_kept_and_labelled(body):
    assert "The next three paragraphs report the plans' evaluation as frozen (Tables 34-38)" in body
    assert "In the plans' evaluation, the result against the classical estimators is uniform" in body
    assert "the failed predictions are reported as failures" in body


def test_the_robust_first_stage_quoted_is_table_135(body):
    s = pd.read_csv(TAB / "table135_audit_sensitivities.csv").set_index("statistic")["value"]
    f1 = s["effective F, Montiel Olea-Pflueger, two-way (instruments dated t-1 (primary))"]
    f2 = s["effective F, Montiel Olea-Pflueger, two-way (instruments dated t-2)"]
    assert f1 < 23.1 < f2
    assert f"is {f1:.1f}, below the threshold of 23.1" in body and f"reach {f2:.1f}" in body


def test_the_residue_disclosure_is_table_137(body):
    r = pd.read_csv(TAB / "table137_frozen_residue_check.csv")
    for mk, tab in (("NEPSE", "table101_anam_holdout_forecast.csv"), ("DSE 2023-2026", "table108_anam_frontier_forecast.csv"),
                    ("Morocco 2012-2026", "table113_anam_morocco_forecast.csv")):
        fz = pd.read_csv(TAB / tab)
        for row in r[r.market == mk].itertuples():
            q = fz[(fz.market == mk) & (fz.test_span == row.span) & (fz.window == row.window) & (fz.estimator == "Anam")].QLIKE.iloc[0]
            assert abs(q - row.QLIKE_Anam_frozen) < 1e-9, "the residue check's frozen run must be the frozen table"
    assert int(r[[c for c in r.columns if c.endswith("_changed")]].any(axis=1).sum()) == 1
    assert (r[r.market.isin(["NEPSE", "NIFTY50", "SP500"])].residue_targets_test == 0).all()
    infl = (r[r.window == 5].QLIKE_Anam_frozen - r[r.window == 5].QLIKE_Anam_zero)
    infl = infl[infl > 1e-9]
    assert f"by {infl.min():.2f} to {infl.max():.2f}" in body


def test_limitations_run_through_seventeenth(doc):
    paras = [p.text for p in doc.paragraphs]
    i = next(k for k, t in enumerate(paras) if t.startswith("Several limitations"))
    j = next(k for k, t in enumerate(paras) if t.startswith("11. Conclusion"))
    assert sum(t.startswith("Seventeenth,") for t in paras[i + 1:j]) == 1


def test_new_references_and_their_doi_rule(doc):
    paras = [p.text for p in doc.paragraphs]
    i = paras.index("References")
    refs = paras[i + 1:]
    for start, doi in (("Bollerslev, T. (1986)", "https://doi.org/10.1016/0304-4076(86)90063-1"),
                       ("Corsi, F. (2009)", "https://doi.org/10.1093/jjfinec/nbp001"),
                       ("Glosten, L. R., Jagannathan, R., & Runkle, D. E. (1993)", "https://doi.org/10.1111/j.1540-6261.1993.tb05128.x")):
        r = next(x for x in refs if x.startswith(start))
        assert r.endswith(doi)
    mop = next(x for x in refs if x.startswith("Montiel Olea, J. L., & Pflueger, C. (2013)"))
    assert "doi.org" not in mop, "the DOI could not be confirmed, so the house style omits it"


def test_the_letters_and_title_page_carry_the_corrections():
    sub = ROOT / "paper" / "submission"
    for f in sorted(sub.glob("03_cover_letter_*.docx")) + [sub / "01_title_page.docx"]:
        text = "\n".join(p.text for p in docx.Document(f).paragraphs)
        for phrase in ("natural experiment", "A complete package", "reproduce every reported result",
                       "calibration, not offsetting", "capped overreaction", "No classical range estimator forecasts"):
            assert phrase not in text, (f.name, phrase)
    letter = "\n".join(p.text for p in docx.Document(sub / "03_cover_letter_Journal_of_Empirical_Finance.docx").paragraphs)
    assert "a post hoc recheck reports both" in letter and "pins by digest" in letter
    with zipfile.ZipFile(ANON) as z:
        for name in z.namelist():
            if name.endswith(".xml"):
                assert "Anam" not in z.read(name).decode("utf-8", "replace"), name


def test_every_correction_is_registered_and_answered():
    reg = (ROOT / "AUDIT-REGISTER.md").read_text()
    for k in range(28, 35):
        assert f"| `M-0{k}` |" in reg, k
    assert "@@" not in reg
    resp = (ROOT / "RESEARCH_AUDIT_RESPONSE.md").read_text()
    for k in range(1, 16):
        assert f"## A{k:02d}" in resp, k
    assert "To be completed" not in resp


def test_m21_freezes_the_table_it_names():
    plan = (ROOT / "M21_PROSPECTIVE_PLAN.md").read_text()
    t = TAB / "table136_m21_frozen_parameters.csv"
    digest = hashlib.sha256(t.read_bytes()).hexdigest()
    assert digest in plan, "the plan must record the digest of the frozen parameter table"
    p = pd.read_csv(t)
    assert len(p) == 14 * 17 and p.groupby(["sample", "window"]).size().eq(17).all()
    assert "never refitted" in plan


def test_m20_results_document_matches_its_tables():
    text = (ROOT / "M20_CORRECTED_EVALUATION_RESULTS.md").read_text()
    v = pd.read_csv(TAB / "table126_m20_verdict_changes.csv")
    assert f"Of the {len(v)} per-rival verdicts" in text or f"the {len(v)} per-rival verdicts" in text
    assert f"**{int(v.changed.sum())} change**" in text
    t39 = pd.read_csv(TAB / "paper_table39_m20_corrected.csv", dtype=str)
    for row in t39.itertuples(index=False):
        assert row[2].replace("-", "−") in text or row[2] in text
