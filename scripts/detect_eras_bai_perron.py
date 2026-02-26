#!/usr/bin/env python3
"""
Bai–Perron era detection on log(126-day RV). Asset-class specific.
Derives breakpoints from canonical benchmark per asset class.
Outputs: era boundary table, JSON params, BIC table, plot, frozen metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Asset class → canonical benchmark (frozen; spec-aligned)
ASSET_CLASS_BENCHMARK = {
    "EQUITIES_US": "SPY",
    "CREDIT_HY": "HYG",
    "CREDIT_IG": "LQD",
    "RATES_LONG": "TLT",
    "RATES_INTERMEDIATE": "IEF",
    "FX_USD_PROXY": "EURUSD",
    "FX_MAJORS": "EURUSD",
    "COMMODITIES_ENERGY": "WTIUSD",
    "COMMODITIES_METALS": "XAUUSD",
    "CRYPTO": "BTCUSD",
}

# Frozen constants (must match era_detection.py)
EPSILON = 1e-12
RV_WINDOW = 126
MIN_SEGMENT = 504

OUT_DIR = ROOT / "data" / "era_metadata"
DATA_DIR = ROOT / "data"
# CSV fallback when Parquet unavailable (Parquet preferred via BarsProvider)
ASSET_FILES = {
    "SPY": "spy_clean.csv",
    "QQQ": "qqq_clean.csv",
    "BTCUSD": "btcusd_clean.csv",
    "XAUUSD": "xauusd_clean.csv",
    "HYG": "hyg_clean.csv",
    "LQD": "lqd_clean.csv",
    "TLT": "tlt_clean.csv",
    "IEF": "ief_clean.csv",
    "EURUSD": "eurusd_clean.csv",
    "WTIUSD": "wtiusd_clean.csv",
}


def load_bars_parquet(symbol: str, tf: str = "1day") -> pd.DataFrame:
    """Load bars from Parquet via BarsProvider."""
    from core.providers.bars_provider import BarsProvider

    lf = BarsProvider.get_bars(symbol, tf)
    pl_df = lf.sort("ts").collect()
    if pl_df.is_empty():
        return pd.DataFrame()
    df = pd.DataFrame({c: pl_df[c].to_numpy() for c in pl_df.columns})
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    df["adj_close"] = df["close"]
    return df


def load_bars_csv(symbol: str) -> pd.DataFrame:
    """Load bars from clean CSV (fallback)."""
    sym = symbol.upper()
    if sym not in ASSET_FILES:
        return pd.DataFrame()
    path = DATA_DIR / ASSET_FILES[sym]
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    col_map = {"Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    if "Adj Close" in df.columns:
        col_map["Adj Close"] = "adj_close"
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    if "date" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    return df[["open", "high", "low", "close", "adj_close", "volume"]]


def load_bars(symbol: str) -> pd.DataFrame:
    """Load bars: Parquet first, then CSV fallback."""
    df = load_bars_parquet(symbol)
    if df.empty or len(df) < 2 * MIN_SEGMENT:
        df = load_bars_csv(symbol)
    return df


def data_hash(df: pd.DataFrame) -> str:
    """SHA256 of close series for reproducibility."""
    close_str = df["adj_close"].dropna().astype(str).str.cat(sep=",")
    return hashlib.sha256(close_str.encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description="Bai-Perron era detection per asset class")
    ap.add_argument("--asset-class", help="Single asset class (default: all)")
    ap.add_argument("--out-dir", default=str(OUT_DIR), help="Output directory")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    classes = [args.asset_class] if args.asset_class else list(ASSET_CLASS_BENCHMARK.keys())
    all_eras = []
    all_metadata = {}

    for ac in classes:
        bench = ASSET_CLASS_BENCHMARK.get(ac)
        if not bench:
            print(f"  Skip {ac}: no benchmark")
            continue

        df = load_bars(bench)
        if df.empty or len(df) < 2 * MIN_SEGMENT:
            print(f"  Skip {ac}: insufficient data for {bench} ({len(df) if not df.empty else 0} bars)")
            continue

        close = df["adj_close"]
        dh = data_hash(df)

        from regime_engine.era_detection import run_era_detection

        result = run_era_detection(close, min_segment=MIN_SEGMENT, data_hash=dh)

        dates = result.dates
        breaks = result.break_indices

        # Era boundaries: [start, end) per era
        boundaries = []
        prev = 0
        for b in breaks:
            boundaries.append((dates[prev].isoformat()[:10], dates[b - 1].isoformat()[:10]))
            prev = b
        boundaries.append((dates[prev].isoformat()[:10], dates[-1].isoformat()[:10]))

        # Era boundary table
        era_rows = []
        for i, (start, end) in enumerate(boundaries):
            era_rows.append({
                "asset_class": ac,
                "benchmark": bench,
                "era_index": i,
                "start_date": start,
                "end_date": end,
            })
            all_eras.append(era_rows[-1])

        # JSON: params + break indices
        params = {
            "epsilon": EPSILON,
            "rv_window": RV_WINDOW,
            "min_segment": MIN_SEGMENT,
            "asset_class": ac,
            "benchmark": bench,
            "break_indices": [int(b) for b in breaks],
            "break_dates": [dates[int(b)].isoformat()[:10] for b in breaks],
            "n_eras": len(boundaries),
            "data_hash": dh,
        }
        json_path = out_dir / f"eras_{ac.replace(' ', '_')}.json"
        json_path.write_text(json.dumps(params, indent=2) + "\n")

        # BIC comparison table
        bic_rows = [{"k_breaks": int(k), "bic": float(v)} for k, v in sorted(result.bic_by_k.items())]
        bic_df = pd.DataFrame(bic_rows)
        bic_path = out_dir / f"bic_{ac.replace(' ', '_')}.csv"
        bic_df.to_csv(bic_path, index=False)

        # Metadata (frozen)
        meta = {
            "asset_class": ac,
            "benchmark": bench,
            "data_hash": dh,
            "epsilon": EPSILON,
            "rv_window": RV_WINDOW,
            "min_segment": MIN_SEGMENT,
            "break_model": "mean_only",
            "n_breaks": len(breaks),
            "n_eras": len(boundaries),
        }
        all_metadata[ac] = meta

        # Plot (requires: pip install matplotlib)
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(12, 5))
            ax.plot(dates, result.log_rv, color="steelblue", alpha=0.8, label="log(RV_126)")
            for b in breaks:
                ax.axvline(dates[int(b)], color="red", linestyle="--", alpha=0.7)
            ax.set_xlabel("Date")
            ax.set_ylabel("log(RV_126 + ε)")
            ax.set_title(f"Bai-Perron breaks: {ac} ({bench})")
            ax.legend()
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            plot_path = out_dir / f"eras_{ac.replace(' ', '_')}.png"
            fig.savefig(plot_path, dpi=150)
            plt.close()
            print(f"    plot -> {plot_path.name}")
        except ImportError:
            print(f"    (install matplotlib for plot: pip install matplotlib)")

        print(f"  {ac} ({bench}): {len(breaks)} breaks, {len(boundaries)} eras -> {json_path.name}")

    # Era boundary table (combined)
    era_df = pd.DataFrame(all_eras)
    if not era_df.empty:
        era_df.to_csv(out_dir / "era_boundaries.csv", index=False)

    # Frozen metadata with data hash
    freeze = {
        "epsilon": EPSILON,
        "rv_window": RV_WINDOW,
        "min_segment": MIN_SEGMENT,
        "break_model": "mean_only",
        "asset_classes": all_metadata,
    }
    (out_dir / "era_metadata_frozen.json").write_text(json.dumps(freeze, indent=2) + "\n")

    print(f"\nOutputs: {out_dir}")
    print(f"  era_boundaries.csv, era_metadata_frozen.json")
    for ac in classes:
        if ac in all_metadata:
            print(f"  eras_{ac.replace(' ', '_')}.json, bic_{ac.replace(' ', '_')}.csv")


if __name__ == "__main__":
    main()
