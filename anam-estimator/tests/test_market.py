"""Anam II (``anam_estimator.market``): mechanics only. The kernel's properties, no look-ahead, purging, the series
case and persistence. The evidence is plan M22 in the parent repository, not these tests."""
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("scipy")

from anam_estimator import (AnamIIModel, bar_coordinates, effective_open, estimate_market, kernel,  # noqa: E402
                            market_kernel, market_move, prepare, simulate_bars)


@pytest.fixture(scope="module")
def bars():
    return simulate_bars(n_securities=12, n_sessions=600, seed=7)


def test_market_move_leaves_the_security_out():
    o = pd.Series([0.01, 0.03, -0.02, 0.05])
    date = pd.Series(["a", "a", "a", "b"])
    m = market_move(o, date)
    assert m[0] == pytest.approx(0.005) and m[2] == pytest.approx(0.02) and m[3] == 0.0


def test_kernel_is_open_free_where_the_open_moved_and_credits_a_stale_bar():
    co = bar_coordinates([101.0, 100.0, 102.0], [103.0, 100.0, 103.0], [100.5, 100.0, 101.0],
                         [102.0, 100.0, 102.5], [100.0, 100.0, 100.0])
    date = pd.Series(["t", "t", "t"])
    eo = effective_open(co["o"], date, "panel")
    assert eo[0] == 0.0 and eo[2] == 0.0                      # their opens moved
    m = (co["o"][0] + co["o"][2]) / 2
    assert eo[1] == pytest.approx(m)                          # the stale bar reads the others' move
    A = market_kernel(co["o"], co["c"], co["u"], co["d"], eo)
    of = kernel(co["o"], co["c"], co["u"], co["d"], pd.Series(0.0, index=co.index))
    assert A[0] == pytest.approx(of[0], rel=1e-12) and A[2] == pytest.approx(of[2], rel=1e-12)
    assert of[1] == 0.0 and A[1] == pytest.approx(0.8 * 2 * m * m)


def test_estimates_use_no_future_bars(bars):
    cut = sorted(bars["date"].unique())[400]
    full = estimate_market(prepare(bars), mode="panel")
    past = estimate_market(prepare(bars[bars["date"] <= cut]), mode="panel")
    rows = (prepare(bars)["date"] <= cut).to_numpy()
    np.testing.assert_allclose(full[rows].to_numpy(), past.to_numpy(), equal_nan=True)


def test_weights_are_convex_and_training_stops_before_train_end(bars):
    cut = pd.Timestamp(sorted(bars["date"].unique())[450])
    m = AnamIIModel(horizon=5).fit(bars, train_end=cut)
    w = m.weights(5)
    assert m.components_ == ["d1", "m5", "m22", "lrM5", "lrM22", "lrCC", "lr"]
    assert w.sum() == pytest.approx(1.0) and (w >= -1e-15).all() and w[-1] >= 0.05 - 1e-12
    # refitting on data cut at the boundary gives the same weights: no outcome after train_end was used
    before = bars[bars["date"] < cut]
    m2 = AnamIIModel(horizon=5).fit(before)
    np.testing.assert_allclose(m2.weights(5), w, atol=1e-8)
    bt = m.backtest()
    assert (bt["date"] >= cut).all() and (bt["forecast"] > 0).all()


def test_series_mode_and_persistence(tmp_path, bars):
    one = bars[bars["symbol"] == bars["symbol"].iloc[0]]
    m = AnamIIModel(horizon=5, mode="series").fit(one)
    assert m.components_ == ["d1", "m5", "m22", "lrCC", "lr"]
    assert (m.variance_path()["market_open"].dropna() == 0).all()
    m.save(tmp_path / "m.json")
    m2 = AnamIIModel.load(tmp_path / "m.json")
    np.testing.assert_array_equal(m2.weights(5), m.weights(5))
    f = m2.forecast(one)
    assert len(f) == 1 and f["variance"].iloc[0] > 0


def test_too_little_history_is_explained(bars):
    short = bars[bars["date"] <= sorted(bars["date"].unique())[50]]
    with pytest.raises(ValueError, match="not enough history"):
        AnamIIModel(horizon=5).fit(short)
