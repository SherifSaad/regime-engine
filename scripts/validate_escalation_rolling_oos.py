#!/usr/bin/env python3
"""
Rolling Out-of-Sample (OOS) robustness test for escalation_score predicting 20-day downside tail risk.

What it does (per rolling window):
- Uses TRAIN ONLY to compute the Top X% escalation cutoff (default 5%).
- Applies that cutoff to TEST (OOS) data.
- Compares TEST forward 20d returns distribution for:
    (A) High escalation (>= cutoff)
    (B) Rest of sample
- Reports:
    - Tail probability P(fwd_20 <= -10%) in each group
    - Ratio (A/B)
    - Mann–Whitney U p-value (two-sided)
    - Cliff's delta effect size
Outputs:
- CSV table of window results
- Summary stats across windows

Inputs expected:
- A CSV that contains at least:
    - date column: timestamp OR date
    - escalation_score column: escalation_score
    - forward 20d return column: prefer fwd_20d_ret (but accepts fwd_20d, fwd_20, etc.)
    - (optional) regime column: regime / regime_label (not required for this step)

No lookahead: cutoff computed from TRAIN only.
"""

import os
import sys
import math
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

import numpy as np
import pandas as pd

try:
    from scipy.stats import mannwhitneyu
except Exception:
    print("ERROR: scipy is required. Install with: pip install scipy")
    sys.exit(1)


# ----------------------------
# Config (edit if needed)
# ----------------------------
DEFAULT_INPUT_CANDIDATES = [
    "spy_regime_daily_forward.csv",          # main regime-forward-returns output
    "escalation_score_daily.csv",            # if it already includes forward returns
    "regime_timeline.csv",
]

DATE_COL_CANDIDATES = ["timestamp", "date", "Datetime", "datetime"]
FWD20_COL_CANDIDATES = ["fwd_20d_ret", "fwd_20d", "fwd_20", "forward_20d", "fwd20", "fwd_20_ret"]
REGIME_COL_CANDIDATES = ["regime", "regime_label"]

ESC_COL = "escalation_score"

TAIL_THRESHOLD = -0.10      # -10% over next 20 trading days
TOP_PCT = 0.05              # top 5% escalation (train-only cutoff)

# Rolling structure (expanding train, fixed test length)
# Use year-based splits for clarity. You can adjust these safely.
TRAIN_START_YEAR = 2001
FIRST_TEST_START_YEAR = 2009
TEST_WINDOW_YEARS = 4
LAST_YEAR = 2026

MIN_TRAIN_ROWS = 500        # sanity: ensure train size is not tiny
MIN_TEST_ROWS = 200         # sanity: ensure test size is not tiny

# Output
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(ROOT, "validation_outputs")
OUTPUT_CSV_NAME = "escalation_rolling_oos_results.csv"


# ----------------------------
# Helpers
# ----------------------------
def _resolve_path(fname: str) -> Optional[str]:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    for base in [".", "validation_outputs", "data", "outputs"]:
        p = os.path.join(root, base, fname) if base != "." else os.path.join(root, fname)
        if os.path.exists(p):
            return p
    return None


def find_existing_input_path() -> str:
    for fname in DEFAULT_INPUT_CANDIDATES:
        p = _resolve_path(fname)
        if p:
            return p
    raise FileNotFoundError(
        "Could not find an input CSV. Place one of these in the current folder or common subfolders:\n"
        f"  {DEFAULT_INPUT_CANDIDATES}\n"
        "Or edit DEFAULT_INPUT_CANDIDATES in this script."
    )


def pick_column(df: pd.DataFrame, candidates: List[str], required: bool = True) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    if required:
        raise KeyError(f"Missing required column. None of these found: {candidates}. Available: {list(df.columns)}")
    return None


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """
    Cliff's delta: probability that a random x is greater than a random y minus reverse.
    Returns in [-1, 1]. Negative means x tends to be smaller than y.
    Implementation: O(n log n) via ranking approximation is possible, but n is small enough for O(n*m) per window.
    We'll do a safe-ish O(n*m) with early type coercion.
    """
    x = x[~np.isnan(x)]
    y = y[~np.isnan(y)]
    if len(x) == 0 or len(y) == 0:
        return np.nan
    # O(n*m)
    gt = 0
    lt = 0
    for xi in x:
        gt += np.sum(xi > y)
        lt += np.sum(xi < y)
    denom = len(x) * len(y)
    return (gt - lt) / denom


@dataclass
class WindowResult:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    n_train: int
    n_test: int
    cutoff: float
    n_high: int
    n_rest: int
    tail_high: float
    tail_rest: float
    ratio: float
    p_value: float
    cliffs_d: float


def safe_ratio(a: float, b: float) -> float:
    if b == 0:
        return math.inf if a > 0 else 1.0
    return a / b


# ----------------------------
# Main
# ----------------------------
def main():
    # 1) Load and merge if needed (escalation_score_daily has escalation, spy_regime_daily_forward has fwd_20d_ret)
    esc_path = _resolve_path("escalation_score_daily.csv")
    fwd_path = _resolve_path("spy_regime_daily_forward.csv")
    if esc_path and fwd_path:
        esc_df = pd.read_csv(esc_path)
        fwd_df = pd.read_csv(fwd_path)
        esc_date = pick_column(esc_df, DATE_COL_CANDIDATES, required=True)
        fwd_date = pick_column(fwd_df, DATE_COL_CANDIDATES, required=True)
        esc_df[esc_date] = pd.to_datetime(esc_df[esc_date], errors="coerce").dt.tz_localize(None)
        fwd_df[fwd_date] = pd.to_datetime(fwd_df[fwd_date], errors="coerce")
        esc_df["_date"] = esc_df[esc_date].dt.normalize()
        fwd_df["_date"] = fwd_df[fwd_date].dt.normalize()
        df = esc_df.merge(
            fwd_df[["_date", "fwd_20d_ret"]].dropna(subset=["fwd_20d_ret"]),
            on="_date",
            how="inner",
        ).drop(columns=["_date"])
        df = df.rename(columns={esc_date: "date"})
        input_path = f"(merged: {esc_path} + {fwd_path})"
    else:
        input_path = find_existing_input_path()
        df = pd.read_csv(input_path)

    if ESC_COL not in df.columns:
        raise KeyError(f"Missing escalation column '{ESC_COL}'. Need escalation_score_daily.csv.")

    date_col = pick_column(df, DATE_COL_CANDIDATES, required=True)
    fwd_col = pick_column(df, FWD20_COL_CANDIDATES, required=True)
    regime_col = pick_column(df, REGIME_COL_CANDIDATES, required=False)  # optional

    # 2) Normalize date + sort
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, ESC_COL, fwd_col]).copy()
    df = df.sort_values(date_col).reset_index(drop=True)

    df["year"] = df[date_col].dt.year.astype(int)

    # 3) Rolling windows
    results: List[WindowResult] = []

    test_start = FIRST_TEST_START_YEAR
    while test_start <= LAST_YEAR:
        test_end = min(test_start + TEST_WINDOW_YEARS - 1, LAST_YEAR)

        train_mask = (df["year"] >= TRAIN_START_YEAR) & (df["year"] <= (test_start - 1))
        test_mask = (df["year"] >= test_start) & (df["year"] <= test_end)

        train = df.loc[train_mask].copy()
        test = df.loc[test_mask].copy()

        # Sanity checks
        if len(train) < MIN_TRAIN_ROWS or len(test) < MIN_TEST_ROWS:
            # Stop once tests get too small near ends, or early start too small.
            # But keep going if only one side is small? We'll stop to avoid junk windows.
            break

        # TRAIN-only cutoff
        cutoff = float(np.nanquantile(train[ESC_COL].to_numpy(dtype=float), 1.0 - TOP_PCT))

        # Apply to TEST
        test_high = test.loc[test[ESC_COL] >= cutoff]
        test_rest = test.loc[test[ESC_COL] < cutoff]

        high_returns = test_high[fwd_col].to_numpy(dtype=float)
        rest_returns = test_rest[fwd_col].to_numpy(dtype=float)

        # Tail probabilities
        tail_high = float(np.mean(high_returns <= TAIL_THRESHOLD)) if len(high_returns) else np.nan
        tail_rest = float(np.mean(rest_returns <= TAIL_THRESHOLD)) if len(rest_returns) else np.nan
        ratio = safe_ratio(tail_high, tail_rest) if (not np.isnan(tail_high) and not np.isnan(tail_rest)) else np.nan

        # Mann–Whitney U (two-sided) comparing distributions
        # Note: if sizes are tiny, p-values can be unstable; we guarded via MIN_TEST_ROWS.
        try:
            u = mannwhitneyu(high_returns, rest_returns, alternative="two-sided")
            p_value = float(u.pvalue)
        except Exception:
            p_value = np.nan

        # Cliff's delta (negative means high escalation has *worse* returns if we compare high vs rest)
        # We want to know if high escalation shifts returns downward (more negative), so we compute delta on returns:
        # If high_returns tend to be smaller than rest_returns -> delta will be negative.
        cliffs_d = float(cliffs_delta(high_returns, rest_returns))

        # Date bounds
        train_start_dt = train[date_col].iloc[0]
        train_end_dt = train[date_col].iloc[-1]
        test_start_dt = test[date_col].iloc[0]
        test_end_dt = test[date_col].iloc[-1]

        results.append(
            WindowResult(
                train_start=train_start_dt.strftime("%Y-%m-%d"),
                train_end=train_end_dt.strftime("%Y-%m-%d"),
                test_start=test_start_dt.strftime("%Y-%m-%d"),
                test_end=test_end_dt.strftime("%Y-%m-%d"),
                n_train=int(len(train)),
                n_test=int(len(test)),
                cutoff=cutoff,
                n_high=int(len(test_high)),
                n_rest=int(len(test_rest)),
                tail_high=tail_high,
                tail_rest=tail_rest,
                ratio=ratio,
                p_value=p_value,
                cliffs_d=cliffs_d,
            )
        )

        # Next test window
        test_start += TEST_WINDOW_YEARS

    if not results:
        print("No valid rolling windows produced. Check years, input data coverage, and MIN_* thresholds.")
        sys.exit(1)

    # 4) Save table
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, OUTPUT_CSV_NAME)

    out_df = pd.DataFrame([r.__dict__ for r in results])

    # Add "directionality" helpers
    out_df["tail_diff"] = out_df["tail_high"] - out_df["tail_rest"]
    out_df["is_ratio_gt_1"] = out_df["ratio"] > 1.0
    out_df["is_p_lt_0_10"] = out_df["p_value"] < 0.10
    out_df["is_p_lt_0_05"] = out_df["p_value"] < 0.05

    out_df.to_csv(out_path, index=False)

    # 5) Print summary
    ratios = out_df["ratio"].replace([np.inf, -np.inf], np.nan).dropna()
    pvals = out_df["p_value"].dropna()
    taildiff = out_df["tail_diff"].dropna()

    print("\n=== Escalation Rolling OOS Robustness (Top 5% train-only cutoff) ===")
    print(f"Input file: {input_path}")
    print(f"Date column: {date_col} | Forward 20d column: {fwd_col} | Escalation column: {ESC_COL}")
    if regime_col:
        print(f"Regime column detected (not used in this step): {regime_col}")

    print(f"\nWindows produced: {len(out_df)}")
    print(f"Saved results: {out_path}")

    print("\n--- Key Stability Stats (across windows) ---")
    print(f"Median tail diff (high - rest): {np.median(taildiff):.4f}")
    print(f"Median ratio (high/rest): {np.median(ratios):.2f}")
    print(f"% windows ratio > 1: {100.0 * out_df['is_ratio_gt_1'].mean():.1f}%")
    print(f"% windows p < 0.10: {100.0 * out_df['is_p_lt_0_10'].mean():.1f}%")
    print(f"% windows p < 0.05: {100.0 * out_df['is_p_lt_0_05'].mean():.1f}%")

    worst = out_df.sort_values("ratio").iloc[0]
    best = out_df.sort_values("ratio").iloc[-1]
    print("\n--- Worst window (by ratio) ---")
    print(worst[["train_end", "test_start", "test_end", "tail_high", "tail_rest", "ratio", "p_value", "cliffs_d"]].to_string())
    print("\n--- Best window (by ratio) ---")
    print(best[["train_end", "test_start", "test_end", "tail_high", "tail_rest", "ratio", "p_value", "cliffs_d"]].to_string())

    print("\nDone.")


if __name__ == "__main__":
    main()
