#!/usr/bin/env python3
"""
Earnings scheduler – 1h + 1week bars for earnings tier symbols.

100% Parquet for bars: reads (last_ts/cursor) and writes from Parquet via BarsProvider.
Single run: fetch 1h and 1week bars for all daily_assets(), append to Parquet.
No RTH check – runs once per day (cron) or on demand.
Only 1h and 1week (not 15min, 4h, 1d) for earnings assets.

Notes:
- TWELVEDATA_API_KEY required in .env
"""

import os
import sys
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import polars as pl
from dotenv import load_dotenv

from core.assets_registry import daily_assets
from core.providers.bars_provider import BarsProvider

# ----------------------------
# Env / Config
# ----------------------------

load_dotenv()

TD_TS_URL = "https://api.twelvedata.com/time_series"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EARNINGS_TIMEFRAMES = ["1h", "1week"]
OVERLAP_BARS = 5
RATE_LIMIT_SLEEP = 65

# ----------------------------
# Helpers
# ----------------------------

def api_key() -> str:
    k = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not k:
        raise RuntimeError("Missing TWELVEDATA_API_KEY (check .env)")
    return k

def get_nth_last_ts_from_parquet(symbol: str, tf: str, n: int) -> Optional[str]:
    """Get nth-from-last ts from Parquet (for incremental fetch start_date)."""
    lf = BarsProvider.get_bars(symbol, tf)
    df = lf.select("ts").sort("ts", descending=True).head(n).collect()
    if df.is_empty():
        return None
    row = df.row(-1)
    return str(row[0]) if row else None


def values_to_pl_df(values: List[Dict]) -> pl.DataFrame:
    """Convert Twelve Data API values to Polars DataFrame for BarsProvider."""

    def to_float(x):
        try:
            return float(x) if x is not None and x != "" else None
        except Exception:
            return None

    if not values:
        return pl.DataFrame()
    rows = []
    for v in values:
        ts = v.get("datetime")
        if not ts:
            continue
        o = to_float(v.get("open"))
        h = to_float(v.get("high"))
        l = to_float(v.get("low"))
        c = to_float(v.get("close"))
        vol = to_float(v.get("volume"))
        rows.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": int(vol) if vol else 0})
    df = pl.DataFrame(rows)
    df = df.with_columns(
        pl.col("ts").str.to_datetime(),
        pl.col("volume").cast(pl.Int64),
    )
    return df


def td_time_series(symbol: str, interval: str, start_date: Optional[str]) -> List[Dict]:
    params = {
        "apikey": api_key(),
        "symbol": symbol,
        "interval": interval,
        "outputsize": 5000,
        "order": "ASC",
        "format": "JSON",
    }
    if start_date:
        params["start_date"] = start_date

    r = requests.get(TD_TS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, dict) and data.get("status") == "error":
        msg = data.get("message", "")
        if "run out of API credits for the current minute" in msg:
            raise RuntimeError("RATE_LIMIT")
        raise RuntimeError(f"Twelve Data error: {msg}")

    values = data.get("values") if isinstance(data, dict) else None
    return values or []

def fetch_earnings_daily_weekly(symbol: str, provider_symbol: str) -> Tuple[int, Optional[str]]:
    """
    Fetch 1h + 1week bars for earnings tier. Appends to Parquet via BarsProvider.
    Returns (inserted_total, error_msg). error_msg is None on success.
    """
    total = 0
    try:
        for tf in EARNINGS_TIMEFRAMES:
            start_date = get_nth_last_ts_from_parquet(symbol, tf, OVERLAP_BARS)

            try:
                values = td_time_series(provider_symbol, tf, start_date=start_date)
            except RuntimeError as e:
                if str(e) == "RATE_LIMIT":
                    time.sleep(RATE_LIMIT_SLEEP)
                    values = td_time_series(provider_symbol, tf, start_date=start_date)
                else:
                    raise

            if not values:
                continue

            df = values_to_pl_df(values)
            if not df.is_empty():
                BarsProvider.write_bars(symbol, tf, df)
                total += len(df)
                print(f"    Appended {len(df)} {tf} bars for {symbol} to Parquet")
            else:
                print(f"    No new {tf} bars for {symbol}")
    except Exception as e:
        return total, str(e)
    return total, None

# ----------------------------
# Main
# ----------------------------

def main():
    daily_list = daily_assets()
    print(f"Earnings daily run – processing {len(daily_list)} symbols")

    if not daily_list:
        print("No daily/earnings symbols enabled")
        return

    for asset in daily_list:
        symbol = asset["symbol"]
        provider_symbol = asset.get("provider_symbol") or symbol
        try:
            print(f"  Fetching 1h + 1week bars for {symbol}")
            inserted, err = fetch_earnings_daily_weekly(symbol, provider_symbol)
            if err:
                print(f"  Error updating {symbol}: {err}")
            else:
                print(f"  Success: updated {symbol} (inserted={inserted})")
        except Exception as e:
            print(f"  Error updating {symbol}: {e}")

    print("Earnings daily run complete")

if __name__ == "__main__":
    main()
