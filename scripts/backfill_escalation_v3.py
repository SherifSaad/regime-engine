#!/usr/bin/env python3
"""
Backfill escalation_history_v3 (esc_raw, esc_pctl, esc_bucket) for an asset.

Reads bars from data/assets/<SYMBOL>/live.db. Full data, no bar cap.
Matches SPY architecture (155-bar diff from warmup).

Usage:
  python scripts/backfill_escalation_v3.py --symbol QQQ
  python scripts/backfill_escalation_v3.py --symbol QQQ -t 1day
  python scripts/backfill_escalation_v3.py --symbol QQQ --all
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from regime_engine.escalation_buckets import compute_bucket_from_percentile
from regime_engine.escalation_fast import compute_dsr_iix_ss_arrays_fast
from regime_engine.escalation_v2 import compute_escalation_v2_series, rolling_percentile_transform
from regime_engine.features import compute_ema

TIMEFRAMES = ["15min", "1h", "4h", "1day", "1week"]
PCTL_WINDOW = 504
MIN_BARS = 400

HORIZON_H = 20

# Multi-horizon percentile windows (bar-counts per timeframe)
PCTL_WINDOWS = {
    "1day":  {"p252": 252,  "p504": 504,  "p1260": 1260},
    "1week": {"p52": 52,    "p104": 104,  "p260": 260},
}

# Era boundaries for era-adjusted percentile (asof date)
ERAS = [
    ("pre2010",  None,               "2010-01-01"),
    ("2010_2019","2010-01-01",        "2020-01-01"),
    ("2020plus", "2020-01-01",        None),
]


def asset_dir(symbol: str) -> Path:
    return Path("data/assets") / symbol


def live_db_path(symbol: str) -> Path:
    return asset_dir(symbol) / "live.db"


def latest_frozen_db_path(symbol: str) -> Path | None:
    d = asset_dir(symbol)
    cands = sorted(d.glob("frozen_*.db"))
    if not cands:
        return None
    return cands[-1]


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS escalation_history_v3 (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            asof TEXT NOT NULL,

            esc_raw REAL,

            -- Canonical percentile (SPY parity)
            esc_pctl REAL,

            -- Multi-horizon percentiles (NULL when TF not supported yet)
            esc_pctl_252 REAL,
            esc_pctl_504 REAL,
            esc_pctl_1260 REAL,

            esc_pctl_52 REAL,
            esc_pctl_104 REAL,
            esc_pctl_260 REAL,

            -- Era-adjusted percentile (based on canonical window)
            esc_pctl_era REAL,

            esc_bucket TEXT,

            -- Forward-event labels for validation (H=20)
            fwd_absret_h REAL,
            event_flag INTEGER,
            event_severity TEXT,

            PRIMARY KEY(symbol, timeframe, asof)
        );
        """
    )

    # --- lightweight in-place migration: add missing columns if table already exists ---
    existing = {row[1] for row in conn.execute("PRAGMA table_info(escalation_history_v3);").fetchall()}

    add_cols = [
        ("esc_pctl_252", "REAL"),
        ("esc_pctl_504", "REAL"),
        ("esc_pctl_1260", "REAL"),
        ("esc_pctl_52", "REAL"),
        ("esc_pctl_104", "REAL"),
        ("esc_pctl_260", "REAL"),
        ("esc_pctl_era", "REAL"),
        ("fwd_absret_h", "REAL"),
        ("event_flag", "INTEGER"),
        ("event_severity", "TEXT"),
    ]

    for col, coltype in add_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE escalation_history_v3 ADD COLUMN {col} {coltype};")

    conn.commit()


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
    df["ts_str"] = df["ts"].astype(str)   # raw DB string
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df["adj_close"] = df["close"]
    for c in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"])
    return df


def backfill_one_tf(conn: sqlite3.Connection, symbol: str, tf: str) -> int:
    df = load_bars(conn, symbol, tf)
    if len(df) < MIN_BARS:
        return 0
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
    pctl = rolling_percentile_transform(esc_series, window=PCTL_WINDOW)

    # --- forward stress metric & event labels (H=20) ---
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

    # event thresholding based on trailing global quantiles of fwd_abs (no lookahead)
    fwd_series = pd.Series(fwd_abs, index=df.index)

    # We define severity by trailing percentile of fwd_abs itself (no leakage)
    fwd_pctl = rolling_percentile_transform(fwd_series, window=PCTL_WINDOW)

    event_flag = np.zeros(n, dtype=int)
    severity = np.array([None] * n, dtype=object)

    for i, p in enumerate(fwd_pctl.values):
        if p is None or (isinstance(p, float) and np.isnan(p)):
            event_flag[i] = 0
            severity[i] = None
            continue

        # "event" starts at 95th percentile of forward-move magnitude
        if p >= 0.95:
            event_flag[i] = 1
            if p >= 0.99:
                severity[i] = "CRISIS"
            elif p >= 0.975:
                severity[i] = "SEVERE"
            else:
                severity[i] = "MODERATE"
        else:
            event_flag[i] = 0
            if p >= 0.90:
                severity[i] = "MILD"
            else:
                severity[i] = None

    # --- multi-horizon percentiles (UI toggle support; stored for speed) ---
    p252 = p504 = p1260 = None
    p52 = p104 = p260 = None

    if tf in PCTL_WINDOWS:
        w = PCTL_WINDOWS[tf]
        if tf == "1day":
            p252 = rolling_percentile_transform(esc_series, window=w["p252"])
            p504 = rolling_percentile_transform(esc_series, window=w["p504"])
            p1260 = rolling_percentile_transform(esc_series, window=w["p1260"])
        elif tf == "1week":
            p52  = rolling_percentile_transform(esc_series, window=w["p52"])
            p104 = rolling_percentile_transform(esc_series, window=w["p104"])
            p260 = rolling_percentile_transform(esc_series, window=w["p260"])

    # --- era-adjusted percentile (canonical window, computed separately within eras) ---
    esc_pctl_era = pd.Series(np.full(len(df), np.nan, dtype=float), index=df.index)

    for _, start_s, end_s in ERAS:
        start = pd.to_datetime(start_s) if start_s else None
        end   = pd.to_datetime(end_s) if end_s else None

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

    # Helper to convert NaN -> None
    def fval(x):
        if x is None:
            return None
        if isinstance(x, float) and np.isnan(x):
            return None
        return float(x)

    rows = []

    # pick the right per-row percentile sources (or None)
    p252_vals  = p252.values  if p252  is not None else [None] * len(df)
    p504_vals  = p504.values  if p504  is not None else [None] * len(df)
    p1260_vals = p1260.values if p1260 is not None else [None] * len(df)

    p52_vals   = p52.values   if p52   is not None else [None] * len(df)
    p104_vals  = p104.values  if p104  is not None else [None] * len(df)
    p260_vals  = p260.values  if p260  is not None else [None] * len(df)

    for i, ts_str in enumerate(df["ts_str"].values):
        asof = ts_str

        ev = esc_raw[i]
        pc = pctl.values[i]
        bk = buckets[i]

        esc_raw_val   = fval(ev)
        esc_pctl_val  = fval(pc)

        esc_pctl_252  = fval(p252_vals[i])
        esc_pctl_504  = fval(p504_vals[i])
        esc_pctl_1260 = fval(p1260_vals[i])

        esc_pctl_52   = fval(p52_vals[i])
        esc_pctl_104  = fval(p104_vals[i])
        esc_pctl_260  = fval(p260_vals[i])

        esc_pctl_era_val = fval(esc_pctl_era.values[i])

        esc_bucket_val = None if bk is None else str(bk)

        fwd_abs_val = fval(fwd_abs[i])
        ev_flag_val = None if (not np.isfinite(fwd_abs[i])) else int(event_flag[i])
        sev_val = None if severity[i] is None else str(severity[i])

        rows.append((
            symbol, tf, asof,
            esc_raw_val, esc_pctl_val,
            esc_pctl_252, esc_pctl_504, esc_pctl_1260,
            esc_pctl_52, esc_pctl_104, esc_pctl_260,
            esc_pctl_era_val,
            esc_bucket_val,
            fwd_abs_val, ev_flag_val, sev_val
        ))

    conn.executemany(
        """
        INSERT OR REPLACE INTO escalation_history_v3(
          symbol,timeframe,asof,
          esc_raw,esc_pctl,
          esc_pctl_252,esc_pctl_504,esc_pctl_1260,
          esc_pctl_52,esc_pctl_104,esc_pctl_260,
          esc_pctl_era,
          esc_bucket,
          fwd_absret_h,event_flag,event_severity
        )
        VALUES(?,?,?,?,?,
               ?,?,?,
               ?,?,?,
               ?,
               ?,
               ?,?,?);
        """,
        rows,
    )
    return len(rows)


def ensure_latest_state(conn: sqlite3.Connection) -> None:
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
            PRIMARY KEY(symbol, timeframe)
        );
        """
    )
    existing = {row[1] for row in conn.execute("PRAGMA table_info(latest_state);").fetchall()}
    add_cols = [
        ("state_json", "TEXT"),
        ("hazard_score", "REAL"),
        ("cross_tf_consensus", "REAL"),
        ("updated_at", "TEXT"),
        ("updated_utc", "TEXT"),
    ]
    for col, coltype in add_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE latest_state ADD COLUMN {col} {coltype};")
    conn.commit()


def hazard_score_from_pctl(p: float | None) -> float | None:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return None
    # simple, deterministic 0–100 scaling
    return float(max(0.0, min(100.0, 100.0 * p)))


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill escalation_history_v3")
    ap.add_argument("--symbol", required=True, help="e.g. QQQ, SPY")
    ap.add_argument("-t", "--timeframe", help="Single TF. Default: all")
    ap.add_argument("--all", action="store_true", help="All TFs (default)")
    ap.add_argument(
        "--use-frozen",
        action="store_true",
        help="Copy latest frozen DB to live.db before compute",
    )
    args = ap.parse_args()
    symbol = args.symbol.strip().upper()
    tfs = [args.timeframe] if args.timeframe else TIMEFRAMES

    if args.use_frozen:
        frozen = latest_frozen_db_path(symbol)
        if frozen is None:
            print(f"[use-frozen] SKIP {symbol}: no frozen DB in {asset_dir(symbol)}")
            return
        db = live_db_path(symbol)
        db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(frozen, db)
        print(f"[use-frozen] copied {frozen.name} -> live.db")

    db = live_db_path(symbol)
    if not db.exists():
        raise SystemExit(f"DB not found: {db}. Run backfill_asset_full.py --symbol {symbol} first.")

    conn = sqlite3.connect(str(db), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    ensure_table(conn)

    print(f"[backfill_escalation_v3] symbol={symbol} DB={db}")
    total = 0
    for tf in tfs:
        print(f"  {tf}...", end=" ", flush=True)
        n = backfill_one_tf(conn, symbol, tf)
        total += n
        print(n)

    ensure_latest_state(conn)

    # Pull latest canonical pctl per TF (esc_pctl = 504-window canonical)
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
            """
            SELECT esc_pctl
            FROM escalation_history_v3
            WHERE symbol=? AND timeframe=? AND asof=?
            """,
            (symbol, tf, asof),
        ).fetchone()
        tf_to_pctl[tf] = None if row is None else row[0]

    # Cross-TF consensus = average canonical percentile across TFs that have a value
    vals = [v for v in tf_to_pctl.values() if v is not None]
    consensus = float(np.mean(vals)) if vals else None

    import datetime as _dt
    now_utc = _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Write one row per TF into latest_state
    rows_latest = []
    for tf, asof in tf_to_asof.items():
        p = tf_to_pctl.get(tf)
        hz = hazard_score_from_pctl(p)
        rows_latest.append((symbol, tf, asof, "{}", hz, consensus, now_utc, now_utc))

    conn.executemany(
        """
        INSERT OR REPLACE INTO latest_state(
            symbol,timeframe,asof,state_json,hazard_score,cross_tf_consensus,updated_at,updated_utc
        )
        VALUES(?,?,?,?,?,?,?,?);
        """,
        rows_latest,
    )

    conn.commit()
    conn.close()
    print(f"DONE. Total rows: {total}")


if __name__ == "__main__":
    main()
