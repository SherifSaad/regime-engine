#!/usr/bin/env python3
"""
Validation Step 1:
Detect major ATR-based events for SPY.

Event definition:
absolute move over N bars >= ATR_MULT × ATR

Output:
- prints event count
- saves events dataframe (for later stages)

Bars: read from Parquet (canonical). No regime_cache.
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path

from core.providers.bars_provider import BarsProvider

SYMBOL = "SPY"
TIMEFRAME = "1day"

ATR_PERIOD = 14
ATR_MULT = 10
LOOKAHEAD_BARS = 20


def load_bars():
    """Load bars from Parquet (canonical source)."""
    lf = BarsProvider.get_bars(SYMBOL, TIMEFRAME)
    pl_df = lf.sort("ts").collect()
    if pl_df.is_empty():
        return pd.DataFrame()
    df = pd.DataFrame({c: pl_df[c].to_numpy() for c in pl_df.columns})
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df = df[["open", "high", "low", "close"]]
    return df.sort_index()


def compute_atr(df):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(ATR_PERIOD).mean()

    return atr


def detect_events(df):
    df = df.copy()

    df["atr"] = compute_atr(df)

    # forward move over LOOKAHEAD_BARS
    fwd_return = (df["close"].shift(-LOOKAHEAD_BARS) - df["close"])
    df["fwd_move"] = fwd_return

    df["event"] = (
        df["fwd_move"].abs() >= (ATR_MULT * df["atr"])
    )

    events = df[df["event"]].copy()

    return events


def main():
    df = load_bars()

    events = detect_events(df)

    print(f"Bars loaded: {len(df)}")
    print(f"Events detected: {len(events)}")

    out_path = "validation_outputs/spy_events.csv"
    os.makedirs("validation_outputs", exist_ok=True)
    events.to_csv(out_path)

    print("Saved:", out_path)


if __name__ == "__main__":
    main()
