"""Regression tests for the defects the 2026-08-28 audit found.

These are not "does the function run" tests. Each one fails if a specific error that
actually occurred in this project -- and in several cases survived into committed results
-- comes back. Audit policy SS21: tests must target scientific failures.
"""

from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from nepsevol.clean.ohlc import (
    CLEANING_ORDER, classify_duplicates, ohlc_violations, repair_audit_table,
    repair_ohlc, resolve_duplicate_keys,
)
from nepsevol.clean.special_sessions import is_special_session, status_of
from nepsevol.validate import SampleValidationError, validate_analysis_sample
from nepsevol.estimators import range_ as R
from nepsevol.estimators.ratios import as_sd, as_var, assert_same_scale, sd_ratio, variance_ratio


def _bars(o, h, l, c):
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, dtype=float)


# --- A-002: the PAP SS3.1 repair was declared mandatory and never implemented -----------

def test_repair_enforces_ohlc_envelope():
    """H >= max(O,C) and L <= min(O,C) after repair, on deliberately broken bars."""
    d = _bars([10, 10, 10], [9, 12, 10], [11, 8, 10], [11, 11, 10])
    out = repair_ohlc(d)
    assert (out.high >= out[["open", "close"]].max(axis=1)).all()
    assert (out.low <= out[["open", "close"]].min(axis=1)).all()
    assert (out.high >= out.low).all()


def test_repair_is_idempotent_and_preserves_originals():
    d = _bars([10, 10], [9, 12], [11, 8], [11, 11])
    once = repair_ohlc(d)
    assert repair_ohlc(once).equals(once)
    for col in ("open", "high", "low", "close"):
        assert (once[f"{col}_original"] == d[col]).all()


def test_repair_emits_a_provenance_record_for_every_change():
    """No bar may be silently mutated -- field, old value, new value, reason."""
    d = pd.DataFrame({
        "symbol": ["A", "B"], "date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
        "open": [10.0, 10.0], "high": [9.0, 12.0], "low": [11.0, 9.0], "close": [11.0, 11.0],
    })
    audit = repair_audit_table(repair_ohlc(d))
    assert set(audit.columns) >= {"symbol", "date", "field", "old_value", "new_value", "reason"}
    assert set(audit.field) == {"high", "low"}          # A had both extrema wrong
    assert (audit.symbol == "A").all()                  # B was already conforming
    row = audit[audit.field == "high"].iloc[0]
    assert row.old_value == 9.0 and row.new_value == 11.0


def test_repair_leaves_conforming_rows_bit_identical():
    d = _bars([10], [12], [9], [11])
    out = repair_ohlc(d)
    assert out.high.iloc[0] == 12 and out.low.iloc[0] == 9
    assert not out.ohlc_repaired.iloc[0]


def test_no_negative_log_range_survives_repair():
    """ln(H/L) < 0 is impossible; two such rows reached the committed analysis sample."""
    d = _bars([10, 10], [9, 8], [11, 12], [11, 9])
    out = repair_ohlc(d)
    assert (np.log(out.high / out.low) >= 0).all()


# --- A-032: negative GK/RS are a data defect, not an estimator property -----------------

def test_gk_and_rs_nonnegative_on_valid_bars():
    """A negative value means invalid OHLC upstream. Proof in the GK docstring."""
    rng = np.random.default_rng(0)
    o = 100 + rng.normal(0, 5, 3000)
    c = o + rng.normal(0, 3, 3000)
    h = np.maximum(o, c) + np.abs(rng.normal(0, 2, 3000))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 2, 3000))
    d = _bars(o, h, l, c)
    assert (R.garman_klass(d) >= 0).all()
    assert (R.rogers_satchell(d) >= 0).all()


def test_gk_lower_bound_is_tight():
    """GK >= (1.5 - 2 ln2) * ln(C/O)^2, attained when the range equals the O-C move."""
    d = _bars([100.0], [110.0], [100.0], [110.0])   # H = C, L = O
    k = np.log(110 / 100)
    assert R.garman_klass(d).iloc[0] == pytest.approx((1.5 - 2 * np.log(2)) * k**2, rel=1e-12)


# --- A-022: an observation is a security-day ------------------------------------------

def test_duplicate_keys_collapsed_and_conflicts_dropped():
    d = pd.DataFrame({
        "symbol": ["A", "A", "B", "B", "C"],
        "date": pd.to_datetime(["2020-01-01"] * 4 + ["2020-01-02"]),
        "open": [10, 10, 10, 10, 10.0], "high": [12, 12, 12, 13, 12.0],
        "low": [9, 9, 9, 9, 9.0], "close": [11, 11, 11, 11, 11.0],
        "volume": [1, 1, 1, 2, 1], "turnover": [1, 1, 1, 2, 1],
    })
    out = resolve_duplicate_keys(d, verbose=False)
    assert not out.duplicated(["symbol", "date"]).any()
    assert set(out.symbol) == {"A", "C"}          # A exact -> collapsed, B conflicting -> dropped


# --- A-038: SD and variance ratios must never be silently compared ---------------------

def test_sd_ratio_is_sqrt_of_var_ratio():
    num, den = pd.Series([0.04, 0.04]), pd.Series([0.16, 0.16])
    v, vs = variance_ratio(num, den)
    s, ss = sd_ratio(num, den)
    assert (vs, ss) == ("variance", "sd")
    assert s == pytest.approx(np.sqrt(v))


def test_comparing_mismatched_scales_raises():
    with pytest.raises(ValueError, match="different scales"):
        assert_same_scale((0.965, "variance"), (0.980, "sd"))


def test_scale_conversion_round_trips():
    assert as_var(as_sd(0.96, "variance"), "sd") == pytest.approx(0.96)


# --- AddRS: the identity that the whole Result-2 argument rests on ---------------------

def test_addrs_identity_holds():
    """AddRS - RS = (x^2/2)(I_u + I_v), exactly."""
    rng = np.random.default_rng(1)
    o = 100 + rng.normal(0, 5, 2000)
    c = o + rng.normal(0, 3, 2000)
    h = np.maximum(o, c) + np.abs(rng.normal(0, 2, 2000))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 2, 2000))
    # force boundary cases so the indicators actually fire
    h[:400] = np.maximum(o, c)[:400]
    l[400:800] = np.minimum(o, c)[400:800]
    d = _bars(o, h, l, c)
    x2 = np.log(d.close / d.open) ** 2
    iu = ((d.high - d.open).abs() <= 1e-12 * d.open.abs()) | ((d.close - d.high).abs() <= 1e-12 * d.high.abs())
    iv = ((d.low - d.open).abs() <= 1e-12 * d.open.abs()) | ((d.close - d.low).abs() <= 1e-12 * d.low.abs())
    expected = (x2 / 2) * (iu.astype(float) + iv.astype(float))
    assert np.allclose(R.add_rs(d) - R.rogers_satchell(d), expected, atol=1e-15)


def test_addrs_correction_is_nonnegative_not_strictly_positive():
    """Exactly zero when no indicator fires -- the manuscript said 'strictly positive'."""
    d = _bars([100.0], [110.0], [90.0], [105.0])   # interior close, no boundary equality
    assert (R.add_rs(d) - R.rogers_satchell(d)).iloc[0] == pytest.approx(0.0, abs=1e-18)


# --- date handling: dayfirst=True on ISO dates produced a plausible wrong answer -------

def test_iso_dates_are_not_month_day_swapped():
    raw = ["2026-06-12", "2026-07-25", "2010-01-04"]
    parsed = pd.to_datetime(pd.Series(raw), format="%Y-%m-%d")
    assert parsed.max().month == 7 and parsed.max().day == 25
    assert parsed.min() == pd.Timestamp("2010-01-04")


def test_panel_ordering_invariant():
    d = pd.DataFrame({"symbol": ["A"] * 3, "date": pd.to_datetime(["2020-01-03", "2020-01-01", "2020-01-02"])})
    s = d.sort_values(["symbol", "date"])
    assert s.date.is_monotonic_increasing


# --- A-022 continued: duplicate CLASSES, and order must not decide the science ---------

def test_duplicate_classes_are_distinguished():
    d = pd.DataFrame({
        "symbol": ["A", "A", "B", "B", "C", "C"],
        "date": pd.to_datetime(["2020-01-01"] * 6),
        "open": [10, 10, 10, 10, 10, 10.0], "high": [12, 12, 12, 13, 12, 12.0],
        "low": [9, 9, 9, 9, 9, 9.0], "close": [11, 11, 11, 11, 11, 11.0],
        "volume": [1, 1, 5, 5, 1, 2], "turnover": [1, 1, 5, 5, 1, 2],
    })
    lab = classify_duplicates(d)
    assert lab[("A", pd.Timestamp("2020-01-01"))] == "EXACT_DUPLICATE"
    assert lab[("B", pd.Timestamp("2020-01-01"))] == "CONFLICTING_OHLC"
    assert lab[("C", pd.Timestamp("2020-01-01"))] == "CONFLICTING_VOLUME"


def test_duplicate_resolution_is_order_independent():
    """Reversing source row order must not change which rows survive."""
    d = pd.DataFrame({
        "symbol": ["A", "A", "B", "B", "C"],
        "date": pd.to_datetime(["2020-01-01"] * 4 + ["2020-01-02"]),
        "open": [10, 10, 10, 10, 10.0], "high": [12, 12, 12, 13, 12.0],
        "low": [9, 9, 9, 9, 9.0], "close": [11, 11, 11, 11, 11.0],
        "volume": [1, 1, 1, 2, 1], "turnover": [1, 1, 1, 2, 1],
    })
    fwd = resolve_duplicate_keys(d, verbose=False)
    rev = resolve_duplicate_keys(d.iloc[::-1].reset_index(drop=True), verbose=False)
    pd.testing.assert_frame_equal(fwd, rev)


# --- SS9: special sessions are an explicit allowlist, never a blanket weekday rule -----

def test_special_session_is_explicit_not_a_blanket_saturday_rule():
    assert is_special_session("2026-07-25")
    assert status_of("2026-07-25") == "PROVISIONAL"
    # any other Saturday must NOT be admitted merely for being a Saturday
    assert not is_special_session("2026-07-18")
    assert status_of("2026-07-18") is None


# --- SS8: the pipeline must STOP, not warn -------------------------------------------

def test_validator_rejects_broken_envelope():
    d = _bars([10.0], [9.0], [11.0], [11.0])
    with pytest.raises(SampleValidationError, match="high < max"):
        validate_analysis_sample(d, universe="full", expect_sec_type=False)


def test_validator_rejects_non_equity_in_equity_sample():
    d = _bars([10.0, 10.0], [12.0, 12.0], [9.0, 9.0], [11.0, 11.0])
    d["sec_type"] = ["equity", "debenture"]
    with pytest.raises(SampleValidationError, match="non-equity"):
        validate_analysis_sample(d, universe="equity")


def test_validator_rejects_duplicate_security_days():
    d = _bars([10.0, 10.0], [12.0, 12.0], [9.0, 9.0], [11.0, 11.0])
    d["symbol"] = ["A", "A"]
    d["date"] = pd.to_datetime(["2020-01-01", "2020-01-01"])
    d["sec_type"] = "equity"
    with pytest.raises(SampleValidationError, match="duplicated"):
        validate_analysis_sample(d, universe="equity")


def test_validator_passes_a_clean_sample():
    d = _bars([10.0, 10.0], [12.0, 12.5], [9.0, 9.5], [11.0, 11.5])
    d["symbol"] = ["A", "B"]
    d["date"] = pd.to_datetime(["2020-01-01", "2020-01-01"])
    d["sec_type"] = "equity"
    validate_analysis_sample(d, universe="equity")       # must not raise


# --- SS12: no active scientific script may reopen the mixed universe directly ----------

def test_no_active_script_reads_the_mixed_universe_directly():
    """Scripts 04-20 each did exactly this, so D-0012's universe decision never took effect.

    In this GitHub subset, only 03 (which writes it) and 22 (the composition result, which
    legitimately needs it) may name the mixed-universe file.
    """
    scripts = pathlib.Path(__file__).resolve().parents[1] / "scripts"
    allowed = {"03_descriptive.py", "22_universe_composition.py"}
    offenders = [
        f.name for f in sorted(scripts.glob("*.py"))
        if f.name not in allowed and "analysis_sample.csv" in f.read_text()
    ]
    assert not offenders, f"scripts bypassing load_sample(): {offenders}"


# --- A-005: an accounting identity must close, or its components are not interpretable --

def test_variance_decomposition_closes():
    """Var(cc) = Var(co) + Var(oc) + 2Cov(co,oc), and all four must use the SAME rows.

    The shipped script computed r_oc on every row while r_cc and r_on were restricted to
    consecutive sessions, so the identity missed by up to 11% on panel data.
    """
    rng = np.random.default_rng(5)
    co = rng.normal(0, 0.01, 5000)
    oc = rng.normal(0, 0.02, 5000) - 0.3 * co
    cc = co + oc
    lhs = np.var(cc, ddof=1)
    rhs = np.var(co, ddof=1) + np.var(oc, ddof=1) + 2 * np.cov(co, oc, ddof=1)[0, 1]
    assert lhs == pytest.approx(rhs, rel=1e-10)


def test_decomposition_breaks_when_samples_differ():
    """Guards the specific bug: computing one component on a different subset."""
    rng = np.random.default_rng(6)
    co = rng.normal(0, 0.01, 4000)
    oc = rng.normal(0, 0.02, 4000)
    cc = co + oc
    mask = np.arange(4000) % 3 != 0          # r_oc on all rows, the rest on a subset
    bad = np.var(co[mask], ddof=1) + np.var(oc, ddof=1) + 2 * np.cov(co[mask], oc[mask], ddof=1)[0, 1]
    assert abs(bad / np.var(cc[mask], ddof=1) - 1) > 1e-6


# --- SS5: NaN semantics. nunique() drops NaN, which would hide a real conflict ----------

def _dup(sym, **cols):
    n = len(next(iter(cols.values())))
    base = {"symbol": [sym] * n, "date": pd.to_datetime(["2020-01-01"] * n),
            "open": [10.0] * n, "high": [12.0] * n, "low": [9.0] * n, "close": [11.0] * n,
            "volume": [1.0] * n, "turnover": [1.0] * n, "n_trades": [5.0] * n}
    base.update(cols)
    return pd.DataFrame(base)


def test_nan_versus_nan_is_an_exact_duplicate():
    d = _dup("A", n_trades=[np.nan, np.nan])
    assert classify_duplicates(d).iloc[0] == "EXACT_DUPLICATE"


def test_nan_versus_value_is_a_conflict_not_an_exact_duplicate():
    """The bug this guards: nunique() ignores NaN, so (NaN, 10) looks like one value."""
    d = _dup("A", n_trades=[np.nan, 10.0])
    assert classify_duplicates(d).iloc[0] == "CONFLICTING_TRADES"


def test_value_versus_different_value_is_a_conflict():
    d = _dup("A", n_trades=[5.0, 10.0])
    assert classify_duplicates(d).iloc[0] == "CONFLICTING_TRADES"


def test_conflict_precedence_is_deterministic_not_evaluation_order():
    """A key conflicting on several dimensions takes the most severe class."""
    d = _dup("A", high=[12.0, 13.0], volume=[1.0, 2.0], n_trades=[5.0, 9.0])
    assert classify_duplicates(d).iloc[0] == "CONFLICTING_OHLC"
    d2 = _dup("A", volume=[1.0, 2.0], n_trades=[5.0, 9.0])
    assert classify_duplicates(d2).iloc[0] == "CONFLICTING_VOLUME"


# --- SS6: row order must have zero scientific effect, for EVERY class ------------------

def test_row_order_has_no_effect_on_any_duplicate_class():
    frames = [
        _dup("A", n_trades=[5.0, 5.0]),            # exact
        _dup("B", high=[12.0, 13.0]),              # OHLC conflict
        _dup("C", volume=[1.0, 2.0]),              # volume conflict
        _dup("D", n_trades=[5.0, 9.0]),            # trades conflict
        _dup("E", high=[12.0, 13.0], volume=[1.0, 2.0]),   # simultaneous
    ]
    d = pd.concat(frames, ignore_index=True)
    canonical = resolve_duplicate_keys(d, verbose=False)
    labels = classify_duplicates(d)
    rng = np.random.default_rng(0)
    for _ in range(8):
        shuffled = d.sample(frac=1.0, random_state=int(rng.integers(1e6))).reset_index(drop=True)
        pd.testing.assert_frame_equal(resolve_duplicate_keys(shuffled, verbose=False), canonical)
        pd.testing.assert_series_equal(classify_duplicates(shuffled), labels)


# --- SS15: conflict detection must run on ORIGINAL values, before repair ---------------

def test_repair_before_dedup_would_mask_a_conflict():
    """Two conflicting bars can become identical after repair. Order is therefore fixed."""
    d = pd.DataFrame({
        "symbol": ["A", "A"], "date": pd.to_datetime(["2020-01-01"] * 2),
        "open": [10.0, 10.0], "high": [9.0, 8.0],      # both below max(O,C) -> both repaired to 11
        "low": [9.0, 9.0], "close": [11.0, 11.0],
        "volume": [1.0, 1.0], "turnover": [1.0, 1.0],
    })
    assert classify_duplicates(d).iloc[0] == "CONFLICTING_OHLC"      # correct order
    masked = classify_duplicates(repair_ohlc(d))                      # wrong order
    assert masked.iloc[0] == "EXACT_DUPLICATE"                        # conflict hidden
    assert CLEANING_ORDER[1].startswith("2. duplicate-key resolution ON ORIGINAL VALUES")


# --- SS16: mutation-style end-to-end checks -------------------------------------------

def test_pipeline_halts_on_each_injected_defect():
    good = pd.DataFrame({
        "symbol": ["A", "B"], "date": pd.to_datetime(["2020-01-01", "2020-01-01"]),
        "open": [10.0, 10.0], "high": [12.0, 12.0], "low": [9.0, 9.0],
        "close": [11.0, 11.0], "sec_type": ["equity", "equity"],
    })
    validate_analysis_sample(good, universe="equity")                 # baseline passes

    cases = {
        "high < max(O,C)": lambda d: d.assign(high=[9.0, 12.0]),
        "low > min(O,C)":  lambda d: d.assign(low=[11.0, 9.0]),
        "zero price":      lambda d: d.assign(close=[0.0, 11.0]),
        "negative price":  lambda d: d.assign(open=[-1.0, 10.0]),
        "non-equity":      lambda d: d.assign(sec_type=["equity", "debenture"]),
        "duplicate key":   lambda d: d.assign(symbol=["A", "A"]),
    }
    for name, mutate in cases.items():
        with pytest.raises(SampleValidationError):
            validate_analysis_sample(mutate(good.copy()), universe="equity")


# --- simulation: the DGP has its own ceiling, and it must be documented not absorbed ----

def test_simulation_ceiling_is_explicit_not_hidden_in_a_tolerance():
    """The latent path is itself discretised, so even dense observation cannot recover sigma.

    With fine_steps = 2000, observing every step still gives Parkinson/true ~= 0.97, not 1.00,
    because the 'true' range is the range of a 2000-step walk rather than of a continuous path.
    The existing recovery test passes only because its tolerance is loose enough to absorb this.
    Pinning the ceiling here means a future change to fine_steps shows up as a failure rather
    than silently shifting every simulated bias curve.
    """
    from nepsevol.estimators.simulate import simulate_observed_ohlc
    true_sigma = 0.02
    df = simulate_observed_ohlc(1500, true_sigma, 4000, noise_sd=0.0, seed=11)
    ratio = np.sqrt(R.parkinson(df).mean()) / true_sigma
    assert 0.95 < ratio < 1.0, f"dense-observation ceiling moved: {ratio:.4f}"


def test_simulated_bias_ratio_is_scale_free_in_sigma():
    """If it were not, the arbitrary choice of TRUE_SIGMA = 0.02 would matter."""
    from nepsevol.estimators.simulate import simulate_observed_ohlc
    ratios = []
    for s in (0.005, 0.02, 0.08):
        df = simulate_observed_ohlc(1200, s, 10, noise_sd=0.0, seed=7)
        ratios.append(np.sqrt(R.parkinson(df).mean()) / s)
    assert max(ratios) - min(ratios) < 1e-9, ratios
