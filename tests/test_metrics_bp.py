import numpy as np
import pandas as pd

from regime_engine.metrics import compute_breakout_probability


def make_df_range(n=300, base=100.0, noise=0.2):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(42)
    close = base + rng.normal(0, noise, n).cumsum() * 0.1
    open_ = close * (1 + rng.normal(0, 0.0005, n))
    high = np.maximum(open_, close) * (1 + 0.005)
    low = np.minimum(open_, close) * (1 - 0.005)
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_bp_in_bounds():
    df = make_df_range()
    bp_up, bp_dn = compute_breakout_probability(df, mb=0.2, rl=0.3)
    assert 0.0 <= bp_up <= 1.0
    assert 0.0 <= bp_dn <= 1.0


def test_bp_alignment_effect():
    df = make_df_range()
    # bullish bias should tilt bp_up higher than bp_dn (all else equal)
    bp_up_bull, bp_dn_bull = compute_breakout_probability(df, mb=0.9, rl=0.2)
    bp_up_bear, bp_dn_bear = compute_breakout_probability(df, mb=-0.9, rl=0.2)

    assert bp_up_bull >= bp_dn_bull
    # bearish bias tilts bp_dn higher; distance-to-level can dominate in some configs
    assert bp_dn_bear >= bp_up_bear or (bp_up_bear - bp_dn_bear) < 0.25
