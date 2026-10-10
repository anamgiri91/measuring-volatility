# Anam II: the development record

This is the record of how a second generation of Anam's estimator was designed. It was written before plan M22
was frozen.

**Data.** Everything here was computed on training data only:

* NEPSE's regimes A1 and B;
* the training halves of the other six samples.

Nothing was computed on a test span of plan M20, or on the Pakistan data that plan M22 adds. The scripts are in
[`scripts/dev_anam2/`](scripts/dev_anam2/), and every result is in [`output/dev_anam2/`](output/dev_anam2/).
`ledger.csv` there lists all 195 variants, round by round.

## Why a second generation

The corrected evaluation (plan M20, `M20_CORRECTED_EVALUATION_RESULTS.md`) left two findings:

* estimating the open's coefficient b never beat setting it to zero (the open-free form);
* the most accurate forecast in most samples pairs the open-free kernel with HAR dynamics.

The open-free form ignores the open altogether. The question was whether a better reading of the open, or
better dynamics, could improve on that pair, and why reading the open through b had failed.

## How the development was run

**Folds.** NEPSE is split into its two training regimes:

* fit on A1, validate on B;
* fit on B, validate on A1.

Each other sample uses three expanding folds of its training half. Each fold fits on the dates before 40%, 60%
or 80% of the training dates and validates on the next fifth. Rounds E1 to E5 used a single split instead: fit on the first
60% of the training dates, validate on the rest. A fit uses only origins whose outcome ends before
the validation span starts.

**Target and loss.** As in M20:

* the mean squared close-to-close return over the next h exchange sessions, h = 5 and 21;
* canonical QLIKE, y/f + ln f, with zero targets scored;
* squared quantities below 1e-18 count as zero.

**Fitting.** HAR-type forecasts are convex combinations of their components. Their weights minimise QLIKE on the
fit span by constrained optimisation (SLSQP with the exact gradient). M20 instead searched a grid of 220 points.
The weight on the long-run component is at least 0.05.

**Statistics.**

* d is the stock-day mean loss difference against the round's reference forecast, averaged over folds;
  negative means the variant is better.
* t is the date-clustered t statistic (Bartlett, 2h lags), averaged over folds.
* "wins" is the number of folds in which the variant has the lower loss.

**Dhaka 2023–2026.** Its training span is the 2023 floor-price period, when 44–51% of daily returns were zero.
Loss differences there are very large and come mostly from forecasts that collapse towards zero for stocks
stuck at the floor. For that sample, read t and wins rather than d.

## What the data say about the open (round E0)

Split each overnight return o into a market part and a stock-specific part:

* o_M, the cross-sectional mean of o on the date;
* o_I = o − o_M.

Within a date the stock-specific parts sum to zero, so the two parts are exactly orthogonal in the sample. The
pooled coefficient b therefore splits exactly into a weighted mean of each part's own coefficient:

    b = μ · b_M + (1 − μ) · b_I,     μ = Σ o_M² / Σ o²   (the market's share of the overnight second moment)

| Sample | Bars | Open = high or low | One-price bars | b (pooled) | b_M (market part) | b_I (stock part) | Market share of o² | μ·b_M + (1−μ)·b_I |
|---|---|---|---|---|---|---|---|---|
| Nepal | 86,675 | 35.9% | 0.1% | 0.279 | 0.907 | 0.200 | 11.3% | 0.279 |
| Dhaka 2023-26 | 141,187 | 55.8% | 24.5% | 0.371 | 0.635 | 0.326 | 14.5% | 0.371 |
| Dhaka 2009-21 | 349,915 | 39.1% | 1.6% | 0.550 | 0.954 | 0.446 | 20.5% | 0.550 |
| Vietnam | 616,635 | 71.2% | 13.7% | 0.592 | 1.004 | 0.515 | 15.7% | 0.592 |
| Morocco | 50,350 | 75.7% | 26.7% | 0.707 | 0.779 | 0.702 | 5.9% | 0.707 |
| NIFTY 50 | 2,018 | 5.8% | 0.0% | 0.897 | | | | |
| S&P 500 | 2,515 | 29.9% | 0.0% | 4.018 | | | | |

The session keeps the market part of the overnight move almost entirely: b_M is between 0.64 and 1.00. It
reverses most of the stock-specific part: b_I is between 0.20 and 0.70. The market part is only 6–21% of the
overnight second moment, so the pooled b is close to b_I.

One coefficient therefore shrinks a reliable component, the market's, by the unreliable component's factor.
That is why reading the open through b did not beat ignoring it. It also suggests reading the market part of the
open, and only that. The market's move can be measured from the other stocks' opens, without the stock's own
opening error: the leave-one-out mean o_M,−i.

## The rounds

| Round | Question | What was tried | What happened |
|---|---|---|---|
| E1 | Read the open by component; drop extremes set by the opening print | the two-component open b_M·o_M + b_I·o_I; excluding an opening-print extreme; HAR and φ dynamics; one 60/40 split | the two-component open with exclusion helped Dhaka 2023–26 and Morocco, and was neutral elsewhere; exclusion anchored at the previous close hurt |
| E3 | Dynamics with a market state | factor HAR: the stock's long-run level times the cross-sectional median of m5/lr and m22/lr; ½ with GJR-GARCH | the factor HAR helped Nepal, Vietnam, Dhaka 2009–21 and Morocco at 5 sessions; ½ with GJR helped Vietnam and hurt Nepal at 21 |
| E4 | Kernel details under HAR | blend w from 0.1 to 0.4; no range extension; market anchors; the one-price divisor | a market anchor helped Dhaka 2023–26 strongly; Vietnam preferred w = 0.4; the one-price divisor helped slightly |
| E5 | Other dynamics (Nepal, Morocco) | leverage HAR; multi-measure HAR; a fitted combination with GJR; weights by liquidity tercile | all worse in Nepal; the multi-measure HAR helped Morocco only |
| E6 | Consolidation with expanding folds | the best kernels of E1–E4 with HAR and factor HAR | the factor HAR added 0.002 to 0.012; the market anchor helped Dhaka 2023–26 and Morocco |
| E7 | Factorial | open {none, market, market + b_I·stock, two-component} × exclusion {off, on} × w {0.2, 0.3, 0.4}, and a self-tuned choice | exclusion rarely helped; the market anchor was best in Morocco and Dhaka 2023–26; the self-tuned choice flipped between Nepal's regimes |
| E8 | The system end to end | self-tuned market weight θ ∈ {0, ½, 1} and w; factor HAR; ½ with the best return-only forecast | the factor HAR on the market-implied kernel beat the open-free HAR in 4 of 5 panels; self-tuning was unstable |
| E9 | Range-GARCH (HEAVY) | variance-targeted GJR-GARCH with the calibrated kernel as a second shock (315-point grid) | no better than the factor HAR in panels, nor than GJR on the indices |
| E10 | How the market move should enter (factor HAR) | full move (M1); move × pooled b_M (BM); market overnight term without the range extension (M1N); market move on stale bars only (MS); w | M1 was best in Morocco and Dhaka 2023–26; BM was worse (attenuated); M1N was much worse; MS kept almost all of the Dhaka 2023–26 gain; Vietnam preferred no market move |
| E11 | How to estimate the market move | bias-corrected square; mean over active stocks only; leave-one-out median; the market's whole bar on stale bars | none beat the plain leave-one-out mean consistently |
| E12 | Refining the factor HAR | a one-day market state; mean instead of median; long run of 125 sessions; calibration over 20 or 120 dates; no own d1 | none better |
| E13 | Stock-specific exposure | the stock's own projection of r on o_M, shrunk; the same relative to the pooled one | worse than the full move: stale stocks have attenuated betas, yet their later returns realise the market's move |
| E14 | The level across stocks | the stock's own calibration, shrunk; the stock's own long-run mean of r² as a HAR component (lrCC) | the stock-level calibration hurt Nepal badly; lrCC helped Vietnam and Dhaka 2009–21 and was neutral elsewhere |
| E15 | A different model class | gradient-boosted trees on 26 bar features, Poisson and gamma deviance, fixed hyperparameters | see below |
| E16 | The final candidates | kernels {open-free, M1, MS, MSO} × dynamics {HAR, factor HAR, factor HAR + lrCC}; return-only forecasts; ½ with GJR | see the next section |

**The simulation** (`sim_m1.py`). The simulated panel has:

* a market factor;
* stochastic volatility;
* an opening error;
* heterogeneous betas;
* stale stocks.

It reproduced the pattern:

* the market-implied open helps with stale stocks, and with similar betas;
* it costs a little when betas differ widely;
* applied to stale bars only, it never costs anything.

**The Vietnam diagnostic** (`diag_vn.py`). The full market move lost in Vietnam's first fold, mostly in the
second quarter of 2010. It over-predicted low-volatility stocks: their forecasts rose by up to 28%, while their
realised variance was the lowest.

## The final comparison (round E16)

Each cell shows d against the open-free HAR (M20's most accurate forecast), with t in parentheses. Every
candidate uses the blend w = 0.2 and the one-price divisor.

The kernels:

* **MSO** reads the market's overnight move only where the stock's own open printed exactly at the previous
  close (a stale open).
* **M1** reads it on every bar.
* **MS** reads it only on bars with no price change at all.

The forecasts:

* **FHARL** is the factor HAR with the stock's own long-run mean of r².
* **r\*** is the best return-only forecast, chosen by fit-span loss.

5 sessions:

| Forecast | Nepal | Dhaka 23-26 | Dhaka 09-21 | Vietnam | Morocco | NIFTY 50 | S&P 500 |
|---|---|---|---|---|---|---|---|
| FHARL-MSO | -0.0125 (-1.8) | -1.53 (-3.4) | -0.0089 (-2.4) | -0.0078 (-3.5) | -0.0143 (-1.5) |  |  |
| FHARL-M1 | -0.0132 (-1.7) | -1.53 (-3.3) | -0.0072 (-1.8) | -0.0047 (-2.1) | -0.0156 (-1.3) |  |  |
| FHARL-MS | -0.0124 (-1.7) | -1.53 (-3.5) | -0.0088 (-2.4) | -0.0082 (-3.7) | -0.0102 (-1.0) |  |  |
| FHARL-OF | -0.0124 (-1.7) | +1.19 (-2.8) | -0.0084 (-2.3) | -0.0049 (-3.2) | -0.0104 (-1.7) |  |  |
| FHAR-OF | -0.0125 (-1.8) | +1.19 (-2.8) | -0.0071 (-1.7) | -0.0030 (-1.9) | -0.0022 (-0.4) |  |  |
| HAR-MSO | -0.0003 (-1.6) | -1.60 (-3.5) | -0.0016 (-2.8) | -0.0045 (-2.4) | -0.0144 (-2.0) |  |  |
| ½ FHARL-MSO + ½ GJR | -0.0053 (-1.5) | -1.40 (-3.6) | -0.0080 (-2.6) | -0.0114 (-6.5) | -0.0151 (-1.5) |  |  |
| r* | +0.0152 (+1.0) | +3.42 (+2.4) | +0.0065 (+0.9) | -0.0046 (-1.6) | -0.0040 (-0.4) | -0.0283 (-1.0) | -0.0147 (-1.1) |
| GJR | +0.0245 (+1.8) | +1.08 (-0.1) | +0.0067 (+1.1) | -0.0031 (-1.2) | -0.0018 (-0.2) | -0.0283 (-1.0) | -0.0147 (-1.1) |
| HARL-OF (series) |  |  |  |  |  | -0.0000 (-0.3) | +0.0000 (+0.5) |
| ½ HARL-OF + ½ GJR |  |  |  |  |  | -0.0245 (-1.5) | -0.0117 (-2.0) |

21 sessions:

| Forecast | Nepal | Dhaka 23-26 | Dhaka 09-21 | Vietnam | Morocco | NIFTY 50 | S&P 500 |
|---|---|---|---|---|---|---|---|
| FHARL-MSO | -0.0055 (-1.1) | -1.49 (-6.0) | -0.0042 (-0.8) | -0.0054 (-2.2) | -0.0152 (-1.1) |  |  |
| FHARL-M1 | -0.0068 (-1.1) | -1.50 (-6.9) | -0.0046 (-1.2) | -0.0036 (-1.3) | -0.0161 (-0.9) |  |  |
| FHARL-MS | -0.0054 (-1.1) | -1.48 (-5.9) | -0.0038 (-0.7) | -0.0055 (-2.3) | -0.0107 (-0.7) |  |  |
| FHARL-OF | -0.0054 (-1.1) | +1.26 (-3.4) | -0.0040 (-0.8) | -0.0039 (-2.4) | -0.0079 (-0.9) |  |  |
| FHAR-OF | -0.0054 (-1.1) | +1.26 (-3.9) | -0.0026 (-0.8) | -0.0011 (-0.9) | -0.0000 (+0.1) |  |  |
| HAR-MSO | -0.0002 (+0.1) | -1.57 (-5.5) | -0.0014 (-1.6) | -0.0031 (-1.1) | -0.0173 (-1.5) |  |  |
| ½ FHARL-MSO + ½ GJR | +0.0219 (+0.9) | -1.30 (-5.4) | -0.0035 (-0.6) | -0.0066 (-2.6) | -0.0127 (-0.8) |  |  |
| r* | +0.0437 (+1.6) | +4.21 (+2.9) | +0.0116 (+1.0) | -0.0016 (-0.4) | +0.0018 (+0.0) | -0.0349 (-0.8) | -0.0165 (-1.1) |
| GJR | +0.0821 (+3.0) | +1.77 (-0.3) | +0.0081 (+1.1) | -0.0020 (-0.6) | +0.0014 (+0.0) | -0.0349 (-0.8) | -0.0165 (-1.1) |
| HARL-OF (series) |  |  |  |  |  | +0.0000 (-0.1) | +0.0000 (+0.4) |
| ½ HARL-OF + ½ GJR |  |  |  |  |  | -0.0256 (-1.2) | -0.0123 (-1.7) |

**What the comparison shows.**

* FHARL-MSO is never far from the best candidate in any panel, and has a lower loss than the open-free HAR in
  every panel at both horizons.
* M1 does better in Nepal and Morocco but loses Vietnam's gain.
* MS gives up a third of Morocco's gain.
* Every FHARL candidate has a lower mean loss than the best return-only forecast in every panel. In Vietnam
  the margin for M1 and the open-free kernel is close to zero (−0.0001 and −0.0003 at 5 sessions), against
  −0.0032 for MSO (t = −2.2).
* On the two indices there is no cross-section, and nothing new helps: the design reduces to the open-free form.

## The design carried into plan M22

* **Kernel (MSO).** For security i on date t:
  * o_M,−i is the equal-weighted mean overnight return of the other securities of the panel that day;
  * the effective open is o* = o_M,−i where the open printed at the previous close (O = C₋), and o* = 0
    otherwise;
  * the kernel is

        A = (1 − w)·[o*² + R*²/D] + w·r²,   w = 0.2,   R* = max(h, o*) − min(l, o*),

    with D = 4 ln 2, except D = 1 on a one-price bar (H = L).

  Everywhere the open moved, this is the open-free kernel. A single series has no cross-section, so o* = 0 and
  the kernel is the open-free kernel with the one-price divisor.
* **Calibration.** The pooled κ over 60 dates, as before (the stock's own over 250 sessions for a single series).
* **Forecast (FHARL).** A convex combination of these components, fitted by QLIKE on the training span:
  * the kernel's d1, m5, m22 and long-run mean lr;
  * lr times the cross-sectional medians of m5/lr and m22/lr;
  * the stock's own long-run mean of r².

  For a single series, the factor terms are dropped.

## What this record does not show

These are development results. Many of the 195 variants were tried on the same folds, and MSO was chosen after
M1 and MS had been seen, so the gains above are optimistic. Only the frozen test of plan M22 can say whether they
are real: on the M20 test spans (seen), on Pakistan (unseen) and prospectively.
