from __future__ import annotations

from pathlib import Path
import pandas as pd


REQUIRED_COLS = ["open", "high", "low", "close", "volume"]


def load_sample_data(symbol: str, n_bars: int = 500) -> pd.DataFrame:
    """
    Load offline CSV from ./data/{symbol}_sample.csv and standardize columns:
      index: timestamp (datetime, ascending)
      cols : open, high, low, close, volume (float)
    """
    symbol_clean = symbol.strip().upper()
    path = Path(__file__).resolve().parents[2] / "data" / f"{symbol_clean.lower()}_sample.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Sample CSV not found: {path}\n"
            f"Expected filename like: data/{symbol_clean.lower()}_sample.csv"
        )

    df = pd.read_csv(path)

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    # Common Yahoo-style columns:
    # date, open, high, low, close, adj close, volume
    if "date" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"date": "timestamp"})

    if "adj close" in df.columns and "close" not in df.columns:
        df = df.rename(columns={"adj close": "close"})

    if "timestamp" not in df.columns:
        raise ValueError(
            f"CSV must contain a 'timestamp' or 'date' column. Found: {list(df.columns)}"
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    df = df.set_index("timestamp")

    # Keep only required columns if present
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns {missing}. Found: {list(df.columns)}")

    df = df[REQUIRED_COLS].copy()

    # Convert to numeric and forward-fill gaps
    for c in REQUIRED_COLS:
        df[c] = (
            df[c]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace('"', "", regex=False)
        )
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.ffill().dropna()

    if n_bars is not None and len(df) > n_bars:
        df = df.tail(n_bars)

    return df
