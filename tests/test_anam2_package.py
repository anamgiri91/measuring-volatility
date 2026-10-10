"""The package's Anam II (``anam_estimator.market``) is the frozen research module (``nepsevol.estimators.anam2``)
of plan M22: the same kernel, calibration and components on every NEPSE stock-day and on both indices, and the
same fitted weights and forecasts when both are fitted on the same purged training origins."""
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

pytest.importorskip("scipy")

import anam_estimator as ae  # noqa: E402
from anam_estimator import evaluation as EV  # noqa: E402
from nepsevol import forecast_baselines as FB  # noqa: E402
from nepsevol.estimators import anam2 as A2  # noqa: E402

COLS = ["symbol", "date", "open", "high", "low", "close", "pc"]


@pytest.fixture(scope="module")
def s40():
    spec = importlib.util.spec_from_file_location("s40_pkg2", ROOT / "scripts" / "40_anam_holdout.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def nepse(s40):
    return s40.nepse()


@pytest.fixture(scope="module")
def nifty(s40):
    pytest.importorskip("arch")
    return s40.nifty()


def _nepse_calendar():
    cal = pd.read_csv(ROOT / "data" / "processed" / "nepse_trading_calendar.csv", parse_dates=["date"])
    return pd.DatetimeIndex(cal.loc[cal["is_session"], "date"])


def _research(d, mode):
    eo = A2.effective_open(d["o"], d["date"], mode)
    A = A2.kernel(d["o"], d["c"], d["u"], d["d"], eo)
    return eo, A, A2.Forecaster(A, d["CC"], d["symbol"], d["date"], mode)


def test_the_package_constants_are_the_research_constants():
    assert ae.market.EPS == A2.EPS and ae.market.FLOOR == A2.FLOOR and ae.LAMBDA0 == A2.LAMBDA0


@pytest.mark.parametrize("which", ["nepse", "nifty"])
def test_kernel_calibration_and_components_equal_the_frozen_module(which, request):
    d = request.getfixturevalue(which)
    mode = "panel" if which == "nepse" else "series"
    eo, A, F = _research(d, mode)
    p = ae.prepare(d[COLS], prev_close="pc", on_invalid="raise")
    mine = ae.estimate_market(p, window=21, mode=mode)
    got = p[["symbol", "date"]].join(mine).merge(d[["symbol", "date"]].assign(eo=eo, A=A, kappa_r=F.kappa),
                                                 on=["symbol", "date"])
    assert len(got) == len(d) == len(p)
    for a, b in (("ostar", "eo"), ("kernel", "A"), ("kappa", "kappa_r")):
        assert (got[a].isna() == got[b].isna()).all(), a
        assert np.nanmax(np.abs(got[a] - got[b])) == 0.0, a
    m = ae.AnamIIModel(horizon=5, mode=mode)
    m._fitted = (p, mode, mine)
    c = m._components(p, mode, mine, 5)
    Zr = d[["symbol", "date"]].join(F.Z)
    Zp = p[["symbol", "date"]].join(c[F.Z.columns])
    both = Zp.merge(Zr, on=["symbol", "date"], suffixes=("_p", "_r"))
    for k in F.Z.columns:
        a, b = both[f"{k}_p"], both[f"{k}_r"]
        assert (a.isna() == b.isna()).all(), k
        assert np.nanmax(np.abs(a - b)) == 0.0, k


@pytest.mark.parametrize("win", [5, 21])
def test_weights_and_forecasts_equal_the_frozen_module_on_nepse(nepse, win):
    d = nepse
    cal = _nepse_calendar()
    a2 = d.loc[d["regime"] == "A2", "date"].min()
    _, _, F = _research(d, "panel")
    ses = EV.session_ordinal(d["date"], cal)
    tgt = EV.forward_target(FB.clean_square(d["CC"]), d["symbol"], ses, win)
    cutoff = int(ses[d["date"] >= a2].min())
    rows = F.defined & tgt["y"].notna() & EV.purged(tgt["end_session"], cutoff)
    c_r, _ = F.fit(tgt["y"], rows)
    m = ae.AnamIIModel(horizon=win, mode="panel", calendar=cal).fit(d[COLS], prev_close="pc", train_end=a2)
    np.testing.assert_allclose(m.weights(win), c_r, rtol=0, atol=1e-10)
    bt = m.backtest()
    f_r = F.forecast(c_r)
    te = (d["date"] >= a2) & F.defined & tgt["y"].notna()
    ref = d.loc[te, ["symbol", "date"]].assign(research=EV.qlike_canonical(tgt["y"][te], f_r[te]))
    both = bt.merge(ref, on=["symbol", "date"])
    assert len(both) == len(bt) == len(ref)
    assert np.max(np.abs(both["qlike_canonical"] - both["research"])) < 1e-9


def test_the_series_model_has_no_factor_terms(nifty):
    m = ae.AnamIIModel(horizon=5, mode="series").fit(nifty[COLS], prev_close="pc")
    assert m.components_ == ["d1", "m5", "m22", "lrCC", "lr"]
    w = m.weights(5)
    assert w.sum() == pytest.approx(1.0) and w[-1] >= A2.FLOOR - 1e-12


def test_save_and_load_keep_the_weights(tmp_path):
    p = ae.simulate_bars()
    m = ae.AnamIIModel(horizon=5).fit(p)
    m.save(tmp_path / "m.json")
    m2 = ae.AnamIIModel.load(tmp_path / "m.json")
    np.testing.assert_array_equal(m2.weights(5), m.weights(5))
    f1, f2 = m.forecast(), m2.forecast(p)
    np.testing.assert_allclose(f1["variance"].to_numpy(), f2["variance"].to_numpy(), rtol=1e-12)
