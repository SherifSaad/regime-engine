import numpy as np
import pandas as pd

from regime_engine.metrics import compute_key_levels


def make_df(n=400):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    close = np.linspace(100, 130, n)
    open_ = close * 1.0002
    high = close * 1.01
    low = close * 0.99
    volume = np.full(n, 1_000_000)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_key_levels_format_and_bounds():
    df = make_df()
    kl = compute_key_levels(df, n_f=20, W=250, k=3, eta=0.35, N=3, min_strength=0.35)

    assert "supports" in kl and "resistances" in kl
    assert isinstance(kl["supports"], list)
    assert isinstance(kl["resistances"], list)

    for side in ["supports", "resistances"]:
        for item in kl[side]:
            assert "price" in item and "strength" in item
            assert isinstance(item["price"], float)
            assert isinstance(item["strength"], float)
            assert 0.0 <= item["strength"] <= 1.0


def test_key_levels_deterministic_same_input_same_output():
    df = make_df()
    kl1 = compute_key_levels(df, n_f=20, W=250, k=3, eta=0.35, N=3, min_strength=0.35)
    kl2 = compute_key_levels(df, n_f=20, W=250, k=3, eta=0.35, N=3, min_strength=0.35)
    assert kl1 == kl2
