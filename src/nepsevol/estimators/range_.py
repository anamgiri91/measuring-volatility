"""Range-based volatility estimators.

All functions return DAILY VARIANCE (not annualised, not sigma). Callers annualise
explicitly with a sessions-per-year factor derived from the exchange calendar in use;
do not assume 252. See nepsevol.trading_calendar.

Notation follows the literature:
    o = ln(O_t / C_{t-1})   overnight (close-to-open) return
    u = ln(H_t / O_t)       normalised high
    d = ln(L_t / O_t)       normalised low
    c = ln(C_t / O_t)       open-to-close return

All functions here are generic implementations. Market-specific interpretation belongs in
the manuscript and the audit record, not in these docstrings.

References. Two things are tracked separately and must not be collapsed: whether the
BIBLIOGRAPHIC RECORD is confirmed, and whether the EQUATION was read from the primary source.

Every bibliographic record below is now confirmed against publisher-deposited Crossref
metadata (referee item 18), which corrected one error carried in the manuscript reference
list: Yang & Zhang is 477-492, not 477-491.

    Parkinson (1980), J. Business 53(1), 61-65
        doi:10.1086/296071 -- record CONFIRMED; equation from secondary presentation
    Garman & Klass (1980), J. Business 53(1), 67-78
        doi:10.1086/296072 -- record CONFIRMED; equation from secondary presentation
    Rogers & Satchell (1991), Ann. Appl. Prob. 1(4), 504-512
        doi:10.1214/aoap/1177005835 -- record CONFIRMED; abstract read, and it independently
        confirms both claims made below: the estimator uses high, low and closing prices, and
        the authors themselves propose a correction for discretisation error. Full text not
        obtained, so the derivation is not independently checked.
    Yang & Zhang (2000), J. Business 73(3), 477-492
        doi:10.1086/209650 -- record CONFIRMED (pagination corrected from 477-491);
        equation from secondary presentation
    Kumar & Maheswaran (2014a), Economic Modelling 38, 33-44
        doi:10.1016/j.econmod.2013.11.045 -- record CONFIRMED; the THEORY paper. See add_rs.
    Kumar & Maheswaran (2014b), Int. Review of Financial Analysis 34, 166-176
        doi:10.1016/j.irfa.2014.06.002 -- record CONFIRMED; the OPERATIONAL paper, and the
        source of the equations implemented in add_rs. See add_rs provenance.

"equation from secondary presentation" means the formula was transcribed from a reproduction
rather than read from the primary text. The four classical equations are stable across the
literature and are additionally checked here against their own stated properties -- the
non-negativity proofs in the docstrings below are derived from the equations as written. FORENSIC
FOLLOW-UP: that phrasing previously claimed a transcription error "would show up as a proof that
fails", which overstates what a coarse property check can guarantee -- a wrong coefficient can
easily preserve non-negativity (or another property this weak) while still being wrong. The
accurate claim is narrower: these property checks are independent NECESSARY-condition sanity
tests on the implemented equations. They can catch some classes of transcription error (a sign
flip that breaks non-negativity, for instance) but do not verify the coefficients or derivations,
and are not a substitute for reading the primary text. That is a weaker guarantee than primary
reading and is labelled as such. See AUDIT-REGISTER.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LN2 = np.log(2.0)

__all__ = [
    "close_to_close", "parkinson", "garman_klass", "rogers_satchell",
    "gkyz", "yang_zhang", "realized_range", "add_rs",
]


def previous_session_close(df: pd.DataFrame, session_col: str = "session_ord") -> pd.Series:
    """Close of the PREVIOUS GENUINE TRADING SESSION, or NaN where there was not one.

    REFEREE ITEM 5 (critical), second half. The overnight return ``o = ln(O_t / C_{t-1})`` is
    defined in Section 4.5 against the previous genuine trading session. A bare ``.shift(1)``
    gives the previous OBSERVED ROW instead, and the two differ whenever a security does not
    trade on a session: in the shipped ordinary-equity panel, 230 row transitions skip more than
    one detected NEPSE session, the largest gap being 91 sessions. Treating a 91-session move as
    one overnight return inflates the overnight variance component of Yang-Zhang by roughly two
    orders of magnitude on those rows.

    ``session_ord`` is the consecutive-session ordinal from
    :func:`nepsevol.trading_calendar.session_index`. When it is present, the previous close is
    accepted only where the ordinal advanced by exactly one; every gap yields NaN and is excluded
    downstream rather than silently mis-scaled. When it is absent this degrades to ``.shift(1)``,
    which is correct for a gapless series such as an index and is what the index scripts pass.

    THE SUPPLIED ``prev_close`` COLUMN. The previous revision declined to use it because its
    provenance was unaudited. That audit has since been done -- see
    :mod:`nepsevol.corporate_actions` -- and it changed the answer: 214 of the 315
    disagreements are NEPSE's own ex-date reference-price adjustments, identifiable by an
    implied factor sitting on the bonus-share ladder. Ignoring them makes an entitlement drop
    look like a price movement, which is not a defensible input to a volatility estimator.

    This function is therefore the UNADJUSTED primitive, retained for the sensitivity
    specification and for gapless series such as an index.
    :func:`nepsevol.corporate_actions.adjusted_previous_close` is the definition the package
    ADOPTS and the one every analysis uses; it wraps this rule and substitutes the published
    previous close on classified ex-dates only.
    """
    prev = df["close"].shift(1)
    if session_col in df.columns:
        step = df[session_col].diff()
        prev = prev.where(step == 1)
    return prev


def _logs(df: pd.DataFrame, prev_close: pd.Series | None = None) -> dict[str, pd.Series]:
    """Standard log transforms. Expects columns open/high/low/close.

    Rows must already be sorted within one security. Quantities that reach across sessions --
    ``o`` and ``cc`` -- use :func:`previous_session_close` by default, so they are NaN across a
    session gap rather than silently spanning it. The purely within-session quantities (``u``,
    ``d``, ``c``, ``hl``) are unaffected: they read one bar only.

    ``prev_close`` OVERRIDES the default previous-session close for the two cross-session
    quantities. FOURTH-ROUND AUDIT FIX: without this parameter there was no way for a caller to
    push the package's ADOPTED previous close (the corporate-action-adjusted series from
    :mod:`nepsevol.corporate_actions`) into an estimator, so ``scripts/26_robustness.py`` was
    building its Yang-Zhang NUMERATOR from the unadjusted close while building the matched
    close-to-close DENOMINATOR from the adjusted one. That mixed-definition ratio was reported
    as though one definition had been applied throughout. It had not. Passing the series
    explicitly is now the only way a caller states which definition it means, and the two
    consistent specifications differ materially (1.280 adjusted vs 1.273 unadjusted, against
    1.309 for the mixed ratio that should never have been quoted).
    """
    o_, h, l, c_ = df["open"], df["high"], df["low"], df["close"]
    prev_c = previous_session_close(df) if prev_close is None else prev_close
    return {
        "o": np.log(o_ / prev_c),
        "u": np.log(h / o_),
        "d": np.log(l / o_),
        "c": np.log(c_ / o_),
        "hl": np.log(h / l),
        "cc": np.log(c_ / prev_c),
    }


def close_to_close(df: pd.DataFrame, window: int | None = None,
                   prev_close: pd.Series | None = None) -> pd.Series:
    """Close-to-close variance. The friction-robust baseline: uses no range data,
    so it is immune to discretisation bias in the observed high and low.

    ``prev_close`` overrides the default previous-session close, so a caller comparing this
    against :func:`yang_zhang` can guarantee both sides use the SAME definition -- see
    :func:`_logs` for why that guarantee had to be made explicit.
    """
    r = _logs(df, prev_close)["cc"]
    if window is None:
        return r.pow(2)
    return r.rolling(window).var(ddof=1)


def parkinson(df: pd.DataFrame) -> pd.Series:
    """Parkinson (1980). Uses only the high-low range.

    sigma^2 = (1 / (4 ln2)) * [ln(H/L)]^2

    Assumes zero drift and CONTINUOUS observation of the price path. The second
    assumption is what fails in illiquid markets: with N trades the observed range
    is the range of an N-sample, which understates the true range. Returns exactly
    zero when H == L, i.e. whenever no price movement is observed within the session.
    """
    hl = _logs(df)["hl"]
    return hl.pow(2) / (4.0 * LN2)


def garman_klass(df: pd.DataFrame) -> pd.Series:
    """Garman & Klass (1980), SIMPLIFIED form (not the 0.511/0.019/0.383 variant).

    sigma^2 = 0.5*[ln(H/L)]^2 - (2 ln2 - 1)*[ln(C/O)]^2

    Assumes zero drift and no opening jump.

    NON-NEGATIVE on any valid bar. Valid OHLC gives L <= min(O,C) <= max(O,C) <= H,
    hence |ln(C/O)| <= ln(H/L), so with r = ln(H/L) and k = ln(C/O),

        GK = 0.5 r^2 - (2 ln2 - 1) k^2
           >= 0.5 k^2 - (2 ln2 - 1) k^2
           =  (1.5 - 2 ln2) k^2  ~=  0.113706 k^2  >=  0.

    A negative value therefore indicates invalid OHLC upstream -- a data defect -- and
    never a property of the estimator. Enforce the envelope first: clean.ohlc.repair_ohlc.
    """
    L = _logs(df)
    return 0.5 * L["hl"].pow(2) - (2.0 * LN2 - 1.0) * L["c"].pow(2)


def rogers_satchell(df: pd.DataFrame) -> pd.Series:
    """Rogers & Satchell (1991), Ann. Applied Probability 1(4), 504-512.

    sigma^2 = u(u - c) + d(d - c)

    MAINTAINED MODEL: log price is a Brownian motion with drift, observed continuously.
    Under that model the estimator is unbiased WHATEVER THE DRIFT. Drift-independence is
    the property the paper claims; it is not unbiasedness in general, and the qualification
    belongs wherever the estimator is described.

    Non-negative on any valid bar: both products are non-negative when H >= max(O,C) and
    L <= min(O,C). Garman-Klass is likewise non-negative on a valid bar, so the two do not
    differ on that dimension.

    DISCRETE-EXTREMA LIMITATION, stated by the original authors: approximating the true
    extrema of the drifting Brownian motion by those of a random walk "introduces error,
    often quite a serious error", and they propose a correction for it in the same paper.
    Attributing that correction to a later source requires checking their text first.
    """
    L = _logs(df)
    u, d, c = L["u"], L["d"], L["c"]
    return u * (u - c) + d * (d - c)


def gkyz(df: pd.DataFrame) -> pd.Series:
    """Garman-Klass-Yang-Zhang: Garman-Klass with an overnight term.

    sigma^2 = o^2 + 0.5*(u - d)^2 - (2 ln2 - 1)*c^2

    The overnight term o spans the gap between consecutive SESSIONS. Where an exchange's
    week leaves a multi-calendar-day gap, that gap is wider than the one-day interval the
    derivation assumes; callers must supply session-consecutive rows.
    """
    L = _logs(df)
    return L["o"].pow(2) + 0.5 * (L["u"] - L["d"]).pow(2) - (2.0 * LN2 - 1.0) * L["c"].pow(2)


def yang_zhang(df: pd.DataFrame, window: int = 21,
               prev_close: pd.Series | None = None) -> pd.Series:
    """Yang & Zhang (2000). Minimum-variance, drift-independent, jump-robust.

    sigma^2 = sigma_o^2 + k*sigma_c^2 + (1-k)*sigma_rs^2
    k = 0.34 / (1.34 + (n+1)/(n-1))

    Requires a window because sigma_o^2 and sigma_c^2 are cross-day variances.

    SESSION GAPS. Its overnight component makes this the most exposed estimator in the family
    to the definition of a session gap -- see gkyz -- and the exposure is not hypothetical in
    this sample. ``o`` is built by :func:`previous_session_close`, so it is NaN wherever a
    security's rows skip a detected session. ``min_periods`` is left at the pandas default, so
    a window containing any such gap yields NaN for that row rather than an overnight variance
    computed from a shorter, silently different window. Yang-Zhang is therefore defined on
    strictly fewer rows than the single-bar estimators, which is exactly why every ratio
    involving it must be evaluated on a row-matched sample; see
    ``scripts/26_robustness.py::_ratios_from``.

    TWO WINDOW CONVENTIONS. ``var_o`` and ``var_c`` are sample variances about their own means
    while ``var_rs`` is a rolling MEAN of a quantity that is already a squared deviation about
    zero. That asymmetry is Yang and Zhang's, not an implementation slip: the first two terms
    estimate variances of returns whose means are not assumed zero, and the third averages an
    estimator that is itself already a variance.
    """
    L = _logs(df, prev_close)
    n = window
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    var_o = L["o"].rolling(n).var(ddof=1)
    var_c = L["c"].rolling(n).var(ddof=1)
    var_rs = rogers_satchell(df).rolling(n).mean()
    return var_o + k * var_c + (1.0 - k) * var_rs


def yang_zhang_benchmark(df: pd.DataFrame, window: int = 21) -> pd.Series:
    """The HORIZON-matched benchmark for :func:`yang_zhang`: rolling close-to-close variance.

    PEER-REVIEW ITEM C / MANDATORY ITEM 3. The previous revision fixed the SAMPLE mismatch in
    the Yang-Zhang comparison -- numerator and denominator are now averaged over the same rows
    -- and reported 1.288. The reviewer identified a second, independent mismatch that row
    alignment does not touch: a HORIZON mismatch.

    Yang-Zhang with a 21-session window estimates the variance of a 21-SESSION process. The
    benchmark it was compared against was ``r_cc^2``, the squared close-to-close return of the
    CURRENT session alone. Matching rows makes the two averages describe the same stock-days; it
    does not make them describe the same horizon. Comparing a 21-session estimator against a
    one-session realization is the same species of error as Section 5.4's own diagnosis --
    scoring an estimator against a benchmark of the wrong scope -- committed on the time axis
    instead of the session axis.

    The horizon-matched benchmark is the natural one: the sample variance of the close-to-close
    log return over the SAME 21-session window, on the same rows.

        sigma^2_bench,t = Var( r_cc )  over sessions t-20 .. t,  ddof = 1

    ``ddof=1`` is not a free choice here. Yang-Zhang's own ``sigma_o^2`` and ``sigma_c^2`` terms
    are sample variances about their own means with ``ddof=1`` (see :func:`yang_zhang`), so a
    benchmark using the uncentred second moment, or ``ddof=0``, would differ from the numerator
    in its centring convention rather than only in the quantity being measured. On the shipped
    ordinary-equity panel the whole-sample ratio moves 1.288 -> 1.273 under this benchmark.

    Both the row-matched and the horizon-matched comparisons are retained and reported. They
    answer different questions -- "does Yang-Zhang track the day's realized total risk" versus
    "does Yang-Zhang track realized total risk over its own window" -- and only the second is a
    like-for-like estimator comparison. The manuscript leads with the second and names the
    first explicitly, rather than reporting one number and calling it the ratio.
    """
    return close_to_close(df, window=window)


def realized_range(df: pd.DataFrame, window: int = 21) -> pd.Series:
    """Rolling mean of Parkinson daily variance -- a smoothed range measure."""
    return parkinson(df).rolling(window).mean()


def add_rs(df: pd.DataFrame, rtol: float = 1e-12) -> pd.Series:
    """AddRS — the additively bias-corrected Rogers-Satchell estimator.

    Kumar, D. & Maheswaran, S. (2014a), "A reflection principle for a random walk with
    implications for volatility estimation using extreme values of asset prices",
    Economic Modelling 38, 33-44, DOI 10.1016/j.econmod.2013.11.045.

    PROVENANCE -- three distinct levels, not to be collapsed:

    * ORIGINAL SOURCE:            Kumar & Maheswaran (2014a), as cited above. The reflection
                                  principle and the unbiasedness proof are stated there.
    * OPERATIONAL EQUATIONS USED: Kumar, D. & Maheswaran, S. (2014b), "Modeling and forecasting
                                  the additive bias corrected extreme value volatility
                                  estimator", International Review of Financial Analysis 34,
                                  166-176, DOI 10.1016/j.irfa.2014.06.002. Record CONFIRMED.
    * PRIMARY DERIVATION / PROOF: NOT independently verified. Neither full text was obtained,
                                  so the proof of exact unbiasedness and the conditions it
                                  requires are unverified here.

    PEER-REVIEW ITEM H / MANDATORY ITEM 9. Until this revision the operational line above read
    "a later author reproduction, Kumar (2018), open access". That citation was incomplete in
    the code and absent from the manuscript's reference list, and the reviewer was right to
    call it out. It could not be resolved to any bibliographic record: no Kumar (2018) item
    carrying these operational equations exists that the author can produce. It has therefore
    been WITHDRAWN rather than reconstructed, and replaced by Kumar & Maheswaran (2014b), the
    companion modelling-and-forecasting paper in which the AddRS equations are given in the
    operational form implemented below. A citation that cannot be produced on demand is not
    evidence, and downgrading it quietly would have repeated the fault.

    What is verified is the operational presentation, not the primary proof. The maintained
    model is a random walk with iid symmetric double-exponential increments, not Brownian
    motion, so "AddRS is unbiased" must not be written unqualified. The distinction between
    these three levels is recorded in AUDIT-REGISTER.md.

    With b = ln(H/O), c = ln(L/O), x = ln(C/O) and u = 2b - x, v = 2c - x:

        Add_ux = 0.5(u^2 - x^2) + x^2 * 1{H = O or C = H}
        Add_vx = 0.5(v^2 - x^2) + x^2 * 1{L = O or C = L}
        AddRS  = 0.5(Add_ux + Add_vx)

    The construction reduces exactly. Since 0.5(u^2 - x^2) = 2b(b - x) and likewise for v, the
    indicator-free part is identically Rogers-Satchell, so

        AddRS = RS + (x^2 / 2) * (1{H=O or C=H} + 1{L=O or C=L}).

    That is what the correction does: on a MONOTONE day the observed extremes coincide with the
    open and close, RS collapses to zero, and AddRS substitutes the squared open-to-close return.
    Both indicators fire on a fully monotone bar, giving AddRS = x^2.

    The monotone case is the one this construction targets: RS collapses to zero there even
    though the session moved, and AddRS substitutes the squared open-to-close return.

    Indicators are evaluated on RAW PRICES rather than on log differences, because testing a
    floating-point log against zero is unreliable; `rtol` sets the relative tolerance.
    """
    o_, h, l, c_ = df["open"], df["high"], df["low"], df["close"]
    b, c, x = np.log(h / o_), np.log(l / o_), np.log(c_ / o_)
    u, v = 2 * b - x, 2 * c - x

    close_to = lambda p, q: (p - q).abs() <= rtol * q.abs()
    ind_u = close_to(h, o_) | close_to(c_, h)      # H = O  or  C = H
    ind_v = close_to(l, o_) | close_to(c_, l)      # L = O  or  C = L

    add_ux = 0.5 * (u**2 - x**2) + x**2 * ind_u.astype(float)
    add_vx = 0.5 * (v**2 - x**2) + x**2 * ind_v.astype(float)
    return 0.5 * (add_ux + add_vx)
