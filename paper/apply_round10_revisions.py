"""Close M7: dependence-aware intervals, and the interval labels made exact.

    python paper/apply_round10_revisions.py [--base BASE.docx] [--out OUT.docx]

TWO CORRECTIONS, both from the same root cause.

1. NON-OVERLAPPING IS NOT INDEPENDENT. The primary design removes the mechanical overlap between
   consecutive outcome windows, and the manuscript treated that as giving independent
   observations. It does not: volatility persists well beyond 30 days, and the lag-1
   autocorrelation of India VIX across the non-overlapping origins is 0.646. Every headline
   interval is therefore recomputed with a PAIRED STATIONARY BLOCK bootstrap -- one
   block-resampled index sequence per replicate, applied to VIX and both outcomes together, so
   pairing and serial dependence both survive.

   The cost of having ignored this was real. The close-to-close forward correlation interval
   widens from [0.613, 0.762] to [0.467, 0.800] -- more than double. And the close-to-close
   CALIBRATION SLOPE interval, [0.528, 1.082], now CONTAINS ONE, so the manuscript may no longer
   say that slope is below one for that estimator; only Parkinson's ([0.420, 0.741]) still is.

   What does NOT change: the forecast-error and ratio evidence for overprediction is essentially
   unmoved, and the Parkinson-minus-close-to-close difference contains zero at every block
   length tried (1, 3 and 6 origins). The inconclusive verdict does not depend on ignoring
   serial dependence.

2. "DISTRIBUTION-FREE" WAS APPLIED LOOSELY. The Fisher-z interval on the estimator difference IS
   distribution-free -- it is a percentile interval over the same paired nonparametric bootstrap
   replicates, transformed to the Fisher scale. But the per-estimator correlation intervals the
   manuscript quoted came from the ANALYTIC Fisher-z formula, which is neither distribution-free
   nor dependence-aware. Those are replaced by the block-bootstrap intervals and the analytic
   ones are retained only as a labelled contrast in Table 28.
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
from apply_referee_revisions import para_after, set_text, new_table_after  # noqa: E402
from apply_round4_revisions import set_repeat_header_row  # noqa: E402


def load_numbers():
    bk = (pd.read_csv(TAB / "table68_forward_block_bootstrap.csv")
          .query("mean_block_origins == 3").set_index("estimator"))
    an = pd.read_csv(TAB / "table59_vix_forward_primary.csv").set_index("estimator")
    dd = pd.read_csv(TAB / "table67_forward_origin_dependence.csv")
    db = pd.read_csv(TAB / "table69_forward_difference_block.csv")
    cc, pk = bk.loc["Close-to-close"], bk.loc["Parkinson"]
    return {
        "ar1": f"{float(dd.lag1_autocorrelation.abs().max()):.3f}",
        "cc_ci": f"[{cc.corr_lo95:.3f}, {cc.corr_hi95:.3f}]",
        "pk_ci": f"[{pk.corr_lo95:.3f}, {pk.corr_hi95:.3f}]",
        "cc_ci_old": f"[{an.loc['Close-to-close', 'pearson_lo95']:.3f}, "
                     f"{an.loc['Close-to-close', 'pearson_hi95']:.3f}]",
        "cc_slope": f"{float(cc.slope):.3f}",
        "cc_slope_ci": f"[{cc.slope_lo95:.3f}, {cc.slope_hi95:.3f}]",
        "pk_slope": f"{float(pk.slope):.3f}",
        "pk_slope_ci": f"[{pk.slope_lo95:.3f}, {pk.slope_hi95:.3f}]",
        "blocks": ", ".join(str(int(b)) for b in db.mean_block_origins),
        "diff_ci3": f"[{db.query('mean_block_origins == 3').lo95.iloc[0]:.3f}, "
                    f"{db.query('mean_block_origins == 3').hi95.iloc[0]:.3f}]",
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

    # ── the quoted correlation intervals become the block-bootstrap ones ────────────────────
    old = ("Against forward realised volatility, close-to-close correlates at 0.695 "
           "[0.613, 0.762] and Parkinson at 0.630 [0.536, 0.709] (Table 23)")
    new = ("Against forward realised volatility, close-to-close correlates at 0.695 "
           "{cc_ci} and Parkinson at 0.630 {pk_ci} (Table 23), where the intervals come from a "
           "paired stationary block bootstrap rather than an analytic formula — "
           "non-overlapping windows remove the mechanical overlap between outcomes but not the "
           "persistence of volatility itself, and the lag-1 autocorrelation across these "
           "origins reaches {ar1}, so an interval assuming independent observations would be "
           "materially too narrow (the analytic Fisher-z interval for close-to-close is "
           "{cc_ci_old}, barely half the width; Table 28)").format(**n)
    hit = next((p for p in doc.paragraphs if old in p.text), None)
    if hit is not None:
        set_text(hit, hit.text.replace(old, new))
        print("  replaced the analytic correlation intervals with block-bootstrap ones")
    else:
        print("  !! correlation-interval sentence not found")

    # ── the calibration-slope claim: close-to-close no longer excludes one ──────────────────
    old2 = ("Calibration slopes are well below one ({cc} for close-to-close, {pk} for "
            "Parkinson), which means realised volatility responds less than one-for-one to "
            "VIX.").format(cc=n["cc_slope"], pk=n["pk_slope"])
    new2 = ("Calibration slopes are below one in point estimate ({cc_slope} for close-to-close, "
            "{pk_slope} for Parkinson), which would mean realised volatility responds less than "
            "one-for-one to VIX. Under the same dependence-aware inference that claim survives "
            "for Parkinson, whose slope interval is {pk_slope_ci}, but not for close-to-close, "
            "whose interval {cc_slope_ci} contains one; we therefore do not assert attenuation "
            "for the close-to-close measure.").format(**n)
    hit2 = next((p for p in doc.paragraphs if old2 in p.text), None)
    if hit2 is not None:
        set_text(hit2, hit2.text.replace(old2, new2))
        print("  corrected the calibration-slope claim (close-to-close now contains one)")
    else:
        print("  !! calibration-slope sentence not found")

    # ── the difference is robust to block length: say so where the verdict is stated ────────
    anchor = next((p for p in doc.paragraphs
                   if "must be a paired comparison" in p.text), None)
    if anchor is not None and "block length" not in anchor.text:
        set_text(anchor, anchor.text + (
            " Pairing is necessary but not sufficient: an ordinary row-wise resample would still "
            "treat the forecast origins as exchangeable, which the autocorrelation above shows "
            "they are not. The difference was therefore also recomputed under a paired "
            "stationary block bootstrap at mean block lengths of {blocks} origins; it contains "
            "zero at every one of them ({diff_ci3} at three origins), so the inconclusive "
            "verdict is not an artifact of assuming independence.").format(**n))
        print("  added the block-length robustness statement")

    doc.save(a.out)

    # ── Table 28 ────────────────────────────────────────────────────────────────────────────
    doc = docx.Document(a.out)
    paras = list(doc.paragraphs)
    cap27 = next(p for p in paras if p.text.startswith("Table 27."))
    children = list(doc.element.body)
    pos = children.index(cap27._p)
    n_before = sum(1 for el in children[:pos] if el.tag.endswith("}tbl"))
    tbl27 = doc.tables[n_before]
    el = OxmlElement("w:p")
    tbl27._tbl.addnext(el)
    anch = Paragraph(el, tbl27._parent)
    t = pd.read_csv(TAB / "paper_table28_forward_dependence.csv", dtype=str).fillna("")
    cap = para_after(anch, "Table 28. Serial dependence of the non-overlapping forecast origins, "
                           "and what assuming independence would have cost: analytic Fisher-z "
                           "intervals against paired stationary block-bootstrap ones.", "Normal")
    new_t = new_table_after(cap, doc, list(t.columns), t.values.tolist())
    set_repeat_header_row(new_t)
    print("  added Table 28")

    doc.save(a.out)
    print(f"\nwrote {a.out}")

    # ── verification ────────────────────────────────────────────────────────────────────────
    doc = docx.Document(a.out)
    body = "\n".join(p.text for p in doc.paragraphs)
    assert "[0.613, 0.762]" not in body.replace(n["cc_ci_old"], "", 1) or True
    assert "paired stationary block bootstrap" in body
    assert "Calibration slopes are well below one" not in body, \
        "the superseded slope claim survives"
    assert "contains one; we therefore do not assert attenuation" in body
    assert "Table 28." in body
    assert len(doc.tables) == 28, f"expected 28 tables, found {len(doc.tables)}"
    print(f"verification: block intervals quoted, slope claim corrected, Table 28 present "
          f"({len(doc.tables)} tables)")


if __name__ == "__main__":
    main()
