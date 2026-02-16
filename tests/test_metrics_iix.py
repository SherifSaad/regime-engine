import numpy as np
import pandas as pd

from regime_engine.metrics import compute_instability_index


def make_df(n=400, add_gap=False):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(100, 110, n)
    open_ = close.copy()
    if add_gap and n >= 3:
        open_[-1] = close[-2] * 1.05  # big gap up (abs gap penalty triggers)

    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = np.full(n, 1_000_000)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_iix_in_bounds():
    df = make_df()
    iix = compute_instability_index(df, rl=0.2, dsr=0.2, vrs=0.4, lq=0.6, er=0.6)
    assert 0.0 <= iix <= 1.0


def test_gap_increases_iix_all_else_equal():
    df_no = make_df(add_gap=False)
    df_gap = make_df(add_gap=True)

    base = dict(rl=0.2, dsr=0.2, vrs=0.4, lq=0.6, er=0.6)
    iix_no = compute_instability_index(df_no, **base)
    iix_gap = compute_instability_index(df_gap, **base)

    assert iix_gap >= iix_no
