#!/usr/bin/env python3
"""
STEP 3 (Reframed) — Forward Distribution Widening / Instability Test
====================================================================

Goal:
Test whether HIGH escalation (esc_pctl >= 0.99) identifies regimes where
forward return distributions widen (bigger moves become more likely) in EITHER direction.

We report, per timeframe, for each horizon H (in bars):
1) P(|fwd_H| >= q95_abs) for HIGH vs LOW esc
2) Mean(|fwd_H|) for HIGH vs LOW esc
3) Std(fwd_H) for HIGH vs LOW esc
4) Max excursion within H bars:
   - MDD_H: min(close_{t+k}/close_t - 1), k=1..H
   - MUR_H: max(close_{t+k}/close_t - 1), k=1..H
   - EXCURSION_H = max(|MDD_H|, |MUR_H|)
   Compare mean(EXCURSION_H) HIGH vs LOW
5) Optional directional skew context:
   P(fwd_H >= +q95_pos) and P(fwd_H <= q05_neg) for HIGH vs LOW

We do NOT claim crash timing. We test "instability / animality" — distribution widening.

Data source:
- DB: regime_cache_SPY_escalation_frozen_2026-02-19.db
- bars table: symbol,timeframe,ts,close
- escalation_history_v3 table: symbol,timeframe,asof,esc_pctl

Outputs:
- validation_outputs/step3_widening_summary.csv
- validation_outputs/step3_widening_detail.csv
"""

from __future__ import annotations

import os
import sqlite3
import numpy as np
import pandas as pd

PROJECT_DIR = "/Users/sherifsaad/Documents/regime-engine"
DB_PATH = os.path.join(PROJECT_DIR, "data", "regime_cache_SPY_escalation_frozen_2026-02-19.db")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "validation_outputs")

SYMBOL = "SPY"
ESC_TABLE = "escalation_history_v3"
BARS_TABLE = "bars"

ESC_HIGH = 0.99
ESC_LOW = 0.50

# Horizons (bars). We choose short-to-medium horizons to capture "instability" across TFs.
# You can expand later, but keep this tight for institutional clarity.
HORIZONS = [5, 20, 60]

ABS_Q = 0.95  # threshold for "large absolute move" based on unconditional abs(fwd_H)

def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_joined(db_path: str) -> pd.DataFrame:
    con = sqlite3.connect(db_path)

    esc = pd.read_sql_query(
        f"SELECT symbol, timeframe, asof, esc_pctl FROM {ESC_TABLE} WHERE symbol = ?",
        con, params=(SYMBOL,)
    )
    bars = pd.read_sql_query(
        f"SELECT symbol, timeframe, ts, close FROM {BARS_TABLE} WHERE symbol = ?",
        con, params=(SYMBOL,)
    )
    con.close()

    esc["asof"] = pd.to_datetime(esc["asof"], errors="coerce")
    bars["ts"] = pd.to_datetime(bars["ts"], errors="coerce")

    esc = esc.dropna(subset=["asof", "timeframe", "esc_pctl"]).copy()
    bars = bars.dropna(subset=["ts", "timeframe", "close"]).copy()

    esc["esc_pctl"] = pd.to_numeric(esc["esc_pctl"], errors="coerce")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")

    esc = esc.dropna(subset=["esc_pctl"])
    bars = bars.dropna(subset=["close"])

    bars = bars.sort_values(["timeframe", "ts"]).reset_index(drop=True)

    df = bars.merge(
        esc,
        left_on=["symbol", "timeframe", "ts"],
        right_on=["symbol", "timeframe", "asof"],
        how="left",
    ).drop(columns=["asof"])

    df = df.dropna(subset=["esc_pctl"]).copy()
    return df

def compute_forward_and_excursions(df_tf: pd.DataFrame, H: int) -> pd.DataFrame:
    """
    Adds columns for a given horizon H:
    - fwd_H : close_{t+H}/close_t - 1
    - abs_fwd_H
    - mdd_H : min future return within 1..H
    - mur_H : max future return within 1..H
    - excursion_H : max(|mdd_H|, |mur_H|)
    """
    close = df_tf["close"].to_numpy(dtype=float)
    n = len(close)

    fwd = np.full(n, np.nan)
    if n > H:
        fwd[:-H] = close[H:] / close[:-H] - 1.0

    # excursion using rolling window future max/min of ratio
    # For each t, look at close[t+1:t+H+1] relative to close[t]
    mdd = np.full(n, np.nan)
    mur = np.full(n, np.nan)

    # O(n*H) is fine for this dataset size, but we keep it reasonably small with H<=60.
    for i in range(n - H):
        base = close[i]
        window = close[i+1:i+H+1] / base - 1.0
        mdd[i] = np.min(window)
        mur[i] = np.max(window)

    excursion = np.maximum(np.abs(mdd), np.abs(mur))

    out = df_tf.copy()
    out[f"fwd_{H}"] = fwd
    out[f"abs_fwd_{H}"] = np.abs(fwd)
    out[f"mdd_{H}"] = mdd
    out[f"mur_{H}"] = mur
    out[f"excursion_{H}"] = excursion

    return out

def summarize(df_tf: pd.DataFrame, H: int) -> pd.DataFrame:
    col_fwd = f"fwd_{H}"
    col_abs = f"abs_fwd_{H}"
    col_exc = f"excursion_{H}"

    work = df_tf.dropna(subset=[col_fwd, col_abs, col_exc]).copy()
    if work.empty:
        return pd.DataFrame()

    # unconditional thresholds per timeframe & horizon
    q_abs = float(work[col_abs].quantile(ABS_Q))
    q_pos = float(work[col_fwd].quantile(0.95))
    q_neg = float(work[col_fwd].quantile(0.05))

    work["is_high"] = work["esc_pctl"] >= ESC_HIGH
    work["is_low"]  = work["esc_pctl"] <= ESC_LOW

    hi = work[work["is_high"]]
    lo = work[work["is_low"]]

    def rate(s: pd.Series) -> float:
        return float(s.mean()) if len(s) else np.nan

    rows = []
    for label, grp in [("HIGH", hi), ("LOW", lo)]:
        rows.append({
            "group": label,
            "n": int(len(grp)),
            "p_abs_ge_q95": rate(grp[col_abs] >= q_abs),
            "mean_abs_fwd": float(grp[col_abs].mean()) if len(grp) else np.nan,
            "std_fwd": float(grp[col_fwd].std(ddof=0)) if len(grp) else np.nan,
            "mean_excursion": float(grp[col_exc].mean()) if len(grp) else np.nan,
            "p_fwd_ge_q95_pos": rate(grp[col_fwd] >= q_pos),
            "p_fwd_le_q05_neg": rate(grp[col_fwd] <= q_neg),
            "q95_abs_threshold": q_abs,
            "q95_pos_threshold": q_pos,
            "q05_neg_threshold": q_neg,
        })

    out = pd.DataFrame(rows)

    # add diffs (HIGH - LOW)
    if len(out) == 2:
        hi_row = out.iloc[0]
        lo_row = out.iloc[1]
        diff = {
            "group": "DIFF_HIGH_MINUS_LOW",
            "n": np.nan,
            "p_abs_ge_q95": hi_row["p_abs_ge_q95"] - lo_row["p_abs_ge_q95"],
            "mean_abs_fwd": hi_row["mean_abs_fwd"] - lo_row["mean_abs_fwd"],
            "std_fwd": hi_row["std_fwd"] - lo_row["std_fwd"],
            "mean_excursion": hi_row["mean_excursion"] - lo_row["mean_excursion"],
            "p_fwd_ge_q95_pos": hi_row["p_fwd_ge_q95_pos"] - lo_row["p_fwd_ge_q95_pos"],
            "p_fwd_le_q05_neg": hi_row["p_fwd_le_q05_neg"] - lo_row["p_fwd_le_q05_neg"],
            "q95_abs_threshold": hi_row["q95_abs_threshold"],
            "q95_pos_threshold": hi_row["q95_pos_threshold"],
            "q05_neg_threshold": hi_row["q05_neg_threshold"],
        }
        out = pd.concat([out, pd.DataFrame([diff])], ignore_index=True)

    return out

def main():
    ensure_dirs()
    df = load_joined(DB_PATH)

    all_detail = []
    all_summary = []

    for tf, df_tf in df.groupby("timeframe"):
        df_tf = df_tf.sort_values("ts").reset_index(drop=True)

        for H in HORIZONS:
            df_h = compute_forward_and_excursions(df_tf, H)
            tab = summarize(df_h, H)
            if tab.empty:
                continue

            tab.insert(0, "timeframe", tf)
            tab.insert(1, "horizon_bars", H)

            all_detail.append(tab)

            # one-line summary (diff row only)
            diff = tab[tab["group"] == "DIFF_HIGH_MINUS_LOW"].copy()
            if not diff.empty:
                all_summary.append(diff)

    detail = pd.concat(all_detail, ignore_index=True) if all_detail else pd.DataFrame()
    summary = pd.concat(all_summary, ignore_index=True) if all_summary else pd.DataFrame()

    out_detail = os.path.join(OUTPUT_DIR, "step3_widening_detail.csv")
    out_summary = os.path.join(OUTPUT_DIR, "step3_widening_summary.csv")

    detail.to_csv(out_detail, index=False)
    summary.to_csv(out_summary, index=False)

    print("=== STEP 3 — Distribution Widening / Instability ===")
    print("DB:", DB_PATH)
    print("HIGH esc_pctl >= 0.99 | LOW esc_pctl <= 0.50")
    print("Horizons:", HORIZONS, "bars | abs q:", ABS_Q)
    print("Outputs:")
    print(" ", out_detail)
    print(" ", out_summary)
    print()

    with pd.option_context("display.width", 200, "display.max_columns", 200):
        print("Summary (DIFF = HIGH - LOW):")
        print(summary)

if __name__ == "__main__":
    main()

