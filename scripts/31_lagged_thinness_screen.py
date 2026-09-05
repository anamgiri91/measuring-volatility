"""A lagged, outcome-independent liquidity screen for the thin tail (mandatory item 4).

WHY THIS EXISTS. The thin tail in ``28_panel_balance.py`` is entered when a security's
participation falls below 90% OR its ZERO-RANGE SHARE reaches 5%. The fourth-round review is
right that the second test selects on the outcome: a zero range is exactly the event that drives
Parkinson to zero, so membership in the group is partly defined by the failure being measured,
and a low Parkinson-to-proxy ratio in that group is guaranteed by construction rather than
discovered. It also let a security with six observed sessions into the tail.

This script replaces that rule for the ROBUSTNESS claim with a screen that reads only trading
activity, and only activity that is already known:

    A stock-day t is THIN when, over the previous 60 SCHEDULED NEPSE sessions (through t-1):
        participation < 90%                                                      OR
        median trade count (conditional on trading) <= the cross-sectional 10th percentile

    Eligibility: the security must have at least 60 SCHEDULED sessions of history. The floor is
    scheduled, not traded -- a floor of 60 *traded* sessions would condition eligibility on the
    very activity being screened, reintroducing the circularity in a subtler form.

WHAT THE SCREEN DOES NOT READ. No price, no range, no return, no estimator output. Only whether
the security traded, and how many trades it made when it did. That is what makes the resulting
comparison informative about liquidity rather than about the estimator's own arithmetic.

NAMING. This is a LAGGED, OUTCOME-INDEPENDENT screen, DECLARED POST HOC and applied
consistently. It is deliberately NOT called "ex ante" or "prespecified": the thresholds were
chosen after the earlier results were known, and only the SENSITIVITY GRIDS below -- not the
authors' judgement -- protect the conclusion from that choice.

LISTING DATES. Official NEPSE listing dates are not available in this package, so the first
observed trading date is used as a proxy for the start of eligibility. It can only be weakly
conservative in one direction: a security listed before its first trade is credited with less
history than it really had, so it stays ineligible slightly longer.

Outputs
    output/tables/table55_lagged_thinness_baseline.csv     the baseline screen and its result
    output/tables/table56_lagged_thinness_grid.csv         3x3 participation x trade-count grid
    output/tables/table57_lagged_thinness_history_floor.csv 40 / 60 / 120 scheduled sessions
    output/tables/table58_lagged_thinness_components.csv   participation only / trades only / OR
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
from nepsevol.sample import load_sample
from nepsevol.estimators import range_ as R
from nepsevol.inference import ratio_of_sums_ci_block, MEAN_BLOCK
from nepsevol.equivalence import equivalence_verdict, MARGIN

TAB = ROOT / "output" / "tables"
TAB.mkdir(parents=True, exist_ok=True)

LOOKBACK = 60          # scheduled sessions in the lagged window
PARTICIPATION = 0.90   # baseline participation threshold
TRADE_TAIL = 0.10      # baseline cross-sectional trade-count tail
HISTORY_FLOOR = 60     # scheduled sessions of history required for eligibility
N_BOOT = 500

panel = load_sample(ROOT, "equity").sort_values(["symbol", "date"]).reset_index(drop=True)
cal = pd.read_csv(ROOT / "data" / "processed" / "nepse_trading_calendar.csv",
                  parse_dates=["date"]).set_index("date")
sessions = sorted(cal.index[cal.is_session.astype(bool)])
sord = {d: i for i, d in enumerate(sessions)}
T = len(sessions)

panel["v_pk"] = R.parkinson(panel)
panel["v_oc"] = np.log(panel.close / panel.open) ** 2
panel["sord"] = panel.date.map(sord)

symbols = sorted(panel.symbol.unique())
sidx = {s: i for i, s in enumerate(symbols)}
S = len(symbols)

# ── dense security x scheduled-session grids ─────────────────────────────────────────────────
traded = np.zeros((S, T), dtype=bool)
trades = np.full((S, T), np.nan)
rows_s = panel.symbol.map(sidx).to_numpy()
rows_t = panel.sord.to_numpy()
traded[rows_s, rows_t] = True
trades[rows_s, rows_t] = panel.n_trades.to_numpy(dtype=float)

first_sord = np.full(S, T, dtype=int)
np.minimum.at(first_sord, rows_s, rows_t)


def lagged_measures(lookback=LOOKBACK):
    """Participation and conditional-median trade count over the PREVIOUS ``lookback``
    scheduled sessions, i.e. using information through t-1 only."""
    part = np.full((S, T), np.nan)
    med = np.full((S, T), np.nan)
    for t in range(T):
        lo = t - lookback
        if lo < 0:
            continue
        win_traded = traded[:, lo:t]                    # excludes t itself
        part[:, t] = win_traded.mean(axis=1)
        win_trades = trades[:, lo:t]
        with np.errstate(all="ignore"):
            allnan = np.isnan(win_trades).all(axis=1)
            m = np.full(S, np.nan)
            if (~allnan).any():
                m[~allnan] = np.nanmedian(win_trades[~allnan], axis=1)
        med[:, t] = m
    return part, med


def eligibility(floor=HISTORY_FLOOR):
    """At least ``floor`` SCHEDULED sessions since first observed eligibility (listing proxy)."""
    age = np.arange(T)[None, :] - first_sord[:, None]
    return age >= floor


def build_flags(part, med, elig, participation=PARTICIPATION, trade_tail=TRADE_TAIL):
    """Thin flag per (security, session), plus the per-date cross-sectional cutoff.

    Ties at the cutoff are handled INCLUSIVELY (``<=``), so a security sitting exactly on the
    10th-percentile trade count is treated as thin rather than excluded by a strict inequality.
    """
    thin = np.zeros((S, T), dtype=bool)
    cutoffs = np.full(T, np.nan)
    for t in range(T):
        e = elig[:, t] & np.isfinite(med[:, t])
        if e.sum() < 10:
            continue
        cutoffs[t] = np.nanquantile(med[e, t], trade_tail)
        thin[:, t] = e & ((part[:, t] < participation) | (med[:, t] <= cutoffs[t]))
    return thin, cutoffs


def ratio_block(sub):
    num = sub.v_pk.to_numpy(dtype=float)
    den = sub.v_oc.to_numpy(dtype=float)
    m = np.isfinite(num) & np.isfinite(den)
    if m.sum() < 50:
        return np.nan, np.nan, np.nan
    r = float(np.sqrt(max(num[m].mean(), 0.0) / den[m].mean()))
    lo, hi = ratio_of_sums_ci_block(np.where(m, np.nan_to_num(num), 0.0),
                                    np.where(m, np.nan_to_num(den), 0.0),
                                    sub.symbol, sub.date, n_boot=N_BOOT,
                                    mean_block=MEAN_BLOCK)
    return r, lo, hi


def evaluate(thin, elig, label):
    """Attach the flag to the traded stock-days and compare thin against the rest."""
    flag = thin[rows_s, rows_t]
    eligible = elig[rows_s, rows_t]
    d = panel.assign(thin=flag, eligible=eligible)
    ev = d[d.eligible]
    out = []
    for name, sub in (("thin (lagged screen)", ev[ev.thin]),
                      ("all other eligible equity", ev[~ev.thin])):
        r, lo, hi = ratio_block(sub)
        out.append({
            "specification": label,
            "group": name,
            "n_securities": int(sub.symbol.nunique()),
            "n_stock_days": int(len(sub)),
            "share_of_eligible_pct": 100 * len(sub) / len(ev) if len(ev) else np.nan,
            "Parkinson": r, "lo95": lo, "hi95": hi,
            "verdict_vs_margin": equivalence_verdict(lo, hi),
        })
    return out, ev


print("Lagged, outcome-independent liquidity screen for the thin tail (mandatory item 4)")
print("=" * 108)
print(f"    lookback {LOOKBACK} scheduled sessions, through t-1 only; participation < "
      f"{PARTICIPATION:.0%} OR conditional-median trades <= cross-sectional "
      f"{TRADE_TAIL:.0%} tail;")
print(f"    eligibility floor {HISTORY_FLOOR} SCHEDULED sessions of history "
      "(first observed trade used as a listing-date proxy).")
print("    The screen reads no price, range, return or estimator output.")

part, med = lagged_measures()
elig = eligibility()
thin, cutoffs = build_flags(part, med, elig)
base_rows, ev = evaluate(thin, elig, "baseline (90%, bottom 10%, floor 60)")
base = pd.DataFrame(base_rows)

_flag = thin[rows_s, rows_t]
_elig = elig[rows_s, rows_t]
_pct = 100 * _flag[_elig].mean()
_excluded = int((~_elig).sum())
base["pct_of_eligible_stock_days_flagged"] = _pct
base.to_csv(TAB / "table55_lagged_thinness_baseline.csv", index=False)

print(f"\n  eligible stock-days: {int(_elig.sum()):,} of {len(panel):,} "
      f"({_excluded:,} excluded for < {HISTORY_FLOOR} scheduled sessions of history)")
print(f"  flagged thin: {_pct:.2f}% of eligible stock-days "
      f"(ties at the trade-count cutoff are included)")
print(f"  median cross-sectional trade-count cutoff across dates: "
      f"{np.nanmedian(cutoffs):.1f} trades/day")
print()
print(base[["group", "n_securities", "n_stock_days", "share_of_eligible_pct",
            "Parkinson", "lo95", "hi95", "verdict_vs_margin"]]
      .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

# ── 3x3 grid: participation x trade-count tail, history floor fixed ─────────────────────────
grid_rows = []
for p_thr in (0.80, 0.90, 0.95):
    for tail in (0.05, 0.10, 0.20):
        th, _ = build_flags(part, med, elig, participation=p_thr, trade_tail=tail)
        rows, ev_g = evaluate(th, elig, f"participation<{p_thr:.0%}, bottom {tail:.0%}")
        thin_row = rows[0]
        grid_rows.append({
            "participation_threshold": p_thr, "trade_count_tail": tail,
            "n_securities_thin": thin_row["n_securities"],
            "n_stock_days_thin": thin_row["n_stock_days"],
            "pct_of_eligible_flagged": thin_row["share_of_eligible_pct"],
            "Parkinson_thin": thin_row["Parkinson"],
            "lo95": thin_row["lo95"], "hi95": thin_row["hi95"],
            "verdict_vs_margin": thin_row["verdict_vs_margin"],
        })
grid = pd.DataFrame(grid_rows)
grid.to_csv(TAB / "table56_lagged_thinness_grid.csv", index=False)
print("\n\n3x3 sensitivity: participation threshold x trade-count tail (history floor 60)")
print("=" * 108)
print(grid.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

# ── history-floor sensitivity, other thresholds at baseline ─────────────────────────────────
floor_rows = []
for floor in (40, 60, 120):
    el = eligibility(floor)
    th, _ = build_flags(part, med, el)
    rows, ev_f = evaluate(th, el, f"history floor {floor}")
    thin_row = rows[0]
    floor_rows.append({
        "history_floor_scheduled_sessions": floor,
        "n_eligible_stock_days": int(len(ev_f)),
        "n_securities_thin": thin_row["n_securities"],
        "n_stock_days_thin": thin_row["n_stock_days"],
        "pct_of_eligible_flagged": thin_row["share_of_eligible_pct"],
        "Parkinson_thin": thin_row["Parkinson"],
        "lo95": thin_row["lo95"], "hi95": thin_row["hi95"],
        "verdict_vs_margin": thin_row["verdict_vs_margin"],
    })
floors = pd.DataFrame(floor_rows)
floors.to_csv(TAB / "table57_lagged_thinness_history_floor.csv", index=False)
print("\n\nHistory-floor sensitivity (participation 90%, bottom 10%)")
print("=" * 108)
print(floors.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

# ── component checks: each leg of the OR on its own ─────────────────────────────────────────
comp_rows = []
for label in ("participation only", "trade count only", "composite OR (baseline)"):
    th = np.zeros((S, T), dtype=bool)
    for t in range(T):
        e = elig[:, t] & np.isfinite(med[:, t])
        if e.sum() < 10:
            continue
        cut = np.nanquantile(med[e, t], TRADE_TAIL)
        by_part = part[:, t] < PARTICIPATION
        by_trade = med[:, t] <= cut
        sel = (by_part if label == "participation only"
               else by_trade if label == "trade count only"
               else (by_part | by_trade))
        th[:, t] = e & sel
    rows, _ = evaluate(th, elig, label)
    thin_row = rows[0]
    comp_rows.append({
        "component": label,
        "n_securities_thin": thin_row["n_securities"],
        "n_stock_days_thin": thin_row["n_stock_days"],
        "pct_of_eligible_flagged": thin_row["share_of_eligible_pct"],
        "Parkinson_thin": thin_row["Parkinson"],
        "lo95": thin_row["lo95"], "hi95": thin_row["hi95"],
        "verdict_vs_margin": thin_row["verdict_vs_margin"],
    })
comps = pd.DataFrame(comp_rows)
comps.to_csv(TAB / "table58_lagged_thinness_components.csv", index=False)
print("\n\nComponent checks (each leg of the OR on its own)")
print("=" * 108)
print(comps.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

_v = set(grid.verdict_vs_margin) | set(floors.verdict_vs_margin) | set(comps.verdict_vs_margin)
print(f"\n  verdicts observed across every specification above: {sorted(_v)}")
print("  -> the screen reads only trading activity known through t-1, so a low Parkinson ratio")
print("     in the thin group is a finding about liquidity rather than an arithmetic")
print("     consequence of how the group was selected. The zero-range grouping in")
print("     28_panel_balance.py is retained as a DESCRIPTIVE FAILURE-CASE INVENTORY only.")
print("\nwrote table55, table56, table57, table58")
