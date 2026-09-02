"""Scale-explicit estimator ratios.

Every ratio in this project is either a VARIANCE ratio or a STANDARD-DEVIATION ratio, and
the two differ by a square root. The repository previously computed both under the bare
name ``ratio``: ``09_cross_market_control.py`` applied ``np.sqrt`` and ``12_benchmark_
diagnosis.py`` did not, and their outputs then appeared in adjacent manuscript sections
under indistinguishable column headers. The same quantity -- NIFTY Rogers-Satchell against
open-to-close -- is printed as 0.980 in one section and 0.965 in the other purely because
of that. Nobody reading the tables could tell.

The fix is not to force a single scale: both are scientifically appropriate in different
places. The fix is to make the scale impossible to omit. Use these helpers instead of a
bare division, name results with the returned label, and comparisons stay dimensionally
valid because mismatched scales raise rather than quietly mislead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["variance_ratio", "sd_ratio", "as_sd", "as_var", "assert_same_scale", "SCALES"]

SCALES = ("variance", "sd")


def variance_ratio(numerator: pd.Series | float, denominator: pd.Series | float) -> tuple[float, str]:
    """Mean(numerator) / mean-or-variance(denominator) on the VARIANCE scale.

    Returns ``(value, "variance")``. Both arguments must already be in variance units.
    """
    num = float(np.mean(numerator)) if not np.isscalar(numerator) else float(numerator)
    den = float(np.mean(denominator)) if not np.isscalar(denominator) else float(denominator)
    if den <= 0:
        return float("nan"), "variance"
    return num / den, "variance"


def sd_ratio(numerator: pd.Series | float, denominator: pd.Series | float) -> tuple[float, str]:
    """The same comparison expressed on the STANDARD-DEVIATION scale.

    Returns ``(value, "sd")``. This is ``sqrt`` of :func:`variance_ratio`, which is why the two
    can never be compared with each other without conversion.
    """
    v, _ = variance_ratio(numerator, denominator)
    return (float("nan") if v < 0 else np.sqrt(v)), "sd"


def as_sd(value: float, scale: str) -> float:
    """Convert a labelled ratio to the standard-deviation scale."""
    _check(scale)
    return value if scale == "sd" else np.sqrt(value)


def as_var(value: float, scale: str) -> float:
    """Convert a labelled ratio to the variance scale."""
    _check(scale)
    return value if scale == "variance" else value ** 2


def assert_same_scale(*labelled: tuple[float, str]) -> str:
    """Guard a comparison. Raises if labelled ratios are not on one scale.

    Put this in front of any table row, figure series, or manuscript sentence that sets
    two ratios side by side.
    """
    scales = {s for _, s in labelled}
    for s in scales:
        _check(s)
    if len(scales) > 1:
        raise ValueError(
            f"refusing to compare ratios on different scales: {sorted(scales)}. "
            f"Convert with as_sd() or as_var() and say which you used."
        )
    return scales.pop()


def _check(scale: str) -> None:
    if scale not in SCALES:
        raise ValueError(f"scale must be one of {SCALES}, got {scale!r}")
