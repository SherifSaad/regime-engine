import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from regime_engine.cli import compute_market_state_from_df
from scripts.validate_regimes import run_engine_over_history


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "validation_outputs"


ASSET_FILES = {
    "SPY": "spy_clean.csv",
    "QQQ": "qqq_clean.csv",
    "NVDA": "nvda_clean.csv",
    "BTCUSD": "btcusd_clean.csv",
    "XAUUSD": "xauusd_clean.csv",
}


def fingerprint_env() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }


def fingerprint_df(df: pd.DataFrame) -> str:
    csv_bytes = df.to_csv(
        index=True,
        date_format="%Y-%m-%d",
        float_format="%.10f",
        lineterminator="\n",
    ).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def load_clean_csv(symbol: str) -> pd.DataFrame:
    sym = symbol.upper()
    if sym not in ASSET_FILES:
        raise SystemExit(f"Unknown symbol '{symbol}'. Use one of: {sorted(ASSET_FILES)}")

    path = DATA_DIR / ASSET_FILES[sym]
    if not path.exists():
        raise SystemExit(f"Missing file: {path}")

    df = pd.read_csv(path)

    # Yahoo-style normalization
    df = df.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )

    if "date" not in df.columns:
        raise SystemExit(f"{path.name} missing Date/date column")

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    # Deterministic fallback
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    # Volume may not exist for some datasets; deterministic fallback to 0
    if "volume" not in df.columns:
        df["volume"] = 0.0

    required = ["open", "high", "low", "close", "adj_close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"{path.name} missing columns: {missing}")

    return df[required].copy()


def main():
    p = argparse.ArgumentParser(description="Build deterministic release audit bundle for a symbol")
    p.add_argument("--symbol", required=True, help="SPY, QQQ, NVDA, BTCUSD, XAUUSD")
    p.add_argument("--bars", type=int, default=1500, help="How many most-recent bars to use")
    p.add_argument("--version", default="v1", help="Release version label (v1, v2, etc.)")
    p.add_argument("--include-escalation-v2", action="store_true")
    args = p.parse_args()

    symbol = args.symbol.upper()
    df_full = load_clean_csv(symbol)

    bars = int(args.bars)
    if bars <= 300:
        raise SystemExit("--bars must be > 300")

    df = df_full.iloc[-bars:].copy()

    env = fingerprint_env()
    data_hash = fingerprint_df(df)

    # --- versioned release folder ---
    run_date = pd.Timestamp.utcnow().strftime("%Y%m%d")
    release_dir = (
        OUT_DIR
        / symbol
        / f"release-audit-{run_date}-{args.version}"
    )
    release_dir.mkdir(parents=True, exist_ok=True)

    # Get git commit (if available)
    try:
        import subprocess
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        git_hash = "unknown"

    # 1) Latest state
    latest_state = compute_market_state_from_df(
        df,
        symbol,
        diagnostics=False,
        include_escalation_v2=bool(args.include_escalation_v2),
    )

    latest_payload = {
        "symbol": symbol,
        "asof": latest_state.get("asof"),
        "env": env,
        "data_sha256": data_hash,
        "git_commit": git_hash,
        "latest_state": latest_state,
    }

    (release_dir / "latest_state.json").write_text(
        json.dumps(latest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # 2) Full history
    hist = run_engine_over_history(df, symbol=symbol)
    hist.to_csv(release_dir / "full_history.csv", index=True)

    # 3) Metadata
    metadata = {
        "symbol": symbol,
        "bars": bars,
        "asof": str(df.index[-1].date()),
        "env": env,
        "data_sha256": data_hash,
        "git_commit": git_hash,
        "files": {
            "latest_state": "latest_state.json",
            "full_history": "full_history.csv",
        },
    }

    (release_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Built RELEASE audit bundle: {release_dir}")


if __name__ == "__main__":
    main()
