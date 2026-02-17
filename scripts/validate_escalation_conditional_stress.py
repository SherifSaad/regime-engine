#!/usr/bin/env python3
"""
STEP 3 — Conditional Escalation Validation (Stress Regimes Only)

Goal:
Test whether escalation_score expands 20-day downside tail
WHEN the system is already in stress-related regimes.

We DO NOT change architecture.
We ONLY change evaluation conditioning.

Condition:
regime_label ∈ {"TRANSITION", "PANIC_RISK", "SHOCK"}

Rolling OOS:
- Expanding train
- 4-year OOS blocks
- Train-only 95th percentile cutoff
- Evaluate ONLY within stress-regime rows in OOS

Outputs:
validation_outputs/escalation_conditional_stress_rolling_oos.csv
"""

import os
import sys
import math
import numpy as np
import pandas as pd

from scipy.stats import mannwhitneyu

ESC_COL = "escalation_score"
FWD_COL = "fwd_20d_ret"
REGIME_COL_CAND = ["regime_label", "regime"]

DATE_COL_CAND = ["date", "timestamp"]

TAIL_THRESHOLD = -0.10
TOP_PCT = 0.05

TRAIN_START_YEAR = 2001
FIRST_TEST_START_YEAR = 2009
TEST_WINDOW_YEARS = 4
LAST_YEAR = 2026

MIN_TRAIN_ROWS = 500
MIN_TEST_ROWS = 100

STRESS_REGIMES = {"TRANSITION", "PANIC_RISK", "SHOCK"}

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "validation_outputs")
os.makedirs(OUT_DIR, exist_ok=True)


def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"Missing date column. Found: {list(df.columns)}")


def cliffs_delta(x, y):
    x = x[~np.isnan(x)]
    y = y[~np.isnan(y)]
    if len(x) == 0 or len(y) == 0:
        return np.nan
    gt = 0
    lt = 0
    for xi in x:
        gt += np.sum(xi > y)
        lt += np.sum(xi < y)
    return (gt - lt) / (len(x) * len(y))


def safe_ratio(a, b):
    if b == 0:
        return math.inf if a > 0 else 0.0
    return a / b


def main():

    esc_path = os.path.join(OUT_DIR, "escalation_score_daily.csv")
    fwd_path = os.path.join(OUT_DIR, "spy_regime_daily_forward.csv")

    if not os.path.exists(esc_path) or not os.path.exists(fwd_path):
        raise FileNotFoundError("Required CSV files not found in validation_outputs/.")

    esc = pd.read_csv(esc_path)
    fwd = pd.read_csv(fwd_path)

    dcol_e = pick_col(esc, DATE_COL_CAND)
    dcol_f = pick_col(fwd, DATE_COL_CAND)

    esc[dcol_e] = pd.to_datetime(esc[dcol_e], errors="coerce")
    fwd[dcol_f] = pd.to_datetime(fwd[dcol_f], errors="coerce")
    esc["_date"] = esc[dcol_e].dt.date
    fwd["_date"] = fwd[dcol_f].dt.date

    esc = esc.drop_duplicates(subset=["_date"], keep="last")
    fwd = fwd.drop_duplicates(subset=["_date"], keep="last")

    regime_col = pick_col(fwd, REGIME_COL_CAND)
    merge_cols = ["_date", FWD_COL, regime_col]
    df = pd.merge(
        esc[["_date", ESC_COL]],
        fwd[merge_cols],
        on="_date",
        how="inner",
    )
    df = df.rename(columns={"_date": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={regime_col: "regime_label"})

    df = df.sort_values("date").reset_index(drop=True)
    df["year"] = df["date"].dt.year

    results = []

    test_start = FIRST_TEST_START_YEAR

    while test_start <= LAST_YEAR:

        test_end = min(test_start + TEST_WINDOW_YEARS - 1, LAST_YEAR)

        train = df[(df["year"] >= TRAIN_START_YEAR) & (df["year"] <= test_start - 1)]
        test = df[(df["year"] >= test_start) & (df["year"] <= test_end)]

        if len(train) < MIN_TRAIN_ROWS:
            break

        # Train-only cutoff
        cutoff = np.nanquantile(train[ESC_COL], 1 - TOP_PCT)

        # Condition OOS to stress regimes only
        test_stress = test[test["regime_label"].isin(STRESS_REGIMES)]

        if len(test_stress) < MIN_TEST_ROWS:
            test_start += TEST_WINDOW_YEARS
            continue

        high = test_stress[test_stress[ESC_COL] >= cutoff]
        rest = test_stress[test_stress[ESC_COL] < cutoff]

        high_ret = high[FWD_COL].to_numpy(dtype=float)
        rest_ret = rest[FWD_COL].to_numpy(dtype=float)

        tail_high = np.mean(high_ret <= TAIL_THRESHOLD) if len(high_ret) else np.nan
        tail_rest = np.mean(rest_ret <= TAIL_THRESHOLD) if len(rest_ret) else np.nan
        ratio = safe_ratio(tail_high, tail_rest)

        try:
            p = mannwhitneyu(high_ret, rest_ret, alternative="two-sided").pvalue
        except Exception:
            p = np.nan

        cd = cliffs_delta(high_ret, rest_ret)

        results.append({
            "test_start_year": test_start,
            "test_end_year": test_end,
            "n_test_stress": len(test_stress),
            "n_high": len(high),
            "n_rest": len(rest),
            "tail_high": tail_high,
            "tail_rest": tail_rest,
            "ratio": ratio,
            "p_value": p,
            "cliffs_d": cd,
        })

        test_start += TEST_WINDOW_YEARS

    out_df = pd.DataFrame(results)
    out_path = os.path.join(OUT_DIR, "escalation_conditional_stress_rolling_oos.csv")
    out_df.to_csv(out_path, index=False)

    print("\n=== STEP 3 — Conditional Stress Validation Completed ===")
    print(f"Windows: {len(out_df)}")
    if len(out_df):
        ratios = out_df["ratio"].replace([np.inf, -np.inf], np.nan).dropna()
        med = float(np.median(ratios)) if len(ratios) else np.nan
        print(f"Median ratio: {med:.3f}")
        print(f"% windows ratio > 1: {100 * (out_df['ratio'] > 1).mean():.1f}%")
        print(f"% windows p < 0.05: {100 * (out_df['p_value'] < 0.05).mean():.1f}%")
    print(f"Output: {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()
