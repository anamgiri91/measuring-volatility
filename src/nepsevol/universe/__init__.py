"""Security-type classification for the NEPSE universe.

NEPSE's daily files carry no instrument-type field, so type is recovered from the ticker
convention and then VALIDATED against par value, which differs by instrument class:

    mutual fund   par     10      observed median close  8.56 - 10.78
    equity        par    100      observed median close   100 - 46,888
    promoter      par    100      observed median close   101 - 11,941
    debenture     par  1,000      observed median close   986 - 1,215

The fund band is separated from everything else by an empty interval: the 51st-lowest median
close is 10.78 and the 52nd is 100.00. Funds are therefore identified by price alone, with no
judgement. Debentures are identified by ticker pattern and confirmed by the tight band around
par -- 81 of 82 pattern matches lie in [986, 1215].

Why this matters: the thinnest liquidity quintile of the full universe is 79% non-equity
(debentures, closed-end funds, promoter shares). Any "illiquidity" contrast drawn across the
full universe is partly an ASSET-CLASS contrast. See DD-018.
"""
import re

FUND_MAX_CLOSE = 40.0        # the gap runs 10.78 -> 100.00; any cut inside it gives the same set
_DEB = re.compile(r"(?:D|B|EB|UR)\s?\d{2}(?:\d{2})?(?:\s?/\s?\d{2}(?:\d{2})?)?(?:KA)?$")
_DEB_NO_YEAR = {"SCBD", "SHINED", "NIFRAGED"}   # debenture tickers carrying no BS year
_PROMOTER = re.compile(r"(?:PO|P)$")


def classify(symbol, median_close=None):
    """Return 'fund' | 'debenture' | 'promoter' | 'equity'.

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


def classify_panel(df, symbol_col="symbol", close_col="close"):
    """Add a `sec_type` column to a long panel, using each security's median close."""
    med = df.groupby(symbol_col)[close_col].median()
    kind = {s: classify(s, med.get(s)) for s in med.index}
    return df.assign(sec_type=df[symbol_col].map(kind))


def equity_only(df, symbol_col="symbol", close_col="close"):
    """Restrict a panel to ordinary common equity."""
    d = classify_panel(df, symbol_col, close_col)
    return d[d.sec_type == "equity"].drop(columns="sec_type")
