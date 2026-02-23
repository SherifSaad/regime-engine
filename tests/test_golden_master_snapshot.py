import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.validate_regimes import run_engine_over_history


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "spy_clean.csv"
GOLDEN_PATH = ROOT / "validation_outputs" / "golden_master_SPY_lastday.json"


def load_spy():
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

    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    return df[["open", "high", "low", "close", "adj_close", "volume"]].iloc[-1500:].copy()


def safe_float(x):
    try:
        x = float(x)
        if np.isnan(x):
            return None
        return x
    except Exception:
        return None


def fingerprint_df(df: pd.DataFrame) -> str:
    csv_bytes = df.to_csv(
        index=True,
        date_format="%Y-%m-%d",
        float_format="%.10f",
        lineterminator="\n",
    ).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def fingerprint_env():
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }


@pytest.mark.slow
def test_golden_master_lastday_snapshot():
    assert GOLDEN_PATH.exists(), "Golden snapshot file missing"

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    df = load_spy()
    data_hash = fingerprint_df(df)
    env = fingerprint_env()

    # Validate environment + data first
    assert golden["data_sha256"] == data_hash
    assert golden["env"]["python"] == env["python"]
    assert golden["env"]["numpy"] == env["numpy"]
    assert golden["env"]["pandas"] == env["pandas"]

    out = run_engine_over_history(df, symbol="SPY")
    last = out.iloc[-1]

    current = {
        "asof": str(out.index[-1].date()),
        "symbol": "SPY",
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

    # Compare only engine outputs (env + hash already checked)
    for k, v in current.items():
        assert golden[k] == v, f"Mismatch in field '{k}': expected {golden[k]}, got {v}"
