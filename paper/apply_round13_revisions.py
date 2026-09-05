"""M13: position the contribution against the located Nepal literature.

    python paper/apply_round13_revisions.py [--base BASE.docx] [--out OUT.docx]

The three literature tables were frozen and reconciled BEFORE this script ran, and the
contribution claim was then narrowed to fit them rather than the reverse. What the search found
retired the original index-versus-security framing: it located Neupane, Neupane and Baral (2022),
a security-level NEPSE volatility study. So this paper does not claim to bring security-level
volatility analysis to Nepal. What survives is the MEASUREMENT question -- that study uses
closing prices only and asks an association question about volume and frequency, not how to
measure volatility from a daily OHLC bar.

RULES ENFORCED HERE
  * The verified security-level study is cited explicitly.
  * The two abstract-only studies are described ONLY to the extent their abstracts support, and
    are never used to establish absence, novelty, methods or detailed findings.
  * "primarily index-level" is not used anywhere.
  * No "fills a gap": the permitted form is "addresses a measurement question not identified in
    the targeted search".
  * The snippet-conflation discovery is a search-quality control and belongs in the audit
    response, NOT in the manuscript body.
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
from apply_referee_revisions import find, para_after, set_text  # noqa: E402

REFS = [
    "Dangal, D. N., & Gajurel, R. P. (2021). Volatility of daily Nepal Stock Exchange (NEPSE) "
    "index return: A GARCH family models. Tribhuvan University Journal, 36(1), 31-44. "
    "https://doi.org/10.3126/tuj.v36i01.43514",
    "Karki, S. (2026). Time-varying efficiency and volatility regimes in Nepal Stock Exchange "
    "(NEPSE): Evidence from daily data under the adaptive market hypothesis. NRB Economic "
    "Review, 37(1), 28-58. https://doi.org/10.3126/nrber.v37i1.92673",
    "Neupane, B., Neupane, D., & Baral, P. (2022). Trading volume, trading price, trading "
    "frequency and stock return volatility of Everest Bank Limited. Pravaha, 28(1), 45-52.",
]

# The banned phrases, checked at the end against the whole body.
BANNED = {
    "primarily index-level": "retired: the search located a security-level study too",
    "fills a gap": "use 'addresses a measurement question not identified in the targeted search'",
    "no prior study": "the search cannot establish absence",
    "first study": "no first claims",
    "the first to": "no first claims",
    "systematic review": "this was a targeted search, not a systematic review",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    ap.add_argument("--out", default=str(ROOT / "paper" /
                    "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"))
    a = ap.parse_args()
    matrix = pd.read_csv(TAB / "table72_nepal_literature_matrix.csv")
    ledger = pd.read_csv(TAB / "table73_nepal_screening_ledger.csv")
    n_inc = len(matrix)
    n_full = int(matrix.full_text_verified.sum())
    n_ina = int((ledger.inclusion == "inaccessible").sum())
    doc = docx.Document(a.base)
    edits = 0

    # ── Abstract: rebuilt to the 250-word cap, with the narrowed contribution ───────────────
    #
    # The abstract had drifted to 340 words as successive rounds added the forward VIX test, the
    # thin-tail correction and the Yang-Zhang figure. The cap is a submission requirement, so it
    # is re-imposed here and asserted, not left to drift again.
    SECTIONS = {
        "Purpose": (
            "Nepal has no exchange-traded equity options, so no forward-looking, risk-neutral "
            "volatility measure exists for its market. This paper asks what daily "
            "open-high-low-close (OHLC) data can measure instead, and how reliable that "
            "measurement is under frontier-market constraints."),
        "Design/methodology/approach": (
            "Close-to-close, Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang and additive "
            "Rogers-Satchell estimators are evaluated on 143,718 ordinary-equity stock-days "
            "(292 securities, March 2024-August 2026), each against a proxy matched to its own "
            "scope, sample and horizon and classified against a stated +/-5% margin. Instrument "
            "classification is validated against an external security master; thinness is "
            "screened on lagged trading activity only; uncertainty comes from multiway and "
            "stationary block bootstraps; and India VIX is tested as a 30-day-ahead forecast "
            "rather than against a trailing window."),
        "Findings": (
            "Range estimators stay close to the matched proxy across the liquidity range "
            "(Parkinson 0.93-1.06), including the thinnest stock-days under an "
            "outcome-independent screen; an earlier grouping that selected partly on zero-range "
            "share had suggested otherwise. Apparent estimator failure in the pooled exchange "
            "file is largely instrument composition, not illiquidity. Yang-Zhang, matched on "
            "rows, horizon and a corporate-action-adjusted previous close, sits at 1.280. India "
            "VIX correlates 0.695 with subsequent close-to-close and 0.630 with subsequent "
            "Parkinson volatility, below its correlation with the preceding 30 days; the "
            "estimator comparison is inconclusive."),
        "Originality/value": (
            "A targeted search located both index-level and security-level NEPSE research, so "
            "no claim is made to introduce security-level volatility analysis to Nepal. The "
            "contribution is a reproducible comparison of daily OHLC estimators under NEPSE's "
            "own calendar, staleness, thin-trading and closing-rule constraints."),
    }
    total_words = sum(len(t.split()) for t in SECTIONS.values())
    assert total_words <= 250, f"abstract is {total_words} words, over the 250 cap"
    for p in list(doc.paragraphs):
        for label, text in SECTIONS.items():
            if p.text.startswith(label + ":"):
                # Rebuild the paragraph from empty. Earlier rounds collapsed some of these to a
                # SINGLE run via set_text, so assuming a [bold label][body] pair and writing to
                # run 1 appends instead of replacing -- which is how the abstract reached 408
                # words on the first attempt.
                for r in list(p.runs):
                    r._r.getparent().remove(r._r)
                lab = p.add_run(f"{label}: ")
                lab.bold = True
                p.add_run(text)
                edits += 1
                break
    print(f"  rebuilt the abstract at {total_words} words (cap 250)")

    # ── Introduction: position against what the search actually found ───────────────────────
    for p in list(doc.paragraphs):
        if "Answering them yields two contributions." in p.text:
            old = p.text
            i = old.index("Answering them yields two contributions.")
            j = old.index("The correct question is not simply")
            new = (
                "Answering them yields a contribution that should be stated narrowly, because a "
                "targeted search of the Nepali literature — logged, screened and reconciled in "
                "the accompanying package — shows what is and is not new here. That search "
                f"located {n_inc} usable studies and could not retrieve {n_ina} further records, "
                "so it supports statements about what it found and not about the literature as a "
                "whole. Among what it found, NEPSE volatility has been studied at the index "
                "level with GARCH-family and regime-switching models (Dangal & Gajurel, 2021; "
                "Karki, 2026), and at the security level: Neupane, Neupane and Baral (2022) "
                "examine daily stock return volatility for a single listed bank over 2010-2021, "
                "relating it to trading volume, price and frequency. This paper therefore makes "
                "no claim to introduce security-level volatility analysis to Nepal. What it "
                "contributes instead is a measurement contribution: a reproducible comparison of "
                "daily OHLC volatility estimators — close-to-close, Parkinson, Garman-Klass, "
                "Rogers-Satchell, Yang-Zhang and an additive correction — each against a proxy "
                "matched to its own scope, sample and horizon, under NEPSE's own calendar, "
                "staleness, thin-trading and closing-rule constraints. The security-level work "
                "the search located uses closing prices alone and asks an association question "
                "about volume and volatility; the question here is how to measure volatility "
                "from the daily high, low and open as well as the close, and which of those "
                "estimators survives contact with a frontier market's data. That addresses a "
                "measurement question not identified in the targeted search, which is a weaker "
                "and more honest statement than a claim of novelty. ")
            set_text(p, old[:i] + new + old[j:])
            edits += 1
            print("  rewrote the Introduction's contribution paragraph")
            break

    # ── Discussion: one sentence placing the result against the located literature ──────────
    for p in list(doc.paragraphs):
        if p.text.startswith("At the same time, the study shows that frontier-market volatility"):
            para_after(p,
                "It is worth being precise about what is added relative to existing Nepali work. "
                "The targeted search located index-level volatility modelling (Dangal & Gajurel, "
                "2021; Karki, 2026) and a security-level study of return volatility built from "
                "closing prices (Neupane, Neupane, & Baral, 2022). None of that work is "
                "superseded here, and the abstract-only records among it are not used to "
                "characterise methods or absence. The difference is one of object: those studies "
                "model or relate volatility once it has been measured, whereas the question here "
                "is how the measurement itself should be done when the inputs are a daily OHLC "
                "bar produced by a market with stale prices, price limits, an opening auction "
                "and corporate-action reference prices. Work on adjusting Nepali return series "
                "for thin trading is adjacent to that question rather than equivalent to it.",
                "Normal")
            edits += 1
            print("  added the Discussion positioning paragraph")
            break

    # ── Conclusion: keep the claim inside the evidence ─────────────────────────────────────
    for p in list(doc.paragraphs):
        if p.text.startswith("The claims should stop there."):
            set_text(p, p.text.replace(
                "The claims should stop there.",
                "The claims should stop there, including the claim to novelty. A targeted search "
                "of the Nepali literature located both index-level volatility modelling and a "
                "security-level study built from closing prices, so nothing here introduces "
                "security-level volatility analysis to Nepal; what it contributes is a "
                "reproducible comparison of daily OHLC estimators under this market's own "
                "calendar, staleness, thin-trading and closing-rule constraints."))
            edits += 1
            print("  narrowed the Conclusion's claim")
            break

    # ── references, kept alphabetical ───────────────────────────────────────────────────────
    paras = list(doc.paragraphs)
    first = find(paras, "Alizadeh, S., Brandt, M. W.")
    last = find(paras, "Zhang, L., Mykland, P. A.")
    existing = [paras[i].text.strip() for i in range(first, last + 1) if paras[i].text.strip()]
    merged = sorted(set(existing) | set(REFS),
                    key=lambda r: re.sub(r"^(The )", "", r).lower())
    slots = list(range(first, last + 1))
    for k, ref in enumerate(merged[:len(slots)]):
        set_text(paras[slots[k]], ref)
    p_last = paras[slots[-1]]
    for ref in merged[len(slots):]:
        p_last = para_after(p_last, ref, "Normal")
    edits += 1
    print(f"  reference list now {len(merged)} entries, alphabetical")

    doc.save(a.out)
    print(f"\n  {edits} edits; wrote {a.out}")

    # ── phrase audit ────────────────────────────────────────────────────────────────────────
    body = "\n".join(p.text for p in docx.Document(a.out).paragraphs)
    bad = {k: v for k, v in BANNED.items() if k in body.lower()}
    if bad:
        print("\nBANNED PHRASES PRESENT:")
        for k, v in bad.items():
            print(f"  {k!r}: {v}")
        raise SystemExit(1)
    for needed in ("Neupane", "Dangal", "Karki",
                   "addresses a measurement question not identified in the targeted search",
                   "no claim is made to introduce security-level",
                   "makes no claim to introduce security-level"):
        assert needed in body, f"missing after M13: {needed!r}"
    # The snippet-conflation control must NOT be in the manuscript body. Checked on terms
    # specific to that control -- "conflated" alone is a false positive, since the manuscript
    # legitimately says the measurement and forecasting layers "should not be conflated" and
    # that the two VIX horizons "must not be conflated".
    for control_term in ("snippet", "search summary", "26 securities", "search-engine",
                         "misattribut"):
        assert control_term not in body.lower(), (
            f"the search-quality control ({control_term!r}) belongs in the audit response, "
            "not the manuscript body")
    print("phrase audit: no banned phrase; all three located studies cited; "
          "search-quality control kept out of the body")


if __name__ == "__main__":
    main()
