"""OHLC validation and cleaning.

Two known defects in the index series, both documented in docs/data_dictionary.md:

1. Rows before 2016-06-06 have Open == High == Low == Close, making every
   range-based estimator undefined.
2. 69 rows inside the usable window violate High >= max(O, C) or Low <= min(O, C).

Cleaning rules are pre-committed in the analysis plan before being applied, because
these rows disproportionately affect the very estimators the paper is about.
"""
