#!/usr/bin/env python3
"""
Run rolling OOS tail validation by bucket.
Requires: regime + escalation_v2 + close for full history.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from regime_engine.escalation_buckets import compute_bucket_from_percentile
from regime_engine.escalation_v2 import expanding_percentile_transform
from regime_engine.hysteresis import hysteresis_high_state, bucket_from_high_state

# Import from validate_regimes (same data loading)
from validate_regimes import load_csv, add_forward_returns, run_engine_over_history

# Import OOS validation
from oos_tail_validation import rolling_oos_tail_report


def main() -> int:
    print("Loading data and running engine over history (this may take a few minutes)...")
    df = load_csv()
    df = add_forward_returns(df)
    df = run_engine_over_history(df, symbol="BTCUSD")

    # Drop rows with NaN escalation_v2 (first 31 bars)
    valid = df["escalation_v2"].notna()
    sub = df.loc[valid].copy()

    # Percentile transform (expanding, min 252 bars)
    esc_v2_pct = expanding_percentile_transform(
        pd.Series(sub["escalation_v2"].values, index=sub.index),
        min_bars=252,
    )
    sub["escalation_v2_pct"] = esc_v2_pct

    # Drop rows where percentile is NaN (first 252 of sub)
    valid_pct = sub["escalation_v2_pct"].notna()
    sub = sub.loc[valid_pct].copy()

    dates = sub.index
    if dates.tz is not None:
        dates = dates.tz_localize(None)

    # Hysteresis bucket: enter >= 90%, exit <= 75% (same as capital allocation)
    is_high = hysteresis_high_state(
        pd.Series(sub["escalation_v2_pct"].values, index=sub.index),
        enter=0.90,
        exit=0.75,
    )
    bucket_series = bucket_from_high_state(is_high, default_bucket="LOW")
    bucket_list = bucket_series.tolist()
    _idx = [0]

    def bucket_func(r, e):
        b = bucket_list[_idx[0]] if _idx[0] < len(bucket_list) else "LOW"
        _idx[0] += 1
        return (b, "HOLD", {})

    report = rolling_oos_tail_report(
        dates=pd.Series(dates),
        close=sub["adj_close"].reset_index(drop=True),
        regime=sub["regime"].reset_index(drop=True),
        escalation_v2=sub["escalation_v2_pct"].reset_index(drop=True),
        bucket_func=bucket_func,
        start_train_years=10,
        test_years=5,
        step_months=6,
        horizon=20,
        tail_level=-0.10,
    )

    print("\n=== ROLLING OOS TAIL REPORT (first 30 rows) ===")
    print(report.head(30).to_string(index=False))

    if len(report) == 0 or "train_start" not in report.columns:
        print("\n=== INSUFFICIENT DATA FOR OOS VALIDATION ===")
        print("Need at least 15 years of data (10 train + 5 test). Skipping stability metric.")
        return 0

    print("\n=== WINDOW-LEVEL SEPARATION SUMMARY ===")
    sep = (
        report.drop_duplicates(["train_start", "train_end", "test_start", "test_end"])[
            ["train_start", "test_start", "tail_sep_high_minus_low"]
        ].dropna()
    )
    print(sep.head(20).to_string(index=False))
    print("\nSeparation stats:")
    print(sep["tail_sep_high_minus_low"].describe().to_string())

    positive_sep_ratio = (sep["tail_sep_high_minus_low"] > 0).mean()
    print("\n=== STABILITY METRIC ===")
    print("Percent of windows where HIGH hazard > LOW hazard:", round(float(positive_sep_ratio), 4))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
