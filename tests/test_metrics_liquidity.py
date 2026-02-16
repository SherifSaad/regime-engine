import numpy as np
import pandas as pd

from regime_engine.metrics import compute_liquidity_context


def make_df(n=120, high_volume=True):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(100, 110, n)
    open_ = close
    high = close * 1.01
    low = close * 0.99

    if high_volume:
        volume = np.full(n, 10_000_000)
    else:
        volume = np.full(n, 100_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_liquidity_in_bounds_and_label_valid():
    df = make_df(high_volume=True)
    out = compute_liquidity_context(df, vrs=0.4, er=0.6, n_dv=20, h=5)
    assert 0.0 <= out["lq"] <= 1.0
    assert out["trend"] in {"IMPROVING", "STABLE", "DETERIORATING"}
    assert out["label"] in {"DEEP", "NORMAL", "THIN"}


def test_higher_volume_tends_to_higher_lq():
    df_hi = make_df(high_volume=True)
    df_lo = make_df(high_volume=False)

    out_hi = compute_liquidity_context(df_hi, vrs=0.4, er=0.6, n_dv=20, h=5)
    out_lo = compute_liquidity_context(df_lo, vrs=0.4, er=0.6, n_dv=20, h=5)

    assert out_hi["lq"] >= out_lo["lq"]
