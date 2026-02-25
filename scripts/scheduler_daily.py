#!/usr/bin/env python3
"""
Daily scheduler – 1day + 1week bars for daily assets.

100% Parquet for bars: reads (last_ts/cursor) and writes from Parquet via BarsProvider.
Single run: fetch 1day and 1week bars for all daily_assets(), append to Parquet.
Canonical compute: invokes compute_asset_full (Parquet input, full history) → compute.db.
No RTH check – runs once per day (cron 16:01 EST) or on demand.
Only 1day and 1week (not 15min, 1h, 4h) for daily assets.

Notes:
- TWELVEDATA_API_KEY required in .env
- Schedule via cron: 1 16 * * 1-5 (16:01 EST Mon–Fri, after market close)
"""

import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import Dict, List, Optional, Tuple

import polars as pl
import requests
from dotenv import load_dotenv

from core.assets_registry import daily_assets
from core.providers.bars_provider import BarsProvider
from core.utils.config_watcher import start_universe_watcher

# ----------------------------
# Env / Config
# ----------------------------

load_dotenv()

TD_TS_URL = "https://api.twelvedata.com/time_series"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "scheduler.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
DAILY_TIMEFRAMES = ["1day", "1week"]
OVERLAP_BARS = 5
RATE_LIMIT_SLEEP = 65
COMPUTE_SCRIPT = Path(__file__).resolve().parent / "compute_asset_full.py"

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


def fetch_daily_bars(symbol: str, provider_symbol: str) -> Tuple[int, Optional[str]]:
    """
    Fetch 1day + 1week bars for daily assets. Appends to Parquet via BarsProvider.
    Returns (inserted_total, error_msg). error_msg is None on success.
    """
    total = 0
    try:
        for tf in DAILY_TIMEFRAMES:
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


def run_canonical_compute(symbol: str) -> bool:
    """Run canonical compute (compute_asset_full, Parquet input, full history) → compute.db."""
    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(COMPUTE_SCRIPT), "--symbol", symbol, "--input", "parquet"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
            timeout=600,
        )
        duration = time.time() - t0
        if result.returncode == 0:
            print(f"    [{symbol}] Canonical compute OK, {duration:.2f}s")
            return True
        logging.warning("[%s] compute_asset_full failed: %s", symbol, result.stderr)
        print(f"    [{symbol}] Compute: ERROR, {duration:.2f}s – {result.stderr[:200]}", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        duration = time.time() - t0
        logging.exception("[%s] compute_asset_full timeout", symbol)
        print(f"    [{symbol}] Compute: TIMEOUT, {duration:.2f}s", file=sys.stderr)
        return False
    except Exception as e:
        duration = time.time() - t0
        logging.exception("[%s] Compute failed: %s", symbol, e)
        print(f"    [{symbol}] Compute: ERROR, {duration:.2f}s – {e}", file=sys.stderr)
        return False


# ----------------------------
# Main
# ----------------------------

def main():
    # Start universe.json watcher in background (for long-running or repeated runs)
    watcher_thread = Thread(target=start_universe_watcher, daemon=True)
    watcher_thread.start()

    daily_list = daily_assets()
    print(f"Daily run – processing {len(daily_list)} symbols (canonical compute → compute.db)")

    if not daily_list:
        print("No daily symbols enabled")
        return

    for asset in daily_list:
        symbol = asset["symbol"]
        provider_symbol = asset.get("provider_symbol") or symbol
        try:
            print(f"  Fetching 1day + 1week bars for {symbol}")
            inserted, err = fetch_daily_bars(symbol, provider_symbol)
            if err:
                print(f"  Error updating {symbol}: {err}")
            else:
                print(f"  Success: updated {symbol} (inserted={inserted})")
                run_canonical_compute(symbol)
        except Exception as e:
            print(f"  Error updating {symbol}: {e}")

    print("Daily run complete")


if __name__ == "__main__":
    main()
