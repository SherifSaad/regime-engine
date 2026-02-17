# scripts/validate_escalation_predictive.py
# Tests whether high escalation scores precede worse forward returns / higher drawdown odds.

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from scipy.stats import mannwhitneyu  # type: ignore
    SCIPY_OK = True
except Exception:
    SCIPY_OK = False


ROOT = Path(__file__).resolve().parents[1]
DATA_SPY = ROOT / "data" / "spy_sample.csv"
ESCALATION = ROOT / "validation_outputs" / "escalation_score_daily.csv"
OUTDIR = ROOT / "validation_outputs"

HORIZONS = [5, 10, 20, 60]
TAILS = [-0.03, -0.05, -0.10, -0.20]  # forward return thresholds
QUANTILES = [0.90, 0.95, 0.975]       # escalation cutoffs


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")


def _to_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=False).dt.tz_localize(None)


def load_price() -> pd.DataFrame:
    _require(DATA_SPY)
    df = pd.read_csv(DATA_SPY)
    if "Date" not in df.columns:
        raise ValueError("data/spy_sample.csv must have a 'Date' column")
    df["Date"] = _to_datetime(df["Date"])
    # Try common close field names
    close_col = None
    for c in ["Adj Close", "Adj_Close", "Close", "close", "adj_close", "AdjClose"]:
        if c in df.columns:
            close_col = c
            break
    if close_col is None:
        raise ValueError("spy_sample.csv must have a Close/Adj Close column")
    df = df[["Date", close_col]].rename(columns={close_col: "Close"}).dropna()
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def load_escalation() -> pd.DataFrame:
    _require(ESCALATION)
    df = pd.read_csv(ESCALATION)
    if "date" not in df.columns:
        raise ValueError("escalation_score_daily.csv must have 'date' column")
    if "escalation_score" not in df.columns:
        # allow "score" as fallback
        if "score" in df.columns:
            df = df.rename(columns={"score": "escalation_score"})
        else:
            raise ValueError("escalation_score_daily.csv must have 'escalation_score' (or 'score') column")
    df["date"] = _to_datetime(df["date"])
    # optional context fields
    keep = ["date", "escalation_score"]
    for c in ["flag95", "flag975", "regime_label"]:
        if c in df.columns:
            keep.append(c)
    df = df[keep].dropna(subset=["date", "escalation_score"]).sort_values("date").reset_index(drop=True)
    return df


def add_forward_returns(px: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    df = px.copy()
    for h in horizons:
        df[f"fwd_{h}d"] = df["Close"].shift(-h) / df["Close"] - 1.0
    return df


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    # Cliff's delta: P(a > b) - P(a < b)
    # O(n*m) but our samples are manageable
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) == 0 or len(b) == 0:
        return np.nan
    gt = 0
    lt = 0
    for x in a:
        gt += np.sum(x > b)
        lt += np.sum(x < b)
    denom = len(a) * len(b)
    return (gt - lt) / denom if denom else np.nan


def mw_pvalue(a: np.ndarray, b: np.ndarray) -> float:
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if (len(a) == 0) or (len(b) == 0) or (not SCIPY_OK):
        return np.nan
    # two-sided Mann-Whitney U
    return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)


@dataclass
class Row:
    quantile: float
    horizon_days: int
    cutoff: float
    n_hi: int
    n_lo: int
    hi_mean: float
    lo_mean: float
    hi_median: float
    lo_median: float
    hi_neg_rate: float
    lo_neg_rate: float
    mw_pvalue: float
    cliffs_delta: float
    tail_thresh: float
    hi_tail_rate: float
    lo_tail_rate: float


def compute_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict] = []
    # df must include escalation_score + fwd_*d columns
    for q in QUANTILES:
        cutoff = float(df["escalation_score"].quantile(q))
        hi_mask = df["escalation_score"] >= cutoff

        for h in HORIZONS:
            col = f"fwd_{h}d"
            d = df.dropna(subset=[col, "escalation_score"]).copy()
            hi = d.loc[hi_mask.reindex(d.index, fill_value=False), col].to_numpy(dtype=float)
            lo = d.loc[~hi_mask.reindex(d.index, fill_value=False), col].to_numpy(dtype=float)

            for tail in TAILS:
                hi_tail = float(np.mean(hi <= tail)) if len(hi) else np.nan
                lo_tail = float(np.mean(lo <= tail)) if len(lo) else np.nan

                rows.append({
                    "quantile": q,
                    "cutoff": cutoff,
                    "horizon_days": h,
                    "tail_threshold": tail,
                    "n_hi": int(len(hi)),
                    "n_lo": int(len(lo)),
                    "hi_mean": float(np.nanmean(hi)) if len(hi) else np.nan,
                    "lo_mean": float(np.nanmean(lo)) if len(lo) else np.nan,
                    "hi_median": float(np.nanmedian(hi)) if len(hi) else np.nan,
                    "lo_median": float(np.nanmedian(lo)) if len(lo) else np.nan,
                    "hi_neg_rate": float(np.mean(hi < 0)) if len(hi) else np.nan,
                    "lo_neg_rate": float(np.mean(lo < 0)) if len(lo) else np.nan,
                    "mw_pvalue": mw_pvalue(hi, lo),
                    "cliffs_delta": cliffs_delta(hi, lo),
                    "hi_tail_rate": hi_tail,
                    "lo_tail_rate": lo_tail,
                })

    return pd.DataFrame(rows)


def compute_hit_rate_for_drawdowns(px: pd.DataFrame, esc: pd.DataFrame, lookahead_td: int = 60) -> pd.DataFrame:
    """
    Event-like precision check:
    - Define a "downside event" as: within next lookahead_td trading days, min fwd return <= threshold.
    - Define a "warning day" as: escalation_score above q-cutoff on that day.
    Then compute precision/recall for each (q, threshold).
    """
    df = px.merge(esc, left_on="Date", right_on="date", how="inner").drop(columns=["date"])
    # Build min forward return in the next lookahead_td
    # (use forward returns from Close shifted)
    close = df["Close"].to_numpy(dtype=float)
    n = len(df)
    min_fwd = np.full(n, np.nan, dtype=float)

    for i in range(n):
        j = min(n - 1, i + lookahead_td)
        if i == j:
            continue
        # forward returns from i to each future day k in (i+1..j)
        future = close[i+1:j+1] / close[i] - 1.0
        if future.size:
            min_fwd[i] = float(np.min(future))

    df["min_fwd_lookahead"] = min_fwd

    out_rows: List[Dict] = []
    for q in QUANTILES:
        cutoff = float(df["escalation_score"].quantile(q))
        warn = df["escalation_score"] >= cutoff

        for thr in [-0.10, -0.20]:
            event = df["min_fwd_lookahead"] <= thr

            tp = int(np.sum(warn & event))
            fp = int(np.sum(warn & ~event))
            fn = int(np.sum(~warn & event))
            tn = int(np.sum(~warn & ~event))

            precision = tp / (tp + fp) if (tp + fp) else np.nan
            recall = tp / (tp + fn) if (tp + fn) else np.nan

            out_rows.append({
                "quantile": q,
                "cutoff": cutoff,
                "lookahead_trading_days": lookahead_td,
                "event_threshold": thr,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "warn_days": int(np.sum(warn)),
                "event_days": int(np.sum(event)),
            })

    return pd.DataFrame(out_rows)


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)

    px = load_price()
    esc = load_escalation()

    px = add_forward_returns(px, HORIZONS)

    df = px.merge(esc, left_on="Date", right_on="date", how="inner").drop(columns=["date"])
    stats = compute_stats(df)
    stats_path = OUTDIR / "escalation_predictive_stats.csv"
    stats.to_csv(stats_path, index=False)

    # Event-like precision/recall for big drawdowns
    pr = compute_hit_rate_for_drawdowns(px, esc, lookahead_td=60)
    pr_path = OUTDIR / "escalation_warning_precision.csv"
    pr.to_csv(pr_path, index=False)

    print("DONE")
    print(f"Predictive stats: {stats_path}")
    print(f"Precision/recall: {pr_path}")
    print(f"SciPy: {SCIPY_OK} (Mann–Whitney p-values {'enabled' if SCIPY_OK else 'disabled'})")

    # quick console peek: 95% quantile, 20d horizon, tail -10%
    peek = stats[(stats["quantile"] == 0.95) & (stats["horizon_days"] == 20) & (stats["tail_threshold"] == -0.10)]
    if len(peek):
        r = peek.iloc[0]
        print("\nPEEK (q=0.95, horizon=20d, tail<=-10%):")
        print(f"cutoff={r['cutoff']:.3f}  hi_tail={r['hi_tail_rate']:.3f}  lo_tail={r['lo_tail_rate']:.3f}  mw_p={r['mw_pvalue']}")


if __name__ == "__main__":
    main()
