import numpy as np
import pandas as pd

from regime_engine.metrics import compute_asymmetry_metric


def make_df(n=300, downside_heavy=False):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(100, 110, n)

    # Inject bigger downside shocks if requested
    if downside_heavy:
        for k in range(50, n, 50):
            close[k:] *= 0.97

    open_ = close.copy()
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_asm_in_bounds():
    df = make_df()
    asm = compute_asymmetry_metric(
        df,
        bp_up=0.3,
        bp_dn=0.2,
        dsr=0.2,
        rl=0.3,
        mb=0.2,
        er=0.5,
        iix=0.5,
        H=60,
        gamma=1.0,
    )
    assert -1.0 <= asm <= 1.0


def test_downside_heavy_returns_push_negative():
    # Use data with explicit downside skew in last 60 bars
    idx = pd.date_range("2020-01-01", periods=120, freq="D")
    close = 100.0 * np.ones(120)
    for i in range(1, 120):
        # Many -2% days, few +0.5% days in tail -> sigma_minus > sigma_plus
        if i >= 60:
            close[i] = close[i - 1] * (0.98 if i % 3 != 0 else 1.005)
        else:
            close[i] = close[i - 1] * 1.001
    df = pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1_000_000},
        index=idx,
    )
    asm = compute_asymmetry_metric(
        df,
        bp_up=0.2,
        bp_dn=0.3,
        dsr=0.6,
        rl=0.6,
        mb=-0.2,
        er=0.4,
        iix=0.9,
        H=60,
        gamma=1.0,
    )
    assert asm < 0
