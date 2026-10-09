"""Anam's estimator: daily-bar volatility for markets whose opening price cannot be trusted.

Quick start::

    import pandas as pd
    from anam_estimator import AnamModel, anam_estimator

    prices = pd.read_csv("prices.csv")              # date, open, high, low, close[, symbol]
    # or, to try it without data: from anam_estimator import simulate_bars; prices = simulate_bars()
    est = anam_estimator(prices, form="open-free")  # the estimate on every bar
    model = AnamModel(form="open-free").fit(prices)
    model.forecast()                                # volatility over the next 5 sessions

See the README for the definition, the two forms, and what the evidence does and does not support.
"""
from ._version import __version__
from .core import (LAMBDA0, MIN_POOL_DATES, MIN_SERIES_SESSIONS, POOL_SESSIONS, SERIES_SESSIONS,
                   bar_coordinates, calibration_panel, calibration_series, extended_range, kernel,
                   open_quality_panel, open_quality_series)
from .data import observed_sessions_per_year, prepare
from .estimator import FORMS, anam_estimator, estimate
from . import evaluation
from .ml import AnamMLModel
from .evaluation import qlike_canonical
from .model import PHI_GRID, AnamModel, qlike
from .simulate import simulate_bars

__all__ = [
    "__version__", "AnamModel", "AnamMLModel", "anam_estimator", "estimate", "prepare", "observed_sessions_per_year",
    "simulate_bars",
    "qlike", "qlike_canonical", "evaluation", "FORMS", "PHI_GRID", "LAMBDA0", "POOL_SESSIONS", "MIN_POOL_DATES", "SERIES_SESSIONS",
    "MIN_SERIES_SESSIONS", "bar_coordinates", "open_quality_panel", "open_quality_series",
    "extended_range", "kernel", "calibration_panel", "calibration_series",
]
