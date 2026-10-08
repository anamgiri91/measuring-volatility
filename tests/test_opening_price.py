"""Tests for the M15 opening-price statistics (nepsevol.opening) and the simulator's rule switch.

They check, where the truth is known, what M15_OPENING_PRICE_ANALYSIS_PLAN.md requires before
the statistics touch the data: that the unbiasedness coefficient is one without frictions, falls
below one by exactly the transient opening error's share of the overnight variance, and rises
above one for opens a band censors; that the event-window and dose-response statistics respond
to a band-widening switch and not to its absence; and that the Yang-Zhang gap decomposes exactly.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nepsevol import opening as op  # noqa: E402
from nepsevol.estimators import range_ as R  # noqa: E402
from nepsevol.estimators.microsim import simulate_panel  # noqa: E402

# The NEPSE-like scenario of scripts/35 (descriptive inputs only): ~20% of opens pinned at +/-2%.
NEPSE = dict(sigma_median=0.024, sigma_disp=0.51, theta=0.6, trades_median=168.0,
             trades_disp=0.97, spread_bp_at_median=40.0, auction_noise_frac=0.25,
             band=0.02, limit=0.10, stale_open_thin=0.25, stale_open_thick=0.02)
NO_FRICTIONS = dict(trades_median=1000.0, trades_disp=0.0, gamma=0.0, spread_bp_at_median=0.0,
                    auction_noise_frac=0.0, band=None, limit=None, stale_open_thin=0.0,
                    stale_open_thick=0.0)
SWITCH_DAY, N_DAYS = 130, 260


def prep(panel: pd.DataFrame) -> pd.DataFrame:
    s = panel.sort_values(["symbol", "date"]).reset_index(drop=True)
    return pd.concat([s, op.opening_coordinates(s, s["prev_close"])], axis=1)


def b_of(s, mask=None):
    return op.unbiasedness(s["o"], s["r"], mask=mask)


@pytest.fixture(scope="module")
def frictionless():
    return prep(simulate_panel(n_sec=60, n_days=300, seed=1, **NO_FRICTIONS))


@pytest.fixture(scope="module")
def noisy_open():
    return prep(simulate_panel(n_sec=60, n_days=300, seed=1, band=None, limit=None,
                               stale_open_thin=0.0, stale_open_thick=0.0, auction_noise_frac=1.0))


@pytest.fixture(scope="module")
def switch_pair():
    """The same NEPSE-like panel with and without a band-widening switch on day 130."""
    out = {}
    for label, sw in [("switch", SWITCH_DAY), ("none", None)]:
        out[label] = [prep(simulate_panel(n_sec=120, n_days=N_DAYS, seed=seed, switch_day=sw,
                                          auction_noise_frac_post=1.0, **NEPSE))
                      for seed in (1, 2, 3)]
    return out


# ---------------------------------------------------------------------------------------------
# The unbiasedness coefficient where the truth is known
# ---------------------------------------------------------------------------------------------

def test_open_is_unbiased_for_the_close_without_frictions(frictionless):
    assert b_of(frictionless) == pytest.approx(1.0, abs=0.05)


def test_transient_open_error_lowers_b_by_its_share_of_overnight_variance(noisy_open):
    s = noisy_open
    ok = s["o"].notna()
    true_share = float((s.loc[ok, "open_err"] ** 2).mean() / (s.loc[ok, "o"] ** 2).mean())
    assert true_share > 0.3                              # the scenario has a large error
    assert 1.0 - b_of(s) == pytest.approx(true_share, abs=0.04)


def test_band_pinned_opens_underreact_and_interior_opens_do_not():
    s = prep(simulate_panel(n_sec=60, n_days=300, seed=3, band=0.02, auction_noise_frac=0.1,
                            stale_open_thin=0.0, stale_open_thick=0.0))
    z = op.zone_labels(s["g"], 0.02)
    assert (z == "pinned").mean() > 0.05
    assert b_of(s, z == "pinned") > 1.15
    assert b_of(s, z == "interior") == pytest.approx(1.0, abs=0.06)


def test_b_is_invariant_to_stale_opens(noisy_open):
    s = noisy_open.dropna(subset=["o", "r"])
    stale = pd.DataFrame({"o": np.zeros(5000), "r": np.random.default_rng(0).normal(0, 0.02, 5000)})
    both = pd.concat([s[["o", "r"]], stale], ignore_index=True)
    assert b_of(both) == pytest.approx(b_of(s), rel=1e-12)


# ---------------------------------------------------------------------------------------------
# Zones, windows and groups
# ---------------------------------------------------------------------------------------------

def test_zone_labels_use_simple_returns_and_the_band_in_force():
    g = np.array([0.0, 0.005, -0.0185, 0.0191, -0.02, 0.03, -0.0489, 0.05, -0.05, np.nan])
    old = op.zone_labels(g, 0.02)
    assert list(old) == ["stale", "interior", "interior", "pinned", "pinned", "pinned",
                         "pinned", "pinned", "pinned", ""]
    new = op.zone_labels(g, 0.05)
    assert list(new) == ["stale", "interior", "interior", "old-band zone", "old-band zone",
                         "old-band zone", "old-band zone", "pinned", "pinned", ""]
    # a -5% open is -0.0513 in logs, beyond ln(1.05): a log rule would misfile it as beyond the band
    assert abs(np.log(0.95)) > np.log(1.05)


def test_band_in_force_switches_on_the_reform_date():
    b = op.band_in_force(["2026-04-17", "2026-04-19", "2026-04-20", "2026-08-26"])
    assert list(b) == [0.02, 0.02, 0.05, 0.05]


def test_event_windows_exclude_the_inter_reform_sessions():
    cal = pd.bdate_range("2026-01-01", "2026-07-31")
    w = op.event_windows(cal, length=40)
    assert len(w["pre"]) == len(w["post"]) == 40
    assert w["pre"].max() < op.WEEK_REFORM <= w["gap"].min()
    assert w["gap"].max() < op.BAND_REFORM == w["post"].min()
    assert not set(w["gap"]) & (set(w["pre"]) | set(w["post"]))


def test_placebo_windows_have_the_actual_geometry():
    cal = pd.bdate_range("2024-01-01", periods=200)
    pl = op.placebo_windows(cal, length=40, gap=9, step=5)
    assert len(pl) == (200 - 89) // 5 + 1
    for d0, pre, post in pl:
        assert len(pre) == len(post) == 40 and post[0] == d0
        i_pre, i_post = cal.get_loc(pre[-1]), cal.get_loc(post[0])
        assert i_post - i_pre - 1 == 9


def test_intensity_groups_are_equal_count_even_with_ties():
    share = pd.Series([0.2] * 10 + [0.3] * 5, index=[f"S{i}" for i in range(15)])
    g = op.intensity_groups(share)
    assert g.value_counts().tolist() == [5, 5, 5]
    assert set(g[share == 0.3]) == {"T3"}


# ---------------------------------------------------------------------------------------------
# H7 and H8 where the switch is known
# ---------------------------------------------------------------------------------------------

def _event_stat(s):
    cal = pd.DatetimeIndex(np.sort(s["date"].unique()))
    w = op.event_windows(cal, post_start=cal[SWITCH_DAY], pre_end_before=cal[SWITCH_DAY - 9])
    db = b_of(s, s["date"].isin(w["post"])) - b_of(s, s["date"].isin(w["pre"]))
    plac = np.array([b_of(s, s["date"].isin(po)) - b_of(s, s["date"].isin(pr))
                     for _, pr, po in op.placebo_windows(cal[cal < cal[SWITCH_DAY - 9]])])
    return db, plac


def test_event_window_detects_the_switch_and_placebos_centre_on_zero(switch_pair):
    """Within one short simulated panel the placebo windows overlap heavily and share volatility
    episodes, so their spread understates the sampling variability of a single Delta-b (the
    no-switch Delta-b varies with sd ~0.14 across seeds, the within-panel placebos with sd ~0.05).
    Centring is therefore checked on the mean across seeds; the real data's ~80 placebos span two
    years, and H7 also requires the bootstrap interval, so it does not rest on the rank alone."""
    placebo_means, null_db = [], []
    for sw, none in zip(switch_pair["switch"], switch_pair["none"]):
        db_sw, plac = _event_stat(sw)
        db_none, plac_none = _event_stat(none)
        np.testing.assert_allclose(plac, plac_none)      # the pre-switch panel is identical
        assert db_sw < plac.min() and db_sw < -0.3
        assert db_sw - db_none < -0.3
        placebo_means.append(plac.mean())
        null_db.append(db_none)
    assert abs(np.mean(placebo_means)) < 0.08
    assert abs(np.mean(null_db)) < 0.15


def _did(s):
    early = s[(s["day"] < 50) & s["o"].notna()]
    share = (early["g"].abs() >= op.OLD_BAND - op.PIN_TOL).groupby(early["symbol"]).mean()
    t = s["symbol"].map(op.intensity_groups(share))
    pre = (s["day"] >= 50) & (s["day"] < SWITCH_DAY - 9)
    post = s["day"] >= SWITCH_DAY
    h1 = pre & (s["day"] < 85)
    h2 = pre & (s["day"] >= 85)

    def d(a, b):
        return ((b_of(s, b & (t == "T3")) - b_of(s, a & (t == "T3")))
                - (b_of(s, b & (t == "T1")) - b_of(s, a & (t == "T1"))))
    return d(pre, post), d(h1, h2)


def test_dose_response_falls_with_the_switch_and_its_placebo_does_not_move(switch_pair):
    for sw, none in zip(switch_pair["switch"], switch_pair["none"]):
        did_sw, placebo_sw = _did(sw)
        did_none, placebo_none = _did(none)
        assert did_sw < 0
        assert did_sw < did_none                         # paired: same seed, same pre-period
        assert placebo_sw == pytest.approx(placebo_none)


# ---------------------------------------------------------------------------------------------
# H11: the Yang-Zhang identity
# ---------------------------------------------------------------------------------------------

def test_yang_zhang_gap_decomposes_exactly(noisy_open):
    s = noisy_open
    parts = []
    for _, g in s.groupby("symbol", sort=False):
        comp = op.yang_zhang_components(g["o"], g["c"], R.rogers_satchell(g))
        comp["yz_package"] = R.yang_zhang(g, 21, prev_close=g["prev_close"])
        parts.append(comp)
    y = pd.concat(parts).dropna()
    assert len(y) > 1000
    np.testing.assert_allclose(y["yz"], y["yz_package"], rtol=1e-10, atol=1e-16)
    np.testing.assert_allclose(y["yz"] - y["var_r"], y["rs_term"] + y["cov_term"],
                               rtol=1e-8, atol=1e-14)
    # with a transient opening error the covariance term is the larger part of the gap
    assert y["cov_term"].mean() > 0 and y["yz"].mean() > y["var_r"].mean()


# ---------------------------------------------------------------------------------------------
# The simulator's switch
# ---------------------------------------------------------------------------------------------

def test_switch_changes_only_the_days_after_it():
    a = simulate_panel(n_sec=5, n_days=80, seed=7, **NEPSE)
    b = simulate_panel(n_sec=5, n_days=80, seed=7, switch_day=40, auction_noise_frac_post=1.0,
                       **NEPSE)
    before = a["day"] < 40
    cols = ["open", "high", "low", "close", "vwap", "n_trades", "prev_close"]
    pd.testing.assert_frame_equal(a.loc[before, cols], b.loc[before, cols])
    g_post = (b["open"] / b["prev_close"] - 1)[b["post_switch"]].abs()
    g_pre = (b["open"] / b["prev_close"] - 1)[~b["post_switch"]].abs()
    assert g_pre.max() <= 0.02 + 1e-12 and g_post.max() <= 0.05 + 1e-12
    assert g_post.max() > 0.02
