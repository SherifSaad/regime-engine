# core/storage/__init__.py
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("REGIME_DB_PATH", "data/regime_cache.db")


def get_conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    # Raw bars cache (vendor-ingested)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bars (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            ts TEXT NOT NULL,            -- ISO8601
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            source TEXT DEFAULT 'twelvedata',
            PRIMARY KEY (symbol, timeframe, ts)
        );
        """
    )

    # Latest computed state (fast UI read)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS latest_state (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,          -- ISO8601 of latest bar used
            state_json TEXT NOT NULL,    -- full latest_state payload (unwrapped, includes classification, metrics, etc.)
            updated_at TEXT NOT NULL,    -- when we computed it
            PRIMARY KEY (symbol, timeframe)
        );
        """
    )

    # Optional: full history of states (for timelines without recompute)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS state_history (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            state_json TEXT NOT NULL,
            PRIMARY KEY (symbol, timeframe, asof)
        );
        """
    )

    # Track last successful fetch timestamp so we can do incremental updates
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_cursor (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            last_ts TEXT,               -- ISO8601
            PRIMARY KEY (symbol, timeframe)
        );
        """
    )

    conn.commit()
    conn.close()
