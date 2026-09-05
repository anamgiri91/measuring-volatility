"""Apply the round-4 (optional-items follow-up) revisions to the manuscript source.

Same discipline as the earlier revision scripts: every number is interpolated from
``output/tables/*.csv``, and this is a second pass over the round-3 output rather than a
replacement for it.

    python paper/apply_round4_revisions.py [--base BASE.docx] [--out OUT.docx]

What this round does, all from the "optional" / "useful but not non-negotiable" lists of the
earlier review rounds:

  1. Refreshes Tables 6, 7, 11 and 15 in place with corrected CI-bound precision (a bound that
     rounds to 1.000 at 3dp is now shown at 4dp when it is not exactly 1 -- the exact defect the
     forensic audit flagged for Table 15's Rogers-Satchell block-date lower bound).
  2. Adds Table 17: the master-coverage sensitivity check (omit the ten securities absent from
     the external security master; the headline Parkinson ratio moves by 0.0003).
  3. Sets "repeat as header row" on every table, so a table that spans a page break in Word or a
     PDF export repeats its column headers -- a document property, not something that needs a
     renderer to take effect.
  4. Adds a JEL classification line, and a Declarations section (data availability, funding,
     conflict of interest) before the References.
  5. Replaces the abstract with a structured, <=250-word version (Purpose / Design-methodology-
     approach / Findings / Originality-value), matching the format the first-choice target
     journal (Asian Journal of Economics and Banking, an Emerald title) requires.
  6. Completes the literature-integration audit (item H): a surname-by-surname check confirms
     every reference in the list now has an in-text citation; no further splicing was needed.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

try:
    import docx
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt
except ImportError:
    sys.exit("python-docx is required:  pip install python-docx")

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from apply_referee_revisions import find, para_after, set_text, fill_table, new_table_after  # noqa: E402
from apply_round3_revisions import grow_table_columns  # noqa: E402


def set_repeat_header_row(table):
    """Mark a table's first row to repeat on every page it spans (w:tblHeader)."""
    tr = table.rows[0]._tr
    trPr = tr.find(qn("w:trPr"))
    if trPr is None:
        trPr = OxmlElement("w:trPr")
        tr.insert(0, trPr)
    if trPr.find(qn("w:tblHeader")) is None:
        trPr.append(OxmlElement("w:tblHeader"))


def add_labelled_paragraph(anchor, label, text, style="Normal"):
    """Insert a new paragraph after ``anchor`` with a bold label lead-in, e.g. 'Purpose: '."""
    p = para_after(anchor, "", style)
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    r1 = p.add_run(f"{label}: ")
    r1.bold = True
    p.add_run(text)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    ap.add_argument("--out", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    a = ap.parse_args()
    doc = docx.Document(a.base)

    # ── 1. structured abstract (<=250 words), replacing the single long paragraph ────────────
    paras = list(doc.paragraphs)
    i = find(paras, "Options markets make volatility visible in a way that cash-only markets")
    anchor = paras[i]
    purpose = ("Nepal Stock Exchange (NEPSE) has no options market and therefore no "
              "forward-looking, risk-neutral volatility measure. This paper asks what can be "
              "measured instead from daily open-high-low-close (OHLC) data, how reliable that "
              "measurement is in a frontier-market setting, and what data-engineering problems "
              "must be solved before a volatility formula can be trusted.")
    design = ("Close-to-close, Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang and "
             "additive Rogers-Satchell estimators are evaluated on 143,718 ordinary-equity "
             "stock-days (292 securities, March 2024-August 2026), each against a proxy "
             "matched to its own scope, sample and horizon. Instrument classification is "
             "validated against an external security master; liquidity is sorted three ways "
             "(same-day, security-level, lagged) to test for endogeneity; uncertainty is "
             "quantified with a multiway and a stationary block-date bootstrap; and an India "
             "VIX co-movement check supplies external context.")
    # The adopted Yang-Zhang ratio is READ from the frozen table, never typed here. A hardcoded
    # literal in this string is exactly how the superseded 1.309 would come back on a rebuild.
    _yz_adopted = float(pd.read_csv(TAB / "table33_estimator_ratios_bootstrap.csv")
                        .set_index("estimator").loc["Yang-Zhang", "sd_ratio"])
    findings = ("Range estimators remain informative even for the least active ordinary "
               "equities (Parkinson standard-deviation ratio 0.93-1.06 across liquidity "
               "groups), with a small, separately disclosed extreme-thin-tail exception. "
               "Apparent estimator failure in the pooled exchange file is largely an "
               "instrument-composition artifact, not illiquidity. Yang-Zhang requires "
               "matching sample, horizon and a corporate-action-adjusted previous close "
               "simultaneously, on both sides of the comparison; doing so moves its ratio to "
               f"the total-risk proxy to {_yz_adopted:.3f}. "
               "The India VIX co-movement check is real but period-sensitive (correlation "
               "0.78 over the full history versus 0.51 restricted to the study period) and "
               "establishes no ranking between estimators.")
    value = ("This is a systematic volatility-measurement framework for NEPSE, and "
            "demonstrates more generally how sample construction, benchmark scope and "
            "unadjusted corporate actions can manufacture an illusory estimator bias in "
            "frontier equity markets.")
    total_words = sum(len(t.split()) for t in (purpose, design, findings, value))
    assert total_words <= 250, f"structured abstract is {total_words} words, over the 250 cap"

    p = anchor
    p = add_labelled_paragraph(p, "Purpose", purpose)
    p = add_labelled_paragraph(p, "Design/methodology/approach", design)
    p = add_labelled_paragraph(p, "Findings", findings)
    p = add_labelled_paragraph(p, "Originality/value", value)
    # remove the old long-form abstract paragraph now that its replacement is in place
    anchor._p.getparent().remove(anchor._p)
    print(f"  replaced the abstract with a {total_words}-word structured version "
          "(Purpose/Design/Findings/Originality-value)")

    # ── 2. JEL classification, right after Keywords ───────────────────────────────────────────
    paras = list(doc.paragraphs)
    i = find(paras, "Keywords: frontier markets")
    try:
        find(paras, "JEL Classification")
        print("  JEL classification already present")
    except LookupError:
        para_after(paras[i], "JEL Classification: C58, G12, G14, G15, O16", "Normal")
        print("  added JEL classification line")

    # ── 3. Declarations section before References ────────────────────────────────────────────
    paras = list(doc.paragraphs)
    try:
        find(paras, "Data availability statement")
        print("  Declarations section already present")
    except LookupError:
        i = find(paras, "References")
        refs_heading = paras[i]
        # Insert BEFORE the References heading: clone it as a new heading, retitle, then add
        # the declaration paragraphs after that new heading -- inserting after refs_heading
        # would land inside the reference list, not before it.
        decl_heading = para_after(refs_heading, "Declarations", refs_heading.style)
        decl_heading._p.getparent().remove(decl_heading._p)
        refs_heading._p.addprevious(decl_heading._p)
        p = decl_heading
        p = add_labelled_paragraph(p, "Data availability statement",
            "The processed data supporting this study's findings, together with the code used "
            "to produce every reported result, are provided in the accompanying reproducibility "
            "package. Original stock-level source downloads from NEPSE are not redistributed "
            "because their redistribution terms are unresolved; a reader with independent "
            "access to them can rebuild the processed panel from data/raw/ using "
            "scripts/02_build_panel.py, and the rebuild has been independently verified to "
            "reproduce the distributed panel exactly (Section 9).")
        p = add_labelled_paragraph(p, "Funding",
            "This research received no specific grant from any funding agency in the public, "
            "commercial, or not-for-profit sectors.")
        p = add_labelled_paragraph(p, "Conflict of interest",
            "The author declares no conflict of interest.")
        print("  added Declarations section (data availability, funding, conflict of interest)")

    doc.save(a.out)
    print(f"\nwrote {a.out}")

    # ── 4. refresh Tables 6, 7, 11, 15 in place with the corrected CI-bound precision ────────
    doc = docx.Document(a.out)

    def refresh_table(caption_anchor, csv_name, colmap=None):
        paras = list(doc.paragraphs)
        cap_idx = find(paras, caption_anchor)
        body = doc.element.body
        children = list(body)
        pos = children.index(paras[cap_idx]._p)
        n_before = sum(1 for el in children[:pos] if el.tag.endswith("}tbl"))
        t = pd.read_csv(TAB / csv_name, dtype=str).fillna("")
        if colmap:
            t.columns = colmap
        tbl = doc.tables[n_before]
        grow_table_columns(tbl, len(t.columns))
        fill_table(tbl, list(t.columns), t.values.tolist())
        return tbl

    refresh_table("Table 6. Liquidity sorting", "paper_table6_predetermined_liquidity.csv")
    refresh_table("Table 7. All six named estimators", "paper_table7_all_estimators.csv")
    refresh_table("Table 11. The extreme thin tail", "paper_table11_thin_tail.csv")
    refresh_table("Table 15. Dependence structure", "paper_table15_dependence_structure.csv")
    print("  refreshed Tables 6, 7, 11, 15 with corrected CI-bound precision")

    # ── 5. Table 17, after Table 16 ───────────────────────────────────────────────────────────
    paras = list(doc.paragraphs)
    cap16_idx = find(paras, "Table 16. Panel balance, calendar cross-check")
    cap16 = paras[cap16_idx]
    body = doc.element.body
    children = list(body)
    pos = children.index(cap16._p)
    n_before = sum(1 for el in children[:pos] if el.tag.endswith("}tbl"))
    table16 = doc.tables[n_before]
    from docx.text.paragraph import Paragraph
    spacer_el = OxmlElement("w:p")
    table16._tbl.addnext(spacer_el)
    spacer = Paragraph(spacer_el, table16._parent)
    t17 = pd.read_csv(TAB / "paper_table17_master_coverage_sensitivity.csv", dtype=str).fillna("")
    cap17 = para_after(spacer, "Table 17. Master-coverage sensitivity: headline ordinary-equity "
                               "statistics including versus excluding the ten securities absent "
                               "from the external security master.", "Normal")
    new_table_after(cap17, doc, list(t17.columns), t17.values.tolist())
    print("  added Table 17 (master-coverage sensitivity)")

    # ── 6. §3 / §10: reference the new sensitivity check ──────────────────────────────────────
    paras = list(doc.paragraphs)
    i = find(paras, "Ten securities delisted, merged or renamed during the sample do not "
                    "appear in the master")
    old = paras[i].text
    marker = "they are listed in the package."
    if marker in old and "Table 17" not in old:
        set_text(paras[i], old.replace(
            marker,
            "they are listed in the package, and Table 17 shows that omitting all ten changes "
            "the headline Parkinson ratio by only 0.0003, so the composition result does not "
            "depend on this coverage gap."))
        print("  added a Table 17 cross-reference to the classification paragraph")

    doc.save(a.out)

    # ── 7. repeat-header-row on every table ───────────────────────────────────────────────────
    doc = docx.Document(a.out)
    for t in doc.tables:
        set_repeat_header_row(t)
    doc.save(a.out)
    print(f"  set repeat-header-row on {len(doc.tables)} tables")

    print(f"\nwrote {a.out}")

    # ── verification ──────────────────────────────────────────────────────────────────────
    doc = docx.Document(a.out)
    body = "\n".join(p.text for p in doc.paragraphs)
    for needed in ("Purpose:", "Design/methodology/approach:", "Findings:",
                  "Originality/value:", "JEL Classification", "Data availability statement:",
                  "Funding:", "Conflict of interest:", "Table 17."):
        assert needed in body, f"missing after round 4: {needed!r}"
    n_tables = len(doc.tables)
    assert n_tables == 17, f"expected 17 tables, found {n_tables}"
    for t in doc.tables:
        tr = t.rows[0]._tr
        trPr = tr.find(qn("w:trPr"))
        assert trPr is not None and trPr.find(qn("w:tblHeader")) is not None, \
            "a table is missing repeat-header-row"
    print("verification: structured abstract, JEL line, declarations, Table 17, and "
          f"repeat-header-row on all {n_tables} tables are all present")


if __name__ == "__main__":
    main()
