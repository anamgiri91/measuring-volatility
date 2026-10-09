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
| Open quality | b = Σ o·r / Σ o², clipped to [0, 1]: the share of the overnight move the session keeps. Pooled over the cross-section and the last 60 dates (at least 20); a single series uses its own last 250 sessions (at least 60) |
| Extended range | R* = R + max(0, b·o − h) + max(0, l − b·o): the range extended to the effective open PC·exp(b·o) |
| Daily kernel | A = (1 − w)·[(b·o)² + R*²/(4 ln 2)] + w·r², with w = 0.2·(1 − b) |
| Calibration | κ = Σ r² / Σ A over the same trailing set, which puts the level on the close-to-close scale |
| Window variance | σ² = κ × mean(A) over the window (21 sessions by default) |

The constants were fixed on development data before any test data were read. The arithmetic is a
verbatim copy of the research code. Tests in the parent repository check that the two agree exactly on
every NEPSE stock-day and on the NIFTY 50 and S&P 500.

### Two forms

* **`form="full"`**: b is measured from the data. With b = 1 it is overnight² + Parkinson.
* **`form="open-free"`**: b = 0. It becomes 0.8 × true-range Parkinson + 0.2 r², and reads only the
  previous close, the high, the low and the close.

In the paper the open-free form had the lower loss of the two wherever b was well below one, which was
every frontier market tested. The full form had the lower loss on two indices, though not significantly.
`anam_estimator(prices)["b"]` shows the b measured on your data.

## The model

`AnamModel` forecasts the mean daily variance over the next `horizon` sessions:

    forecast = κ × (φ × mean A over the last h sessions + (1 − φ) × mean A over the last 250 sessions)

The shrinkage φ is its one fitted parameter. `fit` chooses it by minimising the QLIKE loss of past
forecasts of the mean squared close-to-close return. This is the forecast the paper evaluated. Fitted on
the paper's training span, its forecasts equal the paper's, origin by origin. Where the paper scored the
same forecast origins (both indices, and NEPSE at 21 sessions), it reproduces Table 34's losses to about
10⁻¹¹. The parent repository's tests check both.

| Method | What it does |
|---|---|
| `fit(prices, train_end=None)` | estimate on every bar and choose φ (only from origins before `train_end`, if given) |
| `forecast(data=None, horizon=None)` | forecast per security; pass newer `data` to forecast without refitting |
| `variance_path()` | the estimate on every bar: b, κ, variance, volatility and close-to-close variance |
| `backtest()` / `score()` | every past forecast beside what followed, and its mean QLIKE loss (out of sample after `train_end`) |
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

**Evidence** (out of sample, under plans frozen before testing; paper Section 6.8, Tables 34-38):

* **Against the classical range estimators.** Under the plans' QLIKE loss, none forecast significantly
  better in any of seven test samples: Nepal, Bangladesh (two panels), Vietnam, Morocco, the NIFTY 50
  and the S&P 500. The estimators compared were Parkinson, Garman–Klass, Rogers–Satchell, Yang–Zhang,
  overnight² + Parkinson and overnight² + Garman–Klass. This survives other standard errors. Under an
  MSE loss, the estimators with a full overnight term beat it in Vietnam at 21 sessions.
* **Against plain close-to-close, mixed and dependent on the loss function.**
  * It beat close-to-close on both indices, in Dhaka 2009-2021 and, fragilely, in Morocco.
  * It did not beat it in Nepal's holdout, Dhaka 2023-2026 or Vietnam.
  * Close-to-close beat it right after a rule change in Nepal, and in Vietnam at 21 sessions.
* **The open-free form** passed one test fixed in advance, in Morocco.

**Limitations.**

* Designed on Nepal Stock Exchange data and tested in a finite set of markets.
* The 60-date calibration lags a sudden change in market rules; rely on close-to-close until the window
  has passed the change.
* The level is on the close-to-close scale because of the calibration, which any estimator could be
  given, so the level alone is no evidence of accuracy.
* A b below one shows that the session reverses part of the overnight move, not why.
* Each series needs about 120 sessions of history in series mode.
* Corporate actions not adjusted in the prices distort the returns.

The paper's post hoc recheck of these claims is in
[`ANAM_RECHECK_POSTHOC.md`](https://github.com/anamgiri91/measuring-volatility/blob/main/ANAM_RECHECK_POSTHOC.md).

## Citation

Giri, A. (2026). *When the Open Overreacts: Measuring Daily Volatility in Frontier Markets without
Options.* Working paper. https://github.com/anamgiri91/measuring-volatility

## Licence

MIT (see `LICENSE`).
