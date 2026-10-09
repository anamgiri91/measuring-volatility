"""The corrected forecast evaluation (``anam_estimator.evaluation``) and the model built on it.

The first six tests are the failure modes the 9 October 2026 audit found in version 0.1.0 and in the
paper's original evaluation; each would fail on the old code. The rest check the target, the inference and
the model confidence set against independent, brute-force calculations rather than against the code they
test.
"""
import numpy as np
import pandas as pd
import pytest

from anam_estimator import AnamModel, extended_range, kernel, simulate_bars
from anam_estimator.evaluation import (forward_target, model_confidence_set, purged, qlike_canonical,
                                       qlike_normalized, select_by_loss, session_ordinal, weighted_mean_se)


# ── 1. nothing after the cutoff can change a model fitted before it (audit A01) ───────────────────────

def test_returns_after_the_cutoff_cannot_change_the_fitted_phi(panel):
    cut = panel["date"].sort_values().unique()[300]
    base = AnamModel(form="full", horizon=5).fit(panel, train_end=cut)
    rng = np.random.default_rng(1)
    shocked = panel.copy()
    late = shocked["date"] >= cut
    scale = np.exp(rng.normal(0, 0.5, late.sum()))[:, None]
    shocked.loc[late, ["open", "high", "low", "close"]] = shocked.loc[late, ["open", "high", "low", "close"]] * scale
    for h in (5, 21):
        a = AnamModel(form="full", horizon=h).fit(panel, train_end=cut)
        b = AnamModel(form="full", horizon=h).fit(shocked, train_end=cut)
        assert a.phi_ == b.phi_
    assert base.phi_ == AnamModel(form="full", horizon=5).fit(shocked, train_end=cut).phi_


def test_no_training_outcome_reaches_the_cutoff():
    ses = pd.Series(np.arange(30))
    tgt = forward_target(pd.Series(np.ones(30)), pd.Series(["A"] * 30), ses, 5)
    keep = purged(tgt["end_session"], 20)
    assert ses[keep & tgt["y"].notna()].max() == 14          # origin 14's outcome ends at session 19


# ── 2. a gap in the sessions breaks the target instead of being stitched over (A02) ──────────────────

def test_a_missing_session_is_not_stitched_over():
    dates = pd.bdate_range("2024-01-01", periods=12)
    full = pd.DataFrame({"symbol": "A", "date": dates, "r2": np.arange(1.0, 13.0)})
    gap = full.drop(index=6).reset_index(drop=True)               # session 6 has no bar
    ses = session_ordinal(gap["date"], dates)
    t = forward_target(gap["r2"], gap["symbol"], ses, 5)
    # origins 1-5 would need session 6: the old row count would have used the next five ROWS instead
    for origin in range(1, 6):
        assert np.isnan(t["y"].iloc[origin]) and t["reason"].iloc[origin] == "missing session"
    assert t["y"].iloc[0] == pytest.approx(np.mean([2, 3, 4, 5, 6]))
    assert np.isnan(t["y"].iloc[6]) and t["reason"].iloc[6] == "beyond data"   # session 12 does not exist


# ── 3. a zero target is scored, not dropped (A08) ────────────────────────────────────────────────────

def test_a_zero_target_has_a_finite_loss_and_a_defined_difference():
    y, f1, f2 = np.array([0.0, 1e-4]), np.array([1e-4, 1e-4]), np.array([2e-4, 2e-4])
    l1, l2 = qlike_canonical(y, f1), qlike_canonical(y, f2)
    assert np.isfinite(l1).all() and np.isfinite(l2).all()
    assert l1[0] < l2[0]                                         # a smaller forecast loses less at y = 0
    assert np.isnan(qlike_normalized(y, f1)[0])
    # wherever y > 0 the two forms give the same difference between forecasts
    assert (l1 - l2)[1] == pytest.approx((qlike_normalized(y, f1) - qlike_normalized(y, f2))[1], rel=1e-12)


# ── 4. no candidate is scored on fewer origins than another (A08) ────────────────────────────────────

def test_a_candidate_with_a_nonpositive_forecast_is_rejected_not_rescored():
    y = pd.Series([1.0, 2.0, 1.5, 0.5])
    rows = pd.Series(True, index=y.index)
    good = pd.Series([1.0, 1.5, 1.5, 1.0])
    bad = pd.Series([1.0, 2.0, -1.0, 0.5])                        # perfect wherever it is positive
    best, loss, rejected = select_by_loss(["good", "bad"], y, rows, lambda c: good if c == "good" else bad)
    assert best == "good" and rejected == 1
    with pytest.raises(ValueError, match="every phi"):
        AnamModel(phi_grid=(0.5, 1.2))


# ── 5. the mean and its t statistic estimate the same weighting (A09) ────────────────────────────────

def test_inference_targets_the_reported_weighting_on_an_unbalanced_panel():
    rng = np.random.default_rng(3)
    rows = []
    for t in range(60):
        n = 2 if t % 2 else 30                                    # a deliberately unbalanced panel
        shift = 1.0 if t % 2 else -0.2                            # the few-security dates differ in sign
        for i in range(n):
            rows.append((t, i, shift + rng.normal(0, 0.1)))
    df = pd.DataFrame(rows, columns=["date", "sec", "d"])
    sd = weighted_mean_se(df["d"], df["date"], lags=2)
    ed = weighted_mean_se(df["d"], df["date"], weights=1.0 / df.groupby("date")["d"].transform("size"), lags=2)
    assert sd["mean"] == pytest.approx(df["d"].mean())
    assert ed["mean"] == pytest.approx(df.groupby("date")["d"].mean().mean())
    assert np.sign(sd["mean"]) == np.sign(sd["t"]) == -1         # stock-day mean is negative ...
    assert np.sign(ed["mean"]) == np.sign(ed["t"]) == 1          # ... the equal-date mean positive
    # the standard error is the ratio estimator's, computed by hand
    g = df.assign(u=df["d"] - sd["mean"]).groupby("date").agg(S=("u", "sum"), N=("u", "size"))
    u, T = g["S"].to_numpy(), len(g)
    lrv = u @ u / T + 2 * sum((1 - k / 3) * (u[k:] @ u[:-k]) / T for k in (1, 2))
    assert sd["se"] == pytest.approx(np.sqrt(T * lrv) / g["N"].sum(), rel=1e-12)


# ── 6. extending the range keeps contamination already in the high or low (A05) ─────────────────────

def test_the_extended_range_keeps_an_opening_error_that_set_the_high():
    # previous close = close = low = 100, an erroneous open printed at 105 sets the high; b = 0
    o, u, d, c = np.log(1.05), 0.0, np.log(100 / 105), np.log(100 / 105)
    one = lambda v: pd.Series([v])
    Rs = extended_range(one(o), one(u), one(d), one(0.0))
    assert Rs.iloc[0] == pytest.approx(np.log(1.05))
    A = kernel(one(o), one(c), one(u), one(d), one(0.0))
    assert A.iloc[0] == pytest.approx(0.8 * np.log(1.05) ** 2 / (4 * np.log(2)))
    assert A.iloc[0] > 0                                          # nothing moved but the erroneous print
    # and in general R <= R* <= true range, for any b in [0, 1]
    rng = np.random.default_rng(5)
    n = 2000
    o_ = pd.Series(rng.normal(0, 0.02, n))
    c_ = pd.Series(rng.normal(0, 0.02, n))
    u_ = np.maximum(0, c_) + rng.exponential(0.01, n)
    d_ = np.minimum(0, c_) - rng.exponential(0.01, n)
    b_ = pd.Series(rng.uniform(0, 1, n))
    R, Rstar, TR = u_ - d_, extended_range(o_, u_, d_, b_), extended_range(o_, u_, d_, b_ * 0)
    assert (R <= Rstar + 1e-15).all() and (Rstar <= TR + 1e-15).all()


# ── the target, against a brute-force loop ───────────────────────────────────────────────────────────

def test_forward_target_equals_a_brute_force_calculation():
    rng = np.random.default_rng(11)
    cal = pd.bdate_range("2023-01-02", periods=80)
    parts = []
    for s in "ABC":
        keep = rng.random(len(cal)) > 0.15                       # random missing sessions
        x = pd.DataFrame({"symbol": s, "date": cal[keep], "r2": rng.exponential(1e-4, keep.sum())})
        x.loc[rng.random(len(x)) < 0.05, "r2"] = np.nan          # a few unobserved returns
        x.loc[rng.random(len(x)) < 0.05, "r2"] = 0.0             # and a few zero ones
        parts.append(x)
    p = pd.concat(parts, ignore_index=True)
    ses = session_ordinal(p["date"], cal)
    for h in (1, 5, 21):
        got = forward_target(p["r2"], p["symbol"], ses, h)["y"]
        pos = {(s, k): v for s, k, v in zip(p["symbol"], ses, p["r2"])}
        for i, (s, k) in enumerate(zip(p["symbol"], ses)):
            vals = [pos.get((s, k + j), "missing") for j in range(1, h + 1)]
            ok = all(not isinstance(v, str) and np.isfinite(v) for v in vals) and k + h < len(cal)
            want = np.mean(vals) if ok else np.nan
            assert (np.isnan(want) and np.isnan(got.iloc[i])) or got.iloc[i] == pytest.approx(want, rel=1e-12)


def test_a_date_off_the_calendar_is_refused():
    with pytest.raises(ValueError, match="not in the session calendar"):
        session_ordinal(pd.Series(pd.to_datetime(["2024-01-06"])), pd.bdate_range("2024-01-01", periods=5))


def test_the_model_scores_only_complete_targets_and_keeps_zero_ones(panel):
    thin = panel.copy()
    rng = np.random.default_rng(2)
    thin = thin[rng.random(len(thin)) > 0.03].reset_index(drop=True)      # random missing bars
    m = AnamModel(horizon=5).fit(thin, train_end=thin["date"].sort_values().unique()[300])
    bt = m.backtest()
    cal = pd.DatetimeIndex(sorted(thin["date"].unique()))
    pos = {d: i for i, d in enumerate(cal)}
    have = set(zip(thin["symbol"], thin["date"].map(pos)))
    for s, d in zip(bt["symbol"], bt["date"]):
        k = pos[d]
        assert all((s, k + j) in have for j in range(1, 6))
    np.testing.assert_allclose(bt["qlike_canonical"], qlike_canonical(bt["realised"], bt["forecast"]))


# ── the model confidence set ────────────────────────────────────────────────────────────────────────

def test_the_model_confidence_set_drops_a_clearly_worse_model_and_keeps_equals():
    rng = np.random.default_rng(4)
    T = 300
    base = rng.normal(1.0, 0.2, T)
    S = pd.DataFrame({"a": base + rng.normal(0, 0.01, T), "b": base + rng.normal(0, 0.01, T),
                      "bad": base + 0.3 + rng.normal(0, 0.01, T)})
    out = model_confidence_set(S, pd.Series(np.ones(T)), n_boot=499, mean_block=5, seed=1).set_index("model")
    assert not out.loc["bad", "in_mcs_90"]
    assert out.loc["a", "in_mcs_90"] and out.loc["b", "in_mcs_90"]
    assert out.loc["bad", "mcs_p"] < 0.05


def test_simulated_panel_round_trip():
    bars = simulate_bars(n_securities=4, n_sessions=300, seed=9)
    m = AnamModel(form="open-free", horizon=5).fit(bars)
    assert 0 <= m.phi_ < 1 and m.score() > 0
