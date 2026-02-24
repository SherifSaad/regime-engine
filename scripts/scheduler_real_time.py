#!/usr/bin/env python3
"""
Real-time scheduler – core regime symbols only.

Loop:
  1) For each asset in real_time_assets():
       - Skip US equities outside US trading hours (RTH)
       - Fetch incremental bars (overlap) -> append to Parquet via BarsProvider
  2) If ANY new bars inserted -> compute ALL 5 TF states (read from Parquet, write state to regime_cache.db)
  3) Sleep and repeat

Notes:
- TWELVEDATA_API_KEY required in .env
- REGIME_DB_PATH optional
- REGIME_LOOKBACK optional (default 2000)
"""

import os
import sys
import time
import sqlite3
import requests
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Tuple

import pandas as pd
import polars as pl
from dotenv import load_dotenv

from regime_engine.cli import compute_market_state_from_df

from core.assets_registry import real_time_assets, LegacyAsset
from core.asset_class_rules import should_poll
from core.providers.bars_provider import BarsProvider

# ----------------------------
# Env / Config
# ----------------------------

load_dotenv()

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
TD_TS_URL = "https://api.twelvedata.com/time_series"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = str(PROJECT_ROOT / "data" / "regime_cache.db")

OVERLAP_BARS = 5
DEFAULT_LOOKBACK = int(os.getenv("REGIME_LOOKBACK", "2000"))
SLEEP_SEC = 30
RATE_LIMIT_SLEEP = 65

# ----------------------------
# Helpers
# ----------------------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def api_key() -> str:
    k = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not k:
        raise RuntimeError("Missing TWELVEDATA_API_KEY (check .env)")
    return k

def db_path() -> str:
    return os.getenv("REGIME_DB_PATH", DEFAULT_DB_PATH)

def connect(db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

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


def fetch_incremental_symbol(conn: sqlite3.Connection, symbol: str, vendor_symbol: str) -> Tuple[int, int]:
    """Fetch new bars from API and append to Parquet via BarsProvider."""
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

def load_bars_df_from_parquet(symbol: str, tf: str, limit: int) -> pd.DataFrame:
    """Load bars from Parquet for compute. Returns pandas DataFrame with ts index."""
    lf = BarsProvider.get_bars(symbol, tf)
    pl_df = lf.sort("ts", descending=True).head(limit).collect()
    if pl_df.is_empty():
        return pd.DataFrame()
    df = pd.DataFrame(pl_df.to_dicts())
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def get_latest_bar_ts_from_parquet(symbol: str, tf: str) -> Optional[str]:
    """Get latest bar ts from Parquet."""
    lf = BarsProvider.get_bars(symbol, tf)
    row = lf.select(pl.col("ts").max()).collect()
    if row.is_empty() or row[0, 0] is None:
        return None
    return str(row[0, 0])

def upsert_latest_state(conn: sqlite3.Connection, symbol: str, tf: str, asof: str, state: Dict) -> None:
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

def insert_state_history(conn: sqlite3.Connection, symbol: str, tf: str, asof: str, state: Dict) -> None:
    state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    conn.execute(
        """
        INSERT OR IGNORE INTO state_history(symbol,timeframe,asof,state_json)
        VALUES(?,?,?,?);
        """,
        (symbol, tf, asof, state_json),
    )

def compute_and_persist_symbol(conn: sqlite3.Connection, symbol: str, lookback: int) -> None:
    """Read bars from Parquet, compute state, persist to regime_cache.db."""
    for tf in TIMEFRAMES:
        latest_ts = get_latest_bar_ts_from_parquet(symbol, tf)
        if not latest_ts:
            continue

        df = load_bars_df_from_parquet(symbol, tf, lookback)
        if df.empty or len(df) < 200:
            continue

        df = df.set_index("ts")
        df.index = pd.to_datetime(df.index)

        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]

        for c in ["open", "high", "low", "close", "adj_close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["close"])

        state = compute_market_state_from_df(
            df,
            symbol,
            diagnostics=False,
            include_escalation_v2=True,
        )
        state["timeframe"] = tf

        asof = state.get("asof", latest_ts)

        upsert_latest_state(conn, symbol, tf, asof, state)
        insert_state_history(conn, symbol, tf, asof, state)
        conn.commit()

        print(f"[COMPUTE] {symbol} {tf}: wrote asof={asof}")

# ----------------------------
# Main loop
# ----------------------------

def main():
    db = db_path()
    os.makedirs(os.path.dirname(db), exist_ok=True)

    real_time_list = real_time_assets()
    real_time_symbols = [a["symbol"] for a in real_time_list]
    print("DB:", db)
    print("LOOKBACK:", DEFAULT_LOOKBACK)
    print(f"Scheduler (real-time only): processing {len(real_time_symbols)} symbols: {real_time_symbols}")
    print("TFs:", ", ".join(TIMEFRAMES))
    print("Scheduler starting...\n")

    try:
        from core.storage import init_db  # type: ignore
        init_db()
    except Exception:
        pass

    while True:
        try:
            now_est = datetime.now(ZoneInfo("America/New_York"))
            is_us_trading_day = now_est.weekday() < 5
            is_us_trading_hours = 9 <= now_est.hour < 16

            with connect(db) as conn:
                changed_symbols: List[str] = []
                total_polled = 0
                total_inserted = 0

                for asset in real_time_list:
                    symbol = asset["symbol"]
                    asset_class = asset.get("asset_class", "")
                    if "US_EQUITY" in asset_class and (not is_us_trading_day or not is_us_trading_hours):
                        print(f"Skipping {symbol} – outside US trading hours")
                        continue

                    leg = LegacyAsset.from_dict(asset)
                    sym = leg.symbol.upper()
                    vend = (leg.vendor_symbol or leg.symbol).upper()

                    inserted, polled = fetch_incremental_symbol(conn, sym, vend)
                    total_polled += polled
                    total_inserted += inserted
                    if inserted > 0:
                        changed_symbols.append(sym)

                for sym in changed_symbols:
                    print(f"\n[PIPELINE] {sym} new bars detected -> computing ALL TFs...")
                    compute_and_persist_symbol(conn, sym, DEFAULT_LOOKBACK)

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
