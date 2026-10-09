import numpy as np
import pandas as pd

from anam_estimator.core import LN2, bar_coordinates, extended_range, kernel, _clip_b


def _bars(n=500, seed=0):
    rng = np.random.default_rng(seed)
    pc = 100 * np.exp(rng.normal(0, 0.02, n))
    o = pc * np.exp(rng.normal(0, 0.01, n))
    c = o * np.exp(rng.normal(0, 0.015, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.008, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.008, n)))
    return bar_coordinates(o, h, l, c, pc)


def test_full_trust_is_overnight_squared_plus_parkinson():
    co = _bars()
    one = pd.Series(1.0, index=co.index)
    A = kernel(co.o, co.c, co.u, co.d, one)
    np.testing.assert_allclose(A, co.o ** 2 + (co.u - co.d) ** 2 / (4 * LN2), rtol=1e-12)


def test_open_free_is_true_range_parkinson_blended_with_close_to_close():
    co = _bars()
    zero = pd.Series(0.0, index=co.index)
    A = kernel(co.o, co.c, co.u, co.d, zero)
    true_range = np.maximum(co.h, 0) - np.minimum(co.l, 0)   # ln(max(H, PC) / min(L, PC))
    np.testing.assert_allclose(A, 0.8 * true_range ** 2 / (4 * LN2) + 0.2 * co.r ** 2, rtol=1e-12)


def test_kernel_is_never_negative_and_the_extended_range_never_shorter():
    co = _bars(seed=3)
    for b in (0.0, 0.25, 0.5, 0.75, 1.0):
        bb = pd.Series(b, index=co.index)
        assert (kernel(co.o, co.c, co.u, co.d, bb) >= 0).all()
        assert (extended_range(co.o, co.u, co.d, bb) >= (co.u - co.d) - 1e-15).all()


def test_open_quality_is_clipped_and_zero_where_the_open_never_moved():
    b = _clip_b(pd.Series([2.0, -1.0, 0.3, 0.0]), pd.Series([1.0, 1.0, 1.0, 0.0]))
    assert b.tolist() == [1.0, 0.0, 0.3, 0.0]
