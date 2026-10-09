"""Command line: ``anam-estimator prices.csv`` prints each security's latest estimate and forecast."""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from ._version import __version__
from .estimator import FORMS
from .model import AnamModel


def _annualize(value):
    if value is None or value == "observed":
        return value
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("--annualize takes a number of sessions per year or 'observed'")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="anam-estimator",
        description="Anam's estimator: volatility from daily open-high-low-close bars. Reads a CSV with a "
                    "date column, open, high, low, close and, for several securities, a symbol column.")
    ap.add_argument("csv", help="input CSV file")
    ap.add_argument("--form", choices=FORMS, default="full",
                    help="'full' measures the open's weight from the data; 'open-free' ignores the open "
                         "(default: full)")
    ap.add_argument("--window", type=int, default=21, help="sessions in each estimate (default 21)")
    ap.add_argument("--horizon", type=int, default=5, help="sessions ahead to forecast (default 5)")
    ap.add_argument("--mode", choices=("auto", "panel", "series"), default="auto")
    ap.add_argument("--annualize", type=_annualize, default=None,
                    help="sessions per year, or 'observed' for the market's own count")
    ap.add_argument("--symbol", help="name of the symbol column, if not symbol/ticker/code")
    ap.add_argument("--date", help="name of the date column, if not date/datetime/timestamp")
    ap.add_argument("--prev-close", help="column holding an adjusted previous close, if any")
    ap.add_argument("--max-gap-days", type=float, help="treat longer calendar gaps as breaks")
    ap.add_argument("--on-invalid", choices=("nan", "repair", "raise"), default="nan")
    ap.add_argument("--output", help="also write the estimate on every bar to this CSV")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = ap.parse_args(argv)

    data = pd.read_csv(a.csv)
    model = AnamModel(form=a.form, window=a.window, horizon=a.horizon, mode=a.mode, annualize=a.annualize)
    model.fit(data, symbol=a.symbol, date=a.date, prev_close=a.prev_close, max_gap_days=a.max_gap_days,
              on_invalid=a.on_invalid)
    s = model.summary()
    print(f"Anam's estimator ({s['form']} form, {s['mode']} mode): {s['securities']} securities, "
          f"{s['bars_used']} of {s['bars']} bars used, {s['first_date']} to {s['last_date']}; "
          f"phi = {model.phi_:.2f} for {a.horizon}-session forecasts")
    path = model.variance_path()
    latest = path.dropna(subset=["variance"]).groupby("symbol").tail(1)
    fc = model.forecast()
    table = latest.merge(fc[["symbol", "variance", "volatility"] + (["volatility_annualized"]
                                                                     if "volatility_annualized" in fc else [])],
                         on="symbol", how="outer", suffixes=("", f"_next_{a.horizon}"))
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(table.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
    if a.output:
        path.to_csv(a.output, index=False)
        print(f"wrote {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
