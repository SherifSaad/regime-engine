#!/usr/bin/env python3
"""
Step 5 — Crisis Concentration / Subperiod Robustness
Re-run the Step 4 event-driven non-overlap lift test after:
- Excluding top X% worst drawdown bars (default 5%)
- Excluding crisis years (2008, 2020) explicitly
- Subperiod splits (equal-time buckets)

Outputs:
- validation_outputs/step5_crisis_concentration_summary.csv
- validation_outputs/step5_crisis_concentration_summary.json

This script tries to auto-detect the Step 4 episode file and the 4h price file.
If detection fails, set EPISODES_PATH and PRICES_PATH below.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# =========================
# USER-OVERRIDES (only if auto-detect fails)
# =========================
EPISODES_PATH: Optional[str] = "/Users/sherifsaad/Documents/regime-engine/validation_outputs/step4_event_driven_episodes.csv"
PRICES_PATH: Optional[str] = None

# Drawdown definition
DD_LOOKBACK_BARS = 200          # rolling peak lookback on 4h bars (tunable, but keep fixed for audit)
EXCLUDE_DD_TOP_PCT = 0.05       # exclude worst 5% drawdown bars

# Bootstrap
BOOTSTRAP_N = 500
RNG_SEED = 42

# Expected forward horizon from validation
DEFAULT_H = 20

# Where your project lives
PROJECT_DIR = Path("/Users/sherifsaad/Documents/regime-engine")
VALIDATION_DIR = PROJECT_DIR / "validation_outputs"
# Same DB as Step 4 (SPY 4h bars for drawdown)
DB_PATH = PROJECT_DIR / "data" / "regime_cache_SPY_escalation_frozen_2026-02-19.db"


# =========================
# Helpers
# =========================
def _safe_read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # normalize datetime column
    for c in ["ts", "timestamp", "datetime", "date", "time"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=False, errors="coerce")
            df = df.rename(columns={c: "ts"})
            break
    if "ts" not in df.columns:
        raise ValueError(f"No recognizable timestamp column in {path.name}. Found columns: {list(df.columns)}")
    df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    return df


def _auto_detect_episodes_file() -> Path:
    """
    Try to find the Step 4 event-driven episode sample file.
    We look for likely filenames in validation_outputs.
    """
    candidates = []
    patterns = [
        "*event*driven*episode*.csv",
        "*nonoverlap*episode*.csv",
        "*episode*nonoverlap*.csv",
        "*warning_precision*.csv",          # sometimes used, but not ideal
        "*event*driven*.csv",
        "*nonoverlap*.csv",
    ]
    for pat in patterns:
        candidates.extend(list(VALIDATION_DIR.glob(pat)))

    # Filter: prefer files that contain BOTH high/low episode info
    scored: List[Tuple[int, Path]] = []
    for p in sorted(set(candidates)):
        try:
            df = _safe_read_csv(p)
        except Exception:
            continue

        cols = set(df.columns.str.lower())
        score = 0
        # key signals for episodes
        if any(k in cols for k in ["episode_id", "ep_id", "episode"]):
            score += 5
        if any(k in cols for k in ["label", "bucket", "group"]):
            score += 3
        if any(k in cols for k in ["is_high", "is_low", "high", "low"]):
            score += 2
        if any(k in cols for k in ["esc_pctl", "escalation", "esc"]):
            score += 2
        if any(k in cols for k in ["event", "is_event", "hit"]):
            score += 2
        # discourage giant raw merged files if present
        if df.shape[0] > 2_000_000:
            score -= 10

        scored.append((score, p))

    if not scored:
        raise FileNotFoundError(
            f"Could not auto-detect an episodes CSV in {VALIDATION_DIR}. "
            f"Set EPISODES_PATH manually."
        )

    scored.sort(key=lambda x: (x[0], x[1].stat().st_mtime), reverse=True)
    best = scored[0][1]
    return best


def _auto_detect_prices_file() -> Path:
    """
    Try to find a 4h OHLCV file for SPY.
    Common possibilities:
    - PROJECT_DIR/data/*.csv
    - PROJECT_DIR/*.csv
    - validation_outputs might also contain merged bars
    """
    candidates = []
    patterns = [
        "data/*SPY*4h*.csv",
        "data/*spy*4h*.csv",
        "data/*SPY*.csv",
        "*SPY*4h*.csv",
        "*spy*4h*.csv",
    ]
    for pat in patterns:
        candidates.extend(list(PROJECT_DIR.glob(pat)))
    # Also check validation dir
    for pat in ["*SPY*4h*.csv", "*spy*4h*.csv", "*bars*.csv"]:
        candidates.extend(list(VALIDATION_DIR.glob(pat)))

    candidates = [p for p in set(candidates) if p.is_file()]

    # Score candidates by presence of OHLC columns
    scored = []
    for p in candidates:
        try:
            df = _safe_read_csv(p)
        except Exception:
            continue
        cols = set(df.columns.str.lower())
        score = 0
        if "close" in cols:
            score += 5
        if "open" in cols:
            score += 2
        if "high" in cols:
            score += 2
        if "low" in cols:
            score += 2
        if "adj close" in cols or "adj_close" in cols:
            score += 1
        scored.append((score, p))

    if not scored:
        raise FileNotFoundError(
            f"Could not auto-detect a SPY 4h price CSV under {PROJECT_DIR} or {VALIDATION_DIR}. "
            f"Set PRICES_PATH manually."
        )

    scored.sort(key=lambda x: (x[0], x[1].stat().st_mtime), reverse=True)
    best = scored[0][1]
    return best


def _load_prices_from_db() -> pd.DataFrame:
    """
    Fallback: load SPY 4h bars from the same DB used by Step 4.
    Returns DataFrame with ts, close (compatible with _prepare_prices).
    """
    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"DB not found: {DB_PATH}. Set PRICES_PATH to a SPY 4h CSV manually."
        )
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT ts, close FROM bars WHERE symbol='SPY' AND timeframe='4h'",
        con,
    )
    con.close()
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["ts", "close"]).sort_values("ts").reset_index(drop=True)
    return df


def _wilson_ci(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _bootstrap_diff(p_hi: np.ndarray, p_lo: np.ndarray, n: int, seed: int) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    if len(p_hi) == 0 or len(p_lo) == 0:
        return {"mean": np.nan, "p05": np.nan, "p95": np.nan}
    diffs = []
    for _ in range(n):
        hi = rng.choice(p_hi, size=len(p_hi), replace=True)
        lo = rng.choice(p_lo, size=len(p_lo), replace=True)
        diffs.append(float(np.mean(hi) - np.mean(lo)))
    diffs = np.array(diffs, dtype=float)
    return {
        "mean": float(np.mean(diffs)),
        "p05": float(np.quantile(diffs, 0.05)),
        "p95": float(np.quantile(diffs, 0.95)),
    }


@dataclass
class LiftResult:
    test_name: str
    n_hi: int
    n_lo: int
    hi_rate: float
    lo_rate: float
    diff: float
    ratio: float
    hi_wilson_lo: float
    hi_wilson_hi: float
    lo_wilson_lo: float
    lo_wilson_hi: float
    boot_mean: float
    boot_p05: float
    boot_p95: float


def _standardize_episodes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Try to map arbitrary Step-4 episode CSV columns into a standard schema:
      ts (episode anchor time)
      group in {"HIGH","LOW"}
      event in {0,1}
      H (horizon, optional)
    """
    cols = {c.lower(): c for c in df.columns}

    out = df.copy()

    # ts already normalized by _safe_read_csv
    # group / label
    if "group" not in out.columns:
        for k in ["label", "bucket", "state", "tier"]:
            if k in cols:
                out["group"] = out[cols[k]]
                break
    if "group" not in out.columns:
        # try boolean flags
        if "is_high" in cols:
            out["group"] = np.where(out[cols["is_high"]].astype(int) == 1, "HIGH", "LOW")
        elif "high" in cols and "low" in cols:
            out["group"] = np.where(out[cols["high"]].astype(int) == 1, "HIGH", "LOW")
        else:
            raise ValueError(
                "Could not infer episode group column (HIGH/LOW). "
                "Expected a column like group/label/bucket or is_high."
            )

    out["group"] = out["group"].astype(str).str.upper()
    out = out[out["group"].isin(["HIGH", "LOW"])].copy()

    # event / hit
    if "event" not in out.columns:
        for k in ["is_event", "hit", "flag", "target_event"]:
            if k in cols:
                out["event"] = out[cols[k]]
                break
    if "event" not in out.columns:
        raise ValueError(
            "Could not infer event column. Expected event/is_event/hit/etc."
        )

    out["event"] = pd.to_numeric(out["event"], errors="coerce").fillna(0).astype(int)
    out["event"] = (out["event"] != 0).astype(int)

    # horizon H
    if "h" not in out.columns:
        for k in ["horizon", "H", "h_bars", "forward_h"]:
            if k.lower() in cols:
                out["H"] = pd.to_numeric(out[cols[k.lower()]], errors="coerce")
                break
    if "H" not in out.columns:
        out["H"] = DEFAULT_H

    out = out.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    return out[["ts", "group", "event", "H"]]


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower(): c for c in prices.columns}
    # choose price series for drawdown: adj_close if available, else close
    if "adj_close" in cols:
        px = prices[cols["adj_close"]]
    elif "adj close" in cols:
        px = prices[cols["adj close"]]
    elif "close" in cols:
        px = prices[cols["close"]]
    else:
        raise ValueError("Prices file missing Close/Adj Close column.")

    out = prices[["ts"]].copy()
    out["px"] = pd.to_numeric(px, errors="coerce")
    out = out.dropna(subset=["ts", "px"]).sort_values("ts").reset_index(drop=True)

    # rolling drawdown: dd = px / rolling_max(px) - 1
    roll_max = out["px"].rolling(DD_LOOKBACK_BARS, min_periods=max(10, DD_LOOKBACK_BARS // 4)).max()
    out["dd"] = out["px"] / roll_max - 1.0

    return out


def _merge_episode_with_dd(episodes: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """
    Align episode anchor ts to nearest price ts (asof merge).
    """
    ep = episodes.sort_values("ts").copy()
    pr = prices.sort_values("ts").copy()
    merged = pd.merge_asof(ep, pr[["ts", "dd"]], on="ts", direction="backward")
    return merged


def _compute_lift(episodes: pd.DataFrame, test_name: str) -> LiftResult:
    hi = episodes[episodes["group"] == "HIGH"].copy()
    lo = episodes[episodes["group"] == "LOW"].copy()

    n_hi = int(len(hi))
    n_lo = int(len(lo))

    hi_k = int(hi["event"].sum())
    lo_k = int(lo["event"].sum())

    hi_rate = float(hi_k / n_hi) if n_hi else np.nan
    lo_rate = float(lo_k / n_lo) if n_lo else np.nan
    diff = float(hi_rate - lo_rate) if (n_hi and n_lo) else np.nan
    ratio = float(hi_rate / lo_rate) if (n_hi and n_lo and lo_rate > 0) else np.nan

    hi_ci = _wilson_ci(hi_k, n_hi)
    lo_ci = _wilson_ci(lo_k, n_lo)

    boot = _bootstrap_diff(
        hi["event"].to_numpy(dtype=float),
        lo["event"].to_numpy(dtype=float),
        n=BOOTSTRAP_N,
        seed=RNG_SEED,
    )

    return LiftResult(
        test_name=test_name,
        n_hi=n_hi,
        n_lo=n_lo,
        hi_rate=hi_rate,
        lo_rate=lo_rate,
        diff=diff,
        ratio=ratio,
        hi_wilson_lo=float(hi_ci[0]),
        hi_wilson_hi=float(hi_ci[1]),
        lo_wilson_lo=float(lo_ci[0]),
        lo_wilson_hi=float(lo_ci[1]),
        boot_mean=float(boot["mean"]),
        boot_p05=float(boot["p05"]),
        boot_p95=float(boot["p95"]),
    )


def _exclude_top_dd(episodes_dd: pd.DataFrame, top_pct: float) -> pd.DataFrame:
    """
    Exclude episode anchors that fall in the worst drawdown bars (most negative dd).
    """
    df = episodes_dd.copy()
    df = df.dropna(subset=["dd"]).copy()
    # Worst drawdowns = most negative dd -> take quantile at top_pct (e.g., 5%) of dd distribution's LOWER tail.
    cutoff = float(np.quantile(df["dd"], top_pct))
    # dd <= cutoff are the worst bars
    keep = df["dd"] > cutoff
    return df.loc[keep, ["ts", "group", "event", "H"]].copy()


def _exclude_date_ranges(episodes: pd.DataFrame, ranges: List[Tuple[str, str]]) -> pd.DataFrame:
    df = episodes.copy()
    for start, end in ranges:
        s = pd.to_datetime(start)
        e = pd.to_datetime(end)
        df = df[~((df["ts"] >= s) & (df["ts"] <= e))].copy()
    return df


def _subperiod_splits(episodes: pd.DataFrame, k: int = 3) -> Dict[str, pd.DataFrame]:
    """
    Split by time into k equal-size bins by timestamp.
    """
    df = episodes.sort_values("ts").copy()
    if len(df) < k * 10:
        # too small; return one bucket
        return {"subperiod_all": df}

    qs = np.linspace(0, 1, k + 1)
    cuts = [df["ts"].quantile(q) for q in qs]
    buckets = {}
    for i in range(k):
        a = cuts[i]
        b = cuts[i + 1]
        part = df[(df["ts"] >= a) & (df["ts"] <= b)].copy()
        buckets[f"subperiod_{i+1}_of_{k}"] = part
    return buckets


def main() -> None:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    # --- locate files ---
    episodes_path = Path(EPISODES_PATH) if EPISODES_PATH else _auto_detect_episodes_file()

    if PRICES_PATH:
        prices_path = Path(PRICES_PATH)
        prices_raw = _safe_read_csv(prices_path)
        prices_source = str(prices_path)
        print(f"[Step5] Episodes file: {episodes_path}")
        print(f"[Step5] Prices file:   {prices_path}")
    else:
        try:
            prices_path = _auto_detect_prices_file()
            prices_raw = _safe_read_csv(prices_path)
            prices_source = str(prices_path)
            print(f"[Step5] Episodes file: {episodes_path}")
            print(f"[Step5] Prices file:   {prices_path}")
        except FileNotFoundError:
            prices_raw = _load_prices_from_db()
            prices_source = f"db:{DB_PATH.name}"
            print(f"[Step5] Episodes file: {episodes_path}")
            print(f"[Step5] Prices:        from DB {DB_PATH.name}")

    # --- load ---
    episodes_raw = _safe_read_csv(episodes_path)
    episodes = _standardize_episodes(episodes_raw)

    print(f"[Step5] Episode ts range: {episodes['ts'].min()} -> {episodes['ts'].max()}")
    print("[Step5] Episodes per year:")
    print(episodes['ts'].dt.year.value_counts().sort_index().tail(25))

    prices = _prepare_prices(prices_raw)

    # --- join episodes with drawdown ---
    episodes_dd = _merge_episode_with_dd(episodes, prices)

    results: List[LiftResult] = []

    # Baseline (should match Step 4 approximately if same episode file)
    results.append(_compute_lift(episodes, "baseline_step4_episode_sample"))

    # 5A: Exclude worst drawdown bars (top 5% most negative)
    ep_no_dd = _exclude_top_dd(episodes_dd, EXCLUDE_DD_TOP_PCT)
    results.append(_compute_lift(ep_no_dd, f"exclude_worst_drawdown_top_{int(EXCLUDE_DD_TOP_PCT*100)}pct"))

    # 5B: Exclude 2008 explicitly (full year)
    ep_no_2008 = _exclude_date_ranges(episodes, [("2008-01-01", "2008-12-31")])
    results.append(_compute_lift(ep_no_2008, "exclude_2008"))

    # 5C: Exclude 2020 explicitly (COVID crash year)
    ep_no_2020 = _exclude_date_ranges(episodes, [("2020-01-01", "2020-12-31")])
    results.append(_compute_lift(ep_no_2020, "exclude_2020"))

    # 5D: Exclude both 2008 and 2020
    ep_no_2008_2020 = _exclude_date_ranges(episodes, [("2008-01-01", "2008-12-31"), ("2020-01-01", "2020-12-31")])
    results.append(_compute_lift(ep_no_2008_2020, "exclude_2008_and_2020"))

    # 5E: Subperiod splits (3 bins)
    splits = _subperiod_splits(episodes, k=3)
    for name, part in splits.items():
        results.append(_compute_lift(part, name))

    # --- save outputs ---
    out_csv = VALIDATION_DIR / "step5_crisis_concentration_summary.csv"
    out_json = VALIDATION_DIR / "step5_crisis_concentration_summary.json"

    df_out = pd.DataFrame([asdict(r) for r in results])
    df_out.to_csv(out_csv, index=False)

    payload = {
        "episodes_file": str(episodes_path),
        "prices_file": prices_source,
        "dd_lookback_bars": DD_LOOKBACK_BARS,
        "exclude_dd_top_pct": EXCLUDE_DD_TOP_PCT,
        "bootstrap_n": BOOTSTRAP_N,
        "rng_seed": RNG_SEED,
        "results": [asdict(r) for r in results],
    }
    out_json.write_text(json.dumps(payload, indent=2))

    # --- print compact console summary ---
    print("\n=== Step 5 Summary (key rows) ===")
    show_cols = [
        "test_name", "n_hi", "n_lo", "hi_rate", "lo_rate", "diff", "ratio",
        "boot_p05", "boot_p95"
    ]
    with pd.option_context("display.max_rows", 50, "display.max_columns", 50, "display.width", 140):
        print(df_out[show_cols])

    print(f"\nSaved:\n- {out_csv}\n- {out_json}\n")


if __name__ == "__main__":
    main()

