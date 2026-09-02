"""Analysis-sample selection.

Decision D-0012 (option C) settled which universe carries which claim:

* **ordinary equity** carries the main result;
* the **full mixed universe** is retained as the methodological warning -- the demonstration
  that pooling whatever an exchange publishes manufactures an illiquidity finding that is
  really a composition finding.

Until now every script from 04 onward hard-coded ``analysis_sample.parquet``, the mixed
universe, so the decision was recorded but never took effect. Loading through this module
makes the universe an explicit argument that appears in the run log, rather than a silent
default buried in twenty separate ``read_parquet`` calls.

The mixed universe is not deprecated. It is the right sample for the composition result
and the wrong one for anything described as a property of thin *equities*; the point is
that the choice must be stated.
"""

from __future__ import annotations

import pathlib

import pandas as pd

__all__ = ["load_sample", "UNIVERSES"]

UNIVERSES = {
    "equity": ("equity_sample.parquet", "ordinary common equity only (D-0012 option C, main result)"),
    "full": ("analysis_sample.parquet", "all instrument types (D-0012 option C, composition warning)"),
}


def load_sample(root: pathlib.Path, universe: str = "equity", quiet: bool = False) -> pd.DataFrame:
    """Load an analysis sample, announcing which universe was used.

    `universe` defaults to ``"equity"`` because that is what D-0012 assigns to the main
    result. Pass ``"full"`` deliberately, for the composition analysis.
    """
    if universe not in UNIVERSES:
        raise ValueError(f"universe must be one of {sorted(UNIVERSES)}, got {universe!r}")
    fname, description = UNIVERSES[universe]
    path = pathlib.Path(root) / "data" / "processed" / fname
    df = pd.read_parquet(path)
    if not quiet:
        print(f"  sample: {universe.upper()} -- {description}")
        print(f"          {len(df):,} stock-days, {df.symbol.nunique()} securities, "
              f"{df.date.min().date()} -> {df.date.max().date()}")
    return df
