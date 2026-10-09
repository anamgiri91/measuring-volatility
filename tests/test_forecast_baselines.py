"""The forecast models added for plan M20 (``nepsevol.forecast_baselines``), checked against hand
calculations and against the properties the plan relies on: causality, positivity, the special cases."""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nepsevol import forecast_baselines as FB  # noqa: E402
from nepsevol.estimators import anam as AN  # noqa: E402


def test_ewma_and_garch_paths_follow_their_recursions_by_hand():
    r = np.array([[np.nan], [0.01], [np.nan], [-0.02], [0.0]])
    v = np.array([[np.nan], [1e-4], [1e-4], [2e-4], [2e-4]])
    e = FB.ewma_path(r, v, 0.9)
    assert np.isnan(e[0, 0]) and e[1, 0] == pytest.approx(1e-4)        # started at the level, then updated
    assert e[2, 0] == pytest.approx(e[1, 0])                           # no return: unchanged
    assert e[3, 0] == pytest.approx(0.9 * e[2, 0] + 0.1 * 0.02 ** 2)
    a, b, g = 0.05, 0.85, 0.1
    s = FB.garch_path(r, v, a, b, g)
    p = a + b + g / 2
    assert s[1, 0] == pytest.approx(1e-4)
    assert s[2, 0] == pytest.approx((1 - p) * 1e-4 + p * s[1, 0])      # missing shock -> its expectation
    assert s[3, 0] == pytest.approx((1 - p) * 2e-4 + (a + g) * 0.02 ** 2 + b * s[2, 0])   # a negative return
    assert s[4, 0] == pytest.approx((1 - p) * 2e-4 + b * s[3, 0])
    with pytest.raises(ValueError):
        FB.garch_path(r, v, 0.5, 0.6)


def test_garch_with_no_dynamics_is_the_long_run_level():
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, (50, 3))
    v = np.full((50, 3), 1e-4)
    np.testing.assert_allclose(FB.garch_path(r, v, 0.0, 0.0), v)


def test_the_h_step_mean_is_the_average_of_the_iterated_forecasts():
    s1, vb, p, h = np.array([3e-4]), np.array([1e-4]), 0.9, 7
    it = [vb + (s1 - vb) * p ** j for j in range(h)]
    assert FB.h_step_mean(s1, vb, p, h)[0] == pytest.approx(np.mean(it))


def test_forecasts_made_at_t_use_nothing_after_t():
    rng = np.random.default_rng(1)
    r = rng.normal(0, 0.01, (80, 4))
    v = np.full((80, 4), 1e-4)
    base = FB.garch_path(r, v, 0.06, 0.9, 0.04)
    r2 = r.copy()
    r2[50:] = rng.normal(0, 0.05, (30, 4))
    np.testing.assert_array_equal(FB.garch_path(r2, v, 0.06, 0.9, 0.04)[:50], base[:50])
    np.testing.assert_array_equal(FB.ewma_path(r2, v, 0.94)[:50], FB.ewma_path(r, v, 0.94)[:50])


def test_grids_are_admissible():
    for a, b, g in FB.GARCH_GRID + FB.GJR_GRID:
        assert a >= 0 and b >= 0 and g >= 0 and a + b + g / 2 < 1
    grid = FB.simplex_grid()
    assert len(grid) == 220 and all(abs(sum(c) - 1) < 1e-9 and c[3] >= 0.1 - 1e-12 for c in grid)


def test_posterior_kernel_special_cases_and_unbiasedness():
    rng = np.random.default_rng(2)
    n = 400
    o = pd.Series(rng.normal(0, 0.02, n))
    c = pd.Series(rng.normal(0, 0.02, n))
    u = np.maximum(0, c) + rng.exponential(0.01, n)
    d = np.minimum(0, c) - rng.exponential(0.01, n)
    m2 = pd.Series(np.full(n, 4e-4))
    one, zero = pd.Series(np.ones(n)), pd.Series(np.zeros(n))
    np.testing.assert_allclose(FB.posterior_kernel(o, c, u, d, one, m2), o ** 2 + (u - d) ** 2 / (4 * np.log(2)))
    np.testing.assert_allclose(FB.posterior_kernel(o, c, u, d, zero, m2), AN.kernel(o, c, u, d, zero))
    assert (FB.tr_parkinson(o, u, d) >= (u - d) ** 2 / (4 * np.log(2)) - 1e-18).all()
    # under an uncorrelated opening error the posterior moment is unbiased for E[o*^2], (b o)^2 is not
    s, rho, N = 1.0, 0.8, 2_000_000
    ostar = rng.normal(0, s, N)
    obs = ostar + rng.normal(0, rho, N)
    b = s ** 2 / (s ** 2 + rho ** 2)
    m = s ** 2 + rho ** 2
    assert np.mean(b * b * obs ** 2 + b * (1 - b) * m) == pytest.approx(s ** 2, rel=5e-3)
    assert np.mean((b * obs) ** 2) == pytest.approx(b * s ** 2, rel=5e-3)


def test_matrix_round_trip():
    sec = np.array([0, 0, 1, 1, 1])
    ses = np.array([0, 2, 0, 1, 2])
    vals = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    M = FB.to_matrix(vals, sec, ses, 3, 2, ffill=True)
    assert M[1, 0] == 1.0                                              # carried over the missing session
    np.testing.assert_array_equal(FB.from_matrix(M, sec, ses), vals.to_numpy())
