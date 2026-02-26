#!/usr/bin/env python3
"""
Single compute step: escalation_history_v3 + state_history (market_state) + latest_state.

Reads bars from Parquet (default) or frozen_*.db (deprecated). Writes to compute.db.
Full history, no caps. Hedge fund standards.

Outputs (in compute.db):
- escalation_history_v3 (esc_raw, esc_pctl, esc_bucket, event_flag, etc.)
- state_history (per-bar regime state with 11 metrics + escalation_v2)
- latest_state (state_json + hazard_score + cross_tf_consensus)

Resumable: skips asofs already in state_history for regime loop.

Usage:
  python scripts/compute_asset_full.py --symbol QQQ
  python scripts/compute_asset_full.py --symbol QQQ -t 1day
  python scripts/compute_asset_full.py --symbol QQQ --input parquet   # default
  python scripts/compute_asset_full.py --symbol QQQ --input frozen   # deprecated (emit warning)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from core.manifest import write_compute_manifest
from core.providers.bars_provider import BarsProvider
from core.schema_versions import COMPUTE_DB_SCHEMA_VERSION
from regime_engine.cli import compute_market_state_from_df
from regime_engine.escalation_fast import compute_state_history_batch
from regime_engine.escalation_buckets import compute_bucket_from_percentile
from regime_engine.escalation_fast import compute_dsr_iix_ss_arrays_fast
from regime_engine.era_production import compute_esc_pctl_era_all
from regime_engine.standard_v2_1 import TimeframePolicy
from regime_engine.escalation_v2 import (
    compute_escalation_v2_series,
    compute_escalation_v2_pct_series,
    expanding_percentile_transform,
    rolling_percentile_transform,
    get_escalation_metadata,
)
from regime_engine.features import compute_ema

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
MIN_BARS = 400
MIN_BARS_STATE = 200
COMMIT_EVERY = 50
STATE_BATCH_SIZE = 5000
ESCALATION_BATCH_SIZE = 1000  # avoid "database is locked" on large inserts
HORIZON_H = 20

PCTL_WINDOWS = {
    "1day": {"p252": 252, "p504": 504, "p1260": 1260},
    "1week": {"p52": 52, "p104": 104, "p260": 260},
}

def asset_dir(symbol: str) -> Path:
    return PROJECT_ROOT / "data" / "assets" / symbol


def compute_db_path(symbol: str) -> Path:
    return asset_dir(symbol) / "compute.db"


def latest_frozen_db_path(symbol: str) -> Path | None:
    d = asset_dir(symbol)
    cands = sorted(d.glob("frozen_*.db"))
    if not cands:
        return None
    return cands[-1]


def now_utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def load_bars(conn: sqlite3.Connection, symbol: str, tf: str) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close, volume
        FROM bars
        WHERE symbol=? AND timeframe=?
        ORDER BY ts ASC
        """,
        (symbol, tf),
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts_str"] = df["ts"].astype(str)
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df["adj_close"] = df["close"]
    for c in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"])
    return df


def load_bars_from_parquet(symbol: str, tf: str) -> pd.DataFrame:
    """Load full bars from Parquet. No cap. Full history."""
    lf = BarsProvider.get_bars(symbol, tf)
    pl_df = lf.sort("ts").collect()
    if pl_df.is_empty():
        return pd.DataFrame()
    # Build pandas DataFrame without pyarrow (Polars.to_pandas requires pyarrow)
    df = pd.DataFrame(
        {c: pl_df[c].to_numpy() for c in pl_df.columns}
    )
    df["ts_str"] = df["ts"].astype(str)
    df = df.set_index("ts")
    df["adj_close"] = df["close"]
    for c in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"])
    return df.sort_index()


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS escalation_history_v3 (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            esc_raw REAL,
            esc_pctl REAL,
            esc_pctl_expanding REAL,
            esc_pctl_252 REAL,
            esc_pctl_504 REAL,
            esc_pctl_1260 REAL,
            esc_pctl_2520 REAL,
            esc_pctl_52 REAL,
            esc_pctl_104 REAL,
            esc_pctl_260 REAL,
            esc_pctl_era REAL,
            esc_bucket TEXT,
            fwd_absret_h REAL,
            event_flag INTEGER,
            event_severity TEXT,
            PRIMARY KEY(symbol, timeframe, asof)
        );
        """
    )
    existing_esc = {row[1] for row in conn.execute("PRAGMA table_info(escalation_history_v3);").fetchall()}
    for col, ctype in [
        ("esc_pctl_expanding", "REAL"),
        ("esc_pctl_252", "REAL"), ("esc_pctl_504", "REAL"), ("esc_pctl_1260", "REAL"), ("esc_pctl_2520", "REAL"),
        ("esc_pctl_52", "REAL"), ("esc_pctl_104", "REAL"), ("esc_pctl_260", "REAL"),
        ("esc_pctl_era", "REAL"), ("esc_pctl_era_confidence", "REAL"), ("esc_pctl_era_adj", "REAL"),
        ("fwd_absret_h", "REAL"), ("event_flag", "INTEGER"),
        ("event_severity", "TEXT"),
    ]:
        if col not in existing_esc:
            conn.execute(f"ALTER TABLE escalation_history_v3 ADD COLUMN {col} {ctype}")

    conn.execute(
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS latest_state (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            state_json TEXT,
            hazard_score REAL,
            cross_tf_consensus REAL,
            updated_at TEXT,
            updated_utc TEXT,
            PRIMARY KEY (symbol, timeframe)
        );
        """
    )
    existing_ls = {row[1] for row in conn.execute("PRAGMA table_info(latest_state);").fetchall()}
    for col, ctype in [
        ("state_json", "TEXT"), ("hazard_score", "REAL"), ("cross_tf_consensus", "REAL"),
        ("updated_at", "TEXT"), ("updated_utc", "TEXT"),
    ]:
        if col not in existing_ls:
            conn.execute(f"ALTER TABLE latest_state ADD COLUMN {col} {ctype}")
    conn.commit()


def run_escalation_tf(
    df: pd.DataFrame,
    conn_write: sqlite3.Connection,
    symbol: str,
    tf: str,
) -> int:
    """Backfill escalation_history_v3 for one TF. Returns row count."""
    if len(df) < MIN_BARS:
        return 0

    print(f"  escalation: 1/5 dsr/iix/ss ({len(df)} bars)...", flush=True)
    dsr_arr, iix_arr, ss_arr = compute_dsr_iix_ss_arrays_fast(df, symbol)
    close_arr = df["close"].iloc[20:].astype(float).values
    ema_arr = compute_ema(df["close"], 100).iloc[20:].astype(float).values
    esc_full = compute_escalation_v2_series(dsr_arr, iix_arr, ss_arr, close_arr, ema_arr)

    w_max = 12
    n_esc = max(0, len(df) - 31)
    esc_vals = list(esc_full[w_max - 1 : w_max - 1 + n_esc]) if n_esc > 0 else []
    esc_raw = np.concatenate(
        [np.full(min(31, len(df)), np.nan, dtype=float), np.array(esc_vals, dtype=float)]
    )
    if len(esc_raw) < len(df):
        esc_raw = np.concatenate([np.full(len(df) - len(esc_raw), np.nan), esc_raw])
    elif len(esc_raw) > len(df):
        esc_raw = esc_raw[-len(df) :]

    esc_series = pd.Series(esc_raw, index=df.index)

    tf_policy = TimeframePolicy(tf)
    CONF_TARGET = tf_policy.bars_per_trading_year()
    PCTL_MIN_BARS = tf_policy.percentile_min_bars()

    print(f"  escalation: 2/5 percentiles (era=production, rolling 252/504/1260/2520)...", flush=True)
    esc_pctl_expanding = compute_escalation_v2_pct_series(esc_series, min_bars=PCTL_MIN_BARS)

    esc_pctl_era_adj, esc_pctl_era, esc_pctl_era_confidence = compute_esc_pctl_era_all(
        esc_series, df, symbol, tf
    )
    pctl = esc_pctl_era_adj  # production signal (institutional)

    close = df["close"].astype(float).values
    n = len(close)
    fwd_abs = np.full(n, np.nan, dtype=float)
    H = HORIZON_H
    for i in range(n):
        j2 = min(n - 1, i + H)
        if i + 1 > j2:
            continue
        base = close[i]
        if not np.isfinite(base) or base == 0:
            continue
        window = close[i + 1 : j2 + 1] / base - 1.0
        fwd_abs[i] = float(np.nanmax(np.abs(window)))

    fwd_series = pd.Series(fwd_abs, index=df.index)
    fwd_pctl = expanding_percentile_transform(fwd_series, min_bars=PCTL_MIN_BARS)  # PCTL_MIN_BARS from tf_policy
    event_flag = np.zeros(n, dtype=int)
    severity = np.array([None] * n, dtype=object)
    for i, p in enumerate(fwd_pctl.values):
        if p is None or (isinstance(p, float) and np.isnan(p)):
            event_flag[i] = 0
            severity[i] = None
            continue
        if p >= 0.95:
            event_flag[i] = 1
            severity[i] = "CRISIS" if p >= 0.99 else ("SEVERE" if p >= 0.975 else "MODERATE")
        else:
            event_flag[i] = 0
            severity[i] = "MILD" if p >= 0.90 else None

    print(f"  escalation: 3/5 rolling percentiles (252/504/1260/2520)...", flush=True)
    p252 = rolling_percentile_transform(esc_series, window=252)
    p504 = rolling_percentile_transform(esc_series, window=504)
    p1260 = rolling_percentile_transform(esc_series, window=1260)
    p2520 = rolling_percentile_transform(esc_series, window=2520)
    p52 = p104 = p260 = None
    if tf == "1week":
        p52 = rolling_percentile_transform(esc_series, window=52)
        p104 = rolling_percentile_transform(esc_series, window=104)
        p260 = rolling_percentile_transform(esc_series, window=260)

    buckets = []
    for x in pctl.values:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            buckets.append("NA")
        else:
            buckets.append(compute_bucket_from_percentile(float(x))[0])

    def fval(x):
        if x is None:
            return None
        if isinstance(x, float) and np.isnan(x):
            return None
        return float(x)

    p252_vals = p252.values
    p504_vals = p504.values
    p1260_vals = p1260.values
    p2520_vals = p2520.values
    p52_vals = p52.values if p52 is not None else [None] * len(df)
    p104_vals = p104.values if p104 is not None else [None] * len(df)
    p260_vals = p260.values if p260 is not None else [None] * len(df)
    esc_pctl_exp_vals = esc_pctl_expanding.values
    esc_pctl_era_conf_vals = esc_pctl_era_confidence.values
    esc_pctl_era_adj_vals = esc_pctl_era_adj.values

    print(f"  escalation: 4/5 building rows...", flush=True)
    rows = []
    for i, ts_str in enumerate(df["ts_str"].values):
        asof = ts_str
        ev, pc, bk = esc_raw[i], pctl.values[i], buckets[i]
        rows.append((
            symbol, tf, asof,
            fval(ev), fval(pc),
            fval(esc_pctl_exp_vals[i]),
            fval(p252_vals[i]), fval(p504_vals[i]), fval(p1260_vals[i]), fval(p2520_vals[i]),
            fval(p52_vals[i]), fval(p104_vals[i]), fval(p260_vals[i]),
            fval(esc_pctl_era.values[i]),
            fval(esc_pctl_era_conf_vals[i]),
            fval(esc_pctl_era_adj_vals[i]),
            None if bk is None else str(bk),
            fval(fwd_abs[i]),
            None if not np.isfinite(fwd_abs[i]) else int(event_flag[i]),
            None if severity[i] is None else str(severity[i]),
        ))

    print(f"  escalation: 5/5 writing {len(rows)} rows...", flush=True)
    stmt = """
        INSERT OR REPLACE INTO escalation_history_v3(
          symbol,timeframe,asof,
          esc_raw,esc_pctl,
          esc_pctl_expanding,
          esc_pctl_252,esc_pctl_504,esc_pctl_1260,esc_pctl_2520,
          esc_pctl_52,esc_pctl_104,esc_pctl_260,
          esc_pctl_era,esc_pctl_era_confidence,esc_pctl_era_adj,esc_bucket,
          fwd_absret_h,event_flag,event_severity
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
    """
    for i in range(0, len(rows), ESCALATION_BATCH_SIZE):
        batch = rows[i : i + ESCALATION_BATCH_SIZE]
        conn_write.executemany(stmt, batch)
        conn_write.commit()
    return len(rows)


def run_state_tf(
    df: pd.DataFrame,
    conn_write: sqlite3.Connection,
    symbol: str,
    tf: str,
) -> tuple[int, int]:
    """Backfill state_history for one TF. Returns (wrote, skipped). Batch insert, one transaction."""
    if len(df) < MIN_BARS_STATE:
        return 0, 0

    rows_done = conn_write.execute(
        "SELECT asof FROM state_history WHERE symbol=? AND timeframe=?",
        (symbol, tf),
    ).fetchall()
    asofs_done = {r[0] for r in rows_done}

    # Preload esc_pctl (esc_pctl_era_adj) from escalation_history_v3 for bucket override
    esc_rows = conn_write.execute(
        "SELECT asof, esc_pctl FROM escalation_history_v3 WHERE symbol=? AND timeframe=?",
        (symbol, tf),
    ).fetchall()
    asof_to_esc_pctl = {r[0]: r[1] for r in esc_rows}

    ts_strs = df["ts_str"].values
    asof_set = set(ts_strs)
    asof_to_esc_pctl_full = {a: asof_to_esc_pctl.get(a) for a in asof_set}

    t0 = time.perf_counter()
    batch_results = compute_state_history_batch(
        df, symbol, asof_to_esc_pctl_full,
    )
    t_compute = time.perf_counter() - t0

    rows_to_insert: list[tuple[str, str, str, str]] = []
    for asof, state in batch_results:
        if asof in asofs_done:
            continue
        state["timeframe"] = tf
        state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
        rows_to_insert.append((symbol, tf, asof, state_json))

    wrote = len(rows_to_insert)
    skipped = sum(1 for s in ts_strs if s in asofs_done)

    t1 = time.perf_counter()
    if rows_to_insert:
        for chunk_start in range(0, wrote, STATE_BATCH_SIZE):
            chunk = rows_to_insert[chunk_start : chunk_start + STATE_BATCH_SIZE]
            conn_write.executemany(
                "INSERT OR IGNORE INTO state_history(symbol,timeframe,asof,state_json) VALUES(?,?,?,?)",
                chunk,
            )
        last = rows_to_insert[-1]
        conn_write.execute(
            """
            INSERT INTO latest_state(symbol,timeframe,asof,state_json,updated_at,updated_utc)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(symbol,timeframe) DO UPDATE SET
                asof=excluded.asof,
                state_json=excluded.state_json,
                updated_at=excluded.updated_at,
                updated_utc=excluded.updated_utc
            """,
            (last[0], last[1], last[2], last[3], now_utc_iso(), now_utc_iso()),
        )
        conn_write.commit()
    t_write = time.perf_counter() - t1

    print(f"  state_history: wrote={wrote} skipped={skipped} | compute={t_compute:.1f}s write={t_write:.1f}s", flush=True)
    return wrote, skipped


def hazard_score_from_pctl(p: float | None) -> float | None:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return None
    return float(max(0.0, min(100.0, 100.0 * p)))


def update_latest_state_hazard(conn: sqlite3.Connection, symbol: str) -> None:
    """Update latest_state with hazard_score and cross_tf_consensus from escalation_history_v3."""
    latest = conn.execute(
        """
        SELECT timeframe, MAX(asof) AS asof
        FROM escalation_history_v3
        WHERE symbol=?
        GROUP BY timeframe
        """,
        (symbol,),
    ).fetchall()
    tf_to_asof = {tf: asof for tf, asof in latest}
    tf_to_pctl = {}
    for tf, asof in tf_to_asof.items():
        row = conn.execute(
            "SELECT esc_pctl FROM escalation_history_v3 WHERE symbol=? AND timeframe=? AND asof=?",
            (symbol, tf, asof),
        ).fetchone()
        tf_to_pctl[tf] = None if row is None else row[0]

    vals = [v for v in tf_to_pctl.values() if v is not None]
    consensus = float(np.mean(vals)) if vals else None
    now_utc = now_utc_iso()

    for tf, asof in tf_to_asof.items():
        p = tf_to_pctl.get(tf)
        hz = hazard_score_from_pctl(p)
        existing = conn.execute(
            "SELECT state_json FROM latest_state WHERE symbol=? AND timeframe=?",
            (symbol, tf),
        ).fetchone()
        state_json = existing[0] if existing and existing[0] else "{}"
        conn.execute(
            """
            INSERT OR REPLACE INTO latest_state(
                symbol,timeframe,asof,state_json,hazard_score,cross_tf_consensus,updated_at,updated_utc
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (symbol, tf, asof, state_json, hz, consensus, now_utc, now_utc),
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Single compute: escalation + state_history + latest_state")
    ap.add_argument("--symbol", required=True, help="e.g. QQQ, SPY")
    ap.add_argument("-t", "--timeframe", help="Single TF. Default: all")
    ap.add_argument(
        "--input",
        choices=["parquet", "frozen"],
        default="parquet",
        help="Bar source: parquet (default). frozen is deprecated.",
    )
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    tfs = [args.timeframe] if args.timeframe else TIMEFRAMES
    use_parquet = args.input == "parquet"

    conn_read: sqlite3.Connection | None = None
    frozen: Path | None = None

    if use_parquet:
        print(f"[compute_asset_full] symbol={symbol} input=parquet (full history)")
    else:
        import warnings

        warnings.warn(
            "--input frozen is deprecated. Use Parquet (default). Pipeline will remove freeze step.",
            DeprecationWarning,
            stacklevel=2,
        )
        print("[compute_asset_full] WARNING: --input frozen is deprecated. Use Parquet (default).")
        frozen = latest_frozen_db_path(symbol)
        if frozen is None or not frozen.exists():
            raise SystemExit(
                f"No frozen DB found for {symbol}. "
                f"Use Parquet: run migrate_live_to_parquet.py --symbol {symbol} first."
            )
        conn_read = sqlite3.connect(str(frozen), timeout=60)
        print(f"[compute_asset_full] symbol={symbol} input=frozen read={frozen}")

    compute_db = compute_db_path(symbol)
    compute_db.parent.mkdir(parents=True, exist_ok=True)

    conn_write = sqlite3.connect(str(compute_db), timeout=60)
    try:
        conn_write.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        pass  # Fallback to default (DELETE); some filesystems don't support WAL
    conn_write.execute("PRAGMA synchronous=NORMAL;")
    ensure_tables(conn_write)

    # Write schema version on create/update
    conn_write.execute("DELETE FROM schema_version")
    conn_write.execute(
        "INSERT INTO schema_version(version, updated_at) VALUES(?, ?)",
        (COMPUTE_DB_SCHEMA_VERSION, now_utc_iso()),
    )
    conn_write.commit()

    print(f"  write={compute_db}")
    total_esc = 0
    total_state_wrote = 0
    total_state_skipped = 0
    bar_count_used = 0

    for tf in tfs:
        print(f"\n--- {tf} ---", flush=True)
        if use_parquet:
            df = load_bars_from_parquet(symbol, tf)
        else:
            assert conn_read is not None
            df = load_bars(conn_read, symbol, tf)
        if df.empty:
            print(f"  no bars for {tf}, skipping")
            continue
        bar_count_used += len(df)
        print(f"  bars: {len(df)}", flush=True)
        print(f"  escalation: computing...", flush=True)
        n_esc = run_escalation_tf(df, conn_write, symbol, tf)
        total_esc += n_esc
        print(f"  escalation: {n_esc} rows", flush=True)
        print(f"  state: computing (per-bar)...", flush=True)
        w, s = run_state_tf(df, conn_write, symbol, tf)
        total_state_wrote += w
        total_state_skipped += s

    update_latest_state_hazard(conn_write, symbol)
    conn_write.commit()

    write_compute_manifest(
        symbol,
        bar_count_used=bar_count_used,
        compute_db_path=compute_db,
    )

    if conn_read is not None:
        conn_read.close()
    conn_write.close()

    print(f"\nDONE. escalation={total_esc} | state wrote={total_state_wrote} skipped={total_state_skipped}")


if __name__ == "__main__":
    main()
