# M22 — frozen plan: Anam II, the market-implied open

**Written and frozen on 2026-10-10, after the development record and before Anam II was computed on any test
row, and before any return, range or estimator was computed on the Pakistan data.** The commit that adds this
file also adds:

* `src/nepsevol/estimators/anam2.py`, the estimator and its forecast (SHA-256 below);
* `scripts/52_m22_evaluation.py`, the evaluation, written before it was run on any test row;
* the Pakistan reader and its panel rules in `src/nepsevol/frontier.py`;
* `tests/test_m22_anam2.py`, which checks all three on synthetic data.

The script was checked only by its `--dry-run`. That mode runs on training rows only: each of the seven
existing samples is cut to its training span, which is split in half. The dry run never reads Pakistan, and its
outputs stayed outside the repository. The decision rules below are applied mechanically.

**Recommendation to the author.** Lodge this file and its digests with an external registry (OSF Registries or
AsPredicted) before the evaluation is run. A git commit is timestamped only by a history its author controls
(`M-017`, `M-020`).

## Why this plan

The corrected evaluation (M20, `M20_CORRECTED_EVALUATION_RESULTS.md`) left two findings:

* estimating the open's coefficient b never beat setting it to zero, the open-free form;
* the most accurate forecast in most samples pairs the open-free kernel with HAR dynamics
  ("HAR-open-free").

The development record (`ANAM2_DEVELOPMENT.md`, training spans only) explains the first finding. On each date,
split the overnight return into the market's move (the cross-sectional mean) and the stock's own remainder:

* the session keeps the market part almost fully (b_M between 0.64 and 1.00);
* it reverses most of the stock's own part (b_I between 0.20 and 0.70);
* the market part is only 6–21% of the overnight second moment, so b ≈ b_I.

One coefficient therefore shrinks the reliable component by the unreliable one's factor. The market's move can be
read from the other stocks' opens, free of the stock's own opening error. Anam II reads it where the stock's own
open says nothing: where the open printed at the previous close.

## What was known before freezing (disclosed, so the plan can be judged against it)

1. **Every published result:**
   * M16–M18 and their post hoc recheck;
   * M19 (theory checks);
   * M20, the corrected evaluation, including every M20 forecast's test-span losses, verdicts and model
     confidence sets;
   * M21's frozen parameters.

   The M20 test spans are therefore **seen**. Anam II was never computed on them, but its author knew, for
   example, that HAR-open-free was strong there, and that close-to-close beat the range forecasts in NEPSE's
   regime C.
2. **The development record.** Its 16 rounds and 195 variants were run on the training spans of the seven
   samples (`output/dev_anam2/ledger.csv`). The design below was chosen there, after the alternatives M1 and MS
   had been seen. The development's numbers are optimistic for that reason.
3. **Pakistan, structure only.** These checks used no return, range or variance:
   * the file's digest;
   * its columns, rows, symbols and dates;
   * counts of non-positive prices and envelope violations, and their sizes in rupees;
   * the metadata's sectors.

   Pakistan is the **unseen** market.
4. **The exchange's limit history**, from public reports: 5% or PKR 1, whichever is higher; widened to 7.5% from
   20 January 2020 in fortnightly steps; and to 10% from 27 May 2024, with the last step on 22 July 2024.

## The estimator (`nepsevol.estimators.anam2`)

For security i on date t, with previous close PC and bar (O, H, L, C), write:

* o = ln(O/PC), c = ln(C/O), u = ln(H/O), d = ln(L/O);
* r = o + c, h = o + u, l = o + d.

1. **The market's move** m₋ᵢ,ₜ is the equal-weighted mean of o over the panel's other securities that date. It is
   0 when no other security has a bar.
2. **The effective open** o\* is m₋ᵢ,ₜ where the open printed at the previous close (|o| < 1e−12), and 0
   elsewhere. A single series has no cross-section, so o\* = 0.
3. **The kernel** is

       A = 0.8·[o\*² + R\*²/D] + 0.2·r²,   R\* = max(h, o\*) − min(l, o\*),

   with D = 4 ln 2, except D = 1 on a one-price bar (|u − d| < 1e−12). Where the open moved, A is Anam's
   open-free kernel, apart from the one-price divisor.
4. **The calibration κ** is unchanged from Anam's estimator: sum r²/sum A pooled over the last 60 dates (at least
   20) in a panel, or over the security's own last 250 sessions (at least 60) in a series.
5. **The forecast** is f = κ·Σ cₖZₖ. The components Z are:
   * d1, m5 and m22 of the kernel;
   * lr·M5 and lr·M22, where M5 and M22 are the date's cross-sectional medians of m5/lr and m22/lr (panels
     only);
   * lrCC/κ, the security's own long-run mean of r², divided by κ;
   * lr, the kernel's long-run mean over 250 rows, at least 60.

   The weights are convex (cₖ ≥ 0, Σcₖ = 1), with the last at least 0.05. They minimise the mean canonical
   QLIKE on the training rows, by SLSQP with the exact gradient from two starts (`anam2.fit_weights`).

## Samples, spans and horizons

**The seven samples of M20, with M20's spans.** These are **seen**:

* NEPSE: train on regimes A1 and B; test on A2+C (primary), A2 and C;
* Dhaka 2023–2026, Dhaka 2009–2021, Vietnam 2007–2020, Morocco 2012–2026, the NIFTY 50 and the S&P 500:
  the test half.

**Pakistan 2016–2026 is unseen.** Its source is `combined/PSX_KSE100_Full_Historical_Daily.csv` of
github.com/Muhammad-Wasif/PSX-Stock-Market-Dataset at commit `c3b8ddd127f2440dfde7a29a4e502bd361a68854`
(SHA-256 `0c2d7b48697ea8abdecfda56acdea4357518cf8237f9062bba1b0e57a5127dda`). Its metadata is
`metadata/PSX_All_Listed_Companies.csv` (SHA-256 `05e19088d78f4288423421a837dac007159aacfe8ef0ea40ec66ec7525213a5b`).
Both are placed under `data/external/frontier/psx/`; they are gitignored and checked before use.

The panel follows the frontier rules of `nepsevol.frontier`, with these Pakistan specifics:

1. **Equity.** Ordinary equity only, by the metadata's sector. The real estate investment trusts, modarabas and
   the closed-end mutual fund are excluded, as are exchange-traded funds and debt. This leaves 101 of the 105
   symbols.
2. **Duplicates.** A record repeated exactly is kept once; a key carrying two different records is dropped.
3. **No trade.** A bar with a non-positive price or zero volume is dropped. This catches the 1,000 rows whose
   open is not positive.
4. **Envelope.** A high below max(open, close), or a low above min(open, close), by at most PKR 0.01 is repaired;
   a larger violation drops the record.
5. **Sessions.** As in the other frontier panels: carried-forward files, thin dates and closures are not
   sessions.
6. **Previous close.** It is taken from the immediately preceding session, at most 14 days earlier.
7. **Band screen.** A bar whose high or low lies outside the limit in force, plus 1 point, is dropped as an
   unadjusted corporate action or an error. The limit is the higher of the percentage and PKR 1:
   * 5% before 20 January 2020;
   * 7.5% from 20 January 2020;
   * 10% from 27 May 2024.

   Each phase-in is given its final value from its first day (`PSX_BANDS`).
8. **Split.** Sessions before the median session train; the median session and later are the test span.

Its limitations are stated in advance:

* the 105 companies are, by the source's description, the index's current constituents, so the panel has
  survivorship bias;
* the prices are not adjusted for corporate actions, and changes inside the limit are not detected.

**Horizons:** h = 5 and 21 sessions.

## The design of the evaluation (M20's, unchanged)

* **Target and loss:**
  * the target is the mean squared close-to-close return over h consecutive exchange sessions;
  * the loss is canonical QLIKE, with zero targets scored;
  * squared quantities below 1e−18 are zero.
* **Training rows:** the training span, with outcomes ending before the first test session.
* **Test rows:**
  * the test span, with outcomes ending inside it;
  * on the rows where every M20 forecast of the sample is defined and every M22 forecast is also defined.
* **Mean difference:** the stock-day mean of the loss difference, with a date-clustered Bartlett standard error
  at 2h lags.

**M20's forecasts are rebuilt by M20's code.** Their parameters are chosen by M20's rule on M20's training rows.
On each seen sample and span, HAR-open-free must reproduce M20's published test loss and parameters
(table 127) on M20's rows. Otherwise the script stops.

## Forecasts

**M20's forecasts:**

* HAR-open-free, the **reference**;
* the five return-only forecasts: close-to-close φ-shrinkage, EWMA, GARCH, GJR-GARCH and HAR-CC;
* **r\***, the return-only forecast with the lowest training loss (M20's rule B1).

**M22's forecasts**, fitted by QLIKE on the common training rows:

| Forecast | Kernel | Dynamics | Role |
|---|---|---|---|
| **Anam II** | MSO (above) | FHARL (above) | the forecast tested |
| HAR open-free (continuous) | open-free | M20's four HAR components, continuous fit | ablation: the fitting method |
| FHARL open-free | open-free | FHARL | ablation: the measurement (H2) |
| HAR MSO (continuous) | MSO | four HAR components | ablation: the dynamics |
| FHARL M1 | the market's move on every bar | FHARL | the alternative seen in development |
| FHARL MS | the market's move on bars with one price at the previous close | FHARL | the alternative seen in development |
| ½ Anam II + ½ GJR | | fixed weights | the combination (reported) |

For a single series, Anam II has no factor terms (FHARL loses lr·M5 and lr·M22), and only the first two rows
apply.

## Hypotheses and decision rules

Each hypothesis is judged on each **panel's** primary span:

* NEPSE A2+C;
* the test halves of Dhaka 2023–2026, Dhaka 2009–2021, Vietnam, Morocco and Pakistan.

That is six panels, a family for Holm's adjustment, at each horizon separately. Two-sided p values come from
the t statistic.

A verdict is:

* "better" if the Holm-adjusted p < 0.05 and d < 0;
* "worse" if the Holm-adjusted p < 0.05 and d > 0;
* otherwise "no detectable difference".

The **practical margin** is the secondary rule of M20 (B4). A difference is "practically equivalent" when
|d| + 1.645·se lies within 1% of the reference forecast's normalised QLIKE on the same rows.

* **H1 (primary): Anam II against HAR-open-free (M20).**
* **H2: Anam II against FHARL open-free.** The market-implied open, with the dynamics held fixed.
* **H3: Anam II against r\*.**

**P1, the overall reading of H1**, fixed now:

* **supported**: Anam II is "better" at h = 5 in at least 3 of the 6 panels, and "worse" in no panel at either
  horizon;
* **partly supported**: "better" in 1 or 2 panels and "worse" in none;
* **not supported**: no panel differs, or Anam II is "worse" in at least one panel-horizon.

Pakistan's own H1 verdicts are reported separately, as the unseen-market result.

**P2, the predicted pattern of H2 at h = 5.** It follows from the development and the theory: the market-implied
open matters where stale opens are common.

* "better" in Dhaka 2023–2026, Morocco and Vietnam;
* "no detectable difference" in NEPSE and Dhaka 2009–2021, where a significant difference inside the practical
  margin also counts as none.

The number of the five predictions that hold is reported. Pakistan has no prediction.

**Reported without a decision:**

* the indices: there Anam II is the open-free kernel with the one-price divisor and the own long-run level, and
  the development found no difference;
* the ablations, the alternatives M1 and MS, and the combination with GJR;
* NEPSE's spans A2 and C separately;
* the 90% and 75% model confidence sets (Hansen, Lunde and Nason 2011), over seven forecasts: Anam II,
  HAR-open-free, FHARL open-free, r\*, GJR, ½ Anam II + ½ GJR and close-to-close. They use T_max, a stationary
  bootstrap of dates with mean block max(2h, 10), 1,999 resamples and seed 20261011 + 100·(sample index) + h.

## Part C, the prospective freeze (after the evaluation, by a rule fixed now)

After the evaluation, `scripts/53_m22_freeze.py` fits Anam II's weights on every origin of each sample whose
outcome is observed, and writes them to `table142_m22_frozen_weights.csv`. It does the same for FHARL open-free
and for M20's HAR-open-free by M20's rule. The table records a digest of the inputs, and is never overwritten.

When new sessions arrive, M21's protocol scores them:

* NEPSE after 2026-08-26;
* Dhaka after 2026-10-08;
* Casablanca after 2026-03-27;
* Pakistan after 2026-10-08.

The weights are never refitted; the rolling quantities (κ, the components, the market states) update causally.

## How the results will be reported (fixed now)

* **Every verdict is reported as computed:** H1–H3, P1, P2 and the practical margins. The paper and the package
  describe Anam II by the P1 reading, and separately by Pakistan's verdicts.
* **If P1 is not "supported":**
  * the package keeps Anam's open-free form as its recommended forecast;
  * Anam II is offered as experimental, with its verdicts quoted;
  * the market-implied open is described as a measurement idea whose forecasting value was not established.
* **The seen samples are labelled seen in every table and sentence.** The development's numbers are never quoted
  as evidence.

## Outputs

| File | Content |
|---|---|
| `table138_m22_comparison.csv` | every forecast, sample, span and horizon: parameters, training and test losses, differences and t statistics against HAR-open-free, Anam II, r\* and FHARL open-free |
| `table139_m22_claims.csv` | H1–H3 with Holm's adjustment and the practical margin; P1; P2 |
| `table140_m22_mcs.csv` | the model confidence sets |
| `table141_m22_panels.csv` | each panel's spans, the open's statistics on the training span, and Pakistan's rule counts |
| `table142_m22_frozen_weights.csv` | Part C |

## Digests of the frozen files

| File | SHA-256 |
|---|---|
| `src/nepsevol/estimators/anam2.py` | `38be3fbc8482512764b127b0d5f9e3ae887726cb1e78f77e0d3742ff86fbc766` |
| `scripts/52_m22_evaluation.py` | `be719d826226e6df64e0eee2e39909763b9d11322c34a97ddb6f56ec3d1528c7` |
| `src/nepsevol/frontier.py` | `0b6b1a92f5d52201c347941761900728b1b3202f8dfc67628e5deb3a5d2ea166` |
