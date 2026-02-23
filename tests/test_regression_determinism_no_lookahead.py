import numpy as np
import pandas as pd
import pytest

from scripts.validate_regimes import run_engine_over_history


def _load_small_fixture() -> pd.DataFrame:
    """
    Loads data/spy_clean.csv (Yahoo-style columns)
    Normalizes to engine-required columns:
    open, high, low, close, adj_close, volume

    If adj_close is missing, we set adj_close = close (deterministic fallback).
    """

    path = "data/spy_clean.csv"
    df = pd.read_csv(path)

    rename_map = {
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    df = df.rename(columns=rename_map)

    if "date" not in df.columns:
        raise RuntimeError("spy_clean.csv missing 'Date' column")

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    # Deterministic fallback if Adj Close not present
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    required = ["open", "high", "low", "close", "adj_close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"spy_clean.csv missing columns: {missing}")

    df = df[required].copy()

    # Trim for speed but keep enough history
    return df.iloc[-1500:].copy()


@pytest.mark.slow
def test_runner_is_deterministic():
    df = _load_small_fixture()
    out1 = run_engine_over_history(df.copy(), symbol="SPY")
    out2 = run_engine_over_history(df.copy(), symbol="SPY")
    pd.testing.assert_frame_equal(out1, out2)


@pytest.mark.slow
def test_no_lookahead_in_runner():
    """
    Proper no-lookahead test:
    Modify ONLY future rows (after a cutoff) and ensure earlier outputs are identical.
    Expanding-window runner must not let future data affect past decisions.
    """
    df = _load_small_fixture()

    base = run_engine_over_history(df.copy(), symbol="SPY")

    # Pick a cutoff far enough from the end so we have "future" to modify
    cutoff = df.index[-200]  # last 200 bars are "future"
    df2 = df.copy()

    mask_future = df2.index > cutoff

    # Modify ONLY future prices deterministically (leave past untouched)
    df2.loc[mask_future, "close"] = df2.loc[mask_future, "close"] * 1.10
    df2.loc[mask_future, "adj_close"] = df2.loc[mask_future, "adj_close"] * 1.10

    shifted = run_engine_over_history(df2, symbol="SPY")

    # Compare outputs strictly BEFORE cutoff (past must match exactly)
    past = df.index <= cutoff

    assert base.loc[past, "regime"].equals(shifted.loc[past, "regime"])
    assert np.allclose(
        base.loc[past, "confidence"].astype(float).values,
        shifted.loc[past, "confidence"].astype(float).values,
        equal_nan=True,
    )


@pytest.mark.slow
def test_confidence_bounds():
    df = _load_small_fixture()
    out = run_engine_over_history(df.copy(), symbol="SPY")
    conf = out["confidence"].astype(float)
    assert (conf >= 0.0).all()
    assert (conf <= 1.0).all()
