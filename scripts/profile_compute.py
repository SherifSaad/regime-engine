#!/usr/bin/env python3
"""Profile compute_asset_full to identify bottlenecks."""
from __future__ import annotations

import cProfile
import io
import pstats
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd

# Generate synthetic bars if no real data
def make_synthetic_df(n: int = 3000) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + np.abs(np.random.randn(n)),
            "low": close - np.abs(np.random.randn(n)),
            "close": close,
            "volume": np.random.randint(1e6, 1e7, n),
        },
        index=dates,
    )
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    df["adj_close"] = df["close"]
    df["ts_str"] = df.index.astype(str)
    return df


def main():
    df = make_synthetic_df(800)
    print(f"Profiling with {len(df)} bars...")

    # Import after path setup
    import sqlite3
    from scripts.compute_asset_full import (
        ensure_tables,
        run_escalation_tf,
        run_state_tf,
        compute_db_path,
    )

    db_path = Path(__file__).parent.parent / "data" / "assets" / "_profile" / "compute.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=60)
    ensure_tables(conn)

    prof = cProfile.Profile()
    prof.enable()

    run_escalation_tf(df, conn, "_PROFILE", "1day")
    run_state_tf(df, conn, "_PROFILE", "1day")

    prof.disable()
    s = io.StringIO()
    ps = pstats.Stats(prof, stream=s).sort_stats("cumulative")
    ps.print_stats(40)
    print("\n--- Top 40 by cumulative time ---\n")
    print(s.getvalue())


if __name__ == "__main__":
    main()
