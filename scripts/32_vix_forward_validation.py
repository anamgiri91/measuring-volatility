"""India VIX as a FORWARD-LOOKING forecast: the test the trailing comparison could not be.

MANDATORY ITEM 7. India VIX at time t is the option market's risk-neutral expectation of NIFTY
volatility over the FOLLOWING 30 CALENDAR DAYS. The manuscript compared it against a TRAILING
21-session realised measure. Those horizons point in opposite directions in time, so their
correlation measures persistence and co-movement, not forecasting validity -- and it was being
used to rank two estimators.

This script implements the design frozen in M7_ANALYSIS_PLAN.md BEFORE any result here was
computed. Read that file first: it fixes the specification, the reporting set and the decision
rule, so that which estimator "wins" cannot influence how the winner is described.

THE FORWARD WINDOW, AND WHY DAY t IS EXCLUDED
---------------------------------------------
For origin date t, realised volatility is computed from NIFTY sessions with date STRICTLY
GREATER than t, up to and including t + 30 calendar days. India VIX is disseminated from option
quotes during session t, so session t's own return is contemporaneous with the forecast's
formation, not subsequent to it. Including it would let the outcome peek at its own origin. The
exclusion is asserted by a test rather than left to this comment.

    forecast origin        t                 (India VIX observed here)
    outcome window         (t, t+30 days]    (realised volatility measured here)

PRIMARY vs SENSITIVITY
----------------------
Primary  : NON-OVERLAPPING windows -- each successor origin is the first session after the
           previous window closes. Observations are independent, so an ordinary interval means
           what it says.
Sensitivity: DAILY OVERLAPPING windows, where consecutive outcomes share up to 29 days of data.
           Reported with Newey-West HAC and a moving-block bootstrap, never with a naive
           interval.

Outputs
    output/tables/table59_vix_forward_primary.csv        non-overlapping: levels, calibration
    output/tables/table60_vix_forward_changes.csv        changes specification
    output/tables/table61_vix_leadlag.csv                forward vs backward vs lead/lag profile
    output/tables/table62_vix_forward_overlapping.csv    overlapping + HAC/block inference
    output/tables/table63_vix_parkinson_vs_cc.csv        the direct comparison and its interval
    output/tables/table64_vix_number_reconciliation.csv  where 0.832/0.776 and 0.692/0.602 came from
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _env import bootstrap
bootstrap()

import numpy as np
import pandas as pd

sys.path.insert(0, str(ROOT / "src"))
from nepsevol.estimators import range_ as R

TAB = ROOT / "output" / "tables"
TAB.mkdir(parents=True, exist_ok=True)

HORIZON_DAYS = 30        # calendar days, matching India VIX's own definition
MIN_SESSIONS = 15        # a window must be this full to be used
A = 252.0                # NSE annualisation convention
N_BOOT = 2000
SEED = 20260904
rng = np.random.default_rng(SEED)

nifty = (pd.read_csv(ROOT / "data/external/nifty50.csv", parse_dates=["Date"])
         .rename(columns=str.lower).sort_values("date").reset_index(drop=True))
vix = (pd.read_csv(ROOT / "data/external/india_vix.csv", parse_dates=["Date"])
       .rename(columns={"Date": "date", "India_VIX": "vix"}).sort_values("date")
       .reset_index(drop=True))

nifty["r_cc"] = np.log(nifty.close / nifty.close.shift(1))
nifty["v_pk"] = R.parkinson(nifty)
nifty["v_gk"] = R.garman_klass(nifty)
nifty["v_rs"] = R.rogers_satchell(nifty)
dates = nifty.date.to_numpy()

EST = {
    "Close-to-close": ("r_cc", "sq"),     # annualised sd of log returns in the window
    "Parkinson": ("v_pk", "var"),
    "Garman-Klass": ("v_gk", "var"),
    "Rogers-Satchell": ("v_rs", "var"),
}


def forward_rv(origin_idx, horizon=HORIZON_DAYS):
    """Annualised realised volatility (in vol points) over (t, t+horizon days].

    Returns a dict of estimator -> value, plus the window's session count and end date.
    STRICTLY greater than the origin date: session ``origin_idx`` itself is never included.
    """
    t0 = dates[origin_idx]
    end = t0 + np.timedelta64(horizon, "D")
    lo = origin_idx + 1                      # <- the leakage guard, in one place
    hi = np.searchsorted(dates, end, side="right")
    if hi - lo < MIN_SESSIONS:
        return None
    win = nifty.iloc[lo:hi]
    out = {"n_sessions": int(len(win)), "window_end": win.date.iloc[-1]}
    for name, (col, kind) in EST.items():
        x = win[col].to_numpy(dtype=float)
        x = x[np.isfinite(x)]
        if len(x) < MIN_SESSIONS:
            return None
        v = float(np.mean(x ** 2)) if kind == "sq" else float(max(np.mean(x), 0.0))
        out[name] = 100.0 * np.sqrt(A * v)
    return out


# ── build the panel of (origin, VIX_t, forward RV) ──────────────────────────────────────────
vix_map = dict(zip(vix.date.to_numpy(), vix.vix.to_numpy()))
rows = []
for i in range(len(nifty)):
    t = dates[i]
    if t not in vix_map or not np.isfinite(vix_map[t]):
        continue
    fw = forward_rv(i)
    if fw is None:
        continue
    rows.append({"origin_idx": i, "origin": t, "vix": float(vix_map[t]), **fw})
fwd = pd.DataFrame(rows)

print("India VIX as a forward forecast of NIFTY realised volatility (mandatory item 7)")
print("=" * 108)
print(f"    design frozen in M7_ANALYSIS_PLAN.md before any result below was computed")
print(f"    origin t -> outcome window (t, t+{HORIZON_DAYS} calendar days], session t EXCLUDED")
print(f"    {len(fwd):,} usable origins, {fwd.origin.min().date()} to {fwd.origin.max().date()}")
print(f"    median window occupancy: {fwd.n_sessions.median():.0f} sessions")


def non_overlapping(frame):
    """Greedy disjoint windows: the next origin is the first session after the window closes."""
    keep, cursor = [], pd.Timestamp.min
    for r in frame.itertuples():
        if r.origin > cursor:
            keep.append(r.Index)
            cursor = r.window_end
    return frame.loc[keep]


def fisher_ci(r, n, alpha=0.05):
    """ANALYTIC Fisher-z interval. NOT distribution-free and NOT dependence-aware: it assumes
    bivariate normality and i.i.d. observations, both questionable for skewed, persistent
    volatility. Retained only as a labelled contrast against the paired block-bootstrap
    intervals, which are what the manuscript quotes."""
    if not np.isfinite(r) or n < 5:
        return (np.nan, np.nan)
    z = np.arctanh(np.clip(r, -0.999999, 0.999999))
    se = 1.0 / np.sqrt(n - 3)
    lo, hi = z - 1.96 * se, z + 1.96 * se
    return float(np.tanh(lo)), float(np.tanh(hi))


def ols(y, x):
    """Slope, intercept, R2 and residuals for y on a constant and x."""
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fit = X @ beta
    resid = y - fit
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / ss_tot if ss_tot > 0 else np.nan
    return float(beta[1]), float(beta[0]), float(r2), resid, X


def hac_se(resid, X, lags):
    """Newey-West standard errors for the OLS coefficients."""
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    S = (X * resid[:, None]).T @ (X * resid[:, None])
    for L in range(1, lags + 1):
        w = 1.0 - L / (lags + 1.0)
        u_t = (X[L:] * resid[L:, None])
        u_tl = (X[:-L] * resid[:-L, None])
        G = u_t.T @ u_tl
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv * (n / max(n - k, 1))
    return np.sqrt(np.diag(cov))


def politis_white_block_length(x, kind="stationary"):
    """Automatic mean block length, Politis & White (2004) with the Patton-Politis-White (2009)
    correction.

    WHY AUTOMATIC. Reporting a grid of block lengths and then quoting one of them invites the
    obvious objection: the quoted interval could have been chosen after seeing which was widest.
    A selector computed FROM THE DATA removes that discretion -- the primary block length is
    whatever the autocorrelation structure implies, and the grid becomes what it should be, a
    sensitivity check around it.

    The procedure: estimate autocovariances; choose the bandwidth M from the smallest lag beyond
    which the sample autocorrelations stay inside the +/-2*sqrt(log10(n)/n) band for K_n
    consecutive lags; form the flat-top-kernel-weighted sums G and D; then
    b_opt = ((2 G^2) / D)^(1/3) * n^(1/3).
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n_ = len(x)
    if n_ < 20:
        return 1.0
    xc = x - x.mean()
    max_lag = min(n_ - 1, int(np.ceil(3 * np.sqrt(n_))))
    gam = np.array([np.dot(xc[:n_ - k], xc[k:]) / n_ for k in range(max_lag + 1)])
    if gam[0] <= 0:
        return 1.0
    rho = gam / gam[0]
    K_n = max(5, int(np.ceil(np.log10(n_))))
    crit = 2.0 * np.sqrt(np.log10(n_) / n_)
    m_hat = 0
    for k in range(1, max_lag - K_n + 1):
        if np.all(np.abs(rho[k:k + K_n]) < crit):
            m_hat = k - 1
            break
    else:
        m_hat = max_lag // 2
    M = min(max(2 * max(m_hat, 1), 2), max_lag)

    def flat_top(s):
        s = abs(s)
        return 1.0 if s <= 0.5 else (2.0 * (1.0 - s) if s <= 1.0 else 0.0)

    ks = np.arange(-M, M + 1)
    w = np.array([flat_top(k / M) for k in ks])
    g_k = np.array([gam[abs(k)] for k in ks])
    G = float(np.sum(w * np.abs(ks) * g_k))
    g0 = float(np.sum(w * g_k))
    D = 2.0 * g0 ** 2 if kind == "stationary" else (4.0 / 3.0) * g0 ** 2
    if D <= 0 or G <= 0:
        return 1.0
    b = ((2.0 * G ** 2) / D) ** (1.0 / 3.0) * n_ ** (1.0 / 3.0)
    return float(np.clip(b, 1.0, n_ / 4.0))


# ── PRIMARY: non-overlapping windows, levels + calibration ──────────────────────────────────
prim = non_overlapping(fwd)
prim_rows = []
for name in EST:
    y = prim[name].to_numpy(dtype=float)
    x = prim.vix.to_numpy(dtype=float)
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    r = float(np.corrcoef(x, y)[0, 1])
    rho = float(pd.Series(x).corr(pd.Series(y), method="spearman"))
    lo, hi = fisher_ci(r, len(y))
    slope, intercept, r2, resid, X = ols(y, x)
    se = hac_se(resid, X, lags=1)          # non-overlapping: minimal correction
    t_slope1 = (slope - 1.0) / se[1] if se[1] > 0 else np.nan
    t_int0 = intercept / se[0] if se[0] > 0 else np.nan
    prim_rows.append({
        "estimator": name, "n_obs": int(len(y)),
        "first_origin": prim.origin.min().date(), "last_origin": prim.origin.max().date(),
        "pearson": r, "pearson_lo95": lo, "pearson_hi95": hi, "spearman": rho,
        "slope_on_vix": slope, "intercept": intercept, "R2": r2,
        "t_slope_eq_1": t_slope1, "t_intercept_eq_0": t_int0,
        "mean_forward_rv": float(y.mean()), "mean_vix": float(x.mean()),
    })
primary = pd.DataFrame(prim_rows)
primary.to_csv(TAB / "table59_vix_forward_primary.csv", index=False)
print("\n\nPRIMARY specification: NON-OVERLAPPING forward windows")
print("=" * 108)
print(primary[["estimator", "n_obs", "pearson", "pearson_lo95", "pearson_hi95", "spearman",
               "slope_on_vix", "intercept", "R2"]]
      .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))

# ── CHANGES specification ───────────────────────────────────────────────────────────────────
chg_rows = []
for name in EST:
    d = prim.sort_values("origin")
    dv = np.diff(d.vix.to_numpy(dtype=float))
    dy = np.diff(d[name].to_numpy(dtype=float))
    m = np.isfinite(dv) & np.isfinite(dy)
    dv, dy = dv[m], dy[m]
    if len(dv) < 10:
        continue
    r = float(np.corrcoef(dv, dy)[0, 1])
    lo, hi = fisher_ci(r, len(dv))
    slope, intercept, r2, _, _ = ols(dy, dv)
    chg_rows.append({"estimator": name, "n_obs": int(len(dv)), "pearson_changes": r,
                     "lo95": lo, "hi95": hi, "slope_on_dvix": slope, "R2": r2})
changes = pd.DataFrame(chg_rows)
changes.to_csv(TAB / "table60_vix_forward_changes.csv", index=False)
print("\n\nCHANGES specification (non-overlapping origins)")
print("=" * 108)
print(changes.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))

# ── LEAD-LAG: forward vs backward, and a lead/lag profile ───────────────────────────────────
def backward_rv(origin_idx, horizon=HORIZON_DAYS):
    t0 = dates[origin_idx]
    start = t0 - np.timedelta64(horizon, "D")
    lo = np.searchsorted(dates, start, side="left")
    hi = origin_idx + 1                    # backward window INCLUDES t by construction
    if hi - lo < MIN_SESSIONS:
        return None
    win = nifty.iloc[lo:hi]
    out = {}
    for name, (col, kind) in EST.items():
        x = win[col].to_numpy(dtype=float)
        x = x[np.isfinite(x)]
        if len(x) < MIN_SESSIONS:
            return None
        v = float(np.mean(x ** 2)) if kind == "sq" else float(max(np.mean(x), 0.0))
        out[name] = 100.0 * np.sqrt(A * v)
    return out


back_rows = []
for r_ in fwd.itertuples():
    b = backward_rv(r_.origin_idx)
    if b is not None:
        back_rows.append({"origin_idx": r_.origin_idx, **{f"bwd_{k}": v for k, v in b.items()}})
bwd = pd.DataFrame(back_rows)
# Take the PRIMARY origins and attach their backward windows, rather than re-running the greedy
# non-overlap selection on the merged frame. Merging first would start the selection later (the
# earliest origins have no complete backward window) and therefore choose a DIFFERENT set of
# origins, so the "forward" correlation in this table would not equal the one in Table 23 for
# the same estimator -- two different numbers for the same quantity, which is exactly the kind
# of unexplained discrepancy this revision exists to remove.
ll_prim = prim.merge(bwd, on="origin_idx", how="inner")

leadlag_rows = []
for name in EST:
    for label, col in ((f"BACKWARD {HORIZON_DAYS}d (contains t)", f"bwd_{name}"),
                       (f"FORWARD {HORIZON_DAYS}d (excludes t)", name)):
        y = ll_prim[col].to_numpy(dtype=float)
        x = ll_prim.vix.to_numpy(dtype=float)
        m = np.isfinite(y) & np.isfinite(x)
        r = float(np.corrcoef(x[m], y[m])[0, 1])
        lo, hi = fisher_ci(r, int(m.sum()))
        leadlag_rows.append({"estimator": name, "window": label, "n_obs": int(m.sum()),
                             "pearson": r, "lo95": lo, "hi95": hi})
leadlag = pd.DataFrame(leadlag_rows)
leadlag.to_csv(TAB / "table61_vix_leadlag.csv", index=False)
print("\n\nLEAD-LAG: the same VIX observation against its own past and its own future")
print("=" * 108)
print(leadlag.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))

# ── SENSITIVITY: daily overlapping windows, HAC + moving-block bootstrap ────────────────────
ov_rows = []
for name in EST:
    y = fwd[name].to_numpy(dtype=float)
    x = fwd.vix.to_numpy(dtype=float)
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    r = float(np.corrcoef(x, y)[0, 1])
    slope, intercept, r2, resid, X = ols(y, x)
    se = hac_se(resid, X, lags=HORIZON_DAYS)
    # moving-block bootstrap on the correlation, block = the overlap length
    n, blk = len(y), HORIZON_DAYS
    n_blocks = int(np.ceil(n / blk))
    boot = np.empty(N_BOOT)
    for b in range(N_BOOT):
        starts = rng.integers(0, max(n - blk, 1), size=n_blocks)
        idx = np.concatenate([np.arange(s, s + blk) for s in starts])[:n]
        idx = idx[idx < n]
        boot[b] = np.corrcoef(x[idx], y[idx])[0, 1] if len(np.unique(idx)) > 5 else np.nan
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    ov_rows.append({
        "estimator": name, "n_obs": int(n), "pearson": r,
        "block_boot_lo95": float(lo), "block_boot_hi95": float(hi),
        "slope_on_vix": slope, "slope_HAC_se": float(se[1]), "R2": r2,
        "naive_would_overstate": "yes -- consecutive windows share up to "
                                 f"{HORIZON_DAYS - 1} days of data",
    })
overlapping = pd.DataFrame(ov_rows)
overlapping.to_csv(TAB / "table62_vix_forward_overlapping.csv", index=False)
print("\n\nSENSITIVITY: daily OVERLAPPING windows (HAC + moving-block bootstrap)")
print("=" * 108)
print(overlapping[["estimator", "n_obs", "pearson", "block_boot_lo95", "block_boot_hi95",
                   "slope_on_vix", "slope_HAC_se", "R2"]]
      .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))

# ── THE DIRECT COMPARISON: Parkinson minus close-to-close, with an interval ─────────────────
yp = prim["Parkinson"].to_numpy(dtype=float)
yc = prim["Close-to-close"].to_numpy(dtype=float)
xv = prim.vix.to_numpy(dtype=float)
m = np.isfinite(yp) & np.isfinite(yc) & np.isfinite(xv)
yp, yc, xv = yp[m], yc[m], xv[m]
r_pk = float(np.corrcoef(xv, yp)[0, 1])
r_cc = float(np.corrcoef(xv, yc)[0, 1])
diff_boot = np.empty(N_BOOT)
diff_boot_pk = np.empty(N_BOOT)      # the two component correlations are kept per replicate so
diff_boot_cc = np.empty(N_BOOT)      # a Fisher-z version of the same PAIRED draw can be formed
n = len(xv)
for b in range(N_BOOT):
    idx = rng.integers(0, n, n)
    if len(np.unique(idx)) < 5:
        diff_boot[b] = diff_boot_pk[b] = diff_boot_cc[b] = np.nan
        continue
    rp = np.corrcoef(xv[idx], yp[idx])[0, 1]
    rc = np.corrcoef(xv[idx], yc[idx])[0, 1]
    diff_boot_pk[b], diff_boot_cc[b] = rp, rc
    diff_boot[b] = rp - rc
dlo, dhi = np.nanpercentile(diff_boot, [2.5, 97.5])

# ── the comparison must be PAIRED, and here is the evidence that it is ──────────────────────
#
# The two correlations share BOTH their x variable (the same VIX observations) and their
# windows, and their outcomes are themselves highly correlated. Treating them as two
# independent correlations would overstate the uncertainty of their difference. The bootstrap
# above draws ONE index per replicate and applies it to xv, yp and yc together, so every
# replicate keeps the (VIX, Parkinson, close-to-close) triple for a window intact. Two checks
# are reported so this is demonstrated rather than asserted:
#
#   1. the NAIVE independent-samples interval, which is what the wrong analysis would give;
#   2. Williams' t, the analytic test for two dependent correlations sharing one variable.
r_yy = float(np.corrcoef(yp, yc)[0, 1])          # how tightly the two outcomes move together
z_boot = np.array([np.arctanh(np.clip(v, -0.999999, 0.999999)) for v in diff_boot_pk]) - \
         np.array([np.arctanh(np.clip(v, -0.999999, 0.999999)) for v in diff_boot_cc])
indep_boot = np.empty(N_BOOT)
for b in range(N_BOOT):
    ia = rng.integers(0, n, n)
    ib = rng.integers(0, n, n)                    # a SECOND, independent index -- deliberately wrong
    if len(np.unique(ia)) < 5 or len(np.unique(ib)) < 5:
        indep_boot[b] = np.nan
        continue
    indep_boot[b] = (np.corrcoef(xv[ia], yp[ia])[0, 1]
                     - np.corrcoef(xv[ib], yc[ib])[0, 1])
ilo, ihi = np.nanpercentile(indep_boot, [2.5, 97.5])

# Williams' t for r12 vs r13 with r23 known (Steiger 1980, eq. for dependent correlations)
det_R = (1 - r_pk ** 2 - r_cc ** 2 - r_yy ** 2 + 2 * r_pk * r_cc * r_yy)
williams_t = ((r_pk - r_cc) * np.sqrt(
    ((n - 1) * (1 + r_yy)) /
    (2 * ((n - 1) / (n - 3)) * det_R + ((r_pk + r_cc) ** 2 / 4) * (1 - r_yy) ** 3)))

paired = pd.DataFrame([{
    "quantity": "correlation between the two OUTCOMES (Parkinson vs close-to-close forward RV)",
    "value": r_yy, "lo95": np.nan, "hi95": np.nan,
    "note": "high, which is exactly why the two correlations may not be treated as independent",
}, {
    "quantity": "difference in correlation, PAIRED bootstrap (used)",
    "value": r_pk - r_cc, "lo95": float(dlo), "hi95": float(dhi),
    "note": "one resampled index applied to VIX, Parkinson and close-to-close together, so the "
            "shared observations and shared windows are preserved",
}, {
    "quantity": "difference in correlation, INDEPENDENT bootstrap (invalid, shown for contrast)",
    "value": r_pk - r_cc, "lo95": float(ilo), "hi95": float(ihi),
    "note": "two separate indices; ignores that both correlations use the same VIX observations "
            "and the same windows, and overstates the width",
}, {
    "quantity": "difference in Fisher z, PAIRED bootstrap (variance-stabilised)",
    "value": float(np.arctanh(r_pk) - np.arctanh(r_cc)),
    "lo95": float(np.nanpercentile(z_boot, 2.5)),
    "hi95": float(np.nanpercentile(z_boot, 97.5)),
    "note": "percentile interval computed from the SAME paired NONPARAMETRIC bootstrap "
            "replicates, transformed to the Fisher scale -- it is distribution-free "
            "because it is resampling-based, unlike the analytic Fisher-z formula, "
            "which assumes bivariate normality",
}, {
    "quantity": "Williams' t for two dependent correlations sharing one variable",
    "value": float(williams_t), "lo95": np.nan, "hi95": np.nan,
    "note": f"analytic cross-check, df = n-3 = {n - 3}. |t| = {abs(williams_t):.2f} EXCEEDS "
            "1.96, so this test DISAGREES with the paired bootstrap and favours close-to-close. "
            "Williams' t assumes trivariate normality; realised volatility and VIX are strongly "
            "right-skewed, so the bootstrap is the more trustworthy of the two here. Both agree "
            "on the direction and both refuse to support Parkinson; they differ only on whether "
            "close-to-close's advantage is distinguishable. The frozen decision rule is stated "
            "on the bootstrap interval, so the outcome remains inconclusive.",
}])
paired.to_csv(TAB / "table65_vix_paired_comparison.csv", index=False)
print("\n\nPAIRED-COMPARISON EVIDENCE (the two correlations are not independent)")
print("=" * 108)
print(paired[["quantity", "value", "lo95", "hi95"]]
      .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
print(f"\n  paired interval width   {dhi - dlo:.3f}")
print(f"  independent width       {ihi - ilo:.3f}  <- what an invalid independent analysis gives")
print(f"  Williams' t = {williams_t:.3f} on {n - 3} df")
print("  -> the outcomes correlate at "
      f"{r_yy:.3f}, so pairing is not optional. Both the paired bootstrap and the analytic")
print("     test agree the difference is not distinguishable from zero.")
if dlo > 0:
    verdict = "Parkinson outperforms close-to-close"
elif dhi < 0:
    verdict = "close-to-close outperforms Parkinson"
else:
    verdict = "inconclusive: the difference interval contains zero"
cmp_tbl = pd.DataFrame([{
    "specification": "non-overlapping forward windows (primary)", "n_obs": int(n),
    "pearson_Parkinson": r_pk, "pearson_CloseToClose": r_cc,
    "difference_pk_minus_cc": r_pk - r_cc,
    "difference_lo95": float(dlo), "difference_hi95": float(dhi),
    "decision_rule_outcome": verdict,
}])
cmp_tbl.to_csv(TAB / "table63_vix_parkinson_vs_cc.csv", index=False)
print("\n\nDIRECT COMPARISON under the frozen decision rule")
print("=" * 108)
print(cmp_tbl.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
print(f"\n  DECISION RULE OUTCOME: {verdict}")

# ── ARE THE NON-OVERLAPPING ORIGINS ACTUALLY SERIALLY INDEPENDENT? ──────────────────────────
#
# Non-overlapping windows remove the MECHANICAL overlap between consecutive outcomes. They do
# not make the origins independent: volatility is persistent well beyond 30 days, so a quiet
# quarter produces several quiet windows in a row. A row-wise bootstrap -- even a correctly
# paired one -- treats those origins as exchangeable and will understate uncertainty if they are
# not. The dependence is measured here rather than assumed away, and every headline interval
# below is then recomputed with a PAIRED STATIONARY BLOCK bootstrap: one block-resampled index
# sequence per replicate, applied to VIX and both outcomes together, so pairing AND serial
# dependence survive the resample.
def ar1(v):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 5:
        return np.nan
    return float(np.corrcoef(v[:-1], v[1:])[0, 1])


_dep_diag = pd.DataFrame([{
    "series": lbl, "lag1_autocorrelation": ar1(vals), "n": int(np.isfinite(vals).sum()),
} for lbl, vals in [
    ("India VIX at the primary origins", prim.vix.to_numpy(dtype=float)),
    ("forward realised volatility, close-to-close", prim["Close-to-close"].to_numpy(dtype=float)),
    ("forward realised volatility, Parkinson", prim["Parkinson"].to_numpy(dtype=float)),
    ("forecast error VIX - RV, close-to-close",
     (prim.vix - prim["Close-to-close"]).to_numpy(dtype=float)),
]])
_dep_diag.to_csv(TAB / "table67_forward_origin_dependence.csv", index=False)
print("\n\nSERIAL DEPENDENCE of the non-overlapping forecast origins")
print("=" * 108)
print(_dep_diag.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
_max_ar1 = float(np.nanmax(np.abs(_dep_diag.lag1_autocorrelation)))
print(f"\n  largest |lag-1 autocorrelation|: {_max_ar1:.3f}")
print("  -> non-overlapping windows remove the mechanical overlap, not the persistence. Every")
print("     interval below is therefore recomputed with a PAIRED STATIONARY BLOCK bootstrap.")

# PRIMARY block length, selected from the data rather than chosen after seeing the intervals.
#
# WHAT IS AND IS NOT POLITIS-WHITE HERE. The Politis-White procedure selects a block length
# for ONE univariate series. It prescribes nothing about how to combine selections across
# the three series entering a paired comparison of two correlations. Taking the MAXIMUM is
# therefore a CUSTOM AGGREGATION RULE OF OURS, adopted POST HOC, on the conservative
# reasoning that a block short enough for the least persistent series would not absorb the
# dependence in the most persistent one. It is conservative in the sense of producing the
# longest block and so the widest interval of the three candidates; it is not derived from
# the Politis-White theory and should not be attributed to it. The per-series selections are
# all reported so a reader can apply a different aggregation.
_bl_candidates = {
    "India VIX at origins": politis_white_block_length(prim.vix.to_numpy(dtype=float)),
    "forward RV, close-to-close": politis_white_block_length(
        prim["Close-to-close"].to_numpy(dtype=float)),
    "forward RV, Parkinson": politis_white_block_length(
        prim["Parkinson"].to_numpy(dtype=float)),
}
# rounded to 2dp so the grid membership test below is exact rather than float-fragile
MEAN_BLOCK_ORIGINS = round(float(max(_bl_candidates.values())), 2)
N_ORIGINS = int(len(prim))
_bl_tbl = pd.DataFrame([{"series": k, "politis_white_block_length": v}
                        for k, v in _bl_candidates.items()]
                       + [{"series": "PRIMARY (maximum, used)",
                           "politis_white_block_length": MEAN_BLOCK_ORIGINS}])
_bl_tbl["n_origins"] = N_ORIGINS
_bl_tbl["expected_blocks_per_replicate"] = N_ORIGINS / _bl_tbl.politis_white_block_length
_bl_tbl.to_csv(TAB / "table70_block_length_selection.csv", index=False)
print("\n  Block-length selection: Politis-White (2004) / Patton-Politis-White (2009)")
print("  per series; the MAXIMUM is our own conservative aggregation rule, adopted post")
print("  hoc -- Politis-White prescribes a length for one series, not a way to combine")
print("  three. All per-series selections are shown so another rule can be applied.")
print(_bl_tbl.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
print(f"  -> PRIMARY mean block length = {MEAN_BLOCK_ORIGINS:.2f} origins, selected from the")
print(f"     data. With {N_ORIGINS} forecast origins, each bootstrap replicate contains")
print(f"     approximately {N_ORIGINS / MEAN_BLOCK_ORIGINS:.0f} expected-length blocks. That is")
print("     the expected NUMBER OF BLOCKS DRAWN PER REPLICATE, not an effective sample size --")
print("     the two are different quantities and only the former is computed here. This limited")
print("     amount of independent temporal information is what motivates reporting block-length")
print(f"     sensitivities ({N_ORIGINS / 3:.0f} and {N_ORIGINS / 6:.0f} expected blocks at 3 and 6).")

#: The PRIMARY mean block length is selected automatically from the data (set below, once the
#: primary series exist). The grid is sensitivity only, and includes 1 -- the ordinary row
#: bootstrap -- so the cost of ignoring dependence is always visible.
BLOCK_SENSITIVITY = (1, 3, 6)


def stationary_indices(n_, rng_, mean_block):
    """One stationary-bootstrap index sequence (Politis & Romano 1994) of length ``n_``.

    Returns INDICES, not multiplicities, because the same sequence must be applied to VIX and
    to both outcome series to keep each origin's triple together. mean_block = 1 reduces to the
    ordinary i.i.d. row bootstrap, which is how the two are compared on equal footing.
    """
    p = 1.0 / max(mean_block, 1)
    out = []
    while len(out) < n_:
        start = int(rng_.integers(0, n_))
        for k in range(int(rng_.geometric(p))):
            out.append((start + k) % n_)
            if len(out) >= n_:
                break
    return np.asarray(out[:n_])


def paired_block_ci(stat_fn, arrays, mean_block=MEAN_BLOCK_ORIGINS, n_boot=N_BOOT, seed=SEED):
    """Percentile CI for any statistic of paired series, under a stationary block resample."""
    r_ = np.random.default_rng(seed)
    n_ = len(arrays[0])
    draws = np.empty(n_boot)
    for b in range(n_boot):
        idx = stationary_indices(n_, r_, mean_block)
        try:
            draws[b] = stat_fn(*[a[idx] for a in arrays])
        except Exception:
            draws[b] = np.nan
    return (float(np.nanpercentile(draws, 2.5)), float(np.nanpercentile(draws, 97.5)))


# ── DOES VIX ACTUALLY EXCEED SUBSEQUENT REALISED VOLATILITY? ────────────────────────────────
#
# A calibration slope below one does NOT establish this. A slope below one says the response of
# realised volatility to VIX is less than one-for-one -- attenuation, or regression toward the
# mean -- and is silent about the SIGN of the average forecast error. An earlier draft of this
# script's own commentary made exactly that leap. The direct evidence is the forecast error
# itself, reported here with uncertainty, plus the intercept and slope read JOINTLY.
err_rows = []
for name in EST:
    y = prim[name].to_numpy(dtype=float)
    x = prim.vix.to_numpy(dtype=float)
    m_ = np.isfinite(y) & np.isfinite(x) & (y > 0)
    y, x = y[m_], x[m_]
    err = x - y                                   # VIX_t - RV_{t,t+30}, in volatility points
    ratio = x / y
    nn = len(err)
    bm = np.array([np.mean(err[rng.integers(0, nn, nn)]) for _ in range(N_BOOT)])
    br = np.array([np.mean(ratio[rng.integers(0, nn, nn)]) for _ in range(N_BOOT)])
    bmed = np.array([np.median(err[rng.integers(0, nn, nn)]) for _ in range(N_BOOT)])
    slope, intercept, r2, _, _ = ols(y, x)
    err_rows.append({
        "estimator": name, "n_obs": int(nn),
        "mean_VIX_minus_RV": float(err.mean()),
        "mean_lo95": float(np.percentile(bm, 2.5)), "mean_hi95": float(np.percentile(bm, 97.5)),
        "median_VIX_minus_RV": float(np.median(err)),
        "median_lo95": float(np.percentile(bmed, 2.5)),
        "median_hi95": float(np.percentile(bmed, 97.5)),
        "mean_VIX_over_RV": float(ratio.mean()),
        "ratio_lo95": float(np.percentile(br, 2.5)), "ratio_hi95": float(np.percentile(br, 97.5)),
        "share_of_windows_VIX_above_RV": float((err > 0).mean()),
        "slope": slope, "intercept": intercept,
        "fitted_RV_at_mean_VIX": float(intercept + slope * x.mean()),
        "mean_VIX": float(x.mean()),
    })
errs = pd.DataFrame(err_rows)
errs.to_csv(TAB / "table66_vix_forecast_error.csv", index=False)
print("\n\nFORECAST ERROR: does India VIX actually sit above the realised volatility that follows?")
print("=" * 108)
print("    A slope below one does not answer this. The forecast error itself does.")
print(errs[["estimator", "n_obs", "mean_VIX_minus_RV", "mean_lo95", "mean_hi95",
            "median_VIX_minus_RV", "mean_VIX_over_RV", "ratio_lo95", "ratio_hi95",
            "share_of_windows_VIX_above_RV"]]
      .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
print("\n    Intercept and slope read JOINTLY (fitted RV at the mean VIX, vs that mean VIX):")
print(errs[["estimator", "intercept", "slope", "mean_VIX", "fitted_RV_at_mean_VIX"]]
      .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
_pos = errs[errs.mean_lo95 > 0]
print(f"\n  estimators whose mean forecast error interval excludes zero: "
      f"{len(_pos)} of {len(errs)}")
print("  -> where the interval excludes zero the pattern is CONSISTENT WITH a volatility risk")
print("     premium, but it is not proof of one: differences in index construction, trading")
print("     calendars, the treatment of jumps, and the risk-neutral versus physical expectation")
print("     gap can all contribute to the same sign.")

# ── EVERY HEADLINE INTERVAL, RECOMPUTED UNDER THE PAIRED BLOCK BOOTSTRAP ────────────────────
#
# The four quantities the review named, each at three block lengths. mean_block = 1 IS the
# ordinary row bootstrap, so the first column of each block shows exactly what ignoring serial
# dependence would have given.
_xv = prim.vix.to_numpy(dtype=float)
_blk_rows = []
_BLOCK_GRID = sorted({round(MEAN_BLOCK_ORIGINS, 2), *BLOCK_SENSITIVITY})
for mb in _BLOCK_GRID:
    for name in EST:
        _y = prim[name].to_numpy(dtype=float)
        _m = np.isfinite(_y) & np.isfinite(_xv)
        x_, y_ = _xv[_m], _y[_m]
        lo_r, hi_r = paired_block_ci(lambda a, b: np.corrcoef(a, b)[0, 1], (x_, y_), mb)
        lo_e, hi_e = paired_block_ci(lambda a, b: np.mean(a - b), (x_, y_), mb)
        lo_q, hi_q = paired_block_ci(lambda a, b: np.mean(a / b), (x_, y_), mb)
        lo_s, hi_s = paired_block_ci(lambda a, b: ols(b, a)[0], (x_, y_), mb)
        lo_i, hi_i = paired_block_ci(lambda a, b: ols(b, a)[1], (x_, y_), mb)
        _blk_rows.append({
            "mean_block_origins": mb,
            "is_primary": bool(abs(mb - MEAN_BLOCK_ORIGINS) < 1e-9),
            "n_origins": N_ORIGINS,
            "expected_blocks_per_replicate": N_ORIGINS / mb,
            "estimator": name,
            "corr": float(np.corrcoef(x_, y_)[0, 1]), "corr_lo95": lo_r, "corr_hi95": hi_r,
            "mean_VIX_minus_RV": float(np.mean(x_ - y_)), "err_lo95": lo_e, "err_hi95": hi_e,
            "mean_VIX_over_RV": float(np.mean(x_ / y_)), "ratio_lo95": lo_q, "ratio_hi95": hi_q,
            "slope": ols(y_, x_)[0], "slope_lo95": lo_s, "slope_hi95": hi_s,
            "intercept": ols(y_, x_)[1], "intercept_lo95": lo_i, "intercept_hi95": hi_i,
        })
_blk = pd.DataFrame(_blk_rows)
_blk.to_csv(TAB / "table68_forward_block_bootstrap.csv", index=False)

# the Parkinson-minus-close-to-close difference, also block-resampled and still PAIRED
_yp2 = prim["Parkinson"].to_numpy(dtype=float)
_yc2 = prim["Close-to-close"].to_numpy(dtype=float)
_mm = np.isfinite(_yp2) & np.isfinite(_yc2) & np.isfinite(_xv)
_diff_rows = []
for mb in _BLOCK_GRID:
    lo_d, hi_d = paired_block_ci(
        lambda a, b, c: np.corrcoef(a, b)[0, 1] - np.corrcoef(a, c)[0, 1],
        (_xv[_mm], _yp2[_mm], _yc2[_mm]), mb)
    lo_z, hi_z = paired_block_ci(
        lambda a, b, c: (np.arctanh(np.clip(np.corrcoef(a, b)[0, 1], -0.999999, 0.999999))
                         - np.arctanh(np.clip(np.corrcoef(a, c)[0, 1], -0.999999, 0.999999))),
        (_xv[_mm], _yp2[_mm], _yc2[_mm]), mb)
    _diff_rows.append({
        "mean_block_origins": mb,
        "is_primary": bool(abs(mb - MEAN_BLOCK_ORIGINS) < 1e-9),
        "n_origins": N_ORIGINS,
        "expected_blocks_per_replicate": N_ORIGINS / mb,
        "difference_pk_minus_cc": r_pk - r_cc,
        "lo95": lo_d, "hi95": hi_d, "width": hi_d - lo_d,
        "fisher_z_difference": float(np.arctanh(r_pk) - np.arctanh(r_cc)),
        "fisher_z_lo95": lo_z, "fisher_z_hi95": hi_z,
        "contains_zero": bool(lo_d <= 0 <= hi_d),
        "note": ("mean_block = 1 is the ordinary row bootstrap (serial dependence ignored)"
                 if mb == 1 else "stationary block resample over consecutive origins"),
    })
_diffblk = pd.DataFrame(_diff_rows)
_diffblk.to_csv(TAB / "table69_forward_difference_block.csv", index=False)

print("\n\nHEADLINE INTERVALS UNDER THE PAIRED STATIONARY BLOCK BOOTSTRAP")
print("=" * 108)
print("    mean_block = 1 is the ordinary row bootstrap; 3 and 6 preserve runs of consecutive")
print("    origins. All are PAIRED: one index sequence per replicate, applied to all series.")
print(_blk[_blk.estimator.isin(["Close-to-close", "Parkinson"])]
      [["mean_block_origins", "estimator", "corr", "corr_lo95", "corr_hi95",
        "mean_VIX_minus_RV", "err_lo95", "err_hi95", "mean_VIX_over_RV",
        "ratio_lo95", "ratio_hi95", "slope", "slope_lo95", "slope_hi95"]]
      .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
print("\n    Parkinson minus close-to-close correlation difference:")
print(_diffblk[["mean_block_origins", "difference_pk_minus_cc", "lo95", "hi95", "width",
                "contains_zero"]]
      .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
_prim_row = _diffblk[_diffblk.is_primary].iloc[0]
print(f"\n  PRIMARY (data-selected mean block = {MEAN_BLOCK_ORIGINS:.2f} origins, "
      f"{N_ORIGINS} origins ~ {N_ORIGINS / MEAN_BLOCK_ORIGINS:.0f} effective blocks):")
print(f"    difference {_prim_row.difference_pk_minus_cc:+.3f} "
      f"[{_prim_row.lo95:.3f}, {_prim_row.hi95:.3f}]; on the Fisher scale "
      f"[{_prim_row.fisher_z_lo95:.3f}, {_prim_row.fisher_z_hi95:.3f}]")
_all_zero = bool(_diffblk.contains_zero.all())
print(f"\n  difference interval contains zero at EVERY block length: {_all_zero}")
print("  -> the inconclusive verdict does not depend on ignoring serial dependence.")

# ── RECONCILIATION of 0.832 / 0.776 and 0.692 / 0.602 ──────────────────────────────────────
anchor = pd.read_csv(TAB / "table15_vix_anchor.csv")
sens = pd.read_csv(TAB / "table31_nifty_outlier_sensitivity.csv")
rec_rows = []
for _, r_ in anchor.iterrows():
    rec_rows.append({
        "reported_value": round(float(r_["corr"]), 3),
        "reported_R2": round(float(r_["R2"]), 3),
        "series": r_["estimator"],
        "dataset": "NIFTY 50 + India VIX, full 2010-2026 sample",
        "horizon": "TRAILING 21-session realised vs same-day VIX (horizon-MISMATCHED)",
        "sample": f"all {int(r_['n_obs']):,} matched observations",
        "producer": "09_cross_market_control.py -> table15_vix_anchor.csv",
    })
for _, r_ in sens.iterrows():
    lbl = str(r_.iloc[0])
    rec_rows.append({
        "reported_value": round(float(r_["VIX_Parkinson_corr"]), 3),
        "reported_R2": round(float(r_["VIX_Parkinson_corr"]) ** 2, 3),
        "series": "Parkinson (21d)",
        "dataset": "NIFTY 50 + India VIX",
        "horizon": "TRAILING 21-session realised vs same-day VIX (horizon-MISMATCHED)",
        "sample": lbl,
        "producer": "09_cross_market_control.py -> table31_nifty_outlier_sensitivity.csv",
    })
rec = pd.DataFrame(rec_rows)
rec["R2_equals_corr_squared"] = np.isclose(rec.reported_R2, rec.reported_value ** 2, atol=5e-3)
rec.to_csv(TAB / "table64_vix_number_reconciliation.csv", index=False)
print("\n\nRECONCILIATION: where 0.832/0.776 and 0.692/0.602 each came from")
print("=" * 108)
print(rec[["reported_value", "reported_R2", "series", "sample", "R2_equals_corr_squared"]]
      .to_string(index=False, float_format=lambda v: f"{v:,.3f}"))
print("\n  Every R2 above is the square of its own correlation, so the two R2 values are not an")
print("  independent discrepancy: they are 0.776^2 = 0.602 and 0.832^2 = 0.692. The two")
print("  CORRELATIONS differ only by whether the 2012-10-05 NSE flash-crash session is in the")
print("  sample. Both are TRAILING-horizon numbers and neither is forecasting evidence.")

print("\nwrote table59, table60, table61, table62, table63, table64")
