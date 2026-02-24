#!/usr/bin/env python3
"""
Earnings scheduler – 1h + 1week bars for earnings tier symbols.

100% Parquet for bars: reads (last_ts/cursor) and writes from Parquet via BarsProvider.
Single run: fetch 1h and 1week bars for all daily_assets(), append to Parquet.
Compute regime (Polars incremental + cache) and persist to regime_cache.db.
No RTH check – runs once per day (cron) or on demand.
Only 1h and 1week (not 15min, 4h, 1d) for earnings assets.

Notes:
- TWELVEDATA_API_KEY required in .env
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import polars as pl
import requests
from dotenv import load_dotenv

from core.assets_registry import daily_assets
from core.compute.regime_engine_polars import (
    CODE_VERSION,
    RAW_COLS,
    compute_regime_polars,
    compute_regime_polars_incremental,
    load_regime_cache,
    persist_regime_cache,
    polars_result_to_state,
)
from core.providers.bars_provider import BarsProvider
from core.storage import get_conn, init_db

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
EARNINGS_TIMEFRAMES = ["1h", "1week"]
OVERLAP_BARS = 5
RATE_LIMIT_SLEEP = 65
EARNINGS_LOOKBACK = int(os.getenv("REGIME_LOOKBACK", "2000"))

# ----------------------------
# Helpers
# ----------------------------

def api_key() -> str:
    k = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not k:
        raise RuntimeError("Missing TWELVEDATA_API_KEY (check .env)")
    return k

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_latest_bar_ts_from_parquet(symbol: str, tf: str) -> Optional[str]:
    """Get latest bar ts from Parquet."""
    lf = BarsProvider.get_bars(symbol, tf)
    row = lf.select(pl.col("ts").max()).collect()
    if row.is_empty() or row[0, 0] is None:
        return None
    return str(row[0, 0])


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


def upsert_latest_state(conn, symbol: str, tf: str, asof: str, state: Dict) -> None:
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    updated_at = now_utc_iso()
    conn.execute(
        """
        INSERT INTO latest_state(symbol,timeframe,asof,state_json,updated_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(symbol,timeframe) DO UPDATE SET
            asof=excluded.asof,
            state_json=excluded.state_json,
            updated_at=excluded.updated_at;
        """,
        (symbol, tf, asof, state_json, updated_at),
    )


def insert_state_history(conn, symbol: str, tf: str, asof: str, state: Dict) -> None:
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    conn.execute(
        """
        INSERT OR IGNORE INTO state_history(symbol,timeframe,asof,state_json)
        VALUES(?,?,?,?);
        """,
        (symbol, tf, asof, state_json),
    )


def compute_and_persist_earnings_symbol(conn, symbol: str, lookback: int) -> None:
    """Compute regime for 1h + 1week (Polars incremental + cache), persist to regime_cache.db."""
    for tf in EARNINGS_TIMEFRAMES:
        latest_ts = get_latest_bar_ts_from_parquet(symbol, tf)
        if not latest_ts:
            continue

        t0 = time.time()
        cache_status = "MISS"
        try:
            lf = BarsProvider.get_bars(symbol, tf)
            pl_df = lf.sort("ts", descending=True).head(lookback).collect()
            if pl_df.is_empty() or len(pl_df) < 200:
                continue
            pl_df = pl_df.select([c for c in RAW_COLS if c in pl_df.columns]).sort("ts")

            n_rows = len(pl_df)
            prev_result, prev_meta = load_regime_cache(symbol, tf)

            # Cache hit
            if prev_meta and prev_result is not None:
                if (
                    prev_meta.get("last_bar_ts") == latest_ts
                    and prev_meta.get("n_rows") == n_rows
                    and prev_meta.get("code_version") == CODE_VERSION
                ):
                    cache_status = "HIT"
                    result_df = prev_result
                    state = polars_result_to_state(result_df, symbol, tf)
                    if state:
                        asof = state.get("asof", latest_ts)
                        upsert_latest_state(conn, symbol, tf, asof, state)
                        insert_state_history(conn, symbol, tf, asof, state)
                        conn.commit()
                        duration = time.time() - t0
                        print(f"    [{symbol} {tf}] Compute: {cache_status}, {duration:.2f}s")
                        continue

            # Compute: incremental or full
            if prev_result is not None and not prev_result.is_empty():
                prev_max_ts = prev_result["ts"].max()
                new_bars = pl_df.filter(pl.col("ts") > prev_max_ts)
                if len(new_bars) > 0 and len(pl_df) >= len(prev_result):
                    result_df = compute_regime_polars_incremental(new_bars, prev_result, CODE_VERSION)
                else:
                    result_df = compute_regime_polars(pl_df)
            else:
                result_df = compute_regime_polars(pl_df)

            state = polars_result_to_state(result_df, symbol, tf)
            if not state:
                continue

            asof = state.get("asof", latest_ts)
            upsert_latest_state(conn, symbol, tf, asof, state)
            insert_state_history(conn, symbol, tf, asof, state)
            conn.commit()
            persist_regime_cache(symbol, tf, result_df, latest_ts, len(result_df), CODE_VERSION)
            duration = time.time() - t0
            print(f"    [{symbol} {tf}] Compute: {cache_status}, {duration:.2f}s")
        except Exception as e:
            duration = time.time() - t0
            logging.exception("[%s %s] Compute failed: %s", symbol, tf, e)
            print(f"    [{symbol} {tf}] Compute: ERROR, {duration:.2f}s – {e}", file=sys.stderr)


# ----------------------------
# Main
# ----------------------------

def main():
    daily_list = daily_assets()
    print(f"Earnings daily run – processing {len(daily_list)} symbols")

    if not daily_list:
        print("No daily/earnings symbols enabled")
        return

    init_db()
    conn = get_conn()

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
                compute_and_persist_earnings_symbol(conn, symbol, EARNINGS_LOOKBACK)
        except Exception as e:
            print(f"  Error updating {symbol}: {e}")

    conn.close()
    print("Earnings daily run complete")

if __name__ == "__main__":
    main()
