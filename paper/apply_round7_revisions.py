"""Mandatory item 4: replace the outcome-selected thin tail with a lagged liquidity screen.

    python paper/apply_round7_revisions.py [--base BASE.docx] [--out OUT.docx]

WHAT CHANGED, AND WHY IT MATTERS. The thin tail reported in Section 6.1 and Table 11 is entered
when a security's participation falls below 90% OR its ZERO-RANGE SHARE reaches 5%. The second
test selects on the outcome: a zero range is the event that drives Parkinson to zero, so a low
Parkinson-to-proxy ratio inside that group is partly guaranteed by how the group was built.

Replacing it with a screen that reads only lagged trading activity -- participation and
conditional-median trade count over the previous 60 SCHEDULED sessions, through t-1, with a
60-scheduled-session history floor -- REVERSES the finding:

    zero-range-selected tail (Table 11)      Parkinson 0.814   "different"     -- collapsed
    lagged liquidity screen  (Table 21)      Parkinson 1.020   "inconclusive"  -- no collapse

and no cell of the 3x3 threshold grid, the history-floor sweep, or the composite-OR components
produces a collapse either. The apparent collapse was substantially an artifact of selection.

This STRENGTHENS the paper's central claim rather than weakening it, and the manuscript is
changed accordingly: the "extreme thin tail exception" is withdrawn from the abstract and the
conclusion, Table 11 is retained but demoted to a descriptive failure-case inventory, and the
lagged screen becomes the robustness evidence.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

try:
    import docx
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph
except ImportError:
    sys.exit("python-docx is required:  pip install python-docx")

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from apply_referee_revisions import find, para_after, set_text, new_table_after  # noqa: E402
from apply_round4_revisions import set_repeat_header_row  # noqa: E402


def load_numbers():
    lt = pd.read_csv(TAB / "table55_lagged_thinness_baseline.csv")
    thin, rest = lt.iloc[0], lt.iloc[1]
    grid = pd.read_csv(TAB / "table56_lagged_thinness_grid.csv")
    floors = pd.read_csv(TAB / "table57_lagged_thinness_history_floor.csv")
    comps = pd.read_csv(TAB / "table58_lagged_thinness_components.csv")
    part_only = comps[comps.component == "participation only"].iloc[0]
    allr = pd.concat([grid.Parkinson_thin, floors.Parkinson_thin, comps.Parkinson_thin])
    tail = pd.read_csv(TAB / "table42_thin_tail.csv")
    extreme = tail[tail.group == "extreme thin tail"].iloc[0]
    return {
        "thin_pct": f"{float(thin.share_of_eligible_pct):.1f}",
        "thin_secs": int(thin.n_securities),
        "thin_days": f"{int(thin.n_stock_days):,}",
        "thin_pk": f"{float(thin.Parkinson):.3f}",
        "thin_ci": f"[{thin.lo95:.3f}, {thin.hi95:.3f}]",
        "thin_verdict": thin.verdict_vs_margin,
        "rest_pk": f"{float(rest.Parkinson):.3f}",
        "rest_ci": f"[{rest.lo95:.3f}, {rest.hi95:.3f}]",
        "grid_lo": f"{float(allr.min()):.3f}",
        "grid_hi": f"{float(allr.max()):.3f}",
        "n_specs": int(len(allr)),
        "part_only_secs": int(part_only.n_securities_thin),
        "part_only_days": f"{int(part_only.n_stock_days_thin):,}",
        "part_only_pk": f"{float(part_only.Parkinson_thin):.3f}",
        "part_only_ci": f"[{part_only.lo95:.3f}, {part_only.hi95:.3f}]",
        "zr_pk": f"{float(extreme.Parkinson):.3f}",
        "zr_secs": int(extreme.n_securities),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    ap.add_argument("--out", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    a = ap.parse_args()
    n = load_numbers()
    doc = docx.Document(a.base)

    # ── §6.1: the thin-tail paragraph is rewritten around the lagged screen ──────────────────
    paras = list(doc.paragraphs)
    hit = next((p for p in paras if "A small number of securities with the fewest observed "
                                    "sessions are reported separately" in p.text), None)
    if hit is not None:
        old_start = hit.text.find("A small number of securities with the fewest observed")
        old_end = hit.text.find("Because this contrast is the paper's central empirical claim")
        if old_start >= 0 and old_end > old_start:
            replacement = (
                "How the thinnest stock-days are identified matters more than it appears. An "
                "earlier version of this analysis grouped securities by participation OR by "
                "their zero-range share, and reported that range estimators collapse in that "
                f"group (Parkinson {n['zr_pk']} across {n['zr_secs']} securities). That grouping "
                "selects on the outcome: a zero range is the event that drives Parkinson to "
                "zero, so a low ratio inside a group defined partly by zero ranges is in part an "
                "arithmetic consequence of the selection rather than a finding about liquidity. "
                "The robustness claim is therefore made instead with a lagged, "
                "outcome-independent liquidity screen, declared post hoc and applied "
                "consistently, which reads no price, range, return or estimator output. A "
                "stock-day is thin when, over the previous 60 scheduled sessions and using "
                "information through the prior session only, the security's participation fell "
                "below 90% or its median trade count conditional on trading fell at or below the "
                "cross-sectional tenth percentile, with ties at that cutoff treated as thin; "
                "securities are eligible only after 60 scheduled sessions of history, counted in "
                "scheduled rather than traded sessions so that eligibility does not itself "
                "depend on activity. Official listing dates are not available here, so the first "
                "observed trading date is used as a proxy for the start of eligibility. Under "
                f"that screen {n['thin_pct']}% of eligible stock-days are thin "
                f"({n['thin_secs']} securities, {n['thin_days']} stock-days) and the estimator "
                f"does not collapse in them: Parkinson stands at {n['thin_pk']} {n['thin_ci']} "
                f"against {n['rest_pk']} {n['rest_ci']} for the rest of the eligible sample "
                f"(Table 21). Across all {n['n_specs']} specifications of the sensitivity "
                f"analysis — a 3×3 grid over participation thresholds and trade-count tails, a "
                "history-floor sweep, and each leg of the rule on its own — the thin-group ratio "
                f"stays between {n['grid_lo']} and {n['grid_hi']} (Table 22). The one "
                "specification that does produce a materially lower ratio is the participation "
                f"leg alone, which isolates {n['part_only_secs']} securities and "
                f"{n['part_only_days']} stock-days at {n['part_only_pk']} {n['part_only_ci']}; "
                "that interval is wide and straddles the margin, so it identifies where any "
                "genuine difficulty lies rather than establishing one. "
            )
            set_text(hit, hit.text[:old_start] + replacement + hit.text[old_end:])
            print("  rewrote the §6.1 thin-tail passage around the lagged screen")

    # ── Abstract: withdraw the "extreme thin tail exception" ────────────────────────────────
    for p in list(doc.paragraphs):
        old = ("with a small, separately disclosed extreme-thin-tail exception. ")
        if old in p.text:
            set_text(p, p.text.replace(
                old,
                "including the thinnest stock-days under a lagged, outcome-independent liquidity "
                "screen; an earlier grouping that selected partly on zero-range share had "
                "suggested a collapse there, and that apparent collapse does not survive a "
                "screen which does not read the estimator's own failure mode. "))
            print("  abstract: withdrew the extreme-thin-tail exception")
            break

    # ── §11 Conclusion: same correction ─────────────────────────────────────────────────────
    for p in list(doc.paragraphs):
        marker = "— with the exception of a small extreme tail of "
        if marker in p.text:
            i = p.text.find(marker)
            j = p.text.find("rather than smoothed into that conclusion.")
            if i >= 0 and j > i:
                set_text(p, p.text[:i] + (
                    "— and this now holds under a thinness screen built only from lagged "
                    "trading activity, not from the estimator's own zero-range outcome, which an "
                    "earlier grouping had used and which had suggested a collapse that does not "
                    "survive. ") + p.text[j + len("rather than smoothed into that conclusion."):])
                print("  conclusion: withdrew the extreme-tail exception")
            break

    # ── §10: the limitation about the extreme tail is restated ──────────────────────────────
    for p in list(doc.paragraphs):
        if "the extreme thin tail reported in Section 6.1 and Table 11 comprises" in p.text:
            head = p.text.split(",", 1)[0]     # keep the "Eleventh" ordinal
            set_text(p, f"{head}, the thin-tail evidence rests on how thinness is defined. "
                        "Table 11 groups securities partly by their zero-range share, which is "
                        "the estimator's own failure mode, so it is reported here as a "
                        "descriptive failure-case inventory and not as robustness evidence; the "
                        "robustness claim uses the lagged, outcome-independent screen of Tables "
                        "21 and 22 instead. Both are shown because they disagree, and the "
                        "disagreement is itself the finding: an apparent collapse in the first "
                        "does not survive the second.")
            print("  §10: restated the thin-tail limitation")
            break

    # ── Table 11's caption is demoted to descriptive ────────────────────────────────────────
    for p in list(doc.paragraphs):
        if p.text.startswith("Table 11. The extreme thin tail"):
            set_text(p, "Table 11. Descriptive failure-case inventory: securities grouped partly "
                        "by zero-range share. Because that share is the estimator's own failure "
                        "mode, this grouping selects on the outcome and is NOT robustness "
                        "evidence; see Tables 21-22 for the lagged, outcome-independent screen.")
            print("  demoted the Table 11 caption to descriptive")
            break

    doc.save(a.out)

    # ── Tables 21 and 22 ────────────────────────────────────────────────────────────────────
    doc = docx.Document(a.out)
    paras = list(doc.paragraphs)
    cap20 = next(p for p in paras if p.text.startswith("Table 20."))
    children = list(doc.element.body)
    pos = children.index(cap20._p)
    n_before = sum(1 for el in children[:pos] if el.tag.endswith("}tbl"))
    anchor_tbl = doc.tables[n_before]

    def spacer_after(tbl):
        el = OxmlElement("w:p")
        tbl._tbl.addnext(el)
        return Paragraph(el, tbl._parent)

    anchor = spacer_after(anchor_tbl)
    for caption, csv_name in [
        ("Table 21. Thin stock-days under a lagged, outcome-independent liquidity screen "
         "(participation and conditional-median trade count over the previous 60 scheduled "
         "sessions, through t-1; 60-scheduled-session history floor).",
         "paper_table21_lagged_thinness_screen.csv"),
        ("Table 22. Sensitivity of the lagged thinness screen: threshold grid, history floor, "
         "and each leg of the composite rule on its own.",
         "paper_table22_lagged_thinness_sensitivity.csv"),
    ]:
        t = pd.read_csv(TAB / csv_name, dtype=str).fillna("")
        cap = para_after(anchor, caption, "Normal")
        new_t = new_table_after(cap, doc, list(t.columns), t.values.tolist())
        set_repeat_header_row(new_t)
        anchor = spacer_after(new_t)
    print("  added Tables 21 and 22")

    doc.save(a.out)
    print(f"\nwrote {a.out}")

    # ── verification ────────────────────────────────────────────────────────────────────────
    doc = docx.Document(a.out)
    body = "\n".join(p.text for p in doc.paragraphs)
    assert "lagged, outcome-independent liquidity screen" in body
    assert "declared post hoc and applied consistently" in body
    assert "ex ante" not in body.lower(), "'ex ante' could be misread as prespecification"
    assert "descriptive failure-case inventory" in body
    for t in ("Table 21.", "Table 22."):
        assert t in body, f"missing {t}"
    assert "with the exception of a small extreme tail of" not in body, \
        "the withdrawn extreme-tail exception survives in the conclusion"
    assert len(doc.tables) == 22, f"expected 22 tables, found {len(doc.tables)}"
    print(f"verification: lagged screen in text, Table 11 demoted, Tables 21-22 present "
          f"({len(doc.tables)} tables)")


if __name__ == "__main__":
    main()
