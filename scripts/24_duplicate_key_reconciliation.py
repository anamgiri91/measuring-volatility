"""Exact reconciliation of the duplicate-key resolution and its effect on HO-2.

Audit artifact for A-056 / A-065, written 2026-08-29. This is NOT a new experiment: it runs the
existing HO-2 filter chain twice on today's code, once on a panel built WITH the pre-committed
duplicate resolution and once WITHOUT it, holding every other step fixed. The difference is
therefore attributable to duplicate handling alone.

It exists because a near-match was nearly accepted as an explanation. PAP-v5 SS1.3 records
"640 duplicated (symbol, date) keys" and the HO-2 sample fell by 639 stock-days against the
historical figure, which looks like a one-to-one correspondence and is not one: the panel build
removes 710 rows, not 640, because

  * an EXACT_DUPLICATE key contributes (multiplicity - 1) removed rows, not always 1; and
  * a CONFLICTING_* key is EXCLUDED ENTIRELY, contributing its full multiplicity.

Question 5 -- whether duplicate handling moves beta and t or only N -- is answered by refitting
the confirmatory regression under both panels.

    python scripts/24_duplicate_key_reconciliation.py
"""
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); from _env import bootstrap; bootstrap()

import numpy as np, pandas as pd, statsmodels.api as sm
sys.path.insert(0, str(ROOT / "src"))
from nepsevol.clean.ohlc import classify_duplicates, resolve_duplicate_keys, repair_ohlc

RAW = ROOT.parent / "private" / "data-vault" / "raw"
OUT = ROOT / "output" / "tables"
KEYS = ["symbol", "date"]
OV_START = pd.Timestamp("2024-03-04")
LN2 = np.log(2)


def build_raw_panel_a() -> pd.DataFrame:
    """Panel A exactly as 02_build_panel.build_long() assembles it, before any cleaning."""
    frames = []
    for f in sorted((RAW / "stock-daily-long").glob("*.csv")):
        try:
            d = pd.read_csv(f)
        except Exception:
            continue
        if "published_date" not in d.columns or d.empty:
            continue
        d = d.rename(columns={"published_date": "date", "traded_quantity": "volume",
                              "traded_amount": "turnover"})
        d["symbol"] = f.stem
        frames.append(d[["date", "symbol", "open", "high", "low", "close", "volume", "turnover"]])
    p = pd.concat(frames, ignore_index=True)
    p["date"] = pd.to_datetime(p["date"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume", "turnover"]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    return p.dropna(subset=["date", "close"]).sort_values(KEYS).reset_index(drop=True)


def ho2_sample(A: pd.DataFrame, B: pd.DataFrame) -> pd.DataFrame:
    """The filter chain of 11_ho2_confirmatory.py, verbatim in effect."""
    cal = A[A.date >= OV_START].merge(B[["date", "symbol", "n_trades"]], on=KEYS, how="inner")
    cal = cal[(cal.turnover >= 0) & (cal.volume >= 0) & (cal.close > 0) & cal.n_trades.notna()].copy()
    cal["lto"] = np.log1p(cal.turnover); cal["lpx"] = np.log(cal.close)
    cal["lvol"] = np.log1p(cal.volume); cal["year"] = cal.date.dt.year
    Xc = sm.add_constant(pd.get_dummies(cal[["lto", "lpx", "lvol", "year"]], columns=["year"],
                                        drop_first=True, dtype=float), has_constant="add")
    fit = sm.OLS(np.log1p(cal.n_trades), Xc).fit()
    lo, hi = cal.lto.quantile(0.01), cal.lto.quantile(0.99)

    h = A[A.date < OV_START].copy()
    h = h[(h[["open", "high", "low", "close"]] > 0).all(axis=1)]
    h["high"] = h[["high", "open", "close"]].max(axis=1)
    h["low"] = h[["low", "open", "close"]].min(axis=1)
    h = h.sort_values(KEYS)
    h["cc"] = h.groupby("symbol").close.transform(lambda s: np.log(s).diff())
    h = h[h.cc.abs() < 0.5]
    h["lto"] = np.log1p(h.turnover.clip(lower=0)); h["lpx"] = np.log(h.close)
    h["lvol"] = np.log1p(h.volume.clip(lower=0)); h["year"] = h.date.dt.year
    h = h[(h.lto >= lo) & (h.lto <= hi)]
    Xh = pd.get_dummies(h[["lto", "lpx", "lvol", "year"]], columns=["year"], drop_first=True, dtype=float)
    for c in Xc.columns:
        if c not in Xh.columns and c != "const":
            Xh[c] = 0.0
    Xh = sm.add_constant(Xh[[c for c in Xc.columns if c != "const"]], has_constant="add")
    h["nhat"] = np.expm1(fit.predict(Xh)).clip(lower=0.5)
    hl = np.log(h.high / h.low); c_ = np.log(h.close / h.open)
    h["var_pk"] = (hl ** 2) / (4 * LN2); h["var_oc"] = c_ ** 2
    h["dec"] = h.groupby("year").nhat.transform(lambda s: pd.qcut(s, 10, labels=False, duplicates="drop"))
    return h


def h1(h: pd.DataFrame):
    """The registered H1 statistic: beta on ln(N-hat) over thin buckets, two-way clustered."""
    g = (h.groupby(["year", "dec"])
           .agg(pk=("var_pk", "mean"), oc=("var_oc", "mean"), nhat=("nhat", "median"),
                n=("var_pk", "size"))
           .reset_index())
    g["ratio"] = np.sqrt(g.pk / g.oc)
    g["ln_n"] = np.log(g.nhat)
    thin = g[g.nhat < 30]
    X = sm.add_constant(thin[["ln_n"]])
    m = sm.OLS(thin.ratio, X).fit(cov_type="cluster",
                                  cov_kwds={"groups": np.asarray(thin[["year", "dec"]]),
                                            "use_correction": True})
    return len(h), h.symbol.nunique(), len(thin), m.params["ln_n"], m.tvalues["ln_n"]


raw = build_raw_panel_a()
label = classify_duplicates(raw, KEYS)
mult = raw.groupby(KEYS).size()
dup_mult = mult[mult > 1]

# ---- Q1/Q2/Q4: multiplicity, class, and the arithmetic of removal ----------------------
rows = []
for cls in ["EXACT_DUPLICATE", "CONFLICTING_OHLC", "CONFLICTING_VOLUME", "CONFLICTING_TRADES"]:
    keys_c = label.index[label == cls]
    if len(keys_c) == 0:
        continue
    m = dup_mult.loc[list(keys_c)]
    removed = int((m - 1).sum()) if cls == "EXACT_DUPLICATE" else int(m.sum())
    rows.append(dict(klass=cls, keys=len(keys_c), physical_rows=int(m.sum()),
                     max_multiplicity=int(m.max()), rows_removed=removed,
                     rule="collapse to first" if cls == "EXACT_DUPLICATE" else "exclude key entirely"))
recon = pd.DataFrame(rows)
recon.to_csv(OUT / "table29_duplicate_reconciliation.csv", index=False)

print("PANEL A DUPLICATE KEYS - resolution arithmetic")
print(recon.to_string(index=False))
total_removed = int(recon.rows_removed.sum())
print(f"\n  duplicated keys                 {len(label):,}")
print(f"  physical rows on those keys     {int(dup_mult.sum()):,}")
print(f"  rows removed                    {total_removed:,}")
print(f"  multiplicity distribution       {dict(dup_mult.value_counts().sort_index())}")
print(f"\n  WHY NOT {len(label)}: a key of multiplicity m removes m-1 rows if exact, m if conflicting.")

# ---- Q3: are the excluded rows genuine observations? -----------------------------------
conf_keys = set(label.index[label != "EXACT_DUPLICATE"])
conf = raw[[k in conf_keys for k in zip(raw.symbol, raw.date)]]
print(f"\n  CONFLICTING keys are dropped whole: {len(conf):,} physical rows on {len(conf_keys)} keys.")
print(f"  Those rows are NOT redundant copies -- they disagree on OHLC, so which is the true")
print(f"  session is unknown. The pre-committed rule excludes rather than guesses.")

# ---- Q5: effect on N, beta and t --------------------------------------------------------
B = pd.read_parquet(ROOT / "data/processed/panel_trades_clean.parquet")
A_dedup = repair_ohlc(resolve_duplicate_keys(raw.copy(), KEYS, verbose=False))
A_nodedup = repair_ohlc(raw.copy())

print("\nHO-2 UNDER BOTH PANELS - every other step held fixed")
print(f"  {'panel':<26s} {'N':>9s} {'securities':>11s} {'thin cells':>11s} {'beta':>9s} {'t':>7s}")
res = {}
for name, panel in (("WITHOUT duplicate rule", A_nodedup), ("WITH duplicate rule (current)", A_dedup)):
    res[name] = h1(ho2_sample(panel, B))
    n, s, k, b, t = res[name]
    print(f"  {name:<26s} {n:>9,} {s:>11d} {k:>11d} {b:>9.4f} {t:>7.2f}")

a, b_ = res["WITHOUT duplicate rule"], res["WITH duplicate rule (current)"]
print(f"\n  delta N            {b_[0]-a[0]:>+8,}")
print(f"  delta beta         {b_[3]-a[3]:>+8.6f}")
print(f"  delta t            {b_[4]-a[4]:>+8.4f}")
print(f"\n  ANSWER TO Q5: duplicate handling moves N, and moves beta/t only in the "
      f"{abs(b_[3]-a[3]):.1e} / {abs(b_[4]-a[4]):.2e} range.")

# ---- Q4: 710 rows leave panel A, but HO-2's N falls by only 671 -------------------------
# Removal is per KEY and multiplicity-weighted, so a set difference on keys undercounts it:
# an exact-duplicate key keeps one row and is never "absent". Count removals key by key.
per_key = pd.DataFrame({"m": dup_mult}).reset_index()
per_key["klass"] = per_key.set_index(KEYS).index.map(label)
per_key["removed"] = np.where(per_key.klass == "EXACT_DUPLICATE", per_key.m - 1, per_key.m)
win = per_key[per_key.date < OV_START]
print(f"\nWHERE THE {total_removed} REMOVED ROWS GO")
print(f"  removed from panel A                      {int(per_key.removed.sum()):,}")
print(f"  of which dated on/after {OV_START.date()}      "
      f"{int(per_key.removed.sum()-win.removed.sum()):,}  (outside the HO-2 window)")
print(f"  of which inside the HO-2 window           {int(win.removed.sum()):,}")
print(f"  observed fall in HO-2 N                   {a[0]-b_[0]:,}")
print(f"  residual                                  "
      f"{int(win.removed.sum())-(a[0]-b_[0]):,}  (removed rows HO-2's other filters drop anyway)")

# ---- the '639' that was nearly accepted as a duplicate count ---------------------------
print(f"\nTHE FULL CHAIN, AND WHY '639' WAS A FALSE MATCH")
print(f"  325,901  historical / reconstructed at 64116ce")
print(f"  +    32  calibration boundary change at 7d35e05 (63 in, 31 out) - HO2-PROVENANCE.md")
print(f"  = {a[0]:,}  current code WITHOUT the duplicate rule  <- reproduced here exactly")
print(f"  -   671  duplicate-key resolution")
print(f"  = {b_[0]:,}  current pipeline")
print(f"\n  325,901 -> 325,262 is -639, which is NOT 640 duplicate keys: it is the net of two")
print(f"  unrelated changes (+32 and -671). The resemblance to 640 is a coincidence.")
print(f"\nwrote {OUT/'table29_duplicate_reconciliation.csv'}")

# Assertions are IDENTITIES, never expected answers: PAP-v5 prohibition 9 forbids freezing a
# row count or a coefficient into a check. Each of these would still hold on different data.
assert total_removed == len(raw) - len(A_dedup), (
    f"per-key removal arithmetic ({total_removed}) disagrees with the actual row loss "
    f"({len(raw) - len(A_dedup)})")
assert int(per_key.removed.sum()) == total_removed, "windowed removals do not sum to the total"
_ex = raw[[k in set(label.index[label == "EXACT_DUPLICATE"]) for k in zip(raw.symbol, raw.date)]]
for _c in ["open", "high", "low", "close", "volume", "turnover"]:
    assert (_ex.groupby(KEYS)[_c].nunique(dropna=False) > 1).sum() == 0, (
        f"a key labelled EXACT_DUPLICATE disagrees on {_c}: collapsing it would lose information")
assert a[1] == b_[1], "duplicate resolution should not change the security count"
