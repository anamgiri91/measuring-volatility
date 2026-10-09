"""The experimental ML forecaster: mechanics only (fit, forecast, purging, no look-ahead, persistence).
None of these tests is evidence that it forecasts better than anything."""
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")

from anam_estimator import AnamMLModel, prepare, simulate_bars  # noqa: E402
from anam_estimator.ml import FEATURES, build_features, future_mean  # noqa: E402


@pytest.fixture(scope="module")
def bars():
    return simulate_bars(n_securities=10, n_sessions=500, seed=11)


def test_features_use_no_future_bars(bars):
    cut = sorted(bars["date"].unique())[350]
    full, _ = build_features(prepare(bars), "panel")
    past, _ = build_features(prepare(bars[bars["date"] <= cut]), "panel")
    p = prepare(bars)
    rows = (p["date"] <= cut).to_numpy()
    np.testing.assert_allclose(full[rows].to_numpy(), past.to_numpy(), equal_nan=True)
    assert list(full.columns) == list(FEATURES)


def test_training_targets_stop_before_train_end(bars):
    cut = pd.Timestamp(sorted(bars["date"].unique())[350])
    m = AnamMLModel(horizon=5).fit(bars, train_end=cut)
    p, _, F, y = m._fitted
    _, end = future_mean(build_features(p, "panel")[1], p, 5)
    assert m.validation_cut_ < cut and 1 <= m.n_iter_ <= m.max_iter
    assert m.n_train_ == int((F["log_A_of_21"].notna() & y.notna() & (y > 0) & (end < cut)).sum())
    bt = m.backtest()
    assert (bt["date"] >= cut).all() and m.score() == pytest.approx(bt["qlike"].mean())


def test_forecast_and_persistence(tmp_path, bars):
    m = AnamMLModel(horizon=5, annualize=252).fit(bars)
    fc = m.forecast()
    assert len(fc) == bars["symbol"].nunique() and (fc["variance"] > 0).all()
    m.save(tmp_path / "ml.joblib")
    again = AnamMLModel.load(tmp_path / "ml.joblib")
    pd.testing.assert_frame_equal(again.forecast(bars), fc)
    with pytest.raises(RuntimeError, match="pass data"):
        again.forecast()


def test_too_little_history_is_explained(bars):
    with pytest.raises(ValueError, match="not enough history"):
        AnamMLModel().fit(bars[bars["symbol"] == "S001"].iloc[:90])
