# M14 — results, the frozen decisions, and every correction made after seeing them

This file reports what `scripts/34_instrumented_calibration.py` found when it executed the plan
frozen in `M14_CALIBRATION_ANALYSIS_PLAN.md` (committed and pushed before any real-data result
existed), applies the plan's decision rules exactly as written, and records — separately and by
name — every change made after the first results were seen. Numbers are read from the frozen
tables named in brackets; none is typed from memory.

## The verdicts, applied mechanically (`table86_m14_decisions.csv`)

| Hypothesis | Statistic | Estimate [95% interval] | Verdict |
|---|---|---|---|
| H1 | Parkinson: slope; additive share | 0.919 [0.760, 1.056]; 0.069 [−0.052, 0.203] | **no detectable attenuation** |
| H1 | Garman–Klass | 0.887 [0.668, 1.078]; 0.096 [−0.072, 0.282] | **no detectable attenuation** |
| H1 | Rogers–Satchell | 0.912 [0.650, 1.135]; 0.161 [−0.040, 0.386] | **no detectable attenuation** |
| H2 | Parkinson slope, thinnest − most active quintile | +0.082 [−0.164, +0.343] | **not detected** (point estimate reversed) |
| H3 | out-of-sample noise, composite − k (share of OC's scaled variance) | RS −0.504, GKV −0.467 (intervals below 0); OC −0.439, GK −0.161, P −0.025 (intervals include 0) | **improvement over RS and GKV; not established over OC, P, GK** |
| H4 | Parkinson slope, B − A1 and B − A2 (predicted > 0) | −0.252 [−0.421, 0.077]; −0.240 [−0.414, 0.116] | **not detected** (point estimates opposite to prediction) |
| H4 (reported) | E[c_t o_t+1]/E[P], B − A1 and B − A2 | −0.011 [−0.036, 0.016]; +0.004 [−0.045, 0.046] | not detected |
| H5 | Parkinson slope, C − A2 (predicted > 0) | −0.061 [−0.339, 0.174] | **not detected** |
| H5 (reported) | E[o_t c_t]/E[P], C − A2 (predicted < 0) | −0.365 [−0.464, −0.248] | **as predicted** |
| H6 | NIFTY 50: lagged-instrument minus India-VIX-instrument slopes, all four estimators | every interval contains 0, in both samples | **corroborated** |

Three of the six hypotheses return their pre-specified null-type verdict, and the plan's two
directional predictions from the simulation (H4, H5 on slopes) are not confirmed. That is
reported as found. What the analysis does establish is stated next.

## What the frozen analysis establishes

1. **The near-unit ratios of the range estimators are calibration, not offsetting distortion.**
   The manuscript's central claim rests on mean ratios to the open-to-close proxy. A ratio
   cannot distinguish an estimator that tracks variance from one whose multiplicative and
   additive distortions cancel; the instrumented slope can. For Parkinson, Garman–Klass and
   Rogers–Satchell every slope interval contains one, under the frozen specification and under
   every sensitivity variant (`table85`, and the post hoc `table87`: Parkinson between 0.910 and
   1.042 across seven specifications). The claim therefore survives a test it could not
   previously be put to.
2. **The thin-market bias correction and the average-price estimator overreact to volatility.**
   AddRS's ratio of 1.501 decomposes into a slope of **1.344 [1.092, 1.534]** and an additive share
   of 0.157: its overshoot of the proxy is mostly a slope problem — it rises 34% more than the
   proxy when predictable variance rises — not a constant offset. The new average-price
   estimator AP has slope **1.655 [1.276, 1.959]**. Both intervals exclude one in all four
   specifications of `table87` that carry intervals, and the point estimates stay well above one
   in every variant of `table85` (AddRS 1.343–1.566, AP 1.521–2.126).
3. **Naive statistics are not calibration.** The OLS slopes of the range estimators on the proxy
   (0.16–0.47) and their correlations with it (0.19–0.72) bear no relation to the instrumented
   slopes, exactly as the Monte Carlo predicts (`table74`).
4. **The data's own optimal quadratic is not Garman–Klass's.** The empirical best quadratic
   (`table80`) loads on the VWAP cross-terms and on ud, and puts little weight on u² and d²,
   unlike Garman and Klass's Brownian weights. The VWAP coordinate responds to variance about
   twice as strongly as Brownian motion predicts (slope of a² relative to c²: 0.665 against 1/3),
   the fingerprint of an opening price whose error scales with volatility. Out of sample the
   composite improves on Rogers–Satchell and on the Brownian-optimal GKV, but not detectably on
   Parkinson or Garman–Klass, which are therefore close to optimal for this market.
5. **The opening-band widening changed what the open measures.** Across the regimes the share of
   opening returns at the band is 28.1% (A1), 22.9% (B), 22.5% (A2) and 8.2% (C). The
   overnight–intraday reversal E[o_t c_t]/E[P] is −0.149, −0.214, −0.180 under the ±2% band and
   **−0.545** under ±5% (`table83`). The band had been censoring the open; once it widened, the
   auction price overshot and reverted within the session instead.
6. **The identification is corroborated by an economically distinct instrument.** On NIFTY 50,
   India VIX — an options-implied forecast built from information unrelated to the daily bar's
   sampling error — identifies the same slopes as the lagged realised measures (`table84`):
   excluding the 2012-10-05 flash-crash session, Parkinson 1.005 against 0.996, Garman–Klass
   1.007 against 0.995, Rogers–Satchell 0.998 against 0.988, AddRS 1.037 against 1.040. In the
   liquid market every range estimator is calibrated to the proxy; including the one flash-crash
   session moves every slope down, by 0.04–0.20 depending on estimator and instrument set — the
   same single-session leverage §10 already discloses for the trailing VIX figures.

## What the frozen analysis does not establish

* No liquidity gradient in calibration (H2). Discreteness theory predicts lower slopes in thin
  securities; the point estimate goes the other way and the interval is wide. The one quintile
  whose slopes exclude one is the **most active** (Parkinson 0.802 [0.620, 0.956]; Rogers–Satchell
  0.698 [0.402, 0.945] with additive share 0.285 [0.032, 0.572] — the masking pattern), which a
  discreteness story does not explain; the post hoc E2 below points instead at open-price noise.
* No detectable closing-rule effect (H4). The regime point estimates nonetheless form a clean
  reversal: Parkinson's slope is 0.987 (A1) and 0.975 (A2) under the last-trade close and 0.735 in
  between (B), with additive shares 0.040, 0.022 and 0.376, and the single-index model is rejected
  only in B (Parkinson J p = 0.002, against 0.571, 0.203, 0.520 in A1, A2, C). This is reported as
  a pattern, not a finding: the intervals include zero and the sign is opposite to the
  simulation's prediction, which modelled the averaged close only through averaging and bounce.
* No detectable slope change at the band reform (H5); only the cross-moment moved, strongly.
* The single-index restriction is rejected by the J test in the pooled NEPSE sample and on NIFTY,
  although its rank-one share is 0.994–0.998 and, once the additive component may differ by
  market-design regime (post hoc E1), it is no longer rejected for the range estimators
  (p = 0.154–0.175). Slopes are read throughout as linear-projection slopes on predictable
  variance, as the plan states.

## Not in the plan: post hoc, exploratory (`scripts/36_calibration_exploratory.py`)

Both were written after the frozen results were seen, because those results raised them. They
change no frozen verdict.

* **E1, security × regime fixed effects** (`table87`). Slopes barely move (Parkinson 0.920
  [0.805, 1.034] by FOD, 0.979 [0.806, 1.139] within; AddRS 1.286 and 1.412; AP 1.418 and 1.584,
  all three amplification intervals excluding one), but the range estimators' J tests stop
  rejecting — evidence that the pooled rejections came from additive components that shift with
  the market's rules.
* **E2, the share of the proxy that is transient endpoint noise** (`table88`),
  1 − E[K]/E[OC] with K the endpoint-noise kernel: 14.4% [9.8, 20.3] (A1), 23.4% [18.7, 29.2] (B),
  17.9% [7.4, 27.9] (A2) and **56.2% [46.1, 66.3]** (C). The kernel is biased upward wherever the
  band censors the open or the open is stale, so every figure is a lower bound, and the regime-C
  figure — where only 8% of opens sit at the band — is the most credible. After the reform, at
  least half of the squared open-to-close return, the benchmark this literature scores
  within-session estimators against, is transient noise that reverses within the day.

## Corrections made after the first results were seen

Each is an implementation defect, not a change of specification; each is also in
`AUDIT-REGISTER.md` (`M-001` to `M-006`).

| ID | Defect | Effect |
|---|---|---|
| M-001 | The named composite was formed over a set containing an exact linear dependency (Garman–Klass ≡ 2 ln 2·P − (2 ln 2 − 1)·OC), so its covariance was singular and the solver returned arbitrary offsetting weights (P −58.3, GK +44.0). Now formed with a pseudo-inverse over the independent set {OC, P, RS, AddRS, AP, GKV}. | The composite itself, and every efficiency bound, are unchanged to 5×10⁻¹⁰; the weights are now identified (P 2.720, OC −0.712: exactly the old weights re-expressed through the identity). |
| M-002 | The regime-difference intervals of the cross-moments took percentiles over bootstrap replicates that included undefined draws (a replicate can draw no session from the four-month regime C), returning [nan, nan] and a mechanical "not detected" for the H5 reported moment. Undefined replicates (2 of 499) are now dropped, as for every other statistic. | H5 (reported) moves from "not detected" to **"as predicted"**, −0.365 [−0.464, −0.248]. No decision-hypothesis verdict changes. |
| M-003 | For the single NIFTY series the two-way-clustered J collapses to rank one (J ≈ 0, p = 1), because the "security" cluster is the whole sample. A single series is now clustered on date. | NIFTY J statistics become informative (and reject); H6, which is stated on slope differences, is unchanged. |
| M-004 | Introduced while fixing M-001 and caught before adoption: the interval helper dropped any bootstrap replicate containing a NaN, so once GK's composite weight became NaN by design every interval in table 78 became NaN and the H1 rule fell through to a non-plan label. The helper now works element-wise. | The adopted run reproduces the first run's slopes, intervals and bounds to within 5×10⁻¹⁰. |
| M-005 | The last floating-point bits of the new CSVs varied with BLAS threading. Written at ten significant digits. | None beyond byte-reproducibility. |
| M-006 | The plan described the Monte Carlo's error under a nonlinear measurement relation as 0.02–0.03, from five replications. The full twelve-replication Monte Carlo gives +0.025 to +0.051 for the range estimators and −0.090 for AP. | Disclosed; no verdict depends on it. The error remains toward one for the range estimators, i.e. conservative for an attenuation claim. |
