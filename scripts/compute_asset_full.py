#!/usr/bin/env python3
"""
Single compute step: escalation_history_v3 + state_history (market_state) + latest_state.

Reads bars from Parquet (default) or frozen_*.db. Writes to compute.db.
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
  python scripts/compute_asset_full.py --symbol QQQ --input frozen   # legacy
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from core.providers.bars_provider import BarsProvider
from regime_engine.cli import compute_market_state_from_df
from regime_engine.escalation_buckets import compute_bucket_from_percentile
from regime_engine.escalation_fast import compute_dsr_iix_ss_arrays_fast
from regime_engine.escalation_v2 import compute_escalation_v2_series, rolling_percentile_transform
from regime_engine.features import compute_ema

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
PCTL_WINDOW = 504
MIN_BARS = 400
MIN_BARS_STATE = 200
COMMIT_EVERY = 50
HORIZON_H = 20

PCTL_WINDOWS = {
    "1day": {"p252": 252, "p504": 504, "p1260": 1260},
    "1week": {"p52": 52, "p104": 104, "p260": 260},
}

ERAS = [
    ("pre2010", None, "2010-01-01"),
    ("2010_2019", "2010-01-01", "2020-01-01"),
    ("2020plus", "2020-01-01", None),
]


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
        CREATE TABLE IF NOT EXISTS escalation_history_v3 (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,
            esc_raw REAL,
            esc_pctl REAL,
            esc_pctl_252 REAL,
            esc_pctl_504 REAL,
            esc_pctl_1260 REAL,
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
        ("esc_pctl_252", "REAL"), ("esc_pctl_504", "REAL"), ("esc_pctl_1260", "REAL"),
        ("esc_pctl_52", "REAL"), ("esc_pctl_104", "REAL"), ("esc_pctl_260", "REAL"),
        ("esc_pctl_era", "REAL"), ("fwd_absret_h", "REAL"), ("event_flag", "INTEGER"),
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
    print(f"  escalation: 2/5 percentiles...", flush=True)
    pctl = rolling_percentile_transform(esc_series, window=PCTL_WINDOW)

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
    fwd_pctl = rolling_percentile_transform(fwd_series, window=PCTL_WINDOW)
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

    print(f"  escalation: 3/5 multi-horizon...", flush=True)
    p252 = p504 = p1260 = None
    p52 = p104 = p260 = None
    if tf in PCTL_WINDOWS:
        w = PCTL_WINDOWS[tf]
        if tf == "1day":
            p252 = rolling_percentile_transform(esc_series, window=w["p252"])
            p504 = rolling_percentile_transform(esc_series, window=w["p504"])
            p1260 = rolling_percentile_transform(esc_series, window=w["p1260"])
        elif tf == "1week":
            p52 = rolling_percentile_transform(esc_series, window=w["p52"])
            p104 = rolling_percentile_transform(esc_series, window=w["p104"])
            p260 = rolling_percentile_transform(esc_series, window=w["p260"])

    esc_pctl_era = pd.Series(np.full(len(df), np.nan, dtype=float), index=df.index)
    for _, start_s, end_s in ERAS:
        start = pd.to_datetime(start_s) if start_s else None
        end = pd.to_datetime(end_s) if end_s else None
        mask = pd.Series(True, index=df.index)
        if start is not None:
            mask &= (df.index >= start)
        if end is not None:
            mask &= (df.index < end)
        if mask.sum() == 0:
            continue
        sub = esc_series.loc[mask]
        esc_pctl_era.loc[mask] = rolling_percentile_transform(sub, window=PCTL_WINDOW).values

    buckets = []
    for x in pctl.values:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            buckets.append(None)
        else:
            buckets.append(compute_bucket_from_percentile(float(x))[0])

    def fval(x):
        if x is None:
            return None
        if isinstance(x, float) and np.isnan(x):
            return None
        return float(x)

    p252_vals = p252.values if p252 is not None else [None] * len(df)
    p504_vals = p504.values if p504 is not None else [None] * len(df)
    p1260_vals = p1260.values if p1260 is not None else [None] * len(df)
    p52_vals = p52.values if p52 is not None else [None] * len(df)
    p104_vals = p104.values if p104 is not None else [None] * len(df)
    p260_vals = p260.values if p260 is not None else [None] * len(df)

    print(f"  escalation: 4/5 building rows...", flush=True)
    rows = []
    for i, ts_str in enumerate(df["ts_str"].values):
        asof = ts_str
        ev, pc, bk = esc_raw[i], pctl.values[i], buckets[i]
        rows.append((
            symbol, tf, asof,
            fval(ev), fval(pc),
            fval(p252_vals[i]), fval(p504_vals[i]), fval(p1260_vals[i]),
            fval(p52_vals[i]), fval(p104_vals[i]), fval(p260_vals[i]),
            fval(esc_pctl_era.values[i]),
            None if bk is None else str(bk),
            fval(fwd_abs[i]),
            None if not np.isfinite(fwd_abs[i]) else int(event_flag[i]),
            None if severity[i] is None else str(severity[i]),
        ))

    print(f"  escalation: 5/5 writing {len(rows)} rows...", flush=True)
    conn_write.executemany(
        """
        INSERT OR REPLACE INTO escalation_history_v3(
          symbol,timeframe,asof,
          esc_raw,esc_pctl,
          esc_pctl_252,esc_pctl_504,esc_pctl_1260,
          esc_pctl_52,esc_pctl_104,esc_pctl_260,
          esc_pctl_era,esc_bucket,
          fwd_absret_h,event_flag,event_severity
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
        """,
        rows,
    )
    return len(rows)


def run_state_tf(
    df: pd.DataFrame,
    conn_write: sqlite3.Connection,
    symbol: str,
    tf: str,
) -> tuple[int, int]:
    """Backfill state_history for one TF. Returns (wrote, skipped)."""
    if len(df) < MIN_BARS_STATE:
        return 0, 0

    rows_done = conn_write.execute(
        "SELECT asof FROM state_history WHERE symbol=? AND timeframe=?",
        (symbol, tf),
    ).fetchall()
    asofs_done = {r[0] for r in rows_done}

    idx = df.index
    ts_strs = df["ts_str"].values
    wrote, skipped = 0, 0
    warn_count = 0  # batch same warnings
    for i in range(len(df)):
        asof = ts_strs[i]
        if asof in asofs_done:
            skipped += 1
            continue
        sub = df.iloc[: i + 1].copy()
        try:
            state = compute_market_state_from_df(
                sub, symbol, diagnostics=False, include_escalation_v2=True
            )
        except Exception as e:
            warn_count += 1
            if warn_count <= 3:  # only print first few
                print(f"  [WARN] bar {i} asof={asof}: {e}", flush=True)
            elif warn_count == 4:
                print(f"  [WARN] (further 'not enough history' warnings suppressed)", flush=True)
            continue
        state["timeframe"] = tf
        state_json = json.dumps(state, separators=(",", ":"), ensure_ascii=False)
        conn_write.execute(
            "INSERT OR IGNORE INTO state_history(symbol,timeframe,asof,state_json) VALUES(?,?,?,?)",
            (symbol, tf, asof, state_json),
        )
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
            (symbol, tf, asof, state_json, now_utc_iso(), now_utc_iso()),
        )
        wrote += 1
        if wrote % COMMIT_EVERY == 0:
            conn_write.commit()
        pct = 100 * (i + 1) // len(df) if len(df) else 0
        if (i + 1) % 50 == 0 or i == 0 or i == len(df) - 1:
            print(f"  state progress: {pct}% bar {i+1}/{len(df)} wrote={wrote} skipped={skipped}", flush=True)
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
        help="Bar source: parquet (default) or frozen DB",
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
        frozen = latest_frozen_db_path(symbol)
        if frozen is None or not frozen.exists():
            raise SystemExit(
                f"No frozen DB found for {symbol}. "
                "Run: ingest → validate → freeze (bars only) before compute."
            )
        conn_read = sqlite3.connect(str(frozen), timeout=60)
        print(f"[compute_asset_full] symbol={symbol} input=frozen read={frozen}")

    compute_db = compute_db_path(symbol)
    compute_db.parent.mkdir(parents=True, exist_ok=True)

    conn_write = sqlite3.connect(str(compute_db), timeout=60)
    conn_write.execute("PRAGMA journal_mode=WAL;")
    conn_write.execute("PRAGMA synchronous=NORMAL;")
    ensure_tables(conn_write)

    print(f"  write={compute_db}")
    total_esc = 0
    total_state_wrote = 0
    total_state_skipped = 0

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
        print(f"  bars: {len(df)}", flush=True)
        print(f"  escalation: computing...", flush=True)
        n_esc = run_escalation_tf(df, conn_write, symbol, tf)
        total_esc += n_esc
        print(f"  escalation: {n_esc} rows", flush=True)
        print(f"  state: computing (per-bar, may take a while)...", flush=True)
        w, s = run_state_tf(df, conn_write, symbol, tf)
        total_state_wrote += w
        total_state_skipped += s
        print(f"  state_history: wrote={w} skipped={s}")

    update_latest_state_hazard(conn_write, symbol)
    conn_write.commit()
    if conn_read is not None:
        conn_read.close()
    conn_write.close()

    print(f"\nDONE. escalation={total_esc} | state wrote={total_state_wrote} skipped={total_state_skipped}")


if __name__ == "__main__":
    main()
