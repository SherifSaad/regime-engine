#!/usr/bin/env python3
"""
Statistical validation for regime forward returns.

What it does (deterministic):
- Loads validation_outputs/spy_regime_daily_forward.csv (preferred) or validation_outputs/regime_timeline.csv (fallback if it contains forward returns).
- Finds the best forward-return columns for 5d/10d/20d (robust name matching).
- Runs pairwise tests for selected regime pairs:
  * Welch t-test (difference in means)
  * Mann–Whitney U (difference in distributions; non-parametric)
  * Bootstrap 95% CI for:
      - mean difference
      - median difference
- Writes results to: validation_outputs/regime_stat_tests.csv
"""

from __future__ import annotations

import os
import re
import math
import numpy as np
import pandas as pd

# --- Optional SciPy (preferred). If missing, script still runs with bootstrap + approximate t.
try:
    from scipy import stats  # type: ignore
    SCIPY_OK = True
except Exception:
    SCIPY_OK = False


INPUT_CANDIDATES = [
    "validation_outputs/spy_regime_daily_forward.csv",
    "validation_outputs/spy_regime_annotated.csv",
    "validation_outputs/regime_timeline.csv",
]

OUT_CSV = "validation_outputs/regime_stat_tests.csv"

# Regime pairs we care about first (can expand later)
REGIME_PAIRS = [
    ("SHOCK", "TRENDING_BULL"),
    ("PANIC_RISK", "TRENDING_BULL"),
    ("PANIC_RISK", "TRANSITION"),
    ("TRENDING_BEAR", "TRENDING_BULL"),
    ("CHOP_RISK", "TRENDING_BULL"),
]

HORIZONS = [5, 10, 20]
N_BOOT = 20000
SEED = 42


def pick_input_file() -> str:
    for path in INPUT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Could not find any input file. Expected one of:\n  - " + "\n  - ".join(INPUT_CANDIDATES)
    )


def normalize_col(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.strip().lower())


def find_regime_column(df: pd.DataFrame) -> str:
    candidates = ["regime_label", "regime", "label", "state", "regimeName"]
    norm_map = {normalize_col(c): c for c in df.columns}
    for want in candidates:
        k = normalize_col(want)
        if k in norm_map:
            return norm_map[k]

    # fallback: any column containing "regime"
    for c in df.columns:
        if "regime" in normalize_col(c):
            return c

    raise ValueError("Could not find regime column (expected something like regime_label).")


def find_forward_return_col(df: pd.DataFrame, horizon: int) -> str:
    """
    Robustly find a forward return column for a given horizon.
    Accepts many naming conventions:
      fwd_5d, forward_5d, ret_fwd_5d, r_5d, future_5d, return_5d, etc.
    """
    norm_cols = {normalize_col(c): c for c in df.columns}

    # Priority patterns (most specific first)
    patterns = [
        fr"(forward|fwd|future).*{horizon}d",
        fr"{horizon}d.*(forward|fwd|future)",
        fr"(ret|return|r).*{horizon}d",
        fr"{horizon}d.*(ret|return|r)",
    ]

    for pat in patterns:
        rx = re.compile(pat)
        hits = []
        for n, orig in norm_cols.items():
            if rx.search(n):
                hits.append(orig)

        # Prefer columns that look like returns, not percentiles/summary fields
        if hits:
            # If multiple, pick the shortest name (usually the clean computed column)
            hits_sorted = sorted(hits, key=lambda x: (len(x), x))
            return hits_sorted[0]

    raise ValueError(f"Could not find forward return column for horizon={horizon}d in columns: {list(df.columns)}")


def clean_series(x: pd.Series) -> np.ndarray:
    a = pd.to_numeric(x, errors="coerce").to_numpy(dtype=float)
    a = a[np.isfinite(a)]
    return a


def welch_ttest(a: np.ndarray, b: np.ndarray):
    if len(a) < 2 or len(b) < 2:
        return (np.nan, np.nan)

    if SCIPY_OK:
        res = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
        return float(res.statistic), float(res.pvalue)

    # Approx Welch t-test p-value using normal approximation (fallback).
    ma, mb = float(np.mean(a)), float(np.mean(b))
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    se = math.sqrt(va / len(a) + vb / len(b))
    if se == 0:
        return (np.nan, np.nan)
    t = (ma - mb) / se
    # Normal approx p-value (two-sided)
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return (float(t), float(p))


def mann_whitney(a: np.ndarray, b: np.ndarray):
    if len(a) < 2 or len(b) < 2:
        return (np.nan, np.nan)

    if not SCIPY_OK:
        return (np.nan, np.nan)  # Only available via SciPy

    # two-sided Mann–Whitney U
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    return float(res.statistic), float(res.pvalue)


def bootstrap_ci_diff(a: np.ndarray, b: np.ndarray, func, n_boot: int, rng: np.random.Generator):
    """
    Bootstrap CI for diff = func(a) - func(b)
    """
    if len(a) == 0 or len(b) == 0:
        return (np.nan, np.nan, np.nan)

    diffs = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sa = a[rng.integers(0, len(a), size=len(a))]
        sb = b[rng.integers(0, len(b), size=len(b))]
        diffs[i] = func(sa) - func(sb)

    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return (float(np.mean(diffs)), float(lo), float(hi))


def main():
    in_file = pick_input_file()
    df = pd.read_csv(in_file)

    regime_col = find_regime_column(df)

    # Make sure regime labels are strings
    df[regime_col] = df[regime_col].astype(str).str.strip()

    # Identify forward-return columns for each horizon
    fwd_cols = {}
    for h in HORIZONS:
        fwd_cols[h] = find_forward_return_col(df, h)

    rng = np.random.default_rng(SEED)

    rows = []
    for h in HORIZONS:
        col = fwd_cols[h]

        for r1, r2 in REGIME_PAIRS:
            a = clean_series(df.loc[df[regime_col] == r1, col])
            b = clean_series(df.loc[df[regime_col] == r2, col])

            # Stats + tests
            n1, n2 = len(a), len(b)
            m1, m2 = (float(np.mean(a)) if n1 else np.nan), (float(np.mean(b)) if n2 else np.nan)
            md1, md2 = (float(np.median(a)) if n1 else np.nan), (float(np.median(b)) if n2 else np.nan)

            t_stat, t_p = welch_ttest(a, b)
            u_stat, u_p = mann_whitney(a, b)

            mean_diff = m1 - m2 if (np.isfinite(m1) and np.isfinite(m2)) else np.nan
            median_diff = md1 - md2 if (np.isfinite(md1) and np.isfinite(md2)) else np.nan

            boot_mean_mu, boot_mean_lo, boot_mean_hi = bootstrap_ci_diff(
                a, b, func=lambda x: float(np.mean(x)), n_boot=N_BOOT, rng=rng
            )
            boot_med_mu, boot_med_lo, boot_med_hi = bootstrap_ci_diff(
                a, b, func=lambda x: float(np.median(x)), n_boot=N_BOOT, rng=rng
            )

            rows.append(
                {
                    "horizon_days": h,
                    "forward_return_col": col,
                    "regime_A": r1,
                    "regime_B": r2,
                    "n_A": n1,
                    "n_B": n2,
                    "mean_A": m1,
                    "mean_B": m2,
                    "mean_diff_A_minus_B": mean_diff,
                    "median_A": md1,
                    "median_B": md2,
                    "median_diff_A_minus_B": median_diff,
                    "welch_t_stat": t_stat,
                    "welch_t_pvalue": t_p,
                    "mannwhitney_u_stat": u_stat,
                    "mannwhitney_u_pvalue": u_p,
                    "boot_mean_diff_mean": boot_mean_mu,
                    "boot_mean_diff_ci_lo": boot_mean_lo,
                    "boot_mean_diff_ci_hi": boot_mean_hi,
                    "boot_median_diff_mean": boot_med_mu,
                    "boot_median_diff_ci_lo": boot_med_lo,
                    "boot_median_diff_ci_hi": boot_med_hi,
                    "scipy_available": SCIPY_OK,
                }
            )

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)

    # Print the most important first-pass lines (5d comparisons)
    print(f"INPUT:  {in_file}")
    print(f"OUT:    {OUT_CSV}")
    print(f"SciPy:  {SCIPY_OK}")
    print("\n=== KEY RESULTS (5d) ===")
    show = out[out["horizon_days"] == 5].copy()
    show = show.sort_values(["regime_A", "regime_B"])
    cols = [
        "regime_A","regime_B","n_A","n_B",
        "mean_diff_A_minus_B","welch_t_pvalue",
        "boot_mean_diff_ci_lo","boot_mean_diff_ci_hi",
        "median_diff_A_minus_B","mannwhitney_u_pvalue",
        "boot_median_diff_ci_lo","boot_median_diff_ci_hi",
    ]
    with pd.option_context("display.max_columns", 100, "display.width", 160):
        print(show[cols].to_string(index=False))


if __name__ == "__main__":
    main()
