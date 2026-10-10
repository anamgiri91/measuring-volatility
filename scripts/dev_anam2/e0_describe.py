import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import *
rows = []
for name in SAMPLES:
    D = load_dev(name); d = D["d"]
    ok = d[["o", "c", "u", "d"]].notna().all(axis=1)
    x = d[ok]
    eps = 1e-12
    o_hi = (x["u"].abs() < eps); o_lo = (x["d"].abs() < eps); zr = ((x["u"] - x["d"]).abs() < eps)
    row = dict(sample=name, rows=len(x), open_is_high=o_hi.mean(), open_is_low=o_lo.mean(),
               open_extreme=(o_hi | o_lo).mean(), zero_range=zr.mean(),
               open_extreme_nonzero_range=((o_hi | o_lo) & ~zr).mean())
    if D["mode"] == "panel":
        oM = x.groupby("date")["o"].transform("mean"); rM = x.groupby("date")["r"].transform("mean")
        n = x.groupby("date")["o"].transform("size")
        oI = x["o"] - oM
        r = x["r"]
        # pooled no-intercept bivariate projection of r on (oM, oI)
        X = np.column_stack([oM, oI]); y = r.to_numpy()
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        row.update(b_pooled=float((x["o"] * r).sum() / (x["o"] ** 2).sum()), b_market=beta[0], b_idio=beta[1],
                   market_share_of_o2=float((oM ** 2).sum() / (x["o"] ** 2).sum()),
                   median_cross_section=float(n.median()))
    else:
        row.update(b_pooled=float((x["o"] * x["r"]).sum() / (x["o"] ** 2).sum()))
    rows.append(row); print(row, flush=True)
pd.DataFrame(rows).to_csv(pathlib.Path(__file__).resolve().parents[2] / "output" / "dev_anam2" / "e0_describe.csv", index=False)
