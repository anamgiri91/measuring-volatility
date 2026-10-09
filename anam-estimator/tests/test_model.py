import json

import numpy as np
import pandas as pd
import pytest

from anam_estimator import PHI_GRID, AnamModel, qlike


def test_fit_and_forecast(panel):
    m = AnamModel(form="open-free", annualize=252).fit(panel)
    assert m.phi_ in PHI_GRID
    fc = m.forecast()
    assert len(fc) == panel["symbol"].nunique()
    assert (fc["variance"] > 0).all() and (fc["horizon"] == 5).all()
    assert (fc["as_of"] == panel["date"].max()).all()
    np.testing.assert_allclose(fc["volatility_annualized"] ** 2, fc["variance"] * 252, rtol=1e-12)
    assert "AnamModel(form='open-free'" in repr(m)


def test_forecasts_track_the_true_variance(panel):
    m = AnamModel(horizon=5).fit(panel)
    bt = m.backtest()
    truth = panel.set_index(["symbol", "date"])["true_variance"]
    t = truth.reindex(pd.MultiIndex.from_frame(bt[["symbol", "date"]])).to_numpy()
    assert np.corrcoef(bt["forecast"], t)[0, 1] > 0.6
    assert bt["forecast"].mean() / t.mean() == pytest.approx(1.0, abs=0.15)


def test_backtest_and_score_agree_and_train_end_splits_the_sample(panel):
    cut = panel["date"].sort_values().unique()[300]
    m = AnamModel().fit(panel, train_end=cut)
    bt = m.backtest()
    assert (bt["date"] >= cut).all()
    assert m.score() == pytest.approx(bt["qlike"].mean()) and m.n_scored_ == len(bt)
    np.testing.assert_allclose(bt["qlike"], qlike(bt["realised"], bt["forecast"]))
    insample = m.backtest(start=panel["date"].min())
    assert len(insample) > len(bt)


def test_a_new_horizon_is_fitted_on_first_use(series):
    m = AnamModel(horizon=5).fit(series)
    fc21 = m.forecast(horizon=21)
    assert 21 in m.phis_ and (fc21["horizon"] == 21).all()


def test_save_load_and_forecast_new_data_without_refitting(tmp_path, panel):
    m = AnamModel(form="full", horizon=5).fit(panel)
    path = tmp_path / "model.json"
    m.save(path)
    assert json.loads(path.read_text())["phis"] == {"5": m.phi_}
    loaded = AnamModel.load(path)
    pd.testing.assert_frame_equal(loaded.forecast(panel), m.forecast())
    with pytest.raises(RuntimeError, match="fit"):
        loaded.forecast(panel, horizon=21)
    with pytest.raises(RuntimeError, match="pass data"):
        loaded.forecast()


def test_too_little_history_is_explained(series):
    with pytest.raises(ValueError, match="not enough history"):
        AnamModel().fit(series.iloc[:80])


def test_securities_without_enough_history_are_reported(panel):
    late = panel[(panel["symbol"] != "S002") | (panel["date"] > panel["date"].sort_values().unique()[-30])]
    with pytest.warns(UserWarning, match="no forecast for 1"):
        fc = AnamModel(mode="series").fit(late).forecast()
    assert "S002" not in set(fc["symbol"])


def test_variance_path_matches_the_function(panel):
    from anam_estimator import anam_estimator
    m = AnamModel(window=21).fit(panel)
    a = m.variance_path()
    b = anam_estimator(panel, window=21)
    np.testing.assert_allclose(a["variance"].to_numpy(), b["variance"].to_numpy(), equal_nan=True)
