"""The installable package (``anam-estimator/``) and the research code agree.

* Its estimator equals the frozen research module (``nepsevol.estimators.anam``) on every NEPSE stock-day
  and on both indices, in both forms.
* Its model (version 0.2.0) is the corrected evaluation of plan M20 for one forecast: the same target over
  h consecutive exchange sessions, purged training origins, canonical QLIKE and the convex phi grid. The
  research side is rebuilt here from ``nepsevol.forecast_baselines`` and the shared target, and the two
  agree origin by origin.
* The frozen evaluation (``nepsevol.volforecast``), whose defects M20 corrects, still reproduces the frozen
  Table 34, which stays in the record.
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
from anam_estimator import evaluation as EV  # noqa: E402
from nepsevol import forecast_baselines as FB  # noqa: E402
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


def _nepse_calendar():
    cal = pd.read_csv(ROOT / "data" / "processed" / "nepse_trading_calendar.csv", parse_dates=["date"])
    return pd.DatetimeIndex(cal.loc[cal["is_session"], "date"])


def _research_single(d, kernel, train, test_start, win, scheme, calendar):
    """M20's corrected evaluation of one forecast, from the research module's features."""
    sym, r2, date = d["symbol"], FB.clean_square(d["CC"]), d["date"]
    kernel = FB.clean_square(kernel)
    valid = kernel.notna() & r2.notna()
    Xv = kernel.where(valid)
    cur = FB.rolling_rows(Xv, sym, win)
    lr = FB.rolling_rows(Xv, sym, FB.LONGRUN_SESSIONS, FB.LONGRUN_MIN)
    if scheme == "pool":
        kappa = FB.pooled_kappa(Xv, r2, date, AN.POOL_SESSIONS, AN.MIN_POOL_DATES)
    else:
        kappa = FB.series_kappa(Xv, r2, sym, AN.SERIES_SESSIONS, AN.MIN_SERIES_SESSIONS)
    ses = EV.session_ordinal(date, calendar)
    tgt = EV.forward_target(r2, sym, ses, win)
    ready = kappa.notna() & lr.notna() & cur.notna() & (kappa > 0) & (lr > 0) & tgt["y"].notna()
    cutoff = int(ses[date >= test_start].min())
    tr = train & ready & EV.purged(tgt["end_session"], cutoff)
    fc = lambda ph: kappa * (ph * cur + (1 - ph) * lr)
    phi, _, _ = EV.select_by_loss(ae.PHI_GRID, tgt["y"], tr, fc)
    te = (date >= test_start) & ready
    f = fc(phi)[te]
    return phi, d.loc[te, ["symbol", "date"]].assign(research=EV.qlike_canonical(tgt["y"][te], f))


def _check_against_the_research_evaluation(d, kernel, train, test_start, win, scheme, form, mode, calendar):
    phi, ref = _research_single(d, kernel, train, test_start, win, scheme, calendar)
    m = ae.AnamModel(form=form, horizon=win, mode=mode, calendar=calendar).fit(
        d[COLS], prev_close="pc", train_end=test_start)
    assert m.phi_ == pytest.approx(phi, abs=1e-12)
    bt = m.backtest()
    both = bt.merge(ref, on=["symbol", "date"])
    assert len(both) == len(bt) == len(ref)
    assert np.max(np.abs(both["qlike_canonical"] - both["research"])) < 1e-9


@pytest.mark.parametrize("win", [5, 21])
def test_model_is_the_corrected_evaluation_on_the_indices(indices, s40, win):
    for x in indices.values():
        est, _ = s40.estimator_set(x, "series")
        half = x.loc[x["span"] == "test", "date"].min()
        for name, form in (("Anam", "full"), (VARIANT, "open-free")):
            _check_against_the_research_evaluation(x, est[name], x["span"] == "train", half, win, "series", form,
                                                   "series", pd.DatetimeIndex(x["date"]))


@pytest.mark.parametrize("win", [5, 21])
def test_model_is_the_corrected_evaluation_on_nepse(nepse, s40, win):
    d = nepse
    est, _ = s40.estimator_set(d, "panel")
    train = d["regime"].isin(["A1", "B"])
    a2 = d.loc[d["regime"] == "A2", "date"].min()
    assert d.loc[train, "date"].max() < a2
    for name, form in (("Anam", "full"), (VARIANT, "open-free")):
        _check_against_the_research_evaluation(d, est[name], train, a2, win, "pool", form, "panel",
                                               _nepse_calendar())


def test_the_frozen_evaluation_still_reproduces_table_34(indices, s40):
    f = pd.read_csv(ROOT / "output" / "tables" / "table101_anam_holdout_forecast.csv")
    for mk, x in indices.items():
        est, _ = s40.estimator_set(x, "series")
        for w in (5, 21):
            t, _ = fair_forecast_test(x, est, x["span"] == "train", x["span"] == "test", win=w,
                                      scheme=("series", AN.SERIES_SESSIONS), refs=("Anam", "P", "CC"))
            row = f[(f.market == mk) & (f.test_span == "test half") & (f.window == w) & (f.estimator == "Anam")].iloc[0]
            assert t.loc["Anam", "phi"] == pytest.approx(row.phi, abs=1e-9)
            assert t.loc["Anam", "QLIKE"] == pytest.approx(row.QLIKE, rel=1e-9)
            assert int(t.loc["Anam", "n"]) == int(row.n)


def test_the_research_and_package_rules_for_zero_are_the_same():
    rng = np.random.default_rng(0)
    x = pd.Series(np.where(rng.random(600) < 0.4, 0.0, rng.exponential(1e-4, 600)))
    x[rng.random(600) < 0.05] = 1e-33                    # residues of equal prices
    x[rng.random(600) < 0.05] = np.nan
    by = pd.Series(np.repeat(["A", "B", "C"], 200))
    assert FB.ZERO_SQUARE == EV.ZERO_SQUARE
    pd.testing.assert_series_equal(FB.clean_square(x), EV.clean_square(x))
    for n, mp in ((5, None), (250, 60), (22, 10)):
        a = FB.rolling_rows(FB.clean_square(x), by, n, mp)
        b = EV.rolling_mean_exact(EV.clean_square(x), by, n, mp)
        pd.testing.assert_series_equal(a, b)
    # a window of exact zeros has a mean of exactly zero, not a residue
    z = pd.Series([1e-3, 2e-3] + [0.0] * 30)
    m = FB.rolling_rows(z, pd.Series(["A"] * 32), 5)
    assert (m.iloc[7:] == 0.0).all()
