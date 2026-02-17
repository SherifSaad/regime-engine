#!/usr/bin/env python3
"""
Regime -> Forward Return Validation (SPY)

Inputs:
- validation_outputs/regime_timeline.csv  (full-history regime labels)
- Yahoo SPY daily CSV in ./data/ (must include 'Date' and 'Adj Close')

Outputs:
- validation_outputs/spy_regime_daily_forward.csv
- validation_outputs/spy_regime_forward_summary.csv
"""

from __future__ import annotations

import os
import sys
import glob
import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "validation_outputs")

REGIME_TIMELINE_CANDIDATES = [
    os.path.join(OUT_DIR, "regime_timeline.csv"),
    os.path.join(OUT_DIR, "spy_regime_annotated.csv"),
]


def _find_regime_timeline() -> str:
    for p in REGIME_TIMELINE_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "Could not find a regime timeline file. Expected one of:\n"
        + "\n".join(f"  - {p}" for p in REGIME_TIMELINE_CANDIDATES)
    )


def _find_spy_csv() -> str:
    # Prefer obvious names; fallback to any CSV that contains 'SPY'
    patterns = [
        os.path.join(DATA_DIR, "*SPY*.csv"),
        os.path.join(DATA_DIR, "*spy*.csv"),
        os.path.join(DATA_DIR, "*.csv"),
    ]
    candidates = []
    for pat in patterns:
        candidates.extend(glob.glob(pat))
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for c in candidates:
        if c not in seen:
            uniq.append(c)
            seen.add(c)

    def looks_like_yahoo(df: pd.DataFrame) -> bool:
        cols = {c.strip().lower() for c in df.columns}
        return ("date" in cols) and ("adj close" in cols or "adj_close" in cols or "adjclose" in cols)

    for path in uniq:
        try:
            df = pd.read_csv(path, nrows=5)
        except Exception:
            continue
        if looks_like_yahoo(df):
            # If file contains SPY in name, take it immediately
            base = os.path.basename(path).lower()
            if "spy" in base:
                return path

    # If none contained 'spy' in name but one looked like Yahoo format, take first one
    for path in uniq:
        try:
            df = pd.read_csv(path, nrows=5)
        except Exception:
            continue
        cols = {c.strip().lower() for c in df.columns}
        if ("date" in cols) and ("adj close" in cols or "adj_close" in cols or "adjclose" in cols):
            return path

    # Hard fail with directory listing
    listing = "\n".join(f"  - {os.path.join('data', os.path.basename(p))}" for p in sorted(glob.glob(os.path.join(DATA_DIR, '*'))))
    raise FileNotFoundError(
        "Could not find a Yahoo-style SPY CSV in ./data with columns ['Date', 'Adj Close'].\n"
        "Files currently in ./data:\n" + (listing if listing else "  (no files found)")
    )


def _normalize_date(series: pd.Series) -> pd.Series:
    # Accept "YYYY-MM-DD", or timestamp like "2020-03-09 00:00:00+00:00"
    dt = pd.to_datetime(series, errors="coerce", utc=True)
    # Convert to date (no tz)
    return dt.dt.tz_convert(None).dt.normalize()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    regime_path = _find_regime_timeline()
    spy_path = _find_spy_csv()

    regimes = pd.read_csv(regime_path)
    if "date" not in [c.lower() for c in regimes.columns]:
        raise ValueError(f"{regime_path} must contain a 'date' column. Columns: {list(regimes.columns)}")

    # Normalize regime date + pick key cols
    # Determine actual date col name
    date_col = [c for c in regimes.columns if c.lower() == "date"][0]
    regimes["date"] = _normalize_date(regimes[date_col])

    # Determine label col
    label_candidates = [c for c in regimes.columns if c.lower() in ("regime", "regime_label", "label")]
    if not label_candidates:
        raise ValueError(f"{regime_path} must contain a regime label column (regime/regime_label/label). Columns: {list(regimes.columns)}")
    label_col = label_candidates[0]

    keep_cols = ["date", label_col]
    for optional in ["confidence", "instability_index", "downside_shock_risk", "risk_level", "vrs", "market_bias", "structural_score"]:
        if optional in regimes.columns:
            keep_cols.append(optional)

    regimes = regimes[keep_cols].dropna(subset=["date"]).drop_duplicates(subset=["date"]).sort_values("date")

    # Load SPY yahoo csv
    spy = pd.read_csv(spy_path)
    # Normalize column names
    # Find Date col
    if "Date" in spy.columns:
        spy_date_col = "Date"
    else:
        # fallback case-insensitive
        matches = [c for c in spy.columns if c.strip().lower() == "date"]
        if not matches:
            raise ValueError(f"{spy_path} must contain a 'Date' column. Columns: {list(spy.columns)}")
        spy_date_col = matches[0]

    # Find Adj Close col
    adj_candidates = [c for c in spy.columns if c.strip().lower() in ("adj close", "adj_close", "adjclose")]
    if not adj_candidates:
        raise ValueError(f"{spy_path} must contain an 'Adj Close' column. Columns: {list(spy.columns)}")
    adj_col = adj_candidates[0]

    spy["date"] = pd.to_datetime(spy[spy_date_col], errors="coerce").dt.normalize()
    spy["adj_close"] = pd.to_numeric(spy[adj_col], errors="coerce")

    spy = spy.dropna(subset=["date", "adj_close"]).sort_values("date")

    # Compute forward returns
    for h in (5, 10, 20):
        spy[f"fwd_{h}d_ret"] = spy["adj_close"].shift(-h) / spy["adj_close"] - 1.0

    # Merge regimes with price/returns
    df = regimes.merge(spy[["date", "adj_close", "fwd_5d_ret", "fwd_10d_ret", "fwd_20d_ret"]], on="date", how="inner")

    # Daily output
    daily_out = os.path.join(OUT_DIR, "spy_regime_daily_forward.csv")
    df.to_csv(daily_out, index=False)

    # Summary by regime
    label = label_col  # preserve exact name
    summary_rows = []
    for regime_name, g in df.groupby(label):
        row = {"regime": regime_name, "n": int(g.shape[0])}
        for h in (5, 10, 20):
            x = g[f"fwd_{h}d_ret"].dropna()
            if x.empty:
                continue
            row.update({
                f"mean_{h}d": float(x.mean()),
                f"median_{h}d": float(x.median()),
                f"std_{h}d": float(x.std(ddof=1)) if x.shape[0] > 1 else 0.0,
                f"p05_{h}d": float(x.quantile(0.05)),
                f"p25_{h}d": float(x.quantile(0.25)),
                f"p75_{h}d": float(x.quantile(0.75)),
                f"p95_{h}d": float(x.quantile(0.95)),
                f"neg_rate_{h}d": float((x < 0).mean()),
                f"tail_le_-3pct_{h}d": float((x <= -0.03).mean()),
                f"tail_le_-5pct_{h}d": float((x <= -0.05).mean()),
                f"min_{h}d": float(x.min()),
                f"max_{h}d": float(x.max()),
            })
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows).sort_values("regime")
    summary_out = os.path.join(OUT_DIR, "spy_regime_forward_summary.csv")
    summary.to_csv(summary_out, index=False)

    print("DONE")
    print(f"Regime timeline: {os.path.relpath(regime_path, ROOT)}")
    print(f"SPY price csv:   {os.path.relpath(spy_path, ROOT)}")
    print(f"Daily output:    {os.path.relpath(daily_out, ROOT)}")
    print(f"Summary output:  {os.path.relpath(summary_out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
