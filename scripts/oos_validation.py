#!/usr/bin/env python3
"""
Out-of-Sample (OOS) validation for regime engine forward returns.

What it does:
- Loads SPY price history (data/spy_sample.csv)
- Loads regime timeline output (validation_outputs/regime_timeline.csv)
- Merges them by date
- Computes forward returns (5d/10d/20d) from SPY close
- Splits into Train/Test by date
- For each horizon, runs Mann–Whitney U tests on TEST ONLY:
    - SHOCK vs TRENDING_BULL
    - PANIC_RISK vs TRENDING_BULL
    - TRENDING_BEAR vs TRENDING_BULL
    - CHOP_RISK vs TRENDING_BULL
- Also exports effect sizes (Cliff's delta) and simple distribution stats

Outputs:
- validation_outputs/oos_stat_tests_<TRAINSTART-TRAINEND>__<TESTSTART-TESTEND>.csv
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Dict, Tuple, List

import numpy as np
import pandas as pd

# SciPy optional but recommended (you already have it)
try:
    from scipy.stats import mannwhitneyu
    SCIPY_OK = True
except Exception:
    SCIPY_OK = False


@dataclass(frozen=True)
class Split:
    train_start: str
    train_end: str
    test_start: str
    test_end: str


DEFAULT_SPLIT = Split(
    train_start="2001-01-02",
    train_end="2014-12-31",
    test_start="2015-01-01",
    test_end="2026-02-12",
)

HORIZONS = [5, 10, 20]
BASE_REGIME = "TRENDING_BULL"
COMPARE_REGIMES = ["SHOCK", "PANIC_RISK", "TRENDING_BEAR", "CHOP_RISK"]


def _read_spy_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Date" not in df.columns:
        raise ValueError(f"{path} missing 'Date' column.")
    # Allow common naming
    close_col = None
    for c in ["Close", "close", "Adj Close", "AdjClose", "adj_close"]:
        if c in df.columns:
            close_col = c
            break
    if close_col is None:
        raise ValueError(f"{path} missing a Close/Adj Close column. Found columns: {list(df.columns)}")

    df["Date"] = pd.to_datetime(df["Date"], utc=False).dt.normalize()
    df = df.sort_values("Date").reset_index(drop=True)
    df = df[["Date", close_col]].rename(columns={close_col: "Close"})
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"])
    return df


def _read_regime_timeline(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.shape[1] < 2:
        raise ValueError(f"{path} does not look like a regime timeline CSV.")

    # Expected format from your grep output:
    # date,regime_label,confidence,instability_index,downside_shock_risk,risk_level,vrs,market_bias,structural_score
    # OR with timezone like "2015-08-24 00:00:00+00:00"
    date_col = df.columns[0]
    label_col = df.columns[1]

    df[date_col] = pd.to_datetime(df[date_col], utc=True, errors="coerce")
    # Convert to naive normalized date for merge with SPY daily
    df["Date"] = df[date_col].dt.tz_convert(None).dt.normalize()

    df = df.rename(columns={label_col: "regime_label"})
    keep = ["Date", "regime_label"]
    for c in ["confidence", "instability_index", "downside_shock_risk", "risk_level", "vrs", "market_bias", "structural_score"]:
        if c in df.columns:
            keep.append(c)
    df = df[keep].dropna(subset=["Date", "regime_label"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def _forward_return(close: pd.Series, horizon: int) -> pd.Series:
    # simple forward return: (Close[t+h]/Close[t]) - 1
    return close.shift(-horizon) / close - 1.0


def _cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """
    Cliff's delta: P(X>Y) - P(X<Y)
    Range: [-1, 1]
    """
    x = x[~np.isnan(x)]
    y = y[~np.isnan(y)]
    if len(x) == 0 or len(y) == 0:
        return np.nan
    # Efficient ranking-based approach
    xy = np.concatenate([x, y])
    ranks = pd.Series(xy).rank(method="average").to_numpy()
    rx = ranks[: len(x)]
    ry = ranks[len(x):]
    # U for x:
    u = rx.sum() - len(x) * (len(x) + 1) / 2
    # delta from U:
    delta = (2 * u) / (len(x) * len(y)) - 1
    return float(delta)


def _mw_pvalue(x: np.ndarray, y: np.ndarray) -> float:
    if not SCIPY_OK:
        return np.nan
    x = x[~np.isnan(x)]
    y = y[~np.isnan(y)]
    if len(x) < 5 or len(y) < 5:
        return np.nan
    # two-sided test, asymptotic for speed; exact can be slow on large samples
    res = mannwhitneyu(x, y, alternative="two-sided", method="asymptotic")
    return float(res.pvalue)


def _basic_stats(a: np.ndarray) -> Dict[str, float]:
    a = a[~np.isnan(a)]
    if len(a) == 0:
        return {k: np.nan for k in ["n", "mean", "median", "std", "p05", "p25", "p75", "p95", "neg_rate"]}
    return {
        "n": float(len(a)),
        "mean": float(np.mean(a)),
        "median": float(np.median(a)),
        "std": float(np.std(a, ddof=1)) if len(a) > 1 else 0.0,
        "p05": float(np.quantile(a, 0.05)),
        "p25": float(np.quantile(a, 0.25)),
        "p75": float(np.quantile(a, 0.75)),
        "p95": float(np.quantile(a, 0.95)),
        "neg_rate": float(np.mean(a < 0.0)),
    }


def run_oos(
    spy_csv: str,
    regime_timeline_csv: str,
    out_dir: str,
    split: Split,
) -> str:
    spy = _read_spy_csv(spy_csv)
    reg = _read_regime_timeline(regime_timeline_csv)

    df = pd.merge(spy, reg, on="Date", how="inner").sort_values("Date").reset_index(drop=True)

    # forward returns
    for h in HORIZONS:
        df[f"fwd_{h}d"] = _forward_return(df["Close"], h)

    # split masks
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    train_mask = (df["Date"] >= pd.to_datetime(split.train_start)) & (df["Date"] <= pd.to_datetime(split.train_end))
    test_mask = (df["Date"] >= pd.to_datetime(split.test_start)) & (df["Date"] <= pd.to_datetime(split.test_end))

    train = df.loc[train_mask].copy()
    test = df.loc[test_mask].copy()

    # sanity
    if train.empty or test.empty:
        raise ValueError(
            f"Empty train or test after split. "
            f"Train rows={len(train)} Test rows={len(test)}. "
            f"Check split dates vs data coverage."
        )

    rows: List[Dict[str, object]] = []
    for h in HORIZONS:
        col = f"fwd_{h}d"

        base = test.loc[test["regime_label"] == BASE_REGIME, col].to_numpy(dtype=float)
        base_stats = _basic_stats(base)

        for comp in COMPARE_REGIMES:
            x = test.loc[test["regime_label"] == comp, col].to_numpy(dtype=float)
            comp_stats = _basic_stats(x)

            row = {
                "split_train_start": split.train_start,
                "split_train_end": split.train_end,
                "split_test_start": split.test_start,
                "split_test_end": split.test_end,
                "horizon_days": h,
                "base_regime": BASE_REGIME,
                "compare_regime": comp,
                "mw_pvalue_test": _mw_pvalue(x, base),
                "cliffs_delta_test": _cliffs_delta(x, base),
                # sample sizes on TEST
                "n_base_test": int(base_stats["n"]) if not np.isnan(base_stats["n"]) else 0,
                "n_comp_test": int(comp_stats["n"]) if not np.isnan(comp_stats["n"]) else 0,
                # base stats
                "base_mean": base_stats["mean"],
                "base_median": base_stats["median"],
                "base_std": base_stats["std"],
                "base_p05": base_stats["p05"],
                "base_p25": base_stats["p25"],
                "base_p75": base_stats["p75"],
                "base_p95": base_stats["p95"],
                "base_neg_rate": base_stats["neg_rate"],
                # comp stats
                "comp_mean": comp_stats["mean"],
                "comp_median": comp_stats["median"],
                "comp_std": comp_stats["std"],
                "comp_p05": comp_stats["p05"],
                "comp_p25": comp_stats["p25"],
                "comp_p75": comp_stats["p75"],
                "comp_p95": comp_stats["p95"],
                "comp_neg_rate": comp_stats["neg_rate"],
            }
            rows.append(row)

    out = pd.DataFrame(rows)

    os.makedirs(out_dir, exist_ok=True)
    tag = f"{split.train_start}_{split.train_end}__{split.test_start}_{split.test_end}".replace("-", "")
    out_path = os.path.join(out_dir, f"oos_stat_tests_{tag}.csv")
    out.to_csv(out_path, index=False)
    return out_path


# Rolling OOS: train_len years, test_len years, step 1 year
ROLLING_TRAIN_YEARS = 14
ROLLING_TEST_YEARS = 1
ROLLING_STEP_YEARS = 1


def _rolling_splits() -> List[Split]:
    """Generate rolling train/test splits to catch PANIC windows (2020, 2008, etc.)."""
    splits: List[Split] = []
    start_year = 2001
    end_year = 2026
    for train_start_y in range(start_year, end_year - ROLLING_TRAIN_YEARS - ROLLING_TEST_YEARS + 1, ROLLING_STEP_YEARS):
        train_end_y = train_start_y + ROLLING_TRAIN_YEARS - 1
        test_start_y = train_end_y + 1
        test_end_y = test_start_y + ROLLING_TEST_YEARS - 1
        if test_end_y > end_year:
            break
        splits.append(Split(
            train_start=f"{train_start_y}-01-02",
            train_end=f"{train_end_y}-12-31",
            test_start=f"{test_start_y}-01-01",
            test_end=f"{test_end_y}-12-31",
        ))
    return splits


def main():
    spy_csv = "data/spy_sample.csv"
    timeline_csv = "validation_outputs/regime_timeline.csv"
    out_dir = "validation_outputs"

    # Allow overriding split from CLI:
    # python scripts/oos_validation.py 2001-01-02 2014-12-31 2015-01-01 2026-02-12
    # python scripts/oos_validation.py --rolling
    if "--rolling" in sys.argv:
        splits = _rolling_splits()
        all_rows: List[Dict[str, object]] = []
        for split in splits:
            out_path = run_oos(spy_csv, timeline_csv, out_dir, split)
            df = pd.read_csv(out_path)
            all_rows.extend(df.to_dict("records"))
        combined = pd.DataFrame(all_rows)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "oos_stat_tests_rolling.csv")
        combined.to_csv(out_path, index=False)
        print("DONE")
        print(f"OOS stats (rolling): {out_path}")
        print(f"SciPy: {SCIPY_OK} (Mann–Whitney p-values {'enabled' if SCIPY_OK else 'disabled'})")
    elif len(sys.argv) == 5:
        split = Split(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
        out_path = run_oos(spy_csv, timeline_csv, out_dir, split)
        print("DONE")
        print(f"OOS stats: {out_path}")
        print(f"SciPy: {SCIPY_OK} (Mann–Whitney p-values {'enabled' if SCIPY_OK else 'disabled'})")
    elif len(sys.argv) == 1:
        split = DEFAULT_SPLIT
        out_path = run_oos(spy_csv, timeline_csv, out_dir, split)
        print("DONE")
        print(f"OOS stats: {out_path}")
        print(f"SciPy: {SCIPY_OK} (Mann–Whitney p-values {'enabled' if SCIPY_OK else 'disabled'})")
    else:
        print("Usage: python scripts/oos_validation.py [--rolling | train_start train_end test_start test_end]")
        sys.exit(2)


if __name__ == "__main__":
    main()
