"""A panel of daily bars generated from a known latent variance, under frontier-market frictions.

PURPOSE. :mod:`nepsevol.calibration` claims to identify each daily estimator's calibration slope
and the optimal composite from the data's own volatility persistence, with no high-frequency
benchmark. That claim has to be checked where the answer is known. This module produces a
security x session panel of daily bars -- open, high, low, close, VWAP, trade count, previous
close -- together with the TRUE intraday integrated variance of each session, under the frictions
the NEPSE manuscript documents:

* stochastic volatility with a persistent market factor, a persistent idiosyncratic factor and a
  transitory (unpredictable) component, so that part of each day's variance cannot be forecast --
  the case in which the level of measurement noise is NOT identified (see the calibration module);
* discrete trading: N_it ~ Poisson(lambda_i (sigma_it / sigma_i)^gamma) trades at uniform times,
  so activity rises with volatility, as it does in the data (that is why same-day liquidity sorts
  are endogenous, manuscript Section 6.2);
* bid-ask bounce: every continuous-session trade prints at the efficient price +/- s_i/2, with
  spreads wider for thinner securities;
* an opening call auction whose price carries a transient error and is CLAMPED to a band around
  the previous close (+/-2% by default, NEPSE's pre-April-2026 rule), the unrealised part of the
  overnight move then being traded through during the session;
* auctions that fail to match: with probability p_stale_i the reported open is the previous
  close, as on the ~10.6% of NEPSE equity stock-days on which open == prev_close;
* a daily price limit around the previous close (+/-10%);
* a session VWAP from lognormal trade sizes; and a close equal to the last trade or, under
  ``close_rule="vwap_tail"``, to the VWAP of the trades in the final ``close_tail`` of the session
  (falling back to the last trade when none occurs there) -- NEPSE's rule between 20 March and
  21 September 2025.

Everything is reproducible from ``seed``. Nothing here is calibrated to RESULTS: the frictions
are set from the descriptive features of the panel (trade-count quantiles, the stale-open share,
the band and limit rules), not from any estimator ratio.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

__all__ = ["MicroParams", "simulate_panel"]


@dataclass
class MicroParams:
    n_sec: int = 120
    n_days: int = 500
    # volatility: daily total variance exp(h), h = log(sig_i^2) + f_t + g_it + eta_it
    sigma_median: float = 0.022          # median daily total volatility across securities
    sigma_disp: float = 0.30             # cross-sectional log-sd of security volatility levels
    phi_f: float = 0.98                  # market factor persistence
    sd_f: float = 0.45                   # unconditional sd of the market factor (log variance)
    phi_g: float = 0.95                  # idiosyncratic factor persistence
    sd_g: float = 0.35                   # unconditional sd of the idiosyncratic factor
    sd_eta: float = 0.35                 # transitory, unpredictable log-variance shock
    theta: float = 0.75                  # share of daily variance accruing within the session
    # trading
    trades_median: float = 160.0         # median of security trade intensities lambda_i
    trades_disp: float = 1.0             # cross-sectional log-sd of lambda_i
    gamma: float = 1.0                   # elasticity of trade count to daily volatility
    max_trades: int = 3000               # cap per session (beyond it the range is effectively continuous)
    # frictions
    spread_bp_at_median: float = 40.0    # quoted spread (bp) for a security at the median intensity
    spread_elasticity: float = 0.5       # spread ~ (lambda_median / lambda_i)^elasticity
    spread_cap_bp: float = 300.0
    auction_noise_frac: float = 0.25     # sd of the auction error, as a fraction of overnight sd
    band: float | None = 0.02            # opening-auction band around the previous close
    limit: float | None = 0.10           # daily price limit around the previous close
    stale_open_thin: float = 0.25        # P(no auction match) for the thinnest securities
    stale_open_thick: float = 0.02       # ... and for the most active
    tick_bp: float = 0.0                 # price grid (bp of price); 0 disables rounding
    close_rule: str = "last"             # "last": the last trade; "vwap_tail": VWAP of the final
    close_tail: float = 1.0 / 16.0       #   close_tail of the session (NEPSE 20 Mar - 21 Sep 2025:
                                         #   14:45-15:00 of an 11:00-15:00 session, i.e. 1/16)
    seed: int = 20261004


def _ar1(rng, n, phi, sd, size=()):
    """Stationary AR(1) with unconditional sd ``sd``, length ``n`` along the last axis."""
    e = rng.standard_normal(size + (n,)) * sd * np.sqrt(1 - phi ** 2)
    x = np.empty(size + (n,))
    x[..., 0] = rng.standard_normal(size) * sd
    for t in range(1, n):
        x[..., t] = phi * x[..., t - 1] + e[..., t]
    return x


def simulate_panel(params: MicroParams | None = None, **overrides) -> pd.DataFrame:
    """Simulate the panel. Returns one row per security-session.

    Columns: symbol, day, date, open, high, low, close, vwap, n_trades, prev_close,
    iv (true intraday integrated variance of the efficient log price), v_pred (its predictable
    part, E[iv_t | latent state at t-1]), on (true overnight variance), lam (the security's trade intensity), spread_bp, open_stale, open_clamped,
    session_ord.
    """
    p = params or MicroParams()
    if overrides:
        p = MicroParams(**{**asdict(p), **overrides})
    rng = np.random.default_rng(p.seed)
    S, T = p.n_sec, p.n_days

    sig_i = p.sigma_median * np.exp(p.sigma_disp * rng.standard_normal(S))
    lam_i = p.trades_median * np.exp(p.trades_disp * rng.standard_normal(S))
    spread_i = np.minimum(p.spread_bp_at_median * (p.trades_median / lam_i) ** p.spread_elasticity,
                          p.spread_cap_bp) * 1e-4
    # stale-open probability: interpolate in log-intensity between thick and thin
    z = (np.log(lam_i) - np.log(p.trades_median)) / max(p.trades_disp, 1e-9)
    q = 1 / (1 + np.exp(1.5 * z))               # ~1 for thin, ~0 for thick
    p_stale_i = p.stale_open_thick + (p.stale_open_thin - p.stale_open_thick) * q

    f = _ar1(rng, T, p.phi_f, p.sd_f)
    g = _ar1(rng, T, p.phi_g, p.sd_g, size=(S,))
    eta = rng.standard_normal((S, T)) * p.sd_eta
    # centre the log-variance so E[sigma^2] equals sig_i^2 (lognormal correction)
    var_h = p.sd_f ** 2 + p.sd_g ** 2 + p.sd_eta ** 2
    h = np.log(sig_i[:, None] ** 2) + f[None, :] + g + eta - 0.5 * var_h
    sig2 = np.exp(h)                              # total daily variance
    iv = p.theta * sig2
    on = (1 - p.theta) * sig2
    # PREDICTABLE intraday variance, E[iv_t | latent state at t-1]: the AR(1) components carry
    # forward phi * state, and the new innovations and the transitory shock are integrated out.
    # This is the 'V_t' of nepsevol.calibration's measurement model, known here by construction.
    f_lag = np.concatenate([[0.0], f[:-1]])
    g_lag = np.concatenate([np.zeros((S, 1)), g[:, :-1]], axis=1)
    innov_var = p.sd_f ** 2 * (1 - p.phi_f ** 2) + p.sd_g ** 2 * (1 - p.phi_g ** 2) + p.sd_eta ** 2
    v_pred = p.theta * np.exp(np.log(sig_i[:, None] ** 2) + p.phi_f * f_lag[None, :] + p.phi_g * g_lag
                              - 0.5 * var_h + 0.5 * innov_var)

    rows = []
    for i in range(S):
        n_tr = rng.poisson(lam_i[i] * (np.sqrt(sig2[i]) / sig_i[i]) ** p.gamma)
        n_tr = np.clip(n_tr, 1, p.max_trades)
        nmax = int(n_tr.max())
        # Trade times. Each day's n_tr times are the order statistics of n_tr uniforms: the padded
        # columns are pushed past the session end BEFORE sorting, so a day with fewer trades than
        # nmax does not inherit the smallest n_tr of nmax draws (which would bunch its trades at
        # the start of the session). Column 0 is the auction at tau = 0 when the auction matches;
        # when it does not, all n trades are continuous and the reported open is the previous close.
        mask = np.arange(nmax)[None, :] < n_tr[:, None]
        U = np.where(mask, rng.random((T, nmax)), 2.0)
        U.sort(axis=1)
        stale = rng.random(T) < p_stale_i[i]
        times = U
        times[~stale, 0] = 0.0
        times = np.where(mask, times, 1.0)       # padded columns sit at the session end
        dt = np.diff(np.concatenate([np.zeros((T, 1)), times], axis=1), axis=1)
        inc = np.sqrt(dt * iv[i][:, None]) * rng.standard_normal((T, nmax))
        # efficient intraday path at trade times, relative to the efficient open price
        path = np.cumsum(inc, axis=1)
        # remaining efficient move from the last trade to the session end (keeps IV exact)
        last_t = np.take_along_axis(times, (n_tr - 1)[:, None], axis=1)[:, 0]
        tail = np.sqrt((1 - last_t) * iv[i]) * rng.standard_normal(T)

        # efficient log prices across days: p_open(t) = p_close(t-1) + overnight; p_close = p_open + path_end
        on_move = np.sqrt(on[i]) * rng.standard_normal(T)
        path_last = np.take_along_axis(path, (n_tr - 1)[:, None], axis=1)[:, 0]
        intraday_total = path_last + tail
        p_open = np.empty(T)
        p_close = np.empty(T)
        level = np.log(100.0)
        for t in range(T):
            p_open[t] = level + on_move[t]
            p_close[t] = p_open[t] + intraday_total[t]
            level = p_close[t]

        # observed trades: efficient + bounce (continuous session); auction: efficient + error
        bounce = rng.choice([-1.0, 1.0], size=(T, nmax)) * spread_i[i] / 2
        x = p_open[:, None] + path + bounce
        auction_err = p.auction_noise_frac * np.sqrt(on[i]) * rng.standard_normal(T)

        # previous observed close (log) and the rule-based clamps
        rows_i = []
        prev_c = np.log(100.0)
        for t in range(T):
            n = n_tr[t]
            xt = x[t, :n].copy()
            clamped = False
            if not stale[t]:
                a = p_open[t] + auction_err[t]
                if p.band is not None:
                    lo_b, hi_b = prev_c + np.log(1 - p.band), prev_c + np.log(1 + p.band)
                    if a < lo_b or a > hi_b:
                        clamped = True
                        a = min(max(a, lo_b), hi_b)
                xt[0] = a
            if p.limit is not None:
                lo_l, hi_l = prev_c + np.log(1 - p.limit), prev_c + np.log(1 + p.limit)
                xt = np.clip(xt, lo_l, hi_l)
            if p.tick_bp > 0:
                tk = p.tick_bp * 1e-4
                xt = np.round(xt / tk) * tk
            O = prev_c if stale[t] else xt[0]
            v = rng.lognormal(0.0, 1.0, n)
            C = xt[-1]
            if p.close_rule == "vwap_tail":
                tail_m = times[t, :n] >= 1.0 - p.close_tail
                if not stale[t]:
                    tail_m[0] = False             # the auction print is never in the tail
                if tail_m.any():
                    C = np.log(np.sum(v[tail_m] * np.exp(xt[tail_m])) / v[tail_m].sum())
            elif p.close_rule != "last":
                raise ValueError(f"close_rule must be 'last' or 'vwap_tail', got {p.close_rule!r}")
            H = max(xt.max(), O, C)
            L = min(xt.min(), O, C)
            vwap = np.log(np.sum(v * np.exp(xt)) / v.sum())
            rows_i.append((O, H, L, C, vwap, n, prev_c, stale[t], clamped))
            prev_c = C
        arr = np.array([r_[:7] for r_ in rows_i], dtype=float)
        flags = np.array([r_[7:] for r_ in rows_i], dtype=bool)
        df = pd.DataFrame({
            "symbol": f"S{i:03d}", "day": np.arange(T),
            "open": np.exp(arr[:, 0]), "high": np.exp(arr[:, 1]), "low": np.exp(arr[:, 2]),
            "close": np.exp(arr[:, 3]), "vwap": np.exp(arr[:, 4]), "n_trades": arr[:, 5].astype(int),
            "prev_close": np.exp(arr[:, 6]), "iv": iv[i], "v_pred": v_pred[i], "on": on[i],
            "lam": lam_i[i],
            "spread_bp": spread_i[i] * 1e4, "open_stale": flags[:, 0], "open_clamped": flags[:, 1],
        })
        df.loc[0, "prev_close"] = np.nan          # no observed close before the first session
        rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    out["date"] = pd.Timestamp("2020-01-01") + pd.to_timedelta(out["day"], unit="D")
    out["session_ord"] = out["day"] + 1
    return out
