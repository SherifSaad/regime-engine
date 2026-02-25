#!/usr/bin/env python3
"""
DEPRECATED: Use scheduler_core.py instead. Poll every 15 min.

100% Parquet for bars: reads (last_ts/cursor) and writes from Parquet via BarsProvider.
Canonical compute: invokes compute_asset_full (Parquet input, full history) → compute.db.

Loop:
  1) For each asset in real_time_assets():
       - Skip US equities outside US trading hours (RTH)
       - Fetch incremental bars (overlap) -> append to Parquet via BarsProvider
  2) If ANY new bars inserted -> run canonical compute (compute_asset_full) → compute.db
  3) Sleep and repeat

Notes:
- TWELVEDATA_API_KEY required in .env
"""

import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from threading import Thread
from typing import Dict, List, Optional, Tuple

import requests
import polars as pl
from dotenv import load_dotenv

from core.assets_registry import core_assets, LegacyAsset
from core.asset_class_rules import should_poll
from core.providers.bars_provider import BarsProvider
from core.utils.config_watcher import check_and_clear_universe_changed, start_universe_watcher

# ----------------------------
# Env / Config
# ----------------------------

load_dotenv()

# Logging
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "scheduler.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
TD_TS_URL = "https://api.twelvedata.com/time_series"

OVERLAP_BARS = 5
SLEEP_SEC = 900  # 15 min
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

def to_float(x):
    try:
        return float(x) if x is not None and x != "" else None
    except Exception:
        return None


def get_nth_last_ts_from_parquet(symbol: str, tf: str, n: int) -> Optional[str]:
    """Get nth-from-last ts from Parquet (for incremental fetch start_date)."""
    lf = BarsProvider.get_bars(symbol, tf)
    df = lf.select("ts").sort("ts", descending=True).head(n).collect()
    if df.is_empty():
        return None
    row = df.row(-1)  # nth from end (or oldest if fewer than n rows)
    return str(row[0]) if row else None


def values_to_pl_df(values: List[Dict]) -> pl.DataFrame:
    """Convert Twelve Data API values to Polars DataFrame for BarsProvider."""
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
        if vol is not None:
            vol = int(vol)
        rows.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": vol or 0})
    df = pl.DataFrame(rows)
    df = df.with_columns(
        pl.col("ts").str.to_datetime(),
        pl.col("volume").cast(pl.Int64),
    )
    return df


def fetch_incremental_symbol(symbol: str, vendor_symbol: str) -> Tuple[int, int]:
    """Fetch new bars from API and append to Parquet via BarsProvider. Reads last_ts from Parquet."""
    total = 0
    polled = 0
    for tf in TIMEFRAMES:
        if not should_poll(symbol, tf):
            continue

        start_date = get_nth_last_ts_from_parquet(symbol, tf, OVERLAP_BARS)

        try:
            polled += 1
            values = td_time_series(vendor_symbol, tf, start_date=start_date)
        except RuntimeError as e:
            if str(e) == "RATE_LIMIT":
                print(f"[FETCH] Rate limit hit. Sleeping {RATE_LIMIT_SLEEP}s then retry...")
                time.sleep(RATE_LIMIT_SLEEP)
                polled += 1
                values = td_time_series(vendor_symbol, tf, start_date=start_date)
            else:
                print(f"[FETCH] {symbol} {tf} error: {e}", file=sys.stderr)
                continue

        if not values:
            continue

        df = values_to_pl_df(values)
        if not df.is_empty():
            BarsProvider.write_bars(symbol, tf, df)
            total += len(df)
            print(f"[FETCH] {symbol} {tf}: fetched={len(values)} appended={len(df)} to Parquet")
        else:
            print(f"[FETCH] {symbol} {tf}: no new bars")

    return total, polled

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
            print(f"[{symbol}] Canonical compute OK, {duration:.2f}s")
            return True
        logging.warning("[%s] compute_asset_full failed: %s", symbol, result.stderr)
        print(f"[{symbol}] Compute: ERROR, {duration:.2f}s – {result.stderr[:200]}", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        duration = time.time() - t0
        logging.exception("[%s] compute_asset_full timeout", symbol)
        print(f"[{symbol}] Compute: TIMEOUT, {duration:.2f}s", file=sys.stderr)
        return False
    except Exception as e:
        duration = time.time() - t0
        logging.exception("[%s] Compute failed: %s", symbol, e)
        print(f"[{symbol}] Compute: ERROR, {duration:.2f}s – {e}", file=sys.stderr)
        return False

# ----------------------------
# Main loop
# ----------------------------

def main():
    # Start universe.json watcher in background
    watcher_thread = Thread(target=start_universe_watcher, daemon=True)
    watcher_thread.start()

    core_list = core_assets()
    core_symbols = [a["symbol"] for a in core_list]
    print(f"Scheduler (core): canonical compute → compute.db")
    print(f"Processing {len(core_symbols)} symbols: {core_symbols}")
    print("TFs:", ", ".join(TIMEFRAMES))
    print("Scheduler starting...\n")

    while True:
        try:
            # Reload universe if universe.json changed
            if check_and_clear_universe_changed():
                core_list = core_assets()
                core_symbols = [a["symbol"] for a in core_list]
                print(f"[CONFIG] Reloaded universe: {len(core_symbols)} symbols: {core_symbols}\n")

            now_est = datetime.now(ZoneInfo("America/New_York"))
            is_us_trading_day = now_est.weekday() < 5
            is_us_trading_hours = 9 <= now_est.hour < 16

            changed_symbols: List[str] = []
            total_polled = 0
            total_inserted = 0

            for asset in core_list:
                symbol = asset["symbol"]
                asset_class = asset.get("asset_class", "")
                if "US_EQUITY" in asset_class and (not is_us_trading_day or not is_us_trading_hours):
                    print(f"Skipping {symbol} – outside US trading hours")
                    continue

                leg = LegacyAsset.from_dict(asset)
                sym = leg.symbol.upper()
                vend = (leg.vendor_symbol or leg.symbol).upper()

                inserted, polled = fetch_incremental_symbol(sym, vend)
                total_polled += polled
                total_inserted += inserted
                if inserted > 0:
                    changed_symbols.append(sym)

            for sym in changed_symbols:
                print(f"\n[PIPELINE] {sym} new bars detected -> canonical compute...")
                run_canonical_compute(sym)

            if not changed_symbols:
                if total_polled == 0:
                    print(f"[PIPELINE] Session-gated: no TFs polled. Sleeping {SLEEP_SEC}s.\n")
                else:
                    print(f"[PIPELINE] Polled={total_polled} calls, inserted={total_inserted}. No new bars. Sleeping {SLEEP_SEC}s.\n")
            else:
                print(f"\n[PIPELINE] Updated symbols: {', '.join(changed_symbols)} | polled={total_polled} inserted={total_inserted}. Sleeping {SLEEP_SEC}s.\n")

            time.sleep(SLEEP_SEC)

        except KeyboardInterrupt:
            print("\nStopping scheduler (Ctrl+C).")
            return
        except Exception as e:
            print(f"[PIPELINE] ERROR: {e}", file=sys.stderr)
            time.sleep(15)

if __name__ == "__main__":
    main()
