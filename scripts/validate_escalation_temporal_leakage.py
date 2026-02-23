#!/usr/bin/env python3
"""
STEP 2 — Temporal Leakage / Contemporaneous Shock Check
======================================================

Question:
When esc_pctl is extreme (>= 0.99), is the signal just reacting to same-day / recent negative returns?

For each timeframe:
- Condition on esc_pctl >= threshold (default 0.99)
- Compute mean / median returns for:
    t (same bar)
    t-1, t-2, t-3 (prior bars)
    t+1..t+20 (optional forward context, but NOT the focus of Step 2)
- Also report how often returns are negative at each lag.

Outputs:
- validation_outputs/step2_temporal_leakage_by_timeframe.csv
- validation_outputs/step2_temporal_leakage_summary.csv
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# -----------------------------
# Config
# -----------------------------
PROJECT_DIR = "/Users/sherifsaad/Documents/regime-engine"
DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "validation_outputs")

# If your file name differs, change it here.
ESC_HISTORY_FILE = os.path.join(DATA_DIR, "escalation_history_v3_with_ret.csv")

# Timeframe column name assumptions (robustly handled):
# We look for one of: ["timeframe", "tf", "Timeframe", "TF"]
TF_COL_CANDIDATES = ["timeframe", "tf", "Timeframe", "TF"]

# Date/time column name assumptions:
DT_COL_CANDIDATES = ["asof", "dt", "datetime", "timestamp", "time", "Date", "date"]

# Escalation percentile column:
ESC_PCTL_COL_CANDIDATES = ["esc_pctl", "esc_percentile", "esc_pctl_roll"]

# Return column:
RET_COL_CANDIDATES = ["ret", "return", "logret", "r", "close_ret", "adj_ret"]

# Threshold for "extreme" escalation percentile
PCTL_THRESHOLD = 0.99

# How many prior bars to inspect
N_PRIOR = 3

# (Optional) forward bars to summarize for context; keep small & simple
N_FWD = 5


@dataclass
class ColMap:
    tf: str
    dt: str
    esc_pctl: str
    ret: str


def _pick_col(df: pd.DataFrame, candidates: List[str], required: bool = True) -> Optional[str]:
    cols = list(df.columns)
    for c in candidates:
        if c in cols:
            return c
    if required:
        raise ValueError(f"Missing required column. Tried: {candidates}. Available: {cols[:50]}")
    return None


def _ensure_dirs() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_data(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Could not find: {path}\n"
            f"Expected escalation history CSV in: {DATA_DIR}\n"
            f"If your file has a different name, edit ESC_HISTORY_FILE in this script."
        )

    df = pd.read_csv(path)

    # Column mapping
    colmap = ColMap(
        tf=_pick_col(df, TF_COL_CANDIDATES),
        dt=_pick_col(df, DT_COL_CANDIDATES),
        esc_pctl=_pick_col(df, ESC_PCTL_COL_CANDIDATES),
        ret=_pick_col(df, RET_COL_CANDIDATES),
    )

    # Parse dt
    df[colmap.dt] = pd.to_datetime(df[colmap.dt], errors="coerce", utc=False)
    df = df.dropna(subset=[colmap.dt, colmap.tf, colmap.esc_pctl, colmap.ret]).copy()

    # Coerce numeric
    df[colmap.esc_pctl] = pd.to_numeric(df[colmap.esc_pctl], errors="coerce")
    df[colmap.ret] = pd.to_numeric(df[colmap.ret], errors="coerce")
    df = df.dropna(subset=[colmap.esc_pctl, colmap.ret]).copy()

    # Sort for stable shifting
    df = df.sort_values([colmap.tf, colmap.dt]).reset_index(drop=True)

    # Attach mapping for downstream
    df.attrs["colmap"] = colmap
    return df


def compute_temporal_leakage_table(df: pd.DataFrame, pctl_threshold: float) -> Tuple[pd.DataFrame, pd.DataFrame]:
    colmap: ColMap = df.attrs["colmap"]

    # Create lag/lead returns within each timeframe
    g = df.groupby(colmap.tf, group_keys=False)

    df_work = df[[colmap.tf, colmap.dt, colmap.esc_pctl, colmap.ret]].copy()

    # prior lags
    df_work["ret_t"] = df_work[colmap.ret]
    for k in range(1, N_PRIOR + 1):
        df_work[f"ret_t_minus_{k}"] = g[colmap.ret].shift(k)

    # optional forward context
    for k in range(1, N_FWD + 1):
        df_work[f"ret_t_plus_{k}"] = g[colmap.ret].shift(-k)

    # Condition set
    cond = df_work[colmap.esc_pctl] >= pctl_threshold
    df_hi = df_work.loc[cond].copy()

    # If nothing triggered, return empty outputs but with structure
    if df_hi.empty:
        by_tf = pd.DataFrame(
            columns=[
                "timeframe",
                "n_total",
                "n_hi",
                "hi_rate",
                "mean_ret_t",
                "median_ret_t",
                "pct_neg_ret_t",
            ]
        )
        summary = pd.DataFrame([{
            "pctl_threshold": pctl_threshold,
            "note": "No rows met threshold."
        }])
        return by_tf, summary

    rows = []
    for tf, sub in df_hi.groupby(colmap.tf):
        n_total = int((df_work[colmap.tf] == tf).sum())
        n_hi = int(len(sub))
        hi_rate = n_hi / n_total if n_total else np.nan

        def _stats(series: pd.Series) -> Dict[str, float]:
            s = pd.to_numeric(series, errors="coerce").dropna()
            if s.empty:
                return {"mean": np.nan, "median": np.nan, "pct_neg": np.nan}
            return {
                "mean": float(s.mean()),
                "median": float(s.median()),
                "pct_neg": float((s < 0).mean()),
            }

        out = {
            "timeframe": tf,
            "n_total": n_total,
            "n_hi": n_hi,
            "hi_rate": hi_rate,
        }

        # Stats for t, t-1..t-3, plus a small forward context
        for col in ["ret_t"] + [f"ret_t_minus_{k}" for k in range(1, N_PRIOR + 1)] + [f"ret_t_plus_{k}" for k in range(1, N_FWD + 1)]:
            st = _stats(sub[col])
            out[f"mean_{col}"] = st["mean"]
            out[f"median_{col}"] = st["median"]
            out[f"pct_neg_{col}"] = st["pct_neg"]

        rows.append(out)

    by_tf = pd.DataFrame(rows).sort_values("timeframe").reset_index(drop=True)

    # Overall summary across all timeframes (pooled)
    pooled = df_hi.copy()
    pooled_row = {
        "pctl_threshold": pctl_threshold,
        "n_hi_total": int(len(pooled)),
        "mean_ret_t": float(pd.to_numeric(pooled["ret_t"], errors="coerce").mean()),
        "median_ret_t": float(pd.to_numeric(pooled["ret_t"], errors="coerce").median()),
        "pct_neg_ret_t": float((pd.to_numeric(pooled["ret_t"], errors="coerce") < 0).mean()),
    }
    for k in range(1, N_PRIOR + 1):
        s = pd.to_numeric(pooled[f"ret_t_minus_{k}"], errors="coerce")
        pooled_row[f"mean_ret_t_minus_{k}"] = float(s.mean())
        pooled_row[f"median_ret_t_minus_{k}"] = float(s.median())
        pooled_row[f"pct_neg_ret_t_minus_{k}"] = float((s < 0).mean())

    summary = pd.DataFrame([pooled_row])

    return by_tf, summary


def main() -> int:
    _ensure_dirs()

    df = load_data(ESC_HISTORY_FILE)
    by_tf, summary = compute_temporal_leakage_table(df, PCTL_THRESHOLD)

    out1 = os.path.join(OUTPUT_DIR, "step2_temporal_leakage_by_timeframe.csv")
    out2 = os.path.join(OUTPUT_DIR, "step2_temporal_leakage_summary.csv")

    by_tf.to_csv(out1, index=False)
    summary.to_csv(out2, index=False)

    # Print tight console view (no fluff)
    print("=== STEP 2 — Temporal Leakage Check ===")
    print(f"Input: {ESC_HISTORY_FILE}")
    print(f"Threshold: esc_pctl >= {PCTL_THRESHOLD}")
    print(f"Outputs:\n  {out1}\n  {out2}\n")

    with pd.option_context("display.width", 200, "display.max_columns", 200):
        print("By timeframe:")
        print(by_tf)

        print("\nPooled summary:")
        print(summary)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise

