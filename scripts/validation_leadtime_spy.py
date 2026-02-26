#!/usr/bin/env python3
"""
Validation Step 2 (FAST):
Measure whether escalation warned BEFORE each ATR event using DB state_history (no recompute).

Inputs:
- validation_outputs/spy_events.csv  (from Step 1)
- SQLite: state_history for (SPY, 1day) contains state_json with escalation fields

Output:
- validation_outputs/spy_event_leadtime.csv
- prints summary stats
"""

import os
import json
import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np

# Per-asset compute.db (canonical state source)
from core.storage import get_compute_db_path
DEFAULT_DB = get_compute_db_path("SPY")
DB_PATH = os.getenv("VALIDATION_COMPUTE_DB") or os.getenv("REGIME_DB_PATH") or str(DEFAULT_DB)

EVENTS_CSV = "validation_outputs/spy_events.csv"

SYMBOL = "SPY"
TIMEFRAME = "1day"

LOOKBACK_DAYS = 90
WARNING_BUCKET = "HIGH"


def load_events() -> pd.DataFrame:
    ev = pd.read_csv(EVENTS_CSV, parse_dates=["ts"])
    ev = ev.sort_values("ts").reset_index(drop=True)
    # event date key used in state_history is ISO date for 1day
    ev["event_date"] = ev["ts"].dt.date.astype(str)
    return ev


def load_state_history_daily(symbol: str, tf: str) -> pd.DataFrame:
    """
    Load all daily states for symbol from state_history and extract escalation fields.
    """
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT asof, state_json
        FROM state_history
        WHERE symbol=? AND timeframe=?
        ORDER BY asof ASC
        """,
        (symbol, tf),
    ).fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=["asof", "escalation_v2", "escalation_bucket"])

    recs = []
    for asof, state_json in rows:
        try:
            st = json.loads(state_json)
        except Exception:
            continue
        recs.append({
            "asof": asof,
            "escalation_v2": st.get("escalation_v2", None),
            "escalation_bucket": st.get("escalation_bucket", None),
        })

    df = pd.DataFrame(recs)
    df["asof_dt"] = pd.to_datetime(df["asof"])
    return df


def main():
    events = load_events()
    states = load_state_history_daily(SYMBOL, TIMEFRAME)

    if states.empty:
        raise RuntimeError(
            "No rows found in state_history for SPY 1day. "
            "Run pipeline: backfill → migrate → validate → compute (Parquet). "
            "Or: python scripts/compute_asset_full.py --symbol SPY -t 1day (requires Parquet bars)"
        )

    results = []

    # pre-index for fast slicing
    states = states.sort_values("asof_dt").reset_index(drop=True)

    for _, ev in events.iterrows():
        event_date = ev["event_date"]
        event_dt = pd.to_datetime(event_date)

        start_dt = event_dt - pd.Timedelta(days=LOOKBACK_DAYS)

        # window: [start_dt, event_dt) i.e., strictly before event day
        win = states[(states["asof_dt"] >= start_dt) & (states["asof_dt"] < event_dt)].copy()

        # warning hits
        warn = win[win["escalation_bucket"] == WARNING_BUCKET].copy()
        first_warn = warn["asof"].iloc[0] if len(warn) else None

        lead_days = None
        if first_warn:
            lead_days = (event_dt - pd.to_datetime(first_warn)).days

        # max escalation_v2 (ignore None)
        max_esc = None
        max_esc_asof = None
        win_esc = win.dropna(subset=["escalation_v2"])
        if len(win_esc):
            idx = win_esc["escalation_v2"].astype(float).idxmax()
            max_esc = float(win_esc.loc[idx, "escalation_v2"])
            max_esc_asof = str(win_esc.loc[idx, "asof"])

        results.append({
            "event_date": event_date,
            "fwd_move": float(ev["fwd_move"]),
            "atr": float(ev["atr"]),
            "threshold": float(ev["atr"] * 10),
            "first_warning_date": first_warn,
            "lead_days": lead_days,
            "max_escalation_v2": max_esc,
            "max_escalation_date": max_esc_asof,
            "warning_count_in_window": int(len(warn)),
        })

    out = pd.DataFrame(results)
    os.makedirs("validation_outputs", exist_ok=True)
    out_path = "validation_outputs/spy_event_leadtime.csv"
    out.to_csv(out_path, index=False)

    total = len(out)
    warned = int(out["first_warning_date"].notna().sum())
    hit_rate = (warned / total) if total else 0.0
    avg_lead = out["lead_days"].dropna().mean()
    avg_lead_val = float(avg_lead) if not np.isnan(avg_lead) else None

    print("Events analyzed:", total)
    print(f"Events with warning (bucket={WARNING_BUCKET}):", warned)
    print("Warning hit rate:", hit_rate)
    print("Avg lead days (when warned):", avg_lead_val)
    print("Saved:", out_path)


if __name__ == "__main__":
    main()
