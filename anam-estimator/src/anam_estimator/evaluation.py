"""Forecast evaluation for daily-bar volatility: one implementation for this package and for the paper.

This module was written after an independent audit of the research (9 October 2026), which found four
defects in the forecast evaluation of the paper's plans M16-M18 (``nepsevol.volforecast``, which is kept
unchanged so that the frozen tables stay reproducible) and in this package's model:

* training examples whose outcome window ended inside the test period (audit item A01);
* targets of "h sessions" that were h retained rows, stitched across missing exchange sessions (A02);
* zero targets dropped, and shrinkage candidates scored on different samples (A08);
* reported mean differences and t statistics that estimated different weightings of the panel (A09).

Plan M20 (``M20_CORRECTED_EVALUATION_PLAN.md`` in the paper's repository) fixes the corrected design, and
the paper's corrected evaluation and :class:`anam_estimator.AnamModel` both call the functions below.

THE TARGET
----------
At the close of session t (the forecast origin), for a security and a horizon h,

    y_t(h) = (1/h) * sum_{j=1..h} r_{t+j}^2,

the mean squared close-to-close log return over the next h EXCHANGE sessions. It is observed only when
the security has a close-to-close return on every one of those sessions: it traded on each, and each
return runs from the previous session's close. ``y`` may be zero. Its conditional mean E[y_t(h) | F_t],
the conditional second moment of observed returns, is what the forecasts target. That is not latent
integrated variance: a squared observed return also carries the squared drift and closing-price errors.

THE LOSS
--------
QLIKE in its canonical form ``L(y, f) = y/f + ln f`` (:func:`qlike_canonical`), defined for ``y >= 0`` and ``f > 0``. Its expectation is
minimised at ``f = E[y | F]`` (Patton 2011), so for a conditionally unbiased target it ranks forecasts as
their conditional mean would. Wherever ``y > 0`` it differs from the normalised form
``y/f - ln(y/f) - 1`` only by a term in ``y``, so loss DIFFERENCES between forecasts are the same.

TIMING
------
An origin's outcome ends at session t+h. A parameter fitted on "data before a cutoff" may use only the
origins whose outcome ends before the cutoff (``purged``). Features dated t use bars through t: the
forecast is made after the close.

INFERENCE
---------
A mean loss difference over a panel is a ratio of sums, ``sum_i w_i d_i / sum_i w_i``. Its standard error
comes from the date-level linearisation ``u_t = sum_{i on t} w_i (d_i - mean)`` with a Bartlett long-run
variance over dates, so that the reported mean and its t statistic estimate the same weighting.
Unit weights give the stock-day mean, ``1/N_t`` the equal-date mean and ``1/n_i`` the equal-security
mean. :func:`model_confidence_set` applies Hansen, Lunde and Nason's (2011) model confidence set to the
same weighted means, with a stationary bootstrap over dates.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "session_ordinal", "forward_target", "purged", "qlike_canonical", "qlike_normalized", "date_sums",
    "weighted_mean_se", "bartlett_lrv", "andrews_bandwidth", "stationary_multiplicities",
    "model_confidence_set", "select_by_loss", "TARGET_REASONS", "ZERO_SQUARE", "clean_square",
    "rolling_mean_exact",
]

#: why an origin's target is or is not observed (see :func:`forward_target`)
TARGET_REASONS = ("complete", "missing session", "missing return", "beyond data")
#: a squared log return or daily kernel below this is the floating-point residue of two equal prices (the
#: log of their ratio is of order 1e-16), not a price move: a genuine one-tick move on any exchange's price
#: grid squares to more than 1e-12. Such values count as exactly zero, so that a "positive" long-run level
#: means a positive one (found in the first run of plan M20, where residues of order 1e-36 in the Dhaka
#: panel passed the positivity test and produced near-zero forecasts).
ZERO_SQUARE = 1e-18


def clean_square(x) -> pd.Series:
    """A squared quantity with floating-point residues of equal prices set to exactly zero (NaN kept)."""
    s = pd.Series(x, dtype=float) if not isinstance(x, pd.Series) else x.astype(float)
    return s.where(~(s.abs() < ZERO_SQUARE), 0.0)


def rolling_mean_exact(x: pd.Series, by: pd.Series, n: int, minp: int | None = None) -> pd.Series:
    """Each security's mean of its last ``n`` rows (NaN skipped, at least ``minp`` observed), exactly zero
    where every observed value in the window is zero (a rolling sum can otherwise leave a residue)."""
    mp = n if minp is None else minp
    m = x.groupby(by, sort=False).transform(lambda z: z.rolling(n, min_periods=mp).mean())
    nz = (x.notna() & (x != 0)).astype(float)
    cnt = nz.groupby(by, sort=False).transform(lambda z: z.rolling(n, min_periods=1).sum())
    return m.where(~((cnt == 0) & m.notna()), 0.0)


def session_ordinal(dates, calendar=None) -> pd.Series:
    """The exchange-session number of every date.

    ``calendar`` is the market's sessions in any order; by default it is every distinct date in
    ``dates``, which is the right calendar for a panel in which some security trades on every session.
    A date that is not in the calendar raises, because a bar on a non-session cannot be placed.
    """
    d = pd.Series(pd.to_datetime(pd.Series(dates)).to_numpy(), index=getattr(dates, "index", None))
    cal = pd.DatetimeIndex(pd.to_datetime(pd.Series(d.unique() if calendar is None else calendar))).unique()
    cal = cal.sort_values()
    pos = pd.Series(np.arange(len(cal)), index=cal)
    out = d.map(pos)
    if out.isna().any():
        bad = sorted(set(d[out.isna()].dt.date.astype(str)))[:5]
        raise ValueError(f"dates not in the session calendar: {bad}")
    return out.astype(int)


def forward_target(r2, symbol, session, h: int) -> pd.DataFrame:
    """The target ``y_t(h)`` for every row, and whether and why it is observed.

    ``r2`` holds each row's squared close-to-close return (NaN where it is not observed), ``symbol``
    the security and ``session`` the session ordinal (:func:`session_ordinal`); rows must be sorted by
    (symbol, date) with one row per security and session. Returns a frame aligned with ``r2``:

    * ``y``: the mean of ``r2`` over the security's next ``h`` sessions, NaN unless observed;
    * ``end_session``: the session on which the outcome ends (origin's session + h);
    * ``reason``: one of :data:`TARGET_REASONS`. "missing session" means the security has no row on
      at least one of the h sessions (a gap the old row-count target stitched across); "missing
      return" means a row is there but its return is not observed; "beyond data" means the panel ends
      before the outcome does.
    """
    h = int(h)
    if h < 1:
        raise ValueError("h must be at least 1")
    r2 = pd.Series(r2, dtype=float)
    idx = r2.index
    sym = pd.Series(np.asarray(symbol), index=idx)
    ses = pd.Series(np.asarray(session, dtype=float), index=idx)
    step = ses.groupby(sym, sort=False).diff()
    if (step.dropna() <= 0).any():
        raise ValueError("rows must be sorted by (symbol, date) with one row per security and session")
    nxt = ses.groupby(sym, sort=False).shift(-h)
    fsum = r2.groupby(sym, sort=False).transform(
        lambda z: z[::-1].rolling(h, min_periods=h).sum()[::-1].shift(-1))
    consecutive = (nxt - ses) == h
    complete = consecutive & fsum.notna()
    reason = np.where(nxt.isna(), "beyond data",
                      np.where(~consecutive, "missing session",
                               np.where(fsum.isna(), "missing return", "complete")))
    return pd.DataFrame({"y": (fsum / h).where(complete), "end_session": ses + h, "reason": reason},
                        index=idx)


def purged(end_session, cutoff_session) -> pd.Series:
    """True for origins whose outcome ends strictly before ``cutoff_session`` (the first session the
    fitted model may not see)."""
    e = pd.Series(end_session, dtype=float)
    return e < float(cutoff_session)


def qlike_canonical(y, f):
    """QLIKE loss ``y/f + ln f`` (defined for y >= 0, f > 0; minimised in expectation at f = E[y])."""
    y = np.asarray(y, dtype=float)
    f = np.asarray(f, dtype=float)
    if np.any(f <= 0):
        raise ValueError("a QLIKE forecast must be positive")
    return y / f + np.log(f)


def qlike_normalized(y, f):
    """Normalised QLIKE ``q - ln q - 1``, q = y/f: zero for a perfect forecast, NaN where y = 0."""
    y = np.asarray(y, dtype=float)
    f = np.asarray(f, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        q = y / f
        out = q - np.log(q) - 1.0
    return np.where(y > 0, out, np.nan)


def date_sums(values, dates, weights=None) -> pd.DataFrame:
    """Per-date sums ``S_t = sum w_i v_i`` and ``W_t = sum w_i``, sorted by date. ``values`` may be a
    Series or a DataFrame (one column per model, summed column by column)."""
    v = values if isinstance(values, pd.DataFrame) else pd.DataFrame({"v": values})
    w = pd.Series(1.0, index=v.index) if weights is None else pd.Series(weights, index=v.index, dtype=float)
    key = pd.Series(np.asarray(dates), index=v.index)
    S = v.mul(w, axis=0).groupby(key).sum().sort_index()
    W = w.groupby(key).sum().sort_index()
    return S.assign(_W=W)


def bartlett_lrv(u, lags: int) -> float:
    """Bartlett-kernel long-run variance of a mean-zero series: gamma_0 + 2 sum (1 - k/(L+1)) gamma_k."""
    u = np.asarray(u, dtype=float)
    n = len(u)
    s = float(u @ u) / n
    for k in range(1, min(int(lags), n - 1) + 1):
        s += 2.0 * (1.0 - k / (lags + 1.0)) * float(u[k:] @ u[:-k]) / n
    return s


def andrews_bandwidth(u, floor: int = 1) -> int:
    """Andrews' (1991) AR(1) plug-in bandwidth for the Bartlett kernel, at least ``floor``."""
    u = np.asarray(u, dtype=float)
    n = len(u)
    if n < 3:
        return int(floor)
    rho = float(u[1:] @ u[:-1]) / float(u[:-1] @ u[:-1]) if float(u[:-1] @ u[:-1]) > 0 else 0.0
    rho = float(np.clip(rho, -0.97, 0.97))
    a1 = 4 * rho ** 2 / ((1 - rho) ** 2 * (1 + rho) ** 2)
    return int(max(floor, np.floor(1.1447 * (a1 * n) ** (1 / 3))))


def weighted_mean_se(d, dates, weights=None, lags: int = 1) -> dict:
    """Weighted panel mean of ``d`` and its standard error, clustered by date with a Bartlett HAC.

    The mean is ``sum w d / sum w``; ``u_t = sum_{i on t} w_i (d_i - mean)`` and
    ``Var(mean) = T * LRV(u) / (sum w)^2``. Returns mean, se, t, the number of rows and of dates, and
    the lags used. NaN rows of ``d`` are dropped.
    """
    d = pd.Series(d, dtype=float)
    ok = d.notna()
    w = pd.Series(1.0, index=d.index) if weights is None else pd.Series(weights, index=d.index, dtype=float)
    d, w = d[ok], w[ok]
    dts = pd.Series(np.asarray(dates), index=ok.index)[ok]
    if len(d) == 0:
        return dict(mean=np.nan, se=np.nan, t=np.nan, n=0, n_dates=0, lags=int(lags))
    m = float((w * d).sum() / w.sum())
    g = pd.DataFrame({"S": w * (d - m), "W": w, "date": dts}).groupby("date")[["S", "W"]].sum().sort_index()
    T = len(g)
    if T < 10:
        return dict(mean=m, se=np.nan, t=np.nan, n=int(len(d)), n_dates=T, lags=int(lags))
    lrv = bartlett_lrv(g["S"].to_numpy(), lags)
    se = float(np.sqrt(T * lrv) / g["W"].sum()) if lrv > 0 else np.nan
    return dict(mean=m, se=se, t=m / se if se and se > 0 else np.nan, n=int(len(d)), n_dates=T,
                lags=int(lags))


def stationary_multiplicities(n: int, rng: np.random.Generator, mean_block: float) -> np.ndarray:
    """How often each of ``n`` dates is drawn in one stationary-bootstrap resample (Politis and Romano
    1994): blocks of consecutive dates with geometric lengths of mean ``mean_block``, wrapped around."""
    p = 1.0 / max(float(mean_block), 1.0)
    counts = np.zeros(n)
    drawn = 0
    while drawn < n:
        start = int(rng.integers(0, n))
        length = int(min(rng.geometric(p), n - drawn))
        counts[(start + np.arange(length)) % n] += 1
        drawn += length
    return counts


def model_confidence_set(S: pd.DataFrame, W: pd.Series, alpha=(0.10, 0.25), n_boot: int = 1999,
                         mean_block: float = 10, seed: int = 0) -> pd.DataFrame:
    """Hansen, Lunde and Nason's (2011) model confidence set with the T_max statistic.

    ``S`` holds per-date loss sums (dates x models) on a common set of origins and ``W`` the per-date
    weight sums, so each model's loss is the weighted mean ``sum_t S_t / sum_t W_t``. Dates are resampled
    with a stationary bootstrap. Returns, for every model, its mean loss, the order in which it was
    eliminated (0 = never), its MCS p-value and whether it is in the set at each level in ``alpha``.
    """
    S = S.astype(float)
    W = pd.Series(W, dtype=float).reindex(S.index)
    names = list(S.columns)
    Sa, Wa = S.to_numpy(), W.to_numpy()
    T = len(Wa)
    rng = np.random.default_rng(seed)
    M = np.stack([stationary_multiplicities(T, rng, mean_block) for _ in range(n_boot)])   # B x T
    loss = Sa.sum(0) / Wa.sum()
    boot = (M @ Sa) / (M @ Wa)[:, None]                                                     # B x K
    alive = list(range(len(names)))
    pvals, order, p_running = {}, {}, 0.0
    step = 0
    while len(alive) > 1:
        L, Lb = loss[alive], boot[:, alive]
        d = L - L.mean()
        db = Lb - Lb.mean(1, keepdims=True)
        se = db.std(0, ddof=1)
        se = np.where(se > 0, se, np.inf)
        t = d / se
        tb = ((db - d) / se).max(1)
        p = float(np.mean(tb >= t.max()))
        p_running = max(p_running, p)
        worst = alive[int(np.argmax(t))]
        step += 1
        pvals[worst], order[worst] = p_running, step
        alive.remove(worst)
    pvals[alive[0]], order[alive[0]] = 1.0, 0
    out = pd.DataFrame({"model": names, "loss": loss, "eliminated": [order[k] for k in range(len(names))],
                        "mcs_p": [pvals[k] for k in range(len(names))]})
    for a in np.atleast_1d(alpha):
        out[f"in_mcs_{int(round(100 * (1 - a)))}"] = out["mcs_p"] >= a
    return out.sort_values(["mcs_p", "loss"], ascending=[False, True]).reset_index(drop=True)


def select_by_loss(candidates, y, rows, forecast) -> tuple:
    """Choose the candidate parameter with the lowest mean QLIKE on the fixed rows ``rows``.

    ``forecast(c)`` returns the forecast Series for candidate ``c``. A candidate whose forecast is not
    positive and finite on EVERY row is rejected rather than scored on fewer rows, so all candidates are
    compared on one sample. Returns (best candidate, its mean loss, number of rejected candidates).
    """
    rows = pd.Series(rows, dtype=bool)
    yy = pd.Series(y, dtype=float)[rows]
    if yy.isna().any():
        raise ValueError("every selection row needs an observed target")
    best, best_loss, rejected = None, np.inf, 0
    for c in candidates:
        f = pd.Series(forecast(c), dtype=float)[rows]
        if not (np.isfinite(f).all() and (f > 0).all()):
            rejected += 1
            continue
        m = float(np.mean(qlike_canonical(yy, f)))
        if m < best_loss:
            best, best_loss = c, m
    if best is None:
        raise ValueError("no candidate gives a positive forecast on every selection row")
    return best, best_loss, rejected
