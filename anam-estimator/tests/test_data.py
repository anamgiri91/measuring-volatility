import numpy as np
import pandas as pd
import pytest

from anam_estimator import observed_sessions_per_year, prepare


def test_a_single_series_indexed_by_date_with_capitalised_columns(series):
    wide = series.rename(columns=str.title).set_index("Date")
    p = prepare(wide)
    assert list(p.columns[:7]) == ["symbol", "date", "open", "high", "low", "close", "prev_close"]
    assert (p["symbol"] == "series").all() and len(p) == len(series)
    np.testing.assert_array_equal(p["prev_close"].to_numpy()[1:], series["close"].to_numpy()[:-1])
    assert np.isnan(p["prev_close"].iloc[0])


def test_an_unnamed_date_index_is_read_as_the_date(series):
    p = prepare(series.set_index("date").rename_axis(None))
    assert p["date"].is_monotonic_increasing


@pytest.mark.parametrize("field_first", [True, False])
def test_two_level_columns_for_several_tickers(panel, field_first):
    two = panel[panel["symbol"].isin(["S001", "S002"])]
    wide = two.pivot(index="date", columns="symbol", values=["open", "high", "low", "close"])
    wide.columns = wide.columns.set_names(["Price", "Ticker"])
    if not field_first:
        wide = wide.swaplevel(axis=1)
    wide = wide.rename(columns=str.title, level=0 if field_first else 1)
    p = prepare(wide)
    assert sorted(p["symbol"].unique()) == ["S001", "S002"] and len(p) == len(two)


def test_a_ticker_column_and_sorting(panel):
    shuffled = panel.rename(columns={"symbol": "Ticker"}).sample(frac=1.0, random_state=1)
    p = prepare(shuffled)
    assert p.groupby("symbol")["date"].apply(lambda d: d.is_monotonic_increasing).all()


def test_duplicate_keys_and_missing_columns_are_refused(series):
    with pytest.raises(ValueError, match="duplicated"):
        prepare(pd.concat([series, series.iloc[:1]]))
    with pytest.raises(ValueError, match="missing price columns"):
        prepare(series.drop(columns="low"))
    with pytest.raises(ValueError, match="no date column"):
        prepare(series.drop(columns="date"))


def test_invalid_bars_are_excluded_repaired_or_refused(series):
    bad = series.copy()
    bad.loc[10, "high"] = bad.loc[10, "low"] * 0.99   # high below the low
    bad.loc[20, "close"] = -1.0
    with pytest.warns(UserWarning, match="2 of"):
        p = prepare(bad)
    assert p.loc[[10, 20], "open"].isna().all() and not p["valid"].iloc[[10, 20]].any()
    with pytest.warns(UserWarning, match="1 of"):
        r = prepare(bad, on_invalid="repair")
    assert r.loc[10, "high"] >= max(r.loc[10, "open"], r.loc[10, "close"])
    with pytest.raises(ValueError, match="invalid bars"):
        prepare(bad, on_invalid="raise")


def test_a_named_previous_close_and_a_gap_rule(series):
    s = series.copy()
    s["adj_prev"] = s["close"].shift(1) * 1.0
    p = prepare(s, prev_close="adj_prev")
    np.testing.assert_array_equal(p["prev_close"].to_numpy(), s["adj_prev"].to_numpy())
    gappy = series.drop(index=range(100, 130)).reset_index(drop=True)
    q = prepare(gappy, max_gap_days=10)
    assert int(q["prev_close"].isna().sum()) == 2   # the first bar and the bar after the gap


def test_observed_sessions_per_year():
    d = pd.bdate_range("2020-01-01", "2023-12-31")
    assert observed_sessions_per_year(d) == pytest.approx(261, abs=1.5)
