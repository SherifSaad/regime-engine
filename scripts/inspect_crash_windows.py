#!/usr/bin/env python3
"""
Crash-window inspection: answers the timing question definitively.

For 2020 (COVID), 2008 (GFC), and 2022 (bear), reports:
  - First date regime switched to SHOCK / PANIC_RISK / TRENDING_BEAR
  - (CAPITULATION_REVERSAL in legacy data is treated as PANIC_RISK)
  - Trading days before/after peak and trough when each flag triggered
  - Regime sequence during the crash window

Usage:
  python scripts/inspect_crash_windows.py
  python scripts/inspect_crash_windows.py --rebuild   # regenerate timeline first
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

# -----------------
# CRASH WINDOW DEFINITIONS (known historical dates)
# -----------------
CRASH_WINDOWS = {
    "2020_COVID": {
        "peak": "2020-02-19",   # SPY all-time high before crash
        "trough": "2020-03-23", # SPY intraday low
        "start": "2020-02-01",  # window start
        "end": "2020-04-30",   # window end
    },
    "2008_GFC": {
        "peak": "2007-10-09",   # pre-crash high
        "trough": "2009-03-09", # GFC trough
        "start": "2007-10-01",
        "end": "2009-04-30",
    },
    "2022_BEAR": {
        "peak": "2022-01-04",   # SPY peak before bear
        "trough": "2022-10-13", # bear market low
        "start": "2022-01-01",
        "end": "2022-12-31",
    },
}

# Regimes we care about for crash timing
# CAPITULATION_REVERSAL = legacy name for PANIC_RISK (treat as same for timing)
RISK_REGIMES = ["SHOCK", "PANIC_RISK", "TRENDING_BEAR"]

TIMELINE_PATH = Path("validation_outputs/regime_timeline.csv")
VALIDATE_SCRIPT = Path("scripts/validate_regimes.py")


def load_timeline(rebuild: bool = False) -> pd.DataFrame:
    """Load regime timeline; optionally rebuild via validate_regimes.py."""
    if rebuild or not TIMELINE_PATH.exists():
        print("Building regime timeline (running validate_regimes.py)...")
        result = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            raise RuntimeError("validate_regimes.py failed")
        print("Timeline built.\n")

    df = pd.read_csv(TIMELINE_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df


def trading_days_between(win: pd.DataFrame, d1: str, d2: str) -> int | None:
    """Trading days from d1 to d2 (positive = d2 after d1). Uses window's date column."""
    dates = win["date"].sort_values().reset_index(drop=True)
    d1_dt = pd.Timestamp(d1).normalize()
    d2_dt = pd.Timestamp(d2).normalize()
    # Find nearest dates in the window
    idx1 = (dates <= d1_dt).sum() - 1
    idx2 = (dates <= d2_dt).sum() - 1
    if idx1 < 0 or idx2 < 0:
        return None
    return int(idx2 - idx1)


def inspect_crash_window(
    df: pd.DataFrame,
    name: str,
    config: dict,
) -> dict:
    """Inspect one crash window; return timing summary."""
    start = pd.Timestamp(config["start"])
    end = pd.Timestamp(config["end"])
    peak = pd.Timestamp(config["peak"])
    trough = pd.Timestamp(config["trough"])

    win = df[(df["date"] >= start) & (df["date"] <= end)].copy()
    win = win.sort_values("date").reset_index(drop=True)

    result = {
        "name": name,
        "peak": config["peak"],
        "trough": config["trough"],
        "first_shock": None,
        "first_panic_risk": None,
        "first_trending_bear": None,
        "days_to_trough_from_first_shock": None,
        "days_to_trough_from_first_bear": None,
        "days_from_peak_to_first_risk": None,
        "regime_sequence": [],
    }

    for regime in RISK_REGIMES:
        hits = win[win["regime"] == regime]
        if len(hits) == 0:
            continue
        first_date = hits["date"].iloc[0]
        first_str = pd.Timestamp(first_date).strftime("%Y-%m-%d")
        if regime == "SHOCK":
            result["first_shock"] = first_str
        elif regime == "PANIC_RISK":
            result["first_panic_risk"] = first_str
        elif regime == "TRENDING_BEAR":
            result["first_trending_bear"] = first_str

    # PANIC_RISK: also check legacy CAPITULATION_REVERSAL (same concept)
    for legacy in ["CAPITULATION_REVERSAL"]:
        hits = win[win["regime"] == legacy]
        if len(hits) == 0:
            continue
        first_date = hits["date"].iloc[0]
        first_str = pd.Timestamp(first_date).strftime("%Y-%m-%d")
        if result["first_panic_risk"] is None or first_date < pd.Timestamp(result["first_panic_risk"]):
            result["first_panic_risk"] = first_str

    # Days from first SHOCK to trough
    if result["first_shock"]:
        result["days_to_trough_from_first_shock"] = trading_days_between(
            win, result["first_shock"], config["trough"]
        )
    if result["first_trending_bear"]:
        result["days_to_trough_from_first_bear"] = trading_days_between(
            win, result["first_trending_bear"], config["trough"]
        )

    # Days from peak to first risk regime (earliest of SHOCK, PANIC_RISK, TRENDING_BEAR; CAPITULATION_REVERSAL = legacy PANIC_RISK)
    first_risk_date = None
    for r in ["SHOCK", "PANIC_RISK", "CAPITULATION_REVERSAL", "TRENDING_BEAR"]:
        hits = win[win["regime"] == r]
        if len(hits):
            d = hits["date"].iloc[0]
            if first_risk_date is None or d < first_risk_date:
                first_risk_date = d
    if first_risk_date is not None:
        result["days_from_peak_to_first_risk"] = trading_days_between(
            win, config["peak"], pd.Timestamp(first_risk_date).strftime("%Y-%m-%d")
        )

    # Regime sequence (unique consecutive regimes)
    seq = []
    prev = None
    for _, row in win.iterrows():
        r = row["regime"]
        if r != prev:
            seq.append((row["date"].strftime("%Y-%m-%d"), r))
            prev = r
    result["regime_sequence"] = seq[:20]  # first 20 transitions

    return result


def format_report(results: list[dict]) -> str:
    """Format inspection results as readable report."""
    lines = [
        "=" * 70,
        "CRASH-WINDOW INSPECTION — Timing Question (Definitive)",
        "=" * 70,
        "",
    ]

    for r in results:
        lines.append(f"### {r['name']} ###")
        lines.append(f"  Peak:   {r['peak']}  |  Trough: {r['trough']}")
        lines.append("")
        lines.append("  First regime flags:")
        if r["first_shock"]:
            lines.append(f"    SHOCK:              {r['first_shock']}")
        else:
            lines.append("    SHOCK:              (none in window)")
        if r["first_panic_risk"]:
            lines.append(f"    PANIC_RISK:         {r['first_panic_risk']}")
        else:
            lines.append("    PANIC_RISK:         (none in window)")
        if r["first_trending_bear"]:
            lines.append(f"    TRENDING_BEAR:      {r['first_trending_bear']}")
        lines.append("")
        lines.append("  Lead/lag (trading days):")
        if r["days_from_peak_to_first_risk"] is not None:
            sign = "before" if r["days_from_peak_to_first_risk"] < 0 else "after"
            lines.append(f"    First risk flag: {abs(r['days_from_peak_to_first_risk'])} days {sign} peak")
        if r["days_to_trough_from_first_shock"] is not None:
            lines.append(f"    First SHOCK → trough: {r['days_to_trough_from_first_shock']} days")
        if r["days_to_trough_from_first_bear"] is not None:
            lines.append(f"    First TRENDING_BEAR → trough: {r['days_to_trough_from_first_bear']} days")
        lines.append("")
        lines.append("  Regime sequence (first transitions):")
        for d, reg in r["regime_sequence"][:12]:
            lines.append(f"    {d}  {reg}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Inspect crash windows (2020/2008/2022) — definitive timing"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Run validate_regimes.py first to rebuild regime_timeline.csv",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also write summary to validation_outputs/crash_window_timing.csv",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if not (root / TIMELINE_PATH).exists() and not args.rebuild:
        print("regime_timeline.csv not found. Use --rebuild to generate it.")
        sys.exit(1)

    df = load_timeline(rebuild=args.rebuild)

    # Normalize column name (validate may output "date" or "timestamp")
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

    results = []
    for name, config in CRASH_WINDOWS.items():
        results.append(inspect_crash_window(df, name, config))

    report = format_report(results)
    print(report)

    if args.csv:
        out_path = root / "validation_outputs" / "crash_window_timing.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        summary = pd.DataFrame(
            [
                {
                    "crash": r["name"],
                    "peak": r["peak"],
                    "trough": r["trough"],
                    "first_shock": r["first_shock"],
                    "first_panic_risk": r["first_panic_risk"],
                    "first_trending_bear": r["first_trending_bear"],
                    "days_peak_to_first_risk": r["days_from_peak_to_first_risk"],
                    "days_first_shock_to_trough": r["days_to_trough_from_first_shock"],
                    "days_first_bear_to_trough": r["days_to_trough_from_first_bear"],
                }
            for r in results
        ])
        summary.to_csv(out_path, index=False)
        print(f"Summary written to {out_path}")


if __name__ == "__main__":
    main()
