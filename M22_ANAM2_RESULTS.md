# M22 — results: Anam II, the market-implied open

**Plan.** [`M22_ANAM2_PLAN.md`](M22_ANAM2_PLAN.md) was frozen and pushed in commit `d1d7c0f` (10 October 2026), with
`nepsevol.estimators.anam2`, `scripts/52_m22_evaluation.py` and the Pakistan reader. That was before Anam II was
computed on any test row, and before any return, range or estimator was computed on the Pakistan data. The three
files' SHA-256 digests at the run equal those recorded in the plan.

**Outputs.** The script wrote `output/tables/table138`–`table141`; `scripts/53_m22_freeze.py` wrote `table142`
(Part C). Every number below is read from those tables, and the tables in this document were generated from
them. The decision rules are the plan's, applied mechanically; interpretations are labelled as such.

**Check.** M20's open-free HAR, rebuilt by M20's own code, reproduced table 127 before any comparison was made:
the test loss, the number of origins and the selected weights on every seen sample and span. Every M22 forecast
is defined on all of M20's test rows, so the comparisons below use exactly M20's rows.

**Seen and unseen.** The M20 test spans are **seen**. Anam II was never computed on them, but M20's results there
were known when it was designed. Pakistan is the one **unseen** market.

**In the paper.** Section 6.9 and Table 40 report these results (manuscript round 20,
`paper/apply_round20_revisions.py`).

---

## Summary

1. **The primary reading, P1, is "supported".** Anam II has a lower loss than M20's most accurate forecast, the
   open-free HAR, at 5 sessions in **3 of the 6 panels** after Holm's adjustment, and is worse in **none** at either
   horizon. The three are:
   * Dhaka 2023–2026 (d = −0.0163, t = −6.34);
   * Vietnam (d = −0.0078, t = −5.58);
   * **Pakistan, the market never seen in development** (d = −0.0138, t = −3.95, Holm p < 0.001).

   At 21 sessions it is better in Dhaka 2023–2026 only. In Pakistan the 21-session difference
   (d = −0.0090, t = −2.44) does not survive the adjustment (Holm p = 0.073).
2. **Most of the gain comes from the dynamics, not from the market-implied open** (H2, P2). The plan's
   measurement test holds the factor-HAR dynamics fixed and swaps Anam I's open-free kernel for Anam II's. It
   finds a detectable gain where stale prices are pervasive:
   * Dhaka 2023–2026 at both horizons;
   * Dhaka 2009–2021 at 21 sessions.

   Elsewhere it finds none, and Pakistan's differences lie inside the practical margin. Three of the five
   predictions of P2 held. The predicted gains in Morocco and Vietnam were not detected. With M20's own HAR
   dynamics the market-implied open does improve on the open-free kernel at 5 sessions in Dhaka 2023–2026,
   Vietnam and Morocco, but under the factor HAR most of that improvement is already captured (reported, no
   decision).
3. **Against the best return-only forecast** (H3), Anam II is better at 5 sessions in **5 of 6** panels, every
   panel except NEPSE, and at 21 sessions in 3 (Dhaka 2023–2026, Vietnam and Morocco).
4. **Model confidence sets.** Anam II is in the 90% set in every panel and horizon except two:
   * Vietnam at 5 sessions, where only its combination with GJR-GARCH remains;
   * NEPSE's post-reform regime C, where return-only forecasts and the combination remain, as in M20.

   In Dhaka 2023–2026 only Anam II and its combination are in the set.
5. **NEPSE.** There is no detectable difference on the primary span (A2+C). On regime C Anam II beats the
   open-free HAR (t = −3.8 at 5 sessions), but the return-only forecasts beat both, as in M20. On regime A2
   the open-free HAR has the lowest loss of the seven forecasts in the confidence sets.
6. **The indices.** With no cross-section, Anam II is the open-free kernel with a continuously fitted HAR. Its
   differences from M20's grid-fitted HAR lie inside the practical margin in all four index cells. The largest
   is the NIFTY 50 at 5 sessions: d = +0.0018 against a margin of 0.0042, with t = +3.2.

## H1 (primary): Anam II against M20's open-free HAR

d is the stock-day mean difference in canonical QLIKE (negative: Anam II better), and t is the date-clustered
t statistic (Bartlett, 2h lags). Holm's adjustment runs over the six panels at each horizon. "Inside the margin"
marks a difference whose 90% interval lies within 1% of the reference forecast's normalised QLIKE.

| Panel | h = 5: d | t | Holm p | verdict | h = 21: d | t | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|
| NEPSE (A2+C) | -0.0072 | -0.75 | 0.455 | no detectable difference | -0.0081 | -0.66 | 1.000 | no detectable difference |
| Dhaka 2023–26 | -0.0163 | -6.34 | <0.001 | better | -0.0111 | -3.57 | 0.002 | better |
| Dhaka 2009–21 | -0.0031 | -1.44 | 0.300 | no detectable difference | +0.0005 | +0.12 | 1.000 | no detectable difference |
| Vietnam | -0.0078 | -5.58 | <0.001 | better | -0.0045 | -1.89 | 0.235 | no detectable difference |
| Morocco | -0.0097 | -1.93 | 0.161 | no detectable difference | +0.0031 | +0.48 | 1.000 | no detectable difference |
| **Pakistan (unseen)** | -0.0138 | -3.95 | <0.001 | better | -0.0090 | -2.44 | 0.073 | no detectable difference |

**P1:** supported. Anam II is better at h = 5 in 3 of 6 panels, and worse in 0 of 12 panel-horizons
(table 139).

## H2 and P2: the market-implied open, with the dynamics held fixed

The comparison is Anam II against FHARL on Anam I's open-free kernel.

| Panel | h = 5: d | t | Holm p | verdict | h = 21: d | t | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|
| NEPSE (A2+C) | -0.0000 | -0.08 | 0.981 | no detectable difference (inside the margin) | -0.0000 | -0.26 | 1.000 | no detectable difference (inside the margin) |
| Dhaka 2023–26 | -0.0132 | -5.89 | <0.001 | better | -0.0077 | -2.89 | 0.019 | better |
| Dhaka 2009–21 | -0.0008 | -1.67 | 0.367 | no detectable difference (inside the margin) | -0.0025 | -3.78 | <0.001 | better |
| Vietnam | -0.0024 | -2.29 | 0.111 | no detectable difference (inside the margin) | -0.0007 | -0.52 | 1.000 | no detectable difference |
| Morocco | -0.0020 | -0.69 | 0.981 | no detectable difference | -0.0009 | -0.26 | 1.000 | no detectable difference |
| **Pakistan (unseen)** | +0.0010 | +1.69 | 0.367 | no detectable difference (inside the margin) | +0.0007 | +1.56 | 0.473 | no detectable difference (inside the margin) |

**P2** predicted "better" in Dhaka 2023–2026, Morocco and Vietnam, and "no detectable difference" in NEPSE and
Dhaka 2009–2021. Three of the five held: Dhaka 2023–2026, NEPSE and Dhaka 2009–2021. Two did not:

* Vietnam's −0.0024 (t = −2.29) does not survive Holm's adjustment and lies inside the margin;
* Morocco's −0.0020 (t = −0.69) is not detectable.

## H3: against the best return-only forecast

r\* is chosen on the training span by M20's rule. It is GJR-GARCH or GARCH in every panel and horizon except
Morocco at 5 sessions, where it is the HAR on squared returns (table 138).

| Panel | h = 5: d | t | Holm p | verdict | h = 21: d | t | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|
| NEPSE (A2+C) | -0.0003 | -0.03 | 0.977 | no detectable difference | -0.0063 | -0.33 | 0.742 | no detectable difference |
| Dhaka 2023–26 | -0.0101 | -2.95 | 0.006 | better | -0.0137 | -2.94 | 0.013 | better |
| Dhaka 2009–21 | -0.0230 | -6.11 | <0.001 | better | -0.0158 | -2.37 | 0.054 | no detectable difference |
| Vietnam | -0.0107 | -8.53 | <0.001 | better | -0.0075 | -6.16 | <0.001 | better |
| Morocco | -0.0205 | -3.97 | <0.001 | better | -0.0152 | -3.40 | 0.003 | better |
| **Pakistan (unseen)** | -0.0204 | -4.04 | <0.001 | better | -0.0191 | -2.24 | 0.054 | no detectable difference |

## Where the gain comes from (reported, no decision)

Each forecast is shown against M20's open-free HAR, as d (t), on each panel's primary span. "Continuous" means
the HAR's four weights are fitted by QLIKE, as Anam II's are, rather than chosen from M20's grid.

**5 sessions**

| Forecast | what changes from HAR-open-free | NEPSE (A2+C) | Dhaka 2023–26 | Dhaka 2009–21 | Vietnam | Morocco | Pakistan (unseen) |
|---|---|---|---|---|---|---|---|
| HAR open-free (continuous) | the fitting method | +0.0015 (+0.9) | -0.0027 (-9.0) | +0.0008 (+1.0) | -0.0001 (-0.4) | -0.0002 (-0.8) | +0.0006 (+1.2) |
| HAR MSO (continuous) | the market-implied open, M20's dynamics | +0.0013 (+0.8) | -0.0163 (-6.3) | -0.0015 (-1.5) | -0.0050 (-3.5) | -0.0081 (-2.2) | +0.0012 (+1.2) |
| FHARL open-free | the dynamics, Anam I's kernel | -0.0071 (-0.7) | -0.0032 (-7.6) | -0.0022 (-1.1) | -0.0054 (-8.2) | -0.0077 (-3.0) | -0.0148 (-4.3) |
| Anam II | both | -0.0072 (-0.7) | -0.0163 (-6.3) | -0.0031 (-1.4) | -0.0078 (-5.6) | -0.0097 (-1.9) | -0.0138 (-3.9) |
| FHARL M1 | market move on every bar | -0.0056 (-0.7) | -0.0073 (-3.2) | -0.0033 (-1.5) | -0.0086 (-6.8) | -0.0098 (-2.0) | -0.0139 (-3.8) |
| FHARL MS | market move on stale bars only | -0.0074 (-0.8) | -0.0172 (-5.8) | -0.0026 (-1.2) | -0.0069 (-4.5) | -0.0071 (-1.5) | -0.0137 (-3.9) |
| 1/2 Anam II + 1/2 GJR | the combination | -0.0182 (-1.4) | -0.0162 (-10.5) | -0.0014 (-0.8) | -0.0107 (-8.8) | -0.0064 (-1.6) | -0.0129 (-4.3) |

**21 sessions**

| Forecast | what changes from HAR-open-free | NEPSE (A2+C) | Dhaka 2023–26 | Dhaka 2009–21 | Vietnam | Morocco | Pakistan (unseen) |
|---|---|---|---|---|---|---|---|
| HAR open-free (continuous) | the fitting method | +0.0025 (+1.2) | -0.0034 (-6.5) | -0.0015 (-4.6) | +0.0005 (+1.6) | -0.0009 (-0.7) | -0.0008 (-1.2) |
| HAR MSO (continuous) | the market-implied open, M20's dynamics | +0.0024 (+1.1) | -0.0111 (-3.6) | -0.0046 (-3.6) | -0.0032 (-1.4) | +0.0003 (+0.1) | -0.0001 (-0.1) |
| FHARL open-free | the dynamics, Anam I's kernel | -0.0081 (-0.7) | -0.0034 (-6.5) | +0.0030 (+0.7) | -0.0038 (-3.2) | +0.0040 (+1.0) | -0.0097 (-2.7) |
| Anam II | both | -0.0081 (-0.7) | -0.0111 (-3.6) | +0.0005 (+0.1) | -0.0045 (-1.9) | +0.0031 (+0.5) | -0.0090 (-2.4) |
| FHARL M1 | market move on every bar | -0.0067 (-0.6) | -0.0043 (-1.7) | -0.0009 (-0.2) | -0.0046 (-2.1) | +0.0016 (+0.3) | -0.0097 (-2.7) |
| FHARL MS | market move on stale bars only | -0.0082 (-0.7) | -0.0109 (-2.8) | +0.0014 (+0.4) | -0.0038 (-1.5) | +0.0046 (+0.7) | -0.0088 (-2.4) |
| 1/2 Anam II + 1/2 GJR | the combination | -0.0131 (-0.7) | -0.0090 (-5.1) | +0.0006 (+0.2) | -0.0038 (-1.8) | +0.0059 (+1.1) | -0.0072 (-1.5) |

**Interpretation** (not a rule of the plan):

* **The fitting method changes little.** The continuously fitted HAR on the open-free kernel is close to M20's
  grid-fitted one.
* **The factor HAR with the stock's own long-run level gives most of the gain** in NEPSE, Vietnam, Morocco and
  Pakistan.
* **The market-implied open alone gives the whole gain in Dhaka 2023–2026.** That is the panel whose bars are
  most often stale (37% stale opens and 24% one-price bars on its training span, table 141).
* **The two overlap elsewhere.** The factor states also lift the forecasts of stocks whose own prices have not
  moved, which is the case the market-implied open was built for (Proposition 8(e)).

The alternatives seen in development behave as they did there:

* reading the market's move on every bar (M1) gives up most of Dhaka 2023–2026's gain;
* reading it on stale bars only (MS) is close to Anam II everywhere except Morocco at 5 sessions, where it
  gives up about a quarter of the gain.

## The model confidence sets (table 140)

Seven forecasts were included: Anam II, M20's open-free HAR, FHARL open-free, r\*, GJR, ½ Anam II + ½ GJR, and
close-to-close. The test is T_max with a stationary bootstrap of dates and 1,999 resamples.

| Sample | Span | h | In the 90% set (lowest loss first) | Anam II in it |
|---|---|---|---|---|
| NEPSE | A2+C | 5 | 1/2 Anam II + 1/2 GJR, GJR, Anam II, FHARL open-free, r* (best return-only), HAR-open-free, CC | yes |
| NEPSE | A2 | 5 | HAR-open-free, Anam II, FHARL open-free, 1/2 Anam II + 1/2 GJR, r* (best return-only), GJR, CC | yes |
| NEPSE | C | 5 | GJR, r* (best return-only), 1/2 Anam II + 1/2 GJR, CC | no |
| NEPSE | A2+C | 21 | 1/2 Anam II + 1/2 GJR, Anam II, FHARL open-free, r* (best return-only), GJR, HAR-open-free, CC | yes |
| NEPSE | A2 | 21 | HAR-open-free, Anam II, FHARL open-free, 1/2 Anam II + 1/2 GJR | yes |
| NEPSE | C | 21 | r* (best return-only), GJR, CC, 1/2 Anam II + 1/2 GJR | no |
| NIFTY50 | test half | 5 | 1/2 Anam II + 1/2 GJR, HAR-open-free, GJR, r* (best return-only), Anam II | yes |
| NIFTY50 | test half | 21 | HAR-open-free, Anam II, 1/2 Anam II + 1/2 GJR, GJR, r* (best return-only), CC | yes |
| SP500 | test half | 5 | Anam II, HAR-open-free, 1/2 Anam II + 1/2 GJR, GJR, r* (best return-only) | yes |
| SP500 | test half | 21 | Anam II, HAR-open-free, 1/2 Anam II + 1/2 GJR, CC, r* (best return-only), GJR | yes |
| DSE 2023-2026 | test half | 5 | Anam II, 1/2 Anam II + 1/2 GJR | yes |
| DSE 2023-2026 | test half | 21 | Anam II, 1/2 Anam II + 1/2 GJR | yes |
| Vietnam 2007-2020 | test half | 5 | 1/2 Anam II + 1/2 GJR | no |
| Vietnam 2007-2020 | test half | 21 | Anam II, FHARL open-free, 1/2 Anam II + 1/2 GJR | yes |
| DSE 2009-2021 | test half | 5 | Anam II, FHARL open-free, 1/2 Anam II + 1/2 GJR, HAR-open-free | yes |
| DSE 2009-2021 | test half | 21 | HAR-open-free, Anam II, 1/2 Anam II + 1/2 GJR, FHARL open-free | yes |
| Morocco 2012-2026 | test half | 5 | Anam II, FHARL open-free, 1/2 Anam II + 1/2 GJR | yes |
| Morocco 2012-2026 | test half | 21 | HAR-open-free, Anam II, FHARL open-free, 1/2 Anam II + 1/2 GJR | yes |
| Pakistan 2016-2026 | test half | 5 | FHARL open-free, Anam II, 1/2 Anam II + 1/2 GJR | yes |
| Pakistan 2016-2026 | test half | 21 | FHARL open-free, Anam II, 1/2 Anam II + 1/2 GJR, HAR-open-free, CC | yes |

## NEPSE by regime

Each cell is d (t) against M20's open-free HAR.

| Span | h | Anam II | FHARL open-free | r* (best return-only) | GJR | CC | 1/2 Anam II + 1/2 GJR |
|---|---|---|---|---|---|---|---|
| A2 | 5 | +0.0072 (+0.5) | +0.0075 (+0.5) | +0.0350 (+1.4) | +0.0379 (+1.4) | +0.0524 (+1.7) | +0.0103 (+0.6) |
| A2 | 21 | +0.0052 (+0.3) | +0.0052 (+0.3) | +0.0457 (+1.2) | +0.0457 (+1.2) | +0.0572 (+1.8) | +0.0158 (+0.6) |
| C | 5 | -0.0246 (-3.8) | -0.0249 (-3.7) | -0.0658 (-3.8) | -0.0715 (-4.7) | -0.0552 (-2.2) | -0.0578 (-6.7) |
| C | 21 | -0.0276 (-2.4) | -0.0276 (-2.4) | -0.0699 (-3.3) | -0.0699 (-3.3) | -0.0570 (-2.8) | -0.0557 (-3.9) |
| A2+C | 5 | -0.0072 (-0.7) | -0.0071 (-0.7) | -0.0068 (-0.4) | -0.0075 (-0.4) | +0.0037 (+0.2) | -0.0182 (-1.4) |
| A2+C | 21 | -0.0081 (-0.7) | -0.0081 (-0.7) | -0.0019 (-0.1) | -0.0019 (-0.1) | +0.0092 (+0.3) | -0.0131 (-0.7) |

## The two indices (series mode; reported, no decision)

| Index | h | Anam II | HAR open-free (continuous) | r* (best return-only) | 1/2 Anam II + 1/2 GJR |
|---|---|---|---|---|---|
| NIFTY 50 | 5 | +0.0018 (+3.2) | +0.0018 (+3.2) | +0.0008 (+0.1) | -0.0022 (-0.4) |
| NIFTY 50 | 21 | +0.0010 (+1.1) | +0.0010 (+1.1) | +0.0234 (+1.8) | +0.0081 (+1.2) |
| S&P 500 | 5 | -0.0008 (-1.5) | -0.0008 (-1.5) | +0.0243 (+1.2) | +0.0039 (+0.5) |
| S&P 500 | 21 | -0.0019 (-1.9) | -0.0019 (-1.9) | +0.0884 (+1.2) | +0.0251 (+1.1) |

In series mode the stock's own long-run mean of r², divided by the series' own calibration, equals the kernel's
long-run mean exactly. Both are taken over the same 250 sessions, so the two components share one weight, and
Anam II is a HAR on the open-free kernel fitted by QLIKE. All four differences lie inside the practical margin.
The margin is 1% of the reference's normalised QLIKE: 0.0042 and 0.0039 for the NIFTY 50, 0.0047 and 0.0036 for
the S&P 500.

## The test rows and the fitted weights

| Sample | h | Test origins | Dates | Zero targets | Anam II's weights |
|---|---|---|---|---|---|
| NEPSE (A2+C) | 5 | 51,660 | 208 | 0 | [0.135209, 0.215962, 0.22863, 0.339467, 0.0, 0.030731, 0.05] |
| NEPSE (A2+C) | 21 | 47,131 | 192 | 0 | [0.07195, 0.106324, 0.298461, 0.295352, 0.086891, 0.071403, 0.06962] |
| NIFTY 50 | 5 | 2,013 | 2,013 | 0 | [0.0, 0.300018, 0.381595, 0.159193, 0.159193] |
| NIFTY 50 | 21 | 1,997 | 1,997 | 0 | [0.017853, 0.257958, 0.31324, 0.017975, 0.392975] |
| S&P 500 | 5 | 2,510 | 2,510 | 0 | [0.014924, 0.379319, 0.402145, 0.101806, 0.101806] |
| S&P 500 | 21 | 2,494 | 2,494 | 0 | [0.029854, 0.399684, 0.269697, 0.002499, 0.298266] |
| Dhaka 2023–26 | 5 | 152,779 | 446 | 443 | [0.113138, 0.155935, 0.250138, 0.0, 0.0, 0.0, 0.480789] |
| Dhaka 2023–26 | 21 | 137,966 | 430 | 0 | [0.048276, 0.092017, 0.278654, 0.0, 0.0, 0.0, 0.581053] |
| Dhaka 2009–21 | 5 | 430,268 | 1,537 | 8,166 | [0.136711, 0.229849, 0.168577, 0.29117, 0.0, 0.123693, 0.05] |
| Dhaka 2009–21 | 21 | 375,353 | 1,505 | 1,517 | [0.070614, 0.162555, 0.139154, 0.334678, 0.0, 0.209173, 0.083826] |
| Vietnam | 5 | 662,880 | 1,640 | 5,165 | [0.120749, 0.240547, 0.168281, 0.223142, 0.0, 0.197281, 0.05] |
| Vietnam | 21 | 532,668 | 1,624 | 16 | [0.063662, 0.191911, 0.113156, 0.158603, 0.0, 0.422667, 0.05] |
| Morocco | 5 | 56,688 | 1,732 | 198 | [0.115519, 0.17647, 0.206622, 0.133583, 0.0, 0.107553, 0.260253] |
| Morocco | 21 | 40,275 | 1,716 | 0 | [0.055813, 0.092793, 0.20672, 0.090504, 0.0, 0.0, 0.55417] |
| Pakistan (unseen) | 5 | 112,103 | 1,233 | 10 | [0.104904, 0.173757, 0.111906, 0.337333, 0.0, 0.222099, 0.05] |
| Pakistan (unseen) | 21 | 103,888 | 1,217 | 0 | [0.056562, 0.097061, 0.118421, 0.292855, 0.0, 0.3851, 0.05] |

The weights follow the order of the components: d1, m5, m22, lr·M5, lr·M22, lrCC/κ, lr in a panel; d1, m5, m22,
lrCC/κ, lr in a series.

## The Pakistan panel (table 141)

The snapshot's 105 companies include two real estate investment trusts, a modaraba and a closed-end fund. The
equity rule leaves 101. The construction removed:

* 963 no-trade records (a non-positive price or zero volume);
* 682 envelope violations larger than PKR 0.01 (31 smaller ones were repaired);
* 5,385 bars without a previous close in the immediately preceding session, mostly the bars after a removed
  record;
* 297 bars outside the dated limit plus the margin (unadjusted corporate actions or errors);
* no dates.

That leaves 225,058 stock-days on 2,476 sessions, from 2016-10-13 to 2026-10-08. Training runs to the median
session; the test span starts on 2021-10-12, with 117,900 stock-days.

On the training span:

* the pooled b is 0.58;
* the market part of the overnight move has b_M = 1.09 and the stock-specific part b_I = 0.47;
* the market's share of the overnight second moment is 18%;
* 5.5% of opens printed at the previous close.

## Part C: the weights frozen for the prospective test (table 142)

Anam II's weights, FHARL open-free's and M20's open-free HAR's were fitted on every origin with an observed
outcome, through the last session of each sample's current data. The table records each sample's input digest.
New sessions will be scored with these weights under M21's protocol and never refitted:

* NEPSE after 2026-08-26;
* Dhaka after 2026-10-08;
* Casablanca after 2026-03-27;
* Pakistan after 2026-10-08.

## What this changes (the plan's reporting rules, applied)

P1 is "supported". By the plan, the paper and the package describe Anam II by this reading, and separately by
Pakistan's verdicts:

* **The claim.** Anam II improves on the most accurate forecast of the corrected evaluation in frontier panels.
  It is better at 5 sessions in 3 of 6 panels, including the market not used in its development, and worse in
  none.
* **The mechanism.** The improvement comes mostly from the factor-HAR dynamics with the stock's own long-run
  level. The market-implied open adds detectably only where stale prices are pervasive.
* **Single series.** The package keeps Anam's open-free model as its forecast for single series, where Anam II
  adds nothing.
* **Labels.** The seen samples are labelled seen. The development record's numbers are never quoted as evidence.

## Deviations and notes

* **None in the evaluation.** The script and modules ran as frozen.
* **Rules set after the dry run.** The plan's practical-margin rule, and P2's "a significant difference inside
  the margin counts as no difference", were added after the dry run on training rows showed a negligible but
  significant difference (NEPSE, d = 0.0004, t = 6.1). Both are in the frozen plan.
* **Round E15 was not completed.** The development record's boosted-tree round did not finish and did not inform
  the design.
* **The theory supplement.** Proposition 8 was written after the plan was frozen, while the evaluation ran. Its
  data application (table 144) reads each panel's training span, Pakistan included.
