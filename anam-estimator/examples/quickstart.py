"""Anam's estimator in a few lines. Runs offline on simulated bars; swap in your own prices.

    python examples/quickstart.py
"""
import pandas as pd

from anam_estimator import AnamModel, anam_estimator, simulate_bars

# Your data: one row per security and session with date, open, high, low, close (+ symbol), e.g.
#   prices = pd.read_csv("prices.csv")
# or, for one series from a data library that returns a date-indexed frame:
#   prices = some_library.download("TICKER")        # columns Open, High, Low, Close
prices = simulate_bars(n_securities=10, n_sessions=600, seed=42)

# 1. How far can the open be trusted? b near 1: trust it; b well below 1: use the open-free form.
est = anam_estimator(prices, form="full")
print(f"median open quality b = {est['b'].median():.2f}")

# 2. Fit the model, holding out the last 150 sessions to see how it forecasts out of sample.
cut = sorted(prices["date"].unique())[-150]
model = AnamModel(form="open-free", horizon=5, annualize="observed").fit(prices, train_end=cut)
print(model)
print(f"out-of-sample QLIKE loss: {model.score():.4f} on {model.n_scored_} forecasts")

# 3. Forecast the next 5 sessions for every security, with close-to-close variance beside the estimate.
print(model.forecast().to_string(index=False, float_format=lambda v: f"{v:.4f}"))
latest = model.variance_path().dropna(subset=["variance"]).groupby("symbol").tail(1)
print(latest[["symbol", "date", "volatility", "cc_variance", "volatility_annualized"]]
      .to_string(index=False, float_format=lambda v: f"{v:.4f}"))

# 4. Keep the fitted model and reuse it on newer data without refitting.
model.save("anam_model.json")
again = AnamModel.load("anam_model.json")
pd.testing.assert_frame_equal(again.forecast(prices), model.forecast())
