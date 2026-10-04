"""Monte Carlo validation of the instrumented calibration (nepsevol.calibration).

The empirical section cannot verify that the calibration slopes it reports are the right ones,
because latent variance is not observed in NEPSE. This script verifies the METHOD where the
answer is known: it simulates security x session panels of daily bars from a known latent
variance under the frictions the manuscript documents (nepsevol.estimators.microsim), runs the
identical calibration code the empirical script runs, and compares what it recovers with the
truth.

Scenarios. S0 is the Brownian benchmark (dense trading, no frictions), where Garman-Klass's own
theory should be reproduced. S1 is calibrated to DESCRIPTIVE features of the NEPSE equity panel
-- security trade-intensity quantiles (median 168, log-sd 0.97), daily volatility (median 2.4%,
cross-sectional log-sd 0.51), the stale-open share (10.6%) and the share of opens pinned at the
+/-2% band (24% before April 2026) -- with a last-trade close. S2 is S1 with NEPSE's 2025 closing
rule (VWAP of the final 1/16 of the session). S3 is S1 under the post-April-2026 rules (+/-5%
band, +/-15% limit). No scenario parameter is set from any estimator ratio, slope or other
outcome of the empirical analysis.

Outputs (output/tables/):
    table74_mc_calibration.csv      per scenario x measure: oracle slope, instrumented estimate
                                    (mean, RMSE over replications), and the naive statistics
                                    (mean ratio, OLS slope, correlation) the manuscript used
    table75_mc_composite.csv        true MSE of every estimator and of the estimated composite,
                                    the true efficiency gain, and the identified lower bound
    table76_mc_endpoint_noise.csv   the endpoint-noise kernel against truth, and the closing-rule
                                    and band-reform predictions (S1 vs S2, S1 vs S3)
    table77_bm_vwap_efficiency.csv  efficiency of the best quadratic estimators under Brownian
                                    motion, with and without the VWAP coordinate

Run time: about 10 minutes.
"""
from __future__ import annotations

from _env import bootstrap

ROOT = bootstrap()

import time
from dataclasses import asdict

import numpy as np
import pandas as pd

from nepsevol.calibration import (BLOCKS_OHLCV, bar_logs, calibrate, lagged_means,
                                  named_measures, noise_kernel, predictable_scale,
                                  quadratic_blocks)
from nepsevol.estimators.microsim import MicroParams, simulate_panel
from nepsevol.estimators.range_ import add_rs

TAB = ROOT / "output" / "tables"
TAB.mkdir(parents=True, exist_ok=True)

N_REPS = 12
BASE = dict(n_sec=150, n_days=500)
NEPSE = dict(sigma_median=0.024, sigma_disp=0.51, theta=0.6, trades_median=168.0,
             trades_disp=0.97, spread_bp_at_median=40.0, auction_noise_frac=0.25,
             band=0.02, limit=0.10, stale_open_thin=0.25, stale_open_thick=0.02)
SCENARIOS = {
    "S0_brownian": dict(trades_median=3000.0, trades_disp=0.0, gamma=0.0, spread_bp_at_median=0.0,
                        auction_noise_frac=0.0, band=None, limit=None, stale_open_thin=0.0,
                        stale_open_thick=0.0, sigma_median=0.024, sigma_disp=0.51, theta=0.6),
    "S1_nepse_last_trade": dict(NEPSE),
    "S2_nepse_vwap_close": dict(NEPSE, close_rule="vwap_tail"),
    "S3_nepse_band5_limit15": dict(NEPSE, band=0.05, limit=0.15),
}
MEASURES = ["OC", "P", "GK", "RS", "AddRS", "AP", "GKV"]
INSTR_COLS = ["OC", "P"]


def build(df: pd.DataFrame) -> pd.DataFrame:
    """Every quantity the calibration needs, from a simulated (or real) bar panel."""
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    logs = bar_logs(df, prev_close=df["prev_close"])
    blocks = quadratic_blocks(logs, with_vwap=True)
    named = named_measures(blocks)
    named["AddRS"] = add_rs(df)
    out = pd.concat([df, logs, blocks, named], axis=1)
    out["o_next"] = out.groupby("symbol")["o"].shift(-1)
    out["K"] = noise_kernel(out["c"], out["o"], out["o_next"])
    inst = lagged_means(out, INSTR_COLS, windows=(1, 5, 22), skip=1)
    out = pd.concat([out, inst], axis=1)
    out["w"] = predictable_scale(out, "P", window=22)
    return out


def oracle(frame: pd.DataFrame, cols, weights) -> dict:
    """Within-security weighted regression of each measure on TRUE intraday variance."""
    g = pd.factorize(frame["symbol"])[0]
    w = weights
    def wdm(x):
        sw = np.bincount(g, weights=w)
        mu = np.bincount(g, weights=w * x) / sw
        return x - mu[g]
    ivw = wdm(frame["iv"].to_numpy())
    out = {}
    for c in cols:
        xw = wdm(frame[c].to_numpy())
        out[c] = float((w * ivw * xw).sum() / (w * ivw * ivw).sum())
    return out, ivw, wdm


def one_rep(name: str, overrides: dict, seed: int) -> tuple[list, list, dict]:
    p = MicroParams(**{**asdict(MicroParams()), **BASE, **overrides, "seed": seed})
    d = build(simulate_panel(p))
    inst = [c for c in d.columns if "_L1m" in c]
    use = d.dropna(subset=MEASURES + inst + ["w", "iv"]).reset_index(drop=True)
    X = use[MEASURES].to_numpy()
    Z = use[inst].to_numpy()
    w = use["w"].to_numpy()
    res = calibrate(X, Z, use["symbol"], MEASURES, "OC", weights=w, date=use["date"],
                    composite_over=MEASURES)
    resb = calibrate(use[list(BLOCKS_OHLCV)].to_numpy(), Z, use["symbol"], list(BLOCKS_OHLCV),
                     "c2", weights=w, date=use["date"], composite_over=list(BLOCKS_OHLCV),
                     compute_J=False)
    # the whole-sample within transformation, kept only to measure its order-1/T bias
    resw = calibrate(X, Z, use["symbol"], MEASURES, "OC", weights=w, date=use["date"],
                     composite_over=MEASURES, transform="within", compute_J=False)

    tru, ivw, wdm = oracle(use, MEASURES + list(BLOCKS_OHLCV), w)
    b_oc = tru["OC"]
    # slope on the PREDICTABLE latent variance -- the estimand when the measurement relation is
    # nonlinear (bounce enters the range through a sqrt(IV) cross term; trade counts rise with
    # volatility), so that "the slope" on realised IV and on predictable IV need not coincide
    truV, _, _ = oracle(use.assign(iv=use["v_pred"]), MEASURES, w)
    rows = []
    for k, m in enumerate(MEASURES):
        rows.append({"scenario": name, "seed": seed, "measure": m,
                     "oracle_rel_slope": tru[m] / b_oc, "oracle_rel_slope_V": truV[m] / truV["OC"],
                     "iv_slope": res.beta[k],
                     "iv_slope_within": resw.beta[k],
                     "mean_ratio": res.ratio[k], "ols_slope": res.ols_slope[k],
                     "corr_with_ref": res.corr_with_ref[k], "J": res.J[k], "J_df": res.J_df,
                     "first_stage_F": res.first_stage_F, "rank1_share": res.rank_one_share,
                     "n_obs": res.n_obs})

    # True MSE against the reference-scaled truth T = b_OC * IV (within security), for each
    # estimator rescaled by ITS ESTIMATED slope, for the named composite and the block composite.
    T = b_oc * ivw
    sw = w.sum()
    def mse(x):
        return float((w * (x - T) ** 2).sum() / sw)
    comp = []
    Xw = np.column_stack([wdm(use[m].to_numpy()) for m in MEASURES])
    for k, m in enumerate(MEASURES):
        comp.append({"scenario": name, "seed": seed, "estimator": m,
                     "true_mse": mse(Xw[:, k] / res.beta[k]),
                     "id_eff_lb": res.bounds["eff_lb"][k], "weight": res.weights[k]})
    comp.append({"scenario": name, "seed": seed, "estimator": "composite_named",
                 "true_mse": mse(Xw @ res.weights), "id_eff_lb": np.nan, "weight": np.nan})
    Bw = np.column_stack([wdm(use[b].to_numpy()) for b in BLOCKS_OHLCV])
    # block composite is calibrated to c2 (= OC); same target
    comp.append({"scenario": name, "seed": seed, "estimator": "composite_blocks",
                 "true_mse": mse(Bw @ resb.weights), "id_eff_lb": np.nan, "weight": np.nan})
    # oracle-optimal block composite (true slopes, true noise covariance)
    bt = np.array([tru[b] for b in BLOCKS_OHLCV]) / b_oc
    U = Bw - np.outer(ivw, bt * b_oc)
    Om = (U * w[:, None]).T @ U / sw
    wo = np.linalg.solve(Om, bt)
    wo = wo / (bt @ wo)
    comp.append({"scenario": name, "seed": seed, "estimator": "oracle_blocks",
                 "true_mse": mse(Bw @ wo), "id_eff_lb": np.nan, "weight": np.nan})

    # endpoint noise and the kernel reference
    ok = use["K"].notna()
    endpoint = {
        "scenario": name, "seed": seed,
        "mean_iv": float(use.loc[ok, "iv"].mean()),
        "mean_OC_over_iv": float(use.loc[ok, "OC"].mean() / use.loc[ok, "iv"].mean()),
        "mean_K_over_iv": float(use.loc[ok, "K"].mean() / use.loc[ok, "iv"].mean()),
        "V_open_hat_over_iv": float(-(use.loc[ok, "o"] * use.loc[ok, "c"]).mean() / use.loc[ok, "iv"].mean()),
        "V_close_hat_over_iv": float(-(use.loc[ok, "c"] * use.loc[ok, "o_next"]).mean() / use.loc[ok, "iv"].mean()),
        "share_open_clamped": float(use["open_clamped"].mean()),
        "share_open_stale": float(use["open_stale"].mean()),
        "P_over_OC": float(use["P"].mean() / use["OC"].mean()),
        "iv_slope_P": float(res.beta[MEASURES.index("P")]),
        "oracle_rel_slope_P": tru["P"] / b_oc,
    }
    return rows, comp, endpoint


def bm_vwap_efficiency(n_paths: int = 400_000, n_steps: int = 64, seed: int = 12345) -> pd.DataFrame:
    """Best unbiased quadratic estimators under Brownian motion, exactly sampled.

    Extrema are drawn from the Brownian bridge between grid points and the time integral carries
    the bridge's exact Gaussian residual, so the discretisation of the simulation grid does not
    bias the extremes or the VWAP coordinate. Efficiency is relative to the squared open-to-close
    return (variance 2 sigma^4).
    """
    rng = np.random.default_rng(seed)
    h = 1.0 / n_steps
    parts = []
    for s in range(0, n_paths, 50_000):
        m = min(50_000, n_paths - s)
        inc = rng.standard_normal((m, n_steps)) * np.sqrt(h)
        W = np.concatenate([np.zeros((m, 1)), np.cumsum(inc, axis=1)], axis=1)
        x0, x1 = W[:, :-1], W[:, 1:]
        dx = x1 - x0
        bmax = (x0 + x1 + np.sqrt(dx ** 2 - 2 * h * np.log(rng.random((m, n_steps))))) / 2
        bmin = (x0 + x1 - np.sqrt(dx ** 2 - 2 * h * np.log(rng.random((m, n_steps))))) / 2
        A = ((x0 + x1) / 2).sum(axis=1) * h + rng.standard_normal((m, n_steps)).sum(axis=1) * np.sqrt(h ** 3 / 12)
        parts.append(np.column_stack([bmax.max(1), bmin.min(1), W[:, -1], A]))
    u, d, c, a = np.vstack(parts).T
    blocks = {"u2": u * u, "d2": d * d, "c2": c * c, "ud": u * d, "uc": u * c, "dc": d * c,
              "a2": a * a, "ac": a * c, "au": a * u, "ad": a * d}
    rows = []
    for label, names in [("c^2 (open-to-close)", ["c2"]),
                         ("best quadratic in (u,d)", ["u2", "d2", "ud"]),
                         ("best quadratic in (c,a)  [AP]", ["c2", "a2", "ac"]),
                         ("best quadratic in (u,d,c)  [Garman-Klass]", ["u2", "d2", "c2", "ud", "uc", "dc"]),
                         ("best quadratic in (u,d,c,a)  [GKV]", list(blocks))]:
        Q = np.column_stack([blocks[k] for k in names])
        mu = Q.mean(0)
        Sig = np.atleast_2d(np.cov(Q, rowvar=False))
        th = np.linalg.solve(Sig, mu)
        th = th / (mu @ th)
        rows.append({"estimator": label, "efficiency_vs_c2": 2.0 / float(th @ Sig @ th),
                     "weights": "; ".join(f"{k}={v:+.4f}" for k, v in zip(names, th))})
    LN2 = np.log(2)
    for label, x in [("Parkinson", (u - d) ** 2 / (4 * LN2)),
                     ("Garman-Klass simplified", 0.5 * (u - d) ** 2 - (2 * LN2 - 1) * c ** 2),
                     ("Rogers-Satchell", u * (u - c) + d * (d - c)),
                     ("AP = 2c^2 - 6ac + 6a^2", 2 * c * c - 6 * a * c + 6 * a * a)]:
        rows.append({"estimator": label, "efficiency_vs_c2": 2.0 / float(x.var()),
                     "weights": f"mean={x.mean():.4f}"})
    return pd.DataFrame(rows)


def main() -> None:
    t0 = time.time()
    print("Brownian benchmark: best quadratic estimators with and without the VWAP coordinate")
    bm = bm_vwap_efficiency()
    print(bm.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    bm.to_csv(TAB / "table77_bm_vwap_efficiency.csv", index=False)

    cal_rows, comp_rows, end_rows = [], [], []
    for si, (name, ov) in enumerate(SCENARIOS.items()):
        for rep in range(N_REPS):
            seed = 20261004 + 1000 * si + rep
            r, c, e = one_rep(name, ov, seed)
            cal_rows += r
            comp_rows += c
            end_rows.append(e)
        print(f"  {name}: {N_REPS} replications done ({time.time() - t0:.0f}s)")

    cal = pd.DataFrame(cal_rows)
    agg = (cal.assign(err=cal.iv_slope - cal.oracle_rel_slope_V,
                      err_within=cal.iv_slope_within - cal.oracle_rel_slope_V,
                      J_rej=(cal.J > pd.Series([__import__('scipy.stats', fromlist=['chi2']).chi2.ppf(0.95, d) if d > 0 else np.nan for d in cal.J_df]).values))
           .groupby(["scenario", "measure"], sort=False)
           .agg(oracle_rel_slope_IV=("oracle_rel_slope", "mean"),
                oracle_rel_slope_V=("oracle_rel_slope_V", "mean"), iv_slope_mean=("iv_slope", "mean"),
                iv_slope_rmse=("err", lambda x: float(np.sqrt(np.mean(x ** 2)))),
                iv_slope_bias=("err", "mean"), within_bias=("err_within", "mean"),
                mean_ratio=("mean_ratio", "mean"),
                ols_slope=("ols_slope", "mean"), corr_with_ref=("corr_with_ref", "mean"),
                J_reject_rate=("J_rej", "mean"), first_stage_F=("first_stage_F", "mean"),
                rank1_share=("rank1_share", "mean"), n_obs=("n_obs", "mean"))
           .reset_index())
    agg.to_csv(TAB / "table74_mc_calibration.csv", index=False)
    print("\nCalibration: oracle slope (relative to OC) vs instrumented estimate vs naive statistics")
    print(agg.drop(columns=["n_obs"]).to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    comp = pd.DataFrame(comp_rows)
    base = comp[comp.estimator == "composite_named"][["scenario", "seed", "true_mse"]].rename(columns={"true_mse": "mse_comp"})
    comp = comp.merge(base, on=["scenario", "seed"])
    comp["true_eff_of_composite"] = comp["true_mse"] / comp["mse_comp"]
    comp["lb_holds"] = comp["id_eff_lb"] <= comp["true_eff_of_composite"] + 1e-9
    cagg = (comp.groupby(["scenario", "estimator"], sort=False)
            .agg(true_mse=("true_mse", "mean"), weight=("weight", "mean"),
                 true_eff_of_composite=("true_eff_of_composite", "mean"),
                 id_eff_lb=("id_eff_lb", "mean"), lb_holds_share=("lb_holds", "mean"))
            .reset_index())
    cagg.to_csv(TAB / "table75_mc_composite.csv", index=False)
    print("\nComposite: true MSE (target b_OC * IV), true efficiency of the named composite, identified lower bound")
    print(cagg.to_string(index=False, float_format=lambda x: f"{x:.4g}"))

    end = pd.DataFrame(end_rows).groupby("scenario", sort=False).mean(numeric_only=True).reset_index()
    end.to_csv(TAB / "table76_mc_endpoint_noise.csv", index=False)
    print("\nEndpoint noise and kernel reference, by scenario (means over replications)")
    print(end.drop(columns=["seed"]).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(f"\ndone in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
