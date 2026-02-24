#!/usr/bin/env python3
"""
Test Polars vectorized regime compute on SPY 1day.
Phase 6 Step 1 – verify speed and output.
"""

import time

from core.providers.bars_provider import BarsProvider
from core.compute.regime_engine_polars import compute_regime_polars

if __name__ == "__main__":
    print("Loading SPY 1day from Parquet...")
    lf = BarsProvider.get_bars("SPY", "1day")
    df = lf.collect()
    print(f"Rows: {len(df)}")

    print("Running vectorized regime compute...")
    t0 = time.perf_counter()
    result = compute_regime_polars(df)
    t1 = time.perf_counter()
    print(f"Compute time: {(t1 - t0) * 1000:.1f} ms")

    print("\nLast 5 rows (key columns):")
    cols = ["ts", "close", "regime_state", "trend_strength", "vol_regime"]
    available = [c for c in cols if c in result.columns]
    print(result.select(available).tail(5))

    print("\nOK – Polars vectorized compute tested on SPY 1d")
