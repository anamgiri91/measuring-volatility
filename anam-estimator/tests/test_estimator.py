import numpy as np
import pytest

from anam_estimator import anam_estimator, estimate, prepare


def test_output_layout_and_units(panel):
    e = anam_estimator(panel, annualize=252)
    for col in ("symbol", "date", "b", "kappa", "variance", "volatility", "cc_variance", "volatility_annualized"):
        assert col in e.columns
    ok = e["variance"].notna()
    np.testing.assert_allclose(e.loc[ok, "volatility"] ** 2, e.loc[ok, "variance"], rtol=1e-12)
    np.testing.assert_allclose(e.loc[ok, "volatility_annualized"] ** 2, e.loc[ok, "variance"] * 252, rtol=1e-12)
    assert e.attrs["mode"] == "panel" and e.attrs["form"] == "full"


def test_open_quality_is_recovered_and_the_open_free_form_ignores_it(panel):
    e = anam_estimator(panel)
    assert e["b"].dropna().between(0, 1).all()
    assert e["b"].median() == pytest.approx(0.5, abs=0.1)        # simulated with open_noise = 1
    f = anam_estimator(panel, form="open-free")
    assert (f["b"].dropna() == 0).all()


def test_the_calibrated_level_is_on_the_close_to_close_scale(panel):
    for form in ("full", "open-free"):
        e = anam_estimator(panel, form=form)
        ok = e["variance"].notna() & e["cc_variance"].notna()
        assert e.loc[ok, "variance"].mean() / e.loc[ok, "cc_variance"].mean() == pytest.approx(1.0, abs=0.05)


def test_auto_mode_follows_the_number_of_securities(panel, series):
    assert anam_estimator(series).attrs["mode"] == "series"
    assert anam_estimator(panel).attrs["mode"] == "panel"
    assert anam_estimator(panel, mode="series").attrs["mode"] == "series"


def test_bars_without_a_previous_close_are_left_out_not_poisoning_windows(series):
    e = anam_estimator(series)
    assert np.isnan(e["variance"].iloc[0])
    est = estimate(prepare(series), mode="series")
    assert est["r2"].notna().sum() == len(series) - 1     # every bar but the first has its coordinates
    bad = series.copy()
    bad.loc[200, "high"] = bad.loc[200, "low"] * 0.99      # one invalid bar in the middle
    with pytest.warns(UserWarning):
        f = anam_estimator(bad)
    assert np.isnan(f["variance"].iloc[200])
    assert f["variance"].iloc[201:222].notna().all()      # the windows after it skip it, as in the paper


def test_bad_arguments_are_refused(series):
    with pytest.raises(ValueError, match="form"):
        anam_estimator(series, form="half")
    with pytest.raises(ValueError, match="mode"):
        anam_estimator(series, mode="pooled")
    with pytest.raises(ValueError, match="annualize"):
        anam_estimator(series, annualize="yearly")
