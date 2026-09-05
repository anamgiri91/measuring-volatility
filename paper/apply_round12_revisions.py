"""Two wording corrections closing M7 for good.

    python paper/apply_round12_revisions.py [--base BASE.docx] [--out OUT.docx]

1. "EFFECTIVELY INDEPENDENT BLOCKS" WAS THE WRONG NAME. n / b is approximately the expected
   number of blocks drawn per stationary-bootstrap replicate. It is NOT an effective-sample-size
   estimate -- that is a different quantity, computed differently, and not computed here.

2. THE MAXIMUM-ACROSS-SERIES RULE IS OURS, NOT POLITIS-WHITE'S. The procedure selects a block
   length for one univariate series. Combining three selections by taking the largest is our own
   conservative aggregation, adopted post hoc, and the manuscript must not imply the method
   prescribes it.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import pandas as pd

try:
    import docx
except ImportError:
    sys.exit("python-docx is required:  pip install python-docx")

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAB = ROOT / "output" / "tables"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from apply_referee_revisions import set_text  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    ap.add_argument("--out", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    a = ap.parse_args()
    bl = pd.read_csv(TAB / "table70_block_length_selection.csv")
    prim = bl[bl.series.str.startswith("PRIMARY")].iloc[0]
    b = float(prim.politis_white_block_length)
    n_org = int(prim.n_origins)
    per_series = bl[~bl.series.str.startswith("PRIMARY")]
    doc = docx.Document(a.base)
    edits = 0

    old = re.compile(
        r"at a mean block length of [\d.]+ origins selected automatically from the data by the "
        r"Politis-White procedure rather than chosen by hand \(blocks of [^)]*\)\. With \d+ "
        r"origins a block of that length leaves about \d+ effectively independent blocks, which "
        r"is not many, and is why the sensitivity grid is shown rather than a single interval")
    new = (
        f"at a mean block length of {b:.2f} origins. That length is selected from the data rather "
        "than chosen by hand: the Politis-White procedure is applied to each of the three series "
        "entering the comparison (India VIX and the two forward realised-volatility series, "
        f"giving {', '.join(f'{v:.2f}' for v in per_series.politis_white_block_length)} origins "
        "respectively) and we take the largest. That aggregation is our own conservative rule, "
        "adopted post hoc — the Politis-White procedure selects a length for a single series and "
        "prescribes nothing about combining several — so the per-series selections are reported "
        f"in Table 28 for a reader who would aggregate differently. With {n_org} forecast origins "
        f"and a selected mean block length of {b:.2f} origins, each bootstrap replicate contains "
        f"approximately {n_org / b:.0f} expected-length blocks. This limited amount of independent "
        "temporal information motivates reporting block-length sensitivities, which appear in "
        "Table 28 and leave the verdict unchanged")

    for p in list(doc.paragraphs):
        if old.search(p.text):
            set_text(p, old.sub(new, p.text))
            edits += 1
            print("  corrected the block-count wording and disclosed the aggregation rule")
            break
    else:
        print("  !! block-length sentence not found")

    doc.save(a.out)
    print(f"\n  {edits} edits; wrote {a.out}")

    body = "\n".join(p.text for p in docx.Document(a.out).paragraphs)
    assert "effectively independent blocks" not in body, "the wrong term survives"
    assert "expected-length blocks" in body
    assert "our own conservative rule, adopted post hoc" in body
    assert "prescribes nothing about combining several" in body
    print("verification: expected-blocks wording used; the max rule is disclosed as ours "
          "and post hoc")


if __name__ == "__main__":
    main()
