import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.validate_regimes import run_engine_over_history


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "spy_clean.csv"
OUT_PATH = ROOT / "validation_outputs" / "golden_master_SPY_lastday.json"


def load_spy() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)

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

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    # Deterministic fallback if Adj Close not present
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    df = df[["open", "high", "low", "close", "adj_close", "volume"]].copy()
    return df


def safe_float(x):
    if x is None:
        return None
    if isinstance(x, (float, int)):
        if np.isnan(x):
            return None
        return float(x)
    try:
        x = float(x)
        if np.isnan(x):
            return None
        return x
    except Exception:
        return None


def fingerprint_df(df: pd.DataFrame) -> str:
    """
    Stable fingerprint of the exact input slice used for the golden master.
    Includes index + all required columns in a fixed CSV representation.
    """
    # Fixed formatting for stability
    csv_bytes = df.to_csv(
        index=True,
        date_format="%Y-%m-%d",
        float_format="%.10f",
        lineterminator="\n",
    ).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def fingerprint_env() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }


def main():
    df = load_spy()

    # Use a fixed window slice for stability and speed
    df = df.iloc[-1500:].copy()

    data_hash = fingerprint_df(df)
    env = fingerprint_env()

    out = run_engine_over_history(df, symbol="SPY")
    last = out.iloc[-1]

    payload = {
        "asof": str(out.index[-1].date()),
        "symbol": "SPY",
        "env": env,
        "data_sha256": data_hash,
        "regime": str(last["regime"]),
        "confidence": safe_float(last["confidence"]),
        "conviction": str(last["conviction"]),
        "iix": safe_float(last["iix"]),
        "dsr": safe_float(last["dsr"]),
        "vrs": safe_float(last["vrs"]),
        "lq": safe_float(last["lq"]),
        "risk_level": safe_float(last["risk_level"]),
        "structural_score": safe_float(last["structural_score"]),
        "market_bias": safe_float(last["market_bias"]),
        "escalation_v2": safe_float(last["escalation_v2"]),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote: {OUT_PATH}")


if __name__ == "__main__":
    main()
