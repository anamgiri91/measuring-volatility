"""Estimators are validated against a case with a KNOWN answer.

With a densely-observed path (high n_trades), every estimator must recover the
true sigma. If these fail, nothing downstream is trustworthy.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pytest
from nepsevol.estimators import range_ as R
from nepsevol.estimators.simulate import simulate_ohlc

TRUE_SIGMA = 0.02
DENSE = 2000


@pytest.fixture(scope="module")
def dense():
    return simulate_ohlc(n_days=8000, sigma_daily=TRUE_SIGMA, n_trades=DENSE, seed=42)


@pytest.mark.parametrize("name,fn,tol", [
    ("close_to_close", R.close_to_close, 0.05),
    ("parkinson",      R.parkinson,      0.03),
    ("garman_klass",   R.garman_klass,   0.03),
    ("rogers_satchell",R.rogers_satchell,0.03),
])
def test_recovers_true_sigma(dense, name, fn, tol):
    """Densely observed -> unbiased. This is the textbook claim being checked."""
    sigma_hat = np.sqrt(np.nanmean(fn(dense)))
    rel = abs(sigma_hat - TRUE_SIGMA) / TRUE_SIGMA
    assert rel < tol, f"{name}: sigma_hat={sigma_hat:.5f} true={TRUE_SIGMA} rel_err={rel:.3%}"


def test_parkinson_zero_when_no_range():
    """H == L (a real occurrence on 5% of NEPSE stock-days) -> Parkinson is exactly 0."""
    import pandas as pd
    df = pd.DataFrame({"open": [100., 100.], "high": [100., 100.],
                       "low": [100., 100.], "close": [100., 100.]})
    assert float(R.parkinson(df).iloc[-1]) == 0.0


def test_range_estimators_more_efficient_when_dense(dense):
    """The textbook efficiency claim: range estimators have lower sampling variance
    than close-to-close WHEN the path is densely observed."""
    cc = R.close_to_close(dense).dropna()
    pk = R.parkinson(dense).dropna()
    assert pk.var() < cc.var(), "Parkinson should be more efficient than CC under dense sampling"


def test_discretisation_bias_is_downward():
    """The paper's core mechanism: sparse observation biases the range DOWNWARD."""
    sparse = simulate_ohlc(n_days=8000, sigma_daily=TRUE_SIGMA, n_trades=10, seed=7)
    sigma_sparse = np.sqrt(np.nanmean(R.parkinson(sparse)))
    assert sigma_sparse < TRUE_SIGMA * 0.9, f"expected downward bias, got {sigma_sparse:.5f}"


def test_close_to_close_survives_sparsity():
    """Close-to-close uses only closes, so it should be ~unaffected by trade count."""
    sparse = simulate_ohlc(n_days=8000, sigma_daily=TRUE_SIGMA, n_trades=10, seed=7)
    sigma_cc = np.sqrt(np.nanmean(R.close_to_close(sparse)))
    assert abs(sigma_cc - TRUE_SIGMA) / TRUE_SIGMA < 0.05


# ── AddRS (Kumar & Maheswaran 2014) ───────────────────────────────────────────
def _bar(o, h, l, c):
    import pandas as pd
    return pd.DataFrame({"open": [o], "high": [h], "low": [l], "close": [c]})


def test_addrs_equals_rs_plus_indicator_term():
    """The construction reduces to RS + (x^2/2)(I_u + I_v). Verified symbolically; pinned here
    numerically on a bar where neither indicator fires."""
    import pandas as pd
    df = _bar(100.0, 104.0, 97.0, 101.0)          # H>O, C<H, L<O, C>L -> no indicator fires
    assert float(R.add_rs(df).iloc[0]) == pytest.approx(float(R.rogers_satchell(df).iloc[0]))


def test_addrs_rescues_a_monotone_up_day():
    """O=L, C=H. Rogers-Satchell is exactly zero; AddRS returns the squared open-to-close return.
    This is the case that matters: 59.6% of our RS==0 observations are monotone, not degenerate."""
    df = _bar(100.0, 105.0, 100.0, 105.0)
    x = np.log(105.0 / 100.0)
    assert float(R.rogers_satchell(df).iloc[0]) == pytest.approx(0.0, abs=1e-15)
    assert float(R.add_rs(df).iloc[0]) == pytest.approx(x**2, rel=1e-9)


def test_addrs_rescues_a_monotone_down_day():
    df = _bar(100.0, 100.0, 95.0, 95.0)
    x = np.log(95.0 / 100.0)
    assert float(R.rogers_satchell(df).iloc[0]) == pytest.approx(0.0, abs=1e-15)
    assert float(R.add_rs(df).iloc[0]) == pytest.approx(x**2, rel=1e-9)


def test_addrs_zero_on_a_fully_degenerate_bar():
    """O=H=L=C. Both indicators fire but x=0, so there is nothing to substitute. AddRS cannot
    manufacture volatility from a bar with no price movement at all."""
    df = _bar(100.0, 100.0, 100.0, 100.0)
    assert float(R.add_rs(df).iloc[0]) == pytest.approx(0.0, abs=1e-15)


def test_addrs_is_scale_invariant():
    import pandas as pd
    a = _bar(100.0, 104.0, 97.0, 101.0)
    b = _bar(10000.0, 10400.0, 9700.0, 10100.0)
    assert float(R.add_rs(a).iloc[0]) == pytest.approx(float(R.add_rs(b).iloc[0]), rel=1e-9)


def test_addrs_non_negative_on_valid_bars():
    """Both components are non-negative on a consistent bar, so AddRS >= RS >= 0."""
    from nepsevol.estimators.simulate import simulate_observed_ohlc
    for n_tr in (2, 10, 200):
        df = simulate_observed_ohlc(4000, 0.02, n_tr, seed=n_tr)
        a = np.asarray(R.add_rs(df), dtype=float)
        assert np.nanmin(a) >= -1e-15
        assert np.nanmin(a - np.asarray(R.rogers_satchell(df), dtype=float)) >= -1e-15


def test_addrs_recovers_true_sigma_when_densely_observed(dense):
    sigma_hat = np.sqrt(np.nanmean(R.add_rs(dense)))
    assert abs(sigma_hat - TRUE_SIGMA) / TRUE_SIGMA < 0.05


# ---------------------------------------------------------------- security-type classification
def test_classify_recovers_instrument_type_from_ticker_and_par():
    from nepsevol.universe import classify
    assert classify("SBLD2091", 1080.0) == "debenture"     # bank debenture, par 1000
    assert classify("NICAD85/86", 1095.0) == "debenture"   # slash-format BS year
    assert classify("ADBLB86", 1010.0) == "debenture"      # 'B' bond form
    assert classify("SCBD", 1115.0) == "debenture"         # no year in ticker
    assert classify("NABIL", 625.0) == "equity"
    assert classify("UNL", 46888.0) == "equity"            # price alone must not imply debenture
    assert classify("NABILP", 302.0) == "promoter"
    assert classify("HBLPO", 400.0) == "promoter"
    assert classify("NMB50", 10.4) == "fund"               # par 10 beats the trailing digits
    assert classify("CMF1", 10.36) == "fund"


def test_fund_band_is_separated_by_an_empty_interval():
    """Funds are identified by price alone because nothing trades between 10.78 and 100."""
    from nepsevol.universe import FUND_MAX_CLOSE
    assert 10.78 < FUND_MAX_CLOSE < 100.0


def test_range_ceiling_matches_the_price_limit():
    import numpy as np, pandas as pd
    from nepsevol.clean.limits import range_ceiling, flag_infeasible_range
    d = pd.Series(pd.to_datetime(["2025-01-01", "2026-06-01"]))
    got = range_ceiling(d)
    np.testing.assert_allclose(got, [np.log(1.10 / 0.90), np.log(1.15 / 0.85)], rtol=1e-12)

    # a legal limit-to-limit session passes; the SJLICP record does not
    df = pd.DataFrame({"date": pd.to_datetime(["2025-01-01", "2024-05-12"]),
                       "high": [110.0, 480.0], "low": [90.0, 100.0]})
    assert list(flag_infeasible_range(df)) == [False, True]
