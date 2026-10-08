"""M17: the frontier-market panel rules, checked on synthetic records (no market data is read here)."""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nepsevol import frontier as F  # noqa: E402


def _bars(symbol, dates, close, spread=0.01, volume=100.0):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"symbol": symbol, "date": pd.to_datetime(dates), "open": close,
                         "high": close * (1 + spread), "low": close * (1 - spread), "close": close,
                         "volume": volume})


def _weekdays(n, start="2024-01-01"):
    return pd.bdate_range(start, periods=n)


def test_unswap_exchanges_day_and_month_only_when_ambiguous():
    s = pd.Series(pd.to_datetime(["2020-04-02", "2020-05-31", "2020-03-03", "2019-12-01", "2021-01-13"]))
    out = F.unswap_day_month(s)
    assert list(out.dt.strftime("%Y-%m-%d")) == ["2020-02-04", "2020-05-31", "2020-03-03", "2019-01-12", "2021-01-13"]


def test_upload_reader_repairs_before_2022_drops_2022_and_conflicts(tmp_path):
    rows = [
        ("AAA ", "2020-04-02", 10, 11, 9, 10, 5),     # exchanged: 4 Feb 2020; trailing space stripped
        ("AAA", "2020-04-02", 10, 11, 9, 10, 5),      # same record once stripped: kept once
        ("BBB", "2020-05-31", 20, 21, 19, 20, 5),     # day > 12: as stamped
        ("CCC", "2022-08-02", 30, 31, 29, 30, 5),     # 2022: dropped
        ("DDD", "2023-04-02", 40, 41, 39, 40, 5),     # 2023: as stamped
        ("EEE", "2024-06-03", 50, 51, 49, 50, 5),     # conflicting pair: both dropped
        ("EEE", "2024-06-03", 50, 52, 49, 51, 6),
    ]
    p = tmp_path / "DSE_Data.csv"
    pd.DataFrame(rows, columns=["Trading_Code", "Date", "Open", "High", "Low", "Close", "Volume"]).to_csv(p, index=False)
    x = F.read_dse_upload(p, check=False).set_index("symbol")["date"].dt.strftime("%Y-%m-%d").to_dict()
    assert x == {"AAA": "2020-02-04", "BBB": "2020-05-31", "DDD": "2023-04-02"}


def test_non_equity_list_has_funds_bonds_and_indices_but_not_lookalike_equities():
    for code in ("1JANATAMF", "ABBLPBOND", "BEXGSUKUK", "DEBBXTEX", "GRAMEENS2", "DSEX", "ICB1STNRB"):
        assert code in F.DSE_NON_EQUITY
    for code in ("INDEXAGRO", "PAPERPROC", "GP", "SQURPHARMA", "ACI"):
        assert code not in F.DSE_NON_EQUITY


def test_previous_close_needs_the_immediately_preceding_session():
    d = _weekdays(6)
    a = _bars("A", d, [10, 10.1, 10.2, 10.3, 10.4, 10.5])
    b = _bars("B", d[[0, 1, 3, 4, 5]], [20, 20.2, 20.4, 20.6, 20.8])     # B misses session 2
    panel, log = F.build_panel(pd.concat([a, b]), band=0.10, unit=0.01, min_securities=1)
    pcb = panel[panel.symbol == "B"].set_index("date")["pc"]
    assert d[3] not in pcb.index                                           # first bar after the gap dropped
    assert pcb.loc[d[4]] == pytest.approx(20.4)
    assert log["bars without a previous close"] == 1 + 1 + 1               # A's first, B's first, B after gap


def test_previous_close_is_dropped_across_a_long_closure():
    d = list(_weekdays(3)) + [pd.Timestamp("2024-03-01"), pd.Timestamp("2024-03-04")]
    panel, _ = F.build_panel(_bars("A", d, [10, 10.1, 10.2, 10.3, 10.4]), band=0.10, unit=0.01, min_securities=1)
    assert pd.Timestamp("2024-03-01") not in set(panel["date"])
    assert pd.Timestamp("2024-03-04") in set(panel["date"])


def test_no_trade_records_and_large_envelope_violations_are_dropped_small_ones_repaired():
    d = _weekdays(5)
    a = _bars("A", d, [10, 10, 10, 10, 10])
    a.loc[1, "volume"] = 0                                                  # no trade
    a.loc[2, "high"] = a.loc[2, "close"] - 0.01                             # one unit below the close: repair
    a.loc[3, "low"] = a.loc[3, "close"] + 0.5                               # far above the close: drop
    panel, log = F.build_panel(a, band=0.10, unit=0.01, min_securities=1)
    assert log["no-trade records"] == 1
    assert log["envelope violations repaired"] == 1 and log["envelope violations dropped"] == 1
    assert (panel["high"] >= panel[["open", "close"]].max(axis=1)).all()


def test_carried_forward_and_closed_dates_are_not_sessions():
    d = _weekdays(6)
    frames = [_bars(s, d, [10 + i, 10.2 + i, 10.1 + i, 10.3 + i, 10.2 + i, 10.4 + i]) for i, s in enumerate("ABCDEFGHIJKL")]
    x = pd.concat(frames, ignore_index=True)
    rep = x["date"] == d[3]
    prev = x[x["date"] == d[2]].set_index("symbol")
    for col in ("open", "high", "low", "close", "volume"):
        x.loc[rep, col] = x.loc[rep, "symbol"].map(prev[col]).to_numpy()     # d[3] repeats d[2] for all
    panel, log = F.build_panel(x, band=0.10, unit=0.01, closures=(("2024-01-02", "2024-01-02"),))
    assert d[3] not in set(panel["date"]) and d[1] not in set(panel["date"])
    assert log["dates dropped (carried forward, thin, closed)"] == 2


def test_band_screen_uses_the_limit_plus_the_margin():
    d = _weekdays(4)
    a = _bars("A", d, [10, 10, 10, 10], spread=0.0)
    a.loc[1, ["high", "close"]] = 10 * 1.105                                # inside 10% + 1 point
    a.loc[2, ["open", "high", "low", "close"]] = 1.105 * 10 * 1.12          # 12% above the previous close
    panel, log = F.build_panel(a, band=0.10, unit=0.01, min_securities=1)
    assert d[1] in set(panel["date"]) and d[2] not in set(panel["date"])
    # the jump back is outside the band too: a bad close also poisons the next bar's previous close
    assert d[3] not in set(panel["date"]) and log["bars outside the band"] == 2


def test_split_is_at_the_median_session_and_estimators_are_consistent():
    rng = np.random.default_rng(0)
    d = _weekdays(41)
    frames = []
    for s in "ABCDEFGHIJK":
        c = 10 * np.exp(np.cumsum(rng.normal(0, 0.01, len(d))))
        b = _bars(s, d, c)
        b["open"] = c * np.exp(rng.normal(0, 0.002, len(d)))
        b["high"] = b[["open", "close"]].max(axis=1) * 1.004
        b["low"] = b[["open", "close"]].min(axis=1) * 0.996
        frames.append(b)
    panel, log = F.build_panel(pd.concat(frames, ignore_index=True), band=0.10, unit=0.01)
    used = np.sort(panel["date"].unique())
    assert log["first test session"] == str(pd.Timestamp(used[len(used) // 2]).date())
    assert (panel.loc[panel.span == "train", "date"] < pd.Timestamp(log["first test session"])).all()
    assert np.allclose(panel["CC"], (np.log(panel["close"] / panel["pc"])) ** 2)
    R = np.log(panel["high"] / panel["low"])
    assert np.allclose(panel["P"], R ** 2 / (4 * np.log(2)))
    assert set(F.SPANS) == {"DSE 2023-2026", "DSE 2009-2021", "Vietnam 2007-2020"}


# ── M18: Casablanca's dated band schedule and share files ─────────────────────────────────

def test_band_schedule_applies_the_limit_in_force_on_each_day():
    dates = pd.Series(pd.to_datetime(["2019-12-31", "2020-03-16", "2020-03-17", "2021-10-12", "2023-10-08", "2023-10-09"]))
    assert list(F.band_on(dates, F.MA_BANDS)) == [0.10, 0.10, 0.04, 0.06, 0.06, 0.10]
    assert list(F.band_on(dates, 0.15)) == [0.15] * 6


def test_band_screen_follows_the_schedule():
    d = pd.to_datetime(["2020-03-13", "2020-03-16", "2020-03-17", "2020-03-18"])
    a = _bars("A", d, [10, 10, 10, 10], spread=0.0)
    a.loc[1, ["high", "close"]] = 10 * 1.08     # +8% on 16 March: inside the 10% limit then in force
    a.loc[2, ["open", "high", "low", "close"]] = 10.8                    # 17 March: flat at the new level
    a.loc[3, ["open", "low"]] = 10.8
    a.loc[3, ["high", "close"]] = 10.8 * 1.07   # +7% on 18 March: outside the new 4% limit plus margin
    panel, log = F.build_panel(a, band=F.MA_BANDS, unit=0.01, min_securities=1)
    assert d[1] in set(panel["date"]) and d[3] not in set(panel["date"])
    assert log["bars outside the band"] == 1


def test_casablanca_reader_takes_one_file_per_share(tmp_path):
    for sym, rows in (("ATW", [("2024-01-02", 450, 455, 449, 452, 1000)]), ("IAM", [("2024-01-02", 99, 100, 98, 99.5, 500)])):
        pd.DataFrame(rows, columns=["Time", "Open", "High", "Low", "Close", "Volume"]).to_csv(tmp_path / f"{sym}.csv", index=False)
    x = F.read_casablanca(tmp_path, check=False)
    assert sorted(x["symbol"]) == ["ATW", "IAM"] and list(x.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]
    assert "Morocco 2012-2026" in F.SPANS_M18 and "Morocco 2012-2026" not in F.SPANS
