"""Tests for the instrumented calibration (nepsevol.calibration) and the panel simulator.

These target SPECIFICATIONS, not plumbing: that lagged instruments never see the session they
instrument, that the forward-orthogonal-deviation transformation removes a fixed effect without
leaking the future into the moments, that the slope is recovered where it is known and the naive
statistics are not, that the composite satisfies its constraint and does not depend on the
unidentified latent variance, and that the identified efficiency bound is a bound.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nepsevol import calibration as cal  # noqa: E402
from nepsevol.estimators import range_ as R  # noqa: E402
from nepsevol.estimators.microsim import MicroParams, simulate_panel  # noqa: E402


# ---------------------------------------------------------------------------------------------
# A linear measurement panel with a KNOWN answer
# ---------------------------------------------------------------------------------------------

def linear_panel(n_sec=60, n_days=500, betas=(1.0, 0.8, 1.3), alphas=(0.0, 0.5, -0.2),
                 noise_sd=(1.0, 0.5, 0.8), shared=0.7, sd_h=0.6, seed=1):
    """X_k = alpha_{k,i} + beta_k IV + U_k with same-day correlated, heteroskedastic noise.

    IV = V + transitory; V = exp(AR(1)) is predictable from the past; U is a martingale
    difference correlated across k within a day (corr ``shared``), the case in which classic
    errors-in-variables fixes that need independent errors fail. ``sd_h`` sets how much the
    latent log variance moves over time; it must be large enough for lagged measures to be
    STRONG instruments, or every IV estimator drifts toward OLS (weak-instrument bias) -- a
    property of the data, not of the estimator, which test_weak_instruments_pull_toward_ols
    documents separately.
    """
    rng = np.random.default_rng(seed)
    K = len(betas)
    rows = []
    for i in range(n_sec):
        h = np.zeros(n_days)
        for t in range(1, n_days):
            h[t] = 0.97 * h[t - 1] + rng.normal(0, sd_h * np.sqrt(1 - 0.97 ** 2))
        V = np.exp(h + 0.5 * rng.normal())
        IV = V * np.exp(rng.normal(0, 0.3, n_days) - 0.045)
        common = rng.normal(size=n_days)
        X = np.empty((n_days, K))
        for k in range(K):
            e = shared * common + np.sqrt(1 - shared ** 2) * rng.normal(size=n_days)
            X[:, k] = alphas[k] * (1 + i % 3) + betas[k] * IV + noise_sd[k] * IV * e
        df = pd.DataFrame(X, columns=[f"X{k}" for k in range(K)])
        df["symbol"] = f"S{i:03d}"
        df["date"] = pd.Timestamp("2020-01-01") + pd.to_timedelta(np.arange(n_days), unit="D")
        df["IV"] = IV
        rows.append(df)
    panel = pd.concat(rows, ignore_index=True)
    inst = cal.lagged_means(panel, ["X0", "X1"], windows=(1, 5, 22), skip=1)
    return pd.concat([panel, inst], axis=1).dropna().reset_index(drop=True)


@pytest.fixture(scope="module")
def lin():
    return linear_panel(n_sec=100)


def _fit(p, **kw):
    X = p[["X0", "X1", "X2"]].to_numpy()
    Z = p[[c for c in p.columns if "_L1m" in c]].to_numpy()
    return cal.calibrate(X, Z, p["symbol"], ["X0", "X1", "X2"], "X0", date=p["date"], **kw)


# ---------------------------------------------------------------------------------------------
# Instruments and transformations
# ---------------------------------------------------------------------------------------------

def test_lagged_means_never_see_the_session_they_instrument():
    df = pd.DataFrame({"symbol": ["A"] * 30, "date": pd.date_range("2020-01-01", periods=30),
                       "x": np.arange(30, dtype=float)})
    base = cal.lagged_means(df, ["x"], windows=(1, 5), skip=1)
    bumped = df.copy()
    bumped.loc[20, "x"] = 1e6                   # perturb session 20 only
    after = cal.lagged_means(bumped, ["x"], windows=(1, 5), skip=1)
    # row 20's instruments are built from sessions <= 19, so they must not move
    assert after.loc[20].equals(base.loc[20])
    # ... and the next session's must, which is what makes the perturbation a real test
    assert after.loc[21, "x_L1m1"] == 1e6


def test_lagged_means_with_skip_two_lag_one_more_session():
    df = pd.DataFrame({"symbol": ["A"] * 10, "date": pd.date_range("2020-01-01", periods=10),
                       "x": np.arange(10, dtype=float)})
    z = cal.lagged_means(df, ["x"], windows=(1,), skip=2)
    assert z.loc[5, "x_L2m1"] == 3.0


def test_lagged_means_do_not_cross_securities():
    df = pd.DataFrame({"symbol": ["A"] * 5 + ["B"] * 5,
                       "date": list(pd.date_range("2020-01-01", periods=5)) * 2,
                       "x": [1.0] * 5 + [100.0] * 5})
    z = cal.lagged_means(df, ["x"], windows=(1,), skip=1)
    assert np.isnan(z.loc[5, "x_L1m1"])          # B's first row has no B history
    assert z.loc[6, "x_L1m1"] == 100.0


def test_fod_removes_a_fixed_effect_and_drops_each_last_row():
    codes = np.repeat([0, 1], 6)
    M = np.r_[np.full(6, 3.0), np.full(6, -7.0)][:, None] + 0.0
    out, keep = cal.forward_orthogonal_deviations(M, codes)
    assert keep.sum() == 10 and not keep[5] and not keep[11]
    assert np.allclose(out[keep], 0.0)


def test_fod_keeps_white_noise_white():
    rng = np.random.default_rng(0)
    codes = np.repeat(np.arange(400), 25)
    e = rng.normal(size=(len(codes), 1))
    out, keep = cal.forward_orthogonal_deviations(e, codes)
    x = out[keep, 0]
    assert abs(x.var() - 1.0) < 0.03
    # adjacent transformed errors within a group are uncorrelated (whole-sample demeaning would
    # make them negatively correlated at order 1/T)
    g = codes[keep]
    same = g[1:] == g[:-1]
    r = np.corrcoef(x[1:][same], x[:-1][same])[0, 1]
    assert abs(r) < 0.02


def test_past_demean_uses_only_rows_up_to_each_row():
    codes = np.zeros(5, dtype=int)
    M = np.array([[1.0], [3.0], [5.0], [7.0], [100.0]])
    out = cal.past_demean(M, codes)
    assert np.allclose(out[:4, 0], [0.0, 1.0, 2.0, 3.0])


# ---------------------------------------------------------------------------------------------
# Identification: the slope is recovered, the naive statistics are not
# ---------------------------------------------------------------------------------------------

def test_instrumented_slopes_recover_the_truth(lin):
    r = _fit(lin)
    assert r.beta[0] == pytest.approx(1.0)
    # tolerances are about two sampling standard deviations at this panel size (checked over
    # seeds); the forward-orthogonal-deviation estimator is unbiased but less precise than the
    # whole-sample within estimator, which test_whole_sample_within_and_fod_agree bounds
    assert r.beta[1] == pytest.approx(0.8, abs=0.06)
    assert r.beta[2] == pytest.approx(1.3, abs=0.10)


def test_ols_slope_and_ratio_do_not_recover_the_slope(lin):
    """The point of the module: the naive statistics answer a different question."""
    r = _fit(lin)
    assert abs(r.ols_slope[1] - 0.8) > 0.1           # attenuated and contaminated by shared noise
    assert abs(r.ratio[1] - 0.8) > 0.1               # the additive alpha leaks into the ratio


def test_ratio_decomposes_exactly_into_slope_plus_additive_share(lin):
    r = _fit(lin)
    assert np.allclose(r.ratio, r.beta + r.delta)


def test_whole_sample_within_and_fod_agree_in_a_linear_model(lin):
    a = _fit(lin).beta
    b = _fit(lin, transform="within").beta
    assert np.allclose(a, b, atol=0.08)


def test_first_stage_is_strong_in_the_test_panel(lin):
    assert _fit(lin).first_stage_F > 50


def test_weak_instruments_pull_toward_ols():
    """With little persistent variation in latent variance the lagged measures are weak
    instruments and the slope drifts toward the OLS slope. The first-stage F statistic is the
    diagnostic, which is why every table of scripts/34 reports it."""
    weak = linear_panel(sd_h=0.15, noise_sd=(1.5, 0.6, 1.0), seed=2)
    r = _fit(weak)
    assert r.first_stage_F < _fit(linear_panel(seed=2)).first_stage_F
    assert abs(r.beta[1] - r.ols_slope[1]) < abs(0.8 - r.ols_slope[1]) + 0.2


def test_unknown_transform_is_refused(lin):
    with pytest.raises(ValueError):
        _fit(lin, transform="levels")


def test_fod_needs_dates(lin):
    X = lin[["X0", "X1"]].to_numpy()
    Z = lin[["X0_L1m1", "X0_L1m5"]].to_numpy()
    with pytest.raises(ValueError):
        cal.calibrate(X, Z, lin["symbol"], ["X0", "X1"], "X0")


def test_rank_one_share_is_near_one_under_the_model(lin):
    assert _fit(lin).rank_one_share > 0.97


def test_J_is_not_systematically_large_under_the_model(lin):
    r = _fit(lin)
    # J ~ chi2(L-1) = chi2(5) under the model; its 99.9% quantile is ~20.5
    assert np.nanmax(r.J) < 20.5


# ---------------------------------------------------------------------------------------------
# The composite and its bounds
# ---------------------------------------------------------------------------------------------

def test_composite_weights_satisfy_the_slope_constraint(lin):
    r = _fit(lin)
    assert float(r.weights @ r.beta) == pytest.approx(1.0)


def test_optimal_weights_do_not_depend_on_the_latent_variance():
    """Sherman-Morrison: Sigma_X = v beta beta' + Omega gives the same w* for every v."""
    rng = np.random.default_rng(3)
    A = rng.normal(size=(5, 5))
    Omega = A @ A.T + 5 * np.eye(5)
    beta = np.array([1.0, 0.8, 1.2, 0.9, 1.1])
    w_true = cal.optimal_weights(Omega, beta)
    for v in (0.0, 0.5, 10.0, 1e4):
        assert np.allclose(cal.optimal_weights(Omega + v * np.outer(beta, beta), beta), w_true)


def test_unconstrained_minimum_variance_rewards_attenuation():
    """Without w'beta = 1 the minimum-variance combination loads on an estimator that ignores
    volatility -- here a constant-like series with tiny variance and slope 0.05."""
    Sigma = np.diag([2.0, 0.5, 0.001])
    ones = np.ones(3)
    naive = np.linalg.solve(Sigma, ones)
    naive /= naive.sum()
    beta = np.array([1.0, 1.0, 0.05])
    constrained = cal.optimal_weights(Sigma, beta)
    assert naive[2] > 0.9                      # the naive weights pile onto the dead estimator
    assert float(naive @ beta) < 0.2           # ... and the result barely responds to variance
    assert float(constrained @ beta) == pytest.approx(1.0)


def test_identified_efficiency_bound_is_a_lower_bound(lin):
    r = _fit(lin)
    # true noise of each measure on the latent scale, from the known IV
    X = lin[["X0", "X1", "X2"]].to_numpy()
    betas = np.array([1.0, 0.8, 1.3])
    codes = pd.factorize(lin["symbol"])[0]
    out, keep = cal.forward_orthogonal_deviations(
        np.column_stack([X, lin["IV"].to_numpy()])[np.lexsort((lin["date"], codes))],
        codes[np.lexsort((lin["date"], codes))])
    Xs, IVs = out[keep, :3], out[keep, 3]
    U = Xs - np.outer(IVs, betas)
    Om = np.cov(U, rowvar=False)
    n_true = np.diag(Om) / betas ** 2
    w = cal.optimal_weights(Om, betas)
    n_comp = float(w @ Om @ w)
    true_eff = n_true / n_comp
    assert np.all(r.bounds["eff_lb"] <= true_eff * 1.05)


# ---------------------------------------------------------------------------------------------
# Building blocks and named measures
# ---------------------------------------------------------------------------------------------

def _bars(n=500, seed=4):
    rng = np.random.default_rng(seed)
    o = 100 * np.exp(rng.normal(0, 0.01, n))
    c = o * np.exp(rng.normal(0, 0.015, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.008, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.008, n)))
    v = np.exp(np.log(l) + rng.random(n) * (np.log(h) - np.log(l)))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "vwap": v})


def test_named_measures_equal_the_package_estimators():
    df = _bars()
    nm = cal.named_measures(cal.quadratic_blocks(cal.bar_logs(df)))
    assert np.allclose(nm["P"], R.parkinson(df))
    assert np.allclose(nm["GK"], R.garman_klass(df))
    assert np.allclose(nm["RS"], R.rogers_satchell(df))
    assert np.allclose(nm["OC"], np.log(df.close / df.open) ** 2)


def test_ap_is_the_average_price_estimator():
    df = _bars()
    L = cal.bar_logs(df)
    nm = cal.named_measures(cal.quadratic_blocks(L))
    assert np.allclose(nm["AP"], 2 * L.c ** 2 - 6 * L.a * L.c + 6 * L.a ** 2)


def test_vwap_blocks_require_a_vwap_column():
    df = _bars().drop(columns="vwap")
    with pytest.raises(ValueError):
        cal.quadratic_blocks(cal.bar_logs(df), with_vwap=True)


def test_gk_vwap_weights_are_unbiased_under_brownian_motion():
    """E[GKV] = sigma^2 for continuously observed driftless BM with uniform volume. Exact
    bridge-sampled extrema and a bridge-corrected time integral keep the check sharp."""
    rng = np.random.default_rng(11)
    m, n = 60_000, 64
    h = 1.0 / n
    W = np.concatenate([np.zeros((m, 1)), np.cumsum(rng.normal(0, np.sqrt(h), (m, n)), 1)], 1)
    x0, x1 = W[:, :-1], W[:, 1:]
    dx = x1 - x0
    u = ((x0 + x1 + np.sqrt(dx ** 2 - 2 * h * np.log(rng.random((m, n))))) / 2).max(1)
    d = ((x0 + x1 - np.sqrt(dx ** 2 - 2 * h * np.log(rng.random((m, n))))) / 2).min(1)
    a = ((x0 + x1) / 2).sum(1) * h + rng.normal(0, np.sqrt(h ** 3 / 12), (m, n)).sum(1)
    c = W[:, -1]
    b = {"u2": u * u, "d2": d * d, "c2": c * c, "ud": u * d, "uc": u * c, "dc": d * c,
         "a2": a * a, "ac": a * c, "au": a * u, "ad": a * d}
    gkv = sum(w * b[k] for k, w in cal.GK_VWAP_WEIGHTS.items())
    ap = 2 * b["c2"] - 6 * b["ac"] + 6 * b["a2"]
    assert gkv.mean() == pytest.approx(1.0, abs=0.015)
    assert ap.mean() == pytest.approx(1.0, abs=0.03)
    # and GKV is at least as efficient as simplified Garman-Klass
    gk = 0.5 * (u - d) ** 2 - (2 * np.log(2) - 1) * c ** 2
    assert gkv.var() <= gk.var() * 1.01


def test_noise_kernel_is_unbiased_under_iid_endpoint_noise():
    rng = np.random.default_rng(5)
    n = 200_000
    iv, on, vO, vC = 1.0, 0.5, 0.3, 0.2
    eO = rng.normal(0, np.sqrt(vO), n + 1)
    eC = rng.normal(0, np.sqrt(vC), n + 1)
    pin = rng.normal(0, np.sqrt(iv), n + 1)
    pon = rng.normal(0, np.sqrt(on), n + 1)
    c = pin + eC - eO
    o = pon + eO - np.r_[0.0, eC[:-1]]
    K = cal.noise_kernel(pd.Series(c[:-1]), pd.Series(o[:-1]), pd.Series(o[1:]))
    assert (c[:-1] ** 2).mean() == pytest.approx(iv + vO + vC, rel=0.02)
    assert K.mean() == pytest.approx(iv, rel=0.03)


def test_predictable_scale_uses_only_the_past():
    df = pd.DataFrame({"symbol": ["A"] * 40, "date": pd.date_range("2020-01-01", periods=40),
                       "P": np.linspace(1, 2, 40)})
    w = cal.predictable_scale(df, "P", window=5)
    bumped = df.copy()
    bumped.loc[30, "P"] = 1e3
    w2 = cal.predictable_scale(bumped, "P", window=5)
    assert w.loc[30] == pytest.approx(w2.loc[30])


# ---------------------------------------------------------------------------------------------
# The simulator
# ---------------------------------------------------------------------------------------------

def test_microsim_is_reproducible_and_produces_valid_bars():
    a = simulate_panel(n_sec=4, n_days=60, seed=9)
    b = simulate_panel(n_sec=4, n_days=60, seed=9)
    pd.testing.assert_frame_equal(a, b)
    assert ((a.low <= a[["open", "close"]].min(axis=1) + 1e-12)
            & (a.high >= a[["open", "close"]].max(axis=1) - 1e-12)).all()
    assert ((a.vwap >= a.low - 1e-12) & (a.vwap <= a.high + 1e-12)).all()


def test_microsim_trade_times_span_the_session():
    """Regression: a day with fewer trades than the security's busiest day must not inherit the
    smallest order statistics of the busiest day's draws (which bunched its trades at the start
    and cut the measured open-to-close variance)."""
    p = simulate_panel(n_sec=6, n_days=300, seed=2, band=None, limit=None,
                       spread_bp_at_median=0.0, auction_noise_frac=0.0,
                       stale_open_thin=0.0, stale_open_thick=0.0)
    oc = np.log(p.close / p.open) ** 2
    assert oc.mean() / p.iv.mean() == pytest.approx(1.0, abs=0.08)


def test_microsim_band_clamps_the_open():
    p = simulate_panel(n_sec=5, n_days=200, seed=3, band=0.02)
    o = np.log(p.open / p.prev_close).dropna()
    # the band is symmetric in PRICE, so in logs it runs from ln(0.98) to ln(1.02)
    assert ((o >= np.log(0.98) - 1e-12) & (o <= np.log(1.02) + 1e-12)).all()
    assert (o <= np.log(0.98) + 1e-9).any() and (o >= np.log(1.02) - 1e-9).any()


def test_microsim_vwap_tail_close_is_an_average():
    a = simulate_panel(n_sec=4, n_days=100, seed=6)
    b = simulate_panel(n_sec=4, n_days=100, seed=6, close_rule="vwap_tail")
    assert ((b.close >= b.low - 1e-12) & (b.close <= b.high + 1e-12)).all()
    assert not np.allclose(a.close, b.close)
    with pytest.raises(ValueError):
        simulate_panel(n_sec=2, n_days=10, close_rule="midpoint")


def test_bootstrap_returns_finite_slope_draws(lin):
    X = lin[["X0", "X1", "X2"]].to_numpy()
    Z = lin[[c for c in lin.columns if "_L1m" in c]].to_numpy()
    draws = cal.bootstrap_calibration(X, Z, lin["symbol"], lin["date"], ["X0", "X1", "X2"], "X0",
                                      n_boot=5, seed=1)
    assert draws["beta"].shape == (5, 3)
    assert np.isfinite(draws["beta"]).all()
    assert np.allclose(draws["beta"][:, 0], 1.0)
