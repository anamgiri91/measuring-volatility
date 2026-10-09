"""The installable package (``anam-estimator/``) gives the numbers the paper reports.

* Its estimator equals the frozen research module (``nepsevol.estimators.anam``) on every NEPSE stock-day
  and on both indices, in both forms.
* Its model's forecasts equal the paper's forecast test (``nepsevol.volforecast.fair_forecast_test``)
  origin by origin, with the same shrinkage, and so reproduce Table 34's losses wherever the paper
  scored the same origins. (The paper scored all nine estimators on the origins where every one of them
  was defined; for the NIFTY 50 and the S&P 500, and for NEPSE at 21 sessions, those are the model's own.)
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "anam-estimator" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import anam_estimator as ae  # noqa: E402
from nepsevol.estimators import anam as AN  # noqa: E402
from nepsevol.volforecast import fair_forecast_test  # noqa: E402

VARIANT = "Anam, open-free special case (b=0)"
COLS = ["symbol", "date", "open", "high", "low", "close", "pc"]


@pytest.fixture(scope="module")
def s40():
    spec = importlib.util.spec_from_file_location("s40_pkg", ROOT / "scripts" / "40_anam_holdout.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def nepse(s40):
    return s40.nepse()


@pytest.fixture(scope="module")
def indices(s40):
    pytest.importorskip("arch")
    return {"NIFTY50": s40.nifty(), "SP500": s40.sp500()}


def test_the_package_is_the_frozen_arithmetic():
    for name in ("LAMBDA0", "POOL_SESSIONS", "MIN_POOL_DATES", "SERIES_SESSIONS", "MIN_SERIES_SESSIONS"):
        assert getattr(ae, name) == getattr(AN, name), name


@pytest.mark.parametrize("open_free", [False, True])
def test_estimator_equals_the_frozen_module_on_every_nepse_stock_day(nepse, open_free):
    d = nepse
    frozen = AN.anam_estimator(d.assign(prev_close=d["pc"]), window=21, mode="panel", prev_close="pc",
                               open_free=open_free)
    p = ae.prepare(d[COLS], prev_close="pc", on_invalid="raise")
    mine = ae.estimate(p, form="open-free" if open_free else "full", window=21, mode="panel")
    got = p[["symbol", "date"]].join(mine).merge(d[["symbol", "date"]].join(frozen), on=["symbol", "date"])
    assert len(got) == len(d) == len(p)
    for a, b in (("b_x", "b_y"), ("kernel_x", "kernel_y"), ("kappa_x", "kappa_y"), ("variance", "var")):
        assert (got[a].isna() == got[b].isna()).all(), a
        assert np.nanmax(np.abs(got[a] - got[b])) == 0.0, a


def test_estimator_equals_the_frozen_module_on_both_indices(indices):
    for x in indices.values():
        for open_free in (False, True):
            frozen = AN.anam_estimator(x.assign(prev_close=x["pc"]), window=21, mode="series", prev_close="pc",
                                       open_free=open_free)
            mine = ae.estimate(ae.prepare(x[COLS], prev_close="pc"), form="open-free" if open_free else "full",
                               window=21, mode="series")
            np.testing.assert_array_equal(mine["variance"].to_numpy(), frozen["var"].to_numpy())


def _paper_test(d, kernel, train, test, win, scheme):
    t, losses = fair_forecast_test(d, {"X": kernel}, train, test, win=win, scheme=scheme, refs=("X",))
    return t.loc["X"], losses["X"]


def _check_against_the_paper_test(d, kernel, train, test, train_end, win, scheme, form, mode):
    t, losses = _paper_test(d, kernel, train, test, win, scheme)
    m = ae.AnamModel(form=form, horizon=win, mode=mode).fit(d[COLS], prev_close="pc", train_end=train_end)
    assert m.phi_ == pytest.approx(t["phi"], abs=1e-12)
    bt = m.backtest()
    assert len(bt) == int(t["n"])
    assert bt["qlike"].mean() == pytest.approx(t["QLIKE"], rel=1e-12)
    ref = d.loc[losses.index, ["symbol", "date"]].assign(paper=losses.to_numpy())
    both = bt.merge(ref, on=["symbol", "date"])
    assert len(both) == len(bt)
    assert np.max(np.abs(both["qlike"] - both["paper"])) < 1e-12


@pytest.mark.parametrize("win", [5, 21])
def test_model_forecasts_are_the_paper_test_on_the_indices(indices, s40, win):
    for x in indices.values():
        est, _ = s40.estimator_set(x, "series")
        half = x.loc[x["span"] == "test", "date"].min()
        for name, form in (("Anam", "full"), (VARIANT, "open-free")):
            _check_against_the_paper_test(x, est[name], x["span"] == "train", x["span"] == "test", half, win,
                                          ("series", AN.SERIES_SESSIONS), form, "series")


@pytest.mark.parametrize("win", [5, 21])
def test_model_forecasts_are_the_paper_test_on_nepse(nepse, s40, win):
    d = nepse
    est, _ = s40.estimator_set(d, "panel")
    train, test = d["regime"].isin(["A1", "B"]), d["regime"].isin(["A2", "C"])
    a2 = d.loc[d["regime"] == "A2", "date"].min()
    assert d.loc[train, "date"].max() < a2 <= d.loc[test, "date"].min()
    for name, form in (("Anam", "full"), (VARIANT, "open-free")):
        _check_against_the_paper_test(d, est[name], train, test, a2, win, ("pool", AN.POOL_SESSIONS), form, "panel")


def test_model_reproduces_table_34_where_the_paper_scored_the_same_origins(indices, nepse):
    f = pd.read_csv(ROOT / "output" / "tables" / "table101_anam_holdout_forecast.csv")

    def paper(mk, span, w):
        return f[(f.market == mk) & (f.test_span == span) & (f.window == w) & (f.estimator == "Anam")].iloc[0]
    cases = [(mk, x, "test half", w, x.loc[x["span"] == "test", "date"].min(), "series")
             for mk, x in indices.items() for w in (5, 21)]
    cases.append(("NEPSE", nepse, "A2+C", 21, nepse.loc[nepse["regime"] == "A2", "date"].min(), "panel"))
    for mk, x, span, w, start, mode in cases:
        m = ae.AnamModel(form="full", horizon=w, mode=mode).fit(x[COLS], prev_close="pc", train_end=start)
        row = paper(mk, span, w)
        assert m.phi_ == pytest.approx(row.phi, abs=1e-9), (mk, w)
        assert m.score() == pytest.approx(row.QLIKE, rel=1e-9), (mk, w)
        assert m.n_scored_ == int(row.n), (mk, w)
