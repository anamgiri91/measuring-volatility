"""M22: Anam II (``nepsevol.estimators.anam2``) and the Pakistan panel rules, on synthetic data."""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nepsevol import frontier as F  # noqa: E402
from nepsevol.estimators import anam as AN  # noqa: E402
from nepsevol.estimators import anam2 as A2  # noqa: E402

LN2 = float(np.log(2.0))


def _coords(O, H, L, C, PC):
    return AN.bar_coordinates(np.asarray(O, float), np.asarray(H, float), np.asarray(L, float), np.asarray(C, float),
                              np.asarray(PC, float))


# ── the market's move and the effective open ──────────────────────────────────────────────

def test_market_move_is_the_mean_of_the_other_securities():
    o = pd.Series([0.01, 0.03, np.nan, -0.02, 0.05])
    date = pd.Series(["t1", "t1", "t1", "t1", "t2"])
    m = A2.market_move(o, date)
    assert m[0] == pytest.approx((0.03 - 0.02) / 2)
    assert m[1] == pytest.approx((0.01 - 0.02) / 2)
    assert m[2] == pytest.approx((0.01 + 0.03 - 0.02) / 3)   # a security without o sees all the others
    assert m[4] == 0.0                                        # alone on its date: no market move


def test_market_move_carries_none_of_the_own_open():
    rng = np.random.default_rng(1)
    o = pd.Series(rng.normal(0, 0.01, 40))
    date = pd.Series(np.repeat(["a", "b"], 20))
    m0 = A2.market_move(o, date)
    o2 = o.copy()
    o2[3] += 0.5                                              # a wild opening print for security 3
    m1 = A2.market_move(o2, date)
    assert m1[3] == pytest.approx(m0[3])                      # its own market move is unchanged
    assert (m1[20:] == m0[20:]).all()                         # the other date is untouched


def test_effective_open_reads_the_market_only_on_stale_opens():
    o = pd.Series([0.0, 0.02, -0.01, 0.0])
    date = pd.Series(["t", "t", "t", "t"])
    eo = A2.effective_open(o, date, "panel")
    assert eo[0] == pytest.approx((0.02 - 0.01 + 0.0) / 3) and eo[3] == pytest.approx((0.0 + 0.02 - 0.01) / 3)
    assert eo[1] == 0.0 and eo[2] == 0.0
    assert (A2.effective_open(o, date, "series") == 0.0).all()


# ── the kernel ────────────────────────────────────────────────────────────────────────────

def test_kernel_is_the_open_free_kernel_wherever_the_open_moved():
    rng = np.random.default_rng(2)
    n = 500
    PC = np.full(n, 100.0)
    O = PC * np.exp(rng.normal(0, 0.01, n))
    C = O * np.exp(rng.normal(0, 0.01, n))
    H = np.maximum(O, C) * np.exp(np.abs(rng.normal(0, 0.005, n)) + 1e-6)
    L = np.minimum(O, C) * np.exp(-np.abs(rng.normal(0, 0.005, n)) - 1e-6)
    x = _coords(O, H, L, C, PC)
    zero = pd.Series(0.0, index=x.index)
    a2 = A2.kernel(x["o"], x["c"], x["u"], x["d"], zero)
    of = AN.kernel(x["o"], x["c"], x["u"], x["d"], zero)
    assert np.allclose(a2, of, rtol=1e-12, atol=0)


def test_one_price_bar_uses_the_single_increment_not_parkinsons_constant():
    x = _coords([103.0], [103.0], [103.0], [103.0], [100.0])   # one price, 3% above the previous close
    zero = pd.Series(0.0, index=x.index)
    g = float(np.log(1.03))
    assert A2.kernel(x["o"], x["c"], x["u"], x["d"], zero)[0] == pytest.approx(0.8 * g * g + 0.2 * g * g)
    assert AN.kernel(x["o"], x["c"], x["u"], x["d"], zero)[0] == pytest.approx(0.8 * g * g / (4 * LN2) + 0.2 * g * g)


def test_a_stale_bar_is_credited_the_market_move():
    # security 0 prints only its previous close; three others open 2% up
    x = _coords([100, 102, 102, 102], [100, 103, 102.5, 104], [100, 101, 101.5, 101], [100, 102, 102, 103],
                [100, 100, 100, 100])
    date = pd.Series(["t"] * 4)
    eo = A2.effective_open(x["o"], date, "panel")
    m = float(np.log(1.02))
    assert eo[0] == pytest.approx(m) and (eo[1:] == 0).all()
    a2 = A2.kernel(x["o"], x["c"], x["u"], x["d"], eo)
    assert a2[0] == pytest.approx(0.8 * (m * m + m * m))        # overnight m^2, and the one-price step back to PC
    assert AN.kernel(x["o"], x["c"], x["u"], x["d"], pd.Series(0.0, index=x.index))[0] == 0.0


def test_a_stale_open_with_a_session_extends_the_range_to_the_market_move():
    # open at the previous close, then the session trades between 101 and 103; the market opened 2% up
    x = _coords([100, 102, 102], [103, 103, 103], [100, 101, 101], [102, 102, 102], [100, 100, 100])
    date = pd.Series(["t"] * 3)
    eo = A2.effective_open(x["o"], date, "panel")
    m = float(np.log(1.02))
    h, l, r = np.log(1.03), np.log(1.00), np.log(1.02)
    R = max(h, m) - min(l, m)
    assert A2.kernel(x["o"], x["c"], x["u"], x["d"], eo)[0] == pytest.approx(0.8 * (m * m + R * R / (4 * LN2)) + 0.2 * r * r)


# ── the forecast ──────────────────────────────────────────────────────────────────────────

def test_fit_weights_recovers_known_convex_weights():
    rng = np.random.default_rng(3)
    Z = np.exp(rng.normal(0, 0.5, (20000, 4)))
    c_true = np.array([0.1, 0.3, 0.2, 0.4])
    y = (Z @ c_true) * rng.gamma(4.0, 0.25, 20000)            # mean-one multiplicative noise
    c, loss = A2.fit_weights(Z, y)
    assert c.sum() == pytest.approx(1.0) and (c >= 0).all() and c[-1] >= A2.FLOOR - 1e-12
    assert np.abs(c - c_true).max() < 0.05
    assert loss <= np.mean(y / (Z @ c_true) + np.log(Z @ c_true)) + 1e-9


def _panel(n_sec=12, n_days=420, seed=4):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    rows = []
    vol = np.exp(np.cumsum(rng.normal(0, 0.05, n_days)) * 0.3) * 0.01
    for s in range(n_sec):
        pc = 100.0
        for t, dt in enumerate(dates):
            o = rng.normal(0, 0.4 * vol[t]); c = rng.normal(0, vol[t])
            O = pc * np.exp(o) if rng.uniform() > 0.2 else pc        # a fifth of the opens are stale
            C = O * np.exp(c)
            H = max(O, C) * np.exp(abs(rng.normal(0, 0.3 * vol[t])))
            L = min(O, C) * np.exp(-abs(rng.normal(0, 0.3 * vol[t])))
            rows.append((f"S{s}", dt, O, H, L, C, pc))
            pc = C
    x = pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "pc"])
    x = x.sort_values(["symbol", "date"]).reset_index(drop=True)
    co = AN.bar_coordinates(x["open"], x["high"], x["low"], x["close"], x["pc"])
    for k in ("o", "c", "u", "d", "r"):
        x[k] = co[k]
    x["CC"] = x["r"] ** 2
    return x


def test_forecaster_is_positive_with_weights_on_the_simplex():
    x = _panel()
    eo = A2.effective_open(x["o"], x["date"], "panel")
    A = A2.kernel(x["o"], x["c"], x["u"], x["d"], eo)
    fc = A2.Forecaster(A, x["CC"], x["symbol"], x["date"], "panel")
    assert list(fc.Z.columns) == ["d1", "m5", "m22", "lrM5", "lrM22", "lrCC", "lr"]
    y = x.groupby("symbol")["CC"].transform(lambda z: z[::-1].rolling(5, min_periods=5).mean()[::-1].shift(-1))
    rows = fc.defined & y.notna()
    c, loss = fc.fit(y, rows)
    assert c.sum() == pytest.approx(1.0) and (c >= -1e-15).all() and c[-1] >= A2.FLOOR - 1e-12
    f = fc.forecast(c)[fc.defined]
    assert (f > 0).all()
    # kappa * lrCC-component is the stock's own long-run mean of r^2
    lrcc = (fc.kappa * fc.Z["lrCC"])[fc.defined]
    own = x.groupby("symbol")["CC"].transform(lambda z: z.rolling(250, min_periods=60).mean())[fc.defined]
    assert np.allclose(lrcc, own, rtol=1e-10)


def test_series_mode_drops_the_factor_terms():
    x = _panel(n_sec=1)
    A = A2.kernel(x["o"], x["c"], x["u"], x["d"], A2.effective_open(x["o"], x["date"], "series"))
    fc = A2.Forecaster(A, x["CC"], x["symbol"], x["date"], "series")
    assert list(fc.Z.columns) == ["d1", "m5", "m22", "lrCC", "lr"]


# ── the Pakistan panel (M22) ──────────────────────────────────────────────────────────────

def test_psx_reader_keeps_ordinary_equity_only(tmp_path):
    rows = [("OGDC ", "2024-01-02", 100, 102, 99, 101, 1000, False),
            ("OGDC", "2024-01-02", 100, 102, 99, 101, 1000, False),     # repeat once stripped: kept once
            ("DCR", "2024-01-02", 10, 10.2, 9.9, 10.1, 500, False),     # a REIT
            ("FHAM", "2024-01-02", 20, 20.5, 19.8, 20.1, 300, False),   # a modaraba
            ("HGFA", "2024-01-02", 5, 5.1, 4.9, 5.0, 300, False),       # a closed-end fund
            ("MZNPETF", "2024-01-02", 9, 9.1, 8.9, 9.0, 300, False),    # an ETF
            ("SYS", "2024-01-02", 400, 410, 395, 405, 800, False)]
    comb = tmp_path / "combined.csv"
    pd.DataFrame(rows, columns=["symbol", "date", "open", "high", "low", "close", "volume", "is_anomaly"]).to_csv(comb, index=False)
    meta = tmp_path / "meta.csv"
    pd.DataFrame([("OGDC", "Oil & Gas Dev", "OIL & GAS EXPLORATION COMPANIES", False, False, False),
                  ("DCR", "Dolmen City REIT", "REAL ESTATE INVESTMENT TRUST", False, False, False),
                  ("FHAM", "First Habib Modaraba", "MODARABAS", False, False, False),
                  ("HGFA", "HBL Growth Fund", "CLOSE - END MUTUAL FUND", False, False, False),
                  ("MZNPETF", "Meezan ETF", "EXCHANGE TRADED FUNDS", True, False, False),
                  ("SYS", "Systems", "TECHNOLOGY & COMMUNICATION", False, False, False)],
                 columns=["symbol", "name", "sector_name", "is_etf", "is_debt", "is_gem"]).to_csv(meta, index=False)
    x = F.read_psx(comb, meta, check=False)
    assert sorted(x["symbol"]) == ["OGDC", "SYS"]
    assert list(x.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]


def test_psx_band_schedule_and_rupee_step():
    dates = pd.Series(pd.to_datetime(["2019-12-31", "2020-01-19", "2020-01-20", "2024-05-26", "2024-05-27", "2026-10-08"]))
    assert list(F.band_on(dates, F.PSX_BANDS)) == [0.05, 0.05, 0.075, 0.075, 0.10, 0.10]
    d = pd.bdate_range("2018-01-01", periods=4)
    cheap = pd.DataFrame({"symbol": "LOW", "date": d, "open": [5.0, 5.0, 6.0, 6.0], "high": [5.0, 6.0, 6.0, 6.0],
                          "low": [5.0, 5.0, 6.0, 6.0], "close": [5.0, 6.0, 6.0, 6.0], "volume": 100.0})
    dear = pd.DataFrame({"symbol": "HIGH", "date": d, "open": [100.0, 100.0, 107.0, 107.0], "high": [100.0, 107.0, 107.0, 107.0],
                         "low": [100.0, 100.0, 107.0, 107.0], "close": [100.0, 107.0, 107.0, 107.0], "volume": 100.0})
    panel, log = F.build_panel(pd.concat([cheap, dear], ignore_index=True), min_securities=1, **F.MARKETS["PK"])
    kept = set(zip(panel["symbol"], panel["date"]))
    assert ("LOW", d[1]) in kept            # +PKR 1 on a PKR 5 share (20%): inside "5% or PKR 1, the higher"
    assert ("HIGH", d[1]) not in kept       # +7% on a PKR 100 share in 2018: outside 5% plus the margin
    assert log["bars outside the band"] == 1
    assert "Pakistan 2016-2026" in F.SPANS_M22 and "Pakistan 2016-2026" not in {**F.SPANS, **F.SPANS_M18}
