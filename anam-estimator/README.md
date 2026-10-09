# anam-estimator

**Anam's estimator**: daily volatility from open-high-low-close bars, for markets whose opening price
cannot be trusted. It measures how far the open can be trusted, reads it only that far, and sets its
level on the close-to-close scale.

It comes from the paper *When the Open Overreacts: Measuring Daily Volatility in Frontier Markets
without Options* (Section 6.8). The paper, its data and every test are in the
[parent repository](https://github.com/anamgiri91/measuring-volatility).

## Install

```bash
pip install "anam-estimator @ git+https://github.com/anamgiri91/measuring-volatility.git#subdirectory=anam-estimator"
```

It needs Python 3.9 or later and depends only on numpy and pandas. To pin a version, put a commit
after `.git@`.

## Quick start

```python
import pandas as pd
from anam_estimator import AnamModel, anam_estimator

prices = pd.read_csv("prices.csv")   # date, open, high, low, close (+ symbol for several securities)

# The estimate on every bar
est = anam_estimator(prices, form="open-free", annualize="observed")

# As a model: fit to the history, then forecast the next 5 sessions
model = AnamModel(form="open-free", horizon=5, annualize="observed").fit(prices)
print(model.forecast())
```

No data at hand? `from anam_estimator import simulate_bars; prices = simulate_bars()` gives a panel with
a known volatility and an opening price that overreacts.

From the command line:

```bash
anam-estimator prices.csv --form open-free --annualize observed --output estimates.csv
```

## Input

* **A long table:** a date column, `open`, `high`, `low`, `close` and, for several securities, a
  `symbol` column (`ticker` and `code` are recognised too). Column names may use any capitalisation.
* **A single series indexed by date**, as most data libraries return it.
* **A wide table with two-level columns** (price field × ticker), as returned for several tickers at once.

Prices should be adjusted for splits and stock dividends. If you have the exchange's adjusted
previous close, pass its column as `prev_close=`; otherwise the previous row's close is used. Use
`max_gap_days=` to treat a long suspension as a break. Bad bars are handled as follows:

* a missing or non-positive price, or a high/low that does not contain the open and close, is
  excluded with a warning, and the windows skip it, as in the paper;
* `on_invalid="repair"` widens the high and low instead;
* `on_invalid="raise"` stops.

## What it computes

For a bar (O, H, L, C) with previous close PC, write o = ln(O/PC), r = ln(C/PC), h = ln(H/PC),
l = ln(L/PC) and R = ln(H/L).

| Step | Definition |
|---|---|
| Open quality | b = Σ o·r / Σ o², clipped to [0, 1]: the pooled projection of the close-to-close return on the overnight return, the share of the overnight move the session keeps on average (weighted by the size of the move). Pooled over the cross-section and the last 60 dates (at least 20); a single series uses its own last 250 sessions (at least 60) |
| Extended range | R* = R + max(0, b·o − h) + max(0, l − b·o) = max(h, b·o) − min(l, b·o): the range extended to the anchor PC·exp(b·o). b·o is a shrinkage predictor of the efficient overnight log move, not the move itself |
| Daily kernel | A = (1 − w)·[(b·o)² + R*²/(4 ln 2)] + w·r², with w = 0.2·(1 − b) |
| Calibration | κ = Σ r² / Σ A over the same trailing set, which puts the level on the close-to-close scale |
| Window variance | σ² = κ × mean(A) over the window (21 sessions by default) |

The constants were fixed on development data, in a plan frozen before the estimator was computed on the
test data; the full-sample findings that motivated the design included the test periods, as the plan
discloses. The arithmetic is a verbatim copy of the research code. Tests in the parent repository check that the two agree exactly on
every NEPSE stock-day and on the NIFTY 50 and S&P 500.

### Two forms

* **`form="full"`**: b is measured from the data. With b = 1 it is overnight² + Parkinson.
* **`form="open-free"`**: b = 0. It becomes 0.8 × true-range Parkinson + 0.2 r², and reads only the
  previous close, the high, the low and the close.

`anam_estimator(prices)["b"]` shows the b measured on your data. What the extension cannot do: an opening
print that sets the high or the low stays in R* (R ≤ R* ≤ true range), so neither form removes an opening
error that is already in an extreme. The theory supplement (Proposition 7) measures how much of the error's
variance each form still absorbs. The open-free form absorbs about a quarter to two-fifths of it at the
error sizes the paper's data imply, against about a half for Parkinson. The full form's overnight term
(b·o)² understates the efficient overnight variance unless the error is proportional to the news.

## The model

`AnamModel` forecasts the mean daily variance over the next `horizon` sessions:

    forecast = κ × (φ × mean A over the last h bars + (1 − φ) × mean A over the last 250 bars)

The shrinkage φ ∈ {0, 0.05, …, 0.95} is its one fitted parameter. `fit` chooses it by minimising the QLIKE
loss, y/f + ln f, of past forecasts of the target: the mean squared close-to-close return over the next h
**exchange sessions**.

**Changed in 0.2.0.** An independent audit (9 October 2026) found four defects in version 0.1.0 and in the
paper's original forecast test. The model now follows the paper's corrected evaluation (plan M20,
`anam_estimator.evaluation`):

* a target of h sessions is h consecutive sessions of the calendar, never h bars stitched across a gap;
* with `train_end`, φ is chosen only from origins whose whole outcome window ends before it;
* zero targets are scored;
* the φ grid stops below one, so no candidate is scored on fewer origins.

Pass `calendar=` (the market's sessions) for a single thinly traded series. By default every date in the
data is a session. Fitted on the paper's training span, the model reproduces the corrected evaluation of
the paper, origin by origin, and the parent repository's tests check this. It no longer reproduces the
frozen Table 34, whose defects the correction removes.

| Method | What it does |
|---|---|
| `fit(prices, train_end=None)` | estimate on every bar and choose φ (only from origins before `train_end`, if given) |
| `forecast(data=None, horizon=None)` | forecast per security; pass newer `data` to forecast without refitting |
| `variance_path()` | the estimate on every bar: b, κ, variance, volatility and close-to-close variance |
| `backtest()` / `score(loss="normalized")` | every past forecast beside what followed, its QLIKE loss in both forms (normalised, zero when exact; canonical, y/f + ln f, defined at a zero target), and their mean (out of sample after `train_end`) |
| `save(path)` / `AnamModel.load(path)` | keep the fitted settings as JSON |

## Output

`anam_estimator()` and `variance_path()` return one row per bar with these columns:

* `symbol`, `date`;
* `b`, the open quality;
* `kappa`, the calibration;
* `variance` and `volatility` (daily);
* `cc_variance`, plain close-to-close variance over the same window, which the paper recommends
  reporting beside the estimate;
* `volatility_annualized`, when `annualize=` is set.

For `annualize`, use your market's own session count, or `"observed"` to measure it from the dates,
rather than an imported 252. `forecast()` returns one row per security: the date the forecast is made
from, the forecast variance and volatility, b, κ and φ.

## Model card

**Intended use.** Measuring and forecasting the daily volatility of shares or indices from daily bars.
It is aimed at markets where the opening price comes from a thin market or an auction and is partly
reversed during the session.

**Not for:**

* recovering option-implied (risk-neutral) volatility;
* intraday risk;
* bars without a meaningful high and low.

**Evidence.** Out of sample, under plans frozen before testing (paper Section 6.8).

The corrected evaluation (plan M20, paper Table 39) is the record. An independent audit found four defects in
the evaluation of the earlier plans (Tables 34-38), which is the one version 0.1.0 of this package used. Plan
M20, frozen before it was run, removes them.

* **Against the classical range estimators** (Parkinson, Garman–Klass, Rogers–Satchell, Yang–Zhang,
  overnight² + Parkinson and overnight² + Garman–Klass), over seven test samples (Nepal, Bangladesh in two
  panels, Vietnam, Morocco, the NIFTY 50 and the S&P 500):
  * one classical estimator has significantly lower QLIKE loss than the full form in 1 of 84 comparisons
    (Parkinson, Dhaka 2023-2026, 5 sessions);
  * none has lower loss than the open-free form.
* **Against plain close-to-close at 5 sessions.** After Holm's adjustment across the seven samples:
  * the open-free form wins in six (all but Nepal);
  * the full form wins in three (Dhaka 2009-2021 and both indices);
  * close-to-close beat both right after a rule change in Nepal.
* **Against forecasts built from returns alone** (GARCH, GJR-GARCH, EWMA, a HAR on squared returns):
  * the best range-based forecast is better only in Dhaka 2009-2021 and Morocco, and fragilely in Morocco;
  * the return-only forecast is better in Dhaka 2023-2026;
  * neither is detectably better elsewhere.
* **The most accurate forecast in most samples** pairs the open-free form with HAR dynamics. It is not this
  package's φ-shrinkage model, which is close to the paper's frozen design.
* **Estimating b.** It did not beat setting it to zero (the open-free form) in any sample.

**Limitations.**

* Designed on Nepal Stock Exchange data and tested in a finite set of markets.
* The 60-date calibration lags a sudden change in market rules; rely on close-to-close until the window
  has passed the change.
* The level is on the close-to-close scale because of the calibration, which any estimator could be
  given, so the level alone is no evidence of accuracy.
* A b below one shows that the session reverses part of the overnight move, not why.
* The kernel is a heuristic whose level the calibration sets. Its overnight term understates the efficient
  overnight second moment unless the open's error is proportional to the move. An opening error that is
  already the day's high or low stays in the range: the open-free form absorbs about a quarter to two-fifths
  of its variance (theory supplement, Proposition 7).
* The forecasts target the second moment of observed close-to-close returns, not integrated variance.
* Each series needs about 120 sessions of history in series mode.
* Corporate actions not adjusted in the prices distort the returns.

The earlier post hoc recheck of these claims is in
[`ANAM_RECHECK_POSTHOC.md`](https://github.com/anamgiri91/measuring-volatility/blob/main/ANAM_RECHECK_POSTHOC.md).
The corrected evaluation is in
[`M20_CORRECTED_EVALUATION_RESULTS.md`](https://github.com/anamgiri91/measuring-volatility/blob/main/M20_CORRECTED_EVALUATION_RESULTS.md),
and the prospective test is planned in
[`M21_PROSPECTIVE_PLAN.md`](https://github.com/anamgiri91/measuring-volatility/blob/main/M21_PROSPECTIVE_PLAN.md).

## Citation

Giri, A. (2026). *When the Open Overreacts: Measuring Daily Volatility in Frontier Markets without
Options.* Working paper. https://github.com/anamgiri91/measuring-volatility

## Licence

MIT (see `LICENSE`).
