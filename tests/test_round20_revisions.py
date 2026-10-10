"""Round 20: Anam II, the market-implied open (plan M22), in the manuscript.

These re-derive the quoted figures from the M22 tables independently of ``paper/apply_round20_revisions.py``.
They also check four things:

* Table 40 is the paper table and follows Table 39;
* Pakistan, the market used at no stage of the design, is named as such, and the seen spans are called seen;
* the statements the round-20 checks corrected survive nowhere they are not frozen;
* the anonymous copy carries no trace of the eponym, in either generation's name.
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
SUB = ROOT / "paper" / "submission"
PK = "Pakistan 2016-2026"
PANELS = ["NEPSE", "DSE 2023-2026", "DSE 2009-2021", "Vietnam 2007-2020", "Morocco 2012-2026", PK]
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

docx = pytest.importorskip("docx")


@pytest.fixture(scope="module")
def doc():
    return docx.Document(DOCX)


@pytest.fixture(scope="module")
def body(doc):
    return "\n".join(p.text for p in doc.paragraphs)


@pytest.fixture(scope="module")
def claims():
    return pd.read_csv(TAB / "table139_m22_claims.csv")


def tt(v) -> str:
    return f"{v:+.2f}".replace("-", "−")


def test_table_40_is_the_paper_table_and_follows_table_39(doc):
    assert len(doc.tables) == 40
    caps = [p.text for p in doc.paragraphs if re.match(r"Table \d+\. ", p.text)]
    assert caps.index(next(c for c in caps if c.startswith("Table 40."))) == caps.index(
        next(c for c in caps if c.startswith("Table 39."))) + 1
    t = pd.read_csv(TAB / "paper_table40_m22_anam2.csv", dtype=str).fillna("")
    cells = [[c.text for c in row.cells] for row in doc.tables[39].rows]
    assert cells[0] == list(t.columns) and cells[1:] == t.values.tolist()
    assert len(t) == 12


def test_table_40_rederived_from_the_m22_tables(claims):
    t = pd.read_csv(TAB / "paper_table40_m22_anam2.csv", dtype=str)
    mcs = pd.read_csv(TAB / "table140_m22_mcs.csv")
    labels = dict(zip(t["Test sample"].unique(), PANELS))
    for r in t.itertuples(index=False):
        mk, w = labels[r[0]], int(r[1])
        for k, h in enumerate(("H1", "H2", "H3")):
            c = claims[(claims.hypothesis == h) & (claims.market == mk) & (claims.window == w)].iloc[0]
            assert r[2 + 2 * k] == f"{c.d:+.4f} ({c.t:+.2f})", (mk, w, h)
            p = "<0.001" if c.p_holm < 0.001 else f"{c.p_holm:.3f}"
            assert r[3 + 2 * k].startswith(p + " ("), (mk, w, h)
            assert ("better" in r[3 + 2 * k]) == (c.verdict == "better")
            assert ("inside the margin" in r[3 + 2 * k]) == bool(c.practically_equivalent and c.verdict != "better")
        sp = "A2+C" if mk == "NEPSE" else "test half"
        m = mcs[(mcs.market == mk) & (mcs.span == sp) & (mcs.window == w)].set_index("model")["in_mcs_90"]
        assert r[8] == " / ".join("yes" if m[k] else "no" for k in ("Anam II", "HAR-open-free", "r* (best return-only)"))
    assert "(unseen)" in t["Test sample"].iloc[-1] and labels[t["Test sample"].iloc[-1]] == PK


def test_section_69_quotes_the_primary_reading(body, claims):
    h1 = claims[claims.hypothesis == "H1"]
    better5 = h1[(h1.window == 5) & (h1.verdict == "better")]
    assert len(better5) == 3 and (h1.verdict == "worse").sum() == 0
    assert "6.9 A second estimator: the market-implied open (Anam II)" in body
    assert "The plan's primary reading is supported (Table 40)." in body
    for mk, name in (("DSE 2023-2026", "the recent Dhaka panel"), ("Vietnam 2007-2020", "Vietnam"), (PK, "Pakistan")):
        assert f"{name} (t = {tt(better5.set_index('market').loc[mk, 't'])})" in body, mk
    pk21 = h1[(h1.market == PK) & (h1.window == 21)].iloc[0]
    assert f"(t = {tt(pk21.t)}) does not survive the adjustment (adjusted p = {pk21.p_holm:.3f})" in body
    assert "and significantly higher loss in none of the twelve panel-horizons" in body
    h3 = claims[claims.hypothesis == "H3"]
    assert set(h3[(h3.window == 5) & (h3.verdict == "better")].market) == set(PANELS) - {"NEPSE"}
    n21 = int(((h3.window == 21) & (h3.verdict == "better")).sum())
    assert f"and at 21 sessions in {WORDS[n21]}." in body


def test_the_mechanism_is_stated_with_the_claim(body, claims):
    h2 = claims[claims.hypothesis == "H2"]
    better = set(zip(h2[h2.verdict == "better"].market, h2[h2.verdict == "better"].window.astype(int)))
    assert better == {("DSE 2023-2026", 5), ("DSE 2023-2026", 21), ("DSE 2009-2021", 21)}
    assert "Most of the gain is the dynamics, not the market-implied open." in body
    p2 = claims.loc[claims.hypothesis == "P2", "verdict"].iloc[0]
    held, of = (int(x) for x in re.match(r"(\d+) of (\d+)", p2).groups())
    assert f"{WORDS[held].capitalize()} of the {WORDS[of]} predictions the plan made for H2 held" in body
    assert "One reading, which the plan did not test," in body
    findings = next(p for p in body.splitlines() if p.startswith("Findings:"))
    assert "Anam II" in findings and "unseen Pakistan" in findings and "never loses" in findings


def test_the_panels_quoted_are_table_141_and_144(body):
    pan = pd.read_csv(TAB / "table141_m22_panels.csv").set_index("sample")
    pk = pan.loc[PK]
    assert f"{int(pk['securities'])} ordinary equities and {int(pk['rule: stock-days']):,} stock-days" in body
    assert f"holds {int(pk['rule: test stock-days']):,} stock-days" in body
    assert f"{100 * pan.loc['DSE 2023-2026', 'stale_open_share']:.0f}% of opens" in body
    th = pd.read_csv(TAB / "table144_theory_market_open_data.csv").set_index("sample")
    seen = th[th.seen]
    assert len(seen) == 5 and (seen.b_I < seen.b_M).all()
    assert f"between {seen.b_M.min():.2f} and {seen.b_M.max():.2f})" in body
    assert f"(between {seen.b_I.min():.2f} and {seen.b_I.max():.2f})" in body
    assert f"only {100 * seen.mu.min():.0f}-{100 * seen.mu.max():.0f}% of the overnight second moment" in body


def test_seen_and_unseen_are_labelled(body):
    assert "The test spans of Section 6.8 had nevertheless been seen" in body
    assert "a market used at no stage of the design, the Pakistan Stock Exchange" in body
    assert "Eighteenth, Anam II was designed when the corrected evaluation's results on its test spans were known" in body
    paras = [ln for ln in body.splitlines()]
    i = next(k for k, t in enumerate(paras) if t.startswith("Several limitations"))
    j = next(k for k, t in enumerate(paras) if t.startswith("11. Conclusion"))
    assert sum(t.startswith("Eighteenth,") for t in paras[i + 1:j]) == 1


def test_section_9_counts_are_current(body):
    steps = pd.read_csv(TAB / "table124_theory_proof_steps.csv")
    nsym = int(steps["method"].isin(["symbolic", "symbolic-50dp"]).sum())
    assert f"({len(steps)} steps, {nsym} of them symbolic, all passing)" in body
    checks = pd.read_csv(TAB / "table143_theory_market_open_checks.csv")
    assert bool(checks["pass"].all()) and f"script 54 the eighth" in body
    assert f"({len(checks)} checks, all passing)" in body
    assert "eight propositions with proofs" in body and "seven propositions with proofs" not in body
    led = pd.read_csv(ROOT / "output" / "dev_anam2" / "ledger.csv")
    assert f"({led.groupby(['round', 'model']).ngroups} in all, in the package's development record)" in body


def test_the_pakistan_file_is_in_the_data_statements(body):
    for needle in ("Bangladeshi, Vietnamese, Moroccan and Pakistani results of Sections 6.8 and 6.9",
                   "Dhaka, Vietnamese, Casablanca and Pakistan exchanges", "apply_round20_revisions.py",
                   "(plans M16-M18, the corrected plan M20 and plan M22)"):
        assert needle in body, needle


def test_the_new_reference_and_its_doi(doc):
    paras = [p.text for p in doc.paragraphs]
    i = paras.index("References")
    j = next(k for k, t in enumerate(paras) if t.startswith("Data and reproducibility note"))
    refs = [t for t in paras[i + 1:j] if t.strip()]
    r = next(x for x in refs if x.startswith("Bollerslev, T., Hood, B., Huss, J., & Pedersen, L. H. (2018)"))
    assert r.endswith("https://doi.org/10.1093/rfs/hhy041") and "31(7), 2729-2773" in r
    keys = [re.sub(r"^(The )", "", x).lower() for x in refs]
    assert keys == sorted(keys)
    for cited in ("Scholes, M., & Williams, J. (1977)", "Lo, A. W., & MacKinlay, A. C. (1990)"):
        assert any(x.startswith(cited) for x in refs), cited


def test_corrected_statements_survive_nowhere_unfrozen():
    """M-036: 'reverses most of the stock-specific part' is false in Vietnam and Morocco, and 0.64 and 21% were
    rounded twice. The frozen plan and module docstring keep their text; nothing else may repeat it."""
    files = [ROOT / "README.md", ROOT / "anam-estimator" / "README.md", ROOT / "M22_ANAM2_RESULTS.md",
             ROOT / "anam-estimator" / "src" / "anam_estimator" / "market.py", ROOT / "paper" / "theory" / "theory.tex",
             ROOT / "paper" / "theory" / "section_theory.tex"]
    for f in files:
        text = f.read_text()
        for gone in ("almost entirely", "reverses most of", "0.64 and 1.00", "6–21%", "6-21%"):
            assert gone not in text, (f.name, gone)
    body = "\n".join(p.text for p in docx.Document(DOCX).paragraphs)
    assert "almost entirely" not in body and "reverses most of" not in body
    dev = (ROOT / "ANAM2_DEVELOPMENT.md").read_text()
    assert "audit register `M-036`" in dev
    reg = (ROOT / "AUDIT-REGISTER.md").read_text()
    for k in (35, 36, 37):
        assert f"| `M-0{k}` |" in reg, k


def test_the_anonymous_copy_and_letters():
    with zipfile.ZipFile(SUB / "02_manuscript_anonymous.docx") as z:
        for name in z.namelist():
            if name.endswith(".xml"):
                text = z.read(name).decode("utf-8", "replace")
                assert "Anam" not in text and "ANAM" not in text and "Proposed II" not in text, name
    anon = "\n".join(p.text for p in docx.Document(SUB / "02_manuscript_anonymous.docx").paragraphs)
    assert "6.9 A second estimator: the market-implied open\n" in anon + "\n"
    assert "The second proposed estimator" in anon
    letter = "\n".join(p.text for p in docx.Document(SUB / "03_cover_letter_Journal_of_Empirical_Finance.docx").paragraphs)
    assert "including Pakistan's, a market that played no part in its design" in letter
    assert "Bangladeshi, Vietnamese, Moroccan and Pakistani results" in letter
    title = "\n".join(p.text for p in docx.Document(SUB / "01_title_page.docx").paragraphs)
    assert "Bangladeshi, Vietnamese, Moroccan and Pakistani results" in title
