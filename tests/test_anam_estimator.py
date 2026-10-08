"""Anam's estimator: the properties its definition claims, checked where the answer is known."""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nepsevol.estimators import anam as A  # noqa: E402
from nepsevol.estimators.microsim import simulate_panel  # noqa: E402

LN2 = np.log(2.0)


def random_bars(n=5000, seed=0, sd=0.02):
    """Coordinates of internally consistent bars: L <= min(O, C) <= max(O, C) <= H."""
    rng = np.random.default_rng(seed)
    o = rng.normal(0, sd / 2, n)
    c = rng.normal(0, sd, n)
    u = np.maximum(0, c) + np.abs(rng.normal(0, sd / 2, n))
    d = np.minimum(0, c) - np.abs(rng.normal(0, sd / 2, n))
    return pd.Series(o), pd.Series(c), pd.Series(u), pd.Series(d)


def test_kernel_is_never_negative():
    o, c, u, d = random_bars()
    for bval in (0.0, 0.27, 0.6, 1.0):
        k = A.kernel(o, c, u, d, pd.Series(bval, index=o.index))
        assert (k >= 0).all(), bval


def test_clean_open_gives_overnight_plus_parkinson():
    o, c, u, d = random_bars(seed=1)
    k = A.kernel(o, c, u, d, pd.Series(1.0, index=o.index))
    expected = o ** 2 + (u - d) ** 2 / (4 * LN2)
    assert np.allclose(k, expected)


def test_worthless_open_gives_the_true_range_blend():
    o, c, u, d = random_bars(seed=2)
    k = A.kernel(o, c, u, d, pd.Series(0.0, index=o.index))
    h, l, r = o + u, o + d, o + c
    true_range = np.maximum(h, 0) - np.minimum(l, 0)          # Wilder: max(H, PC) - min(L, PC)
    expected = 0.8 * true_range ** 2 / (4 * LN2) + 0.2 * r ** 2
    assert np.allclose(k, expected)


def test_extended_range_contains_the_range_and_reaches_the_effective_open():
    o, c, u, d = random_bars(seed=3)
    for bval in (0.0, 0.4, 1.0):
        b = pd.Series(bval, index=o.index)
        Rs = A.extended_range(o, u, d, b)
        assert (Rs >= (u - d) - 1e-15).all()
        # the extended interval [min(l, b o), max(h, b o)] has exactly this length
        h, l, ot = o + u, o + d, b * o
        assert np.allclose(Rs, np.maximum(h, ot) - np.minimum(l, ot))


def test_kernel_scales_with_variance():
    o, c, u, d = random_bars(seed=4)
    b = pd.Series(0.3, index=o.index)
    k1 = A.kernel(o, c, u, d, b)
    k3 = A.kernel(3 * o, 3 * c, 3 * u, 3 * d, b)
    assert np.allclose(k3, 9 * k1)


def test_open_quality_recovers_the_permanent_share():
    # o = e + eta (eta transient, independent), r = e + e_c: b = var(e) / (var(e) + var(eta))
    rng = np.random.default_rng(5)
    n_dates, n_sec = 300, 50
    date = pd.Series(np.repeat(np.arange(n_dates), n_sec))
    e = rng.normal(0, 0.01, len(date)); eta = rng.normal(0, 0.015, len(date)); ec = rng.normal(0, 0.02, len(date))
    o, r = pd.Series(e + eta), pd.Series(e + ec)
    b = A.open_quality_panel(o, r, date, sessions=60)
    true_b = 0.01 ** 2 / (0.01 ** 2 + 0.015 ** 2)
    assert abs(b.iloc[-1] - true_b) < 0.03
    assert b[date < A.MIN_POOL_DATES - 1].isna().all()        # not defined before enough history


def test_open_quality_is_zero_where_the_open_never_moves():
    date = pd.Series(np.repeat(np.arange(40), 3))
    o = pd.Series(0.0, index=date.index); r = pd.Series(np.linspace(-0.01, 0.01, len(date)))
    assert (A.open_quality_panel(o, r, date).dropna() == 0.0).all()


@pytest.fixture(scope="module")
def sim():
    return simulate_panel(n_sec=40, n_days=260, seed=11).sort_values(["symbol", "day"]).reset_index(drop=True)


def test_no_look_ahead(sim):
    full = A.anam_estimator(sim, window=21, mode="panel", date="day")
    cut = sim["day"].quantile(0.6)
    part = sim[sim["day"] <= cut]
    early = A.anam_estimator(part, window=21, mode="panel", date="day")
    both = full.loc[early.index]
    m = early["var"].notna()
    assert m.sum() > 1000
    assert np.allclose(early.loc[m, "var"], both.loc[m, "var"])
    assert np.allclose(early["b"].dropna(), both["b"].loc[early["b"].dropna().index])


def test_series_mode_runs_one_series_at_a_time(sim):
    one = sim[sim["symbol"] == sim["symbol"].iloc[0]].reset_index(drop=True)
    out = A.anam_estimator(one, window=21, mode="series", date="day")
    assert out["var"].notna().sum() > 100 and (out["var"].dropna() > 0).all()


def test_calibration_sets_the_level_to_close_to_close(sim):
    out = A.anam_estimator(sim, window=21, mode="panel", date="day")
    r2 = np.log(sim["close"] / sim["prev_close"]) ** 2
    m = out["var"].notna() & r2.notna()
    ratio = out.loc[m, "var"].mean() / r2.groupby(sim["symbol"]).transform(
        lambda z: z.rolling(21, min_periods=21).mean())[m].mean()
    assert abs(ratio - 1) < 0.06


def test_estimates_true_total_variance_under_a_heavy_opening_error():
    """Where the open's error is 2.2 overnight sd (b ~ 0.27, NEPSE's level), the calibrated estimator
    tracks the TRUE total variance better than overnight^2 + Parkinson under the same calibration,
    and its uncalibrated level is far closer to the truth than Yang-Zhang-type sums."""
    s = simulate_panel(n_sec=60, n_days=300, seed=7, auction_noise_frac=2.2).sort_values(["symbol", "day"])
    s = s.reset_index(drop=True)
    out = A.anam_estimator(s, window=21, mode="panel", date="day")
    co = A.bar_coordinates(s.open, s.high, s.low, s.close, s.prev_close)
    truth = (s.iv + s.on).groupby(s.symbol).transform(lambda z: z.rolling(21, min_periods=21).mean())
    alt = co.o ** 2 + (co.u - co.d) ** 2 / (4 * LN2)
    kap = A.calibration_panel(alt, co.r ** 2, s["day"])
    alt_var = kap * alt.groupby(s.symbol).transform(lambda z: z.rolling(21, min_periods=21).mean())
    m = out["var"].notna() & alt_var.notna() & truth.notna()
    ql = lambda f: float(np.mean(truth[m] / f[m] - np.log(truth[m] / f[m]) - 1))
    assert ql(out["var"]) < ql(alt_var)
    raw_alt = alt.groupby(s.symbol).transform(lambda z: z.rolling(21, min_periods=21).mean())
    raw_anam = out["kernel"].groupby(s.symbol).transform(lambda z: z.rolling(21, min_periods=21).mean())
    assert abs(raw_anam[m].mean() / truth[m].mean() - 1) < abs(raw_alt[m].mean() / truth[m].mean() - 1)


def test_open_free_option_is_the_b_zero_kernel_calibrated_the_same_way(sim):
    """The open-free form (b = 0) is reachable through the public function and equals the kernel at
    b = 0 with the same pooled calibration; the default is the frozen M16 estimator, unchanged."""
    d = sim
    of = A.anam_estimator(d, window=21, mode="panel", by="symbol", date="day", open_free=True)
    full = A.anam_estimator(d, window=21, mode="panel", by="symbol", date="day")
    co = A.bar_coordinates(d["open"], d["high"], d["low"], d["close"], d["prev_close"])
    A0 = A.kernel(co["o"], co["c"], co["u"], co["d"], pd.Series(0.0, index=d.index))
    assert (of["b"] == 0).all() and np.allclose(of["kernel"].dropna(), A0.dropna())
    k0 = A.calibration_panel(A0, co["r"] ** 2, d["day"])
    ok = of["kappa"].notna()
    assert np.allclose(of["kappa"][ok], k0[ok])
    j = full["kernel"].notna() & of["kernel"].notna()     # the full form waits for its pooled b
    assert not np.allclose(full["kernel"][j], of["kernel"][j])

