#!/usr/bin/env python3
"""
STEP 4 — Overlapping Forward-Window Bias Check (Distribution Widening)
======================================================================

Purpose:
Forward-window events (e.g., |fwd_H| >= q95_abs) create overlapping samples.
This can inflate apparent confidence / effective sample size.

We compare:
A) Overlapping evaluation (all timestamps)
B) Non-overlapping evaluation (take every H bars)
C) Block-bootstrap style sampling (random non-overlapping blocks)

Focus (for now):
- SPY
- timeframe = 4h
- horizon H = 20
- HIGH esc_pctl >= 0.99 vs LOW esc_pctl <= 0.50
- Event = |fwd_H| >= q95_abs (threshold computed on OVERLAPPING universe for that TF)

Outputs:
- validation_outputs/step4_overlap_bias_summary.csv

Console prints a tight summary.
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

PROJECT_DIR = "/Users/sherifsaad/Documents/regime-engine"
DB_PATH = os.path.join(PROJECT_DIR, "data", "regime_cache_SPY_escalation_frozen_2026-02-19.db")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "validation_outputs")

SYMBOL = "SPY"
ESC_TABLE = "escalation_history_v3"
BARS_TABLE = "bars"

TF = "1day"
H = 20

ESC_HIGH = 0.95
ESC_LOW = 0.50

ABS_Q = 0.95

# Block sampling config
N_BOOT = 500          # number of resamples
SEED = 7              # deterministic
MAX_BLOCKS = 20000    # safety cap


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_joined() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)

    esc = pd.read_sql_query(
        f"SELECT symbol, timeframe, asof, esc_pctl FROM {ESC_TABLE} WHERE symbol=? AND timeframe=?",
        con, params=(SYMBOL, TF)
    )
    bars = pd.read_sql_query(
        f"SELECT symbol, timeframe, ts, close FROM {BARS_TABLE} WHERE symbol=? AND timeframe=?",
        con, params=(SYMBOL, TF)
    )
    con.close()

    esc["asof"] = pd.to_datetime(esc["asof"], errors="coerce")
    bars["ts"] = pd.to_datetime(bars["ts"], errors="coerce")

    esc = esc.dropna(subset=["asof", "esc_pctl"]).copy()
    bars = bars.dropna(subset=["ts", "close"]).copy()

    esc["esc_pctl"] = pd.to_numeric(esc["esc_pctl"], errors="coerce")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")

    esc = esc.dropna(subset=["esc_pctl"])
    bars = bars.dropna(subset=["close"])

    bars = bars.sort_values("ts").reset_index(drop=True)

    df = bars.merge(
        esc,
        left_on=["symbol", "timeframe", "ts"],
        right_on=["symbol", "timeframe", "asof"],
        how="left"
    ).drop(columns=["asof"])

    df = df.dropna(subset=["esc_pctl"]).copy()
    return df


def add_forward(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"].to_numpy(float)
    n = len(close)

    fwd = np.full(n, np.nan)
    if n > H:
        fwd[:-H] = close[H:] / close[:-H] - 1.0

    out = df.copy()
    out["fwd_H"] = fwd
    out["abs_fwd_H"] = np.abs(fwd)
    out = out.dropna(subset=["fwd_H", "abs_fwd_H"]).copy()
    return out


def compute_lift(work: pd.DataFrame, q95_abs: float) -> dict:
    work = work.copy()
    work["event"] = work["abs_fwd_H"] >= q95_abs
    hi = work[work["esc_pctl"] >= ESC_HIGH]
    lo = work[work["esc_pctl"] <= ESC_LOW]

    hi_n = len(hi)
    lo_n = len(lo)
    hi_rate = float(hi["event"].mean()) if hi_n else np.nan
    lo_rate = float(lo["event"].mean()) if lo_n else np.nan

    return {
        "n_total": int(len(work)),
        "hi_n": int(hi_n),
        "lo_n": int(lo_n),
        "hi_event_rate": hi_rate,
        "lo_event_rate": lo_rate,
        "diff_hi_minus_lo": (hi_rate - lo_rate) if (hi_n and lo_n) else np.nan,
        "ratio_hi_over_lo": (hi_rate / lo_rate) if (hi_n and lo_n and lo_rate > 0) else np.nan,
    }


def _event_driven_pick(work: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """
    Generic event-driven non-overlap picker:
    - Scan forward.
    - When mask[i] is True, keep i and then skip the next H bars.
    """
    work = work.reset_index(drop=True).copy()
    mask = mask.reset_index(drop=True)

    keep_idx = []
    i = 0
    n = len(work)
    while i < n:
        if bool(mask.iloc[i]):
            keep_idx.append(i)
            i += H
        else:
            i += 1
    return work.iloc[keep_idx].copy()


def non_overlap_high(work: pd.DataFrame) -> pd.DataFrame:
    """Event-driven non-overlap HIGH episodes (consume HIGH then skip H)."""
    return _event_driven_pick(work, work["esc_pctl"] >= ESC_HIGH)


def non_overlap_low(work: pd.DataFrame) -> pd.DataFrame:
    """Event-driven non-overlap LOW episodes (consume LOW then skip H)."""
    return _event_driven_pick(work, work["esc_pctl"] <= ESC_LOW)

def bootstrap_event_driven(work: pd.DataFrame, q95_abs: float, n_boot: int, seed: int) -> dict:
    """
    Bootstrap on event-driven non-overlapping episodes.
    Resample HIGH and LOW episode blocks with replacement.
    """
    rng = np.random.default_rng(seed)

    hi = work[work["esc_pctl"] >= ESC_HIGH].copy()
    lo = work[work["esc_pctl"] <= ESC_LOW].copy()

    if len(hi) == 0 or len(lo) == 0:
        return {"boot_mean_diff": np.nan,
                "boot_p05_diff": np.nan,
                "boot_p95_diff": np.nan,
                "boot_draws": 0}

    diffs = []

    for _ in range(n_boot):
        hi_s = hi.sample(n=len(hi), replace=True, random_state=None)
        lo_s = lo.sample(n=len(lo), replace=True, random_state=None)

        hi_rate = float((hi_s["abs_fwd_H"] >= q95_abs).mean())
        lo_rate = float((lo_s["abs_fwd_H"] >= q95_abs).mean())
        diffs.append(hi_rate - lo_rate)

    diffs = np.array(diffs, dtype=float)

    return {
        "boot_mean_diff": float(np.mean(diffs)),
        "boot_p05_diff": float(np.quantile(diffs, 0.05)),
        "boot_p95_diff": float(np.quantile(diffs, 0.95)),
        "boot_draws": int(len(diffs)),
    }
def main():
    ensure_dirs()

    df = load_joined()
    work = add_forward(df)

    # Threshold defined on the overlapping universe (unconditional q95 of abs forward move)
    q95_abs = float(work["abs_fwd_H"].quantile(ABS_Q))

    # A) overlapping
    a = compute_lift(work, q95_abs)
    a.update({"method": "A_overlapping", "timeframe": TF, "H": H, "q95_abs_threshold": q95_abs})

    # B) non-overlapping deterministic slice
    work_hi = non_overlap_high(work)
    work_lo = non_overlap_low(work)
    work_b = pd.concat([work_hi, work_lo], ignore_index=True)
    # STEP 5 SUPPORT: export episode-level sample used for non-overlap lift
    # Add group (HIGH/LOW) and event (1 if |fwd_H| >= q95_abs) for Step 5
    work_b = work_b.copy()
    work_b["group"] = np.where(work_b["esc_pctl"] >= ESC_HIGH, "HIGH", "LOW")
    work_b["event"] = (work_b["abs_fwd_H"] >= q95_abs).astype(int)
    out_eps = Path("validation_outputs/step4_event_driven_episodes.csv")
    work_b.sort_values("ts").to_csv(out_eps, index=False)
    print(f"[Step4] Wrote episode-level file for Step 5: {out_eps}  rows={len(work_b)}")
    b = compute_lift(work_b, q95_abs)
    b.update({"method": "B_event_driven_nonoverlap", "timeframe": TF, "H": H, "q95_abs_threshold": q95_abs})

    # C) bootstrap non-overlapping
    boot = bootstrap_event_driven(work_b, q95_abs, N_BOOT, SEED)
    c = compute_lift(work_b, q95_abs)  # reuse B rates as point estimate for non-overlap
    c.update({
        "method": "C_bootstrap_nonoverlap_CI",
        "timeframe": TF,
        "H": H,
        "q95_abs_threshold": q95_abs,
        "boot_mean_diff": boot["boot_mean_diff"],
        "boot_p05_diff": boot["boot_p05_diff"],
        "boot_p95_diff": boot["boot_p95_diff"],
        "boot_draws": boot["boot_draws"],
    })

    out = pd.DataFrame([a, b, c])

    out_path = os.path.join(OUTPUT_DIR, "step4_overlap_bias_summary.csv")
    out.to_csv(out_path, index=False)

    print("=== STEP 4 — Overlap Bias Check ===")
    print(f"TF={TF} | H={H} | Event: |fwd_H| >= q95_abs (q={ABS_Q})")
    print(f"q95_abs_threshold = {q95_abs:.6f}")
    print("Output:", out_path)
    print()

    with pd.option_context("display.width", 200, "display.max_columns", 200):
        print(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

