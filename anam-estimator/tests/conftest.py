"""Run the tests against this checkout's source, whether or not the package is installed."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from anam_estimator import simulate_bars  # noqa: E402


@pytest.fixture(scope="session")
def panel():
    return simulate_bars(n_securities=12, n_sessions=420, open_noise=1.0, seed=7)


@pytest.fixture(scope="session")
def series(panel):
    return panel[panel["symbol"] == "S001"].drop(columns="symbol").reset_index(drop=True)
