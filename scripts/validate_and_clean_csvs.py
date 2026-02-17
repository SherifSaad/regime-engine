#!/usr/bin/env python3
"""
Validate and clean *_sample.csv files.
Produces *_clean.csv and data_validation_report.csv.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

# =========================
# CONFIG
# =========================
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INPUT_GLOB = "*_sample.csv"   # your naming pattern
OUTPUT_SUFFIX = "_clean.csv"  # output naming
MIN_ROWS = 500               # sanity: too few rows usually means bad file

# For Yahoo/Investing variations
DATE_COL_CANDIDATES = ["Date", "date"]
OPEN_CANDIDATES = ["Open", "open"]
HIGH_CANDIDATES = ["High", "high"]
LOW_CANDIDATES  = ["Low", "low"]
CLOSE_CANDIDATES = ["Close", "close", "Price", "price"]
ADJ_CLOSE_CANDIDATES = ["Adj Close", "AdjClose", "adj close", "adj_close", "Adj_Close"]
VOLUME_CANDIDATES = ["Volume", "Vol.", "vol", "volume"]

DIVIDEND_TEXT_PAT = re.compile(r"dividend|split", re.IGNORECASE)


def _first_present(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None


def _coerce_numeric(series: pd.Series) -> pd.Series:
    # Remove commas and stray spaces
    s = series.astype(str).str.replace(",", "", regex=False).str.strip()
    # Empty strings -> NaN
    s = s.replace({"": np.nan, "nan": np.nan, "None": np.nan})
    return pd.to_numeric(s, errors="coerce")


def validate_and_clean_file(path: Path) -> dict:
    raw = pd.read_csv(path)
    raw.columns = [c.strip() for c in raw.columns]

    cols = set(raw.columns)

    date_col = _first_present(cols, DATE_COL_CANDIDATES)
    open_col = _first_present(cols, OPEN_CANDIDATES)
    high_col = _first_present(cols, HIGH_CANDIDATES)
    low_col  = _first_present(cols, LOW_CANDIDATES)
    close_col = _first_present(cols, CLOSE_CANDIDATES)
    adj_col = _first_present(cols, ADJ_CLOSE_CANDIDATES)
    vol_col = _first_present(cols, VOLUME_CANDIDATES)

    issues = []
    info = {
        "file": path.name,
        "rows_in": len(raw),
        "rows_out": None,
        "has_adj_close": adj_col is not None,
        "has_volume": vol_col is not None,
        "dividend_rows_removed": 0,
        "duplicate_dates_removed": 0,
        "missing_close_removed": 0,
        "ohlc_sanity_violations": 0,
        "date_gaps_gt_7d": 0,
        "issues": issues,
        "output_file": None,
    }

    # Basic column presence
    missing = [("Date", date_col), ("Open", open_col), ("High", high_col), ("Low", low_col), ("Close/Price", close_col)]
    for label, col in missing:
        if col is None:
            issues.append(f"Missing required column for {label}")

    if issues:
        return info  # can't proceed

    df = raw.copy()

    # Remove dividend/split rows if any text appears in numeric columns
    # Many exports place "Dividend" in Open/High/Low or another numeric column.
    text_mask = pd.Series(False, index=df.index)
    for c in [open_col, high_col, low_col, close_col]:
        text_mask = text_mask | df[c].astype(str).str.contains(DIVIDEND_TEXT_PAT, na=False)

    removed = int(text_mask.sum())
    if removed > 0:
        df = df.loc[~text_mask].copy()
        info["dividend_rows_removed"] = removed

    # Parse date
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).copy()

    # Numeric conversions
    df["Open"] = _coerce_numeric(df[open_col])
    df["High"] = _coerce_numeric(df[high_col])
    df["Low"]  = _coerce_numeric(df[low_col])

    # Choose Close: prefer Adj Close if present (equities/ETFs)
    # Scale OHLC when using Adj Close to preserve consistency
    if adj_col is not None:
        raw_close = _coerce_numeric(df[close_col])
        df["Close"] = _coerce_numeric(df[adj_col])
        scale = df["Close"] / raw_close
        scale = scale.replace([np.inf, -np.inf], np.nan).fillna(1.0)
        df["Open"] = (df["Open"] * scale).astype(float)
        df["High"] = (df["High"] * scale).astype(float)
        df["Low"] = (df["Low"] * scale).astype(float)
        df["High"] = df[["Open", "High", "Close"]].max(axis=1)
        df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)
    else:
        df["Close"] = _coerce_numeric(df[close_col])

    if vol_col is not None:
        df["Volume"] = _coerce_numeric(df[vol_col])
    else:
        df["Volume"] = np.nan

    # Drop rows with missing close
    before = len(df)
    df = df.dropna(subset=["Close"]).copy()
    info["missing_close_removed"] = int(before - len(df))

    # Sort ascending
    df = df.sort_values(date_col).copy()

    # Remove duplicate dates (keep last)
    before = len(df)
    df = df.drop_duplicates(subset=[date_col], keep="last").copy()
    info["duplicate_dates_removed"] = int(before - len(df))

    # OHLC sanity checks (allow NaNs but count violations)
    sanity = pd.Series(True, index=df.index)
    sanity &= df["High"] >= df[["Open", "Close", "Low"]].max(axis=1)
    sanity &= df["Low"]  <= df[["Open", "Close", "High"]].min(axis=1)
    violations = int((~sanity).sum())
    info["ohlc_sanity_violations"] = violations
    if violations > 0:
        issues.append(f"OHLC sanity violations: {violations} rows")

    # Date gaps (rough check)
    dates = df[date_col].values
    if len(dates) >= 2:
        gaps = pd.Series(pd.to_datetime(dates)).diff().dt.days.fillna(0)
        # More than 7 days gap might be missing chunks (not weekends)
        info["date_gaps_gt_7d"] = int((gaps > 7).sum())
        if info["date_gaps_gt_7d"] > 0:
            issues.append(f"Date gaps > 7 days: {info['date_gaps_gt_7d']}")

    # Final shape check
    if len(df) < MIN_ROWS:
        issues.append(f"Too few rows after cleaning: {len(df)} (MIN_ROWS={MIN_ROWS})")

    # Output standardized columns
    out = df[[date_col, "Open", "High", "Low", "Close", "Volume"]].copy()
    out = out.rename(columns={date_col: "Date"})

    # Save
    out_name = path.name.replace("_sample.csv", OUTPUT_SUFFIX)
    out_path = path.parent / out_name
    out.to_csv(out_path, index=False)

    info["rows_out"] = len(out)
    info["output_file"] = out_path.name

    return info


def main():
    folder = DATA_DIR
    files = sorted(folder.glob(INPUT_GLOB))
    if not files:
        print(f"No files found matching: {INPUT_GLOB} in {folder}")
        return

    results = []
    for f in files:
        info = validate_and_clean_file(f)
        results.append(info)

    report = pd.DataFrame(results)

    # Save report
    report_path = folder / "data_validation_report.csv"
    report.to_csv(report_path, index=False)

    # Print compact summary
    print("\n=== DATA VALIDATION SUMMARY ===")
    print(report[[
        "file", "rows_in", "rows_out", "has_adj_close", "has_volume",
        "dividend_rows_removed", "duplicate_dates_removed", "missing_close_removed",
        "ohlc_sanity_violations", "date_gaps_gt_7d", "output_file"
    ]].to_string(index=False))

    # Print issues (if any)
    any_issues = report["issues"].astype(str).str.len().gt(2).any()
    if any_issues:
        print("\n=== FILES WITH ISSUES ===")
        for _, row in report.iterrows():
            if row["issues"]:
                print(f"- {row['file']}: {row['issues']}")
    print(f"\nSaved: {report_path}")


if __name__ == "__main__":
    main()
