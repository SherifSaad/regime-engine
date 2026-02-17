#!/usr/bin/env python3
"""
STEP 2 — Stability Diagnostics for escalation_score

Goal:
- Diagnose why rolling OOS tail-expansion is unstable WITHOUT changing architecture.

Tests:
A) Escalation distribution stability by era/decade buckets:
   - count, mean, std, p95, p99, max
B) Cutoff drift:
   - global (full-sample) 95th percentile cutoff (single fixed value)
   - compare to per-window train-only cutoffs
C) Rolling OOS with FIXED global cutoff:
   - does tail-expansion become more stable if cutoff is fixed?
D) Sanity leakage checks:
   - ensures merge alignment and no duplicate dates
   - reports missingness after merge

Inputs:
- escalation_score_daily.csv  (must have date + escalation_score)
- spy_regime_daily_forward.csv (must have date + fwd_20d_ret)

Outputs (written to validation_outputs/):
- stability_escalation_distribution_by_era.csv
- stability_escalation_cutoff_drift.csv
- stability_escalation_fixed_cutoff_rolling_oos.csv
"""

import os
import sys
import math
import numpy as np
import pandas as pd

try:
    from scipy.stats import mannwhitneyu
except Exception:
    print("ERROR: scipy is required. Install with: pip install scipy")
    sys.exit(1)

ESC_COL = "escalation_score"
FWD_COL = "fwd_20d_ret"
DATE_COL_ESC_CAND = ["date", "timestamp", "Datetime", "datetime"]
DATE_COL_FWD_CAND = ["date", "timestamp", "Datetime", "datetime"]

TAIL_THRESHOLD = -0.10
TOP_PCT = 0.05  # 5%

TRAIN_START_YEAR = 2001
FIRST_TEST_START_YEAR = 2009
TEST_WINDOW_YEARS = 4
LAST_YEAR = 2026

MIN_TRAIN_ROWS = 500
MIN_TEST_ROWS = 200

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "validation_outputs")
os.makedirs(OUT_DIR, exist_ok=True)


def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"Missing date col. Looked for {candidates}. Found {list(df.columns)}")


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    x = x[~np.isnan(x)]
    y = y[~np.isnan(y)]
    if len(x) == 0 or len(y) == 0:
        return np.nan
    gt = 0
    lt = 0
    for xi in x:
        gt += np.sum(xi > y)
        lt += np.sum(xi < y)
    denom = len(x) * len(y)
    return (gt - lt) / denom


def safe_ratio(a: float, b: float) -> float:
    if b == 0:
        return math.inf if a > 0 else 0.0
    return a / b


def era_bucket(year: int) -> str:
    # Era buckets aligned to your project story (pre/post GFC, post-2017)
    if year <= 2008:
        return "2001-2008"
    if year <= 2016:
        return "2009-2016"
    return "2017-2026"


def main():
    esc_path = os.path.join(OUT_DIR, "escalation_score_daily.csv")
    fwd_path = os.path.join(OUT_DIR, "spy_regime_daily_forward.csv")

    if not os.path.exists(esc_path):
        esc_path = os.path.join(os.getcwd(), "escalation_score_daily.csv")
    if not os.path.exists(esc_path):
        raise FileNotFoundError(f"Missing escalation_score_daily.csv. Tried: {OUT_DIR} and {os.getcwd()}")
    if not os.path.exists(fwd_path):
        fwd_path = os.path.join(os.getcwd(), "spy_regime_daily_forward.csv")
    if not os.path.exists(fwd_path):
        raise FileNotFoundError(f"Missing spy_regime_daily_forward.csv. Tried: {OUT_DIR} and {os.getcwd()}")

    esc = pd.read_csv(esc_path)
    fwd = pd.read_csv(fwd_path)

    dcol_e = pick_col(esc, DATE_COL_ESC_CAND)
    dcol_f = pick_col(fwd, DATE_COL_FWD_CAND)

    if ESC_COL not in esc.columns:
        raise KeyError(f"{esc_path} missing column: {ESC_COL}")
    if FWD_COL not in fwd.columns:
        raise KeyError(f"{fwd_path} missing column: {FWD_COL}")

    esc[dcol_e] = pd.to_datetime(esc[dcol_e], errors="coerce")
    fwd[dcol_f] = pd.to_datetime(fwd[dcol_f], errors="coerce")
    # Normalize to date-only for merge (esc may be UTC-aware, fwd tz-naive)
    esc["_date"] = esc[dcol_e].dt.date
    fwd["_date"] = fwd[dcol_f].dt.date

    esc = esc.dropna(subset=[dcol_e, ESC_COL]).copy()
    fwd = fwd.dropna(subset=[dcol_f, FWD_COL]).copy()

    esc = esc.sort_values(dcol_e)
    fwd = fwd.sort_values(dcol_f)

    # Deduplicate dates defensively (keep last)
    esc_before = len(esc)
    fwd_before = len(fwd)
    esc = esc.drop_duplicates(subset=["_date"], keep="last")
    fwd = fwd.drop_duplicates(subset=["_date"], keep="last")

    # Merge (inner join to enforce alignment)
    df = pd.merge(esc[["_date", ESC_COL]], fwd[["_date", FWD_COL]], on="_date", how="inner")
    df = df.rename(columns={"_date": "date"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Basic sanity diagnostics
    sanity = {
        "esc_rows_before_dedup": esc_before,
        "esc_rows_after_dedup": len(esc),
        "fwd_rows_before_dedup": fwd_before,
        "fwd_rows_after_dedup": len(fwd),
        "merged_rows": len(df),
        "merged_min_date": str(df["date"].min().date()) if len(df) else None,
        "merged_max_date": str(df["date"].max().date()) if len(df) else None,
    }

    # Add year/era
    df["year"] = df["date"].dt.year.astype(int)
    df["era"] = df["year"].apply(era_bucket)

    # ------------------------------------------------------------------
    # A) Distribution stability by era
    # ------------------------------------------------------------------
    dist_rows = []
    for era, g in df.groupby("era"):
        x = g[ESC_COL].to_numpy(dtype=float)
        dist_rows.append({
            "era": era,
            "n": int(len(x)),
            "mean": float(np.mean(x)),
            "std": float(np.std(x, ddof=1)) if len(x) > 1 else np.nan,
            "p95": float(np.nanquantile(x, 0.95)),
            "p99": float(np.nanquantile(x, 0.99)),
            "max": float(np.max(x)),
        })
    dist_df = pd.DataFrame(dist_rows).sort_values("era")
    dist_out = os.path.join(OUT_DIR, "stability_escalation_distribution_by_era.csv")
    dist_df.to_csv(dist_out, index=False)

    # ------------------------------------------------------------------
    # B) Cutoff drift across rolling windows (train-only 95th percentile)
    # ------------------------------------------------------------------
    cutoff_rows = []
    test_start = FIRST_TEST_START_YEAR
    while test_start <= LAST_YEAR:
        test_end = min(test_start + TEST_WINDOW_YEARS - 1, LAST_YEAR)
        train = df[(df["year"] >= TRAIN_START_YEAR) & (df["year"] <= test_start - 1)]
        test = df[(df["year"] >= test_start) & (df["year"] <= test_end)]

        if len(train) < MIN_TRAIN_ROWS or len(test) < MIN_TEST_ROWS:
            break

        cutoff = float(np.nanquantile(train[ESC_COL].to_numpy(dtype=float), 1.0 - TOP_PCT))
        cutoff_rows.append({
            "train_end_year": test_start - 1,
            "test_start_year": test_start,
            "test_end_year": test_end,
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "train_cutoff_p95": cutoff,
        })
        test_start += TEST_WINDOW_YEARS

    cutoff_df = pd.DataFrame(cutoff_rows)
    cutoff_out = os.path.join(OUT_DIR, "stability_escalation_cutoff_drift.csv")
    cutoff_df.to_csv(cutoff_out, index=False)

    # ------------------------------------------------------------------
    # C) Rolling OOS using FIXED global cutoff (full-sample p95)
    # ------------------------------------------------------------------
    global_cutoff = float(np.nanquantile(df[ESC_COL].to_numpy(dtype=float), 1.0 - TOP_PCT))

    fixed_rows = []
    test_start = FIRST_TEST_START_YEAR
    while test_start <= LAST_YEAR:
        test_end = min(test_start + TEST_WINDOW_YEARS - 1, LAST_YEAR)
        train = df[(df["year"] >= TRAIN_START_YEAR) & (df["year"] <= test_start - 1)]
        test = df[(df["year"] >= test_start) & (df["year"] <= test_end)]

        if len(train) < MIN_TRAIN_ROWS or len(test) < MIN_TEST_ROWS:
            break

        hi = test[test[ESC_COL] >= global_cutoff]
        rest = test[test[ESC_COL] < global_cutoff]

        hi_ret = hi[FWD_COL].to_numpy(dtype=float)
        re_ret = rest[FWD_COL].to_numpy(dtype=float)

        tail_hi = float(np.mean(hi_ret <= TAIL_THRESHOLD)) if len(hi_ret) else np.nan
        tail_re = float(np.mean(re_ret <= TAIL_THRESHOLD)) if len(re_ret) else np.nan
        ratio = safe_ratio(tail_hi, tail_re) if (not np.isnan(tail_hi) and not np.isnan(tail_re)) else np.nan

        try:
            p = float(mannwhitneyu(hi_ret, re_ret, alternative="two-sided").pvalue)
        except Exception:
            p = np.nan

        cd = float(cliffs_delta(hi_ret, re_ret))

        fixed_rows.append({
            "test_start_year": test_start,
            "test_end_year": test_end,
            "n_test": int(len(test)),
            "global_cutoff_p95": global_cutoff,
            "n_high": int(len(hi)),
            "n_rest": int(len(rest)),
            "tail_high": tail_hi,
            "tail_rest": tail_re,
            "ratio": ratio,
            "p_value": p,
            "cliffs_d": cd,
        })

        test_start += TEST_WINDOW_YEARS

    fixed_df = pd.DataFrame(fixed_rows)
    fixed_out = os.path.join(OUT_DIR, "stability_escalation_fixed_cutoff_rolling_oos.csv")
    fixed_df.to_csv(fixed_out, index=False)

    # ------------------------------------------------------------------
    # Print short summary (what you will paste back)
    # ------------------------------------------------------------------
    print("\n=== STEP 2 — Stability Diagnostics Completed ===")
    print(f"Working dir: {os.getcwd()}")
    print(f"Sanity: {sanity}")
    print(f"Global p95 cutoff (fixed): {global_cutoff:.6f}")

    if len(cutoff_df):
        drift = float(cutoff_df["train_cutoff_p95"].max() - cutoff_df["train_cutoff_p95"].min())
        print(f"Train-cutoff drift range (max-min): {drift:.6f}")

    if len(fixed_df):
        ratios = fixed_df["ratio"].replace([np.inf, -np.inf], np.nan).dropna()
        med_ratio = float(np.median(ratios)) if len(ratios) else np.nan
        print("\n--- Fixed-cutoff rolling stats ---")
        print(f"Windows: {len(fixed_df)}")
        print(f"Median ratio: {med_ratio:.3f}")
        print(f"% windows ratio > 1: {100.0 * float((fixed_df['ratio'] > 1.0).mean()):.1f}%")
        print(f"% windows p < 0.05: {100.0 * float((fixed_df['p_value'] < 0.05).mean()):.1f}%")

    print("\nOutputs written:")
    print(f"  {dist_out}")
    print(f"  {cutoff_out}")
    print(f"  {fixed_out}")
    print("Done.")


if __name__ == "__main__":
    main()
