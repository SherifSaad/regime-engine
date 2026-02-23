#!/usr/bin/env python3
"""
STEP 3A' — Controlled (Binned) Distribution Widening Test
========================================================
Question:
Does esc_pctl add incremental widening information AFTER controlling for current stress?

We test for each timeframe (focus: 1h, 4h) and horizon H=20:
Event = |fwd_H| >= q95_abs (threshold computed per timeframe)
Then we control for stress by binning on:
  - abs(ret_t) deciles
  - recent realized vol deciles (RV over last 20 bars)

Within each (abs_ret_bin, rv_bin):
  Compare event rate for HIGH esc (>=0.99) vs LOW esc (<=0.50)
  Then compute a weighted average lift across bins.

Outputs:
- validation_outputs/step3A_widening_binned_detail.csv
- validation_outputs/step3A_widening_binned_summary.csv
"""

from __future__ import annotations

import os, sqlite3
import numpy as np
import pandas as pd

PROJECT_DIR = "/Users/sherifsaad/Documents/regime-engine"
DB_PATH = os.path.join(PROJECT_DIR, "data", "regime_cache_SPY_escalation_frozen_2026-02-19.db")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "validation_outputs")

SYMBOL = "SPY"
ESC_TABLE = "escalation_history_v3"
BARS_TABLE = "bars"

TF_FOCUS = {"1h", "4h"}   # we can expand later
H = 20

ESC_HIGH = 0.99
ESC_LOW  = 0.50

N_BINS = 10  # deciles
RV_WINDOW = 20  # recent realized vol window (bars)

def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_joined() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    esc = pd.read_sql_query(
        f"SELECT symbol, timeframe, asof, esc_pctl FROM {ESC_TABLE} WHERE symbol=?",
        con, params=(SYMBOL,)
    )
    bars = pd.read_sql_query(
        f"SELECT symbol, timeframe, ts, close FROM {BARS_TABLE} WHERE symbol=?",
        con, params=(SYMBOL,)
    )
    con.close()

    esc["asof"] = pd.to_datetime(esc["asof"], errors="coerce")
    bars["ts"]  = pd.to_datetime(bars["ts"], errors="coerce")
    esc = esc.dropna(subset=["asof","timeframe","esc_pctl"])
    bars = bars.dropna(subset=["ts","timeframe","close"])

    esc["esc_pctl"] = pd.to_numeric(esc["esc_pctl"], errors="coerce")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    esc = esc.dropna(subset=["esc_pctl"])
    bars = bars.dropna(subset=["close"])

    bars = bars.sort_values(["timeframe","ts"]).reset_index(drop=True)

    df = bars.merge(
        esc,
        left_on=["symbol","timeframe","ts"],
        right_on=["symbol","timeframe","asof"],
        how="left",
    ).drop(columns=["asof"])

    df = df.dropna(subset=["esc_pctl"]).copy()
    return df

def qbin(s: pd.Series, n=N_BINS):
    try:
        return pd.qcut(s, q=n, duplicates="drop")
    except Exception:
        r = s.rank(method="average")
        return pd.qcut(r, q=n, duplicates="drop")

def main():
    ensure_dirs()
    df = load_joined()

    details = []
    summaries = []

    for tf, d in df.groupby("timeframe"):
        if tf not in TF_FOCUS:
            continue

        d = d.sort_values("ts").reset_index(drop=True)
        close = d["close"].to_numpy(float)

        # returns
        d["ret_t"] = pd.Series(close).pct_change().to_numpy()
        d["abs_ret_t"] = np.abs(d["ret_t"])

        # realized vol (std of returns over RV_WINDOW)
        d["rv_20"] = pd.Series(d["ret_t"]).rolling(RV_WINDOW).std(ddof=0)

        # forward return
        fwd = np.full(len(d), np.nan)
        if len(d) > H:
            fwd[:-H] = close[H:] / close[:-H] - 1.0
        d["fwd_H"] = fwd
        d["abs_fwd_H"] = np.abs(d["fwd_H"])

        # drop warmup / nan rows
        d = d.dropna(subset=["ret_t","abs_ret_t","rv_20","fwd_H","abs_fwd_H"]).copy()

        # event threshold = unconditional q95 of abs_fwd_H (per timeframe)
        q95_abs = float(d["abs_fwd_H"].quantile(0.95))
        d["event"] = d["abs_fwd_H"] >= q95_abs

        # groups
        d["is_high"] = d["esc_pctl"] >= ESC_HIGH
        d["is_low"]  = d["esc_pctl"] <= ESC_LOW

        # control bins
        d["bin_absret"] = qbin(d["abs_ret_t"], N_BINS)
        d["bin_rv"]     = qbin(d["rv_20"], N_BINS)

        # within-bin comparison
        for (b1, b2), sub in d.groupby(["bin_absret","bin_rv"]):
            hi = sub[sub["is_high"]]
            lo = sub[sub["is_low"]]
            if len(hi) == 0 or len(lo) == 0:
                continue

            hi_rate = float(hi["event"].mean())
            lo_rate = float(lo["event"].mean())
            diff = hi_rate - lo_rate

            details.append({
                "timeframe": tf,
                "H": H,
                "q95_abs_threshold": q95_abs,
                "bin_absret": str(b1),
                "bin_rv": str(b2),
                "n_total": int(len(sub)),
                "hi_n": int(len(hi)),
                "lo_n": int(len(lo)),
                "hi_event_rate": hi_rate,
                "lo_event_rate": lo_rate,
                "diff_hi_minus_lo": diff,
                "bin_mean_absret": float(sub["abs_ret_t"].mean()),
                "bin_mean_rv": float(sub["rv_20"].mean()),
            })

        det = pd.DataFrame(details)
        det_tf = det[det["timeframe"] == tf].copy()

        if det_tf.empty:
            summaries.append({
                "timeframe": tf,
                "note": "No bins had both HIGH and LOW samples.",
                "adj_diff": np.nan,
                "bins_used": 0
            })
            continue

        # weighted average diff across bins
        w = np.minimum(det_tf["hi_n"].values, det_tf["lo_n"].values).astype(float)
        adj = float(np.average(det_tf["diff_hi_minus_lo"].values, weights=w)) if w.sum() > 0 else np.nan

        summaries.append({
            "timeframe": tf,
            "H": H,
            "q95_abs_threshold": q95_abs,
            "bins_used": int(len(det_tf)),
            "adj_diff_hi_minus_lo": adj,
            "mean_bin_absret": float(det_tf["bin_mean_absret"].mean()),
            "mean_bin_rv": float(det_tf["bin_mean_rv"].mean()),
        })

    detail_df = pd.DataFrame(details)
    summary_df = pd.DataFrame(summaries).sort_values("timeframe").reset_index(drop=True)

    out_detail = os.path.join(OUTPUT_DIR, "step3A_widening_binned_detail.csv")
    out_summary = os.path.join(OUTPUT_DIR, "step3A_widening_binned_summary.csv")

    detail_df.to_csv(out_detail, index=False)
    summary_df.to_csv(out_summary, index=False)

    print("=== STEP 3A' — Controlled Widening (Binned) ===")
    print("TF focus:", sorted(TF_FOCUS), "| H =", H, "| Event: |fwd_H| >= q95_abs (per TF)")
    print("Controls: abs(ret_t) deciles + RV(20) deciles")
    print("Outputs:")
    print(" ", out_detail)
    print(" ", out_summary)
    print()
    with pd.option_context("display.width", 200, "display.max_columns", 200):
        print(summary_df)

if __name__ == "__main__":
    main()

