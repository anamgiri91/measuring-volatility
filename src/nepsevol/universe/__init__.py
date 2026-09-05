"""Security-type classification for the NEPSE universe.

NEPSE's daily files carry no instrument-type field, so type has to be supplied from outside
the price data. Two sources are used here, in a fixed order of authority:

    1. AN EXTERNAL SECURITY MASTER (authoritative). ``data/external/nepse_security_master.csv``
       carries an instrument category and par value for every currently listed NEPSE security,
       harvested from the exchange's listed-securities categories. Where a symbol appears in
       the master, the master decides.
    2. THE TICKER-CONVENTION RULE (fallback). Type is recovered from the ticker convention and
       validated against par value, which differs by instrument class:

           mutual fund   par     10      observed median close  8.56 - 10.78
           equity        par    100      observed median close   100 - 46,888
           promoter      par    100      observed median close   101 - 11,941
           debenture     par  1,000      observed median close   986 - 1,215

       The fund band is separated from everything else by an empty interval: the 51st-lowest
       median close is 10.78 and the 52nd is 100.00. Funds are therefore identified by price
       alone, with no judgement. Debentures are identified by ticker pattern and confirmed by
       the tight band around par -- 81 of 82 pattern matches lie in [986, 1215].

WHY THE MASTER WAS ADDED (referee item 2, critical). The rule alone carried the paper's
strongest substantive claim -- that apparent thin-market estimator collapse is an
instrument-composition artifact -- with no independent validation, which is an avoidable
evidentiary weakness. Reconciling the rule against the master (``scripts/27_classification_audit.py``)
agrees on 509 of 511 matched securities, 99.61%, and isolates exactly two rule failures, both
of which are now corrected because the master overrides:

    ADBLB   rule ``equity``    master ``debenture``   "4% Agricultural Bond", median close 1000.00
            The debenture ticker pattern does not match ``ADBLB``, so a bond sat inside the
            ordinary-equity universe that carries every headline result.

    NADEP   rule ``promoter``  master ``equity``      "NADEP Laghubitta Bittiya Sanstha Limited"
            The promoter pattern ``(?:PO|P)$`` fired on a trailing "P" that is part of the
            company name, so an ordinary equity was excluded from that universe.

Both are one-security errors in opposite directions. They are reported rather than quietly
fixed because the *rate* is the evidence: a 99.6% agreement rate is what makes the composition
result safe to lean on, and a reader cannot check that from a corrected classification alone.

Symbols absent from the master -- ten securities delisted, merged or renamed during the
sample -- fall back to the rule and are listed in the audit output. The master lists currently
listed securities, so a security that left the board during 2024-2026 cannot appear in it.

Why any of this matters: in the paper sample, the two thinnest security-level liquidity
quintiles contain only four ordinary equities among 209 securities, and the thinnest stock-day
decile is 94.3% non-equity. Any "illiquidity" contrast drawn across the full universe is
therefore partly an ASSET-CLASS contrast.
"""
import functools
import pathlib
import re

FUND_MAX_CLOSE = 40.0        # the gap runs 10.78 -> 100.00; any cut inside it gives the same set
_DEB = re.compile(r"(?:D|B|EB|UR)\s?\d{2}(?:\d{2})?(?:\s?/\s?\d{2}(?:\d{2})?)?(?:KA)?$")
_DEB_NO_YEAR = {"SCBD", "SHINED", "NIFRAGED"}   # debenture tickers carrying no BS year
_PROMOTER = re.compile(r"(?:PO|P)$")

#: Path of the shipped master, relative to the package root.
MASTER_REL = pathlib.Path("data") / "external" / "nepse_security_master.csv"

#: Classes the master can assign. ``preference`` is neither ordinary equity nor any of the three
#: excluded classes the rule knows about, so it is kept distinct rather than folded into one.
MASTER_CLASSES = ("equity", "debenture", "fund", "promoter", "preference")

__all__ = ["classify", "classify_panel", "equity_only", "load_master", "reconcile",
           "FUND_MAX_CLOSE", "MASTER_REL", "MASTER_CLASSES"]


def _root() -> pathlib.Path:
    """Package root, inferred from this file's location (src/nepsevol/universe/__init__.py)."""
    return pathlib.Path(__file__).resolve().parents[3]


@functools.lru_cache(maxsize=4)
def _master_map(path: str) -> dict:
    import pandas as pd
    m = pd.read_csv(path)
    return dict(zip(m["symbol"].astype(str).str.upper().str.replace(" ", "", regex=False),
                    m["sec_type_master"]))


def load_master(root=None):
    """Return ``{normalised symbol: sec_type}`` from the shipped master, or ``{}`` if absent.

    Absence is not an error: the rule is a complete classifier on its own and the package must
    stay runnable without the external file. It IS reported, because a silent fallback to an
    unvalidated classifier is exactly the failure mode referee item 2 identifies.
    """
    path = pathlib.Path(root or _root()) / MASTER_REL
    if not path.exists():
        return {}
    return dict(_master_map(str(path)))


def classify(symbol, median_close=None):
    """Return the RULE-BASED type: 'fund' | 'debenture' | 'promoter' | 'equity'.

    This is deliberately the unvalidated rule, unchanged, so that
    :func:`reconcile` compares two genuinely independent classifiers. Call
    :func:`classify_panel` for the authoritative assignment.

    `median_close` is optional but recommended: it is what separates funds from everything
    else and what stops a fund like NMB50 being read as a debenture by its trailing digits.
    """
    u = symbol.upper().replace(" ", "")
    if median_close is not None and median_close < FUND_MAX_CLOSE:
        return "fund"
    if u in _DEB_NO_YEAR or _DEB.search(u):
        return "debenture"
    if _PROMOTER.search(u) and not u[-1].isdigit():
        return "promoter"
    return "equity"


def classify_panel(df, symbol_col="symbol", close_col="close", root=None, use_master=True):
    """Add a `sec_type` column to a long panel: master where available, rule otherwise.

    Also adds `sec_type_source`, one of ``"master"`` or ``"rule"``, so every downstream table
    can state how each security was typed instead of asserting it.
    """
    med = df.groupby(symbol_col)[close_col].median()
    rule = {s: classify(s, med.get(s)) for s in med.index}
    master = load_master(root) if use_master else {}

    def _norm(s):
        return str(s).upper().replace(" ", "")

    final, source = {}, {}
    for s in med.index:
        hit = master.get(_norm(s))
        final[s] = hit if hit is not None else rule[s]
        source[s] = "master" if hit is not None else "rule"
    return df.assign(sec_type=df[symbol_col].map(final),
                     sec_type_source=df[symbol_col].map(source))


def equity_only(df, symbol_col="symbol", close_col="close", root=None):
    """Restrict a panel to ordinary common equity."""
    d = classify_panel(df, symbol_col, close_col, root=root)
    return d[d.sec_type == "equity"].drop(columns=["sec_type", "sec_type_source"])


def reconcile(df, symbol_col="symbol", close_col="close", root=None):
    """One row per security: rule-based type, master type, and whether they agree.

    This is the evidence for referee item 2 and is what
    ``scripts/27_classification_audit.py`` turns into a confusion table. It is kept here rather
    than in the script so the comparison is testable.
    """
    import pandas as pd
    med = df.groupby(symbol_col)[close_col].median()
    master = load_master(root)
    out = pd.DataFrame({
        "symbol": med.index,
        "median_close": med.values,
        "rule_based": [classify(s, med.get(s)) for s in med.index],
    })
    out["master"] = [master.get(str(s).upper().replace(" ", "")) for s in out.symbol]
    out["in_master"] = out.master.notna()
    out["agrees"] = out.in_master & (out.rule_based == out.master)
    out["final"] = out.master.where(out.in_master, out.rule_based)
    out["sec_type_source"] = out.in_master.map({True: "master", False: "rule"})
    return out.sort_values("symbol").reset_index(drop=True)
