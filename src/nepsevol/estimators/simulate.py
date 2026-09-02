"""Simulation apparatus for discretisation bias in range-based estimators.

This is the paper's core experiment. A range estimator assumes the observed daily
high and low are the supremum and infimum of a CONTINUOUS diffusion. In reality
they are the max and min of N discrete transactions. This module generates price
paths with KNOWN volatility, samples them at controllable trade intensity, and
measures the resulting bias in each estimator.

Because the true sigma is known by construction, this is the one setting where
"which estimator is more accurate" has an unambiguous answer -- which is exactly
what NEPSE lacks.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["simulate_ohlc", "simulate_ohlc_fast", "bias_curve"]


def simulate_ohlc(
    n_days: int,
    sigma_daily: float,
    n_trades: int,
    drift_daily: float = 0.0,
    fine_steps: int = 2000,
    seed: int | None = None,
    open_jump_sd: float = 0.0,
    price_limit: float | None = None,
    tick: float | None = None,
    p0: float = 100.0,
) -> pd.DataFrame:
    """Simulate daily OHLC from a fine-grained GBM path observed at `n_trades` points.

    Parameters
    ----------
    sigma_daily : true daily volatility (the quantity estimators should recover)
    n_trades    : transactions observed per day. The friction. Low N -> observed
                  range understates true range -> range estimators biased down.
    fine_steps  : resolution of the latent path. n_trades are drawn from it.
    open_jump_sd: overnight gap volatility (tests GKYZ / Yang-Zhang overnight terms)
    price_limit : symmetric daily price limit as a fraction (e.g. 0.10 for +/-10%).
                  Censors the observed high and low, as a circuit breaker does.
    tick        : price discreteness. Rounds observed prices to this grid.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / fine_steps
    sd_step = sigma_daily * np.sqrt(dt)
    mu_step = drift_daily * dt

    rows = []
    prev_close = p0
    for _ in range(n_days):
        # overnight gap, then the intraday latent path
        open_px = prev_close * np.exp(rng.normal(0.0, open_jump_sd)) if open_jump_sd > 0 else prev_close
        steps = rng.normal(mu_step, sd_step, fine_steps)
        path = open_px * np.exp(np.cumsum(steps))

        # observe only n_trades points, in time order, always including the last (close)
        if n_trades >= fine_steps:
            obs = path
        else:
            idx = np.sort(rng.choice(fine_steps - 1, size=max(n_trades - 1, 1), replace=False))
            obs = np.concatenate([path[idx], path[-1:]])

        if tick:
            obs = np.round(obs / tick) * tick
            open_px = round(open_px / tick) * tick

        hi, lo, close_px = obs.max(), obs.min(), obs[-1]

        if price_limit is not None:                      # circuit-breaker censoring
            cap, floor_ = prev_close * (1 + price_limit), prev_close * (1 - price_limit)
            hi, lo = min(hi, cap), max(lo, floor_)
            close_px = min(max(close_px, floor_), cap)
            open_px = min(max(open_px, floor_), cap)

        hi = max(hi, open_px, close_px)                  # enforce OHLC consistency
        lo = min(lo, open_px, close_px)
        rows.append((open_px, hi, lo, close_px))
        prev_close = close_px

    return pd.DataFrame(rows, columns=["open", "high", "low", "close"])


def simulate_ohlc_fast(
    n_days: int,
    sigma_daily: float,
    n_trades: int,
    drift_daily: float = 0.0,
    fine_steps: int = 1000,
    seed: int | None = None,
    open_jump_sd: float = 0.0,
    p0: float = 100.0,
) -> pd.DataFrame:
    """Vectorised simulate_ohlc for the no-censoring case.

    Identical model to simulate_ohlc but generates all days at once. Used for the
    bias-curve experiment, which needs millions of simulated days. Does not support
    price limits or tick rounding (both are path-dependent); use simulate_ohlc for those.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / fine_steps
    incr = rng.normal(drift_daily * dt, sigma_daily * np.sqrt(dt), size=(n_days, fine_steps))
    rel = np.exp(np.cumsum(incr, axis=1))          # path relative to that day's open

    # observe n_trades points per day; the close (last point) is always observed
    if n_trades >= fine_steps:
        obs = rel
    else:
        k = max(int(n_trades) - 1, 1)
        idx = rng.integers(0, fine_steps - 1, size=(n_days, k))
        obs = np.take_along_axis(rel, idx, axis=1)
        obs = np.concatenate([obs, rel[:, -1:]], axis=1)

    hi_r, lo_r, cl_r = obs.max(axis=1), obs.min(axis=1), rel[:, -1]

    # chain days: each day's open is the previous close, times any overnight gap
    gaps = np.exp(rng.normal(0.0, open_jump_sd, size=n_days)) if open_jump_sd > 0 else np.ones(n_days)
    opens = p0 * np.concatenate([[1.0], np.cumprod(cl_r * gaps)[:-1]]) * gaps

    hi = opens * hi_r
    lo = opens * lo_r
    cl = opens * cl_r
    hi = np.maximum.reduce([hi, opens, cl])        # enforce OHLC consistency
    lo = np.minimum.reduce([lo, opens, cl])
    return pd.DataFrame({"open": opens, "high": hi, "low": lo, "close": cl})


def bias_curve(
    n_trades_grid,
    estimators: dict,
    n_days: int = 2000,
    sigma_daily: float = 0.02,
    n_reps: int = 20,
    seed: int = 0,
    **sim_kwargs,
) -> pd.DataFrame:
    """Measure each estimator's bias as a function of trading intensity.

    Returns tidy frame: n_trades, estimator, rep, sigma_hat, ratio (= sigma_hat / true).
    ratio == 1 means unbiased; < 1 means the estimator understates volatility.
    """
    out = []
    for n_tr in n_trades_grid:
        for rep in range(n_reps):
            df = simulate_ohlc_fast(
                n_days=n_days, sigma_daily=sigma_daily, n_trades=int(n_tr),
                seed=seed + rep * 1000 + int(n_tr), **sim_kwargs,
            )
            for name, fn in estimators.items():
                var = fn(df)
                v = np.nanmean(np.asarray(var, dtype=float))
                sigma_hat = np.sqrt(v) if v > 0 else np.nan
                out.append({
                    "n_trades": int(n_tr), "estimator": name, "rep": rep,
                    "sigma_hat": sigma_hat, "ratio": sigma_hat / sigma_daily,
                })
    return pd.DataFrame(out)


def simulate_observed_ohlc(
    n_days: int,
    sigma_daily: float,
    n_trades: int,
    noise_sd: float = 0.0,
    fine_steps: int = 1000,
    seed: int | None = None,
    p0: float = 100.0,
) -> pd.DataFrame:
    """Realistic observation model for a thinly traded security.

    Differs from simulate_ohlc_fast in three ways that matter in illiquid markets:

    1. Trade times are SORTED, and Open is the FIRST trade while Close is the LAST
       trade -- which is what an exchange actually reports, rather than the price at
       the instant the bell rings.
    2. Because of (1), the O/H/L/C of a thinly traded stock describe only the window
       in which it actually traded. That window is a random subinterval of the
       session and is strictly shorter than it. Every OHLC-derived measure therefore
       understates the day's variance by roughly the ratio of traded-window length to
       session length -- a bias distinct from, and additional to, undersampling of
       the path within the window.
    3. Each observed trade carries iid multiplicative noise (bid-ask bounce, price
       impact). This contaminates the high and low far more than the open and close,
       because extremes are order statistics: it biases the range UPWARD, opposing
       the two downward biases above.

    A 'true_cc' column carries the full-session close-to-close return, so the
    calendar-day variance remains available as the benchmark.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / fine_steps
    incr = rng.normal(0.0, sigma_daily * np.sqrt(dt), size=(n_days, fine_steps))
    rel = np.exp(np.cumsum(incr, axis=1))          # within-day path, each day starts at 1

    if n_trades >= fine_steps:
        idx = np.tile(np.arange(fine_steps), (n_days, 1))
    else:
        idx = np.sort(rng.integers(0, fine_steps, size=(n_days, max(int(n_trades), 1))), axis=1)
    obs = np.take_along_axis(rel, idx, axis=1)
    if noise_sd > 0:
        obs = obs * np.exp(rng.normal(0.0, noise_sd, size=obs.shape))

    o, c = obs[:, 0], obs[:, -1]
    hi = np.maximum.reduce([obs.max(axis=1), o, c])
    lo = np.minimum.reduce([obs.min(axis=1), o, c])

    lvl = p0 * np.concatenate([[1.0], np.cumprod(rel[:, -1])[:-1]])   # chain across days
    return pd.DataFrame({
        "open": lvl * o, "high": lvl * hi, "low": lvl * lo, "close": lvl * c,
        "true_cc": np.log(rel[:, -1]),
    })
