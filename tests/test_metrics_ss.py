import numpy as np
import pandas as pd

from regime_engine.metrics import compute_structural_score


def make_df_trend(n=400, up=True):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    if up:
        close = np.linspace(100, 150, n)
    else:
        close = np.linspace(150, 100, n)

    open_ = close
    high = close * 1.01
    low = close * 0.99
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_ss_in_bounds():
    df = make_df_trend(up=True)
    kl = {"supports": [{"price": 120.0, "strength": 0.8}], "resistances": [{"price": 160.0, "strength": 0.8}]}
    ss = compute_structural_score(df, mb=0.5, rl=0.2, dsr=0.1, key_levels=kl)
    assert -1.0 <= ss <= 1.0


def test_ss_higher_when_stable_and_clean():
    df = make_df_trend(up=True)
    kl = {"supports": [{"price": 120.0, "strength": 0.9}], "resistances": [{"price": 160.0, "strength": 0.9}]}

    ss_stable = compute_structural_score(df, mb=0.7, rl=0.1, dsr=0.05, key_levels=kl)
    ss_unstable = compute_structural_score(df, mb=0.7, rl=0.8, dsr=0.8, key_levels=kl)

    assert ss_stable > ss_unstable
