from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from regime_engine.ingestor import Bar, normalize_bars


REQUIRED_COLS = ["open", "high", "low", "close", "volume"]


def load_bars(symbol: str, n_bars: int = 500) -> list[Bar]:
    """
    Load offline CSV and return normalized Bar objects (data contract).
    """
    _, bars = _load_bars_internal(symbol, n_bars)
    return bars


def load_sample_data(symbol: str, n_bars: int = 500) -> pd.DataFrame:
    """
    Load offline CSV from ./data/{symbol}_sample.csv and standardize columns:
      index: timestamp (datetime, ascending)
      cols : open, high, low, close, adj_close, volume (float)
      adj_close used for return-based series; raw OHLC for ATR/gaps/levels
    """
    df, _ = _load_bars_internal(symbol, n_bars)
    return df


def _load_bars_internal(symbol: str, n_bars: int = 500) -> tuple[pd.DataFrame, list[Bar]]:
    symbol_clean = symbol.strip().upper()
    path = Path(__file__).resolve().parents[2] / "data" / f"{symbol_clean.lower()}_sample.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Sample CSV not found: {path}\n"
            f"Expected filename like: data/{symbol_clean.lower()}_sample.csv"
        )

    df = pd.read_csv(path)

    # Normalize column names first
    df.columns = [c.strip().lower() for c in df.columns]

    # 1) Remove dividend rows (text like "Dividend" in Open/High/Low)
    for col in ["open", "high", "low"]:
        if col in df.columns:
            mask = df[col].astype(str).str.contains("Dividend", case=False, na=False)
            df = df[~mask]

    # 2) Keep only real price bars: coerce to numeric
    price_cols = ["open", "high", "low", "close", "volume"]
    if "adj close" in df.columns:
        price_cols = ["open", "high", "low", "close", "adj close", "volume"]
    for c in price_cols:
        if c in df.columns:
            df[c] = (
                df[c]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace('"', "", regex=False)
            )
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])

    # 3) Use Adj Close as Close if it exists; drop original Close
    # Scale OHLC proportionally to preserve consistency: factor = adj_close/close
    if "adj close" in df.columns:
        raw_close = df["close"].astype(float)
        adj_close = df["adj close"].astype(float)
        scale = adj_close / raw_close
        scale = scale.replace([np.inf, -np.inf], np.nan).fillna(1.0)
        df["open"] = (df["open"].astype(float) * scale).astype(float)
        df["high"] = (df["high"].astype(float) * scale).astype(float)
        df["low"] = (df["low"].astype(float) * scale).astype(float)
        df["close"] = adj_close
        df = df.drop(columns=["adj close"])
        # Enforce OHLC consistency after scaling (handles floating-point)
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

    # Common Yahoo-style columns
    if "date" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"date": "timestamp"})

    if "timestamp" not in df.columns:
        raise ValueError(
            f"CSV must contain a 'timestamp' or 'date' column. Found: {list(df.columns)}"
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    df = df.set_index("timestamp")

    # adj_close = close (we already replaced close with Adj Close above)
    df["adj_close"] = df["close"].astype(float)

    # Keep required columns + adj_close
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns {missing}. Found: {list(df.columns)}")

    keep_cols = REQUIRED_COLS + ["adj_close"]
    df = df[[c for c in keep_cols if c in df.columns]].copy()

    # Forward-fill and drop any remaining NaN
    df = df.ffill().dropna()

    if n_bars is not None and len(df) > n_bars:
        df = df.tail(n_bars)

    records = df.reset_index().to_dict("records")
    bars = normalize_bars(records)
    return df, bars
