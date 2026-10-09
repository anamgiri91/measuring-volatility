"""Simulated daily bars with a known volatility and an opening price that overreacts.

Useful for trying the package without data, and for tests. Each session has an efficient overnight move
and an efficient intraday path; the printed open adds a transient error that the session undoes, as in
the markets the estimator was built for. The true daily variance is returned beside the bars.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["simulate_bars"]


def simulate_bars(n_securities: int = 20, n_sessions: int = 500, daily_vol: float = 0.02,
                  overnight_share: float = 0.3, open_noise: float = 1.0, steps: int = 40,
                  start: str = "2020-01-01", seed: int | None = 0) -> pd.DataFrame:
    """Daily bars for ``n_securities`` over ``n_sessions`` business days.

    The true daily variance follows a slow cycle around ``daily_vol**2``; ``overnight_share`` of it falls
    overnight. The printed open is the efficient open plus a transient error whose variance is
    ``open_noise`` times the overnight variance, so the open's unbiasedness coefficient is about
    ``1 / (1 + open_noise)``. The high and low are the extremes of an intraday path of ``steps`` steps
    that starts at the printed open and ends at the efficient close.

    Returns columns ``symbol, date, open, high, low, close, true_variance``.
    """
    if n_securities < 1 or n_sessions < 2 or steps < 2:
        raise ValueError("need at least one security, two sessions and two intraday steps")
    if not 0 < overnight_share < 1 or open_noise < 0 or daily_vol <= 0:
        raise ValueError("overnight_share must lie in (0, 1); open_noise and daily_vol must be positive")
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n_sessions)
    cycle = 1.0 + 0.5 * np.sin(np.linspace(0.0, 4.0 * np.pi, n_sessions))
    var = daily_vol ** 2 * cycle / cycle.mean()
    frames = []
    for i in range(n_securities):
        s_on = np.sqrt(overnight_share * var)
        s_in = np.sqrt((1.0 - overnight_share) * var)
        eta = rng.normal(0.0, s_on)                              # efficient overnight move
        err = rng.normal(0.0, np.sqrt(open_noise) * s_on)        # transient opening error
        incr = rng.normal(0.0, 1.0, (n_sessions, steps)) * (s_in / np.sqrt(steps))[:, None]
        path = np.cumsum(incr, axis=1)                           # efficient intraday path from the open
        log_pc = np.log(100.0) + np.concatenate([[0.0], np.cumsum(eta + path[:, -1])[:-1]])
        log_open = log_pc + eta + err
        # the printed open, then a path that removes the opening error over the session
        decay = np.linspace(1.0, 0.0, steps)[None, :]
        intraday = log_pc[:, None] + eta[:, None] + path + err[:, None] * decay
        log_close = intraday[:, -1]
        high = np.maximum(log_open, intraday.max(axis=1))
        low = np.minimum(log_open, intraday.min(axis=1))
        frames.append(pd.DataFrame({"symbol": f"S{i + 1:03d}", "date": dates, "open": np.exp(log_open),
                                    "high": np.exp(high), "low": np.exp(low), "close": np.exp(log_close),
                                    "true_variance": var}))
    return pd.concat(frames, ignore_index=True)
