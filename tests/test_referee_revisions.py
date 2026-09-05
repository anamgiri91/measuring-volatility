"""Regression tests for the referee revisions of 2026-09-02.

Same standard as ``test_audit_invariants.py``: each test fails if a specific defect the referee
report identified -- and which was present in committed results -- comes back. The referee's
own observation applies to this file too: passing tests establish that the code behaves as
programmed, not that the comparison is correctly specified. These therefore test the
SPECIFICATION, not the plumbing: that numerator and denominator describe the same rows, that an
overnight return spans one session, that two reforms keep two dates.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from nepsevol.clean.limits import REGIMES
from nepsevol.estimators import range_ as R
from nepsevol.inference import ratio_of_sums_ci, weighted_stat_ci, weighted_var
from nepsevol.trading_calendar import SCHEDULES, WEEK_REFORM, expected_weekdays
from nepsevol.universe import classify, classify_panel, reconcile

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ── Referee item 5: numerator and denominator must describe the same observations ─────────

def _panel(n=60, seed=0):
    rng = np.random.default_rng(seed)
    o = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    c = o * np.exp(rng.normal(0, 0.01, n))
    h = np.maximum(o, c) * (1 + abs(rng.normal(0, 0.005, n)))
    l = np.minimum(o, c) * (1 - abs(rng.normal(0, 0.005, n)))
    return pd.DataFrame({"date": pd.date_range("2024-03-04", periods=n, freq="D"),
                         "symbol": "AAA", "open": o, "high": h, "low": l, "close": c,
                         "session_ord": np.arange(n)})


def test_unmatched_rows_change_the_ratio_so_matching_is_not_cosmetic():
    """The defect this guards against must be capable of moving the number.

    A test that only asserts the corrected value is passing would also pass if row matching
    were a no-op. Establish first that the two computations genuinely differ.
    """
    d = _panel()
    yz = R.yang_zhang(d, 21)
    cc = np.log(d.close / R.previous_session_close(d)) ** 2
    unmatched = np.sqrt(yz.mean() / cc.mean())
    m = yz.notna() & cc.notna()
    matched = np.sqrt(yz[m].mean() / cc[m].mean())
    assert yz.notna().sum() < cc.notna().sum(), "Yang-Zhang must be the scarcer series"
    assert not np.isclose(unmatched, matched, rtol=1e-6), (
        "row matching made no difference on this fixture, so the test cannot detect the defect")


def test_ratio_is_computed_on_the_intersection_of_numerator_and_denominator():
    """Every ratio must use only rows where BOTH its series are defined."""
    d = _panel()
    yz = R.yang_zhang(d, 21)
    cc = np.log(d.close / R.previous_session_close(d)) ** 2
    m = yz.notna() & cc.notna()
    num = np.where(m, yz.fillna(0), 0.0)
    den = np.where(m, cc.fillna(0), 0.0)
    # the masked sums must have identical support, which is what makes the ratio a ratio
    assert (num != 0).sum() == m.sum()
    assert (den != 0).sum() == m.sum()
    assert np.isclose(np.sqrt(num.sum() / den.sum()),
                      np.sqrt(yz[m].mean() / cc[m].mean()))


def test_shipped_yang_zhang_ratio_uses_fewer_rows_than_parkinson():
    """On the real panel the estimators genuinely differ in support, so the fix binds."""
    tab = ROOT / "output" / "tables" / "table33_estimator_ratios_bootstrap.csv"
    if not tab.exists():
        pytest.skip("run scripts/26_robustness.py first")
    t = pd.read_csv(tab).set_index("estimator")
    assert t.loc["Yang-Zhang", "n_matched_rows"] < t.loc["Parkinson", "n_matched_rows"]
    assert t.loc["Yang-Zhang", "sd_ratio"] > 1.25, (
        "the row-matched Yang-Zhang ratio is ~1.29; a value near 1.245 means the old "
        "unmatched computation has come back")


# ── Referee item 5, second half: an overnight return spans exactly one session ────────────

def test_previous_close_is_nan_across_a_session_gap():
    d = _panel(10)
    d.loc[5:, "session_ord"] += 40           # a 41-session absence before row 5
    prev = R.previous_session_close(d)
    assert pd.isna(prev.iloc[5]), "a gap must not be treated as one overnight return"
    assert not pd.isna(prev.iloc[6]), "a normal transition must survive"


def test_previous_close_equals_shift_when_there_are_no_gaps():
    d = _panel(10)
    assert R.previous_session_close(d).equals(d.close.shift(1))


def test_previous_close_degrades_to_shift_without_a_session_column():
    d = _panel(10).drop(columns="session_ord")
    assert R.previous_session_close(d).equals(d.close.shift(1))


def test_yang_zhang_does_not_span_gaps():
    """A single 91-session gap must not silently inflate the overnight component."""
    clean = _panel(60)
    gapped = clean.copy()
    gapped.loc[30:, "session_ord"] += 90
    assert R.yang_zhang(gapped, 21).notna().sum() < R.yang_zhang(clean, 21).notna().sum()


# ── Referee item 9: two reforms, two dates ───────────────────────────────────────────────

def test_trading_week_and_price_regime_have_different_dates():
    """They were both 2026-04-20; conflating them mis-dates the calendar by two weeks."""
    assert WEEK_REFORM == pd.Timestamp("2026-04-06")
    assert REGIMES[1][0] == pd.Timestamp("2026-04-20")
    assert WEEK_REFORM != REGIMES[1][0]


def test_the_week_between_the_two_reforms_is_mon_fri_under_the_old_price_limit():
    mid = pd.Timestamp("2026-04-13")
    assert "Friday" in expected_weekdays(mid)
    assert "Sunday" not in expected_weekdays(mid)
    limit = [l for start, _, l in REGIMES if mid >= start][-1]
    assert limit == 0.10, "6-19 April traded a Mon-Fri week under the OLD +/-10% limit"


def test_fridays_after_the_week_reform_are_scheduled_sessions():
    for d in ("2026-04-10", "2026-04-17"):
        assert "Friday" in expected_weekdays(pd.Timestamp(d))


def test_last_sunday_session_is_scheduled_and_the_next_is_not():
    assert "Sunday" in expected_weekdays(pd.Timestamp("2026-04-05"))
    assert "Sunday" not in expected_weekdays(pd.Timestamp("2026-04-12"))


def test_shipped_calendar_has_no_off_schedule_sessions_in_the_transition():
    """The four days the wrong boundary mislabelled must now be labelled correctly.

    Note what is NOT asserted: that the window contains no inferred holiday at all. Tuesday
    2026-04-14 is a genuine weekday holiday (Nepali New Year) on which the archive carries the
    previous session forward, and it must stay flagged as one. The defect was specifically that
    weekend days were being read as holidays and Friday sessions as off-schedule.
    """
    cal_path = ROOT / "data" / "processed" / "nepse_trading_calendar.csv"
    if not cal_path.exists():
        pytest.skip("calendar not present")
    cal = pd.read_csv(cal_path, parse_dates=["date"]).set_index("date")
    w = cal.loc["2026-04-06":"2026-04-19"]
    assert not w.off_schedule_session.any(), (
        "a session off the documented schedule in the transition window means the schedule "
        "boundary is wrong again")
    for sunday in ("2026-04-12", "2026-04-19"):
        row = cal.loc[pd.Timestamp(sunday)]
        assert not row.scheduled_session, f"{sunday} is a weekend day under the Mon-Fri week"
        assert not row.inferred_holiday, f"{sunday} is a weekend day, not a holiday"
    for friday in ("2026-04-10", "2026-04-17"):
        row = cal.loc[pd.Timestamp(friday)]
        assert row.scheduled_session and row.is_session, f"{friday} is a scheduled session"
    assert cal.loc[pd.Timestamp("2026-04-14")].inferred_holiday, (
        "a genuine weekday holiday must still be detected")


# ── Referee item 2: the classification must be validated, and the validation must bind ───

def test_security_master_is_shipped_and_covers_the_panel():
    m = ROOT / "data" / "external" / "nepse_security_master.csv"
    assert m.exists(), "the classification audit has nothing to validate against"
    df = pd.read_csv(m)
    assert {"symbol", "sec_type_master"} <= set(df.columns)
    assert df.symbol.is_unique
    assert set(df.sec_type_master) <= {"equity", "debenture", "fund", "promoter", "preference"}


def test_master_overrides_the_rule_on_the_two_known_rule_failures():
    """ADBLB is a bond the ticker rule reads as equity; NADEP an equity it reads as promoter."""
    d = pd.DataFrame({"symbol": ["ADBLB", "NADEP"], "close": [1000.0, 818.3]})
    out = classify_panel(d, root=ROOT)
    got = dict(zip(out.symbol, out.sec_type))
    assert classify("ADBLB", 1000.0) == "equity" and got["ADBLB"] == "debenture"
    assert classify("NADEP", 818.3) == "promoter" and got["NADEP"] == "equity"
    assert set(out.sec_type_source) == {"master"}


def test_rule_and_master_agree_on_the_overwhelming_majority():
    """The AGREEMENT RATE is the evidence for Section 5.1, so it is asserted, not assumed."""
    panel = ROOT / "data" / "processed" / "panel_trades_clean.csv"
    if not panel.exists():
        pytest.skip("panel not present")
    p = pd.read_csv(panel, usecols=["symbol", "close"])
    rec = reconcile(p, root=ROOT)
    matched = rec[rec.in_master]
    assert len(matched) > 500
    assert matched.agrees.mean() > 0.99, (
        "if the rule and an independent listing stop agreeing, the composition result in "
        "Section 5.1 is no longer safe to attribute to instrument type")


def test_equity_sample_contains_no_security_the_master_calls_non_equity():
    eq = ROOT / "data" / "processed" / "equity_sample.csv"
    if not eq.exists():
        pytest.skip("equity sample not built")
    s = pd.read_csv(eq, usecols=["symbol", "sec_type"])
    assert (s.sec_type == "equity").all()
    master = pd.read_csv(ROOT / "data" / "external" / "nepse_security_master.csv")
    bad = set(s.symbol) & set(master.symbol[master.sec_type_master != "equity"])
    assert not bad, f"master says these are not ordinary equity: {sorted(bad)}"


# ── Referee item 14: inference must respect both dependence dimensions ────────────────────

def _clustered(n_sec=40, n_date=60, seed=1):
    """A panel with a genuine common date shock, so date clustering has something to absorb."""
    rng = np.random.default_rng(seed)
    date_shock = rng.normal(0, 1.0, n_date)          # hits every security at once
    sec, dte, num, den = [], [], [], []
    for i in range(n_sec):
        level = rng.normal(0, 0.3)
        for j in range(n_date):
            sec.append(i); dte.append(j)
            base = np.exp(level + date_shock[j])
            den.append(base)
            num.append(base * np.exp(rng.normal(0, 0.05)))
    return np.array(num), np.array(den), np.array(sec), np.array(dte)


def test_two_way_interval_is_wider_than_security_only():
    """The whole point of item 14: ignoring date dependence understates uncertainty."""
    num, den, sec, dte = _clustered()
    lo1, hi1 = ratio_of_sums_ci(num, den, sec, dte, dims=("security",), n_boot=300)
    lo2, hi2 = ratio_of_sums_ci(num, den, sec, dte, dims=("security", "date"), n_boot=300)
    assert (hi2 - lo2) > (hi1 - lo1)


def test_shipped_two_way_intervals_are_wider_than_the_security_only_ones():
    tab = ROOT / "output" / "tables" / "table33_estimator_ratios_bootstrap.csv"
    if not tab.exists():
        pytest.skip("run scripts/26_robustness.py first")
    t = pd.read_csv(tab)
    t = t[t.estimator != "Close-to-close"]           # definitional anchor, zero width
    w_two = t.hi95_twoway - t.lo95_twoway
    w_sec = t.hi95_security_only - t.lo95_security_only
    assert (w_two > w_sec).all(), (
        "a two-way interval can only be at least as wide as a one-way one; a narrower one "
        "means the date dimension is not actually being resampled")


def test_bootstrap_is_reproducible_under_a_fixed_seed():
    num, den, sec, dte = _clustered()
    a = ratio_of_sums_ci(num, den, sec, dte, n_boot=200, seed=7)
    b = ratio_of_sums_ci(num, den, sec, dte, n_boot=200, seed=7)
    assert a == b


def test_interval_brackets_the_point_estimate():
    num, den, sec, dte = _clustered()
    point = np.sqrt(num.sum() / den.sum())
    lo, hi = ratio_of_sums_ci(num, den, sec, dte, n_boot=300)
    assert lo < point < hi


def test_weighted_variance_matches_pandas_at_unit_weights():
    x = np.array([1.0, 4.0, 9.0, 16.0, 25.0])
    assert np.isclose(weighted_var(x, np.ones_like(x)), pd.Series(x).var(ddof=1))


def test_weighted_variance_respects_frequency_weights():
    """Weight 2 must equal duplicating the observation, or the resample is not a resample."""
    x = np.array([1.0, 4.0, 9.0])
    w = np.array([2.0, 1.0, 1.0])
    assert np.isclose(weighted_var(x, w), pd.Series([1.0, 1.0, 4.0, 9.0]).var(ddof=1))


def test_weighted_stat_ci_runs_on_a_variance_statistic():
    num, den, sec, dte = _clustered(n_sec=15, n_date=20)
    f = pd.DataFrame({"num": num, "den": den})
    lo, hi = weighted_stat_ci(
        lambda fr, w: (w * fr["num"]).sum() / w.sum() / weighted_var(fr["den"].to_numpy(), w),
        f, sec=sec, date=dte, n_boot=100)
    assert np.isfinite(lo) and np.isfinite(hi) and lo < hi


# ── Referee items 4 and 15: the package and the manuscript must not contradict ────────────

def test_every_manuscript_table_named_by_the_map_has_a_frozen_output():
    m = pd.read_csv(ROOT / "REPRODUCIBILITY_MAP.csv")
    missing = []
    for _, r in m.iterrows():
        for out in str(r["Frozen output"]).split(";"):
            out = out.strip()
            if out and not out.endswith("/") and "*" not in out:
                if not (ROOT / out).exists():
                    missing.append((r["Manuscript item"], out))
    assert not missing, f"map names outputs that do not exist: {missing}"


def test_every_producer_named_by_the_map_exists():
    m = pd.read_csv(ROOT / "REPRODUCIBILITY_MAP.csv")
    missing = []
    for _, r in m.iterrows():
        for prod in str(r["Producer"]).replace(";", ",").split(","):
            prod = prod.split("(")[0].strip()
            if prod.endswith(".py") and not (ROOT / "scripts" / prod).exists():
                missing.append((r["Manuscript item"], prod))
    assert not missing, f"map names producers that do not exist: {missing}"


def test_run_script_executes_every_paper_facing_producer():
    """A script the map calls a producer but the runner never runs cannot have been used."""
    run = (ROOT / "run_paper_analysis.sh").read_text()
    m = pd.read_csv(ROOT / "REPRODUCIBILITY_MAP.csv")
    named = set()
    for _, r in m.iterrows():
        for prod in str(r["Producer"]).replace(";", ",").split(","):
            prod = prod.split("(")[0].strip()
            if prod.endswith(".py"):
                named.add(prod)
    named -= {"02_build_panel.py"}       # needs raw inputs, not redistributed
    assert not (named - set(run.split())), f"not run by run_paper_analysis.sh: {named - set(run.split())}"


# ── Referee item 1: conflict-freedom must be demonstrated, not assumed ────────────────────

def test_daily_trades_duplicate_audit_is_shipped_and_explicit():
    p = ROOT / "data" / "processed" / "audit" / "panel_trades_duplicate_audit.csv"
    assert p.exists(), "the audit referee item 1 asks for must be in the package"
    a = pd.read_csv(p).set_index("class")["duplicate_keys"]
    for cls in ("EXACT_DUPLICATE", "CONFLICTING_OHLC", "CONFLICTING_VOLUME",
                "CONFLICTING_TRADES"):
        assert cls in a.index, f"{cls} must be listed even when zero, or absence proves nothing"
    assert a["KEYS_EXAMINED"] == a["ROWS_EXAMINED"], (
        "one row per key is what 'no duplicated security-days' means")
    assert int(a[["CONFLICTING_OHLC", "CONFLICTING_VOLUME", "CONFLICTING_TRADES"]].sum()) == 0
