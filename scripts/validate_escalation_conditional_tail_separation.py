#!/usr/bin/env python3
"""
STEP 3 — Conditional Tail Separation (Incremental Value Test)
============================================================

Goal:
Show whether esc_pctl adds incremental tail-risk information AFTER controlling for
contemporaneous / recent returns.

We test two conditioning schemes (per timeframe):
A) Condition on same-bar return deciles (ret_t deciles)
B) Condition on recent-return composite deciles (ret_t + ret_{t-1}+ret_{t-2}+ret_{t-3})

Within each decile-bin:
- Compare tail rate for HIGH escalation vs LOW escalation
    HIGH: esc_pctl >= 0.99
    LOW:  esc_pctl <= 0.50  (broad low-stress baseline)

Tail event definition:
- Forward 20 bars return (within timeframe) <= -10%
    fwd_20 = close_{t+20}/close_t - 1

Outputs:
- validation_outputs/step3_conditional_tail_by_ret_decile.csv
- validation_outputs/step3_conditional_tail_by_recent_decile.csv
- validation_outputs/step3_conditional_tail_summary.csv
"""

from __future__ import annotations

import os
import sys
import sqlite3
import numpy as np
import pandas as pd


PROJECT_DIR = "/Users/sherifsaad/Documents/regime-engine"
DB_PATH = os.path.join(PROJECT_DIR, "data", "regime_cache_SPY_escalation_frozen_2026-02-19.db")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "validation_outputs")

SYMBOL = "SPY"

ESC_TABLE = "escalation_history_v3"   # has: symbol,timeframe,asof,esc_pctl,...
BARS_TABLE = "bars"                   # has: symbol,timeframe,ts,close,...

# Step 3 parameters
ESC_HIGH = 0.99
ESC_LOW  = 0.50

HORIZON_BARS = 20
TAIL_CUTOFF = -0.10

N_BINS = 10  # deciles


def _ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_from_db(db_path: str) -> pd.DataFrame:
    con = sqlite3.connect(db_path)

    esc = pd.read_sql_query(
        f"""
        SELECT symbol, timeframe, asof, esc_pctl
        FROM {ESC_TABLE}
        WHERE symbol = ?
        """,
        con,
        params=(SYMBOL,),
    )

    bars = pd.read_sql_query(
        f"""
        SELECT symbol, timeframe, ts, close
        FROM {BARS_TABLE}
        WHERE symbol = ?
        """,
        con,
        params=(SYMBOL,),
    )

    con.close()

    esc["asof"] = pd.to_datetime(esc["asof"], errors="coerce")
    bars["ts"] = pd.to_datetime(bars["ts"], errors="coerce")
    esc = esc.dropna(subset=["asof", "timeframe", "esc_pctl"])
    bars = bars.dropna(subset=["ts", "timeframe", "close"])

    esc["esc_pctl"] = pd.to_numeric(esc["esc_pctl"], errors="coerce")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    esc = esc.dropna(subset=["esc_pctl"])
    bars = bars.dropna(subset=["close"])

    bars = bars.sort_values(["timeframe", "ts"]).reset_index(drop=True)

    # returns + forward return
    g = bars.groupby(["timeframe"], group_keys=False)
    bars["ret_t"] = g["close"].pct_change()
    for k in [1, 2, 3]:
        bars[f"ret_t_minus_{k}"] = g["ret_t"].shift(k)

    bars["fwd_20"] = g["close"].shift(-HORIZON_BARS) / bars["close"] - 1.0
    bars["tail_20"] = bars["fwd_20"] <= TAIL_CUTOFF

    # join esc_pctl onto bars (asof ↔ ts)
    df = bars.merge(
        esc,
        left_on=["symbol", "timeframe", "ts"],
        right_on=["symbol", "timeframe", "asof"],
        how="left",
    ).drop(columns=["asof"])

    # we only keep rows where we have esc_pctl and returns exist
    df = df.dropna(subset=["esc_pctl", "ret_t", "ret_t_minus_1", "ret_t_minus_2", "ret_t_minus_3", "fwd_20"]).copy()

    return df


def _bin_by_quantiles(s: pd.Series, n_bins: int) -> pd.Series:
    # robust quantile binning; duplicates allowed -> fewer bins if needed
    try:
        return pd.qcut(s, q=n_bins, duplicates="drop")
    except Exception:
        # fallback: rank-based bins
        r = s.rank(method="average")
        return pd.qcut(r, q=n_bins, duplicates="drop")


def conditional_tail_table(df: pd.DataFrame, bin_col: str, label: str) -> pd.DataFrame:
    # define groups
    df = df.copy()
    df["is_high"] = df["esc_pctl"] >= ESC_HIGH
    df["is_low"] = df["esc_pctl"] <= ESC_LOW

    df["bin"] = _bin_by_quantiles(df[bin_col], N_BINS)

    rows = []
    for b, sub in df.groupby("bin"):
        hi = sub[sub["is_high"]]
        lo = sub[sub["is_low"]]

        # tail rates
        hi_n = len(hi)
        lo_n = len(lo)
        hi_tail = float(hi["tail_20"].mean()) if hi_n else np.nan
        lo_tail = float(lo["tail_20"].mean()) if lo_n else np.nan

        rows.append({
            "scheme": label,
            "bin": str(b),
            "bin_col": bin_col,
            "bin_n_total": int(len(sub)),
            "hi_n": int(hi_n),
            "lo_n": int(lo_n),
            "hi_tail_rate": hi_tail,
            "lo_tail_rate": lo_tail,
            "tail_rate_diff_hi_minus_lo": (hi_tail - lo_tail) if (hi_n and lo_n) else np.nan,
            "bin_mean_ret_t": float(sub["ret_t"].mean()),
        })

    out = pd.DataFrame(rows)

    # adjusted (bin-weighted) difference using bins where both groups exist
    valid = out.dropna(subset=["tail_rate_diff_hi_minus_lo", "hi_n", "lo_n"])
    if len(valid):
        # weight by min(hi_n, lo_n) to avoid one-sided bins dominating
        w = np.minimum(valid["hi_n"].values, valid["lo_n"].values).astype(float)
        adj = float(np.average(valid["tail_rate_diff_hi_minus_lo"].values, weights=w)) if w.sum() > 0 else np.nan
    else:
        adj = np.nan

    out.attrs["adjusted_diff"] = adj
    return out


def main() -> int:
    _ensure_dirs()

    df = load_from_db(DB_PATH)

    # composite recent return
    df["ret_recent_4"] = df["ret_t"] + df["ret_t_minus_1"] + df["ret_t_minus_2"] + df["ret_t_minus_3"]

    # scheme A: bin on ret_t
    tab_a = conditional_tail_table(df, "ret_t", "A_ret_t_deciles")

    # scheme B: bin on ret_recent_4
    tab_b = conditional_tail_table(df, "ret_recent_4", "B_recent4_deciles")

    out_a = os.path.join(OUTPUT_DIR, "step3_conditional_tail_by_ret_decile.csv")
    out_b = os.path.join(OUTPUT_DIR, "step3_conditional_tail_by_recent_decile.csv")
    tab_a.to_csv(out_a, index=False)
    tab_b.to_csv(out_b, index=False)

    # summary per timeframe
    # (We run per timeframe separately for institutional clarity)
    summaries = []
    for tf, sub in df.groupby("timeframe"):
        sub = sub.copy()
        sub["ret_recent_4"] = sub["ret_t"] + sub["ret_t_minus_1"] + sub["ret_t_minus_2"] + sub["ret_t_minus_3"]

        ta = conditional_tail_table(sub, "ret_t", "A_ret_t_deciles")
        tb = conditional_tail_table(sub, "ret_recent_4", "B_recent4_deciles")

        summaries.append({
            "timeframe": tf,
            "rows_used": int(len(sub)),
            "hi_count": int((sub["esc_pctl"] >= ESC_HIGH).sum()),
            "lo_count": int((sub["esc_pctl"] <= ESC_LOW).sum()),
            "overall_tail_rate": float(sub["tail_20"].mean()),
            "hi_tail_rate_overall": float(sub.loc[sub["esc_pctl"] >= ESC_HIGH, "tail_20"].mean()),
            "lo_tail_rate_overall": float(sub.loc[sub["esc_pctl"] <= ESC_LOW, "tail_20"].mean()),
            "overall_diff_hi_minus_lo": float(sub.loc[sub["esc_pctl"] >= ESC_HIGH, "tail_20"].mean()
                                             - sub.loc[sub["esc_pctl"] <= ESC_LOW, "tail_20"].mean()),
            "adj_diff_cond_on_ret_t": ta.attrs.get("adjusted_diff", np.nan),
            "adj_diff_cond_on_recent4": tb.attrs.get("adjusted_diff", np.nan),
        })

    summary = pd.DataFrame(summaries).sort_values("timeframe").reset_index(drop=True)
    out_s = os.path.join(OUTPUT_DIR, "step3_conditional_tail_summary.csv")
    summary.to_csv(out_s, index=False)

    # Tight console output
    print("=== STEP 3 — Conditional Tail Separation ===")
    print("DB:", DB_PATH)
    print(f"Horizon bars: {HORIZON_BARS} | Tail cutoff: {TAIL_CUTOFF:.2%}")
    print(f"HIGH esc_pctl >= {ESC_HIGH} | LOW esc_pctl <= {ESC_LOW}")
    print("Outputs:")
    print(" ", out_a)
    print(" ", out_b)
    print(" ", out_s)
    print()

    with pd.option_context("display.width", 200, "display.max_columns", 200):
        print(summary)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise

