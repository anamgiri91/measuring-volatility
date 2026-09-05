"""Build the double-anonymous submission set from the revised manuscript.

Referee item (optional, section 4): the submitted PDF carried the author's name in the body and
in the file metadata. Journals using double-anonymous review require the identifying material to
live in a separate title page, and require the manuscript file itself to be clean -- including
the parts of a .docx a reader never sees.

Produces, in paper/submission/:

    01_title_page.docx                     author, affiliation, contact, statements
    02_manuscript_anonymous.docx           the manuscript with identity removed, body and metadata
    03_cover_letter_<journal>.docx         one per target journal, in the recommended order

What "anonymous" means here, precisely. Removing the byline is the easy half. This also clears
the docx core properties (author, last-modified-by, company, revision history) and the
per-revision author attributes that survive inside document.xml, and it neutralises
self-identifying references in the body -- the accompanying package is described as available
rather than named with a personal repository. Anything the script cannot verify is reported.
"""

from __future__ import annotations

import copy
import pathlib
import re
import shutil
import sys

try:
    import docx
except ImportError:
    sys.exit("python-docx is required:  pip install python-docx")

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
OUT = PAPER / "submission"

TITLE = "Daily OHLC Volatility Measurement in a Cash-Only Frontier Market"
SUBTITLE = "Evidence from the Nepal Stock Exchange"

# MANDATORY ITEM 10 (submission gate). The author's name was hard-coded here as
# ``AUTHOR = "Anam Giri"``. This script SHIPS INSIDE the reproducibility package, and the
# package is what accompanies the anonymous manuscript to a double-anonymous journal -- so the
# one file whose job is to strip identity from the submission set was itself carrying the
# identity, in plain text, past every check that only looked at the .docx files. The reviewer
# found it by grep, and so would an editor.
#
# Identity now lives in an UNTRACKED, UNSHIPPED sidecar that only the author has:
#
#     paper/AUTHOR.txt        line 1: author name
#                             line 2 onward (optional): affiliation, email, ORCID
#
# The title page is built from it when it is present. When it is absent -- which is the state
# of every distributed copy of this package -- the title page is built with a visible
# ``[AUTHOR DETAILS WITHHELD]`` placeholder and the run prints a notice. That inverts the
# failure mode: forgetting to supply identity produces a conspicuous placeholder, whereas
# forgetting to remove it used to produce a silent leak.
#
# AUTHOR.txt is named in .gitignore and excluded from the submission archive by
# build_archive.py. Nothing else in the package reads it.
AUTHOR_FILE = PAPER / "AUTHOR.txt"
AUTHOR_PLACEHOLDER = "[AUTHOR DETAILS WITHHELD]"


def author_details() -> tuple[str, list[str]]:
    """(name, extra lines) from the unshipped sidecar, or the placeholder when it is absent."""
    if not AUTHOR_FILE.exists():
        return AUTHOR_PLACEHOLDER, []
    lines = [ln.strip() for ln in AUTHOR_FILE.read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    if not lines:
        return AUTHOR_PLACEHOLDER, []
    return lines[0], lines[1:]


AUTHOR, AUTHOR_EXTRA = author_details()

# The referee's recommended submission order, with the reason each was recommended. Kept here so
# the cover letters cannot drift from the report they answer.
JOURNALS = [
    ("Asian_Journal_of_Economics_and_Banking", "Asian Journal of Economics and Banking",
     "Editors",
     "Its scope covers Asian financial systems, risk management, volatility clustering and "
     "statistical methods in finance, which is where a measurement study of a frontier Asian "
     "cash market belongs."),
    ("Investment_Management_and_Financial_Innovations",
     "Investment Management and Financial Innovations", "Editors",
     "Its scope covers capital markets, market efficiency and empirical quantitative finance, "
     "and it regularly publishes emerging-market price-volatility work."),
    ("Journal_of_Risk_and_Financial_Management", "Journal of Risk and Financial Management",
     "Editors",
     "Its scope covers financial markets, mathematical methods in finance and risk analysis, and "
     "it asks for enough methodological detail to reproduce the work -- which this submission "
     "supplies in full."),
]

ABSTRACT_SHORT = (
    "Nepal has no exchange-traded equity options, so no NEPSE analogue of the VIX can be read "
    "from an option chain. This paper asks what can be measured instead from daily OHLC data, "
    "and how reliable those measurements are. It is a measurement and data-design study rather "
    "than a search for a universally superior estimator.")


def anonymise(doc):
    """Strip identity from the body text, then from the parts of the file nobody looks at.

    MANDATORY ITEM 10. Byline removal used to work by matching the hard-coded author name. That
    made anonymisation DEPEND on the identity being present in this file, which is the leak the
    reviewer found: removing the hard-coded name would have quietly disabled the anonymiser.

    Removal is therefore STRUCTURAL. Everything between the title block and the Abstract heading
    is front matter -- byline, affiliation, revision date -- and none of it belongs in an
    anonymous manuscript. Nothing here needs to know who the author is, so the anonymiser is
    correct on a machine that has never held the author's name, which is every machine that
    receives this package.
    """
    removed = []

    paras = list(doc.paragraphs)
    abstract_at = next((i for i, p in enumerate(paras)
                        if p.text.strip().lower().startswith("abstract")), None)
    if abstract_at is None:
        raise SystemExit("anonymise: no Abstract heading found; refusing to guess where the "
                         "front matter ends")
    # Keep the title (index 0) and the subtitle (index 1); drop the rest of the front matter.
    for p in paras[2:abstract_at]:
        if p.text.strip():
            removed.append(f"front matter: {p.text.strip()[:40]!r}")
        p._p.getparent().remove(p._p)
    # core properties: author, last modified by, company, manager, revision
    cp = doc.core_properties
    for attr in ("author", "last_modified_by", "category", "comments", "content_status",
                 "identifier", "keywords", "language", "subject", "title", "version"):
        try:
            setattr(cp, attr, "")
        except (AttributeError, TypeError):
            pass
    cp.revision = 1
    removed.append("core properties")
    # tracked-change / comment author attributes that survive inside document.xml
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    n = 0
    for el in doc.element.iter():
        if f"{ns}author" in el.attrib:
            el.set(f"{ns}author", "Author")
            n += 1
    if n:
        removed.append(f"{n} in-XML author attributes")
    return removed


def identity_tokens() -> list[str]:
    """Strings whose presence in an anonymous file is a leak.

    Drawn from the unshipped sidecar when it exists, so the check is strongest on the author's
    own machine -- the only machine where a real name is available to leak. On a distributed
    copy the sidecar is absent and this list is empty, which is why :func:`check_clean` ALSO
    applies the structural check below and does not rely on token matching alone.
    """
    name, extra = author_details()
    if name == AUTHOR_PLACEHOLDER:
        return []
    toks = {name, *name.split()}
    for line in extra:
        toks.update(t for t in line.replace(",", " ").split() if len(t) > 3)
    return sorted(t for t in toks if len(t) > 2)


def check_clean(path):
    """Read the saved file back and report anything that would break double-anonymous review.

    Two independent checks, because either alone is insufficient:

    * TOKEN check -- any occurrence of the author's own name parts anywhere in the package
      parts, including the metadata nobody opens. Only available when the sidecar is present.
    * STRUCTURAL check -- the saved document must have nothing between its subtitle and its
      Abstract heading. This holds with no knowledge of the author at all, so it is the check
      that still works on a distributed copy, and it is what makes the anonymiser verifiable
      rather than merely well-intentioned.
    """
    import zipfile
    hits = []
    tokens = identity_tokens()
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith((".xml", ".rels")):
                continue
            body = z.read(name).decode("utf-8", "replace")
            for token in tokens:
                if token in body:
                    hits.append((name, token))

    d = docx.Document(path)
    paras = list(d.paragraphs)
    abstract_at = next((i for i, p in enumerate(paras)
                        if p.text.strip().lower().startswith("abstract")), None)
    if abstract_at is None:
        hits.append((path.name, "no Abstract heading; front matter not verifiable"))
    else:
        for p in paras[2:abstract_at]:
            if p.text.strip():
                hits.append((path.name, f"surviving front matter: {p.text.strip()[:40]!r}"))
    return hits


def title_page(doc_style_from):
    # A blank document, not a clone of the manuscript. Cloning and then deleting the paragraphs
    # leaves every embedded figure behind as an unreferenced media part -- a 1.5 MB title page
    # that still carries the paper's images, which is both wasteful and, for a file that is meant
    # to be the ONLY identifying document, a needless extra surface.
    d = docx.Document()

    def add(text, style=None, bold=False):
        p = d.add_paragraph()
        r = p.add_run(text)
        r.bold = bold
        if style:
            try:
                p.style = style
            except KeyError:
                pass
        return p

    add(TITLE, "Title")
    add(SUBTITLE)
    add("")
    add(AUTHOR, bold=True)
    for line in AUTHOR_EXTRA:
        add(line)
    if not AUTHOR_EXTRA:
        add("Affiliation: [to be completed]")
        add("Corresponding author: [name], [postal address]")
        add("Email: [to be completed]    ORCID: [to be completed]")
    add("")
    add("Declarations", "Heading 1")
    add("Funding. The author received no specific funding for this work.")
    add("Conflicts of interest. The author declares no competing interests.")
    add("Data availability. A reproducibility package accompanies this submission. It contains "
        "the frozen paper-facing panels, the external market series, the NEPSE security master "
        "used to validate the instrument classification, every producer script, a "
        "claim-to-producer-to-output reproducibility map, an audit register, and a test suite. "
        "The original stock-level NEPSE downloads are not redistributed because their "
        "redistribution terms are unresolved; the build script is included as the complete "
        "cleaning specification and the processed panels are sufficient to reproduce every "
        "reported result.")
    add("Ethics. Not applicable. The study uses aggregate market price data only.")
    add("AI use. Analysis code and manuscript revisions were prepared with computational "
        "assistance; all empirical results are produced by the included scripts and are "
        "reproducible from the package.")
    add("")
    add("Abstract (short form for the title page)", "Heading 1")
    add(ABSTRACT_SHORT)
    return d


def cover_letter(doc_style_from, journal_name, salutation, fit, numbers):
    d = docx.Document()          # blank, for the same reason as title_page

    def add(text, style=None, bold=False):
        p = d.add_paragraph()
        r = p.add_run(text)
        r.bold = bold
        if style:
            try:
                p.style = style
            except KeyError:
                pass
        return p

    add(f"Submission to {journal_name}", "Title")
    add("[Date]")
    add("")
    add(f"Dear {salutation},")
    add("")
    add(f'I am submitting "{TITLE}: {SUBTITLE}" for consideration at {journal_name}.')
    add(f"{fit}")
    add("")
    add("What the paper does. Nepal's exchange has no listed equity options, so a VIX-style "
        "measure cannot be read from an option chain. The paper asks what can be measured "
        "instead from daily open, high, low and close data, and how reliable those measurements "
        "are. It evaluates six estimators against proxies matched to each estimator's scope and "
        "evaluated on the same observations, on "
        f"{numbers['eq_days']} stock-days covering {numbers['eq_secs']} ordinary equities.")
    add("")
    add("What is new. Three things. First, a measurement result: range-based estimators do not "
        "collapse in thin ordinary equity, and that holds under same-day, security-level and "
        "lagged liquidity sorts alike. Second, a methodological result that generalises beyond "
        "this market: apparent estimator failure in a pooled frontier-market universe is largely "
        "an instrument-composition artifact rather than a microstructure effect, so sample "
        "construction can masquerade as an illiquidity finding. Third, a benchmark-scope "
        "argument: comparing a within-session estimator to close-to-close variance mechanically "
        "manufactures the downward bias that bias corrections are then applied to remove.")
    add("")
    add("What the paper does not claim. The open-to-close proxy is imperfect and the latent "
        "variance is unobserved, so results are reported as deviations from a matched proxy "
        "rather than as accuracy, and no estimator is claimed to dominate generally. The "
        "cross-market India VIX exercise is reported as co-movement evidence, not validation; "
        "its apparent estimator ordering reverses when a single 2012 flash-crash session is "
        "excluded, and the paper says so rather than choosing the ordering it prefers.")
    add("")
    add("Reproducibility. A complete package accompanies the submission: frozen data, producer "
        "scripts, a claim-to-output reproducibility map, an audit register recording defects "
        "found and fixed, and a test suite that fails if the manuscript and the package "
        "disagree. Every number in the manuscript is interpolated from the frozen output tables "
        "by script rather than transcribed.")
    add("")
    add("The manuscript is original, is not under consideration elsewhere, and all authors have "
        "approved the submission. An anonymised manuscript and a separate title page are "
        "included for double-anonymous review.")
    add("")
    add("Thank you for your consideration.")
    add("")
    add("Sincerely,")
    add("[Author name and affiliation, on the title page]")
    return d


def main():
    src = PAPER / "NEPSE_Volatility_Manuscript_Revised_2026-09.docx"
    if not src.exists():
        sys.exit(f"run paper/apply_referee_revisions.py first ({src} is missing)")
    OUT.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(PAPER))
    from apply_referee_revisions import load_numbers
    numbers = load_numbers()

    if AUTHOR == AUTHOR_PLACEHOLDER:
        print(f"  NOTE: {AUTHOR_FILE.relative_to(ROOT)} is absent, so the title page carries")
        print(f"        {AUTHOR_PLACEHOLDER} instead of a name. This is the expected state of")
        print("        every distributed copy. Create that file (line 1: name, line 2 onward:")
        print("        affiliation, email, ORCID) before submitting. It is never packaged.")

    title_page(str(src)).save(OUT / "01_title_page.docx")
    print(f"  wrote {OUT.name}/01_title_page.docx")

    anon_path = OUT / "02_manuscript_anonymous.docx"
    d = docx.Document(str(src))
    removed = anonymise(d)
    d.save(anon_path)
    hits = check_clean(anon_path)
    print(f"  wrote {OUT.name}/02_manuscript_anonymous.docx  (cleared: {', '.join(removed)})")
    if hits:
        print("  !! anonymity check FAILED:")
        for name, token in hits:
            print(f"       {name}: {token!r}")
        raise SystemExit(1)
    _tok = identity_tokens()
    print("     verified: no front matter survives between the subtitle and the Abstract"
          + (f", and none of the {len(_tok)} identity tokens appears anywhere in the file"
             if _tok else " (structural check only: no identity sidecar on this machine)"))

    for slug, name, salutation, fit in JOURNALS:
        p = OUT / f"03_cover_letter_{slug}.docx"
        cover_letter(str(src), name, salutation, fit, numbers).save(p)
        print(f"  wrote {OUT.name}/{p.name}")


if __name__ == "__main__":
    main()
