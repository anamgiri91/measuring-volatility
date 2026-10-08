"""Daily equity panels for two more frontier markets: the Dhaka Stock Exchange and Vietnam (M17).

M17 scores Anam's estimator, frozen in M16 (``nepsevol.estimators.anam``), on markets it was never
designed on. This module turns three third-party files into panels with the NEPSE panel's coordinates
and conventions, so that the M16 tests apply unchanged. None of the files is stored in this package
(``data/external/README.md`` says where each comes from); each is pinned by its SHA-256 below and
checked before use.

SOURCES
-------
``DSE_UPLOAD``  ``DSE_Data.csv`` as supplied by the author: Dhaka Stock Exchange daily OHLC and
                volume, 534 trading codes, stamped 1999-01-02 to 2025-04-08. Its name, span and
                columns match the "Dhaka Stock Exchange Historical Data (1999-2025)" release
                (Sunny, Nafis and Khan, Mendeley Data, 2025); its row count does not match that
                listing's, so it is identified by checksum rather than by DOI.
``DSE_MIRROR``  ``data/prices.csv`` of github.com/nifty1303/dse-data at commit 9f11a76, scraped from
                the exchange's own day-end archive: 2024-09-30 to 2026-10-08, with the exchange's
                previous close and trade count. On the 52,920 stock-days the two DSE files share it
                agrees with the upload exactly, so it continues the upload after 2025-04-08.
``VN_TICKERS``  ``tickers/*.csv`` of github.com/88d52bdba0366127fffca9dfa93895/vnstock-data at commit
                b52e2fe: one file per Vietnamese security (HOSE, HNX and UPCoM, not labelled),
                2000-07-28 to 2020-03-18, prices adjusted for corporate actions and rounded to 0.01
                (thousand dong). The three-character codes are ordinary shares; the six longer codes
                are exchange-traded and real-estate funds.

THE UPLOAD'S DATES
------------------
Before 2023 the upload's dates have day and month exchanged whenever the day is 12 or less: 2020-04-02
holds 4 February 2020, and the stamps from 2 April to 11 May 2020 fall inside the exchange's
COVID-19 closure (26 March to 30 May 2020). The evidence, all from the calendar and none from prices:
every one of the 189 Friday stamps from 2009 to 2022 has a day of 12 or less (before 2009, 13 of 153
do not, M-016); reversing day and month for every such stamp from 2009 to 2021 leaves no Friday
session and no collision with an existing date; in 2022 the file
holds two copies of the same months, one exchanged and one not (all 9,650 conflicting records are
2022 stamps with a day of 12 or less); from 2023 on there is no Friday or Saturday stamp and the file
agrees exactly with the mirror. The panels therefore use 2009-2021 with the dates repaired
(``unswap_day_month``) and 2023 onward as stamped; 2022 is dropped. Before 2009 the exchange's
trading week changed and the weekday evidence cannot separate a repair from a genuine session, so
those years are not used.

RULES (frozen in ``M17_ANAM_FRONTIER_PLAN.md``)
-----------------------------------------------
1. Ordinary equity only (``DSE_NON_EQUITY``; Vietnam's three-character codes).
2. A record repeated exactly is kept once; a (security, date) key carrying two different records is
   dropped.
3. No-trade records (a non-positive price, or zero volume) are dropped.
4. OHLC envelope: a high below max(open, close) or a low above min(open, close) by at most one price
   unit (``unit``: rounding) is repaired as in the NEPSE panel (``nepsevol.clean.ohlc``); a larger
   violation drops the record.
5. Sessions: a date on which at least ``CARRY_FORWARD_SHARE`` of the records repeat the security's
   previous record is a carried-forward file, not a session; dates with fewer than
   ``MIN_SECURITIES`` securities, and dates inside a regulatory closure, are dropped.
6. Previous close: the security's close in the immediately preceding session, provided that session
   is at most ``MAX_GAP_DAYS`` calendar days earlier; otherwise NaN and the bar is dropped (a halt, a
   listing gap, the record-date suspension that precedes a Dhaka corporate action, a long closure).
7. Band screen: a bar whose high or low lies further from the previous close than the market's widest
   regular daily limit plus ``BAND_MARGIN`` is dropped (an unadjusted corporate action or a data
   error; Dhaka 10%, Vietnam 15%, the UPCoM limit).
8. Train/test: sessions before the panel's median session train the forecast shrinkage; the median
   session and later are the test span.
"""
from __future__ import annotations

import hashlib
import pathlib
import re

import numpy as np
import pandas as pd

from nepsevol.estimators import anam as AN

__all__ = ["DSE_NON_EQUITY", "SPANS", "unswap_day_month", "read_dse_upload", "read_dse_mirror", "read_vietnam",
           "build_panel", "market_panel", "sha256_file", "sha256_manifest"]

LN2 = float(np.log(2.0))
PRICES = ["open", "high", "low", "close"]

#: SHA-256 of the inputs the frozen plan was written against
DSE_UPLOAD_SHA256 = "a619a0ff80ce944414f94f6b1cd88e8ee186e83241a0934c2330036c190c6763"
DSE_MIRROR_SHA256 = "552e1a4515e36348a35069fca13067149988e9242e03b0bcac5b1a289b1b9633"
DSE_MIRROR_COMMIT = "9f11a766ae8690bdb798f68b077a1ce5449807e0"
VN_MANIFEST_SHA256 = "69caa964702c5152574eba580dc7e406213fbdf41b6824e53584d50c9c7e2691"
VN_COMMIT = "b52e2fe0905417e0d1c7215fbda1d352dde47492"

CARRY_FORWARD_SHARE = 0.90
MIN_SECURITIES = 10
MAX_GAP_DAYS = 14
BAND_MARGIN = 0.01
#: the upload's stamps before this date carry exchanged day and month (day <= 12); 2022 is mixed
DSE_SWAP_BEFORE = pd.Timestamp("2022-01-01")
DSE_MIXED_YEAR = 2022
#: the mirror continues the upload after its last stamp
DSE_UPLOAD_LAST = pd.Timestamp("2025-04-08")

#: market -> widest regular daily limit, price unit for the envelope repair, regulatory closures
MARKETS = {
    "DSE": dict(band=0.10, unit=0.1, closures=(("2020-03-26", "2020-05-30"),)),
    "VN": dict(band=0.15, unit=0.01, closures=()),
}
#: panel -> (market, first date, last date)
SPANS = {
    "DSE 2023-2026": ("DSE", "2023-01-01", "2026-10-08"),
    "DSE 2009-2021": ("DSE", "2009-01-01", "2021-12-31"),
    "Vietnam 2007-2020": ("VN", "2007-01-01", "2020-03-18"),
}

#: Dhaka codes that are not ordinary equity: mutual funds, corporate bonds, debentures and Sukuk by the
#: exchange's sector field (``fundamentals.csv`` of the mirror, snapshots 2026-09-30/10-03), the three
#: DSE indices, and the funds and bonds that had left the list before the snapshot, identified by name.
DSE_NON_EQUITY = frozenset("""
1JANATAMF 1STPRIMFMF ABB1STMF ABBLPBOND AIBL1STIMF AIBLPBOND APSCLBOND BANKASI1PB BEXGSUKUK CAPITECGBF
CAPMBDBLMF CAPMIBBLMF CBLPBOND DBH1STMF DBLPBOND DEBARACEM DEBBDLUGG DEBBDWELD DEBBDZIPP DEBBXDENIM
DEBBXFISH DEBBXKNI DEBBXTEX EBL1STMF EBLNRBMF EXIM1STMF FBFIF GLDNJMF GRAMEENS2 GREENDELMF IBBL2PBOND
IBBLPBOND ICB3RDNRB ICBAGRANI1 ICBAMCL2ND ICBEPMF1S1 ICBSONALI1 IFIC1STMF IFILISLMF1 LRGLOBMF1 MBL1STMF
MBPLCPBOND MTBPBOND NCCBLMF1 PBLPBOND PF1STMF PHPMF1 POPULAR1MF PREBPBOND PRIME1ICBA RELIANCE1 SEB1PBOND
SEMLFBSLGF SEMLIBBLSF SJIBLPBOND TRUSTB1MF UCB2PBOND VAMLBDMF1 VAMLRBBF
ACIZCBOND AIMS1STMF ATCSLGF BRACSCBOND DS30 DSES DSEX GRAMEEN1 ICB1STNRB ICB2NDNRB ICBAMCL1ST ICBISLAMIC
NLI1STMF SEBL1STMF SEMLLECMF
""".split())


# --------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------

def sha256_file(path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def sha256_manifest(paths) -> str:
    """Digest of the sorted ``"<file name> <sha256>"`` lines of a set of files."""
    lines = [f"{p.name} {sha256_file(p)}" for p in sorted(pathlib.Path(p) for p in paths)]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _check(actual: str, expected: str, what: str) -> None:
    if actual != expected:
        raise ValueError(f"{what}: SHA-256 {actual} differs from the frozen {expected}")


def unswap_day_month(stamp: pd.Series) -> pd.Series:
    """Exchange day and month wherever the day is 12 or less and differs from the month."""
    s = pd.to_datetime(stamp)
    amb = (s.dt.day <= 12) & (s.dt.day != s.dt.month)
    out = s.copy()
    if amb.any():
        out[amb] = pd.to_datetime(pd.DataFrame({"year": s[amb].dt.year, "month": s[amb].dt.day,
                                                "day": s[amb].dt.month}))
    return out


def _dedupe(x: pd.DataFrame) -> pd.DataFrame:
    """Rule 2: exact repeats kept once; keys with two different records dropped."""
    x = x.drop_duplicates()
    return x[~x.duplicated(["symbol", "date"], keep=False)]


def read_dse_upload(path, check: bool = True) -> pd.DataFrame:
    """The upload, with its dates repaired (stamps before 2022), 2022 dropped and rule 2 applied."""
    if check:
        _check(sha256_file(path), DSE_UPLOAD_SHA256, "DSE upload")
    raw = pd.read_csv(path, dtype={"Trading_Code": str})
    stamp = pd.to_datetime(raw["Date"])
    x = pd.DataFrame({"symbol": raw["Trading_Code"].str.strip(), "stamp": stamp,
                      "open": raw["Open"], "high": raw["High"], "low": raw["Low"], "close": raw["Close"],
                      "volume": raw["Volume"]})
    x = x[x["stamp"].dt.year != DSE_MIXED_YEAR]
    x = x.drop_duplicates()
    x = x[~x.duplicated(["symbol", "stamp"], keep=False)]
    early = x["stamp"] < DSE_SWAP_BEFORE
    x["date"] = x["stamp"]
    x.loc[early, "date"] = unswap_day_month(x.loc[early, "stamp"])
    x = x.drop(columns="stamp")
    return _dedupe(x).reset_index(drop=True)


def read_dse_mirror(path, check: bool = True) -> pd.DataFrame:
    if check:
        _check(sha256_file(path), DSE_MIRROR_SHA256, "DSE mirror")
    m = pd.read_csv(path, dtype={"symbol": str})
    x = pd.DataFrame({"symbol": m["symbol"].str.strip(), "date": pd.to_datetime(m["date"]),
                      "open": m["open"], "high": m["high"], "low": m["low"], "close": m["close"],
                      "volume": m["volume"]})
    return _dedupe(x).reset_index(drop=True)


def read_vietnam(ticker_dir, check: bool = True) -> pd.DataFrame:
    files = sorted(f for f in pathlib.Path(ticker_dir).glob("*.csv") if re.fullmatch(r"[a-z0-9]{3}", f.stem))
    if check:
        _check(sha256_manifest(files), VN_MANIFEST_SHA256, "Vietnam ticker files")
    parts = []
    for f in files:
        t = pd.read_csv(f)
        parts.append(pd.DataFrame({"symbol": f.stem.upper(), "date": pd.to_datetime(t["date"]),
                                   "open": t["open"], "high": t["high"], "low": t["low"], "close": t["close"],
                                   "volume": t["volume"]}))
    return _dedupe(pd.concat(parts, ignore_index=True)).reset_index(drop=True)


# --------------------------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------------------------

def build_panel(x: pd.DataFrame, *, band: float, unit: float, closures=(), start=None, end=None,
                min_securities: int = MIN_SECURITIES):
    """Rules 3-8 on records ``[symbol, date, open, high, low, close, volume]`` of one market.

    Returns ``(panel, log)``: the panel carries the bar, ``pc`` (previous close), the coordinates
    o, c, u, d, r, h, l, the daily estimators CC, P, GK, RS and ``span`` ("train"/"test"); ``log``
    counts what each rule removed.
    """
    x = x.copy()
    if start is not None:
        x = x[x["date"] >= pd.Timestamp(start)]
    if end is not None:
        x = x[x["date"] <= pd.Timestamp(end)]
    log = {"records": len(x)}
    live = (x[PRICES] > 0).all(axis=1) & (x["volume"] > 0)
    log["no-trade records"] = int((~live).sum())
    x = x[live]
    gap = np.maximum(x[["open", "close"]].max(axis=1) - x["high"], x["low"] - x[["open", "close"]].min(axis=1))
    big = gap > unit * (1 + 1e-6)
    log["envelope violations dropped"] = int(big.sum())
    log["envelope violations repaired"] = int(((gap > 0) & ~big).sum())
    x = x[~big].copy()
    x["high"] = x[["high", "open", "close"]].max(axis=1)
    x["low"] = x[["low", "open", "close"]].min(axis=1)

    x = x.sort_values(["symbol", "date"]).reset_index(drop=True)
    cols = PRICES + ["volume"]
    same = (x[cols] == x.groupby("symbol", sort=False)[cols].shift(1)).all(axis=1)
    share = same.groupby(x["date"]).mean()
    count = x.groupby("date").size()
    drop = set(share.index[share >= CARRY_FORWARD_SHARE]) | set(count.index[count < min_securities])
    for a, b in closures:
        drop |= {t for t in count.index if pd.Timestamp(a) <= t <= pd.Timestamp(b)}
    log["dates dropped (carried forward, thin, closed)"] = len(drop)
    x = x[~x["date"].isin(drop)].reset_index(drop=True)

    sessions = np.sort(x["date"].unique())
    x["session"] = x["date"].map(pd.Series(np.arange(len(sessions)), index=sessions))
    g = x.groupby("symbol", sort=False)
    step = x["session"] - g["session"].shift(1)
    days = (x["date"] - g["date"].shift(1)).dt.days
    x["pc"] = g["close"].shift(1).where((step == 1) & (days <= MAX_GAP_DAYS))
    log["bars without a previous close"] = int(x["pc"].isna().sum())
    x = x[x["pc"].notna()].reset_index(drop=True)

    co = AN.bar_coordinates(x["open"], x["high"], x["low"], x["close"], x["pc"])
    lim = band + BAND_MARGIN
    out = (co["h"] > np.log1p(lim)) | (co["l"] < np.log1p(-lim))
    log["bars outside the band"] = int(out.sum())
    x, co = x[~out].reset_index(drop=True), co[~out].reset_index(drop=True)
    for k in ("o", "c", "u", "d", "r", "h", "l"):
        x[k] = co[k]
    R = x["u"] - x["d"]
    x["P"] = R ** 2 / (4 * LN2)
    x["GK"] = 0.5 * R ** 2 - (2 * LN2 - 1) * x["c"] ** 2
    x["RS"] = x["u"] * (x["u"] - x["c"]) + x["d"] * (x["d"] - x["c"])
    x["CC"] = x["r"] ** 2
    used = np.sort(x["date"].unique())
    half = used[len(used) // 2]
    x["span"] = np.where(x["date"] < half, "train", "test")
    log.update({"stock-days": len(x), "securities": int(x["symbol"].nunique()), "sessions": len(used),
                "first session": str(pd.Timestamp(used[0]).date()), "last session": str(pd.Timestamp(used[-1]).date()),
                "first test session": str(pd.Timestamp(half).date()),
                "train stock-days": int((x["span"] == "train").sum()), "test stock-days": int((x["span"] == "test").sum())})
    return x.sort_values(["symbol", "date"]).reset_index(drop=True), log


def market_panel(name: str, root, check: bool = True):
    """The panel ``name`` of :data:`SPANS`, built from the inputs under ``root``
    (``data/external/frontier``)."""
    root = pathlib.Path(root)
    market, start, end = SPANS[name]
    if market == "DSE":
        up = read_dse_upload(root / "dse_upload" / "DSE_Data.csv", check=check)
        x = up
        if pd.Timestamp(end) > DSE_UPLOAD_LAST:
            mir = read_dse_mirror(root / "dse_mirror" / "prices.csv", check=check)
            x = pd.concat([up, mir[mir["date"] > DSE_UPLOAD_LAST]], ignore_index=True)
        x = x[~x["symbol"].isin(DSE_NON_EQUITY)]
    else:
        x = read_vietnam(root / "vietnam" / "tickers", check=check)
    return build_panel(x, start=start, end=end, **MARKETS[market])
